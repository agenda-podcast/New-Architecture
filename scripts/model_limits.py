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
# Keep these in sync with platform.openai.com/docs/models
MODEL_MAX_OUTPUT_TOKENS: Dict[str, int] = {
    # GPT-5 family
    "gpt-5": 128_000,
    "gpt-5-mini": 128_000,
    "gpt-5-nano": 128_000,
    "gpt-5.2": 128_000,
    "gpt-5.2-pro": 128_000,
    "gpt-5-pro": 272_000,  # larger max output
    # Chat snapshots (smaller max outputs)
    "gpt-5-chat-latest": 16_384,
    "gpt-5.2-chat-latest": 16_384,  # if you use chat-latest snapshots
    # GPT-4.1 family (non-reasoning)
    "gpt-4.1": 32_768,
    "gpt-4.1-mini": 32_768,
    "gpt-4.1-nano": 32_768,
}

# Context windows (input+output total). Conservative defaults where unknown.
MODEL_CONTEXT_TOKENS: Dict[str, int] = {
    "gpt-5": 400_000,
    "gpt-5-mini": 400_000,
    "gpt-5-nano": 400_000,
    "gpt-5.2": 400_000,
    "gpt-5.2-pro": 400_000,
    "gpt-5-pro": 400_000,
    "gpt-5-chat-latest": 128_000,
    "gpt-5.2-chat-latest": 128_000,
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1-nano": 1_047_576,
}

def get_max_output_tokens(model: str) -> int:
    m = (model or "").strip()
    return int(MODEL_MAX_OUTPUT_TOKENS.get(m, 16_384))

def get_context_window_tokens(model: str) -> int:
    m = (model or "").strip()
    return int(MODEL_CONTEXT_TOKENS.get(m, 128_000))

def default_max_output_tokens(model: str, requested: int | None = None) -> int:
    """Return an appropriate max output token budget.

    This repository has historically used two calling conventions:

    1) ``default_max_output_tokens(model)`` meaning "use the model maximum".
    2) ``default_max_output_tokens(model, requested)`` meaning "use requested
       if provided, otherwise use the model maximum, and always clamp to the
       model maximum".

    The second form is used by ``openai_utils.py`` and some generators. We keep
    it to avoid runtime TypeErrors.
    """
    if requested is None:
        return get_max_output_tokens(model)
    return clamp_max_output_tokens(model, requested)

def clamp_max_output_tokens(model: str, requested: int) -> int:
    mx = get_max_output_tokens(model)
    if requested is None:
        return mx
    try:
        r = int(requested)
    except Exception:
        r = mx
    if r <= 0:
        return mx
    return min(r, mx)


# Backwards-compatible alias -------------------------------------------------
# Earlier revisions of this repository exposed `clamp_output_tokens()`.
# Some modules (e.g., openai_utils.py, responses_api_generator.py) still
# import that symbol. Keep both names to avoid runtime import errors.
def clamp_output_tokens(model: str, requested: int) -> int:
    """Alias for :func:`clamp_max_output_tokens` (kept for compatibility)."""
    return clamp_max_output_tokens(model, requested)

def estimate_tokens(text: str) -> int:
    # very rough: ~4 chars/token average in English
    return max(1, int(len(text or "") / 4))

def truncate_text_to_fit_context(model: str, prompt: str, max_output_tokens: int) -> str:
    """
    Ensures `prompt` fits within the model context window leaving room for output.
    We approximate tokens; this is protective, not exact.
    """
    ctx = get_context_window_tokens(model)
    out_budget = clamp_max_output_tokens(model, max_output_tokens)
    # keep a small safety buffer for system/instructions/tool overhead
    safety = 2_000 if ctx >= 128_000 else 1_000
    in_budget = max(1_000, ctx - out_budget - safety)

    txt = prompt or ""
    if estimate_tokens(txt) <= in_budget:
        return txt

    # Truncate by characters proportionally
    ratio = in_budget / max(1, estimate_tokens(txt))
    new_len = max(1_000, int(len(txt) * ratio))
    txt2 = txt[:new_len]

    # Trim to last paragraph boundary if possible
    cut = txt2.rfind("\n\n")
    if cut > 500:
        txt2 = txt2[:cut]

    return txt2.strip()
