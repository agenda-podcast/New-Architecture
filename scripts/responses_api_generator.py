#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Two-pass script generation using the OpenAI Responses API.

Updated behavior (Dec 2025 + mock-mode support):

Pass A:
- Only used for long scripts (type == "long") AND only when:
  - long is enabled AND
  - NOT testing/gesting mode AND
  - NO test data source file present
- Pass A outputs PLAIN TEXT (no JSON):
    SOURCES:
    - [1] Publisher — Title (YYYY-MM-DD). URL
    SCRIPT:
    HOST_A: ...
    HOST_B: ...

Pass B:
- Always returns ONE JSON object with ALL non-long items in ONE response.
- If Pass A ran: derive from Pass A script and sources (no new facts, no web_search).
- If Pass A skipped: generate non-long items directly (may do not browse the web unless sources provided).

Mock mode (NEW):
- If Testing Mode is True AND a Source Text file exists:
  - DO NOT call OpenAI at all.
  - Create mock Pass A (SOURCES + SCRIPT plain text) and mock Pass B (single JSON with all items).
  - Return the same shape as normal:
      {"content":[...], "sources":[...], "pass_a_raw_text":"..."}
- If Testing Mode is True AND Source Text file does NOT exist:
  - This module will not create it (script_generate will), but will still fall back to minimal mocks.

Source Text file format supported (plain text):
- If the file contains these headers, they will be parsed:
    SOURCES:
    - [1] ...
    FULL_TEXT:
    <full article text...>
  Also accepts TEXT: instead of FULL_TEXT:
- If headers absent: entire file is treated as FULL_TEXT.

"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional: used for custom HTTP transport to mitigate CI proxy disconnects.
try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None

try:
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


def _count_words(s: str) -> int:
    return len([w for w in re.split(r"\s+", (s or "").strip()) if w])


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
        # Fallback: model returned plain text; wrap it into a minimal JSON object.
        return {"script": t}

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


# ---------------------------------------------------------------------------
# Hosts / roles resolver (ROBUST: supports dict and list)
# ---------------------------------------------------------------------------

def _resolve_hosts(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Robust host resolver.

    Supports config["roles"] in multiple shapes:
    1) dict:
       {"host_a": {"name": "...", "bio": "..."}, "host_b": {...}}
    2) dict with uppercase keys:
       {"HOST_A": {...}, "HOST_B": {...}}
    3) list:
       [{"role":"host_a","name":"...","bio":"..."}, {"role":"host_b",...}]
       or simply [{...}, {...}] where first=A second=B
    """
    roles = config.get("roles") or {}

    # Normalize roles if it's a list
    if isinstance(roles, list):
        host_a: Dict[str, Any] = {}
        host_b: Dict[str, Any] = {}

        for item in roles:
            if not isinstance(item, dict):
                continue
            key = (
                item.get("role")
                or item.get("id")
                or item.get("code")
                or item.get("key")
                or ""
            )
            k = str(key).strip().lower()

            if k in ("host_a", "host a", "a", "hosta", "primary", "main"):
                host_a = item
            elif k in ("host_b", "host b", "b", "hostb", "cohost", "co-host", "secondary"):
                host_b = item

        if not host_a and len(roles) >= 1 and isinstance(roles[0], dict):
            host_a = roles[0]
        if not host_b and len(roles) >= 2 and isinstance(roles[1], dict):
            host_b = roles[1]

        roles = {"host_a": host_a, "host_b": host_b}

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


# ---------------------------------------------------------------------------
# Spec helpers
# ---------------------------------------------------------------------------

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
    # 1) config flags
    if _truthy(config.get("testing_mode")):
        return True
    if _truthy(config.get("gesting_mode")):
        return True
    if _truthy(config.get("gisting_mode")):
        return True

    # 2) env flags
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
# Source Text file support + mock mode
# ---------------------------------------------------------------------------

def _source_text_file_path(config: Dict[str, Any]) -> Optional[Path]:
    """
    Locate a Source Text file path from config.
    Supported keys:
      - source_text_file
      - sources_text_file
      - source_text_path
      - sources_text_path
    """
    candidates = [
        config.get("source_text_file"),
        config.get("sources_text_file"),
        config.get("source_text_path"),
        config.get("sources_text_path"),
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(str(c))
        if p.is_file():
            return p
    return None


def _split_source_text_file(text: str) -> Tuple[str, str]:
    """
    Return (sources_text, full_text) from a source text file content.

    Supported headers:
      SOURCES:
      FULL_TEXT:
    or
      SOURCES:
      TEXT:
    """
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not t.strip():
        return "", ""

    m_sources = re.search(r"(?im)^\s*sources\s*:\s*$", t)
    m_full = re.search(r"(?im)^\s*(full_text|text)\s*:\s*$", t)

    if not m_sources and not m_full:
        return "", t.strip()

    sources_text = ""
    full_text = ""

    if m_sources and m_full:
        if m_sources.start() < m_full.start():
            sources_text = t[m_sources.end() : m_full.start()].strip()
            full_text = t[m_full.end() :].strip()
        else:
            # uncommon ordering; treat everything after FULL_TEXT as full_text
            sources_text = ""
            full_text = t[m_full.end() :].strip()
        return _normalize_ws(sources_text), _normalize_ws(full_text)

    # If only FULL_TEXT exists
    if m_full and not m_sources:
        full_text = t[m_full.end() :].strip()
        return "", _normalize_ws(full_text)

    # If only SOURCES exists
    if m_sources and not m_full:
        sources_text = t[m_sources.end() :].strip()
        return _normalize_ws(sources_text), ""

    return "", t.strip()


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

        date = ""
        mdate = re.search(r"\((\d{4}-\d{2}-\d{2})\)", l_wo_url)
        if mdate:
            date = mdate.group(1)
            l_wo_url = (l_wo_url[:mdate.start()] + l_wo_url[mdate.end():]).strip()

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


def _sentences_from_text(text: str) -> List[str]:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return []
    # basic sentence split
    parts = re.split(r"(?<=[\.\!\?])\s+", t)
    return [p.strip() for p in parts if p and p.strip()]


def _mock_dialogue_from_text(full_text: str, target_words: int, min_lines: int = 20) -> str:
    """
    Deterministic mock dialogue generator: alternates HOST_A/HOST_B by sentence,
    until target_words reached.
    """
    target_words = max(120, int(target_words or 0))
    sents = _sentences_from_text(full_text)

    if not sents:
        # hard fallback
        base = [
            "HOST_A: [MOCK] Source text is empty or missing. Provide FULL_TEXT in the source text file.",
            "HOST_B: [MOCK] Once FULL_TEXT is present, this mock generator will build realistic dialogue.",
        ]
        # extend to satisfy downstream parsers
        while _count_words("\n".join(base)) < min(target_words, 250):
            base.append("HOST_A: [MOCK] Placeholder continuation.")
            base.append("HOST_B: [MOCK] Placeholder continuation.")
        return "\n".join(base).strip()

    lines: List[str] = []
    word_budget = target_words
    speaker_a = True
    i = 0

    while i < len(sents) and _count_words("\n".join(lines)) < word_budget:
        spk = "HOST_A" if speaker_a else "HOST_B"
        sent = sents[i]
        lines.append(f"{spk}: {sent}")
        speaker_a = not speaker_a
        i += 1

    # Ensure minimum dialogue density for downstream processing
    while len(lines) < min_lines:
        spk = "HOST_A" if speaker_a else "HOST_B"
        lines.append(f"{spk}: [MOCK] Continuation segment.")
        speaker_a = not speaker_a

    return "\n".join(lines).strip()


def _truncate_dialogue_to_words(dialogue: str, max_words: int) -> str:
    if max_words <= 0:
        return dialogue.strip()
    words = re.split(r"\s+", dialogue.strip())
    if len(words) <= max_words:
        return dialogue.strip()
    cut = " ".join(words[:max_words]).strip()
    # try to cut to last punctuation for cleaner end
    m = re.search(r"^(.+[\.\!\?])\s", cut[::-1])
    return cut


def _make_mock_outputs_from_source_text(config: Dict[str, Any], enabled_specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build:
      - pass_a_raw_text (plain text SOURCES+SCRIPT) if long enabled, otherwise empty
      - content list for ALL enabled specs (long + non-long)
      - sources list
    """
    src_path = _source_text_file_path(config)
    src_text = ""
    if src_path and src_path.is_file():
        src_text = src_path.read_text(encoding="utf-8", errors="ignore")
    sources_text, full_text = _split_source_text_file(src_text)

    sources_list = _sources_text_to_list(sources_text)

    # If no structured sources, create at least one local reference
    if not sources_list:
        sources_list = [{
            "n": 1,
            "publisher": "LOCAL",
            "title": "Source Text File",
            "date": "",
            "url": f"file://{str(src_path) if src_path else 'missing'}",
        }]

    long_specs, nonlong_specs = _enabled_specs_from_content_specs(enabled_specs)

    # Long script (Pass A mock) - script-only JSON to match real Pass A output
    pass_a_raw_text = ""
    long_script_text = ""
    if long_specs:
        target_words = 9000
        for s in long_specs:
            target_words = max(target_words, _safe_int(s.get("target_words") or s.get("max_words"), 9000))

        long_script_text = _mock_dialogue_from_text(full_text or src_text, target_words=target_words)

        pass_a_raw_text = json.dumps({"script": long_script_text.strip()}, ensure_ascii=False)

    # Build content list for all items
    content: List[Dict[str, Any]] = []

    # long items use the same long_script_text
    for i, spec in enumerate(long_specs):
        code = str(spec.get("code") or f"L{i+1}")
        mw = _safe_int(spec.get("target_words") or spec.get("max_words"), 9000)
        content.append({
            "code": code,
            "type": "long",
            "script": _truncate_dialogue_to_words(long_script_text, mw),
            "max_words": mw,
        })

    # non-long items: summarized parts per item
    # Requirement: "Pass B we need to get only summarized parts per each item of each content type."
    # Here: simply take the first N words from the long_script_text (or build from full_text if no long).
    base_for_summary = long_script_text or _mock_dialogue_from_text(full_text or src_text, target_words=2000)

    for spec in nonlong_specs:
        code = str(spec.get("code") or "X1")
        t = str(spec.get("type") or "unknown")
        mw = _safe_int(spec.get("target_words") or spec.get("max_words"), 350)

        # create a short/medium/reel from the base text, capped to mw
        short_script = _truncate_dialogue_to_words(base_for_summary, mw)
        # ensure it starts with HOST_A
        if not short_script.strip().upper().startswith("HOST_A:"):
            short_script = "HOST_A: [MOCK] " + short_script.strip()

        content.append({
            "code": code,
            "type": t,
            "script": short_script.strip(),
            "max_words": mw,
        })

    return {
        "content": content,
        "sources": sources_list,
        "pass_a_raw_text": pass_a_raw_text.strip(),
    }


# ---------------------------------------------------------------------------
# Prompt builders (real OpenAI paths)
# ---------------------------------------------------------------------------

def _pick_model_pass_a(config: Dict[str, Any]) -> str:
    return (os.getenv("PASS_A_MODEL") or config.get("gpt_model_pass_a") or "gpt-5.2-pro").strip()


def _pick_model_pass_b(config: Dict[str, Any]) -> str:
    return (os.getenv("PASS_B_MODEL") or config.get("gpt_model_pass_b") or "gpt-5-nano").strip()


def _build_pass_a_prompt(config: Dict[str, Any], long_specs: List[Dict[str, Any]]) -> str:
    """Build the Pass A prompt.

    Pass A returns ONLY strict JSON and MUST contain ONLY the long dialogue script.
    Web sources must NOT be included in the output (to keep output size stable and
    to simplify downstream Pass B inputs).
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

    target_words = 9000
    for s in long_specs:
        target_words = max(target_words, _safe_int(s.get("target_words") or s.get("max_words"), 9000))

    return f"""System: Return only valid JSON.

You are Pass A of a two-pass dialogue pipeline.

Topic: {topic}
Topic description: {desc}

Host personas:
- HOST_A ({hosts['host_a_name']}): {hosts['host_a_bio']}
- HOST_B ({hosts['host_b_name']}): {hosts['host_b_bio']}

Write ONE long dialogue script of EXACTLY {target_words} words between HOST_A and HOST_B.

Rules:
- Use concrete dates when you mention time.
- No bullet lists; write as spoken dialogue.
- Use speaker tags HOST_A: and HOST_B:.
- Output MUST be a single JSON object.
- The JSON object MUST contain ONLY one key: "script".
- Do NOT include sources, citations, URLs, or any other keys.

JSON output schema:
{{
  "script": "HOST_A: ...\\nHOST_B: ..."
}}
"""


def _build_pass_b_prompt_from_pass_a(
    config: Dict[str, Any],
    nonlong_specs: List[Dict[str, Any]],
    pass_a_json_text: str,
) -> str:
    """
    Pass B prompt when Pass A ran: derive summaries from Pass A script only.
    Must return ONE JSON object with ALL items.
    """
    topic = str(config.get("title") or config.get("topic") or "").strip() or "(untitled topic)"

    req_lines: List[str] = []
    for s in nonlong_specs:
        c = str(s.get("code") or "").strip()
        t = str(s.get("type") or "").strip()
        mw = _safe_int(s.get("target_words") or s.get("max_words"), 300)
        if not c:
            continue
        # Do NOT require exact word counts; exact targets can cause model-side refusal.
        # Treat mw as an upper bound.
        req_lines.append(f"- {c} ({t}): max_words={mw} (at most; may be shorter)")

    req_txt = "\n".join(req_lines) if req_lines else "- (no Pass B outputs requested)"

    return f"""You are Pass B of a two-pass pipeline.

You will be given PASS_A_JSON (a strict JSON object) containing a single key: "script".

Your task:
- Create summarized/derived scripts for each requested item below.
- Do NOT introduce new facts. Use ONLY what is supported by PASS_A_JSON.script.
- Return ALL items in ONE response as STRICT JSON (no markdown).

Topic: {topic}

Requested items:
{req_txt}

PASS_A_JSON:
{pass_a_json_text}

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
- Keep each script within max_words (at most; being shorter is acceptable).
- Return ONLY the JSON object.
"""


def _build_single_pass_b_prompt(config: Dict[str, Any], nonlong_specs: List[Dict[str, Any]]) -> str:
    """Single-pass generation (no Pass A). Returns all requested items in one JSON response.

    Note: This prompt must not instruct the model to browse the web. It should work from its internal knowledge
    and the provided topic description only.
    """
    hosts = _resolve_hosts(config)

    topic = str(config.get("title") or config.get("topic") or "").strip() or "(untitled topic)"
    desc = str(config.get("description") or "").strip()

    req_lines: List[str] = []
    for s in nonlong_specs:
        c = str(s.get("code") or "").strip()
        t = str(s.get("type") or "").strip()
        mw = _safe_int(s.get("target_words") or s.get("max_words"), 300)
        if not c:
            continue
        # Do NOT require exact word counts; exact targets can cause model-side refusal.
        # Treat mw as an upper bound.
        req_lines.append(f"- {c} ({t}): max_words={mw} (at most; may be shorter)")
    req_txt = "\n".join(req_lines) if req_lines else "- (none)"

    host_a = hosts.get("HOST_A") or {}
    host_b = hosts.get("HOST_B") or {}

    persona_block = f"""Personas:
HOST_A: {host_a.get('name','HOST_A')} — {host_a.get('summary','')}
HOST_B: {host_b.get('name','HOST_B')} — {host_b.get('summary','')}

Constraints:
- Return ONLY valid JSON.
- Do not add any facts or sources not implied by the topic description.
- Use speaker tags HOST_A: and HOST_B: at the start of lines.
"""

    prompt = f"""System: Return only valid JSON.

You are generating multiple short scripts from existing context (no external browsing).
Topic: {topic}
Topic description: {desc}

{persona_block}

Targets to generate (all in ONE JSON object):
{req_txt}

Output format:
{{ "items": [ {{ "code": "S1", "text": "..." }}, ... ] }}
"""
    return prompt

def _parse_pass_a_text(pass_a_text: str) -> Tuple[str, str]:
    """
    Extract (sources_text, script_text) from Pass A plain text.
    """
    t = (pass_a_text or "").strip()
    if not t:
        return "", ""

    t = t.replace("\r\n", "\n").replace("\r", "\n")

    m_sources = re.search(r"(?im)^\s*sources\s*:\s*$", t)
    m_script = re.search(r"(?im)^\s*script\s*:\s*$", t)

    if not m_sources or not m_script:
        return "", t.strip()

    sources_start = m_sources.end()
    script_start = m_script.end()

    if m_sources.start() < m_script.start():
        sources_text = t[sources_start : m_script.start()].strip()
        script_text = t[script_start :].strip()
    else:
        sources_text = ""
        script_text = t[script_start :].strip()

    return _normalize_ws(sources_text), _normalize_ws(script_text)




def _estimate_max_output_tokens_from_specs(specs: list[dict], *, tokens_per_word: float = 2.2, overhead: int = 2500, floor: int = 4096) -> int:
    """Estimate an appropriate `max_output_tokens` for a set of requested content specs.

    This is a reliability guard: requesting the *model maximum* output tokens for every call increases the chance
    of network/proxy disconnects on long-running responses. Instead, we size the budget to what the request
    actually needs (still within the model's hard cap), while allowing an explicit override via config/env.
    """
    total_words = 0
    for s in specs or []:
        try:
            mw = _safe_int(s.get('target_words') or s.get('max_words'), 0)
        except Exception:
            mw = 0
        if mw > 0:
            total_words += mw

    est = int((int(total_words * tokens_per_word) + int(overhead)) * 2)
    if est < floor:
        est = floor
    return est
# ---------------------------------------------------------------------------
# Pass runners (real OpenAI paths)
# ---------------------------------------------------------------------------

def _run_pass_a(
    client: Any,
    config: Dict[str, Any],
    long_specs: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], str, str, str]:
    """
    Run Pass A.

    Returns: (sources_list, sources_text, script_text, raw_text)

    Notes:
      - Pass A now returns strict JSON with ONLY {"script": ...}.
      - sources_list and sources_text are returned as empty for backward compatibility.
    """
    model = _pick_model_pass_a(config)
    prompt = _build_pass_a_prompt(config, long_specs)

    requested_cfg = config.get("pass_a_max_output_tokens")
    force_max = str(os.getenv("OPENAI_FORCE_MAX_OUTPUT", "false")).strip().lower() in ("1", "true", "yes", "y")
    if requested_cfg is None and not force_max:
        requested_out = _estimate_max_output_tokens_from_specs(long_specs)
    else:
        # Respect explicit config override, but optionally cap oversize values unless force_max is set.
        requested_out = _safe_int(requested_cfg, default_max_output_tokens(model))
        if not force_max:
            est = _estimate_max_output_tokens_from_specs(long_specs)
            if requested_out > int(est * 1.8):
                logger.warning(f"pass_a_max_output_tokens={requested_out} is far above estimated need ({est}); capping to estimate for stability. Set OPENAI_FORCE_MAX_OUTPUT=true to override.")
                requested_out = est
    max_out = clamp_output_tokens(model, requested_out)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=None,
        json_mode=True,
        max_completion_tokens=max_out,
    )

    raw_text = extract_completion_text(resp, model)
    raw_text = raw_text.strip() if isinstance(raw_text, str) else ""

    # Pass A is expected to be strict JSON: {"script": "..."}
    data: Any = None
    try:
        data = json.loads(raw_text) if raw_text else None
    except Exception:
        data = _extract_first_json_object(raw_text)

    script_text = ""
    if isinstance(data, dict):
        script_text = str(data.get("script") or "").strip()
    else:
        # Best-effort fallback: treat raw text as the script.
        script_text = raw_text

    return [], "", script_text, raw_text


def _run_pass_b_from_pass_a(
    client: Any,
    config: Dict[str, Any],
    nonlong_specs: List[Dict[str, Any]],
    pass_a_json_text: str,
) -> Dict[str, Any]:
    """
    Pass B derived from Pass A (no external browsing). Strict JSON mode.
    """
    model = _pick_model_pass_b(config)
    prompt = _build_pass_b_prompt_from_pass_a(config, nonlong_specs, pass_a_json_text)

    requested_cfg = config.get("pass_b_max_output_tokens")
    force_max = str(os.getenv("OPENAI_FORCE_MAX_OUTPUT", "false")).strip().lower() in ("1", "true", "yes", "y")
    if requested_cfg is None and not force_max:
        requested_out = _estimate_max_output_tokens_from_specs(nonlong_specs, tokens_per_word=2.0, overhead=1800, floor=2048)
    else:
        requested_out = _safe_int(requested_cfg, default_max_output_tokens(model))
        if not force_max:
            est = _estimate_max_output_tokens_from_specs(nonlong_specs, tokens_per_word=2.0, overhead=1800, floor=2048)
            if requested_out > int(est * 2.0):
                logger.warning(f"pass_b_max_output_tokens={requested_out} is far above estimated need ({est}); capping to estimate for stability. Set OPENAI_FORCE_MAX_OUTPUT=true to override.")
                requested_out = est
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


def _run_single_pass_b(
    client: Any,
    config: Dict[str, Any],
    nonlong_specs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Single-pass: do not browse the web and produce all non-long items in one JSON response.
    JSON mode cannot be enforced when strict JSON mode is not enforceable; we parse best-effort.
    """
    model = _pick_model_pass_b(config)
    prompt = _build_single_pass_b_prompt(config, nonlong_specs)

    requested_cfg = config.get("pass_b_max_output_tokens")
    force_max = str(os.getenv("OPENAI_FORCE_MAX_OUTPUT", "false")).strip().lower() in ("1", "true", "yes", "y")
    if requested_cfg is None and not force_max:
        requested_out = _estimate_max_output_tokens_from_specs(nonlong_specs, tokens_per_word=2.0, overhead=1800, floor=2048)
    else:
        requested_out = _safe_int(requested_cfg, default_max_output_tokens(model))
        if not force_max:
            est = _estimate_max_output_tokens_from_specs(nonlong_specs, tokens_per_word=2.0, overhead=1800, floor=2048)
            if requested_out > int(est * 2.0):
                logger.warning(f"pass_b_max_output_tokens={requested_out} is far above estimated need ({est}); capping to estimate for stability. Set OPENAI_FORCE_MAX_OUTPUT=true to override.")
                requested_out = est
    max_out = clamp_output_tokens(model, requested_out)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=None,
        json_mode=False,
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
    """
    Generate multi-format scripts.

    Supported calls:
      - generate_all_content_two_pass(config, sources=None, client=None, enabled_specs=None)
      - generate_all_content_two_pass(client, config, pass_a_long_script, sources)  (legacy, Pass-B only)
    """
    # Legacy style: (client, config, pass_a_long_script, sources)
    if len(args) >= 4 and not isinstance(args[0], dict):
        client, config, pass_a_long_script, sources = args[0], args[1], args[2], args[3]
        if client is None:
            raise ValueError("OpenAI client is required")
        enabled_specs = kwargs.get("enabled_specs") or []
        _, nonlong_specs = _enabled_specs_from_content_specs(enabled_specs)
        script_text = str(pass_a_long_script or "").strip()
        pass_a_json_text = json.dumps({"script": script_text}, ensure_ascii=False)
        out = _run_pass_b_from_pass_a(client, config, nonlong_specs, pass_a_json_text)
        return {"content": out.get("content", []), "sources": sources or [], "pass_a_raw_text": ""}

    # New style: (config, ...)
    if not args or not isinstance(args[0], dict):
        raise TypeError("generate_all_content_two_pass expected first argument to be config dict")

    config: Dict[str, Any] = args[0]
    sources_in: List[Dict[str, Any]] = kwargs.get("sources") or config.get("sources") or []
    enabled_specs: List[Dict[str, Any]] = kwargs.get("enabled_specs") or config.get("enabled_specs") or []
    client = kwargs.get("client")

    # -----------------------------------------------------------------------
    # MOCK MODE: Testing mode + Source Text file present (or created upstream)
    # -----------------------------------------------------------------------
    if _is_testing_or_gesting_mode(config):
        # If source text file exists -> generate mocks based on it.
        # If missing -> still produce minimal mocks so pipeline can continue.
        mock = _make_mock_outputs_from_source_text(config, enabled_specs)
        return mock

    # Real mode: create OpenAI client if needed
    if client is None:
        if OpenAI is None:
            raise ImportError("openai package is required. Install with: pip install openai")
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GPT_KEY")
        # Long-form script generation can take minutes for large outputs.
        # Increase timeouts and retries to reduce transient disconnect failures in CI.
        timeout_s = float(os.getenv("OPENAI_TIMEOUT", "600"))
        # NOTE: this controls SDK-level retries. Default remains 0 to preserve your
        # "one request per pass" policy. If you want automatic retries on transient
        # disconnects, set OPENAI_MAX_RETRIES to a small number (e.g., 1-2).
        max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "0"))

        # CI/CD environments sometimes sit behind proxies that are more stable over HTTP/2.
        # When available, we can pass a custom httpx client to the OpenAI SDK.
        http_client = None
        use_http2 = str(os.getenv("OPENAI_HTTP2", "true")).strip().lower() in ("1", "true", "yes", "y")
        if httpx is not None and use_http2:
            try:
                limits = httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=60)
                http_client = httpx.Client(http2=True, timeout=timeout_s, limits=limits)
            except Exception as e:
                logger.warning("Failed to init custom httpx client (HTTP/2). Falling back to SDK default: %s", str(e))
                http_client = None

        if http_client is not None:
            client = OpenAI(api_key=api_key, timeout=timeout_s, max_retries=max_retries, http_client=http_client)
        else:
            client = OpenAI(api_key=api_key, timeout=timeout_s, max_retries=max_retries)

    long_specs, nonlong_specs = _enabled_specs_from_content_specs(enabled_specs)

    pass_a_raw_text = ""
    sources_out: List[Dict[str, Any]] = []
    content: List[Dict[str, Any]] = []

    if _should_run_pass_a(config, enabled_specs):
        # Pass A: long script only (plain text). Treat incomplete as completed.
        sources_out, _sources_text_unused, script_text, pass_a_raw_text = _run_pass_a(client, config, long_specs)

        # Build long content item(s)
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
            # Pass B consumes the Pass A JSON (script-only) to avoid re-parsing.
            out_b = _run_pass_b_from_pass_a(client, config, nonlong_specs, pass_a_raw_text or json.dumps({"script": script_text}, ensure_ascii=False))
            content.extend(out_b.get("content", []))

    else:
        # No Pass A. Generate non-long items directly in a single call.
        if sources_in:
            model = _pick_model_pass_b(config)

            req_lines = []
            for s in nonlong_specs:
                c = str(s.get("code") or "").strip()
                t = str(s.get("type") or "").strip()
                mw = _safe_int(s.get("target_words") or s.get("max_words"), 300)
                if c:
                    req_lines.append(f"- {c} ({t}): max_words={mw} (at most; may be shorter)")
            req_txt = "\n".join(req_lines) if req_lines else "- (no outputs requested)"

            prompt = f"""You are a newsroom producer and dialogue scriptwriter for an English-language news podcast.

You will be given SOURCE_ITEMS (pre-collected). Do NOT do not browse the web.
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
            # If no L1 is requested, we may still have an existing Source Text file
            # (mock-data / pre-collected context). In that case, use it as the
            # SOURCE_TEXT for Pass B instead of relying only on the topic description.
            st_path = _source_text_file_path(config)
            if st_path is not None:
                try:
                    st_raw = st_path.read_text(encoding="utf-8")
                except Exception:
                    st_raw = st_path.read_text(errors="ignore")
                st_sources_text, st_full_text = _split_source_text_file(st_raw)
                pass_a_json_text = json.dumps({"script": st_full_text}, ensure_ascii=False)
                out_b = _run_pass_b_from_pass_a(client, config, nonlong_specs, pass_a_json_text)
                sources_out = _sources_text_to_list(st_sources_text)
                content.extend(out_b.get("content", []))
            else:
                out_b = _run_single_pass_b(client, config, nonlong_specs)
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