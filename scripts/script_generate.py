#!/usr/bin/env python3
"""
Generate podcast script from sources and topic configuration.

This script is the main entry point for content generation and output file creation.
It loads topic configuration, generates multi-format scripts, and saves them to output files.

Updated architecture:
- Uses multi_format_generator (Pass A optional, Pass B always)
- Saves generated scripts in multiple formats (.txt, .json, chapters, ffmeta)
- Saves sources file as real sources list (not placeholder meta)
- Saves raw Pass A output (PASS_A.txt) if Pass A ran (even if incomplete)
"""

from __future__ import annotations

import os
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Local imports
from global_config import (
    TOPICS_DIR,
    OUTPUTS_DIR,
    CONTENT_TYPES,
    get_openai_api_key,
    validate_topic_config,
)
from multi_format_generator import generate_multi_format_scripts

# Script parser for converting script text to structured segments
# Note: Keep parser simple and robust for dialogue format.

def script_to_text(script: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Convert structured script JSON to plain text dialogue."""
    lines: List[str] = []
    for seg in script.get("segments", []):
        speaker = seg.get("speaker", "HOST")
        dialogue = seg.get("dialogue", "")
        if dialogue:
            lines.append(f"{speaker}: {dialogue}".strip())
    return "\n".join(lines).strip() + "\n"


def parse_dialogue_to_segments(script_text: str) -> List[Dict[str, Any]]:
    """
    Parse plain dialogue text into structured segments.
    Expected format:
      HOST_A: ...
      HOST_B: ...
    """
    segments: List[Dict[str, Any]] = []
    if not script_text:
        return segments

    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r"^(HOST_[AB]|HOST|NARRATOR)\s*:\s*(.*)$", line, re.IGNORECASE)
        if m:
            speaker = m.group(1).upper()
            dialogue = m.group(2).strip()
            if dialogue:
                segments.append({"speaker": speaker, "dialogue": dialogue})
        else:
            # Continuation line: append to last segment if present
            if segments:
                segments[-1]["dialogue"] = (segments[-1].get("dialogue", "") + " " + line).strip()
            else:
                segments.append({"speaker": "HOST_A", "dialogue": line})
    return segments


def generate_chapters(script: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate simple chapters for the script.
    This is a heuristic placeholder; refine as needed.
    """
    chapters: List[Dict[str, Any]] = []
    segs = script.get("segments", []) or []
    if not segs:
        return chapters

    # Simple: split into 5 chapters by segment count
    total = len(segs)
    n = 5 if total >= 10 else max(1, min(3, total))
    step = max(1, total // n)

    for i in range(0, total, step):
        idx = i // step + 1
        chapters.append({
            "id": idx,
            "title": f"Chapter {idx}",
            "start_segment": i,
        })

    return chapters


def chapters_to_ffmeta(chapters: List[Dict[str, Any]]) -> str:
    """
    Convert chapters list into FFmpeg ffmetadata format (no timestamps computed here).
    """
    lines = [";FFMETADATA1"]
    for ch in chapters:
        title = ch.get("title", "Chapter")
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            "START=0",
            "END=0",
            f"title={title}",
        ]
    return "\n".join(lines).strip() + "\n"


def load_topic_config(topic_id: str) -> Dict[str, Any]:
    """Load topic JSON config from topics directory."""
    path = Path(TOPICS_DIR) / f"{topic_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Topic config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_output_dir(tenant_id: str, topic_id: str) -> Path:
    """Ensure output directory exists for topic under tenant."""
    out_dir = Path(OUTPUTS_DIR) / tenant_id / "outputs" / topic_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def generate_topic_scripts(topic_id: str, tenant_id: str = "0000000001") -> bool:
    """Main generation function for a single topic."""
    try:
        config = load_topic_config(topic_id)
        validate_topic_config(config)

        # Prepare output dir and date suffix
        output_dir = ensure_output_dir(tenant_id, topic_id)
        date_str = datetime.now().strftime("%Y%m%d")

        print(f"Generating scripts for topic: {topic_id}")
        print(f"Output directory: {output_dir}")

        # Use empty source list unless your pipeline provides sources explicitly.
        # Generator will decide whether to use Pass A, Pass B with web_search, or sources-only.
        picked_sources: List[Dict[str, Any]] = []

        # Generate all scripts using multi-format generator
        print(f"Generating multi-format scripts for {topic_id}...")
        multi_data = generate_multi_format_scripts(config, picked_sources)

        # Process each content piece
        content_list = multi_data.get('content', [])
        if not content_list:
            print("Error: No content generated")
            return False

        print(f"Generated {len(content_list)} content pieces")

        # Save each script in multiple formats
        for item in content_list:
            code = item.get("code", "X1")
            ctype = item.get("type", "unknown")
            script_text_raw = item.get("script", "")
            max_words = item.get("max_words") or item.get("target_words") or None

            # Parse text into segments
            segments = parse_dialogue_to_segments(script_text_raw)

            # Build structured script object
            script: Dict[str, Any] = {
                "topic_id": topic_id,
                "code": code,
                "type": ctype,
                "generated_at": datetime.now().isoformat(),
                "max_words": max_words,
                "segments": segments,
            }

            # File naming: topic-ID-date-CODE (e.g., topic-01-20241216-L1)
            base_name = f"{topic_id}-{date_str}-{code}"

            # Save script text
            script_text = script_to_text(script, config)
            script_path = output_dir / f"{base_name}.script.txt"
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_text)

            # Save script JSON
            script_json_path = output_dir / f"{base_name}.script.json"
            with open(script_json_path, 'w', encoding='utf-8') as f:
                json.dump(script, f, indent=2, ensure_ascii=False)

            # Save chapters
            chapters = generate_chapters(script)
            chapters_path = output_dir / f"{base_name}.chapters.json"
            with open(chapters_path, 'w', encoding='utf-8') as f:
                json.dump(chapters, f, indent=2, ensure_ascii=False)

            # Save FFmpeg metadata
            ffmeta = chapters_to_ffmeta(chapters)
            ffmeta_path = output_dir / f"{base_name}.ffmeta"
            with open(ffmeta_path, 'w', encoding='utf-8') as f:
                f.write(ffmeta)

            print(f"  - Saved {code}: {len(segments)} segments")

        # Save sources (from generator, if available)
        sources_out = multi_data.get('sources', []) or []
        sources_path = output_dir / f"{topic_id}-{date_str}.sources.json"
        with open(sources_path, 'w', encoding='utf-8') as f:
            json.dump(sources_out, f, indent=2, ensure_ascii=False)

        # Save raw Pass A output (if Pass A ran). Treat incomplete output as completed.
        pass_a_raw = (multi_data.get('pass_a_raw_text') or '').strip()
        if pass_a_raw:
            pass_a_path = output_dir / f"{topic_id}-{date_str}-PASS_A.txt"
            with open(pass_a_path, 'w', encoding='utf-8') as f:
                f.write(pass_a_raw + "\n")

        print(f"Multi-format scripts generated for {topic_id}: {len(content_list)} pieces")
        return True

    except Exception as e:
        print(f"Error generating multi-format scripts for {topic_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate multi-format scripts for a topic.")
    parser.add_argument("--topic", required=True, help="Topic ID (e.g., topic-01)")
    parser.add_argument("--tenant", default="0000000001", help="Tenant ID")
    args = parser.parse_args()

    ok = generate_topic_scripts(args.topic, args.tenant)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
