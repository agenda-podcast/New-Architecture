#!/usr/bin/env python3
"""
Captions + image titles + static frame burn-in.

This module is renderer-agnostic and intended to run as a post-processing step.

Features
- Burns dialogue captions into the bottom ~20% of the screen.
- Burns image titles into the top ~20% of the screen.
- TikTok-style neon glow for captions (gender-based) and titles (configurable).
- Optional static PNG frame overlay from repo root assets folder (no movement).

Inputs (best-effort discovery)
- Captions:
    * <audio>.captions.json (preferred)
    * <audio>.captions.srt
    * <video>.captions.json / <video>.captions.srt
- Image titles:
    * <video>.image_titles.json

Outputs
- By default, replaces the input video in-place with burned overlays.

Configuration
- ENABLE_BURN_IN_CAPTIONS (default: true)
- CAPTIONS_STYLE_PRESET (default: tiktok)
- CAPTIONS_HIDE_SPEAKER_NAMES (default: true)
- CAPTIONS_GLOW_COLOR_MALE (default: #00D1FF)
- CAPTIONS_GLOW_COLOR_FEMALE (default: #FF4FD8)
- CAPTIONS_GLOW_COLOR_NEUTRAL (default: #C0C0C0)
- CAPTIONS_TITLE_GLOW_COLOR (default: #00D1FF)
- VIDEO_FRAME_PNG or FRAME_PNG: explicit frame path (absolute or repo-relative)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import json
import os
import re
import subprocess
import tempfile

from config import load_topic_config

_TIME_RE = re.compile(r"(\d+):(\d+):(\d+)[,\.](\d+)")


def _srt_time_to_seconds(t: str) -> float:
    m = _TIME_RE.search(t.strip())
    if not m:
        return 0.0
    hh, mm, ss, ms = m.groups()
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def _parse_srt_simple(srt_path: Path) -> List[Dict[str, Any]]:
    """Parse SRT into list of {start,end,text} (best-effort)."""
    out: List[Dict[str, Any]] = []
    try:
        raw = srt_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return out
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    for b in blocks:
        lines = [ln.strip("\n") for ln in b.split("\n") if ln.strip() != ""]
        if len(lines) < 2:
            continue

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


def _ass_time(t: float) -> str:
    # ASS uses H:MM:SS.cs (centiseconds)
    t = max(0.0, float(t))
    hh = int(t // 3600)
    mm = int((t % 3600) // 60)
    ss = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    cs = max(0, min(99, cs))
    return f"{hh}:{mm:02d}:{ss:02d}.{cs:02d}"


def _ass_color_rgba(hex_rgb: str, alpha: int) -> str:
    """Return ASS &HAABBGGRR from #RRGGBB and alpha 0-255 (0=opaque)."""
    h = (hex_rgb or "").strip()
    if h.startswith("#"):
        h = h[1:]
    if len(h) != 6:
        rr, gg, bb = (255, 255, 255)
    else:
        rr = int(h[0:2], 16)
        gg = int(h[2:4], 16)
        bb = int(h[4:6], 16)
    aa = max(0, min(255, int(alpha)))
    return f"&H{aa:02X}{bb:02X}{gg:02X}{rr:02X}"


def _ass_escape(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\\", "\\\\")
    t = t.replace("{", "\\{").replace("}", "\\}")
    t = t.replace("\n", "\\N")
    return t


def _escape_filter_path(p: str) -> str:
    # For ffmpeg filters, escape backslashes and single quotes.
    return p.replace("\\", "\\\\").replace("'", r"\'")


def _ffmpeg_has_filter(name: str) -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=False)
        return name in (r.stdout or "")
    except Exception:
        return False


_TOPIC_ID_RE = re.compile(r"\b(topic-\d+)\b", re.IGNORECASE)


def _infer_topic_id_from_path(p: Path) -> Optional[str]:
    for part in reversed(p.parts):
        m = _TOPIC_ID_RE.search(part)
        if m:
            return m.group(1).lower()
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


def _pick_glow_color_for_gender(gender: str) -> str:
    male = os.environ.get("CAPTIONS_GLOW_COLOR_MALE", "#00D1FF").strip()
    female = os.environ.get("CAPTIONS_GLOW_COLOR_FEMALE", "#FF4FD8").strip()
    neutral = os.environ.get("CAPTIONS_GLOW_COLOR_NEUTRAL", "#C0C0C0").strip()
    g = (gender or "unknown").lower()
    if g == "male":
        return male
    if g == "female":
        return female
    return neutral


def _repo_root_from_here() -> Path:
    # .../repo_root/scripts/captions/burner.py
    return Path(__file__).resolve().parents[2]


def _discover_frame_png(repo_root: Path) -> Optional[Path]:
    # Explicit override
    for envk in ("VIDEO_FRAME_PNG", "FRAME_PNG"):
        v = (os.environ.get(envk) or "").strip()
        if v:
            p = Path(v)
            if not p.is_absolute():
                p = (repo_root / p).resolve()
            if p.exists() and p.is_file():
                return p

    assets = repo_root / "assets"
    if not assets.exists():
        return None

    # Preferred name
    preferred = assets / "frame.png"
    if preferred.exists():
        return preferred

    # Any frame_*.png or frame*.png
    candidates = sorted(assets.glob("frame*.png")) + sorted(assets.glob("Frame*.png"))
    return candidates[0] if candidates else None


def _strip_speaker_prefix(text: str, known_names: List[str], hide: bool) -> str:
    """Remove leading 'Name: ' (or A:/B:) prefix for display text."""
    t = (text or "").strip()
    if not t:
        return ""
    if not hide:
        return t

    # A: / B:
    m = re.match(r"^\s*([AB])\s*:\s+(.+)$", t, flags=re.IGNORECASE)
    if m:
        return m.group(2).strip()

    # Name: ...
    # Requirement: no speaker names should be visible in burned captions.
    # We therefore strip a "prefix:" when it looks like a speaker label.
    m = re.match(r"^\s*([^:\n]{1,48})\s*:\s+(.+)$", t)
    if not m:
        return t
    name = m.group(1).strip()
    rest = m.group(2).strip()
    if not rest:
        return t

    # Always strip explicit A:/B: and known host names.
    for kn in known_names:
        if kn and name.lower() == kn.lower():
            return rest

    # Heuristic: strip short, name-like prefixes (1–3 tokens, alphabetic-ish).
    tokens = [x for x in re.split(r"\s+", name) if x]
    if 1 <= len(tokens) <= 3 and len(name) <= 24:
        if re.fullmatch(r"[A-Za-z][A-Za-z\s\-\.']{0,23}", name):
            return rest
        if name.isupper() and re.fullmatch(r"[A-Z\s\-\.']{1,24}", name):
            return rest

    # Otherwise keep as-is (e.g., "Note:", "Q:").
    return t


@dataclass(frozen=True)
class CaptionBurnConfig:
    enabled: bool = True

    # Presets: "tiktok" (default), others kept for compatibility
    style_preset: str = "tiktok"

    # Rendering strategy (kept for compatibility; this implementation uses libass subtitles filter)
    renderer: str = "auto"

    # Typography & layout
    bottom_margin_fraction: float = 0.20
    left_right_margin_fraction: float = 0.05
    font_size_fraction: float = 0.033

    # Font candidates (kept for compatibility)
    font_bold_candidates: Tuple[str, ...] = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    )
    font_regular_candidates: Tuple[str, ...] = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    )

    # TikTok look parameters (some are consumed via env vars; fields kept for call compatibility)
    tiktok_glow_color: str = "#C0C0C0"
    tiktok_glow_alpha: float = 0.18
    tiktok_glow_borderw: int = 20
    tiktok_main_borderw: int = 10
    tiktok_shadow_xy: int = 3

    # Additional behavior
    hide_speaker_names: bool = True


def _load_config_from_env() -> CaptionBurnConfig:
    def _env_bool(k: str, default: bool) -> bool:
        v = os.environ.get(k)
        if v is None:
            return default
        return v.strip().lower() in ("1", "true", "yes", "y", "on")

    enabled = _env_bool("ENABLE_BURN_IN_CAPTIONS", True)
    preset = (os.environ.get("CAPTIONS_STYLE_PRESET") or os.environ.get("CAPTIONS_STYLE") or "tiktok").strip().lower()
    bmf = float(os.environ.get("CAPTIONS_BOTTOM_MARGIN_FRACTION", "0.20"))
    lrmf = float(os.environ.get("CAPTIONS_LEFT_RIGHT_MARGIN_FRACTION", "0.05"))
    fsf = float(os.environ.get("CAPTIONS_FONT_SIZE_FRACTION", "0.033"))
    hide = _env_bool("CAPTIONS_HIDE_SPEAKER_NAMES", True)

    return CaptionBurnConfig(
        enabled=enabled,
        style_preset=preset or "tiktok",
        renderer=(os.environ.get("CAPTIONS_RENDERER", "auto").strip().lower()),
        bottom_margin_fraction=bmf,
        left_right_margin_fraction=lrmf,
        font_size_fraction=fsf,
        hide_speaker_names=hide,
    )


class CaptionBurner:
    def __init__(self, config: Optional[CaptionBurnConfig] = None):
        self.config = config or _load_config_from_env()

    def _discover_captions_json(self, video_path: Path, audio_path: Optional[Path]) -> Optional[Path]:
        cands: List[Path] = []
        if audio_path:
            cands += [
                audio_path.with_suffix(".captions.json"),
                Path(str(audio_path) + ".captions.json"),
            ]
        cands += [
            video_path.with_suffix(".captions.json"),
            Path(str(video_path) + ".captions.json"),
        ]
        for p in cands:
            try:
                if p.exists() and p.stat().st_size > 0:
                    return p
            except Exception:
                continue
        return None

    def _discover_captions_srt(self, video_path: Path, audio_path: Optional[Path]) -> Optional[Path]:
        cands: List[Path] = []
        if audio_path:
            cands += [
                audio_path.with_suffix(".captions.srt"),
                Path(str(audio_path) + ".captions.srt"),
                audio_path.with_suffix(".srt"),
            ]
        cands += [
            video_path.with_suffix(".captions.srt"),
            Path(str(video_path) + ".captions.srt"),
            video_path.with_suffix(".srt"),
        ]
        for p in cands:
            try:
                if p.exists() and p.stat().st_size > 0:
                    return p
            except Exception:
                continue
        return None

    def _load_image_title_segments(self, video_path: Path) -> List[Dict[str, Any]]:
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
        out: List[Dict[str, Any]] = []
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

    def _load_topic_context(self, video_path: Path) -> Dict[str, Any]:
        topic_id = _infer_topic_id_from_path(video_path)
        if not topic_id:
            return {"topic_id": None, "a_name": "", "b_name": "", "a_gender": "unknown", "b_gender": "unknown"}
        try:
            cfg = load_topic_config(topic_id)
        except Exception:
            return {"topic_id": topic_id, "a_name": "", "b_name": "", "a_gender": "unknown", "b_gender": "unknown"}

        return {
            "topic_id": topic_id,
            "a_name": str(cfg.get("voice_a_name", "")).strip(),
            "b_name": str(cfg.get("voice_b_name", "")).strip(),
            "a_gender": _normalize_gender(cfg.get("voice_a_gender")),
            "b_gender": _normalize_gender(cfg.get("voice_b_gender")),
        }

    def _load_caption_segments(self, video_path: Path, audio_path: Optional[Path]) -> List[Dict[str, Any]]:
        json_path = self._discover_captions_json(video_path, audio_path)
        if json_path:
            try:
                data = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
                caps = data.get("captions") if isinstance(data, dict) else None
                if isinstance(caps, list):
                    out: List[Dict[str, Any]] = []
                    for c in caps:
                        if not isinstance(c, dict):
                            continue
                        try:
                            start = float(c.get("start", 0.0))
                            end = float(c.get("end", 0.0))
                            text = str(c.get("text", "")).strip()
                            if not text or end <= start:
                                continue
                            seg: Dict[str, Any] = {"start": start, "end": end, "text": text}
                            sp = c.get("speaker")
                            if sp is not None:
                                seg["speaker"] = str(sp)
                            out.append(seg)
                        except Exception:
                            continue
                    return out
            except Exception:
                pass

        srt_path = self._discover_captions_srt(video_path, audio_path)
        if srt_path:
            return _parse_srt_simple(srt_path)
        return []

    def _build_ass_file(
        self,
        width: int,
        height: int,
        caption_segments: List[Dict[str, Any]],
        title_segments: List[Dict[str, Any]],
        a_gender: str,
        b_gender: str,
        known_names: List[str],
        hide_speaker_names: bool,
    ) -> Path:
        """Build a temporary ASS file with TikTok-style glow."""
        # Separate sizing for titles vs captions. Titles should be smaller (avoid clipping on mobile).
        caption_font_size = max(24, int(height * self.config.font_size_fraction))
        title_font_size = max(20, int(caption_font_size * 0.50))

        # Safe-area margins: glow/outline can visually extend beyond glyph bounds.
        # We therefore add padding proportional to outline sizes to prevent border clipping.
        margin_v_bottom = max(24, int(height * self.config.bottom_margin_fraction))
        margin_v_top = max(24, int(height * 0.10))  # inside top ~20%
        margin_lr = max(24, int(width * self.config.left_right_margin_fraction))

        # Glow parameters
        main_outline = int(os.environ.get("CAPTIONS_MAIN_OUTLINE", "10"))
        glow_outline = int(os.environ.get("CAPTIONS_GLOW_OUTLINE", "20"))
        shadow = int(os.environ.get("CAPTIONS_SHADOW", "3"))

        # Add a safety pad to margins so no part of glow/outline gets clipped at frame edges.
        safe_pad = max(16, int(max(main_outline, glow_outline) * 1.8))
        margin_lr = max(margin_lr, safe_pad + 24)
        margin_v_top = max(margin_v_top, safe_pad + 24)
        margin_v_bottom = max(margin_v_bottom, safe_pad + 24)

        # Opacity: 0=opaque in ASS; use partially transparent glow
        glow_alpha_float = float(os.environ.get("CAPTIONS_GLOW_ALPHA_ASS", "0.55"))
        glow_alpha = max(0, min(255, int(round(255 * glow_alpha_float))))
        glow_aa = max(0, min(255, 255 - glow_alpha))

        # Colors
        white = _ass_color_rgba("#FFFFFF", 0)
        black = _ass_color_rgba("#000000", 0)

        title_glow = os.environ.get("CAPTIONS_TITLE_GLOW_COLOR", "#00D1FF").strip()
        glow_primary = _ass_color_rgba("#FFFFFF", glow_aa)
        title_outline = _ass_color_rgba(title_glow, glow_aa)

        male_outline = _ass_color_rgba(_pick_glow_color_for_gender("male"), glow_aa)
        female_outline = _ass_color_rgba(_pick_glow_color_for_gender("female"), glow_aa)
        neutral_outline = _ass_color_rgba(_pick_glow_color_for_gender("unknown"), glow_aa)

        def style_line(name: str, font_sz: int, primary: str, outline: str, outline_sz: int, shadow_sz: int, alignment: int, margin_v: int) -> str:
            # BorderStyle=1, outline+shadow enabled
            return (
                f"Style: {name},DejaVu Sans,{font_sz},{primary},&H00000000,{outline},&H00000000,"
                f"-1,0,0,0,100,100,0,0,1,{outline_sz},{shadow_sz},{alignment},{margin_lr},{margin_lr},{margin_v},1"
            )

        lines: List[str] = []
        lines.append("[Script Info]")
        lines.append("ScriptType: v4.00+")
        lines.append(f"PlayResX: {width}")
        lines.append(f"PlayResY: {height}")
        lines.append("WrapStyle: 2")
        lines.append("ScaledBorderAndShadow: yes")
        lines.append("")

        lines.append("[V4+ Styles]")
        lines.append("Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding")
        # Captions bottom (alignment 2 = bottom-center)
        lines.append(style_line("CapGlowMale", caption_font_size, glow_primary, male_outline, glow_outline, 0, 2, margin_v_bottom))
        lines.append(style_line("CapGlowFemale", caption_font_size, glow_primary, female_outline, glow_outline, 0, 2, margin_v_bottom))
        lines.append(style_line("CapGlowNeutral", caption_font_size, glow_primary, neutral_outline, glow_outline, 0, 2, margin_v_bottom))
        lines.append(style_line("CapMain", caption_font_size, white, black, main_outline, shadow, 2, margin_v_bottom))
        # Titles top (alignment 8 = top-center)
        title_main_outline = max(4, int(main_outline * 0.60))
        title_glow_outline = max(8, int(glow_outline * 0.60))
        title_shadow = max(2, int(shadow * 0.60))
        lines.append(style_line("TitleGlow", title_font_size, glow_primary, title_outline, title_glow_outline, 0, 8, margin_v_top))
        lines.append(style_line("TitleMain", title_font_size, white, black, title_main_outline, title_shadow, 8, margin_v_top))
        lines.append("")

        lines.append("[Events]")
        lines.append("Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text")

        def glow_style_for_speaker_token(token: str) -> str:
            t = (token or "").strip().upper()
            if t == "A":
                return "CapGlowMale" if a_gender == "male" else ("CapGlowFemale" if a_gender == "female" else "CapGlowNeutral")
            if t == "B":
                return "CapGlowMale" if b_gender == "male" else ("CapGlowFemale" if b_gender == "female" else "CapGlowNeutral")
            return "CapGlowNeutral"

        def wrap_title(text: str) -> str:
            """Hard-wrap long titles to avoid clipping on mobile frames."""
            raw = (text or "").strip()
            if not raw:
                return ""
            # Approximate max chars per line based on available width and font size.
            try:
                avail = max(200, width - 2 * margin_lr)
                approx_chars = max(18, int(avail / max(10, int(title_font_size * 0.55))))
            except Exception:
                approx_chars = 44
            max_lines = 2

            words = raw.split()
            if not words:
                return raw
            lines_out: List[str] = []
            cur: List[str] = []
            cur_len = 0
            for w in words:
                w_len = len(w)
                add = w_len if not cur else (w_len + 1)
                if cur and (cur_len + add) > approx_chars:
                    lines_out.append(" ".join(cur))
                    cur = [w]
                    cur_len = w_len
                else:
                    cur.append(w)
                    cur_len += add
            if cur:
                lines_out.append(" ".join(cur))

            if len(lines_out) > max_lines:
                # Truncate to max lines and add ellipsis.
                kept = lines_out[:max_lines]
                kept[-1] = (kept[-1].rstrip(" .") + "…") if not kept[-1].endswith("…") else kept[-1]
                lines_out = kept

            return "\\N".join(lines_out)

        # Titles (top)
        for seg in title_segments:
            start = _ass_time(seg["start"])
            end = _ass_time(seg["end"])
            txt = _ass_escape(wrap_title(str(seg["text"]) or ""))
            if not txt:
                continue
            lines.append(f"Dialogue: 0,{start},{end},TitleGlow,,0,0,0,,{txt}")
            lines.append(f"Dialogue: 1,{start},{end},TitleMain,,0,0,0,,{txt}")

        # Captions (bottom)
        for seg in caption_segments:
            start = _ass_time(seg["start"])
            end = _ass_time(seg["end"])
            raw_text = str(seg.get("text", "")).strip()
            if not raw_text:
                continue

            visible = _strip_speaker_prefix(raw_text, known_names, hide_speaker_names)
            if not visible:
                continue

            sp = str(seg.get("speaker", "")).strip()
            glow_style = glow_style_for_speaker_token(sp)
            txt = _ass_escape(visible)

            lines.append(f"Dialogue: 0,{start},{end},{glow_style},,0,0,0,,{txt}")
            lines.append(f"Dialogue: 1,{start},{end},CapMain,,0,0,0,,{txt}")

        tmp_dir = Path(tempfile.mkdtemp(prefix="ass_"))
        ass_path = tmp_dir / "overlays.ass"
        ass_path.write_text("\n".join(lines), encoding="utf-8")
        return ass_path

    def burn(
        self,
        video_path: Path,
        audio_path: Optional[Path],
        width: int,
        height: int,
        fps: int,
        in_place: bool = True,
    ) -> bool:
        video_path = Path(video_path)
        if not self.config.enabled:
            return True
        if not video_path.exists():
            print(f"  ✗ Video not found: {video_path}")
            return False

        if not _ffmpeg_has_filter("subtitles"):
            print("  ✗ FFmpeg subtitles filter (libass) not available; cannot burn TikTok-style overlays")
            return False

        title_segments = self._load_image_title_segments(video_path)
        caption_segments = self._load_caption_segments(video_path, audio_path)

        if not title_segments and not caption_segments:
            print("  ⓘ No captions and no titles sidecar; skipping overlays")
            return True

        ctx = self._load_topic_context(video_path)
        known_names = [ctx.get("a_name", ""), ctx.get("b_name", "")]
        known_names = [n for n in known_names if n]

        ass_path = self._build_ass_file(
            width=width,
            height=height,
            caption_segments=caption_segments,
            title_segments=title_segments,
            a_gender=ctx.get("a_gender", "unknown"),
            b_gender=ctx.get("b_gender", "unknown"),
            known_names=known_names,
            hide_speaker_names=self.config.hide_speaker_names,
        )

        repo_root = _repo_root_from_here()
        frame_png = _discover_frame_png(repo_root)

        tmp_out = Path(tempfile.mkstemp(prefix="burn_", suffix=video_path.suffix)[1])
        try:
            if frame_png and frame_png.exists():
                # Burn ASS then overlay frame on top (static)
                filter_complex = (
                    f"[0:v]subtitles=filename='{_escape_filter_path(str(ass_path))}':charenc=UTF-8[v0];"
                    f"[1:v]scale={width}:{height}[fr];"
                    f"[v0][fr]overlay=0:0:format=auto[v]"
                )
                cmd = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(video_path),
                    "-loop", "1", "-i", str(frame_png),
                    "-filter_complex", filter_complex,
                    "-map", "[v]",
                    "-map", "0:a?",
                    "-r", str(int(fps)),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-c:a", "copy",
                    str(tmp_out),
                ]
            else:
                vf = f"subtitles=filename='{_escape_filter_path(str(ass_path))}':charenc=UTF-8"
                cmd = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
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
                print(f"  ✗ Overlay burn-in failed: ffmpeg exit {r.returncode}")
                if r.stderr:
                    for ln in (r.stderr or "").splitlines()[-40:]:
                        print(f"    {ln}")
                return False

            if in_place:
                os.replace(str(tmp_out), str(video_path))
            else:
                # If not in_place, caller passed output path as video_path
                os.replace(str(tmp_out), str(video_path))

            print("  ✓ Overlays burned into video")
            return True
        finally:
            try:
                if tmp_out.exists():
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
    burner = CaptionBurner(config=config)
    return burner.burn(video_path=Path(video_path), audio_path=audio_path, width=width, height=height, fps=fps, in_place=True)


def build_overlays_ass_from_segments(
    video_path: Path,
    width: int,
    height: int,
    caption_segments: List[Dict[str, Any]],
    title_segments: List[Dict[str, Any]],
    config: Optional[CaptionBurnConfig] = None,
    hide_speaker_names: bool = True,
) -> Optional[Path]:
    """Create an ASS overlays file (titles + captions) without running FFmpeg.

    Intended for single-pass rendering where overlays are applied during the main
    FFmpeg encode (subtitles filter), avoiding additional re-encodes.
    """
    burner = CaptionBurner(config=config)
    if not burner.config.enabled:
        return None
    ctx = burner._load_topic_context(Path(video_path))
    known_names = [ctx.get("a_name", ""), ctx.get("b_name", "")]
    known_names = [n for n in known_names if n]
    return burner._build_ass_file(
        width=int(width),
        height=int(height),
        caption_segments=caption_segments or [],
        title_segments=title_segments or [],
        a_gender=ctx.get("a_gender", "unknown"),
        b_gender=ctx.get("b_gender", "unknown"),
        known_names=known_names,
        hide_speaker_names=hide_speaker_names,
    )
