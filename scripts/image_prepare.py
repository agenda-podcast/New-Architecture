#!/usr/bin/env python3
"""Prepare/normalize images for video rendering.

Segmented pipeline module:
  - Reads raw images under outputs/<topic>/images/
  - Writes prepared images under outputs/<topic>/_prepared_images/<WxH>/processed/
  - Writes a small manifest JSON for traceability
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from config import load_topic_config, get_output_dir
from global_config import CONTENT_TYPES
from video_render import get_video_resolution_for_code, process_images_for_video


def _discover_images(output_dir: Path) -> List[Path]:
    images_dir = output_dir / "images"
    if not images_dir.exists():
        return []
    out: List[Path] = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        out.extend(sorted(images_dir.glob(ext)))
    return out


def _enabled_prefixes(config: Dict) -> Tuple[set, Dict[str, int]]:
    allowed = set()
    max_per: Dict[str, int] = {}
    ct_cfg = config.get("content_types", {}) or {}
    for ct_key, ct_spec in ct_cfg.items():
        if not isinstance(ct_spec, dict) or not ct_spec.get("enabled", False):
            continue
        pfx = (CONTENT_TYPES.get(ct_key, {}) or {}).get("code_prefix")
        if not pfx:
            continue
        p = str(pfx).upper()
        allowed.add(p)
        try:
            items = int(ct_spec.get("items", 0))
        except Exception:
            items = 0
        if items > 0:
            max_per[p] = items
    return allowed, max_per


def _discover_audio_codes(output_dir: Path, topic_id: str, date_str: str, config: Dict) -> List[str]:
    patt = str(output_dir / f"{topic_id}-{date_str}-*.m4a")
    files = sorted(glob.glob(patt))
    if not files:
        files = sorted(glob.glob(str(output_dir / f"{topic_id}-{date_str}-*.mp3")))
        files += sorted(glob.glob(str(output_dir / f"{topic_id}-{date_str}-*.wav")))

    allowed_prefixes, max_per = _enabled_prefixes(config)
    seen: Dict[str, int] = {}
    codes: List[str] = []
    for fp in files:
        stem = Path(fp).stem
        parts = stem.split("-")
        if len(parts) < 4:
            continue
        code = parts[3]
        if not code:
            continue
        pfx = code[0].upper()
        if allowed_prefixes and pfx not in allowed_prefixes:
            continue
        if pfx in max_per:
            n = seen.get(pfx, 0)
            if n >= max_per[pfx]:
                continue
            seen[pfx] = n + 1
        codes.append(code)
    return codes


def prepare_for_topic(topic_id: str, date_str: str) -> bool:
    config = load_topic_config(topic_id)
    output_dir = get_output_dir(topic_id)
    images = _discover_images(output_dir)
    if not images:
        print("No raw images found. Run image collection first.")
        return False

    codes = _discover_audio_codes(output_dir, topic_id, date_str, config)
    if not codes:
        print("No audio codes found. Run TTS first.")
        return False

    try:
        min_pool = int(os.environ.get("PREPARED_IMAGES_MIN_COUNT", "60"))
    except Exception:
        min_pool = 60

    needed_res = sorted({get_video_resolution_for_code(c) for c in codes})
    summary = {}
    for w, h in needed_res:
        cache_dir = output_dir / "_prepared_images" / f"{w}x{h}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        prepared = process_images_for_video(images, w, h, cache_dir, min_required_images=min_pool)
        summary[f"{w}x{h}"] = {
            "source_images": len(images),
            "prepared_images": len(prepared),
            "processed_dir": str((cache_dir / "processed").resolve()),
        }

    meta_path = output_dir / f"{topic_id}-{date_str}.images_prepared.json"
    meta_path.write_text(json.dumps({"topic_id": topic_id, "date": date_str, "resolutions": summary}, indent=2), encoding="utf-8")
    print("✓ Image preparation completed")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    return 0 if prepare_for_topic(args.topic, args.date) else 1


if __name__ == "__main__":
    raise SystemExit(main())
