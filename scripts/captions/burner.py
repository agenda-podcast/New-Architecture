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
import json

from config import load_topic_config, get_repo_root


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

def _discover_frame_png() -> Optional[Path]:
    """Locate a static PNG frame overlay in the repo's assets folder.

    Priority:
      1) Env: VIDEO_FRAME_PNG / CAPTIONS_FRAME_PNG / FRAME_PNG
      2) Repo: <repo_root>/assets/frame.png
      3) Repo: first match in <repo_root>/assets/frame*.png
    """
    env_keys = ("VIDEO_FRAME_PNG", "CAPTIONS_FRAME_PNG", "FRAME_PNG")
    for k in env_keys:
        v = os.environ.get(k, "").strip()
        if not v:
            continue
        p = Path(v)
        if p.exists() and p.is_file() and p.suffix.lower() == ".png":
            return p

    try:
        assets_dir = get_repo_root() / "assets"
    except Exception:
        assets_dir = None

    if not assets_dir or not assets_dir.exists():
        return None

    direct = assets_dir / "frame.png"
    if direct.exists() and direct.is_file():
        return direct

    matches = sorted([p for p in assets_dir.glob("frame*.png") if p.is_file()])
    return matches[0] if matches else None


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


_TOPIC_ID_RE = re.compile(r"\b(topic-\d+)\b", re.IGNORECASE)


def _infer_topic_id_from_path(p: Path) -> Optional[str]:
    # Prefer a directory segment (e.g., .../outputs/topic-01/...)
    for part in reversed(p.parts):
        m = _TOPIC_ID_RE.search(part)
        if m:
            return m.group(1).lower()
    # Fallback: search full path
    m = _TOPIC_ID_RE.search(str(p))
    return m.group(1).lower() if m else None


def _normalize_gender(g: Optional[str]) -> str:
    if not g:
        return "unknown"
    v = str(g).strip().lower()
    if v in {"m", "male", "man"}:
        return "male"
    if v in {"f", "female", "woman"}:
        return "female"
    return "unknown"


def _load_host_gender_map(topic_id: Optional[str]) -> dict:
    """Return a case-insensitive mapping of host name -> gender."""
    if not topic_id:
        return {}
    try:
        cfg = load_topic_config(topic_id)
    except Exception:
        return {}

    a_name = str(cfg.get("voice_a_name", "")).strip()
    b_name = str(cfg.get("voice_b_name", "")).strip()
    a_gender = _normalize_gender(cfg.get("voice_a_gender"))
    b_gender = _normalize_gender(cfg.get("voice_b_gender"))

    out = {}
    if a_name:
        out[a_name.lower()] = a_gender
    if b_name:
        out[b_name.lower()] = b_gender
    return out

def _load_ab_gender_map(topic_id: Optional[str]) -> dict:
    """Return mapping {'a': gender, 'b': gender} from topic config."""
    if not topic_id:
        return {}
    try:
        cfg = load_topic_config(topic_id)
    except Exception:
        return {}
    return {
        "a": _normalize_gender(cfg.get("voice_a_gender")),
        "b": _normalize_gender(cfg.get("voice_b_gender")),
    }


def _load_host_name_to_speaker_tag_map(topic_id: Optional[str]) -> dict:
    """Return case-insensitive mapping of configured host display names -> speaker tag ('A'/'B')."""
    if not topic_id:
        return {}
    try:
        cfg = load_topic_config(topic_id)
    except Exception:
        return {}
    a_name = str(cfg.get("voice_a_name", "")).strip()
    b_name = str(cfg.get("voice_b_name", "")).strip()
    out: dict = {}
    if a_name:
        out[a_name.lower()] = "A"
    if b_name:
        out[b_name.lower()] = "B"
    return out




def _pick_glow_color_for_gender(gender: str) -> str:
    male = os.environ.get("CAPTIONS_GLOW_COLOR_MALE", "#00D1FF").strip()  # cyan
    female = os.environ.get("CAPTIONS_GLOW_COLOR_FEMALE", "#FF4FD8").strip()  # magenta
    neutral = os.environ.get("CAPTIONS_GLOW_COLOR_NEUTRAL", "#C0C0C0").strip()  # silver

    g = (gender or "unknown").lower()
    if g == "male":
        return male
    if g == "female":
        return female
    return neutral


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


def _ass_time(t: float) -> str:
    # ASS uses H:MM:SS.cs (centiseconds)
    t = max(0.0, float(t))
    hh = int(t // 3600)
    mm = int((t % 3600) // 60)
    ss = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs >= 100:
        cs = 99
    return f"{hh}:{mm:02d}:{ss:02d}.{cs:02d}"


def _ass_color_rgba(hex_rgb: str, alpha: int) -> str:
    """Return ASS &HAABBGGRR from #RRGGBB and alpha 0-255 (0=opaque)."""
    h = (hex_rgb or "").strip()
    if h.startswith("#"):
        h = h[1:]
    if len(h) != 6:
        # fallback white
        rr, gg, bb = (255, 255, 255)
    else:
        rr = int(h[0:2], 16)
        gg = int(h[2:4], 16)
        bb = int(h[4:6], 16)
    aa = max(0, min(255, int(alpha)))
    # ASS expects BBGGRR
    return f"&H{aa:02X}{bb:02X}{gg:02X}{rr:02X}"


def _ass_escape(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\\", "\\\\")
    t = t.replace("{", "\\{").replace("}", "\\}")
    t = t.replace("\n", "\\N")
    return t


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


    def discover_captions_json(self, video_path: Path, audio_path: Optional[Path]) -> Tuple[Optional[Path], List[Path]]:
        """Returns: (captions_json_or_none, checked_paths)."""
        checked: List[Path] = []

        def candidates(base: Path) -> List[Path]:
            return [
                base.with_suffix(".captions.json"),
                Path(str(base) + ".captions.json"),
            ]

        if audio_path is not None:
            for c in candidates(Path(str(audio_path))):
                checked.append(c)
                try:
                    if c.exists() and c.stat().st_size > 0:
                        return c, checked
                except OSError:
                    continue

        for c in candidates(video_path):
            checked.append(c)
            try:
                if c.exists() and c.stat().st_size > 0:
                    return c, checked
            except OSError:
                continue

        return None, checked


    def _load_image_title_segments(self, video_path: Path) -> List[dict]:
        """Load image title timeline sidecar produced by video_render.py.

        Expected sidecar: <video>.image_titles.json (same directory, same stem).
        """
        sidecar = video_path.with_suffix(".image_titles.json")
        if not sidecar.exists() or sidecar.stat().st_size == 0:
            return []
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return []
        segs = data.get("segments") if isinstance(data, dict) else None
        if not isinstance(segs, list):
            return []
        out: List[dict] = []
        for seg in segs:
            try:
                start = float(seg.get("start", 0.0))
                end = float(seg.get("end", 0.0))
                text = str(seg.get("text", "")).strip()
                if text and end > start:
                    out.append({"start": start, "end": end, "text": text})
            except Exception:
                continue
        return out

    def _split_speaker(self, text: str, host_gender_map: dict) -> Tuple[Optional[str], str]:
        """Try to identify speaker from a line prefix like 'Name: ...'."""
        t = (text or "").strip()
        m = re.match(r"^\s*([^:\n]{1,48})\s*:\s*(.+)$", t)
        if not m:
            return None, t
        speaker = m.group(1).strip()
        rest = m.group(2).strip()

        # Only treat it as a speaker prefix if it matches a known host name.
        if host_gender_map:
            s_l = speaker.lower()
            for name in host_gender_map.keys():
                # allow partial match (e.g., 'Gary' vs 'Gary Thompson')
                if s_l == name or s_l in name or name in s_l:
                    return name, rest
        return None, t

    def _build_ass_file(
        self,
        width: int,
        height: int,
        caption_segments: List[dict],
        title_segments: List[dict],
        host_gender_map: dict,
        ab_gender_map: dict,
    ) -> Path:
        """Build a temporary ASS subtitle file with TikTok-like glow.

        We duplicate each line into 2 layers:
          - Glow layer (colored outline, slightly transparent)
          - Main layer (white text with black stroke)
        """
        font_size = max(24, int(height * self.config.font_size_fraction))
        margin_v_bottom = max(24, int(height * self.config.bottom_margin_fraction))
        # Title is placed within top 20% of the screen, centered vertically around 10% height.
        margin_v_top = max(24, int(height * 0.10))
        margin_lr = max(24, int(width * self.config.left_right_margin_fraction))

        # Glow colors
        title_glow = os.environ.get("CAPTIONS_TITLE_GLOW_COLOR", "#00D1FF").strip()  # silver
        glow_alpha = int(float(os.environ.get("CAPTIONS_GLOW_ALPHA_ASS", "0.55")) * 255)
        glow_alpha = max(0, min(255, glow_alpha))

        # Main stroke size approximations
        main_outline = int(os.environ.get("CAPTIONS_MAIN_OUTLINE", str(self.config.tiktok_main_borderw)))
        glow_outline = int(os.environ.get("CAPTIONS_GLOW_OUTLINE", str(self.config.tiktok_glow_borderw)))
        shadow = int(os.environ.get("CAPTIONS_SHADOW", str(self.config.tiktok_shadow_xy)))

        # ASS colors: alpha 0=opaque; convert from 0..255 opacity
        glow_aa = max(0, min(255, 255 - glow_alpha))

        # Common colors
        white = _ass_color_rgba("#FFFFFF", 0)
        black = _ass_color_rgba("#000000", 0)

        def style_line(name: str, primary: str, outline: str, shadow_col: str, outline_sz: int, shadow_sz: int, alignment: int, margin_v: int) -> str:
            return (
                f"Style: {name},DejaVu Sans,{font_size},{primary},&H00000000,{outline},&H00000000,"
                f"-1,0,0,0,100,100,0,0,1,{outline_sz},{shadow_sz},{alignment},{margin_lr},{margin_lr},{margin_v},1"
            )

        # Styles
        # Glow styles use semi-transparent white primary and colored outline.
        glow_primary = _ass_color_rgba("#FFFFFF", glow_aa)
        title_outline = _ass_color_rgba(title_glow, glow_aa)

        # Gender-specific outlines
        male_outline = _ass_color_rgba(_pick_glow_color_for_gender("male"), glow_aa)
        female_outline = _ass_color_rgba(_pick_glow_color_for_gender("female"), glow_aa)
        neutral_outline = _ass_color_rgba(_pick_glow_color_for_gender("unknown"), glow_aa)

        lines: List[str] = []
        lines.append("[Script Info]")
        lines.append("ScriptType: v4.00+")
        lines.append(f"PlayResX: {width}")
        lines.append(f"PlayResY: {height}")
        lines.append("WrapStyle: 2")
        lines.append("ScaledBorderAndShadow: yes")
        lines.append("")

        lines.append("[V4+ Styles]")
        lines.append(
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding"
        )
        # Bottom captions
        lines.append(style_line("CapGlowMale", glow_primary, male_outline, black, glow_outline, 0, 2, margin_v_bottom))
        lines.append(style_line("CapGlowFemale", glow_primary, female_outline, black, glow_outline, 0, 2, margin_v_bottom))
        lines.append(style_line("CapGlowNeutral", glow_primary, neutral_outline, black, glow_outline, 0, 2, margin_v_bottom))
        lines.append(style_line("CapMain", white, black, black, main_outline, shadow, 2, margin_v_bottom))
        # Top titles
        lines.append(style_line("TitleGlow", glow_primary, title_outline, black, glow_outline, 0, 8, margin_v_top))
        lines.append(style_line("TitleMain", white, black, black, main_outline, shadow, 8, margin_v_top))
        lines.append("")

        lines.append("[Events]")
        lines.append("Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text")

        def cap_style_for_segment(seg: dict) -> str:
            # 1) Prefer explicit speaker tags ('A'/'B') from captions.json
            sp = str(seg.get("speaker", "")).strip().lower()
            gender = "unknown"
            if sp in {"a", "b"}:
                gender = ab_gender_map.get(sp, "unknown")
            else:
                # 2) Try speaker name (from captions.json or text prefix)
                speaker_name = seg.get("speaker_name")
                raw_for_infer = str(seg.get("_raw", seg.get("text", "")))
                if not speaker_name:
                    speaker_name, _rest = self._split_speaker(raw_for_infer, host_gender_map)
                if speaker_name:
                    gender = host_gender_map.get(str(speaker_name).lower(), "unknown")

            if gender == "male":
                return "CapGlowMale"
            if gender == "female":
                return "CapGlowFemale"
            return "CapGlowNeutral"

        # Image titles (silver glow) - always top
        for seg in title_segments:
            start = _ass_time(seg["start"])
            end = _ass_time(seg["end"])
            text = _ass_escape(str(seg["text"]))
            # Glow then main
            lines.append(f"Dialogue: 0,{start},{end},TitleGlow,,0,0,0,,{text}")
            lines.append(f"Dialogue: 1,{start},{end},TitleMain,,0,0,0,,{text}")

        # Captions - bottom
        for seg in caption_segments:
            start = _ass_time(seg["start"])
            end = _ass_time(seg["end"])
            raw = str(seg["text"]) 
            text = _ass_escape(raw)
            glow_style = cap_style_for_segment(seg)
            lines.append(f"Dialogue: 0,{start},{end},{glow_style},,0,0,0,,{text}")
            lines.append(f"Dialogue: 1,{start},{end},CapMain,,0,0,0,,{text}")

        tmp_dir = Path(tempfile.mkdtemp(prefix="ass_"))
        ass_path = tmp_dir / "overlays.ass"
        ass_path.write_text("\n".join(lines), encoding="utf-8")
        return ass_path

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

        captions_srt, checked_srt = self.discover_captions_srt(video_path=video_path, audio_path=audio_path)
        captions_json, checked_json = self.discover_captions_json(video_path=video_path, audio_path=audio_path)
        title_segments = self._load_image_title_segments(video_path)

        if captions_srt is None and captions_json is None and not title_segments:
            checked = (checked_srt or []) + (checked_json or [])
            looked_for = ", ".join(p.name for p in checked) if checked else "(none)"
            print(f"  ⓘ No captions/titles to burn; skipping post-process overlays. Looked for captions: {looked_for}")
            return True

        if captions_json is not None:
            print(f"  Captions detected: {captions_json.name} (preset={self.config.style_preset})")
        elif captions_srt is not None:
            print(f"  Captions detected: {captions_srt.name} (preset={self.config.style_preset})")
        if title_segments:
            print(f"  Image title overlay segments: {len(title_segments)}")

        # Decide renderer
        preset = self.config.style_preset
        renderer = self.config.renderer

        # TikTok overlays are rendered via a generated ASS file to avoid command-length issues
        # (drawtext-per-cue can exceed OS argv limits on long episodes).
        if preset == "tiktok":
            renderer = "subtitles"

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
                if not _ffmpeg_has_filter("subtitles"):
                    print("  ⚠ subtitles filter unavailable in this ffmpeg build; skipping burn-in")
                    return False

                if preset == "tiktok":
                    topic_id = _infer_topic_id_from_path(video_path)
                    host_gender_map = _load_host_gender_map(topic_id)
                    ab_gender_map = _load_ab_gender_map(topic_id)

                    # Prefer speaker-tagged JSON captions when available.
                    caption_segments: List[dict] = []
                    if captions_json is not None:
                        try:
                            payload = json.loads(captions_json.read_text(encoding="utf-8", errors="replace"))
                            caps = payload.get("captions", []) if isinstance(payload, dict) else []
                            for c in caps:
                                if not isinstance(c, dict):
                                    continue
                                try:
                                    start = float(c.get("start", 0.0))
                                    end = float(c.get("end", 0.0))
                                except Exception:
                                    continue
                                text = str(c.get("text", "")).strip()
                                if not text or end <= start:
                                    continue
                                seg: dict = {"start": start, "end": end, "text": text}
                                sp = str(c.get("speaker", "")).strip().upper()
                                if sp in ("A", "B"):
                                    seg["speaker"] = sp
                                caption_segments.append(seg)
                        except Exception:
                            caption_segments = []

                    # Fallback to SRT if JSON captions are absent.
                    if not caption_segments and captions_srt is not None:
                        caption_segments = _parse_srt_simple(captions_srt)
                        hide_names = os.environ.get("CAPTIONS_HIDE_SPEAKER_NAMES", "true").strip().lower() in ("1", "true", "yes", "on")
                        name_map = _load_host_name_to_speaker_tag_map(topic_id)
                        cleaned: List[dict] = []
                        for seg in caption_segments:
                            raw = str(seg.get("text", "")).strip()
                            speaker, rest = self._split_speaker(raw, host_gender_map)
                            out_seg = dict(seg)
                            out_seg["_raw"] = raw
                            if hide_names and rest:
                                out_seg["text"] = rest
                            if speaker:
                                out_seg["speaker_name"] = speaker
                                tag = name_map.get(str(speaker).lower())
                                if tag:
                                    out_seg["speaker"] = tag
                            cleaned.append(out_seg)
                        caption_segments = cleaned

                    ass_path = self._build_ass_file(
                        width=width,
                        height=height,
                        caption_segments=caption_segments,
                        title_segments=title_segments,
                        host_gender_map=host_gender_map,
                        ab_gender_map=ab_gender_map,
                    )
                    vf = f"subtitles=filename='{_escape_filter_path(str(ass_path))}'"
                else:
                    # Boxed/plain via libass subtitles filter
                    if captions_srt is None:
                        print("  ⓘ No captions available; skipping burn-in for non-TikTok preset")
                        return True
                    force_style = self._build_ass_force_style(width, height)
                    safe_style = force_style.replace("'", "\\'")
                    vf = f"subtitles=filename='{_escape_filter_path(str(captions_srt))}':charenc=UTF-8:force_style='{safe_style}'"
                    print("  ⓘ Using subtitles filter (libass) for burn-in")
            else:
                if not _ffmpeg_has_filter("drawtext"):
                    print("  ⚠ drawtext filter unavailable in this ffmpeg build; skipping burn-in")
                    return False
                if captions_srt is None:
                    print("  ⓘ Drawtext renderer requires captions; skipping")
                    return True
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

            frame_png = _discover_frame_png()

            if frame_png is not None:
                # Overlay a static PNG frame (no motion, no transitions).
                filter_complex = (
                    f"[0:v]{vf}[v0];"
                    f"[1:v]scale={width}:{height},format=rgba[frm];"
                    f"[v0][frm]overlay=0:0:format=auto,format=yuv420p[v]"
                )

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel", "error",
                    "-i", str(video_path),
                    "-loop", "1",
                    "-i", str(frame_png),
                    "-filter_complex", filter_complex,
                    "-map", "[v]",
                    "-map", "0:a?",
                    "-r", str(int(fps)),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-c:a", "copy",
                    "-shortest",
                    str(tmp_out),
                ]
            else:
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
                    "-map", "0:v:0",
                    "-map", "0:a?",
                    "-c:a", "copy",
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
