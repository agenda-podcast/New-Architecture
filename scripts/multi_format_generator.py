#!/usr/bin/env python3
"""
Multi-format content generation for podcast topics.

Current architecture:
- Pass A (optional): ONLY when long content is enabled AND not in testing/gesting mode AND no test data source file.
  Pass A produces a long script using web_search and returns plain text (SOURCES + SCRIPT).

- Pass B (always): Produces all non-long formats (medium/short/reels) in ONE JSON response.
  - If Pass A ran: Pass B derives summaries from the long script (no new facts, no web_search).
  - If Pass A is skipped: Pass B generates the requested items directly (may use web_search unless sources are supplied).

IMPORTANT:
- This function must be called ONCE per topic.
- It generates ALL enabled items (e.g., M1..Mn, S1..Sn, R1..Rn) in a single run.
"""

from __future__ import annotations

import logging
import traceback
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from global_config import CONTENT_TYPES

# Try to import generator
try:
    from responses_api_generator import generate_all_content_two_pass
    TWO_PASS_AVAILABLE = True
except Exception as e:
    _two_pass_import_error = str(e)
    _two_pass_import_tb = traceback.format_exc()
    logger.warning(f"Two-pass generator not available: {e}")
    logger.warning(_two_pass_import_tb)
    TWO_PASS_AVAILABLE = False
    generate_all_content_two_pass = None  # type: ignore


_generation_in_progress = False


def get_enabled_content_types(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Determine which content items are requested by topic config.

    Supports both shapes:
      - {"content_types": {"long": true, "short": true, ...}}  (boolean)
      - {"content_types": {"short": {"enabled": true, "items": 4, "max_words": 350}, ...}}  (dict)
    """
    enabled: List[Dict[str, Any]] = []
    content_types_config = config.get("content_types", {}) or {}

    for type_name, type_spec in CONTENT_TYPES.items():
        raw = content_types_config.get(type_name, False)

        if isinstance(raw, bool):
            is_enabled = raw
            items = int(type_spec.get("count", 0))
            max_words = int(type_spec.get("target_words", 500))
        elif isinstance(raw, dict):
            is_enabled = bool(raw.get("enabled", False))
            items = int(raw.get("items", type_spec.get("count", 0)))
            max_words = int(raw.get("max_words", type_spec.get("target_words", 500)))
        else:
            is_enabled = False
            items = 0
            max_words = int(type_spec.get("target_words", 500))

        if not is_enabled:
            continue

        for i in range(items):
            enabled.append(
                {
                    "type": type_name,
                    "index": i + 1,
                    "code": f"{type_spec['code_prefix']}{i + 1}",
                    # keep key name consistent across modules
                    "target_words": max_words,
                }
            )

    return enabled


def generate_multi_format_scripts(config: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate all requested scripts for a topic.

    Returns a dict:
      {
        "content": [ {code,type,script,max_words,...}, ... ],
        "sources": [...],
        "pass_a_raw_text": "..."   # present when Pass A ran
      }
    """
    global _generation_in_progress

    if _generation_in_progress:
        raise RuntimeError(
            "Duplicate call detected: generate_multi_format_scripts is already in progress. "
            "This function should only be called once per topic."
        )

    try:
        _generation_in_progress = True

        if not TWO_PASS_AVAILABLE or generate_all_content_two_pass is None:
            raise ImportError(
                f"responses_api_generator.py is not available. Import error: {globals().get('_two_pass_import_error', 'unknown')}"
            )

        content_specs = get_enabled_content_types(config)
        if not content_specs:
            raise ValueError("No content types enabled in topic configuration.")

        logger.info("=" * 80)
        logger.info("MULTI-FORMAT GENERATION")
        logger.info("=" * 80)
        logger.info(f"Topic: {config.get('title', 'Unknown')}")
        logger.info(f"Requested content items: {[s['code'] for s in content_specs]}")
        logger.info("=" * 80)

        # Delegate execution to responses_api_generator (handles pass selection internally)
        out = generate_all_content_two_pass(
            config,
            sources=sources or [],
            enabled_specs=content_specs,
            client=None,
        )

        # Normalize output shape
        content_list = out.get("content", []) or []
        sources_out = out.get("sources", []) or []
        pass_a_raw = out.get("pass_a_raw_text", "") or ""
        search_queries = out.get("search_queries") or []

        return {
            "content": content_list,
            "sources": sources_out,
            "pass_a_raw_text": pass_a_raw,
            "search_queries": search_queries,
        }

    finally:
        _generation_in_progress = False
