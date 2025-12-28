#!/usr/bin/env python3
"""
Generate podcast script(s) for a topic.

This module is called by run_pipeline.py as:
    script_generate.generate_for_topic(topic_id, date_str)

Key additions (Dec 2025):
- If config.testing_mode (or gesting/gisting) is True:
  - Ensure a Source Text file exists (create template if missing).
  - Put its path into config["source_text_file"] so responses_api_generator can produce mock Pass A/B.
- In testing mode, downstream will receive mock scripts with the same shapes and file outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_topic_config, get_data_dir, get_output_dir

try:
    from multi_format_generator import generate_multi_format_scripts
except Exception:
    generate_multi_format_scripts = None  # type: ignore

try:
    from script_parser import convert_content_script_to_segments, validate_segments
except Exception:
    convert_content_script_to_segments = None  # type: ignore
    validate_segments = None  # type: ignore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on", "enabled")


def _is_testing_or_gesting_mode(config: Dict[str, Any]) -> bool:
    if _truthy(config.get("testing_mode")):
        return True
    if _truthy(config.get("gesting_mode")):
        return True
    if _truthy(config.get("gisting_mode")):
        return True
    if _truthy(os.getenv("TESTING_MODE")):
        return True
    if _truthy(os.getenv("GESTING_MODE")):
        return True
    if _truthy(os.getenv("GISTING_MODE")):
        return True
    try:
        import global_config
        if _truthy(getattr(global_config, "TESTING_MODE", False)):
            return True
    except Exception:
        pass
    return False


def _estimate_duration_sec_from_words(words: int, wpm: int = 150) -> int:
    if not words or words <= 0:
        return 0
    minutes = float(words) / float(wpm)
    return int(minutes * 60)


def script_to_text(script: Dict[str, Any], config: Dict[str, Any]) -> str:
    voice_a_name = config.get("voice_a_name", "Host A")
    voice_b_name = config.get("voice_b_name", "Host B")

    lines: List[str] = []
    for segment in script.get("segments", []) or []:
        for dialogue in segment.get("dialogue", []) or []:
            speaker_code = dialogue.get("speaker", "A")
            if speaker_code not in ("A", "B"):
                speaker_code = "A"
            speaker_name = voice_a_name if speaker_code == "A" else voice_b_name
            text = str(dialogue.get("text", "")).strip()
            if text:
                lines.append(f"{speaker_name}: {text}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def generate_chapters(script: Dict[str, Any]) -> List[Dict[str, Any]]:
    chapters: List[Dict[str, Any]] = []
    for seg in script.get("segments", []) or []:
        chapters.append(
            {
                "chapter": seg.get("chapter", 1),
                "title": seg.get("title", "Chapter"),
                "start_time": seg.get("start_time", 0),
                "duration": seg.get("duration", 0),
            }
        )
    return chapters


def chapters_to_ffmeta(chapters: List[Dict[str, Any]]) -> str:
    lines = [";FFMETADATA1"]
    for ch in chapters:
        title = str(ch.get("title", "Chapter"))
        start = int(ch.get("start_time", 0) or 0) * 1000
        dur = int(ch.get("duration", 0) or 0) * 1000
        end = start + dur if dur > 0 else start
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start}",
            f"END={end}",
            f"title={title}",
        ]
    return "\n".join(lines).strip() + "\n"


def _ensure_source_text_file(config: Dict[str, Any], data_dir: Path) -> Path:
    """
    Ensure a Source Text file exists in testing mode.
    If config already points to one, use it. Otherwise create default:
      <data_dir>/source_text.txt

    The template follows the same parsing requirements used later:
      SOURCES:
      FULL_TEXT:
    """
    candidate = (
        config.get("source_text_file")
        or config.get("sources_text_file")
        or config.get("source_text_path")
        or config.get("sources_text_path")
    )

    if candidate:
        p = Path(str(candidate))
        p.parent.mkdir(parents=True, exist_ok=True)
    else:
        p = data_dir / "source_text.txt"

    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        template = (
            "SOURCES:\n"
            "- [1] <Publisher> — <Title> (YYYY-MM-DD). <URL>\n"
            "- [2] <Publisher> — <Title> (YYYY-MM-DD). <URL>\n"
            "\n"
            "FULL_TEXT:\n"
            "Paste the full article text(s) here. You can include multiple articles.\n"
            "The mock generator will convert this into HOST_A/HOST_B dialogue.\n"
            "\n"
        )
        p.write_text(template, encoding="utf-8")

    # Inject canonical key into config so generator can reliably find it
    config["source_text_file"] = str(p)
    return p


# ---------------------------------------------------------------------------
# Public API expected by run_pipeline.py
# ---------------------------------------------------------------------------

def generate_for_topic(topic_id: str, date_str: str | None = None) -> bool:
    try:
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")

        config = load_topic_config(topic_id)
        data_dir = get_data_dir(topic_id)
        output_dir = get_output_dir(topic_id)

        # Ensure Source Text file exists when in Testing/Gesting mode
        if _is_testing_or_gesting_mode(config):
            src_path = _ensure_source_text_file(config, data_dir)
            print(f"[TESTING MODE] Source Text file: {src_path}")

        return generate_multi_format_for_topic(topic_id, date_str, config, data_dir, output_dir)

    except Exception as e:
        print(f"Error generating scripts for {topic_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_multi_format_for_topic(
    topic_id: str,
    date_str: str,
    config: Dict[str, Any],
    data_dir: Path,
    output_dir: Path,
) -> bool:
    try:
        if generate_multi_format_scripts is None:
            print("Error: multi_format_generator not available")
            return False

        print(f"Generating scripts for {topic_id} using multi-format generator...")
        picked_sources: List[Dict[str, Any]] = []  # generator decides whether to web_search

        multi_data = generate_multi_format_scripts(config, picked_sources)

        content_list = (multi_data.get("content") or [])
        if not content_list:
            print("Error: No content generated")
            return False

        # Save sources (REAL sources list if available)
        sources_out = multi_data.get("sources")
        sources_path = output_dir / f"{topic_id}-{date_str}.sources.json"
        if isinstance(sources_out, list):
            with open(sources_path, "w", encoding="utf-8") as f:
                json.dump(sources_out, f, indent=2, ensure_ascii=False)
        else:
            with open(sources_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "note": "No structured sources returned by generator.",
                        "generated_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

        # Save raw Pass A output (if present) — even if incomplete
        pass_a_raw = (multi_data.get("pass_a_raw_text") or "").strip()
        if pass_a_raw:
            pass_a_path = output_dir / f"{topic_id}-{date_str}-PASS_A.txt"
            with open(pass_a_path, "w", encoding="utf-8") as f:
                f.write(pass_a_raw + "\n")

        print(f"Generated {len(content_list)} content pieces")

        # Save each generated script
        for content_item in content_list:
            code = str(content_item.get("code", "UNKNOWN"))
            content_type = str(content_item.get("type", "unknown"))
            # Some upstream generators may return "segments" without "script", or
            # return a non-standard key such as "text". Downstream TTS requires
            # valid segments, so we normalize here to avoid empty outputs.
            script_text_raw = (
                content_item.get("script")
                or content_item.get("text")
                or content_item.get("output_text")
                or ""
            )

            target_duration = int(content_item.get("target_duration", 0) or 0)
            if target_duration <= 0:
                max_words = content_item.get("max_words") or content_item.get("target_words") or 0
                try:
                    target_duration = _estimate_duration_sec_from_words(int(max_words))
                except Exception:
                    target_duration = 0

            # Convert script text to segments (required for TTS)
            if convert_content_script_to_segments is not None:
                content_item = convert_content_script_to_segments(content_item)
            else:
                print(f"ERROR: script_parser not available; cannot build segments for {code}.")
                continue

            segments = content_item.get("segments") or []
            if not segments:
                # Last-resort: create a minimal placeholder script so that downstream
                # steps have a .script.json to work with. This is preferable to a hard
                # failure that blocks the entire pipeline.
                fallback_text = (script_text_raw or "").strip()
                if not fallback_text:
                    fallback_text = f"HOST_A: [EMPTY SCRIPT] Generator produced no script for {code}."
                content_item["script"] = fallback_text
                content_item = convert_content_script_to_segments(content_item)
                segments = content_item.get("segments") or []
                if not segments:
                    segments = [
                        {
                            "chapter": 1,
                            "title": content_type.capitalize(),
                            "start_time": 0,
                            "duration": 0,
                            "dialogue": [{"speaker": "A", "text": fallback_text}],
                        }
                    ]
                print(f"WARN: {code} had no segments; wrote placeholder segments to keep pipeline moving.")

            if validate_segments is not None:
                if not validate_segments(segments, code):
                    print(f"ERROR: {code} has invalid segments; skipping.")
                    continue

            total_dialogue = sum(len(seg.get("dialogue", []) or []) for seg in segments)
            print(f"  {code}: {len(segments)} segment(s), {total_dialogue} dialogue items")

            script_obj: Dict[str, Any] = {
                "title": f"{config.get('title', topic_id)} - {code}",
                "duration_sec": target_duration,
                "segments": segments,
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "num_sources": len(sources_out) if isinstance(sources_out, list) else 0,
                    "content_type": content_type,
                    "content_code": code,
                },
            }

            base_name = f"{topic_id}-{date_str}-{code}"

            script_path = output_dir / f"{base_name}.script.txt"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_to_text(script_obj, config))

            script_json_path = output_dir / f"{base_name}.script.json"
            with open(script_json_path, "w", encoding="utf-8") as f:
                json.dump(script_obj, f, indent=2, ensure_ascii=False)

            chapters = generate_chapters(script_obj)
            chapters_path = output_dir / f"{base_name}.chapters.json"
            with open(chapters_path, "w", encoding="utf-8") as f:
                json.dump(chapters, f, indent=2, ensure_ascii=False)

            ffmeta_path = output_dir / f"{base_name}.ffmeta"
            with open(ffmeta_path, "w", encoding="utf-8") as f:
                f.write(chapters_to_ffmeta(chapters))

            print(f"  - Saved {code}: ~{target_duration}s")

        print(f"Multi-format scripts generated for {topic_id}: {len(content_list)} pieces")
        return True

    except Exception as e:
        print(f"Error generating multi-format scripts for {topic_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate scripts (multi-format)")
    parser.add_argument("--topic", required=True, help="Topic ID (e.g., topic-01)")
    parser.add_argument("--date", default=None, help="Date string YYYYMMDD (optional)")
    args = parser.parse_args()

    ok = generate_for_topic(args.topic, args.date)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())