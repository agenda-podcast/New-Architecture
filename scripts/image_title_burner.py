#!/usr/bin/env python3
"""Burn Google image titles (and host badges) into images.

This is designed for a "TikTok style" overlay:
- A title placed within the top fraction of the frame (default 20%).
- Silver glow around the title.
- Host badges (both hosts) rendered at the top-left and top-right with a
  glow color that depends on host gender.

Inputs:
- Raw images: outputs/<topic>/images/
- Metadata file: outputs/<topic>/images/metadata.json (written by image_collector)
- Topic config: topics/<topic>.json (voice_a_name/gender and voice_b_name/gender)

Outputs:
- Burned images: outputs/<topic>/_prepared_images/<WxH>/processed_burned/
- Burn manifest: outputs/<topic>/_prepared_images/<WxH>/processed_burned/manifest_burn_<WxH>.json

The burner is caching-aware: it skips re-burn if the output is newer than the
source and the burn configuration (hosts + title mapping version) has not changed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont


@dataclass(frozen=True)
class HostBadge:
    name: str
    gender: str  # 'male'|'female'|'other'


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _norm_gender(s: str | None) -> str:
    v = (s or "").strip().lower()
    if v in ("m", "male", "man"):
        return "male"
    if v in ("f", "female", "woman"):
        return "female"
    return "other"


def extract_hosts(topic_cfg: dict) -> List[HostBadge]:
    """Extract hosts from topic config.

    Prefers voice_a_* and voice_b_* fields; falls back to roles if needed.
    """
    hosts: List[HostBadge] = []

    a_name = (topic_cfg.get("voice_a_name") or "").strip()
    a_gender = _norm_gender(topic_cfg.get("voice_a_gender"))
    b_name = (topic_cfg.get("voice_b_name") or "").strip()
    b_gender = _norm_gender(topic_cfg.get("voice_b_gender"))

    if a_name:
        hosts.append(HostBadge(name=a_name, gender=a_gender))
    if b_name and b_name.lower() != a_name.lower():
        hosts.append(HostBadge(name=b_name, gender=b_gender))

    if len(hosts) >= 2:
        return hosts[:2]

    # Fallback to roles list
    roles = topic_cfg.get("roles") or []
    for r in roles:
        if not isinstance(r, dict):
            continue
        n = (r.get("name") or "").strip()
        if not n:
            continue
        if any(h.name.lower() == n.lower() for h in hosts):
            continue
        # gender not present in roles; infer from common prefixes if any
        hosts.append(HostBadge(name=n, gender="other"))
        if len(hosts) >= 2:
            break

    # Ensure two badges for layout consistency
    if len(hosts) == 1:
        hosts.append(HostBadge(name="", gender="other"))
    elif not hosts:
        hosts = [HostBadge(name="", gender="other"), HostBadge(name="", gender="other")]

    return hosts[:2]


def load_titles_map(images_dir: Path) -> Dict[str, str]:
    """Return filename -> Google-visible title."""
    meta_path = images_dir / "metadata.json"
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        items = data.get("items") or []
        out: Dict[str, str] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            lf = str(it.get("local_file") or "").strip()
            if not lf:
                continue
            title = str(it.get("google_title") or it.get("htmlTitle") or "").strip()
            if title:
                out[lf] = title
        return out
    except Exception:
        return {}


def _load_prepare_manifest(processed_dir: Path, w: int, h: int) -> Dict[str, str]:
    """Map composite out_file -> source_name for a specific resolution."""
    m = processed_dir / f"manifest_{w}x{h}.json"
    if not m.exists():
        return {}
    try:
        data = json.loads(m.read_text(encoding="utf-8"))
        out: Dict[str, str] = {}
        for e in data.get("entries") or []:
            if not isinstance(e, dict):
                continue
            if e.get("mode") == "composite" and e.get("out_file") and e.get("source_name"):
                out[str(e["out_file"])] = str(e["source_name"])
        return out
    except Exception:
        return {}


def _safe_filename_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _find_font(prefer_bold: bool = False) -> ImageFont.FreeTypeFont:
    """Best-effort font resolution.

    Uses FONT_PATH env var if provided; otherwise tries common DejaVu fonts.
    Falls back to PIL's default bitmap font.
    """
    font_path_env = (os.environ.get("FONT_PATH") or "").strip()
    candidates: List[str] = []
    if font_path_env:
        candidates.append(font_path_env)

    if prefer_bold:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
        ]
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    ]

    for p in candidates:
        try:
            if p and Path(p).exists():
                # caller sets size later via font_variant
                return ImageFont.truetype(p, size=24)
        except Exception:
            continue

    return ImageFont.load_default()


def _truncate(text: str, max_chars: int) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= max_chars:
        return t
    return t[: max(0, max_chars - 1)].rstrip() + "…"


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    """Simple greedy wrapper (word-based)."""
    words = (text or "").split()
    if not words:
        return []
    lines: List[str] = []
    cur: List[str] = []

    for w in words:
        test = (" ".join(cur + [w])).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def _gender_glow_rgba(gender: str) -> Tuple[int, int, int, int]:
    g = _norm_gender(gender)
    # Gender-based glow colors (explicitly configurable)
    male = os.environ.get("HOST_GLOW_MALE", "64,160,255")
    female = os.environ.get("HOST_GLOW_FEMALE", "255,80,200")
    other = os.environ.get("HOST_GLOW_OTHER", "180,180,180")

    def parse(s: str) -> Tuple[int, int, int]:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 3:
            return (180, 180, 180)
        try:
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            return (180, 180, 180)

    if g == "male":
        r, gg, b = parse(male)
    elif g == "female":
        r, gg, b = parse(female)
    else:
        r, gg, b = parse(other)
    return (r, gg, b, 255)


def _draw_glow_text(
    base: Image.Image,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int, int],
    glow_rgb: Tuple[int, int, int],
    glow_radius: int,
    glow_alpha: int,
    align: str = "left",
    anchor: Optional[str] = None,
) -> None:
    """Draw glow by rendering text to a layer, blurring, then compositing."""
    if not text:
        return

    w, h = base.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    glow = (glow_rgb[0], glow_rgb[1], glow_rgb[2], glow_alpha)
    d.text(xy, text, font=font, fill=glow, align=align, anchor=anchor)
    layer = layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    base.alpha_composite(layer)

    d2 = ImageDraw.Draw(base)
    d2.text(xy, text, font=font, fill=fill, align=align, anchor=anchor)


def _draw_badge(
    base: Image.Image,
    rect: Tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    glow_rgba: Tuple[int, int, int, int],
) -> None:
    """Draw a pill badge with glow."""
    if not text:
        return

    x1, y1, x2, y2 = rect
    w, h = base.size

    # Badge background
    badge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)

    radius = max(8, int((y2 - y1) * 0.45))

    # Soft outer glow
    glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=(glow_rgba[0], glow_rgba[1], glow_rgba[2], 120))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=max(8, int((y2 - y1) * 0.35))))
    base.alpha_composite(glow_layer)

    # Badge fill
    bd.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=(0, 0, 0, 140))

    # Text with subtle inner glow
    tx = (x1 + x2) // 2
    ty = (y1 + y2) // 2
    _draw_glow_text(
        badge,
        (tx, ty),
        text,
        font,
        fill=(255, 255, 255, 255),
        glow_rgb=(glow_rgba[0], glow_rgba[1], glow_rgba[2]),
        glow_radius=max(2, int((y2 - y1) * 0.12)),
        glow_alpha=200,
        align="center",
        anchor="mm",
    )

    base.alpha_composite(badge)


def burn_title_and_hosts(
    src_path: Path,
    dst_path: Path,
    *,
    title: str,
    hosts: List[HostBadge],
    top_fraction: float = 0.20,
) -> bool:
    """Burn title + host badges onto a single image."""
    try:
        im = Image.open(src_path)
        im = im.convert("RGBA")
        w, h = im.size

        top_h = max(1, int(h * top_fraction))

        # Overlay for readability (top gradient)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)

        # Gradient: stronger at very top, fades by ~top_h
        for y in range(0, top_h):
            # 0..1
            t = y / max(1, top_h)
            alpha = int(200 * (1 - t) ** 1.7)
            od.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
        im.alpha_composite(overlay)

        draw = ImageDraw.Draw(im)

        # Fonts
        base_title_font = _find_font(prefer_bold=True)
        base_badge_font = _find_font(prefer_bold=True)

        # Dynamic sizing
        title_size = max(22, int(h * 0.055))
        badge_size = max(16, int(h * 0.030))
        title_font = base_title_font.font_variant(size=title_size) if hasattr(base_title_font, "font_variant") else base_title_font
        badge_font = base_badge_font.font_variant(size=badge_size) if hasattr(base_badge_font, "font_variant") else base_badge_font

        # Layout
        margin_x = int(w * 0.04)
        margin_y = int(h * 0.03)
        badge_h = max(26, int(h * 0.05))
        badge_w = max(240, int(w * 0.36))

        # Host badges (ensure both are attempted)
        h1 = hosts[0] if len(hosts) > 0 else HostBadge("", "other")
        h2 = hosts[1] if len(hosts) > 1 else HostBadge("", "other")

        # Left badge
        _draw_badge(
            im,
            (margin_x, margin_y, margin_x + badge_w, margin_y + badge_h),
            text=_truncate(h1.name, 40),
            font=badge_font,
            glow_rgba=_gender_glow_rgba(h1.gender),
        )

        # Right badge
        _draw_badge(
            im,
            (w - margin_x - badge_w, margin_y, w - margin_x, margin_y + badge_h),
            text=_truncate(h2.name, 40),
            font=badge_font,
            glow_rgba=_gender_glow_rgba(h2.gender),
        )

        # Title text (TikTok style, centered within top band)
        safe_title = _truncate(title, 140)
        if safe_title:
            max_text_width = int(w * 0.88)
            lines = _wrap_text(draw, safe_title, title_font, max_text_width)
            # Prefer <= 2 lines for readability
            if len(lines) > 2:
                lines = lines[:2]
                lines[-1] = _truncate(lines[-1], 70)

            # Compute total block height
            line_h = int(title_size * 1.12)
            block_h = len(lines) * line_h

            center_y = int(top_h * 0.62)
            start_y = max(int(h * 0.02) + badge_h, center_y - block_h // 2)

            for idx, line in enumerate(lines):
                y = start_y + idx * line_h
                _draw_glow_text(
                    im,
                    (w // 2, y),
                    line,
                    title_font,
                    fill=(255, 255, 255, 255),
                    glow_rgb=(200, 200, 200),  # silver glow
                    glow_radius=max(2, int(title_size * 0.18)),
                    glow_alpha=210,
                    align="center",
                    anchor="mm",
                )

        # Persist
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst_path.with_suffix(dst_path.suffix + ".tmp")
        out = im

        # Preserve format
        if dst_path.suffix.lower() in (".jpg", ".jpeg"):
            out = out.convert("RGB")
            out.save(tmp, format="JPEG", quality=92, optimize=True)
        elif dst_path.suffix.lower() == ".webp":
            out.save(tmp, format="WEBP", quality=90, method=6)
        else:
            out.save(tmp)

        os.replace(tmp, dst_path)
        return True

    except Exception:
        return False


def burn_prepared_pool(
    *,
    prepared_pool: List[Path],
    cache_dir: Path,
    images_dir: Path,
    topic_cfg: dict,
    target_width: int,
    target_height: int,
) -> List[Path]:
    """Create burned versions for a prepared pool.

    Returns a list of burned image paths (same ordering as prepared_pool, skipping
    those that failed to burn).
    """
    enable = (os.environ.get("ENABLE_IMAGE_TITLE_BURN", "true").strip().lower() in ("1", "true", "yes", "y", "on"))
    if not enable:
        return prepared_pool

    top_fraction = float(os.environ.get("IMAGE_TITLE_BURN_TOP_FRACTION", "0.20"))

    burned_dir = cache_dir / "processed_burned"
    burned_dir.mkdir(parents=True, exist_ok=True)

    titles_map = load_titles_map(images_dir)
    fallback_title = str(topic_cfg.get("title") or "").strip()

    hosts = extract_hosts(topic_cfg)

    # Map composite file -> original source filename (so titles map works)
    processed_dir = cache_dir / "processed"
    composite_to_source = _load_prepare_manifest(processed_dir, target_width, target_height)

    # Burn config hash: hosts + titles mapping version (metadata updated_at if available)
    meta_hash_seed = ""
    meta_path = images_dir / "metadata.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta_hash_seed = str(meta.get("updated_at") or meta.get("created_at") or "")
        except Exception:
            meta_hash_seed = ""

    hosts_seed = "|".join([f"{h.name}:{h.gender}" for h in hosts])
    burn_cfg_hash = _safe_filename_hash(f"{hosts_seed}::{meta_hash_seed}::{top_fraction}")

    manifest_path = burned_dir / f"manifest_burn_{target_width}x{target_height}.json"

    def load_burn_manifest() -> dict:
        if not manifest_path.exists():
            return {}
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    burn_manifest = load_burn_manifest() or {}
    prev_hash = str(burn_manifest.get("burn_cfg_hash") or "")

    # If config changed, force re-burn by ignoring cached mtimes.
    force = prev_hash != burn_cfg_hash

    entries: List[dict] = []
    burned: List[Path] = []

    for src in prepared_pool:
        src = Path(src)
        out_name = src.name
        dst = burned_dir / out_name

        try:
            st = src.stat()
        except Exception:
            continue

        # Determine title
        source_name = composite_to_source.get(src.name) or src.name
        title = titles_map.get(source_name) or titles_map.get(src.name) or fallback_title

        # Cache check
        if not force and dst.exists():
            try:
                if dst.stat().st_mtime >= st.st_mtime and dst.stat().st_size > 0:
                    burned.append(dst)
                    entries.append({
                        "source_file": str(src.name),
                        "source_name": str(source_name),
                        "source_size": int(st.st_size),
                        "source_mtime": float(st.st_mtime),
                        "out_file": str(dst.name),
                        "title_hash": _safe_filename_hash(title),
                    })
                    continue
            except Exception:
                pass

        ok = burn_title_and_hosts(
            src,
            dst,
            title=title,
            hosts=hosts,
            top_fraction=top_fraction,
        )
        if ok and dst.exists() and dst.stat().st_size > 0:
            burned.append(dst)
            entries.append({
                "source_file": str(src.name),
                "source_name": str(source_name),
                "source_size": int(st.st_size),
                "source_mtime": float(st.st_mtime),
                "out_file": str(dst.name),
                "title_hash": _safe_filename_hash(title),
            })

    # Write manifest
    try:
        payload = {
            "version": 1,
            "burn_cfg_hash": burn_cfg_hash,
            "generated_at": _now_iso(),
            "target": f"{target_width}x{target_height}",
            "count": len(entries),
            "entries": entries,
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass

    return burned
