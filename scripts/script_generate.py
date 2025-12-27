#!/usr/bin/env python3
"""
Generate podcast script(s) for a topic.

This module is called by run_pipeline.py as:
    script_generate.generate_for_topic(topic_id, date_str)

Architecture:
- Delegates multi-format generation to multi_format_generator.generate_multi_format_scripts()
- Expects output:
    {
      "content": [ { "code": "...", "type": "...", "script": "...", ... }, ... ],
      "sources": [ ... ],              # structured sources if available
      "pass_a_raw_text": "..."         # optional raw Pass-A output if Pass A ran
    }

Outputs written to config.get_output_dir(topic_id):
- <topic>-<date>-<CODE>.script.txt
- <topic>-<date>-<CODE>.script.json
- <topic>-<date>-<CODE>.chapters.json
- <topic>-<date>-<CODE>.ffmeta
- <topic>-<date>.sources.json         (REAL sources list, if provided)
- <topic>-<date>-PASS_A.txt           (raw Pass A text, if provided)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_topic_config, get_data_dir, get_output_dir

# Multi-format generator (required for new architecture)
try:
    from multi_format_generator import generate_multi_format_scripts
except Exception:
    generate_multi_format_scripts = None  # type: ignore

# Script parser for converting script text to segments
try:
    from script_parser import convert_content_script_to_segments, validate_segments
except Exception:
    convert_content_script_to_segments = None  # type: ignore
    validate_segments = None  # type: ignore


# ---------------------------------------------------------------------------
# Helpers: text/segments/chapters
# ---------------------------------------------------------------------------

def _estimate_duration_sec_from_words(words: int, wpm: int = 150) -> int:
    """
    Conservative estimate: spoken news dialogue ~140–170 WPM.
    Default 150 WPM.
    """
    if not words or words <= 0:
        return 0
    minutes = float(words) / float(wpm)
    return int(minutes * 60)


def script_to_text(script: Dict[str, Any], config: Dict[str, Any]) -> str:
    """
    Convert structured script JSON (segments/dialogue) to plain text dialogue.
    Speaker mapping uses A/B codes if present.
    """
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
        lines.append("")  # blank line between segments
    return "\n".join(lines).strip() + "\n"


def generate_chapters(script: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create a simple chapters list based on segments.
    Downstream ffmeta generation uses this structure.
    """
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
    """
    Convert chapters into FFmpeg metadata format.
    Timing is best-effort; if start/duration missing, they remain 0.
    """
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


# ---------------------------------------------------------------------------
# Public API expected by run_pipeline.py
# ---------------------------------------------------------------------------

def generate_for_topic(topic_id: str, date_str: str | None = None) -> bool:
    """
    Entry point used by run_pipeline.py.

    Args:
        topic_id: e.g. "topic-01"
        date_str: YYYYMMDD (default today)
    """
    try:
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")

        config = load_topic_config(topic_id)
        data_dir = get_data_dir(topic_id)      # kept for compatibility / future use
        output_dir = get_output_dir(topic_id)

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
    """
    Generate all enabled content types for a topic and save outputs.

    Notes:
    - Source collection is no longer done here; generator will use web_search as needed.
    - If generator returns sources list, save it as-is.
    - If generator returns pass_a_raw_text, save it as PASS_A.txt (even if incomplete).
    """
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
        if isinstance(sources_out, list):
            sources_path = output_dir / f"{topic_id}-{date_str}.sources.json"
            with open(sources_path, "w", encoding="utf-8") as f:
                json.dump(sources_out, f, indent=2, ensure_ascii=False)
        else:
            # Fallback: save a small note to keep file presence consistent
            sources_path = output_dir / f"{topic_id}-{date_str}.sources.json"
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

        # Save raw Pass A output if present (even if incomplete)
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
            script_text_raw = content_item.get("script", "") or ""

            # Best-effort duration estimation
            target_duration = int(content_item.get("target_duration", 0) or 0)
            if target_duration <= 0:
                # prefer explicit word targets if present
                max_words = content_item.get("max_words") or content_item.get("target_words") or 0
                try:
                    target_duration = _estimate_duration_sec_from_words(int(max_words))
                except Exception:
                    target_duration = 0

            # Convert script text to segments if needed (required for TTS)
            if convert_content_script_to_segments is not None:
                content_item = convert_content_script_to_segments(content_item)
            else:
                # If parser missing, we cannot safely proceed to TTS.
                print(f"ERROR: script_parser not available; cannot build segments for {code}.")
                continue

            segments = content_item.get("segments") or []

            # Validate segments
            if not segments:
                print(f"ERROR: {code} has no segments; skipping save to avoid downstream failures.")
                preview = script_text_raw[:200].replace("\n", " ")
                print(f"  Script preview: {preview}...")
                continue

            if validate_segments is not None:
                if not validate_segments(segments, code):
                    print(f"ERROR: {code} has invalid segments; skipping.")
                    continue

            total_dialogue = sum(len(seg.get("dialogue", []) or []) for seg in segments)
            print(f"  {code}: {len(segments)} segment(s), {total_dialogue} dialogue items")

            # Build script structure (what downstream modules expect)
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

            # Save script text
            script_path = output_dir / f"{base_name}.script.txt"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_to_text(script_obj, config))

            # Save script JSON
            script_json_path = output_dir / f"{base_name}.script.json"
            with open(script_json_path, "w", encoding="utf-8") as f:
                json.dump(script_obj, f, indent=2, ensure_ascii=False)

            # Save chapters JSON
            chapters = generate_chapters(script_obj)
            chapters_path = output_dir / f"{base_name}.chapters.json"
            with open(chapters_path, "w", encoding="utf-8") as f:
                json.dump(chapters, f, indent=2, ensure_ascii=False)

            # Save ffmeta
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
    parser = argparse.ArgumentParser(description="Generate podcast scripts (multi-format)")
    parser.add_argument("--topic", required=True, help="Topic ID (e.g., topic-01)")
    parser.add_argument("--date", default=None, help="Date string YYYYMMDD (optional)")
    args = parser.parse_args()

    ok = generate_for_topic(args.topic, args.date)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())