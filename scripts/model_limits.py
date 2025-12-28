# -*- coding: utf-8 -*-
"""
Model token limits + helpers.

Purpose
- Provide *accurate* (not artificially conservative) context-window and max-output-token limits
  for the models used by this repo.
- Keep callers safe by clamping any requested output budget to the model maximum.
- Provide a lightweight prompt truncation helper that reserves an output budget.

Notes
- These are hard model caps. You cannot exceed them via API parameters.
- Values below are sourced from OpenAI's public model docs (platform.openai.com).

If you add new models, extend the dictionaries below (prefer aliases, and prefix matching will
cover snapshot variants like "gpt-4o-2024-05-13" or "gpt-4.1-2025-04-14".)
"""

from __future__ import annotations

import re
from typing import Dict, Iterable


# ======= Limits (aliases) =====================================================

# Context window (prompt + output, plus any reasoning tokens) in tokens.
MODEL_CONTEXT_TOKENS: Dict[str, int] = {
    # GPT-5 family (Responses API)
    "gpt-5.2-pro": 400_000,
    "gpt-5.2": 400_000,
    "gpt-5.1": 400_000,
    "gpt-5-pro": 400_000,
    "gpt-5": 400_000,
    "gpt-5-mini": 400_000,
    "gpt-5-nano": 400_000,
    "gpt-5.1-codex": 400_000,
    "gpt-5.1-codex-max": 400_000,
    "gpt-5-codex": 400_000,

    # GPT-4.1 family
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1-nano": 1_047_576,

    # GPT-4o family
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,

    # Legacy chat models
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
}

# Max *visible* output tokens the API will allow you to request for the model.
MODEL_MAX_OUTPUT_TOKENS: Dict[str, int] = {
    # GPT-5 family
    "gpt-5-pro": 272_000,
    "gpt-5.2-pro": 128_000,
    "gpt-5.2": 128_000,
    "gpt-5.1": 128_000,
    "gpt-5": 128_000,
    "gpt-5-mini": 128_000,
    "gpt-5-nano": 128_000,
    "gpt-5.1-codex": 128_000,
    "gpt-5.1-codex-max": 128_000,
    "gpt-5-codex": 128_000,

    # GPT-4.1 family
    "gpt-4.1": 32_768,
    "gpt-4.1-mini": 32_768,
    "gpt-4.1-nano": 32_768,

    # GPT-4o family
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,

    # Legacy chat models
    "gpt-4-turbo": 4_096,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 4_096,
}


# ======= Helpers ==============================================================

_DATE_SUFFIX_RE = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def _model_key_candidates(model: str) -> Iterable[str]:
    """Yield candidate lookup keys for a model string."""
    m = (model or "").strip()
    if not m:
        return
    yield m

    # Common aliases/suffixes.
    for suf in ("-latest", "-preview"):
        if m.endswith(suf):
            yield m[: -len(suf)]

    # Snapshot variants: gpt-4o-2024-05-13, gpt-4.1-2025-04-14, etc.
    m2 = _DATE_SUFFIX_RE.sub("", m)
    if m2 != m:
        yield m2


def _lookup_model_value(model: str, mapping: Dict[str, int], default: int) -> int:
    """Lookup a model value using exact match, then prefix match, then default."""
    # Exact/candidate match first.
    for cand in _model_key_candidates(model):
        if cand in mapping:
            return int(mapping[cand])

    # Prefix match to cover snapshot variants even when not stripped cleanly.
    # (Longest keys first to avoid accidental partial matches.)
    keys = sorted(mapping.keys(), key=len, reverse=True)
    for cand in _model_key_candidates(model):
        for k in keys:
            if cand.startswith(k):
                return int(mapping[k])

    return int(default)


def get_context_window_tokens(model: str) -> int:
    return _lookup_model_value(model, MODEL_CONTEXT_TOKENS, 128_000)


def get_max_output_tokens(model: str) -> int:
    return _lookup_model_value(model, MODEL_MAX_OUTPUT_TOKENS, 16_384)


def default_max_output_tokens(model: str, requested: int | None = None) -> int:
    """Return an appropriate max output token budget.

    Calling conventions supported:
      1) default_max_output_tokens(model) => model maximum
      2) default_max_output_tokens(model, requested) => min(requested, model maximum)

    "requested" is treated as a user preference; it is never allowed to exceed the model cap.
    """
    max_out = get_max_output_tokens(model)
    if requested is None:
        return max_out
    try:
        req = int(requested)
    except Exception:
        return max_out
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
    """Ensure prompt fits within context window after reserving max_output_tokens.

    Conservative heuristic (character-based). This is only used as a last resort; ideally
    you keep prompts comfortably within the context window.

    - Reserves the output budget (clamped to model max output).
    - Truncates the prompt to fit the remaining budget.
    """
    ctx = get_context_window_tokens(model)
    reserve = clamp_max_output_tokens(model, max_output_tokens)
    budget = max(1, ctx - reserve)

    # Convert token budget to char budget (~4 chars/token)
    char_budget = budget * 4
    p = prompt or ""
    if len(p) <= char_budget:
        return p

    # Keep head by default.
    return p[:char_budget]
