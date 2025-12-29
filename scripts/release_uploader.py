#!/usr/bin/env python3
"""scripts/release_uploader.py

GitHub Releases uploader.

Policy (strict):
  - A release must contain **ONLY** the final MP4 videos.
  - Assets must be flat (no folders).
  - Asset names must be **<CODE>.mp4** (no tenant, no topic, no date).
  - Remove everything else (zips, scripts, audio, folders) from the release.

Implementation:
  - Ensure a release exists for the tag.
  - Delete all existing assets for that tag.
  - Upload only video files, renamed to <CODE>.mp4.

This module intentionally does NOT package, zip, or upload any other artifacts.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Dict

from tenant_assets import ensure_release, upload_asset, delete_asset


def _run_gh(cmd: List[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def _list_release_assets(tag: str) -> List[str]:
    rc, out, err = _run_gh(["gh", "release", "view", tag, "--json", "assets", "--jq", ".assets[].name"])
    if rc != 0:
        if "release not found" in (err or "").lower():
            return []
        raise RuntimeError(f"Failed to list release assets for tag={tag}: {err or out}")
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


_CODE_RE = re.compile(r"([A-Z]+\d+)$")


def _extract_code_from_filename(name: str) -> Optional[str]:
    """Extract trailing content code, e.g. 'R8' from 'topic-01-20251229-R8.mp4'."""
    base = name
    for suf in (".burned.mp4", ".final.mp4", ".mp4", ".blender.mp4"):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    # keep only last dash segment
    last = base.split("-")[-1]
    m = _CODE_RE.match(last.strip())
    return m.group(1) if m else None


def _prefer_video(candidates: List[Path]) -> List[Path]:
    """De-duplicate by code and prefer burned/final over plain mp4; skip blender mp4."""
    by_code: Dict[str, Path] = {}

    def score(p: Path) -> int:
        n = p.name.lower()
        # Higher is better
        if n.endswith(".burned.mp4"):
            return 30
        if n.endswith(".final.mp4"):
            return 20
        if n.endswith(".blender.mp4"):
            return -10
        return 10  # plain mp4

    for p in candidates:
        if not p.is_file():
            continue
        if p.name.lower().endswith(".blender.mp4"):
            # Never publish blender intermediates
            continue
        code = _extract_code_from_filename(p.name)
        if not code:
            continue
        prev = by_code.get(code)
        if prev is None or score(p) > score(prev):
            by_code[code] = p

    return [by_code[k] for k in sorted(by_code.keys())]


def find_final_videos(topic_id: str, output_dir: Path, date_str: str) -> List[Path]:
    """Find candidate mp4s and select finals."""
    # Accept both "<topic>-<date>-*.mp4" and optionally already-suffixed finals
    cand: List[Path] = []
    cand += sorted(output_dir.glob(f"{topic_id}-{date_str}-*.burned.mp4"))
    cand += sorted(output_dir.glob(f"{topic_id}-{date_str}-*.final.mp4"))
    cand += sorted(output_dir.glob(f"{topic_id}-{date_str}-*.mp4"))
    return _prefer_video(cand)


def upload_only_videos(
    *,
    topic_id: str,
    output_dir: Path,
    date_str: str,
    release_tag: str,
    dry_run: bool,
) -> None:
    videos = find_final_videos(topic_id, output_dir, date_str)
    if not videos:
        raise RuntimeError(f"No final MP4 videos found in {output_dir} for {topic_id} on {date_str}")

    print(f"Preparing release tag={release_tag} (videos only)")
    for v in videos:
        code = _extract_code_from_filename(v.name) or v.stem
        print(f"  - {v.name} -> {code}.mp4")

    if dry_run:
        print("Dry-run enabled; no release changes made.")
        return

    # Ensure release exists
    ensure_release(release_tag, title=f"{topic_id} videos")

    # Delete ALL existing assets so the release contains ONLY mp4 finals
    existing = _list_release_assets(release_tag)
    if existing:
        print(f"Cleaning existing release assets ({len(existing)})...")
        for a in existing:
            print(f"  - deleting: {a}")
            delete_asset(release_tag, a)

    # Upload with clean names (stage to enforce name)
    tmp_dir = output_dir / "_release_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        import shutil

        for v in videos:
            code = _extract_code_from_filename(v.name) or v.stem
            asset_name = f"{code}.mp4"
            staged = tmp_dir / asset_name
            shutil.copy2(v, staged)
            upload_asset(release_tag, staged, clobber=True)
            staged.unlink(missing_ok=True)
    finally:
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

    print(f"Uploaded {len(videos)} video asset(s) to tag={release_tag}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, help="Topic id (e.g., topic-01)")
    ap.add_argument("--date", required=True, help="Date string YYYYMMDD")
    ap.add_argument("--output-dir", default="outputs", help="Outputs root directory")
    ap.add_argument("--tag", default=None, help="Release tag (default: <topic>-latest)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    topic_id = args.topic.strip()
    date_str = args.date.strip()
    outputs_root = Path(args.output_dir)
    output_dir = outputs_root / topic_id
    release_tag = (args.tag or f"{topic_id}-latest").strip()

    # Final MP4s live in outputs/<topic>/
    upload_only_videos(
        topic_id=topic_id,
        output_dir=output_dir,
        date_str=date_str,
        release_tag=release_tag,
        dry_run=bool(args.dry_run),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
