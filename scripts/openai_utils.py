#!/usr/bin/env python3
"""
Utility functions for OpenAI API interactions.

This module provides helper functions to abstract the differences between
OpenAI's chat completions, Responses API, and legacy completions endpoints,
allowing for dynamic endpoint selection based on the model being used.
"""
from typing import Dict, Any, List, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from global_config import get_openai_endpoint_type

# Constants for logging and monitoring
TOKEN_LIMIT_WARNING_THRESHOLD = 0.95  # Warn when using >95% of max tokens
ERROR_CONTEXT_MESSAGE_COUNT = 3  # Number of recent messages to log on error
LOG_PREVIEW_LENGTH = 500  # Maximum characters to preview in logs


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
                "Use params['text'] = {'format': {'type': 'json_object'}} instead."
            )
        if "input" not in params:
            raise ValueError("Responses API request is missing required parameter: 'input'")
        # Defensive: Chat-only field
        if "messages" in params:
            raise ValueError("Responses API does not accept 'messages' directly; pass 'input' text instead")

    elif endpoint_type == "chat":
        if "text" in params:
            raise ValueError(
                "Unsupported parameter for Chat Completions: 'text'. "
                "Use params['response_format'] = {'type': 'json_object'} instead."
            )
        if "messages" not in params:
            raise ValueError("Chat Completions request is missing required parameter: 'messages'")

    elif endpoint_type == "completion":
        if "prompt" not in params:
            raise ValueError("Completions request is missing required parameter: 'prompt'")

def create_openai_completion(
    client: 'OpenAI',
    model: str,
    messages: Optional[List[Dict[str, str]]] = None,
    prompt: Optional[str] = None,
    output_file: Optional[str] = None,
    max_tokens: Optional[int] = None,
    max_completion_tokens: Optional[int] = None,
    temperature: float = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    json_mode: bool = False,
    **kwargs
) -> Any:
    """
    Create an OpenAI completion using the appropriate endpoint based on the model.
    
    This function dynamically selects between chat completions, responses API,
    and completions endpoints based on the model configuration.
    
    Args:
        client: OpenAI client instance
        model: Model name (e.g., "gpt-5.2-pro", "gpt-4")
        messages: Messages array for chat completions (required for chat/responses models)
        prompt: Prompt string for completions (required for completion models)
        max_tokens: Maximum tokens for completion models
        max_completion_tokens: Maximum tokens for chat completion and responses models
        temperature: Sampling temperature
        tools: Tools array for chat completions and responses (e.g., web_search)
        **kwargs: Additional parameters to pass to the API
        
    Returns:
        OpenAI API response object
        
    Raises:
        ValueError: If required parameters are missing for the endpoint type
    """
    endpoint_type = get_openai_endpoint_type(model)
    
    # Log what we're sending to OpenAI
    logger.info("=" * 80)
    logger.info(f"OpenAI API Request - Model: {model}, Endpoint: {endpoint_type}")
    logger.info("=" * 80)
    
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
        if max_completion_tokens:
            params["max_output_tokens"] = max_completion_tokens
        elif max_tokens:
            params["max_output_tokens"] = max_tokens
        
        # Reasoning controls are model-dependent. Only include them when the caller
        # explicitly provides a `reasoning` object to avoid 400s on models that
        # do not support `reasoning.effort`.
        if "reasoning" in kwargs and kwargs["reasoning"] is not None:
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
                params["text"] = {"format": {"type": "json_object"}}
        
        # Add streaming if requested
        if "stream" in kwargs:
            params["stream"] = kwargs.pop("stream")
        
        # Add any additional kwargs
        params.update(kwargs)
        
        # Log request details (truncate input if too long)
        input_preview = _sanitize_for_logging(input_text, LOG_PREVIEW_LENGTH)
        logger.info(f"Request params: model={model}, max_output_tokens={params.get('max_output_tokens', 'N/A')}")
        logger.info(f"Input preview: {input_preview}")
        if tools:
            logger.info(f"Tools: {tools}")
        
        # Fail fast on parameter mismatches before making a paid call.
        _validate_params_for_endpoint(endpoint_type, params)

        response = client.responses.create(**params)

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
                    
                    # Check if we hit the limit
                    completion_tokens = usage.get('completion_tokens', 0)
                    max_output = params.get('max_output_tokens', 0)
                    if completion_tokens >= max_output * TOKEN_LIMIT_WARNING_THRESHOLD:
                        logger.warning(f"Response may be truncated: used {completion_tokens} of {max_output} max_output_tokens")
            except Exception as e:
                logger.warning(f"Could not dump response: {e}")
        
        return response
    
    elif endpoint_type == "completion":
        # Use /v1/completions endpoint
        logger.info(f"Using completion endpoint for model: {model}")
        
        # Convert messages to prompt if needed
        if prompt is None and messages:
            prompt = _messages_to_prompt(messages)
        
        if prompt is None:
            raise ValueError("prompt is required for completion models")
        
        # Build parameters for completion endpoint
        params = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
        }
        
        # Use max_tokens (not max_completion_tokens) for completion endpoint
        # Note: Completion endpoint only accepts 'max_tokens', so we translate both parameter names
        if max_completion_tokens:
            params["max_tokens"] = max_completion_tokens
        elif max_tokens:
            params["max_tokens"] = max_tokens
        
        # Add any additional kwargs
        params.update(kwargs)
        
        # Note: tools are not supported by completion endpoint
        if tools:
            logger.info(f"Tools parameter not supported by completion endpoint for model {model} - tools will not be used")
        
        # Log request details
        prompt_preview = _sanitize_for_logging(prompt, LOG_PREVIEW_LENGTH)
        logger.info(f"Request params: model={model}, max_tokens={params.get('max_tokens', 'N/A')}, temperature={temperature}")
        logger.info(f"Prompt preview: {prompt_preview}")
        
        _validate_params_for_endpoint("completion", params)
        response = client.completions.create(**params)
        
        # Log response details
        logger.info("Response received from OpenAI Completions API")
        logger.info(f"Response type: {type(response)}")
        
        # Log token usage if available
        if hasattr(response, 'usage'):
            logger.info(f"Token usage: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
        
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
        # Note: Chat endpoint prefers 'max_completion_tokens', so we translate 'max_tokens' if provided
        if max_completion_tokens:
            params["max_completion_tokens"] = max_completion_tokens
        elif max_tokens:
            # Log deprecation warning when caller uses old parameter name
            logger.warning(f"Using deprecated 'max_tokens' parameter for chat completion. Please use 'max_completion_tokens' instead.")
            params["max_completion_tokens"] = max_tokens
        
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
        logger.info(f"Request params: model={model}, max_completion_tokens={params.get('max_completion_tokens', 'N/A')}, temperature={temperature}")
        logger.info(f"Messages count: {len(messages)}, Last message preview: {content_preview}")
        if tools:
            logger.info(f"Tools: {tools}")
        
        _validate_params_for_endpoint("chat", params)
        response = client.chat.completions.create(**params)
        
        # Log response details
        logger.info("Response received from OpenAI Chat Completions API")
        logger.info(f"Response type: {type(response)}")
        
        # Log token usage if available
        if hasattr(response, 'usage'):
            logger.info(f"Token usage: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
        
        return response


def _get_incomplete_reason(response: Any) -> str:
    """
    Extract the reason for an incomplete response.
    
    Args:
        response: OpenAI API response object with incomplete status
        
    Returns:
        Reason string (e.g., 'max_output_tokens', 'length')
    """
    reason = 'max_output_tokens'  # default
    if hasattr(response, 'incomplete_details'):
        incomplete_details = response.incomplete_details
        logger.debug(f"Incomplete details: {incomplete_details}")
        if hasattr(incomplete_details, 'reason'):
            reason = incomplete_details.reason
        elif isinstance(incomplete_details, dict):
            reason = incomplete_details.get('reason', 'max_output_tokens')
    return reason


def extract_completion_text(response: Any, model: str) -> str:
    """
    Extract the completion text from an OpenAI API response.
    
    Handles chat completion, responses API, and completion response formats.
    
    Args:
        response: OpenAI API response object
        model: Model name used for the request
        
    Returns:
        Extracted text content from the response
    """
    endpoint_type = get_openai_endpoint_type(model)
    
    # Log what we're extracting from
    logger.info(f"Extracting text from {endpoint_type} endpoint response")
    logger.info(f"Response type: {type(response)}")
    logger.info(f"Response has attributes: {', '.join([a for a in dir(response) if not a.startswith('_')])}")
    
    if endpoint_type == "responses":
        # Responses API response format
        # Log the actual response structure for debugging
        logger.info("Attempting to extract from Responses API response...")
        
        # Fail fast on incomplete Responses API outputs to avoid additional paid retries.
        # If the response is incomplete (including reason=max_output_tokens), we treat it as a hard failure.
        if hasattr(response, 'status') and response.status == 'incomplete':
            reason = _get_incomplete_reason(response)
            logger.warning("Response status is 'incomplete' (reason: %s)" % reason)
            raise ValueError(
                "Response is incomplete (reason: %s). This is treated as a hard failure to prevent additional spend. "
                "Reduce requested output (max_words), tighten prompts, or increase max_output_tokens appropriately." % reason
            )

        # Try multiple extraction methods for Responses API
        # IMPORTANT: Some SDK convenience properties (e.g., output_text) may throw when the
        # response is incomplete (reason: max_output_tokens). Prefer model_dump() first.

        # Method 1: Parse `model_dump()` (robust across SDK versions / output modes)
        # This handles cases where the model returns structured output blocks (e.g., output_json)
        # and `output_text` convenience property is empty.
        try:
            if hasattr(response, 'model_dump'):
                dump = response.model_dump()
                if isinstance(dump, dict):
                    out_text = dump.get('output_text')
                    if isinstance(out_text, str) and out_text.strip():
                        text = out_text.strip()
                        logger.info(f"Extracted {len(text)} chars from model_dump().output_text")
                        return text
                    output_list = dump.get('output')
                    if isinstance(output_list, list):
                        collected: List[str] = []
                        for item in output_list:
                            if not isinstance(item, dict):
                                continue
                            # Sometimes text is on the item
                            for k in ('output_text', 'text'):
                                v = item.get(k)
                                if isinstance(v, str) and v.strip():
                                    collected.append(v.strip())
                            # Common structure: item['content'] is a list of blocks
                            content_blocks = item.get('content')
                            if isinstance(content_blocks, list):
                                for blk in content_blocks:
                                    if not isinstance(blk, dict):
                                        continue
                                    # output_text blocks
                                    v = blk.get('text')
                                    if isinstance(v, str) and v.strip():
                                        collected.append(v.strip())
                                        continue
                                    # output_json / structured blocks
                                    for k in ('json', 'data', 'parsed'):
                                        if k in blk and blk.get(k) is not None:
                                            try:
                                                collected.append(json.dumps(blk.get(k), ensure_ascii=False))
                                            except Exception:
                                                collected.append(str(blk.get(k)))
                                            break
                        merged = "\n".join([c for c in collected if c]).strip()
                        if merged:
                            logger.info(f"Extracted {len(merged)} chars from model_dump().output")
                            return merged
        except Exception as e:
            logger.warning(f"model_dump() extraction failed: {e}")

        # Method 1b: Prefer output_text when it is available and non-empty (guarded)
        if hasattr(response, 'output_text'):
            try:
                ot = response.output_text
                logger.info(f"Found output_text attribute, value type: {type(ot)}")
                if ot is not None:
                    text = str(ot)
                    if isinstance(text, str) and text.strip():
                        text = text.strip()
                        logger.info(f"Extracted {len(text)} chars from output_text")
                        return text
                logger.info("output_text is empty; will attempt deeper extraction from response.output")
            except Exception as e:
                logger.warning(f"Accessing output_text raised (likely incomplete response): {e}")

        def _extract_text_from_responses_output(output_obj) -> str:
            """Extract assistant text from Responses API 'output' structures."""
            texts = []
            if output_obj is None:
                return ""
            def to_dict(x):
                if hasattr(x, 'model_dump'):
                    try:
                        return x.model_dump()
                    except Exception:
                        pass
                if hasattr(x, 'dict'):
                    try:
                        return x.dict()
                    except Exception:
                        pass
                return x

            def extract_from_content(content_list):
                if not isinstance(content_list, list):
                    return
                for c in content_list:
                    cd = to_dict(c)
                    if isinstance(cd, dict):
                        # Common case: output_text blocks
                        t = cd.get('text')
                        if isinstance(t, str) and t.strip():
                            texts.append(t.strip())
                            continue

                        # JSON-mode blocks sometimes expose structured payload
                        for k in ('json', 'data', 'parsed'):
                            if k in cd and cd.get(k) is not None:
                                try:
                                    texts.append(json.dumps(cd.get(k), ensure_ascii=False))
                                except Exception:
                                    texts.append(str(cd.get(k)))
                                break
                    else:
                        if hasattr(c, 'text'):
                            t = getattr(c, 'text')
                            if isinstance(t, str) and t.strip():
                                texts.append(t.strip())

            out = to_dict(output_obj)
            if isinstance(out, list):
                for item in out:
                    it = to_dict(item)
                    if isinstance(it, dict):
                        extract_from_content(it.get('content'))
                        t = it.get('output_text')
                        if isinstance(t, str) and t.strip():
                            texts.append(t.strip())
                    else:
                        if hasattr(item, 'content'):
                            extract_from_content(getattr(item, 'content'))
                        if hasattr(item, 'output_text'):
                            t = getattr(item, 'output_text')
                            if isinstance(t, str) and t.strip():
                                texts.append(t.strip())
            elif isinstance(out, dict):
                extract_from_content(out.get('content'))
                t = out.get('output_text') or out.get('text')
                if isinstance(t, str) and t.strip():
                    texts.append(t.strip())

            return "\n".join(texts).strip()

        # Method 2: Parse Responses API output array (robust)
        if hasattr(response, 'output'):
            logger.info(f"Found output attribute, type: {type(response.output)}")
            try:
                text = _extract_text_from_responses_output(response.output)
                if text:
                    logger.info(f"Extracted {len(text)} chars from response.output")
                    return text
            except Exception as e:
                logger.warning(f"Failed to extract from response.output: {e}")
        # Method 3: Try choices format (similar to chat completion)
        if hasattr(response, 'choices'):
            logger.info(f"Found choices attribute with {len(response.choices) if response.choices else 0} choices")
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                logger.info(f"First choice type: {type(choice)}, attributes: {', '.join([a for a in dir(choice) if not a.startswith('_')])}")
                
                if hasattr(choice, 'message'):
                    logger.info(f"Found message in choice")
                    if hasattr(choice.message, 'content'):
                        text = str(choice.message.content).strip()
                        logger.info(f"Extracted {len(text)} chars from choices[0].message.content")
                        return text
                
                if hasattr(choice, 'text'):
                    logger.info(f"Found text in choice")
                    text = str(choice.text).strip()
                    logger.info(f"Extracted {len(text)} chars from choices[0].text")
                    return text
        
        # Log full response structure for debugging
        logger.error("Unable to extract text from Responses API response")
        logger.error(f"Response object: {response}")
        if hasattr(response, 'model_dump'):
            try:
                logger.error(f"Response dump: {response.model_dump()}")
            except Exception as e:
                logger.error(f"Could not dump response: {e}")
        
        raise ValueError(f"Unable to extract text from responses API response. Response type: {type(response)}, Has choices: {hasattr(response, 'choices')}, Has output_text: {hasattr(response, 'output_text')}, Has output: {hasattr(response, 'output')}")
    
    elif endpoint_type == "completion":
        # Completion endpoint response format
        logger.info("Extracting from Completions API response")
        text = response.choices[0].text.strip()
        logger.info(f"Extracted {len(text)} chars from choices[0].text")
        return text
    else:
        # Chat completion endpoint response format
        logger.info("Extracting from Chat Completions API response")
        text = response.choices[0].message.content.strip()
        logger.info(f"Extracted {len(text)} chars from choices[0].message.content")
        return text


def get_finish_reason(response: Any, model: str) -> str:
    """
    Extract the finish reason from an OpenAI API response.
    
    Handles chat completion, responses API, and completion response formats.
    
    Args:
        response: OpenAI API response object
        model: Model name used for the request
        
    Returns:
        Finish reason string (e.g., "stop", "length", etc.)
        Returns "unknown" if finish reason cannot be determined
    """
    endpoint_type = get_openai_endpoint_type(model)
    
    logger.info(f"Getting finish reason from {endpoint_type} endpoint response")
    
    # Try to get finish_reason from various possible locations
    try:
        # Method 1: Standard choices format (works for chat and completion endpoints)
        if hasattr(response, 'choices') and response.choices and len(response.choices) > 0:
            choice = response.choices[0]
            if hasattr(choice, 'finish_reason'):
                reason = choice.finish_reason
                logger.info(f"Finish reason: {reason}")
                return reason
        
        # Method 2: Check for finish_reason at top level (some Responses API variants)
        if hasattr(response, 'finish_reason'):
            reason = response.finish_reason
            logger.info(f"Finish reason (top-level): {reason}")
            return reason
        
        # Method 3: Check for status or similar fields
        if hasattr(response, 'status'):
            status = response.status
            logger.info(f"Status field found: {status}")
            # Map status to finish reason if applicable
            if status in ['complete', 'completed', 'done']:
                return 'stop'
            elif status in ['truncated', 'length_limit', 'incomplete']:
                # All these statuses indicate length/token limits were reached
                if status == 'incomplete':
                    reason = _get_incomplete_reason(response)
                    logger.info(f"Incomplete reason: {reason}")
                return 'length'
        
        # If we can't find finish_reason, log warning and return unknown
        logger.warning(f"Could not find finish_reason in response. Available attributes: {', '.join([a for a in dir(response) if not a.startswith('_')])}")
        return 'unknown'
        
    except Exception as e:
        logger.error(f"Error getting finish reason: {e}")
        return 'unknown'


def _format_messages_as_text(messages: List[Dict[str, str]]) -> str:
    """
    Convert chat messages array to a single text string.
    
    This shared helper formats messages for both Responses API (input parameter)
    and legacy Completions endpoint (prompt parameter).
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        Combined text string with role labels
    """
    parts = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "system":
            parts.append(f"System: {content}")
        elif role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(content)
    
    return "\n\n".join(parts)


def _messages_to_input(messages: List[Dict[str, str]]) -> str:
    """
    Convert chat messages array to input string for Responses API.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        Combined input string formatted for Responses API
    """
    return _format_messages_as_text(messages)


def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    """
    Convert chat messages array to prompt string for legacy Completions endpoint.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content' keys
        
    Returns:
        Combined prompt string
    """
    return _format_messages_as_text(messages)


def _prompt_to_messages(prompt: str) -> List[Dict[str, str]]:
    """
    Convert a prompt string to a messages array for chat completion endpoint.
    
    Args:
        prompt: Prompt string
        
    Returns:
        List of message dictionaries for chat completion
    """
    return [{"role": "user", "content": prompt}]


def _sanitize_for_logging(text: str, max_length: int) -> str:
    """
    Sanitize text for logging by truncating and removing sensitive information.
    
    This function helps prevent exposing sensitive data in logs while still
    providing useful context for debugging.
    
    Args:
        text: Text to sanitize
        max_length: Maximum length before truncation
        
    Returns:
        Sanitized text suitable for logging
    """
    if not text:
        return ""
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    # Note: Additional sanitization could be added here if needed, such as:
    # - Redacting API keys (look for patterns like "sk-...")
    # - Redacting email addresses
    # - Redacting URLs with auth tokens
    # For now, we rely on the caller not passing sensitive data in prompts
    
    return text


def create_openai_streaming_completion(
    client: 'OpenAI',
    model: str,
    messages: Optional[List[Dict[str, str]]] = None,
    prompt: Optional[str] = None,
    max_tokens: Optional[int] = None,
    max_completion_tokens: Optional[int] = None,
    temperature: float = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    output_path: Optional[str] = None,
    flush_threshold: int = 20000,
    json_mode: bool = False,
    return_meta: bool = False,
    **kwargs
) -> Any:
    """
    Create an OpenAI streaming completion using the appropriate endpoint.
    
    This function enables streaming responses which are crucial for long-running
    requests to prevent timeouts and disconnections. Partial output is written
    to a file as it arrives.
    
    Args:
        client: OpenAI client instance
        model: Model name (e.g., "gpt-5.2-pro", "gpt-4")
        messages: Messages array for chat completions
        prompt: Prompt string for completions
        max_tokens: Maximum tokens for completion models
        max_completion_tokens: Maximum tokens for chat/responses models
        temperature: Sampling temperature
        tools: Tools array for chat completions and responses
        output_path: Optional file path to write streaming output
        flush_threshold: Number of characters to buffer before flushing to file (default: 20000)
        **kwargs: Additional parameters to pass to the API
        
    Returns:
        Complete accumulated response text
        
    Raises:
        ValueError: If required parameters are missing
    """
    endpoint_type = get_openai_endpoint_type(model)
    
    # Log what we're sending to OpenAI
    logger.info("=" * 80)
    logger.info(f"OpenAI Streaming API Request - Model: {model}, Endpoint: {endpoint_type}")
    logger.info("=" * 80)
    
    if endpoint_type == "responses":
        # Use /v1/responses endpoint (Responses API) with streaming
        logger.info(f"Using Responses API endpoint with STREAMING for model: {model}")
        
        # Convert messages to input string
        if messages:
            input_text = _messages_to_input(messages)
        elif prompt:
            input_text = prompt
        else:
            raise ValueError("messages or prompt is required for responses models")
        
        # Build parameters for responses endpoint
        params = {
            "model": model,
            "input": input_text,
        }
        
        # Use max_output_tokens
        if max_completion_tokens:
            params["max_output_tokens"] = max_completion_tokens
        elif max_tokens:
            params["max_output_tokens"] = max_tokens
        
        # Reasoning controls are model-dependent. Only include them when the caller
        # explicitly provides a `reasoning` object to avoid 400s on models that
        # do not support `reasoning.effort`.
        if "reasoning" in kwargs and kwargs["reasoning"] is not None:
            params["reasoning"] = kwargs.pop("reasoning")
        
        # Add tools if provided
        if tools:
            params["tools"] = tools

        # Enforce valid JSON output when requested
        if json_mode:
            has_web_search = bool(tools) and any((t or {}).get("type") == "web_search" for t in tools)
            if has_web_search:
                logger.warning("JSON mode requested but web_search tool is present; disabling JSON mode for this request.")
            else:
                params["text"] = {"format": {"type": "json_object"}}
        
        # Add any additional kwargs
        params.update(kwargs)
        
        # Log request details
        input_preview = _sanitize_for_logging(input_text, LOG_PREVIEW_LENGTH)
        logger.info(f"Request params: model={model}, max_output_tokens={params.get('max_output_tokens', 'N/A')}, streaming=True")
        logger.info(f"Input preview: {input_preview}")
        if output_path:
            logger.info(f"Output will be written to: {output_path}")
            logger.info(f"Flush threshold: {flush_threshold} chars")
        if tools:
            logger.info(f"Tools: {tools}")
        
        # Create output directory if needed
        if output_path:
            import os
            output_dir = os.path.dirname(output_path)
            if output_dir:  # Only create directory if path contains a directory component
                os.makedirs(output_dir, exist_ok=True)
            # Clear the file if it exists
            with open(output_path, 'w') as f:
                f.write('')
        
        accumulated_text = ""
        buffer = ""
        chars_received = 0
        last_log_chars = 0
        
        logger.info("Starting to receive streaming response...")
        
        # Fail fast on parameter mismatches before making a paid call.
        _validate_params_for_endpoint(endpoint_type, params)

        # Stream the response - Note: .stream() method doesn't accept 'stream' parameter
        final_response = None

        with client.responses.stream(**params) as stream:
            for event in stream:
                if event.type == "response.output_text.delta":
                    delta = event.delta
                    buffer += delta
                    accumulated_text += delta
                    chars_received += len(delta)
                    
                    # Log progress periodically (every 10k chars)
                    if chars_received - last_log_chars >= 10000:
                        logger.info(f"Received {chars_received} chars so far...")
                        last_log_chars = chars_received
                    
                    # Flush to file when buffer exceeds threshold
                    if output_path and len(buffer) >= flush_threshold:
                        with open(output_path, 'a') as f:
                            f.write(buffer)
                        logger.info(f"Flushed {len(buffer)} chars to {output_path} (total: {chars_received} chars)")
                        buffer = ""

            # Attempt to capture the final response object for status/incomplete_details/tool traces.
            try:
                if hasattr(stream, "get_final_response"):
                    final_response = stream.get_final_response()
                elif hasattr(stream, "response"):
                    final_response = getattr(stream, "response")
            except Exception as e:
                logger.warning(f"Failed to fetch final response from stream: {e}")
        
        # Final flush of remaining buffer
        if output_path and buffer:
            with open(output_path, 'a') as f:
                f.write(buffer)
            logger.info(f"Final flush: {len(buffer)} chars to {output_path}")
        
        logger.info(f"Streaming complete: {chars_received} total chars received")
        logger.info(f"Response saved to: {output_path}" if output_path else "Response accumulated in memory")

        # Persist the final Responses payload alongside the streamed text.
        if output_path and final_response is not None:
            try:
                resp_path = str(output_path) + ".response.json"
                if hasattr(final_response, "model_dump_json"):
                    Path(resp_path).write_text(final_response.model_dump_json(indent=2), encoding="utf-8")
                elif hasattr(final_response, "model_dump"):
                    Path(resp_path).write_text(json.dumps(final_response.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
                else:
                    Path(resp_path).write_text(json.dumps(str(final_response), ensure_ascii=False), encoding="utf-8")
                logger.info(f"Saved final response JSON to: {resp_path}")
            except Exception as e:
                logger.warning(f"Failed to write streamed response JSON: {e}")
        
        
        # If streaming yields no text (can happen when the SDK/event types change or when output arrives only in the final response),
        # fall back to a non-streaming request to avoid producing empty chunk files.
        if chars_received == 0:
            logger.warning("Streaming yielded 0 chars; falling back to non-streaming Responses API call.")
            fallback_text = extract_completion_text(
                create_openai_completion(
                    client=client,
                    model=model,
                    messages=messages,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    max_completion_tokens=max_completion_tokens,
                    temperature=temperature,
                    tools=tools,
                    **kwargs
                ),
                model
            )
            if output_path:
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(fallback_text or "")
                    logger.info(f"Fallback response saved to: {output_path}")
                except Exception as e:
                    logger.warning(f"Failed to write fallback response to file: {e}")
            logger.info(f"Fallback complete: {len(fallback_text or '')} chars received")
            return (fallback_text or "", final_response) if return_meta else (fallback_text or "")

        return (accumulated_text or "", final_response) if return_meta else (accumulated_text or "")
    
    else:
        # For non-responses endpoints, streaming is not supported by this function
        # Use the standard non-streaming create_openai_completion instead
        logger.info(f"Streaming only supported for responses endpoint. Using standard API for {endpoint_type} endpoint.")
        return extract_completion_text(
            create_openai_completion(
                client=client,
                model=model,
                messages=messages,
                prompt=prompt,
                max_tokens=max_tokens,
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
                tools=tools,
                **kwargs
            ),
            model
        )
