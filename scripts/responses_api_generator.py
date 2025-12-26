#!/usr/bin/env python3
"""OpenAI Responses API generator (two-pass).

Pass A (gpt-5.2-pro + web_search)
- Generates long-form scripts (L1..Ln) only.
- Output is stored as raw text (not JSON) to preserve everything returned.

Pass B (gpt-4.1-nano, no web_search)
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
    GPT_MODEL,
    MOCK_RESPONSES_DIR,
    MOCK_SOURCE_TEXT_DIR,
    TESTING_MODE,
    get_content_code,
)

from openai_utils import (
    create_openai_completion,
    create_openai_streaming_completion,
    extract_completion_text,
)

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ============================================================================
# Helpers
# ============================================================================

def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


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


def stringify_for_prompt(text: str) -> str:
    """Make SOURCE_TEXT safe to embed in JSON-ish prompts.

    - Normalizes newlines
    - Removes NUL and other control chars
    - Leaves normal punctuation intact
    """
    if text is None:
        return ""

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Drop problematic control characters (keep \n and \t)
    cleaned = []
    for ch in text:
        o = ord(ch)
        if ch in ("\n", "\t"):
            cleaned.append(ch)
        elif o < 32:
            continue
        else:
            cleaned.append(ch)

    return "".join(cleaned)


def _extract_urls(text: str) -> List[str]:
    if not text:
        return []
    # basic URL extractor
    urls = re.findall(r"https?://[^\s\]\)\>\"']+", text)
    # strip trailing punctuation
    cleaned: List[str] = []
    for u in urls:
        u2 = u.rstrip(".,;:!?")
        if u2 not in cleaned:
            cleaned.append(u2)
    return cleaned


def _urls_to_source_dicts(urls: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in urls:
        try:
            host = urlparse(u).netloc
        except Exception:
            host = ""
        out.append({"url": u, "host": host})
    return out


def _split_pass_a_sections(raw_text: str) -> Tuple[str, List[str]]:
    """Try to split Pass A output into (script_text, urls).

    Conventions supported:
    - Optional "SOURCES:" section
    - Optional "SCRIPT:" marker

    If markers are absent, returns full text as script_text.
    """
    if not raw_text:
        return "", []

    urls = _extract_urls(raw_text)

    m_script = re.search(r"\n\s*SCRIPT\s*:\s*\n", raw_text, flags=re.IGNORECASE)
    if m_script:
        script_text = raw_text[m_script.end():].strip()
        return script_text, urls

    # If no SCRIPT marker, but SOURCES exists, cut it off.
    m_sources = re.search(r"^\s*SOURCES\s*:\s*$", raw_text, flags=re.IGNORECASE | re.MULTILINE)
    if m_sources:
        # script is everything after sources block if there's another marker, else full text
        # Find end of sources block: next blank line after sources header.
        after = raw_text[m_sources.end():]
        m_blank = re.search(r"\n\s*\n", after)
        if m_blank:
            possible_script = after[m_blank.end():].strip()
            if possible_script:
                return possible_script, urls

    return raw_text.strip(), urls


# ============================================================================
# Mock persistence
# ============================================================================


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _repo_root() -> Path:
    """Return repository root directory (parent of the scripts/ folder)."""
    return Path(__file__).resolve().parents[1]


def _resolve_repo_path(path_str: str) -> Path:
    """Resolve a path that may be repo-relative (preferred) or absolute."""
    p = Path(path_str)
    return p if p.is_absolute() else (_repo_root() / p)



def get_mock_response_path(name: str) -> Path:
    base = _resolve_repo_path(MOCK_RESPONSES_DIR)
    _ensure_dir(base)
    return base / f"{name}.json"


def save_mock_response(name: str, payload: Dict[str, Any]) -> None:
    path = get_mock_response_path(name)
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved mock response: {path}")


def load_mock_response(name: str) -> Dict[str, Any]:
    path = get_mock_response_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Mock response not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_mock_source_text_path(topic_id: str) -> Path:
    base = _resolve_repo_path(MOCK_SOURCE_TEXT_DIR)
    _ensure_dir(base)
    return base / f"{topic_id}.txt"


def load_mock_source_text(topic_id: str) -> str:
    path = get_mock_source_text_path(topic_id)
    if not path.exists():
        raise FileNotFoundError(
            f"Pass B needs source text but no L* was generated and fallback file is missing: {path}"
        )
    return path.read_text(encoding="utf-8")


# ============================================================================
# Topic config normalization
# ============================================================================

@dataclass(frozen=True)
class ContentTypePlan:
    enabled: bool
    items: int
    max_words: int


def normalize_content_types(config: Dict[str, Any]) -> Dict[str, ContentTypePlan]:
    """Normalize topic content_types to v2 plan objects.

    Supports:
    - V1: {"long": true, "medium": false, ...}
    - V2: {"long": {"enabled": true, "items": 1, "max_words": 20000}, ...}

    Defaults (if absent): disabled for all types.
    """
    raw = config.get("content_types", {})
    out: Dict[str, ContentTypePlan] = {}

    for type_name, spec in CONTENT_TYPES.items():
        default_items = int(spec.get("count", 0))
        default_max_words = int(spec.get("target_words", 0))

        v = raw.get(type_name, False)
        if isinstance(v, bool):
            out[type_name] = ContentTypePlan(enabled=v, items=(default_items if v else 0), max_words=default_max_words)
        elif isinstance(v, dict):
            enabled = bool(v.get("enabled", False))
            items = int(v.get("items", default_items))
            max_words = int(v.get("max_words", default_max_words))
            if not enabled:
                items = 0
            out[type_name] = ContentTypePlan(enabled=enabled, items=max(0, items), max_words=max_words)
        else:
            out[type_name] = ContentTypePlan(enabled=False, items=0, max_words=default_max_words)

    return out


def normalize_roles(config: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]]]:
    """Return (use_roles, roles[]) in a consistent shape.

    Behavior:
    - If config.use_roles is explicitly set, respect it.
    - Else (legacy): treat voice_a/voice_b as two roles.
    """
    use_roles = config.get("use_roles", None)
    roles = config.get("roles", None)

    if use_roles is False:
        return False, []

    if use_roles is True and isinstance(roles, list) and roles:
        normalized: List[Dict[str, str]] = []
        for r in roles:
            if not isinstance(r, dict):
                continue
            name = str(r.get("name", "")).strip() or "Host"
            bio = str(r.get("bio", "")).strip()
            normalized.append({"name": name, "bio": bio})
        return True, normalized

    # Legacy fallback
    legacy_roles: List[Dict[str, str]] = []
    a_name = str(config.get("voice_a_name", "Host A")).strip() or "Host A"
    a_bio = str(config.get("voice_a_bio", "")).strip()
    b_name = str(config.get("voice_b_name", "Host B")).strip() or "Host B"
    b_bio = str(config.get("voice_b_bio", "")).strip()

    legacy_roles.append({"name": a_name, "bio": a_bio})
    if b_name or b_bio:
        legacy_roles.append({"name": b_name, "bio": b_bio})

    return True, legacy_roles


# ============================================================================
# Prompt building
# ============================================================================


def build_pass_a_prompt(
    *,
    topic_title: str,
    topic_description: str,
    max_words: int,
    language: str,
    freshness_hours: int,
    min_sources: int,
    queries: List[str],
    use_roles: bool,
    roles: List[Dict[str, str]],
) -> str:
    """Build Pass A prompt for one long script."""

    role_block = ""
    output_style = ""

    if not use_roles:
        output_style = (
            "Write as a neutral, professional narrator. Do NOT use HOST_* labels or personas. "
            "Write in a clear broadcast style."
        )
    else:
        if len(roles) <= 1:
            r = roles[0] if roles else {"name": "Host", "bio": ""}
            role_block = f"Persona (single host):\n- Name: {r['name']}\n- Bio: {r.get('bio','')}\n"
            output_style = (
                "Write in first-person (I/me/my) as this persona. Do NOT use HOST_* labels."
            )
        else:
            lines = []
            for idx, r in enumerate(roles, start=1):
                host_code = chr(ord('A') + (idx - 1))
                lines.append(
                    f"- HOST_{host_code}: {r['name']} ({r.get('bio','')})"
                )
            role_block = "Personas:\n" + "\n".join(lines) + "\n"
            output_style = (
                "Write as a conversation with short back-and-forth turns. "
                "Prefix each line with the correct HOST_X label (HOST_A:, HOST_B:, HOST_C:, ...)."
            )

    queries_block = "\n".join([f"- {q}" for q in (queries or [])])

    return (
        "You are producing a news-style spoken script in the requested language.\n\n"
        f"Topic: {topic_title}\n"
        f"Topic description: {topic_description}\n"
        f"Language: {language}\n"
        f"Freshness window: last {freshness_hours} hours (prefer the newest credible sources).\n"
        f"Minimum sources to consult: {min_sources}.\n\n"
        "Search queries to guide discovery:\n"
        f"{queries_block}\n\n"
        f"{role_block}\n"
        "Hard constraints:\n"
        f"- Max words: {max_words} (do not exceed).\n"
        "- Use the web_search tool to verify claims and prioritize recency.\n"
        "- Prefer primary/credible outlets and official sources when available.\n"
        "- Do not fabricate sources or quotes.\n\n"
        "Output format:\n"
        "1) Start with a section exactly labeled 'SOURCES:' containing a bullet list of URLs used (one per line).\n"
        "2) Then a section exactly labeled 'SCRIPT:' followed by the full script.\n\n"
        f"Style requirements:\n{output_style}\n"
    )


def build_pass_b_prompt(
    *,
    source_text: str,
    topic_title: str,
    language: str,
    use_roles: bool,
    roles: List[Dict[str, str]],
    medium_items: int,
    medium_max_words: int,
    short_items: int,
    short_max_words: int,
    reels_items: int,
    reels_max_words: int,
) -> str:
    """Build Pass B prompt: JSON output only."""

    # Role instructions mirrored from Pass A, but the constraint is: "no new facts".
    role_block = ""
    output_style = ""

    if not use_roles:
        output_style = "Neutral narrator voice; do NOT use HOST_* labels or personas."
    else:
        if len(roles) <= 1:
            r = roles[0] if roles else {"name": "Host", "bio": ""}
            role_block = f"Persona (single host):\n- Name: {r['name']}\n- Bio: {r.get('bio','')}\n"
            output_style = "Write in first-person (I/me/my) as this persona; no HOST_* labels."
        else:
            lines = []
            for idx, r in enumerate(roles, start=1):
                host_code = chr(ord('A') + (idx - 1))
                lines.append(f"- HOST_{host_code}: {r['name']} ({r.get('bio','')})")
            role_block = "Personas:\n" + "\n".join(lines) + "\n"
            output_style = "Conversational style; prefix each line with HOST_X labels."

    plan_lines = []
    if medium_items > 0:
        plan_lines.append(f"- medium: {medium_items} items, each <= {medium_max_words} words")
    if short_items > 0:
        plan_lines.append(f"- short: {short_items} items, each <= {short_max_words} words")
    if reels_items > 0:
        plan_lines.append(f"- reels: {reels_items} items, each <= {reels_max_words} words")

    plan_block = "\n".join(plan_lines) if plan_lines else "(none)"

    # IMPORTANT: SOURCE_TEXT is provided as an escaped block and must be treated as the only source of truth.
    safe_text = stringify_for_prompt(source_text)

    return (
        "You are summarizing an existing SOURCE_TEXT into shorter scripts.\n"
        "You MUST NOT introduce any new facts, new sources, or additional context beyond SOURCE_TEXT.\n"
        "If a detail is missing/unclear in SOURCE_TEXT, omit it.\n\n"
        f"Topic: {topic_title}\n"
        f"Language: {language}\n\n"
        f"{role_block}\n"
        "Targets to generate:\n"
        f"{plan_block}\n\n"
        "Output requirements (JSON only):\n"
        "Return an object with key 'content' as an array. Each array element must contain:\n"
        "- code: string like M1, M2, S1.., R1.. (sequential per type)\n"
        "- type: one of 'medium'|'short'|'reels'\n"
        "- script: the script text in the required style\n"
        "- actual_words: integer word count of script\n"
        "Rules:\n"
        "- Enforce the per-item max words strictly.\n"
        "- Keep dialogue/persona style consistent with SOURCE_TEXT (role instructions below).\n"
        "- Do not include URLs.\n"
        "- Do not include additional keys.\n\n"
        f"Style requirements: {output_style}\n\n"
        "SOURCE_TEXT (verbatim):\n"
        "-----BEGIN SOURCE_TEXT-----\n"
        f"{safe_text}\n"
        "-----END SOURCE_TEXT-----\n"
    )


# ============================================================================
# Pass A
# ============================================================================


def generate_pass_a_content(
    *,
    config: Dict[str, Any],
    client: 'OpenAI',
    plan: Dict[str, ContentTypePlan],
    use_roles: bool,
    roles: List[Dict[str, str]],
    output_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """Generate L* scripts.

    Returns (sources, l_contents, raw_text_combined)
    - sources: list of dicts {url, host}
    - l_contents: list of content items for L*
    - raw_text_combined: concatenated raw text outputs
    """

    long_plan = plan.get("long", ContentTypePlan(False, 0, 0))
    if not long_plan.enabled or long_plan.items <= 0:
        return [], [], ""

    topic_id = str(config.get("id", "topic"))
    topic_title = str(config.get("title", ""))
    topic_desc = str(config.get("description", ""))
    language = str(config.get("language", "en"))
    freshness_hours = int(config.get("freshness_hours", 24))
    min_sources = int(config.get("min_fresh_sources", 5))
    queries = list(config.get("queries", []) or [])

    model = str(config.get("gpt_model_pass_a", GPT_MODEL))

    tools = [{"type": "web_search"}]

    sources_all: List[str] = []
    l_contents: List[Dict[str, Any]] = []
    raw_texts: List[str] = []

    # Output directory for raw Pass A text (authoritative, not JSON)
    if output_dir is None:
        output_dir = Path("outputs") / topic_id / "raw"
    _ensure_dir(output_dir)

    logger.info("=" * 80)
    logger.info("PASS A: Generating long-form content")
    logger.info(f"Model: {model}")
    logger.info(f"Long items: {long_plan.items}, max_words per item: {long_plan.max_words}")
    logger.info("=" * 80)

    for i in range(long_plan.items):
        code = get_content_code("long", i + 1)
        prompt = build_pass_a_prompt(
            topic_title=topic_title,
            topic_description=topic_desc,
            max_words=long_plan.max_words,
            language=language,
            freshness_hours=freshness_hours,
            min_sources=min_sources,
            queries=queries,
            use_roles=use_roles,
            roles=roles,
        )

        # Pass A: high cap + continuation logic.
        # Use a hard cap of 125k output tokens (overrideable by env but never above 125k).
        max_tokens = min(int(os.getenv("PASS_A_MAX_OUTPUT_TOKENS", "125000")), 125000)

        # Streaming to avoid disconnects on large outputs.
        # Always persist raw output to per-part files AND a combined {code}_raw.txt.
        raw_txt_path = output_dir / f"{code}_raw.txt"  # combined
        try:
            raw_txt_path.write_text("", encoding="utf-8")
        except Exception:
            _ensure_dir(raw_txt_path.parent)
            raw_txt_path.write_text("", encoding="utf-8")

        def _continue_prompt(last_tail: str) -> str:
            tail = (last_tail or "").strip()
            return (
                "Continue the SAME script from exactly where it stopped. "
                "Do NOT repeat anything already written. "
                "Maintain the same structure, style, roles/personas, and language. "
                "Do not add a new intro. Do not add a new SOURCES block. "
                "Start with the next sentence/paragraph after the last visible text.\n\n"
                f"Last tail (for continuity, do not repeat):\n```\n{tail}\n```"
            )

        start = time.time()
        logger.info(f"Pass A request for {code}: max_output_tokens={max_tokens}")

        raw_text_parts: List[str] = []
        max_parts = int(os.getenv("PASS_A_MAX_PARTS", "6"))

        if TESTING_MODE:
            mock = load_mock_response("pass_a")
            if "raw_text" in mock and mock.get("raw_text"):
                raw_text = str(mock.get("raw_text", ""))
            elif "raw_text_file" in mock and mock.get("raw_text_file"):
                raw_text = Path(str(mock.get("raw_text_file"))).read_text(encoding="utf-8")
            else:
                raw_text = ""
            raw_txt_path.write_text(raw_text or "", encoding="utf-8")
        else:
            last_tail = ""
            part_files: List[Path] = []
            for part in range(1, max_parts + 1):
                part_path = output_dir / f"{code}_raw.part{part:02d}.txt"
                part_files.append(part_path)

                # Web search only on the first part to avoid repeated tool calls.
                part_tools = tools if part == 1 else None

                user_content = prompt if part == 1 else _continue_prompt(last_tail)

                part_text, part_resp = create_openai_streaming_completion(
                    client=client,
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a careful producer. Use web search for verification only when available."},
                        {"role": "user", "content": user_content},
                    ],
                    tools=part_tools,
                    max_completion_tokens=max_tokens,
                    output_path=str(part_path),
                    flush_threshold=20000,
                    json_mode=False,
                    return_meta=True,
                )

                # Ensure part file exists and is non-empty before proceeding.
                if not part_path.exists() or part_path.stat().st_size == 0:
                    part_path.write_text(part_text or "", encoding="utf-8")
                if part_path.stat().st_size == 0:
                    raise RuntimeError(f"Pass A part file is empty after write: {part_path}")

                raw_text_parts.append(part_text or "")
                # Append to combined file immediately
                with open(raw_txt_path, "a", encoding="utf-8") as f:
                    f.write(part_text or "")

                # Prepare tail for the next continuation call
                last_tail = (part_text or "")[-2000:]

                # Continuation condition: Responses API status=incomplete AND reason=max_output_tokens
                reason = None
                try:
                    if part_resp is not None and hasattr(part_resp, "model_dump"):
                        d = part_resp.model_dump()
                        if isinstance(d, dict) and d.get("status") == "incomplete":
                            inc = d.get("incomplete_details") or {}
                            if isinstance(inc, dict):
                                reason = inc.get("reason")
                except Exception:
                    reason = None

                if reason == "max_output_tokens":
                    logger.warning(f"Pass A {code} hit max_output_tokens on part {part}; continuing...")
                    continue

                # Otherwise, we assume completion.
                break
            else:
                logger.warning(f"Pass A {code} reached max_parts={max_parts} without a complete finish.")

            # Write a combined response pointer JSON so you can inspect which part responses exist.
            try:
                combined_resp = {
                    "topic_id": topic_id,
                    "code": code,
                    "model": model,
                    "parts": [
                        {
                            "part": idx + 1,
                            "text_file": str(p).replace("\\", "/"),
                            "response_json_file": (str(p) + ".response.json").replace("\\", "/"),
                        }
                        for idx, p in enumerate(part_files)
                        if p.exists()
                    ],
                }
                (Path(str(raw_txt_path) + ".response.json")).write_text(
                    json.dumps(combined_resp, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.warning(f"Failed to write combined Pass A response pointer JSON: {e}")

            raw_text = raw_txt_path.read_text(encoding="utf-8")

        # Ensure combined raw output is persisted before downstream steps.
        try:
            if not raw_txt_path.exists() or raw_txt_path.stat().st_size == 0:
                raw_txt_path.write_text(raw_text or "", encoding="utf-8")
            if raw_txt_path.stat().st_size == 0:
                raise RuntimeError("Raw L output file is empty after write")
        except Exception as e:
            raise RuntimeError(f"Failed to persist raw Pass A output to {raw_txt_path}: {e}")

        elapsed = time.time() - start
        logger.info(f"Pass A {code} completed in {elapsed:.1f}s; chars={len(raw_text)}")

        script_text, urls = _split_pass_a_sections(raw_text)
        for u in urls:
            if u not in sources_all:
                sources_all.append(u)

        l_contents.append(
            {
                "code": code,
                "type": "long",
                "script": script_text,
                "actual_words": count_words(script_text),
                "target_words": long_plan.max_words,
                "api_provider": "openai_responses_api_two_pass",
                "web_search_enabled": True,
            }
        )

        raw_texts.append(raw_text)

        # Write a small meta JSON next to the raw text file
        try:
            sha = hashlib.sha256((raw_text or "").encode("utf-8", errors="ignore")).hexdigest()
            meta = {
                "topic_id": topic_id,
                "code": code,
                "model": model,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "max_words": long_plan.max_words,
                "max_output_tokens": max_tokens,
                "web_search_enabled": True,
                "raw_text_file": str(raw_txt_path).replace("\\", "/"),
                "response_json_file": (str(raw_txt_path) + ".response.json").replace("\\", "/"),
                "sources": _urls_to_source_dicts(urls),
                "sha256": sha,
                "chars": len(raw_text or ""),
                "script_words": count_words(script_text),
            }
            (output_dir / f"{code}_meta.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to write Pass A meta for {code}: {e}")

    sources = _urls_to_source_dicts(sources_all)
    raw_combined = "\n\n".join(raw_texts)

    # Also persist a combined raw file (useful as SOURCE_TEXT for Pass B)
    if output_dir is not None:
        try:
            combined_path = output_dir / "L_raw_combined.txt"
            combined_path.write_text(raw_combined, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write combined Pass A raw file: {e}")

    if not TESTING_MODE:
        # Save a lightweight mock payload for debugging (avoid embedding huge raw text in JSON).
        try:
            save_mock_response(
                "pass_a",
                {
                    "raw_text_file": str((output_dir / "L_raw_combined.txt")).replace("\\", "/"),
                    "raw_files": [
                        {"code": c.get("code"), "file": str((output_dir / f"{c.get('code')}_raw.txt")).replace("\\", "/")}
                        for c in l_contents
                    ],
                    "sources": sources,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to save pass_a mock pointer JSON: {e}")

    return sources, l_contents, raw_combined


# ============================================================================
# Pass B
# ============================================================================


def generate_pass_b_content(
    *,
    config: Dict[str, Any],
    client: 'OpenAI',
    plan: Dict[str, ContentTypePlan],
    use_roles: bool,
    roles: List[Dict[str, str]],
    source_text: str,
    output_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Generate M/S/R from a given source_text."""

    medium_plan = plan.get("medium", ContentTypePlan(False, 0, 0))
    short_plan = plan.get("short", ContentTypePlan(False, 0, 0))
    reels_plan = plan.get("reels", ContentTypePlan(False, 0, 0))

    if (medium_plan.items + short_plan.items + reels_plan.items) <= 0:
        return []

    topic_id = str(config.get("id", "topic"))
    if output_dir is None:
        output_dir = Path("outputs") / topic_id / "raw"
    _ensure_dir(output_dir)

    topic_title = str(config.get("title", ""))
    language = str(config.get("language", "en"))

    prompt = build_pass_b_prompt(
        source_text=source_text,
        topic_title=topic_title,
        language=language,
        use_roles=use_roles,
        roles=roles,
        medium_items=medium_plan.items,
        medium_max_words=medium_plan.max_words,
        short_items=short_plan.items,
        short_max_words=short_plan.max_words,
        reels_items=reels_plan.items,
        reels_max_words=reels_plan.max_words,
    )

    # Token budget: approximate by total words expected.
    # Pass B must be cost-controlled; cap hard at 60k tokens (override via PASS_B_MAX_OUTPUT_TOKENS).
    total_target_words = (
        medium_plan.items * medium_plan.max_words
        + short_plan.items * short_plan.max_words
        + reels_plan.items * reels_plan.max_words
    )

    max_tokens = calculate_max_output_tokens(
        total_target_words,
        buffer_ratio=1.30,
        cap_tokens=min(int(os.getenv("PASS_B_MAX_OUTPUT_TOKENS", "60000")), 60000),
    )

    # Pass B is intended to be a low-cost summarization step. Default to gpt-5-nano.
    # (Can be overridden per-topic via "gpt_model_pass_b".)
    model = str(config.get("gpt_model_pass_b", "gpt-5-nano"))

    logger.info("=" * 80)
    logger.info("PASS B: Summarization")
    logger.info(f"Model: {model}")
    logger.info(
        f"Targets: medium={medium_plan.items}x{medium_plan.max_words}, short={short_plan.items}x{short_plan.max_words}, reels={reels_plan.items}x{reels_plan.max_words}"
    )
    logger.info(f"Max output tokens: {max_tokens}")
    logger.info("=" * 80)

    if TESTING_MODE:
        mock = load_mock_response("pass_b")
        content_list = list(mock.get("content", []) or [])
        return content_list

    def _persist_pass_b_raw(attempt: int, resp_obj: Any, resp_text: Optional[str]) -> None:
        """Persist raw Pass B artifacts immediately (before any parsing/validation)."""
        suffix = "" if attempt == 1 else f".{attempt}"

        # Save full response JSON
        try:
            resp_json_path = output_dir / f"pass_b.response{suffix}.json"
            if hasattr(resp_obj, "model_dump_json"):
                resp_json_path.write_text(resp_obj.model_dump_json(indent=2), encoding="utf-8")
            elif hasattr(resp_obj, "model_dump"):
                resp_json_path.write_text(json.dumps(resp_obj.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
            else:
                resp_json_path.write_text(json.dumps(str(resp_obj), ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write Pass B raw response JSON (attempt {attempt}): {e}")

        # Save extracted text (if already available)
        if resp_text is not None:
            try:
                (output_dir / f"pass_b_raw{suffix}.txt").write_text(resp_text or "", encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to write Pass B extracted text (attempt {attempt}): {e}")

    def _response_incomplete_reason(resp_obj: Any) -> Optional[str]:
        try:
            if hasattr(resp_obj, "model_dump"):
                d = resp_obj.model_dump()
                if isinstance(d, dict) and d.get("status") == "incomplete":
                    inc = d.get("incomplete_details") or {}
                    if isinstance(inc, dict):
                        return inc.get("reason")
        except Exception:
            return None
        return None

    def _parse_pass_b_json(text: str) -> Dict[str, Any]:
        # Strip anything before/after JSON object defensively
        m = re.search(r"\{.*\}", text, re.DOTALL)
        json_text = m.group(0) if m else text
        return json.loads(json_text)

    def _validate_content(out_items: List[Dict[str, Any]]) -> List[str]:
        errs: List[str] = []
        got_m = len([x for x in out_items if x.get("type") == "medium"])
        got_s = len([x for x in out_items if x.get("type") == "short"])
        got_r = len([x for x in out_items if x.get("type") == "reels"])
        if got_m != medium_plan.items:
            errs.append(f"medium items mismatch: expected {medium_plan.items}, got {got_m}")
        if got_s != short_plan.items:
            errs.append(f"short items mismatch: expected {short_plan.items}, got {got_s}")
        if got_r != reels_plan.items:
            errs.append(f"reels items mismatch: expected {reels_plan.items}, got {got_r}")
        # Word-limit validation (hard)
        for it in out_items:
            t = it.get("type")
            aw = int(it.get("actual_words", 0) or 0)
            tw = int(it.get("target_words", 0) or 0)
            if tw > 0 and aw > tw:
                errs.append(f"{it.get('code')} exceeds max_words: actual {aw} > target {tw}")
        return errs

    # Pass B: single-call generation with validation + optional one retry.
    last_errs: List[str] = []
    for attempt in (1, 2):
        attempt_prompt = prompt
        if attempt == 2:
            # Make the second attempt explicitly more compact to avoid truncation.
            attempt_prompt = (
                prompt
                + "\n\nIMPORTANT RETRY INSTRUCTIONS:\n"
                + "- Your previous response was invalid (missing items / too long / truncated).\n"
                + "- Regenerate STRICTLY within the per-item max_words. Use ~80% of each max_words to ensure it fits under max_output_tokens.\n"
                + "- Return ONLY valid JSON with the required number of items per type."
            )

        response = create_openai_completion(
            client=client,
            model=model,
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": attempt_prompt},
            ],
            tools=None,
            json_mode=True,
            max_completion_tokens=max_tokens,
        )

        # Persist raw response immediately (even if extraction/parsing fails).
        _persist_pass_b_raw(attempt, response, None)

        # If truncated by max_output_tokens, retry once (attempt 2).
        reason = _response_incomplete_reason(response)
        if reason == "max_output_tokens":
            logger.error("Pass B response is incomplete due to max_output_tokens; will retry once with stricter compression.")
            if attempt == 1:
                continue
            raise RuntimeError("Pass B truncated due to max_output_tokens even after retry. Consider lowering max_words per item.")

        # Extract text
        try:
            response_text = extract_completion_text(response, model)
        except Exception as e:
            logger.error(f"Pass B text extraction failed (attempt {attempt}): {e}")
            if attempt == 1:
                continue
            raise

        _persist_pass_b_raw(attempt, response, response_text)

        # Parse JSON
        try:
            data = _parse_pass_b_json(response_text)
        except Exception as e:
            logger.error(f"Pass B JSON parse failed (attempt {attempt}): {e}")
            logger.error(f"Pass B response preview: {response_text[:1200]}...")
            if attempt == 1:
                continue
            raise

        content_list = list(data.get("content", []) or [])

        # Defensive filtering + ensure codes follow expected counts
        out: List[Dict[str, Any]] = []
        m_idx = s_idx = r_idx = 0
        for item in content_list:
            if not isinstance(item, dict):
                continue
            t = item.get("type")
            script = str(item.get("script", ""))
            aw = int(item.get("actual_words", count_words(script)))

            if t == "medium" and m_idx < medium_plan.items:
                m_idx += 1
                code = f"M{m_idx}"
                out.append({"code": code, "type": "medium", "script": script, "actual_words": aw, "target_words": medium_plan.max_words})
            elif t == "short" and s_idx < short_plan.items:
                s_idx += 1
                code = f"S{s_idx}"
                out.append({"code": code, "type": "short", "script": script, "actual_words": aw, "target_words": short_plan.max_words})
            elif t == "reels" and r_idx < reels_plan.items:
                r_idx += 1
                code = f"R{r_idx}"
                out.append({"code": code, "type": "reels", "script": script, "actual_words": aw, "target_words": reels_plan.max_words})

        last_errs = _validate_content(out)
        if last_errs:
            logger.error(f"Pass B validation failed (attempt {attempt}): {last_errs}")
            # Save validation report
            try:
                (output_dir / f"pass_b_validation{'' if attempt==1 else '.'+str(attempt)}.json").write_text(
                    json.dumps({"errors": last_errs}, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass
            if attempt == 1:
                continue
            raise RuntimeError(f"Pass B validation failed after retry: {last_errs}")

        # Save mock data for reuse
        save_mock_response("pass_b", {"content": out})
        return out

    raise RuntimeError(f"Pass B failed after retry. Last errors: {last_errs}")


# ============================================================================
# Orchestrator
# ============================================================================


def generate_all_content_two_pass(
    config: Dict[str, Any],
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate all enabled content pieces using the two-pass approach."""

    if OpenAI is None:
        raise ImportError("openai package is required. Install with: pip install openai")

    plan = normalize_content_types(config)
    use_roles, roles = normalize_roles(config)

    # Decide if we need Pass A and/or Pass B
    need_pass_a = plan.get("long", ContentTypePlan(False, 0, 0)).items > 0
    need_pass_b = (
        plan.get("medium", ContentTypePlan(False, 0, 0)).items
        + plan.get("short", ContentTypePlan(False, 0, 0)).items
        + plan.get("reels", ContentTypePlan(False, 0, 0)).items
    ) > 0

    if not (need_pass_a or need_pass_b):
        raise ValueError("No content types enabled. Configure content_types in the topic JSON.")

    # Initialize client
    if not TESTING_MODE:
        api_key = api_key or os.environ.get("GPT_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("GPT_KEY or OPENAI_API_KEY environment variable is required")
        client = OpenAI(api_key=api_key, timeout=3600.0, max_retries=0)
    else:
        client = OpenAI(api_key="TEST") if OpenAI else None

    topic_id = str(config.get("id", "topic"))
    # Persist raw L* responses under outputs/<topic_id>/raw/ as plain text.
    output_dir = Path("outputs") / topic_id / "raw"
    _ensure_dir(output_dir)

    sources: List[Dict[str, Any]] = []
    content: List[Dict[str, Any]] = []
    raw_l_text = ""

    # Pass A
    if need_pass_a:
        sources, l_content, raw_l_text = generate_pass_a_content(
            config=config,
            client=client,
            plan=plan,
            use_roles=use_roles,
            roles=roles,
            output_dir=output_dir,
        )
        content.extend(l_content)

        # Verify raw L files exist BEFORE moving to Pass B.
        for li in l_content:
            code = li.get("code")
            if not code:
                continue
            p = output_dir / f"{code}_raw.txt"
            if not p.exists() or p.stat().st_size == 0:
                raise RuntimeError(f"Expected raw L output file missing/empty: {p}")

    # Resolve SOURCE_TEXT for Pass B
    if need_pass_b:
        if raw_l_text.strip():
            source_text = raw_l_text
        else:
            # No L output generated: use mock source text file
            source_text = load_mock_source_text(topic_id)

        # Persist the source text used for Pass B (always) so failures are diagnosable.
        try:
            (output_dir / "pass_b_source_text.txt").write_text(source_text or "", encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write Pass B source text: {e}")

        b_content = generate_pass_b_content(
            config=config,
            client=client,
            plan=plan,
            use_roles=use_roles,
            roles=roles,
            source_text=source_text,
            output_dir=output_dir,
        )
        content.extend(b_content)

    # Attach sources metadata to all pieces
    for item in content:
        item["sources"] = sources
        item["api_provider"] = item.get("api_provider", "openai_responses_api_two_pass")

    # Validate expected counts
    expected = 0
    for k, p in plan.items():
        expected += int(p.items)
    if len(content) != expected:
        logger.warning(f"Expected {expected} content items but produced {len(content)}")

    return content


def generate_all_content_with_responses_api(
    config: Dict[str, Any],
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Backward-compatible wrapper used by older pipeline code."""
    return generate_all_content_two_pass(config=config, api_key=api_key)
