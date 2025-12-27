#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Two-pass generator (Responses API).

Fixes:
- No import of DEFAULT_SYSTEM_PROMPT (it does not exist in your global_config.py)
- Pass A uses gpt-5.2-pro and enforces supported reasoning effort levels
- Pass B uses gpt-5-nano (default minimal reasoning)
- Keeps contract expected by multi_format_generator:
    generate_all_content_two_pass(client, config, pass_a_long_script, sources)
    generate_all_content_with_responses_api(client, config, pass_a_long_script, sources)
"""

from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from global_config import CONTENT_TYPES, get_content_code
from model_limits import (
    get_max_output_tokens,
    default_max_output_tokens,
    clamp_output_tokens,
    truncate_text_to_fit_context,
)
from openai_utils import create_openai_completion, extract_completion_text

logger = logging.getLogger(__name__)


# -----------------------
# Defaults / constants
# -----------------------

DEFAULT_PASS_A_MODEL = "gpt-5.2-pro"
DEFAULT_PASS_B_MODEL = "gpt-5-nano"

DEFAULT_SYSTEM_PROMPT_FALLBACK = (
    "You are a professional podcast/news scriptwriter. Follow instructions precisely."
)


# -----------------------
# Helpers
# -----------------------

def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def truncate_to_words(text: str, max_words: int) -> str:
    if not text:
        return ""
    if max_words <= 0:
        return text
    words = re.findall(r"\S+", text)
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).strip()


def calculate_max_output_tokens(target_words: int, *, model: str, floor: int = 2048) -> int:
    """
    Rough sizing: 0.75 words/token, plus buffer.
    Then clamp to model max output.
    """
    if target_words <= 0:
        wanted = floor
    else:
        wanted = int((target_words / 0.75) * 1.35)
        wanted = max(wanted, floor)

    mx = get_max_output_tokens(model)
    return min(wanted, mx)


def pick_model_pass_a(config: Dict[str, Any]) -> str:
    # Allow topic config or env override; otherwise force gpt-5.2-pro as requested.
    return (
        os.getenv("PASS_A_MODEL")
        or config.get("gpt_model_pass_a")
        or config.get("gpt_model")
        or DEFAULT_PASS_A_MODEL
    )


def pick_model_pass_b(config: Dict[str, Any]) -> str:
    return (
        os.getenv("PASS_B_MODEL")
        or config.get("gpt_model_pass_b")
        or DEFAULT_PASS_B_MODEL
    )


def normalize_reasoning_effort_for_model(model: str, requested: str) -> str:
    """
    Enforce per-model supported values.

    gpt-5.2-pro supports: medium, high, xhigh (NOT minimal/low/none).  :contentReference[oaicite:1]{index=1}
    For other reasoning models, the platform docs list: none|minimal|low|medium|high|xhigh
    (model-dependent; the API will 400 if invalid).
    """
    m = (model or "").strip().lower()
    r = (requested or "").strip().lower() or "medium"

    if m == "gpt-5.2-pro":
        if r not in ("medium", "high", "xhigh"):
            logger.warning("gpt-5.2-pro does not support reasoning.effort='%s'. Using 'medium' instead.", r)
            return "medium"
        return r

    # For everything else, keep the requested value; if it's invalid, API will error.
    return r


def get_pass_a_reasoning(config: Dict[str, Any], model: str) -> Dict[str, str]:
    # Lowest available on gpt-5.2-pro is medium.
    requested = os.getenv("PASS_A_REASONING_EFFORT") or str(config.get("pass_a_reasoning_effort") or "medium")
    effort = normalize_reasoning_effort_for_model(model, requested)
    return {"effort": effort}


def get_pass_b_reasoning(config: Dict[str, Any], model: str) -> Dict[str, str]:
    requested = os.getenv("PASS_B_REASONING_EFFORT") or str(config.get("pass_b_reasoning_effort") or "minimal")
    effort = normalize_reasoning_effort_for_model(model, requested)
    return {"effort": effort}


def get_system_prompt(config: Dict[str, Any]) -> str:
    # Your topic config may define system_prompt; otherwise fallback.
    sp = config.get("system_prompt")
    if isinstance(sp, str) and sp.strip():
        return sp.strip()
    return DEFAULT_SYSTEM_PROMPT_FALLBACK


def build_source_text(pass_a_long_script: str, sources: List[Dict[str, Any]]) -> str:
    srcs = []
    for s in sources or []:
        title = (s.get("title") or "").strip()
        url = (s.get("url") or "").strip()
        if title and url:
            srcs.append(f"- {title}\n  {url}")
        elif url:
            srcs.append(f"- {url}")

    src_block = "\n".join(srcs)
    return (
        "=== LONG SCRIPT (PASS A) ===\n"
        f"{pass_a_long_script}\n\n"
        "=== SOURCES (PASS A WEB SEARCH / PROVIDED) ===\n"
        f"{src_block}\n"
    )


# -----------------------
# Pass B generator
# -----------------------

def _generate_pass_b_item(
    client: Any,
    config: Dict[str, Any],
    content_type: str,
    source_text: str,
) -> Dict[str, Any]:
    ct = CONTENT_TYPES[content_type]
    code = get_content_code(content_type)
    max_words = int(ct.get("max_words", 0) or 0)
    template = str(ct.get("template", ""))

    model = pick_model_pass_b(config)
    system_prompt = get_system_prompt(config)

    # Make SOURCE_TEXT as large as possible but still fit model context (reserve output budget).
    desired_out = default_max_output_tokens(model, None) or get_max_output_tokens(model)
    bounded_source = truncate_text_to_fit_context(
        source_text or "",
        model=model,
        desired_output_tokens=int(desired_out),
        overhead_tokens=int(os.getenv("PASS_B_CONTEXT_OVERHEAD_TOKENS", "2500") or "2500"),
    )

    prompt = template.replace("{{SOURCE_TEXT}}", bounded_source)

    # Output budget: request near model max unless word cap is smaller.
    max_out = calculate_max_output_tokens(max_words, model=model)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        tools=None,
        json_mode=False,
        max_completion_tokens=max_out,
        reasoning=get_pass_b_reasoning(config, model),
    )

    txt = (extract_completion_text(resp, model) or "").strip()
    txt = truncate_to_words(txt, max_words=max_words)

    return {
        "code": code,
        "type": content_type,
        "script": txt,
        "actual_words": count_words(txt),
        "target_words": max_words,
        "model": model,
        "reasoning_effort": get_pass_b_reasoning(config, model).get("effort"),
    }


# -----------------------
# Public entrypoints (expected by your pipeline)
# -----------------------

def generate_all_content_two_pass(
    client: Any,
    config: Dict[str, Any],
    pass_a_long_script: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Called by multi_format_generator.py (two-pass mode).
    pass_a_long_script comes from Pass A stage elsewhere in your pipeline.
    """
    source_text = build_source_text(pass_a_long_script, sources)

    enabled = [k for k, v in (config.get("content_types") or {}).items() if v]
    enabled = enabled or ["M", "S", "R"]

    out: List[Dict[str, Any]] = []
    for content_type in enabled:
        out.append(_generate_pass_b_item(client, config, content_type, source_text))

    return {"content": out}


def generate_all_content_with_responses_api(
    client: Any,
    config: Dict[str, Any],
    pass_a_long_script: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    # Backward-compatible alias used by some versions of multi_format_generator
    return generate_all_content_two_pass(client, config, pass_a_long_script, sources)


# -----------------------
# Optional: helper for Pass A calls (if you want Pass A here too)
# -----------------------

def pass_a_reasoning_object_for_model(config: Dict[str, Any]) -> Dict[str, str]:
    """
    If you run Pass A in another file, import and use this helper to ensure
    gpt-5.2-pro gets a supported effort setting.
    """
    model = pick_model_pass_a(config)
    return get_pass_a_reasoning(config, model)
