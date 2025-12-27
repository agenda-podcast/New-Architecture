#!/usr/bin/env python3
"""OpenAI Responses API generator (two-pass).

Pass A (gpt-5.2-pro + web_search)
- Generates long-form scripts (L1..Ln) only.
- Output is stored as raw text (not JSON) to preserve everything returned.

Pass B (gpt-5-nano, no web_search)
- Summarizes a SOURCE_TEXT into enabled content types (M/S/R) according to the topic config.
- Output is JSON (content array) suitable for downstream pipeline.

This module is intentionally backward compatible with the existing pipeline by
exposing generate_all_content_two_pass() and generate_all_content_with_responses_api().
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from global_config import (
    CONTENT_TYPES,
    DEFAULT_SYSTEM_PROMPT,
    OUTPUTS_DIR,
    TESTING_MODE,
    get_content_code,
)

from model_limits import get_max_output_tokens, truncate_text_to_fit_context, default_max_output_tokens

from openai_utils import (
    create_openai_completion,
    create_openai_streaming_completion,
    extract_completion_text,
)

logger = logging.getLogger(__name__)


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _truncate_to_words(text: str, max_words: int) -> str:
    if max_words <= 0:
        return text
    words = re.findall(r"\S+", text or "")
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def calculate_max_output_tokens(
    target_words: int,
    *,
    buffer_ratio: float = 1.35,
    min_tokens: int = 2048,
    cap_tokens: Optional[int] = None,
) -> int:
    """Approximate output token budget from a word target.

    Assumption: ~0.75 words/token for English output.
    """
    if target_words <= 0:
        return min_tokens

    est = int((target_words / 0.75) * buffer_ratio)
    est = max(est, min_tokens)
    if cap_tokens is not None:
        est = min(est, cap_tokens)
    return est


def _persist_item_raw(code: str, resp: Any, txt: Optional[str]) -> None:
    """Persist raw response and/or extracted text for debugging."""
    try:
        out_dir = Path(OUTPUTS_DIR) / "debug"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = out_dir / f"{code}-{ts}"

        # Persist response JSON
        try:
            resp_json = resp.model_dump_json(indent=2)
            (base.with_suffix(".response.json")).write_text(resp_json, encoding="utf-8")
        except Exception:
            # Some SDK objects may not have model_dump_json
            try:
                (base.with_suffix(".response.json")).write_text(json.dumps(resp, indent=2), encoding="utf-8")
            except Exception:
                pass

        # Persist extracted text
        if txt is not None:
            (base.with_suffix(".txt")).write_text(txt, encoding="utf-8")

    except Exception as e:
        logger.warning(f"Failed to persist raw item output: {e}")


def _safe_slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "item"


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def _build_source_text_for_pass_b(pass_a_long_script: str, sources: List[Dict[str, Any]]) -> str:
    """Build the SOURCE_TEXT passed to Pass B."""
    srcs = []
    for s in sources or []:
        url = s.get("url") or ""
        title = s.get("title") or ""
        srcs.append(f"- {title}\n  {url}")
    src_block = "\n".join(srcs)

    return (
        "=== LONG SCRIPT (PASS A) ===\n"
        f"{pass_a_long_script}\n\n"
        "=== SOURCES (PASS A WEB SEARCH) ===\n"
        f"{src_block}\n"
    )


def _generate_item(
    client: Any,
    config: Dict[str, Any],
    content_type: str,
    source_text: str,
) -> Dict[str, Any]:
    """Generate one content type in Pass B."""
    ct = CONTENT_TYPES[content_type]
    code = get_content_code(content_type)
    max_words = int(ct.get("max_words", 0) or 0)
    template = ct.get("template", "")

    system_prompt = str(config.get("system_prompt", DEFAULT_SYSTEM_PROMPT))
    model = str(config.get("gpt_model_pass_b", "gpt-5-nano"))

    # Bound source size (chars). Default is 0 (no arbitrary cap).
    source_max_chars = int(os.environ.get("PASS_B_SOURCE_MAX_CHARS", "0") or "0")
    bounded_source = (source_text or "")
    if source_max_chars > 0 and len(bounded_source) > source_max_chars:
        bounded_source = bounded_source[:source_max_chars]

    # Use the model context window (when known) rather than an arbitrary char cap.
    # This attempts to maximize input without exceeding the hard context limit.
    # We reserve budget for the desired output tokens + overhead.
    desired_out = default_max_output_tokens(model, None) or 0
    bounded_source = truncate_text_to_fit_context(
        bounded_source,
        model=model,
        desired_output_tokens=int(desired_out),
        overhead_tokens=int(os.environ.get("PASS_B_CONTEXT_OVERHEAD_TOKENS", "2500") or "2500"),
    )

    logger.info("=" * 80)
    logger.info(f"Pass B: generating type={content_type} code={code} model={model} max_words={max_words}")

    prompt = template.replace("{{SOURCE_TEXT}}", bounded_source)

    # Default to model max output tokens unless overridden.
    per_item_cap = int(
        os.environ.get("PASS_B_ITEM_MAX_TOKENS", str(get_max_output_tokens(model) or 12500))
        or str(get_max_output_tokens(model) or 12500)
    )
    max_tokens = calculate_max_output_tokens(max_words, cap_tokens=per_item_cap)

    # Attempt with optional continuation when the model hits max_output_tokens.
    # This prevents the entire pipeline from failing due to a single truncated response.
    max_parts = int(os.environ.get('PASS_B_MAX_PARTS', '4') or '4')
    tail_chars = int(os.environ.get('PASS_B_CONTINUE_TAIL_CHARS', '3500') or '3500')
    allow_continue = str(os.environ.get('PASS_B_CONTINUE_ON_INCOMPLETE', 'true')).strip().lower() in ('1','true','yes','y')

    resp_parts: List[str] = []
    last_resp = None

    for part in range(1, max_parts + 1):
        # First part uses the normal prompt. Continuations send a minimal tail + 'continue' instruction.
        if part == 1:
            messages_to_send = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
        else:
            # Provide only the tail of the last output to anchor continuation without resending everything.
            prev_tail = (resp_parts[-1] if resp_parts else "")[-tail_chars:]
            cont_prompt = (
                "Continue from exactly where you left off. "
                "Output ONLY the continuation text. "
                "Do NOT repeat earlier text. "
                "Do NOT add headings, preambles, or metadata."
            )
            messages_to_send = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": prev_tail},
                {"role": "user", "content": cont_prompt},
            ]

        last_resp = create_openai_completion(
            client=client,
            model=model,
            messages=messages_to_send,
            tools=None,
            json_mode=False,
            max_completion_tokens=max_tokens,
            reasoning={"effort": os.environ.get("PASS_B_REASONING_EFFORT", "minimal")},
        )

        _persist_item_raw(code, last_resp, None)

        part_txt = extract_completion_text(last_resp, model) or ""
        _persist_item_raw(code, last_resp, part_txt)

        if part_txt:
            resp_parts.append(part_txt)

        # Stop if not incomplete or continuation disabled.
        status = getattr(last_resp, "status", None)
        if status != "incomplete":
            break

        # If incomplete, check reason
        reason = None
        try:
            inc = getattr(last_resp, "incomplete_details", None)
            if hasattr(inc, "reason"):
                reason = inc.reason
            elif isinstance(inc, dict):
                reason = inc.get("reason")
        except Exception:
            reason = None

        if not allow_continue or reason != "max_output_tokens":
            # If it's incomplete for some other reason, or continuation disabled, stop.
            break

    txt = "".join(resp_parts).strip()
    txt = _truncate_to_words(txt, max_words=max_words)
    aw = count_words(txt)
    return {"code": code, "type": content_type, "script": txt, "actual_words": aw, "target_words": max_words}


def generate_all_content_two_pass(
    client: Any,
    config: Dict[str, Any],
    pass_a_long_script: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate multi-format content using two-pass approach."""
    source_text = _build_source_text_for_pass_b(pass_a_long_script, sources)

    enabled = [k for k, v in (config.get("content_types") or {}).items() if v]
    enabled = enabled or ["M", "S", "R"]

    out: List[Dict[str, Any]] = []
    for content_type in enabled:
        item = _generate_item(client, config, content_type, source_text)
        out.append(item)

    return {"content": out}


def generate_all_content_with_responses_api(
    client: Any,
    config: Dict[str, Any],
    pass_a_long_script: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Backward-compatible alias."""
    return generate_all_content_two_pass(client, config, pass_a_long_script, sources)
