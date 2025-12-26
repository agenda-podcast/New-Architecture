"""Output retention configuration.

This module defines which output types should be retained on disk after processing.
It is primarily used to reduce workspace disk usage on CI runners.

Defaults are intentionally aggressive for CI: keep only the final burned videos.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool_env(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    v = val.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


@dataclass(frozen=True)
class OutputRetention:
    """Retention flags per output type."""

    keep_burned_videos: bool = True
    # In the segmented architecture, outputs are committed into the repo.
    # Safe default is to retain all artifact types.
    keep_audio: bool = True
    keep_subtitles: bool = True
    keep_json: bool = True
    keep_text: bool = True
    keep_image_cache: bool = True


def get_output_retention() -> OutputRetention:
    """Read retention flags from environment variables.

    Environment variables:
      - KEEP_OUTPUT_BURNED_VIDEOS (default: true)
      - KEEP_OUTPUT_AUDIO (default: false)
      - KEEP_OUTPUT_SUBTITLES (default: false)
      - KEEP_OUTPUT_JSON (default: false)
      - KEEP_OUTPUT_TEXT (default: false)
      - KEEP_OUTPUT_IMAGE_CACHE (default: false)

    Defaults retain all outputs, which is the expected behavior when outputs are
    committed to the repository between modules.
    """

    return OutputRetention(
        keep_burned_videos=_get_bool_env("KEEP_OUTPUT_BURNED_VIDEOS", True),
        keep_audio=_get_bool_env("KEEP_OUTPUT_AUDIO", True),
        keep_subtitles=_get_bool_env("KEEP_OUTPUT_SUBTITLES", True),
        keep_json=_get_bool_env("KEEP_OUTPUT_JSON", True),
        keep_text=_get_bool_env("KEEP_OUTPUT_TEXT", True),
        keep_image_cache=_get_bool_env("KEEP_OUTPUT_IMAGE_CACHE", True),
    )
