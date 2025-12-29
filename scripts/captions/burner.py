# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

_BACKSLASH_SEQ_RE = re.compile(r'\\([\\/\"\'])')
_ESCAPED_WHITESPACE_RE = re.compile(r'\\[ \t]+')
_LITERAL_UNICODE_RE = re.compile(r'\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})')

def _decode_literal_unicode(s: str) -> str:
    def repl(m: re.Match) -> str:
        h4 = m.group(1)
        h8 = m.group(2)
        try:
            if h4:
                return chr(int(h4, 16))
            if h8:
                return chr(int(h8, 16))
        except Exception:
            return m.group(0)
        return m.group(0)
    return _LITERAL_UNICODE_RE.sub(repl, s)

def sanitize_dialog_text_for_burn(s: str) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)

    s = _decode_literal_unicode(s)
    s = s.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")  # normalize double-escapes

    s = s.replace("\n", "\n").replace("\r", "").replace("\t", " ")
    s = s.replace('\\"', '"').replace("\\'", "'").replace('\\/', '/')
    s = s.replace('\\\\', '\\')

    s = _BACKSLASH_SEQ_RE.sub(r"\1", s)
    s = _ESCAPED_WHITESPACE_RE.sub(" ", s)

    # Drop any remaining standalone backslashes (titles/captions must not show them)
    s = s.replace("\\", "")

    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def pick_frame_png(width: int, height: int, repo_root: Path) -> Optional[Path]:
    override = os.getenv("VIDEO_FRAME_PNG") or os.getenv("FRAME_PNG")
    if override:
        p = (repo_root / override).resolve() if not os.path.isabs(override) else Path(override)
        if p.exists():
            return p

    assets_dir = repo_root / "assets"
    cand = assets_dir / ("frame_vertical.png" if height > width else "frame_horizontal.png")
    if cand.exists():
        return cand

    fallback = assets_dir / "frame.png"
    if fallback.exists():
        return fallback

    frames = sorted(assets_dir.glob("frame*.png"))
    return frames[0] if frames else None

# Integration notes:
# - Call sanitize_dialog_text_for_burn() on BOTH caption lines and titles BEFORE ASS escaping.
# - Set title_font_size = caption_font_size to ensure equal size.
