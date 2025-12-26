#!/usr/bin/env python3
"""
Standalone captions burn-in command.

Usage:
  python scripts/burn_captions.py --video path/to/video.mp4 --audio path/to/audio.m4a --width 1080 --height 1920 --fps 30

Configuration is primarily environment-driven via scripts/global_config.py variables:
  ENABLE_BURN_IN_CAPTIONS=true|false
  CAPTIONS_STYLE_PRESET=tiktok|boxed|plain
  CAPTIONS_RENDERER=auto|drawtext|subtitles
  (plus font overrides and layout fractions)
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from captions.burner import CaptionBurner


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="Input video path (will be replaced in-place unless --out provided)")
    ap.add_argument("--audio", default=None, help="Optional audio path to locate captions via <audio>.captions.srt")
    ap.add_argument("--out", default=None, help="Optional output path (if omitted, in-place replace)")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    video = Path(args.video)
    audio: Optional[Path] = Path(args.audio) if args.audio else None
    out: Optional[Path] = Path(args.out) if args.out else None

    burner = CaptionBurner.from_env()
    ok = burner.burn(video_path=video, audio_path=audio, width=args.width, height=args.height, fps=args.fps, output_path=out, in_place=(out is None))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
