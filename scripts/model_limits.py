# -*- coding: utf-8 -*-
"""
Model token limits + helpers.

You cannot remove hard model limits. You CAN:
- Set requested max output tokens to the model maximum
- Clamp oversized values
- Truncate input to fit context with reserved output budget
"""

from __future__ import annotations

import re
from typing import Dict

# Source of truth should be OpenAI model docs.
# These values are conservative defaults for safety; override via env if needed.
MODEL_CONTEXT_TOKENS: Dict[str, int] = {
    "gpt-5.2-pro": 200_000,
    "gpt-5.2": 200_000,
    "gpt-5": 200_000,
    "gpt-5-nano": 128_000,
    "gpt-4.1": 128_000,
    "gpt-4.1-mini": 128_000,
    "gpt-4.1-nano": 128_000,
}

MODEL_MAX_OUTPUT_TOKENS: Dict[str, int] = {
    "gpt-5.2-pro": 32_768,
    "gpt-5.2": 32_768,
    "gpt-5": 32_768,
    "gpt-5-nano": 16_384,
    "gpt-4.1": 16_384,
    "gpt-4.1-mini": 16_384,
    "gpt-4.1-nano": 16_384,
}


def get_max_output_tokens(model: str) -> int:
    m = (model or "").strip()
    return int(MODEL_MAX_OUTPUT_TOKENS.get(m, 16_384))


def get_context_window_tokens(model: str) -> int:
    m = (model or "").strip()
    return int(MODEL_CONTEXT_TOKENS.get(m, 128_000))


def default_max_output_tokens(model: str, requested: int | None = None) -> int:
    """Return an appropriate max output token budget.

    Calling conventions supported:
      1) default_max_output_tokens(model) => model maximum
      2) default_max_output_tokens(model, requested) => min(requested, model maximum)
    """
    max_out = get_max_output_tokens(model)
    if requested is None:
        return max_out
    try:
        req = int(requested)
    except Exception:
        req = max_out
    if req <= 0:
        return max_out
    return min(req, max_out)


def clamp_max_output_tokens(model: str, requested: int) -> int:
    """Clamp requested output tokens to the model maximum (>= 1)."""
    max_out = get_max_output_tokens(model)
    try:
        r = int(requested)
    except Exception:
        r = max_out
    r = max(1, r)
    return min(r, max_out)


def clamp_output_tokens(model: str, requested: int) -> int:
    """Alias for :func:`clamp_max_output_tokens` (kept for compatibility)."""
    return clamp_max_output_tokens(model, requested)


def estimate_tokens(text: str) -> int:
    # very rough: ~4 chars/token average in English
    return max(1, int(len(text or "") / 4))


def truncate_text_to_fit_context(model: str, prompt: str, max_output_tokens: int) -> str:
    """
    Ensure prompt fits within context window after reserving max_output_tokens.
    This is a conservative heuristic (character-based).
    """
    ctx = get_context_window_tokens(model)
    reserve = clamp_max_output_tokens(model, max_output_tokens)
    budget = max(1, ctx - reserve)

    # Convert token budget to char budget (~4 chars/token)
    char_budget = budget * 4
    p = prompt or ""
    if len(p) <= char_budget:
        return p

    # Keep tail-heavy prompts? Default keep head.
    return p[:char_budget]
