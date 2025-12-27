#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Two-pass script generation using the OpenAI Responses API.

This module is used by ``multi_format_generator.py``.

The repository went through several refactors, and different files expect
different call signatures. To keep the pipeline stable, we support both:

1) New architecture (called by multi_format_generator):

    generate_all_content_two_pass(config, sources=None, client=None) -> dict
      Returns: {"content": [ {code,type,script,...}, ... ], "sources": [...], "canonical_pack": {...} }

2) Legacy compatibility (older callers):

    generate_all_content_two_pass(client, config, pass_a_long_script, sources) -> dict
      Returns: {"content": [ ... ]}  (Pass-B only)

Pass A uses a reasoning model with the web_search tool to produce a structured
"canonical pack" plus optional long-form scripts (L*). Pass B produces the
remaining scripts (M/S/R) STRICTLY from the canonical pack, with JSON output.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None

_CODE_PREFIX = {"long": "L", "medium": "M", "short": "S", "reels": "R"}
from model_limits import clamp_output_tokens, default_max_output_tokens
from openai_utils import create_openai_completion, extract_completion_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

DEFAULT_PASS_A_MODEL = "gpt-5.2-pro"
DEFAULT_PASS_B_MODEL = "gpt-5-nano"


def _pick_model_pass_a(config: Dict[str, Any]) -> str:
    return os.getenv("PASS_A_MODEL") or config.get("gpt_model_pass_a") or config.get("gpt_model") or DEFAULT_PASS_A_MODEL


def _pick_model_pass_b(config: Dict[str, Any]) -> str:
    return os.getenv("PASS_B_MODEL") or config.get("gpt_model_pass_b") or DEFAULT_PASS_B_MODEL


def _normalize_reasoning_effort_for_model(model: str, requested: str) -> str:
    """Prevent 400s from invalid reasoning.effort values.

    In this repo's architecture notes, gpt-5.2-pro is treated as requiring
    medium/high/xhigh; using minimal/low can 400.
    """
    m = (model or "").strip().lower()
    r = (requested or "").strip().lower() or "medium"

    if m == "gpt-5.2-pro":
        if r not in ("medium", "high", "xhigh"):
            logger.warning("gpt-5.2-pro does not support reasoning.effort='%s'. Using 'medium'.", r)
            return "medium"
        return r

    # For other models we pass through; if unsupported, the API will error.
    return r


def _pass_a_reasoning(config: Dict[str, Any], model: str) -> Dict[str, str]:
    requested = os.getenv("PASS_A_REASONING_EFFORT") or str(config.get("pass_a_reasoning_effort") or "medium")
    return {"effort": _normalize_reasoning_effort_for_model(model, requested)}


def _pass_b_reasoning(config: Dict[str, Any], model: str) -> Dict[str, str]:
    requested = os.getenv("PASS_B_REASONING_EFFORT") or str(config.get("pass_b_reasoning_effort") or "minimal")
    return {"effort": _normalize_reasoning_effort_for_model(model, requested)}


# ---------------------------------------------------------------------------
# Client / JSON helpers
# ---------------------------------------------------------------------------

def _get_openai_client(explicit_client: Any | None = None) -> Any:
    if explicit_client is not None:
        return explicit_client

    api_key = os.getenv("GPT_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("GPT_KEY or OPENAI_API_KEY environment variable is required")
    if OpenAI is None:
        raise ImportError("openai package is required. Install with: pip install openai")
    return OpenAI(api_key=api_key)


def _extract_first_json_object(text: str) -> Dict[str, Any]:
    """Extract the first JSON object found in `text`.

    Pass A uses web_search, so we cannot force strict JSON via SDK flags.
    We therefore parse "best effort".
    """
    if not text:
        raise ValueError("Empty model output; expected JSON")

    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass

    # Find a JSON object block
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Unable to locate JSON object in model output")

    candidate = text[start : end + 1]
    # Strip code fences if present
    candidate = re.sub(r"^```(json)?\s*", "", candidate.strip(), flags=re.IGNORECASE)
    candidate = re.sub(r"\s*```$", "", candidate.strip())
    return json.loads(candidate)


def _safe_int(x: Any, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _clean_bio(text: str) -> str:
    # Light cleanup to avoid template artifacts.
    return re.sub(r"\s+", " ", (text or "").strip())


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _resolve_hosts(config: Dict[str, Any]) -> Dict[str, str]:
    host_a_name = str(config.get("voice_a_name") or "Host A").strip()
    host_b_name = str(config.get("voice_b_name") or "Host B").strip()
    host_a_bio = _clean_bio(str(config.get("voice_a_bio") or ""))
    host_b_bio = _clean_bio(str(config.get("voice_b_bio") or ""))
    # Replace template variables if present
    host_b_bio = host_b_bio.replace("{{HOST_A}}", host_a_name).replace("HOST_A", host_a_name)
    return {
        "host_a_name": host_a_name,
        "host_b_name": host_b_name,
        "host_a_bio": host_a_bio,
        "host_b_bio": host_b_bio,
    }


def _desired_pass_a_words(enabled_specs: List[Dict[str, Any]]) -> int:
    """Pick a reasonable Pass A word budget.

    - If long content is enabled, use that max_words.
    - Otherwise generate a compact but information-rich pack for summarization.
    """
    long_specs = [s for s in enabled_specs if s.get("type") == "long"]
    if long_specs:
        return max(_safe_int(s.get("max_words"), 8000) for s in long_specs)

    # When long is disabled, produce something big enough to anchor S/R.
    nonlong_max = 0
    for s in enabled_specs:
        nonlong_max = max(nonlong_max, _safe_int(s.get("max_words"), 400))
    return max(1500, min(6000, nonlong_max * 6))


def _build_pass_a_prompt(config: Dict[str, Any], enabled_specs: List[Dict[str, Any]]) -> str:
    hosts = _resolve_hosts(config)

    topic = str(config.get("title") or config.get("topic") or "").strip() or "(untitled topic)"
    desc = str(config.get("description") or "").strip()

    freshness_hours = _safe_int(config.get("freshness_hours"), 24)
    freshness_window = f"last {freshness_hours} hours"
    regions = config.get("search_regions") or []
    region_txt = ", ".join([str(r).upper() for r in regions]) if regions else "GLOBAL"
    queries = config.get("queries") or []
    query_txt = "\n".join([f"- {q}" for q in queries]) if queries else "- (use your judgment)"

    l_words = _desired_pass_a_words(enabled_specs)

    # If the topic config explicitly allows rumors, respect it; default to False.
    rumors_allowed = bool(config.get("rumors_allowed", False))

    return f"""You are a newsroom producer and dialogue scriptwriter for an English-language news podcast.
You MUST use the web_search tool before writing to verify the latest developments and to avoid any 'knowledge cutoff' disclaimers. Never say you cannot browse.
If sources within the window are limited, say: "sources within the window are limited" and use the most recent credible sources.

Historical Context & Analysis:
- Use web_search for RECENT news within the freshness window (breaking news, latest developments, fresh quotes)
- Use your EXISTING KNOWLEDGE for historical context, background information, and deeper analysis
- Combine both: Frame recent news with historical patterns, precedents, and context you already know

Topic: {topic}
Topic description: {desc}
Freshness window: {freshness_window}
Region: {region_txt}
Rumors allowed: {str(rumors_allowed).lower()}

Host personas:
- HOST_A ({hosts['host_a_name']}): {hosts['host_a_bio']}
- HOST_B ({hosts['host_b_name']}): {hosts['host_b_bio']}

Search guidance (use as web_search queries; adjust as needed):
{query_txt}

Your job in Pass A:
1) Use web_search to gather and cross-check facts from multiple reputable sources.
2) Produce a CANONICAL_PACK that can be used to generate consistent summaries.
3) Optionally produce a long "SOURCE_TEXT" (about {l_words} words) in HOST_A/HOST_B dialogue format that reflects:
   - Recent verified developments
   - Historical context and analysis
   - Clear transitions and structure

OUTPUT FORMAT (single JSON object):
{{
  "sources": [{{"title": "...", "url": "...", "publisher": "...", "date": "YYYY-MM-DD"}}],
  "canonical_pack": {{
    "timeline": "...",
    "key_facts": "...",
    "key_players": "...",
    "claims_evidence": "...",
    "beats_outline": "...",
    "punchlines": "...",
    "historical_context": "..."
  }},
  "source_text": "HOST_A: ...\\nHOST_B: ...\\n...",
  "long_content": [{{"code": "L1", "type": "long", "script": "HOST_A: ...\\nHOST_B: ..."}}]
}}

Rules:
- Keep all factual claims grounded in sources from web_search.
- Use concrete dates when possible.
- The JSON must be valid.
"""


def _build_pass_b_prompt(
    config: Dict[str, Any],
    enabled_specs: List[Dict[str, Any]],
    canonical_pack: Dict[str, Any],
    source_text: str,
) -> str:
    hosts = _resolve_hosts(config)

    # Build a deterministic list of requested outputs.
    # Each spec has {type, code, max_words}.
    req_lines = []
    for s in enabled_specs:
        c = str(s.get("code") or "").strip()
        t = str(s.get("type") or "").strip()
        mw = _safe_int(s.get("max_words"), 300)
        if not c or t == "long":
            continue
        req_lines.append(f"- {c} ({t}): max_words={mw}")

    req_txt = "\n".join(req_lines) if req_lines else "- (no Pass B outputs requested)"

    return f"""You are Pass B of a two-pass pipeline.

You will be given:
1) CANONICAL_PACK (facts, timeline, players, evidence, historical context)
2) SOURCE_TEXT (dialogue-style anchor text)

Your task:
- Generate the requested scripts ONLY from CANONICAL_PACK and SOURCE_TEXT.
- Do not add new facts, quotes, or numbers not already present.
- Keep tone consistent with the host personas.
- Output MUST be valid JSON.

Hosts:
- HOST_A is {hosts['host_a_name']}
- HOST_B is {hosts['host_b_name']}

Requested outputs:
{req_txt}

Formatting rules for each script:
- Dialogue must use HOST_A: and HOST_B: prefixes.
- No markdown.
- Respect max_words.

INPUTS:
CANONICAL_PACK:
{json.dumps(canonical_pack, ensure_ascii=False)}

SOURCE_TEXT:
{source_text}

OUTPUT JSON schema:
{{
  "content": [
    {{"code": "S1", "type": "short", "script": "HOST_A: ...\\nHOST_B: ..."}},
    ...
  ]
}}
"""


# ---------------------------------------------------------------------------
# Two-pass execution
# ---------------------------------------------------------------------------

def _run_pass_a(
    client: Any,
    config: Dict[str, Any],
    enabled_specs: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str, List[Dict[str, Any]]]:
    """Run Pass A. Returns (sources, canonical_pack, source_text, long_content)."""

    model = _pick_model_pass_a(config)
    prompt = _build_pass_a_prompt(config, enabled_specs)

    # Output budget: let the caller request large outputs, but clamp to model.
    requested_out = _safe_int(config.get("pass_a_max_output_tokens"), default_max_output_tokens(model))
    max_out = clamp_output_tokens(model, requested_out)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search"}],
        json_mode=False,  # web_search + strict JSON mode can be incompatible in some SDKs
        max_completion_tokens=max_out,
        reasoning=_pass_a_reasoning(config, model),
    )

    txt = extract_completion_text(resp, model)
    data = _extract_first_json_object(txt)

    sources = data.get("sources") or []
    canonical_pack = data.get("canonical_pack") or {}
    source_text = str(data.get("source_text") or "").strip()
    long_content = data.get("long_content") or []

    if not isinstance(sources, list):
        sources = []
    if not isinstance(canonical_pack, dict):
        canonical_pack = {}
    if not isinstance(long_content, list):
        long_content = []

    return sources, canonical_pack, source_text, long_content


def _run_pass_b(
    client: Any,
    config: Dict[str, Any],
    enabled_specs: List[Dict[str, Any]],
    canonical_pack: Dict[str, Any],
    source_text: str,
) -> Dict[str, Any]:
    model = _pick_model_pass_b(config)
    prompt = _build_pass_b_prompt(config, enabled_specs, canonical_pack, source_text)

    requested_out = _safe_int(config.get("pass_b_max_output_tokens"), default_max_output_tokens(model))
    max_out = clamp_output_tokens(model, requested_out)

    resp = create_openai_completion(
        client=client,
        model=model,
        messages=[{"role": "user", "content": prompt}],
        tools=None,
        json_mode=True,
        max_completion_tokens=max_out,
        reasoning=_pass_b_reasoning(config, model),
    )

    txt = extract_completion_text(resp, model)
    # With json_mode=True, this should be strict JSON.
    data = json.loads(txt) if isinstance(txt, str) else {}
    if not isinstance(data, dict):
        raise ValueError("Pass B output is not a JSON object")
    if "content" not in data or not isinstance(data.get("content"), list):
        raise ValueError("Pass B output JSON missing 'content' list")
    return data


def _pass_b_only(
    client: Any,
    config: Dict[str, Any],
    pass_a_long_script: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Legacy: generate M/S/R from an existing pass_a_long_script + sources."""
    # Minimal canonical pack: just wrap the long script in SOURCE_TEXT.
    canonical_pack = {
        "timeline": "",
        "key_facts": "",
        "key_players": "",
        "claims_evidence": "",
        "beats_outline": "",
        "punchlines": "",
        "historical_context": "",
    }

    enabled_specs = _enabled_specs_from_config(config)
    source_text = _build_source_text(pass_a_long_script, sources)
    return _run_pass_b(client, config, enabled_specs, canonical_pack, source_text)


def _build_source_text(pass_a_long_script: str, sources: List[Dict[str, Any]]) -> str:
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
        "=== SOURCES ===\n"
        f"{src_block}\n"
    )


def _enabled_specs_from_config(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert topic config 'content_types' into a flat list of script specs.

    Expected config shape (current repo):
      content_types: {
        "short": {"enabled": true, "items": 4, "max_words": 350},
        ...
      }
    """
    out: List[Dict[str, Any]] = []
    ct_cfg = config.get("content_types") or {}
    if not isinstance(ct_cfg, dict):
        return out

    for ct_name, spec in ct_cfg.items():
        if not isinstance(spec, dict):
            continue
        if not spec.get("enabled", False):
            continue
        items = _safe_int(spec.get("items"), 1)
        max_words = _safe_int(spec.get("max_words"), 400)
        prefix = _CODE_PREFIX.get(str(ct_name).strip().lower())
        if not prefix:
            continue
        for i in range(items):
            out.append({
                "type": ct_name,
                "code": f"{prefix}{i + 1}",
                "max_words": max_words,
            })
    return out


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def generate_all_content_two_pass(*args, **kwargs) -> Dict[str, Any]:
    """Generate multi-format scripts with a two-pass architecture.

    Supported calls:
      - generate_all_content_two_pass(config, sources=None, client=None)
      - generate_all_content_two_pass(client, config, pass_a_long_script, sources)
    """

    # Legacy style: (client, config, pass_a_long_script, sources)
    if len(args) >= 4 and not isinstance(args[0], dict):
        client, config, pass_a_long_script, sources = args[0], args[1], args[2], args[3]
        return _pass_b_only(client, config, pass_a_long_script, sources)

    # New style: (config, ...)
    if not args or not isinstance(args[0], dict):
        raise TypeError("generate_all_content_two_pass expected config dict or legacy (client, config, pass_a_long_script, sources)")

    config: Dict[str, Any] = args[0]
    sources: List[Dict[str, Any]] = kwargs.get("sources") or (args[1] if len(args) > 1 else [])
    client = _get_openai_client(kwargs.get("client"))

    enabled_specs = _enabled_specs_from_config(config)
    if not enabled_specs:
        return {"content": [], "sources": [], "canonical_pack": {}}

    sources_out, canonical_pack, source_text, long_content = _run_pass_a(client, config, enabled_specs)

    # If Pass A didn't return a usable SOURCE_TEXT, fall back to concatenating long content.
    if not source_text.strip() and long_content:
        source_text = "\n\n".join([str(x.get("script") or "") for x in long_content if isinstance(x, dict)])

    pass_b_data = _run_pass_b(client, config, enabled_specs, canonical_pack, source_text)
    content = pass_b_data.get("content", [])

    # Merge long content (if any) into final content list.
    if isinstance(long_content, list) and long_content:
        # Ensure required keys exist
        for item in long_content:
            if isinstance(item, dict) and "code" in item and "script" in item:
                item.setdefault("type", "long")
        content = long_content + content

    return {
        "content": content,
        "sources": sources_out,
        "canonical_pack": canonical_pack,
    }


def generate_all_content_with_responses_api(*args, **kwargs) -> Dict[str, Any]:
    """Backward compatible alias."""
    return generate_all_content_two_pass(*args, **kwargs)
