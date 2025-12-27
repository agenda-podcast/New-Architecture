#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Two-pass script generation using the OpenAI Responses API.

This module is used by ``multi_format_generator.py``.

Updated behavior (Dec 2025):
- Pass A is ONLY used to generate long-form scripts (L*). It outputs plain text (no JSON):
    SOURCES:
    - ...
    SCRIPT:
    HOST_A: ...
    HOST_B: ...

- Pass A is SKIPPED when any of the following is true:
    1) Topic content_types.long.enabled == False
    2) Testing / "gesting" mode is enabled (global_config.TESTING_MODE, or config.testing_mode / gisting_mode / gesting_mode)
    3) A test data source file is configured (config.test_data_source_file / config.sources_file / config.data_source_file etc.) and exists

- Pass B returns a SINGLE JSON object with *all* requested non-long items (M/S/R, etc.) in one response.
  Pass B generates only summarized/derived pieces per item of each content type.

- Pass A is never re-requested. Whatever comes back (even if incomplete) is treated as completed and saved upstream.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    # Optional in some CI/test environments
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

from model_limits import clamp_output_tokens, default_max_output_tokens
from openai_utils import create_openai_completion, extract_completion_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "on", "enabled")


def _normalize_ws(s: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", (s or "").strip())


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """
    Best-effort extraction of the first JSON object from a string.
    Used when we cannot rely on strict JSON mode (e.g. web_search present).
    """
    if not isinstance(text, str):
        raise ValueError("Expected string text for JSON extraction")

    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        return json.loads(t)

    # Scan for balanced braces
    start = t.find("{")
    if start < 0:
        raise ValueError("No JSON object start '{' found")

    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = t[start : i + 1]
                    return json.loads(candidate)

    raise ValueError("Could not find a complete JSON object in output")


def _resolve_hosts(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Robust host resolver.

    Supports config["roles"] in multiple shapes:
    1) dict:
       {
         "host_a": {"name": "...", "bio": "..."},
         "host_b": {"name": "...", "bio": "..."}
       }
    2) dict with uppercase keys:
       {"HOST_A": {...}, "HOST_B": {...}}
    3) list:
       [
         {"role": "host_a", "name": "...", "bio": "..."},
         {"role": "host_b", "name": "...", "bio": "..."}
       ]
       or simply [ {...}, {...} ] (first is A, second is B)
    4) anything else -> fallback defaults
    """
    roles = config.get("roles") or {}

    # Normalize roles if it's a list (your current failing case)
    if isinstance(roles, list):
        host_a: Dict[str, Any] = {}
        host_b: Dict[str, Any] = {}

        # Try to identify by explicit labels inside dicts
        for item in roles:
            if not isinstance(item, dict):
                continue
            key = (
                item.get("role")
                or item.get("id")
                or item.get("code")
                or item.get("key")
                or item.get("name")
                or ""
            )
            k = str(key).strip().lower()

            if k in ("host_a", "host a", "a", "hosta", "primary", "main"):
                host_a = item
            elif k in ("host_b", "host b", "b", "hostb", "cohost", "co-host", "secondary"):
                host_b = item

        # If still missing, fall back to list order
        if not host_a and len(roles) >= 1 and isinstance(roles[0], dict):
            host_a = roles[0]
        if not host_b and len(roles) >= 2 and isinstance(roles[1], dict):
            host_b = roles[1]

        roles = {"host_a": host_a, "host_b": host_b}

    # If roles is not a dict by now, reset to empty
    if not isinstance(roles, dict):
        roles = {}

    host_a_obj = roles.get("host_a") or roles.get("HOST_A") or {}
    host_b_obj = roles.get("host_b") or roles.get("HOST_B") or {}

    def _pick(obj: Any, key: str, fallback: str) -> str:
        if isinstance(obj, dict):
            v = obj.get(key)
            if v:
                return str(v).strip()
        return fallback

    return {
        "host_a_name": _pick(host_a_obj, "name", "HOST_A"),
        "host_a_bio": _pick(host_a_obj, "bio", "Primary host"),
        "host_b_name": _pick(host_b_obj, "name", "HOST_B"),
        "host_b_bio": _pick(host_b_obj, "bio", "Co-host"),
    }


def _enabled_specs_from_content_specs(content_specs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split enabled specs into (long_specs, nonlong_specs)."""
    long_specs: List[Dict[str, Any]] = []
    nonlong_specs: List[Dict[str, Any]] = []
    for s in content_specs or []:
        t = str(s.get("type") or "").strip().lower()
        if t == "long":
            long_specs.append(s)
        else:
            nonlong_specs.append(s)
    return long_specs, nonlong_specs


def _has_existing_test_data_source_file(config: Dict[str, Any]) -> bool:
    """
    Detect whether a test data source file is configured and exists.
    We support multiple key names to tolerate config drift.
    """
    candidates = [
        config.get("test_data_source_file"),
        config.get("test_sources_file"),
        config.get("sources_file"),
        config.get("data_source_file"),
        config.get("data_source_path"),
        config.get("test_data_path"),
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(str(c))
        if p.is_file():
            return True
    return False


def _is_testing_or_gesting_mode(config: Dict[str, Any]) -> bool:
    # 1) topic-level flags
    if _truthy(config.get("testing_mode")):
        return True
    if _truthy(config.get("gesting_mode")):
        return True
    if _truthy(config.get("gisting_mode")):
        return True

    # 2) environment flags
    if _truthy(os.getenv("TESTING_MODE")):
        return True
    if _truthy(os.getenv("GESTING_MODE")):
        return True
    if _truthy(os.getenv("GISTING_MODE")):
        return True

    # 3) global_config constant (if present)
    try:
        import global_config  # local module
        if _truthy(getattr(global_config, "TESTING_MODE", False)):
            return True
    except Exception:
        pass

    return False


def _should_run_pass_a(config: Dict[str, Any], content_specs: List[Dict[str, Any]]) -> bool:
    """
    Pass A is only needed for long content, and must be suppressed by the user rules.
    """
    long_specs, _ = _enabled_specs_from_content_specs(content_specs)

    # Rule 1: if long is not requested, don't run Pass A.
    if not long_specs:
        return False

    # Rule 2: if testing/gesting mode, don't run Pass A.
    if _is_testing_or_gesting_mode(config):
        return False

    # Rule 3: if a test data source file exists, don't run Pass A.
    if _has_existing_test_data_source_file(config):
        return False

    return True


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _pick_model_pass_a(config: Dict[str, Any]) -> str:
    return (os.getenv("PASS_A_MODEL") or config.get("gpt_model_pass_a") or "gpt-5.2-pro").strip()


def _pick_model_pass_b(config: Dict[str, Any]) -> str:
    return (os.getenv("PASS_B_MODEL") or config.get("gpt_model_pass_b") or "gpt-5-nano").strip()


def _build_pass_a_prompt(config: Dict[str, Any], long_specs: List[Dict[str, Any]]) -> str:
    """
    Pass A prompt: ONLY "SOURCES" and "SCRIPT" in plain text. No JSON.
    """
    hosts = _resolve_hosts(config)

    topic = str(config.get("title") or config.get("topic") or "").strip() or "(untitled topic)"
    desc = str(config.get("description") or "").strip()
    freshness_hours = _safe_int(config.get("freshness_hours"), 24)
    freshness_window = f"last {freshness_hours} hours"

    regions = config.get("search_regions") or []
    region_txt = ", ".join([str(r).upper() for r in regions]) if regions else "GLOBAL"

    queries = config.get("queries") or []
    query_txt = "\n".join([f"- {q}" for q in queries]) if queries else "- (use your judgment)"

    # Word target: take max target_words among long specs.
    target_words = 9000
    for s in long_specs:
        target_words = max(target_words, _safe_int(s.get("target_words") or s.get("max_words"), 9000))

    return f"""You are a newsroom producer and dialogue scriptwriter for an English-language news podcast.
You MUST use the web_search tool before writing to verify the latest news and to avoid any "knowledge cutoff" disclaimers.

Topic: {topic}
Topic description: {desc}
Freshness window: {freshness_window}
Region focus: {region_txt}

Host personas:
- HOST_A ({hosts['host_a_name']}): {hosts['host_a_bio']}
- HOST_B ({hosts['host_b_name']}): {hosts['host_b_bio']}

Search guidance (use as web_search queries; adjust as needed):
{query_txt}

OUTPUT FORMAT (STRICT — no markdown, no JSON):
SOURCES:
- [1] <Publisher> — <Title> (<YYYY-MM-DD>). <URL>
- [2] ...
(Include 6–12 high-quality sources. Prefer primary/official where possible.)

SCRIPT:
Write ONE long dialogue script (~{target_words} words) between HOST_A and HOST_B.
- Use concrete dates.
- Clearly distinguish verified facts vs claims.
- Keep it engaging but grounded.
- No bullet lists inside the script; write as spoken dialogue with speaker tags.

Return ONLY the two sections above: SOURCES and SCRIPT.
"""


def _build_pass_b_prompt_from_pass_a(
    config: Dict[str, Any],
    nonlong_specs: List[Dict[str, Any]],
    pass_a_sources_text: str,
    pass_a_script_text: str,
) -> str:
    """
    Pass B prompt when Pass A ran: derive summaries from Pass A script only.
    Must return ONE JSON object with ALL items.
    """
    hosts = _resolve_hosts(config)
    topic = str(config.get("title") or config.get("topic") or "").strip() or "(untitled topic)"

    req_lines: List[str] = []
    for s in nonlong_specs:
        c = str(s.get("code") or "").strip()
        t = str(s.get("type") or "").strip()
        mw = _safe_int(s.get("target_words") or s.get("max_words"), 300)
        if not c:
            continue
        req_lines.append(f"- {c} ({t}): max_words={mw}")

    req_txt = "\n".join(req_lines) if req_lines else "- (no Pass B outputs requested)"

    return f"""You are Pass B of a two-pass pipeline.

You will be given:
1) SOURCES (as text)
2) LONG_SCRIPT (dialogue)

Your task:
- Create summarized/derived scripts for each requested item below.
- Do NOT introduce new facts. Use ONLY what is supported by LONG_SCRIPT and SOURCES.
- Return ALL items in ONE response as STRICT JSON (no markdown).

Topic: {topic}

Requested items:
{req_txt}

SOURCES (text, for attribution / grounding):
{pass_a_sources_text}

LONG_SCRIPT (text, for summarization/derivation):
{pass_a_script_text}

JSON OUTPUT SCHEMA (STRICT):
{{
  "content": [
    {{
      "code": "M1",
      "type": "medium",
      "script": "HOST_A: ...\\nHOST_B: ...",
      "max_words": 1200
    }}
  ]
}}

Rules:
- Use speaker tags HOST_A and HOST_B (do NOT replace with names).
- Each 'script' must be standalone (it must make sense without the long script).
- Keep each script within max_words.
- Return ONLY the JSON object.
"""


def _build_single_pass_b_prompt_with_web_search(config: Dict[str, Any], nonlong_specs: List[Dict[str, Any]]) -> str:
    """
    Single-pass generation (no Pass A). Uses web_search and returns all requested items in one JSON response.
    """
    hosts = _resolve_hosts(config)

    topic = str(config.get("title") or config.get("topic") or "").strip() or "(untitled topic)"
    desc = str(config.get("description") or "").strip()
    freshness_hours = _safe_int(config.get("freshness_hours"), 24)
    freshness_window = f"last {freshness_hours} hours"

    regions = config.get("search_regions") or []
    region_txt = ", ".join([str(r).upper() for r in regions]) if regions else "GLOBAL"

    queries = config.get("queries") or []
    query_txt = "\n".join([f"- {q}" for q in queries]) if queries else "- (use your judgment)"

    req_lines: List[str] = []
    for s in nonlong_specs:
        c = str(s.get("code") or "").strip()
        t = str(s.get("type") or "").strip()
        mw = _safe_int(s.get("target_words") or s.get("max_words"), 300)
        if not c:
            continue
        req_lines.append(f"- {c} ({t}): max_words={mw}")
    req_txt = "\n".join(req_lines) if req_lines else "- (no outputs requested)"

    return f"""You are a newsroom producer and dialogue scriptwriter for an English-language news podcast.
You MUST use the web_search tool before writing to verify the latest news and to avoid any "knowledge cutoff" disclaimers.

Topic: {topic}
Topic description: {desc}
Freshness window: {freshness_window}
Region focus: {region_txt}

Host personas:
- HOST_A ({hosts['host_a_name']}): {hosts['host_a_bio']}
- HOST_B ({hosts['host_b_name']}): {hosts['host_b_bio']}

Search guidance (use as web_search queries; adjust as needed):
{query_txt}

Your task:
1) Use web_search to gather and cross-check facts from multiple reputable sources.
2) Produce the requested summarized scripts below.
3) Return ALL items in ONE response as STRICT JSON (no markdown).

Requested items:
{req_txt}

JSON OUTPUT SCHEMA (STRICT):
{{
  "sources": [
    {{
      "n": 1,
      "publisher": "Publisher",
      "title": "Title",
      "date": "YYYY-MM-DD",
      "url": "https://..."
    }}
  ],
  "content": [
    {{
      "code": "S1",
      "type": "short",
      "script": "HOST_A: ...\\nHOST_B: ...",
      "max_words": 350
    }}
  ]
}}

Rules:
- Use speaker tags HOST_A and HOST_B (do NOT replace with names).
- Keep each script within max_words.
- Use concrete dates.
- Return ONLY the JSON object.
"""


# ---------------------------------------------------------------------------
# Parsing helpers for Pass A output
# ---------------------------------------------------------------------------

def _parse_pass_a_text(pass_a_text: str) -> Tuple[str, str]:
    """
    Extract (sources_text, script_text) from Pass A plain text.
    """
    t = (pass_a_text or "").strip()
    if not t:
        return "", ""

    # Normalize common variants
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    # Find SOURCES and SCRIPT blocks
    m_sources = re.search(r"(?im)^\s*sources\s*:\s*$", t)
    m_script = re.search(r"(?im)^\s*script\s*:\s*$", t)

    if not m_sources or not m_script:
        # Fallback: treat the whole thing as script
        return "", t.strip()

    sources_start = m_sources.end()
    script_start = m_script.end()

    if m_sources.start() < m_script.start():
        sources_text = t[sources_start : m_script.start()].strip()
        script_text = t[script_start :].strip()
    else:
        # weird ordering; fallback
        sources_text = ""
        script_text = t[script_start :].strip()

    return _normalize_ws(sources_text), _normalize_ws(script_text)


def _sources_text_to_list(sources_text: str) -> List[Dict[str, Any]]:
    """
    Best-effort parse of sources lines into a structured list.
    Accepts lines like:
      - [1] Publisher — Title (YYYY-MM-DD). URL
    """
    out: List[Dict[str, Any]] = []
    if not sources_text:
        return out

    for line in sources_text.splitlines():
        l = line.strip()
        if not l or l.startswith("#"):
            continue

        # Remove leading bullets
        l = re.sub(r"^[\-\*\u2022]\s*", "", l)

        n = None
        m = re.match(r"^\[(\d+)\]\s*(.*)$", l)
        if m:
            n = _safe_int(m.group(1), 0)
            l = m.group(2).strip()

        url = ""
        murl = re.search(r"(https?://\S+)", l)
        if murl:
            url = murl.group(1).rstrip(").,;")
            l_wo_url = (l[:murl.start()] + l[murl.end():]).strip()
        else:
            l_wo_url = l

        # Try parse date in parentheses
        date = ""
        mdate = re.search(r"\((\d{4}-\d{2}-\d{2})\)", l_wo_url)
        if mdate:
            date = mdate.group(1)
            l_wo_url = (l_wo_url[:mdate.start()] + l_wo_url[mdate.end():]).strip()

        # Split publisher/title by em dash or hyphen
        publisher = ""
        title = l_wo_url.strip(" .")
        if "—" in l_wo_url:
            parts = [p.strip() for p in l_wo_url.split("—", 1)]
            publisher = parts[0]
            title = parts[1] if len(parts) > 1 else title
        elif " - " in l_wo_url:
            parts = [p.strip() for p in l_wo_url.split(" - ", 1)]
            publisher = parts[0]
            title = parts[1] if len(parts) > 1 else title

        item = {"title": title}
        if n:
            item["n"] = n
        if publisher:
            item["publisher"] = publisher
        if date:
            item["date"] = date
        if url:
            item["url"] = url

        out.append(item)

    return out


# ---------------------------------------------------------------------------
# Pass runners
# ---------------------------------------------------------------------------

def _run_pass_a(
    client: Any,
    config: Dict[str, Any],
    long_specs: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], str, str, str]:
    """
    Run Pass A. Returns: (sources_list, sources_text, script_text, raw_text)
    """
    model = _pick_model_pass_a(config)
    prompt = _build_pass_a_prompt(config, long_specs)

    requested_out = _safe_int(config.get("pass_a_max_output_tokens"), default_max_output_tokens(model))
    max_out = clamp_output_tokens(model, requested_out)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search"}],
        json_mode=False,
        max_completion_tokens=max_out,
    )

    raw_text = extract_completion_text(resp, model)
    raw_text = raw_text.strip() if isinstance(raw_text, str) else ""
    sources_text, script_text = _parse_pass_a_text(raw_text)
    sources_list = _sources_text_to_list(sources_text)

    return sources_list, sources_text, script_text, raw_text


def _run_pass_b_from_pass_a(
    client: Any,
    config: Dict[str, Any],
    nonlong_specs: List[Dict[str, Any]],
    sources_text: str,
    script_text: str,
) -> Dict[str, Any]:
    """
    Pass B derived from Pass A (no web_search). Strict JSON mode.
    """
    model = _pick_model_pass_b(config)
    prompt = _build_pass_b_prompt_from_pass_a(config, nonlong_specs, sources_text, script_text)

    requested_out = _safe_int(config.get("pass_b_max_output_tokens"), default_max_output_tokens(model))
    max_out = clamp_output_tokens(model, requested_out)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=None,
        json_mode=True,
        max_completion_tokens=max_out,
    )

    txt = extract_completion_text(resp, model)
    data = json.loads(txt) if isinstance(txt, str) else {}
    if not isinstance(data, dict):
        raise ValueError("Pass B output is not a JSON object")
    if "content" not in data or not isinstance(data.get("content"), list):
        raise ValueError("Pass B output JSON missing 'content' list")
    return data


def _run_single_pass_b_with_web_search(
    client: Any,
    config: Dict[str, Any],
    nonlong_specs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Single-pass: use web_search and produce all non-long items in one JSON response.
    JSON mode cannot be enforced when web_search is present; we parse best-effort.
    """
    model = _pick_model_pass_b(config)
    prompt = _build_single_pass_b_prompt_with_web_search(config, nonlong_specs)

    requested_out = _safe_int(config.get("pass_b_max_output_tokens"), default_max_output_tokens(model))
    max_out = clamp_output_tokens(model, requested_out)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search"}],
        json_mode=False,  # cannot enforce with web_search
        max_completion_tokens=max_out,
    )

    txt = extract_completion_text(resp, model) or ""
    data = _extract_first_json_object(txt)
    if not isinstance(data, dict):
        raise ValueError("Single-pass output is not a JSON object")
    if "content" not in data or not isinstance(data.get("content"), list):
        raise ValueError("Single-pass output JSON missing 'content' list")
    if "sources" in data and not isinstance(data.get("sources"), list):
        data["sources"] = []
    return data


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def generate_all_content_two_pass(*args, **kwargs) -> Dict[str, Any]:
    """Generate multi-format scripts.

    Supported calls:
      - generate_all_content_two_pass(config, sources=None, client=None, enabled_specs=None)
      - generate_all_content_two_pass(client, config, pass_a_long_script, sources)  (legacy, Pass-B only)
    """
    # Legacy style: (client, config, pass_a_long_script, sources)
    if len(args) >= 4 and not isinstance(args[0], dict):
        client, config, pass_a_long_script, sources = args[0], args[1], args[2], args[3]
        # Legacy: treat pass_a_long_script as LONG_SCRIPT and derive non-long outputs.
        # This keeps older modules working.
        if client is None:
            raise ValueError("OpenAI client is required")
        enabled_specs = kwargs.get("enabled_specs") or []
        _, nonlong_specs = _enabled_specs_from_content_specs(enabled_specs)
        sources_text = ""  # unknown in legacy path
        script_text = str(pass_a_long_script or "").strip()
        out = _run_pass_b_from_pass_a(client, config, nonlong_specs, sources_text, script_text)
        return {"content": out.get("content", []), "sources": sources or [], "pass_a_raw_text": ""}

    # New style: (config, ...)
    if not args or not isinstance(args[0], dict):
        raise TypeError("generate_all_content_two_pass expected first argument to be config dict")

    config: Dict[str, Any] = args[0]
    sources_in: List[Dict[str, Any]] = kwargs.get("sources") or config.get("sources") or []
    enabled_specs: List[Dict[str, Any]] = kwargs.get("enabled_specs") or config.get("enabled_specs") or []
    client = kwargs.get("client")

    if client is None:
        if OpenAI is None:
            raise ImportError("openai package is required. Install with: pip install openai")
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY") or os.getenv("GPT_KEY"))

    long_specs, nonlong_specs = _enabled_specs_from_content_specs(enabled_specs)

    pass_a_raw_text = ""
    sources_out: List[Dict[str, Any]] = []
    content: List[Dict[str, Any]] = []

    if _should_run_pass_a(config, enabled_specs):
        # Pass A: long script only (plain text). Treat incomplete as completed.
        sources_out, sources_text, script_text, pass_a_raw_text = _run_pass_a(client, config, long_specs)

        # Build long content item(s)
        # If multiple long specs exist, duplicate the same script unless caller provides a different strategy.
        for i, spec in enumerate(long_specs):
            code = str(spec.get("code") or f"L{i+1}")
            content.append({
                "code": code,
                "type": "long",
                "script": script_text,
                "max_words": _safe_int(spec.get("target_words") or spec.get("max_words"), 9000),
            })

        # Pass B: generate all non-long items derived from the long script + sources.
        if nonlong_specs:
            out_b = _run_pass_b_from_pass_a(client, config, nonlong_specs, sources_text, script_text)
            content.extend(out_b.get("content", []))

    else:
        # No Pass A. Generate non-long items directly in a single call.
        # If the caller supplied sources, we will include them as-is; otherwise, we use web_search.
        if sources_in:
            # Caller-provided sources path: no web_search, strict JSON mode.
            # We instruct the model to use provided sources only.
            model = _pick_model_pass_b(config)

            req_lines = []
            for s in nonlong_specs:
                c = str(s.get("code") or "").strip()
                t = str(s.get("type") or "").strip()
                mw = _safe_int(s.get("target_words") or s.get("max_words"), 300)
                if c:
                    req_lines.append(f"- {c} ({t}): max_words={mw}")
            req_txt = "\n".join(req_lines) if req_lines else "- (no outputs requested)"

            prompt = f"""You are a newsroom producer and dialogue scriptwriter for an English-language news podcast.

You will be given SOURCE_ITEMS (pre-collected). Do NOT use web_search.
Use only SOURCE_ITEMS for facts.

Requested items:
{req_txt}

SOURCE_ITEMS (JSON):
{json.dumps(sources_in, ensure_ascii=False)}

Return STRICT JSON only:
{{"content":[{{"code":"S1","type":"short","script":"HOST_A:...\\nHOST_B:...","max_words":350}}]}}
"""

            requested_out = _safe_int(config.get("pass_b_max_output_tokens"), default_max_output_tokens(model))
            max_out = clamp_output_tokens(model, requested_out)

            resp = create_openai_completion(
                client=client,
                model=model,
                messages=[{"role": "user", "content": prompt}],
                tools=None,
                json_mode=True,
                max_completion_tokens=max_out,
            )
            txt = extract_completion_text(resp, model)
            out_b = json.loads(txt) if isinstance(txt, str) else {}
            if not isinstance(out_b, dict) or "content" not in out_b or not isinstance(out_b.get("content"), list):
                raise ValueError("Single-pass (sources provided) output JSON missing 'content' list")
            sources_out = sources_in
            content.extend(out_b.get("content", []))
        else:
            out_b = _run_single_pass_b_with_web_search(client, config, nonlong_specs)
            sources_out = out_b.get("sources", []) or []
            content.extend(out_b.get("content", []))

    return {
        "content": content,
        "sources": sources_out,
        "pass_a_raw_text": pass_a_raw_text,
    }


def generate_all_content_with_responses_api(*args, **kwargs) -> Dict[str, Any]:
    """Backward compatible alias."""
    return generate_all_content_two_pass(*args, **kwargs)
