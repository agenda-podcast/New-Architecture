#!/usr/bin/env python3
"""
Captions burn-in subflow.

This module is intentionally decoupled from the video renderer. It consumes:
- An already-rendered video (with or without audio)
- A sibling captions file (*.captions.srt) generated during TTS

It produces:
- A new video with captions burned in (in-place replacement by default)

Key design goals:
- Renderer-agnostic (works for both FFmpeg and Blender video generation)
- Deterministic, debuggable: prints exact caption discovery decisions and ffmpeg failures
- Centralized configuration via scripts/global_config.py (env driven)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import os
import re
import subprocess
import tempfile


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"(\d+):(\d+):(\d+)[,\.](\d+)")


def _srt_time_to_seconds(t: str) -> float:
    m = _TIME_RE.search(t.strip())
    if not m:
        return 0.0
    hh, mm, ss, ms = m.groups()
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def _parse_srt_simple(srt_path: Path) -> List[dict]:
    """Parse SRT into a list of {start, end, text} segments. Minimal parser."""
    out: List[dict] = []
    try:
        raw = srt_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return out

    # Normalize line endings.
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    for b in blocks:
        lines = [ln.strip("\n") for ln in b.split("\n") if ln.strip() != ""]
        if len(lines) < 2:
            continue

        # optional numeric index on first line
        idx = 0
        if re.fullmatch(r"\d+", lines[0].strip()):
            idx = 1
        if idx >= len(lines):
            continue

        ts = lines[idx].strip()
        if "-->" not in ts:
            continue
        start_s, end_s = [p.strip() for p in ts.split("-->", 1)]
        start = _srt_time_to_seconds(start_s)
        end = _srt_time_to_seconds(end_s)
        if end <= start:
            continue

        text_lines = lines[idx + 1 :]
        text = "\n".join(text_lines).strip()
        if not text:
            continue
        out.append({"start": start, "end": end, "text": text})
    return out


def _escape_drawtext_text(text: str) -> str:
    """
    Escape text for ffmpeg drawtext.
    Notes:
      - Backslash must be escaped first.
      - ':' and '\'' are special in drawtext.
      - Newlines become \n.
    """
    t = text.replace("\\", "\\\\")
    t = t.replace(":", r"\:")
    t = t.replace("'", r"\'")
    t = t.replace("\n", r"\n")
    return t


def _escape_filter_path(p: str) -> str:
    # For ffmpeg filters, escape backslashes and single quotes.
    return p.replace("\\", "\\\\").replace("'", r"\'")


def _ffmpeg_has_filter(name: str) -> bool:
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
        return name in (r.stdout or "")
    except Exception:
        return False


def _pick_first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        try:
            if p and os.path.exists(p):
                return p
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaptionBurnConfig:
    enabled: bool = True

    # Presets: "tiktok" (default), "boxed" (libass if available), "plain"
    style_preset: str = "tiktok"

    # Rendering strategy:
    # - "auto": prefer subtitles (libass) for boxed/plain; for tiktok always drawtext
    # - "drawtext": force drawtext path
    # - "subtitles": force libass subtitles filter
    renderer: str = "auto"

    # Typography & layout
    bottom_margin_fraction: float = 0.20
    left_right_margin_fraction: float = 0.05
    font_size_fraction: float = 0.033  # tuned for 1080x1920 & 1920x1080

    # Font candidates (Ubuntu runners usually have DejaVu)
    font_bold_candidates: Tuple[str, ...] = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    )
    font_regular_candidates: Tuple[str, ...] = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    )

    # TikTok look parameters (reasonable defaults)
    tiktok_glow_color: str = "cyan"
    tiktok_glow_alpha: float = 0.18
    tiktok_glow_borderw: int = 20
    tiktok_main_borderw: int = 10
    tiktok_shadow_xy: int = 3


def _load_config_from_env() -> CaptionBurnConfig:
    def _env_bool(k: str, default: bool) -> bool:
        v = os.environ.get(k)
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "y", "on")

    enabled = _env_bool("ENABLE_BURN_IN_CAPTIONS", True)
    preset = os.environ.get("CAPTIONS_STYLE_PRESET", os.environ.get("CAPTIONS_STYLE", "tiktok")).strip().lower()
    renderer = os.environ.get("CAPTIONS_RENDERER", "auto").strip().lower()

    bmf = float(os.environ.get("CAPTIONS_BOTTOM_MARGIN_FRACTION", "0.20"))
    lrmf = float(os.environ.get("CAPTIONS_LEFT_RIGHT_MARGIN_FRACTION", "0.05"))
    fsf = float(os.environ.get("CAPTIONS_FONT_SIZE_FRACTION", "0.033"))

    # allow overriding font paths
    bold = tuple(
        p.strip()
        for p in os.environ.get("CAPTIONS_FONT_BOLD", "").split(os.pathsep)
        if p.strip()
    ) or CaptionBurnConfig().font_bold_candidates
    regular = tuple(
        p.strip()
        for p in os.environ.get("CAPTIONS_FONT_REGULAR", "").split(os.pathsep)
        if p.strip()
    ) or CaptionBurnConfig().font_regular_candidates

    glow_color = os.environ.get("CAPTIONS_TIKTOK_GLOW_COLOR", "cyan").strip()
    glow_alpha = float(os.environ.get("CAPTIONS_TIKTOK_GLOW_ALPHA", "0.18"))
    glow_bw = int(os.environ.get("CAPTIONS_TIKTOK_GLOW_BORDERW", "20"))
    main_bw = int(os.environ.get("CAPTIONS_TIKTOK_MAIN_BORDERW", "10"))
    shadow_xy = int(os.environ.get("CAPTIONS_TIKTOK_SHADOW_XY", "3"))

    return CaptionBurnConfig(
        enabled=enabled,
        style_preset=preset,
        renderer=renderer,
        bottom_margin_fraction=bmf,
        left_right_margin_fraction=lrmf,
        font_size_fraction=fsf,
        font_bold_candidates=bold,
        font_regular_candidates=regular,
        tiktok_glow_color=glow_color,
        tiktok_glow_alpha=glow_alpha,
        tiktok_glow_borderw=glow_bw,
        tiktok_main_borderw=main_bw,
        tiktok_shadow_xy=shadow_xy,
    )


# ---------------------------------------------------------------------------
# Core burn-in implementation
# ---------------------------------------------------------------------------

class CaptionBurner:
    def __init__(self, config: Optional[CaptionBurnConfig] = None):
        self.config = config or _load_config_from_env()

    @classmethod
    def from_env(cls) -> "CaptionBurner":
        return cls(_load_config_from_env())

    def discover_captions_srt(self, video_path: Path, audio_path: Optional[Path]) -> Tuple[Optional[Path], List[Path]]:
        """
        Returns: (captions_srt_or_none, checked_paths)
        Accepts legacy naming variants.
        """
        checked: List[Path] = []

        def candidates(base: Path) -> List[Path]:
            return [
                base.with_suffix(".captions.srt"),
                Path(str(base) + ".captions.srt"),  # legacy double extension
                base.with_suffix(".srt"),
            ]

        # prefer audio-derived captions
        if audio_path is not None:
            for c in candidates(Path(str(audio_path))):
                checked.append(c)
                try:
                    if c.exists() and c.stat().st_size > 0:
                        return c, checked
                except OSError:
                    continue

        # then video-derived captions
        for c in candidates(video_path):
            checked.append(c)
            try:
                if c.exists() and c.stat().st_size > 0:
                    return c, checked
            except OSError:
                continue

        return None, checked

    def _build_ass_force_style(self, width: int, height: int) -> str:
        margin_v = max(24, int(height * self.config.bottom_margin_fraction))
        margin_lr = max(24, int(width * self.config.left_right_margin_fraction))
        font_size = max(24, int(height * self.config.font_size_fraction))
        force_style = (
            f"FontName=DejaVu Sans,FontSize={font_size},"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,"
            f"BorderStyle=3,Outline=3,Shadow=1,Alignment=2,"
            f"MarginV={margin_v},MarginL={margin_lr},MarginR={margin_lr}"
        )
        return force_style

    def _build_drawtext_tiktok_vf(self, segments: List[dict], width: int, height: int) -> str:
        """
        TikTok preset uses layered drawtext:
          1) Glow underlay (colored, big border, low opacity)
          2) Main text (white, heavy black stroke, shadow)

        Critical: commas inside between() MUST be escaped as \\, or quoted.
        We do both for robustness: enable='between(t\\,a\\,b)'
        """
        margin_v = max(24, int(height * self.config.bottom_margin_fraction))
        font_size = max(24, int(height * self.config.font_size_fraction))

        font_bold = _pick_first_existing(list(self.config.font_bold_candidates)) or _pick_first_existing(list(self.config.font_regular_candidates))
        if not font_bold:
            # Leave blank; ffmpeg will attempt fontconfig. Still may work.
            font_bold = ""

        filters: List[str] = ["format=yuv420p"]
        for seg in segments:
            start = float(seg["start"])
            end = float(seg["end"])
            esc = _escape_drawtext_text(str(seg["text"]))

            enable = f"enable='between(t\\,{start:.3f}\\,{end:.3f})'"
            common_pos = f"x=(w-text_w)/2:y=h-{margin_v}-text_h:{enable}"

            # Under-glow layer
            glow = (
                "drawtext="
                + (f"fontfile={_escape_filter_path(font_bold)}:" if font_bold else "")
                + f"text='{esc}':"
                + f"fontsize={font_size}:"
                + f"fontcolor=white@{self.config.tiktok_glow_alpha}:"
                + f"borderw={self.config.tiktok_glow_borderw}:"
                + f"bordercolor={self.config.tiktok_glow_color}@0.25:"
                + "shadowx=0:shadowy=0:"
                + common_pos
            )
            filters.append(glow)

            # Main layer
            main = (
                "drawtext="
                + (f"fontfile={_escape_filter_path(font_bold)}:" if font_bold else "")
                + f"text='{esc}':"
                + f"fontsize={font_size}:"
                + "fontcolor=white@1.0:"
                + f"borderw={self.config.tiktok_main_borderw}:"
                + "bordercolor=black@1.0:"
                + f"shadowx={self.config.tiktok_shadow_xy}:shadowy={self.config.tiktok_shadow_xy}:shadowcolor=black@0.95:"
                + common_pos
            )
            filters.append(main)

        return ",".join(filters)

    def burn(
        self,
        video_path: Path,
        audio_path: Optional[Path],
        width: int,
        height: int,
        fps: int,
        output_path: Optional[Path] = None,
        in_place: bool = True,
    ) -> bool:
        """
        Perform burn-in. If in_place=True (default), replaces the input video.
        """
        if not self.config.enabled:
            return True

        video_path = Path(video_path)
        if output_path is None:
            output_path = video_path

        captions_srt, checked = self.discover_captions_srt(video_path=video_path, audio_path=audio_path)
        if captions_srt is None:
            looked_for = ", ".join(p.name for p in checked) if checked else "(none)"
            print(f"  ⓘ No captions file found; skipping burn-in. Looked for: {looked_for}")
            return True

        print(f"  Captions detected: {captions_srt.name} (preset={self.config.style_preset})")

        # Decide renderer
        preset = self.config.style_preset
        renderer = self.config.renderer

        # TikTok is always drawtext unless user forces subtitles
        if preset == "tiktok" and renderer == "auto":
            renderer = "drawtext"

        tmp_dir = video_path.parent
        tmp_out = tmp_dir / (video_path.stem + ".captions.tmp.mp4")

        if tmp_out.exists():
            try:
                tmp_out.unlink()
            except Exception:
                pass

        # Build filtergraph and run ffmpeg
        try:
            if renderer == "subtitles" or (renderer == "auto" and _ffmpeg_has_filter("subtitles")):
                # Boxed/plain via libass subtitles filter
                force_style = self._build_ass_force_style(width, height)
                safe_style = force_style.replace("'", "\\'")
                vf = f"subtitles=filename='{_escape_filter_path(str(captions_srt))}':charenc=UTF-8:force_style='{safe_style}'"
                print("  ⓘ Using subtitles filter (libass) for burn-in")
            else:
                if not _ffmpeg_has_filter("drawtext"):
                    print("  ⚠ drawtext filter unavailable in this ffmpeg build; skipping burn-in")
                    return False
                segments = _parse_srt_simple(captions_srt)
                if not segments:
                    print("  ⚠ Captions file parsed as empty; skipping burn-in")
                    return True

                if preset == "tiktok":
                    print("  ⓘ Using drawtext for TikTok-style captions")
                    vf = self._build_drawtext_tiktok_vf(segments, width, height)
                else:
                    # Minimal readable fallback via subtitles if available; else drawtext main only
                    print("  ⓘ Using drawtext (plain) for burn-in")
                    vf = self._build_drawtext_tiktok_vf(segments, width, height)  # reuse tiktok as best plain; still readable

            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(video_path),
                "-vf", vf,
                "-r", str(int(fps)),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                str(tmp_out),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if r.returncode != 0:
                print(f"  ⚠ Caption burn-in failed (non-fatal): ffmpeg exit {r.returncode}")
                if r.stderr:
                    for ln in (r.stderr or "").splitlines()[-30:]:
                        print(f"    {ln}")
                return False

            # Replace output
            if in_place:
                os.replace(str(tmp_out), str(output_path))
            else:
                os.replace(str(tmp_out), str(output_path))

            print("  ✓ Captions burned into video")
            return True

        finally:
            if tmp_out.exists():
                try:
                    tmp_out.unlink()
                except Exception:
                    pass


def burn_captions_subflow(
    video_path: Path,
    audio_path: Optional[Path],
    width: int,
    height: int,
    fps: int,
    config: Optional[CaptionBurnConfig] = None,
) -> bool:
    """
    Convenience wrapper intended for video_render.py.
    Keeps caption logic fully encapsulated in this module.
    """
    burner = CaptionBurner(config=config)
    return burner.burn(video_path=Path(video_path), audio_path=audio_path, width=width, height=height, fps=fps, in_place=True)
