#!/usr/bin/env python3
"""
Model token limits and helper utilities.

Important:
- OpenAI models have hard ceilings for context (input+output) and max output tokens.
- You cannot "remove" these limits. The best you can do is:
  (1) default to each model's maximum output token limit, and
  (2) size/truncate inputs to fit within the model's context window.

The values below should be kept in sync with OpenAI model docs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict
import os
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelLimits:
    # Total context window: input + output tokens
    context_window_tokens: Optional[int]
    # Maximum completion/output tokens per request
    max_output_tokens: Optional[int]


# Known model limits (based on official docs as of 2025-12-26).
# For unknown models, we return None and avoid clamping unless explicitly overridden.
KNOWN_LIMITS: Dict[str, ModelLimits] = {
    # GPT-4o family
    "gpt-4o": ModelLimits(context_window_tokens=128_000, max_output_tokens=16_384),
    "gpt-4o-mini": ModelLimits(context_window_tokens=128_000, max_output_tokens=16_384),
    "chatgpt-4o-latest": ModelLimits(context_window_tokens=128_000, max_output_tokens=16_384),

    # GPT-4.1 family
    "gpt-4.1": ModelLimits(context_window_tokens=1_047_576, max_output_tokens=32_768),
    "gpt-4.1-mini": ModelLimits(context_window_tokens=1_047_576, max_output_tokens=32_768),
    "gpt-4.1-nano": ModelLimits(context_window_tokens=1_047_576, max_output_tokens=32_768),

    # GPT-5 family (pricing/announcement pages list 400k context, 128k output)
    "gpt-5": ModelLimits(context_window_tokens=400_000, max_output_tokens=128_000),
    "gpt-5-mini": ModelLimits(context_window_tokens=400_000, max_output_tokens=128_000),
    "gpt-5-nano": ModelLimits(context_window_tokens=400_000, max_output_tokens=128_000),

    # GPT-5.2 (assumed same caps as GPT-5 family)
    "gpt-5.2-pro": ModelLimits(context_window_tokens=400_000, max_output_tokens=128_000),
    "gpt-5.2-mini": ModelLimits(context_window_tokens=400_000, max_output_tokens=128_000),
    "gpt-5.2-nano": ModelLimits(context_window_tokens=400_000, max_output_tokens=128_000),
}


def _normalize_model_name(model: str) -> str:
    return (model or "").strip()


def get_model_limits(model: str) -> ModelLimits:
    """
    Return ModelLimits for a model.

    Supports:
    - exact matches in KNOWN_LIMITS
    - prefix matches for known families (e.g., gpt-5.2-*, gpt-4.1-*)

    Override:
    - MODEL_MAX_OUTPUT_TOKENS: force max_output_tokens for all models (int)
    - MODEL_CONTEXT_WINDOW_TOKENS: force context window for all models (int)
    """
    m = _normalize_model_name(model)

    # Global overrides (useful if OpenAI changes caps, or if you're using a custom deployment)
    try:
        out_override = int(os.environ.get("MODEL_MAX_OUTPUT_TOKENS", "") or 0)
    except Exception:
        out_override = 0
    try:
        ctx_override = int(os.environ.get("MODEL_CONTEXT_WINDOW_TOKENS", "") or 0)
    except Exception:
        ctx_override = 0

    if out_override > 0 or ctx_override > 0:
        return ModelLimits(
            context_window_tokens=ctx_override or None,
            max_output_tokens=out_override or None,
        )

    if m in KNOWN_LIMITS:
        return KNOWN_LIMITS[m]

    # Family fallbacks
    if m.startswith("gpt-5.2-"):
        return KNOWN_LIMITS["gpt-5.2-pro"]
    if m.startswith("gpt-5."):
        return KNOWN_LIMITS["gpt-5"]
    if m.startswith("gpt-4.1-"):
        return KNOWN_LIMITS["gpt-4.1"]
    if m.startswith("gpt-4o"):
        return KNOWN_LIMITS["gpt-4o"]

    return ModelLimits(context_window_tokens=None, max_output_tokens=None)


def get_max_output_tokens(model: str) -> Optional[int]:
    return get_model_limits(model).max_output_tokens


def get_context_window_tokens(model: str) -> Optional[int]:
    return get_model_limits(model).context_window_tokens


def clamp_output_tokens(model: str, requested: Optional[int]) -> Optional[int]:
    """Clamp requested output tokens to the model's maximum, if known."""
    if requested is None:
        return None
    try:
        req = int(requested)
    except Exception:
        return requested

    if req <= 0:
        return requested

    lim = get_max_output_tokens(model)
    if lim is None:
        return req

    if req > lim:
        logger.warning("Clamping requested output tokens from %s to %s for model=%s", req, lim, model)
        return lim
    return req


def default_max_output_tokens(model: str, requested: Optional[int]) -> Optional[int]:
    """If requested is None/0, return the model max (if known). Otherwise clamp."""
    try:
        if requested is None or int(requested or 0) <= 0:
            return get_max_output_tokens(model) or requested
    except Exception:
        # If requested cannot be int-cast, just return it.
        return requested
    return clamp_output_tokens(model, requested)


def estimate_tokens_from_chars(char_count: int) -> int:
    """Rough heuristic: ~4 chars/token (English-like text)."""
    if char_count <= 0:
        return 0
    return max(1, int(char_count / 4))


def truncate_text_to_fit_context(
    text: str,
    *,
    model: str,
    desired_output_tokens: int,
    overhead_tokens: int = 2_000,
) -> str:
    """
    Truncate text so that (estimated_input_tokens + desired_output_tokens + overhead_tokens)
    fits within the model context window.

    - If model context is unknown, returns text unchanged.
    - Uses a simple char/token heuristic to avoid dependency on tokenizer libs.
    """
    if not text:
        return ""

    ctx = get_context_window_tokens(model)
    if not ctx:
        return text

    available_for_input = ctx - int(desired_output_tokens or 0) - int(overhead_tokens or 0)
    if available_for_input <= 0:
        return ""

    max_chars = available_for_input * 4  # inverse heuristic
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
