#!/usr/bin/env python3
"""
Utility functions for OpenAI API interactions.

This module provides helper functions to abstract the differences between
OpenAI's chat completions, Responses API, and legacy completions endpoints,
allowing for dynamic endpoint selection based on the model being used.
"""
from typing import Dict, Any, List, Optional
import os
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional: used only for selective retry classification when the OpenAI SDK
# raises transport exceptions (it uses httpx under the hood).
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from global_config import get_openai_endpoint_type
from model_limits import default_max_output_tokens, clamp_output_tokens

# Constants for logging and monitoring
TOKEN_LIMIT_WARNING_THRESHOLD = 0.95  # Warn when using >95% of max tokens
ERROR_CONTEXT_MESSAGE_COUNT = 3  # Number of recent messages to log on error
LOG_PREVIEW_LENGTH = 500  # Maximum characters to preview in logs


class StreamedResponse:
    """Lightweight stand-in for a Responses API object when using stream=True.

    Downstream code expects `.output_text` and sometimes `.model_dump_json()`.
    We provide minimal compatibility so the pipeline can remain unchanged.
    """

    def __init__(self, output_text: str, status: str = "completed", response_id: str | None = None):
        self.output_text = output_text or ""
        self.status = status
        self.id = response_id
        self.incomplete_details = None
        self.usage = None

    def model_dump(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "output_text": self.output_text,
        }

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(), indent=indent)



def _validate_params_for_endpoint(endpoint_type: str, params: Dict[str, Any]) -> None:
    """Fail fast on parameter/endpoint mismatches to avoid paid API attempts.

    The OpenAI Python SDK will raise TypeError when unsupported keyword arguments
    are passed (e.g., `response_format` passed to the Responses API). Those
    failures still cost time, and in some pipelines may already have incurred
    other paid calls. We therefore validate the parameter set locally.
    """
    if endpoint_type == "responses":
        if "response_format" in params:
            raise ValueError(
                "Unsupported parameter for Responses API: 'response_format'. "
                "Use 'text.format' instead."
            )
        if "temperature" in params:
            raise ValueError(
                "Unsupported parameter for Responses API: 'temperature'. "
                "Responses API does not support temperature."
            )
    elif endpoint_type == "chat":
        if "text" in params:
            raise ValueError(
                "Unsupported parameter for Chat Completions API: 'text'. "
                "Use 'response_format' instead for structured output."
            )
        if "input" in params:
            raise ValueError(
                "Unsupported parameter for Chat Completions API: 'input'. "
                "Chat completions uses 'messages' instead."
            )
        if "prompt" in params:
            raise ValueError(
                "Unsupported parameter for Chat Completions API: 'prompt'. "
                "Chat completions uses 'messages' instead."
            )
    elif endpoint_type == "completion":
        if "messages" in params:
            raise ValueError(
                "Unsupported parameter for Legacy Completions API: 'messages'. "
                "Use 'prompt' instead."
            )
        if "response_format" in params:
            raise ValueError(
                "Unsupported parameter for Legacy Completions API: 'response_format'. "
                "Legacy completions does not support structured output."
            )
        if "text" in params:
            raise ValueError(
                "Unsupported parameter for Legacy Completions API: 'text'. "
                "Legacy completions does not support 'text.format'."
            )


def _sanitize_for_logging(text: str, max_length: int = LOG_PREVIEW_LENGTH) -> str:
    """Sanitize text for safe logging by truncating and removing sensitive info."""
    if not text:
        return ""
    # Truncate long text
    if len(text) > max_length:
        text = text[:max_length] + "... [truncated]"
    return text


def _messages_to_input(messages: List[Dict[str, Any]]) -> str:
    """Convert chat messages to a single input string for Responses API."""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Handle multi-modal content (text, images, etc.)
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(f"{role}: {item.get('text', '')}")
        else:
            parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


def create_openai_completion(
    client: OpenAI,
    model: str,
    messages: Optional[List[Dict[str, Any]]] = None,
    prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    max_completion_tokens: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    json_mode: bool = False,
    output_file: Optional[str] = None,
    **kwargs
) -> Any:
    """Create a completion using the appropriate OpenAI endpoint based on model.

    Args:
        client: OpenAI client instance
        model: Model name to use
        messages: Chat messages (for chat completion models)
        prompt: Text prompt (for legacy completion models)
        temperature: Temperature for sampling (chat completion models only)
        max_tokens: Deprecated token limit parameter (use max_completion_tokens instead)
        max_completion_tokens: Maximum tokens for completion (preferred parameter)
        tools: Tools to use (for supported models)
        json_mode: Whether to enforce valid JSON output
        output_file: Optional file path to save response
        **kwargs: Additional parameters passed to API

    Returns:
        OpenAI API response
    """
    endpoint_type = get_openai_endpoint_type(model)

    # Transport-level retries are OFF by default to preserve the pipeline's
    # single-request-per-pass behavior. If you run in CI and occasionally hit
    # transient disconnects (e.g., httpx.RemoteProtocolError), you can enable a
    # small number of retries via env without changing code.
    transport_retries = int(os.getenv("OPENAI_TRANSPORT_RETRIES", "0"))
    transport_retry_sleep_s = float(os.getenv("OPENAI_TRANSPORT_RETRY_SLEEP_S", "1.5"))

    def _is_retryable_transport_error(e: Exception) -> bool:
        if httpx is None:
            return False
        retryable = (
            getattr(httpx, "RemoteProtocolError", tuple()),
            getattr(httpx, "ReadTimeout", tuple()),
            getattr(httpx, "ConnectError", tuple()),
            getattr(httpx, "ReadError", tuple()),
            getattr(httpx, "WriteError", tuple()),
            getattr(httpx, "ProtocolError", tuple()),
        )
        return isinstance(e, retryable)

    def _with_transport_retries(fn):
        attempts = max(1, 1 + transport_retries)
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as e:
                last_exc = e
                if attempt >= attempts or not _is_retryable_transport_error(e):
                    raise
                logger.warning(
                    "Transient transport error from OpenAI SDK (attempt %d/%d): %s",
                    attempt,
                    attempts,
                    str(e),
                )
                time.sleep(transport_retry_sleep_s)
        if last_exc:
            raise last_exc
        raise RuntimeError("Unexpected retry wrapper state")

    transport_backoff_s = float(os.getenv("OPENAI_TRANSPORT_BACKOFF", "2.0"))

    def _is_retryable_transport_error(exc: Exception) -> bool:
        if httpx is None:
            return False
        retryables = (
            getattr(httpx, "RemoteProtocolError", ()),
            getattr(httpx, "ReadTimeout", ()),
            getattr(httpx, "ConnectTimeout", ()),
            getattr(httpx, "ConnectError", ()),
            getattr(httpx, "ReadError", ()),
        )
        try:
            return isinstance(exc, retryables)
        except Exception:
            return False

    if endpoint_type == "responses":
        # Use /v1/responses endpoint (Responses API)
        logger.info(f"Using Responses API endpoint for model: {model}")

        # Convert messages to input string
        if messages:
            # For responses API, we need to convert messages to a single input string
            input_text = _messages_to_input(messages)
        elif prompt:
            input_text = prompt
        else:
            raise ValueError("messages or prompt is required for responses models")

        # Build parameters for responses endpoint
        # Note: Responses API does not support 'temperature' parameter
        params = {
            "model": model,
            "input": input_text,  # Responses API uses 'input' not 'prompt'
        }

        # Use max_output_tokens (Responses API parameter)
        # If caller didn't specify, default to the model maximum. If caller overshoots, clamp.
        requested_out = max_completion_tokens or max_tokens
        desired_out = default_max_output_tokens(model, requested_out)
        if desired_out:
            params["max_output_tokens"] = clamp_output_tokens(model, desired_out)

        # Reasoning controls are model-dependent. Only include them when the caller
        # explicitly provides a `reasoning` object to avoid 400s on models that
        # don't support it.
        if "reasoning" in kwargs:
            params["reasoning"] = kwargs.pop("reasoning")

        # Add tools if provided
        if tools:
            params["tools"] = tools

        # Enforce valid JSON output when requested
        # NOTE: Responses API uses `text.format`. Chat Completions uses `response_format`.
        if json_mode:
            has_web_search = bool(tools) and any((t or {}).get("type") == "web_search" for t in tools)
            if has_web_search:
                logger.warning("JSON mode requested but web_search tool is present; disabling JSON mode for this request.")
            else:
                params.setdefault("text", {})
                # Ensure nested format structure per Responses API
                params["text"].setdefault("format", {"type": "json_object"})

        # Add any additional kwargs
        params.update(kwargs)

        # Log request details
        content_preview = _sanitize_for_logging(str(input_text), LOG_PREVIEW_LENGTH)
        logger.info(f"Request params: model={model}, max_output_tokens={params.get('max_output_tokens', 'N/A')}")
        logger.info(f"Input preview: {content_preview}")
        if tools:
            logger.info(f"Tools: {tools}")

        _validate_params_for_endpoint("responses", params)

        # Streaming is strongly recommended for very large outputs; it reduces the risk of
        # upstream proxies closing an idle connection while the model is still generating.
        # It is still a single request to the API; results are delivered incrementally.
        stream_pref = params.pop("stream", None)
        env_stream = str(os.getenv("OPENAI_STREAM_RESPONSES", "true")).strip().lower() in ("1", "true", "yes", "y")
        requested_for_stream = params.get("max_output_tokens")
        if stream_pref is None:
            # Default: stream when large outputs are requested, or when explicitly enabled via env.
            stream = env_stream or (isinstance(requested_for_stream, int) and requested_for_stream >= 4096)
        else:
            stream = bool(stream_pref)

        if stream:
            params_stream = dict(params)
            params_stream['stream'] = True
            out_parts: List[str] = []
            response_id: Optional[str] = None
            try:
                stream_iter = _with_transport_retries(lambda: client.responses.create(**params_stream))
                for ev in stream_iter:
                    etype = getattr(ev, 'type', None)
                    if etype is None and isinstance(ev, dict):
                        etype = ev.get('type')
                    if etype == 'response.created':
                        rid = getattr(ev, 'response', None)
                        if rid is None and isinstance(ev, dict):
                            rid = ev.get('response')
                        try:
                            response_id = getattr(rid, 'id', None) if rid is not None else response_id
                        except Exception:
                            pass
                    elif etype == 'response.output_text.delta':
                        delta = getattr(ev, 'delta', None)
                        if delta is None and isinstance(ev, dict):
                            delta = ev.get('delta')
                        if isinstance(delta, str) and delta:
                            out_parts.append(delta)
            except Exception as e:
                # Single-request policy: do not retry; surface the failure.
                logger.exception('Streaming Responses API request failed: %s', str(e))
                raise
            return StreamedResponse(output_text=''.join(out_parts), status='completed', response_id=response_id)
        else:
            response = _with_transport_retries(lambda: client.responses.create(**params))

        # Persist the full Responses API payload (including tool calls/results) for later analysis
        if output_file:
            try:
                Path(str(output_file) + '.response.json').write_text(response.model_dump_json(indent=2), encoding='utf-8')
            except Exception as e:
                logger.warning(f'Failed to write full response JSON to disk: {e}')

        # Log response details
        logger.info("Response received from OpenAI Responses API")
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Response attributes: {dir(response)}")

        # Log token usage if available
        if hasattr(response, 'usage'):
            logger.info(f"Token usage: {response.usage}")

        # Log response structure
        if hasattr(response, 'model_dump'):
            try:
                response_dict = response.model_dump()
                logger.info(f"Response structure keys: {list(response_dict.keys())}")

                # Log usage details if present
                if 'usage' in response_dict:
                    usage = response_dict['usage']
                    logger.info(f"Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                    logger.info(f"Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                    logger.info(f"Total tokens: {usage.get('total_tokens', 'N/A')}")

                # Log output structure
                if 'output' in response_dict and response_dict['output']:
                    logger.info(f"Output count: {len(response_dict['output'])}")
            except Exception as e:
                logger.warning(f"Error analyzing response structure: {e}")

        return response

    else:
        # Use /v1/chat/completions endpoint
        logger.info(f"Using chat completion endpoint for model: {model}")

        if messages is None:
            raise ValueError("messages are required for chat completion models")

        # Build parameters for chat completion endpoint
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        # Use max_completion_tokens for chat endpoint (preferred parameter)
        # If caller didn't specify, default to the model maximum. If caller overshoots, clamp.
        requested_out = max_completion_tokens or max_tokens
        desired_out = default_max_output_tokens(model, requested_out)
        if desired_out:
            params["max_completion_tokens"] = clamp_output_tokens(model, desired_out)
        elif max_tokens:
            # Keep backward compatibility warning if max_tokens was explicitly provided.
            logger.warning("Using deprecated 'max_tokens' param for chat completion. Please use 'max_completion_tokens' instead.")

        # Add tools if provided
        if tools:
            params["tools"] = tools

        # Enforce valid JSON output when requested
        # NOTE: The Chat Completions API uses `response_format` (NOT `text.format`, which is Responses API-only).
        if json_mode:
            has_web_search = bool(tools) and any((t or {}).get("type") == "web_search" for t in tools)
            if has_web_search:
                logger.warning("JSON mode requested but web_search tool is present; disabling JSON mode for this request.")
            else:
                params["response_format"] = {"type": "json_object"}

        # Add any additional kwargs
        params.update(kwargs)

        # Log request details
        last_message = messages[-1] if messages else {}
        last_content = str(last_message.get('content', ''))
        content_preview = _sanitize_for_logging(last_content, LOG_PREVIEW_LENGTH)
        logger.info(
            f"Request params: model={model}, max_completion_tokens={params.get('max_completion_tokens', 'N/A')}, temperature={temperature}"
        )
        logger.info(f"Messages count: {len(messages)}, Last message preview: {content_preview}")
        if tools:
            logger.info(f"Tools: {tools}")

        _validate_params_for_endpoint("chat", params)
        response = _with_transport_retries(lambda: client.chat.completions.create(**params))

        # Log response details
        logger.info("Response received from OpenAI Chat Completions API")
        logger.info(f"Response type: {type(response)}")

        # Log token usage if available
        if hasattr(response, 'usage'):
            logger.info(f"Token usage: {response.usage}")

        # Write response to file if requested
        if output_file:
            try:
                Path(str(output_file) + '.response.json').write_text(json.dumps(response.model_dump(), indent=2), encoding='utf-8')
            except Exception as e:
                logger.warning(f'Failed to write full response JSON to disk: {e}')

        return response


def _get_incomplete_reason(response: Any) -> Optional[str]:
    """Extract incomplete reason from a Responses API response."""
    try:
        inc = getattr(response, "incomplete_details", None)
        if hasattr(inc, "reason"):
            return inc.reason
        if isinstance(inc, dict):
            return inc.get("reason")
    except Exception:
        pass
    return None


def extract_completion_text(response: Any, model: Optional[str] = None) -> str:
    """Extract text content from OpenAI API response across endpoints.

    Supports both:
    - Responses API output (response.output_text)
    - Chat Completions (response.choices[0].message.content)
    """
    # Handle Responses API
    if hasattr(response, 'output_text'):
        # Handle incomplete Responses API outputs.
        # Default behavior: DO NOT hard-fail when output is cut off by max_output_tokens.
        # This enables upstream callers to stitch multi-part outputs ("continue") without a full run failure.
        if hasattr(response, 'status') and response.status == 'incomplete':
            reason = _get_incomplete_reason(response)
            logger.warning("Response status is 'incomplete' (reason: %s)" % reason)
            fail_fast = str(os.getenv('FAIL_ON_INCOMPLETE', 'false')).strip().lower() in ('1','true','yes','y')
            if fail_fast:
                raise ValueError(
                    "Response is incomplete (reason: %s). This is treated as a hard failure because FAIL_ON_INCOMPLETE=true. "
                    "Reduce requested output (max_words), tighten prompts, or increase max_output_tokens appropriately." % reason
                )

        return response.output_text or ""

    # Handle Chat Completions API
    if hasattr(response, 'choices') and response.choices:
        choice = response.choices[0]
        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
            return choice.message.content or ""
        if hasattr(choice, 'text'):
            return choice.text or ""

    # Fallback for other response structures
    logger.warning(f"Unable to extract text from response type: {type(response)}")
    return ""
