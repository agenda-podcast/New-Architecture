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
# Keep a conservative buffer for unknowns.
MODEL_LIMITS: Dict[str, Dict[str, int]] = {
    # GPT-5 family
    "gpt-5": {"context": 200_000, "max_output": 16_384},
    "gpt-5.2": {"context": 200_000, "max_output": 16_384},
    "gpt-5.2-pro": {"context": 200_000, "max_output": 16_384},
    "gpt-5-pro": {"context": 200_000, "max_output": 16_384},
    "gpt-5-mini": {"context": 200_000, "max_output": 16_384},
    "gpt-5-nano": {"context": 200_000, "max_output": 16_384},
    # GPT-4.x / 4o family (fallbacks)
    "gpt-4o": {"context": 128_000, "max_output": 16_384},
    "gpt-4o-mini": {"context": 128_000, "max_output": 16_384},
    "gpt-4.1": {"context": 128_000, "max_output": 16_384},
    "gpt-4.1-mini": {"context": 128_000, "max_output": 16_384},
    "gpt-4.1-nano": {"context": 128_000, "max_output": 16_384},
    # Safe default
    "__default__": {"context": 32_000, "max_output": 4_096},
}


def _normalize_model_name(model: str) -> str:
    m = (model or "").strip()
    if not m:
        return "__default__"

    # strip vendor prefixes if present
    m = re.sub(r"^(openai/|oai/)", "", m)

    # remove snapshot suffixes (e.g. -2025-xx-xx) or variants
    # keep base model family
    for pat in (
        r"-\d{4}-\d{2}-\d{2}$",
        r"-\d{8}$",
    ):
        m = re.sub(pat, "", m)

    return m


def get_max_output_tokens(model: str) -> int:
    m = _normalize_model_name(model)
    return MODEL_LIMITS.get(m, MODEL_LIMITS["__default__"])["max_output"]


def get_context_window_tokens(model: str) -> int:
    m = _normalize_model_name(model)
    return MODEL_LIMITS.get(m, MODEL_LIMITS["__default__"])["context"]


def default_max_output_tokens(model: str) -> int:
    """
    Sensible default when caller didn't specify max output.
    Keep below the hard max to reduce truncation risk for multi-step prompts.
    """
    mx = get_max_output_tokens(model)
    return min(mx, 4_096) if mx > 4_096 else mx


def clamp_max_output_tokens(model: str, requested: int) -> int:
    """
    Clamp requested max output tokens to the model's hard maximum.
    """
    mx = get_max_output_tokens(model)
    try:
        r = int(requested)
    except Exception:
        r = default_max_output_tokens(model)

    if r <= 0:
        r = default_max_output_tokens(model)

    return min(r, mx)


def clamp_output_tokens(model: str, requested: int) -> int:
    """Backward-compatible alias for clamp_max_output_tokens.

    Some modules import clamp_output_tokens; the canonical helper in this
    codebase is clamp_max_output_tokens. Keep both to avoid breaking older
    imports.
    """
    return clamp_max_output_tokens(model, requested)


def estimate_tokens(text: str) -> int:
    # very rough: ~4 chars/token average in English
    return max(1, int(len(text or "") / 4))


def truncate_text_to_fit_context(
    model: str,
    prompt: str,
    reserved_output_tokens: int,
    safety_margin_tokens: int = 256,
) -> str:
    """
    Truncate input text so that:
        input_tokens + reserved_output_tokens + safety_margin_tokens <= context_window

    This is an approximation (char-based token estimator). It's meant to prevent
    obvious overflows, not to be perfect.
    """
    ctx = get_context_window_tokens(model)
    in_budget = max(1, ctx - max(0, int(reserved_output_tokens)) - max(0, int(safety_margin_tokens)))

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
