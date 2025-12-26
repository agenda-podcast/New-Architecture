"""Cleanup outputs according to retention configuration.

Designed for CI runners where disk is constrained. This script removes output
artifacts after they have been published (e.g., uploaded to Releases).

By default, it keeps only burned (final) videos.

Usage:
  python scripts/cleanup_outputs.py --topic topic-01 --date 20251222
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Iterable, List

from output_retention import get_output_retention


def _safe_unlink(p: Path) -> bool:
    try:
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        return False
    return False


def _collect_by_globs(base: Path, globs: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for g in globs:
        out.extend(sorted(base.glob(g)))
    # Unique
    seen = set()
    uniq: List[Path] = []
    for p in out:
        rp = str(p)
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def cleanup_topic_outputs(topic_dir: Path, topic: str, date_yyyymmdd: str) -> int:
    r = get_output_retention()
    prefix = f"{topic}-{date_yyyymmdd}"

    removed = 0
    kept = 0

    # Always delete known intermediates (these should never be kept)
    intermediates = _collect_by_globs(
        topic_dir,
        [
            f"{prefix}*.raw.mp4",
            f"{prefix}*.mux.mp4",
            f"{prefix}*.tmp.mp4",
            f"{prefix}*.captions.mp4",
            f"{prefix}*.work.mp4",
            "**/*.tmp",
        ],
    )
    for p in intermediates:
        if _safe_unlink(p):
            removed += 1

    # Output types
    if not r.keep_audio:
        for p in _collect_by_globs(topic_dir, [f"{prefix}*.m4a", f"{prefix}*.mp3", f"{prefix}*.wav"]):
            if _safe_unlink(p):
                removed += 1

    if not r.keep_subtitles:
        for p in _collect_by_globs(topic_dir, [f"{prefix}*.srt", f"{prefix}*.vtt", f"{prefix}*.ass"]):
            if _safe_unlink(p):
                removed += 1

    if not r.keep_text:
        for p in _collect_by_globs(topic_dir, [f"{prefix}*.script.txt", f"{prefix}*.txt"]):
            # Avoid deleting README-like files if any exist in topic dir
            if p.name.startswith(prefix):
                if _safe_unlink(p):
                    removed += 1

    if not r.keep_json:
        for p in _collect_by_globs(
            topic_dir,
            [
                f"{prefix}*.json",  # script.json, chapters.json, sources.json
            ],
        ):
            if _safe_unlink(p):
                removed += 1

    # Videos: keep only burned/final mp4 by default
    video_files = _collect_by_globs(topic_dir, [f"{prefix}*.mp4"])
    if r.keep_burned_videos:
        kept += len(video_files)
    else:
        for p in video_files:
            if _safe_unlink(p):
                removed += 1

    # Image cache / processed images
    if not r.keep_image_cache:
        for d in [topic_dir / "processed_images", topic_dir / "_prepared_images", topic_dir / "render_tmp", topic_dir / "_download_tmp"]:
            if d.exists() and d.is_dir():
                try:
                    shutil.rmtree(d)
                    removed += 1
                except Exception:
                    pass

    print(
        f"Output cleanup ({topic} {date_yyyymmdd}): removed={removed}, kept_videos={kept}, "
        f"retain={{videos:{r.keep_burned_videos}, audio:{r.keep_audio}, subtitles:{r.keep_subtitles}, "
        f"json:{r.keep_json}, text:{r.keep_text}, image_cache:{r.keep_image_cache}}}"
    )
    return removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--date", required=True, help="YYYYMMDD")
    ap.add_argument("--outputs-root", default="outputs")
    args = ap.parse_args()

    outputs_root = Path(args.outputs_root)
    topic_dir = outputs_root / args.topic
    if not topic_dir.exists():
        print(f"No outputs directory: {topic_dir}")
        return 0

    cleanup_topic_outputs(topic_dir, args.topic, args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
