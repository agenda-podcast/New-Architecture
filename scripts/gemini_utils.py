#!/usr/bin/env python3
"""Gemini (Google GenAI) utilities.

This repo primarily targets OpenAI, but some topics/configs already reference
Gemini models. This module adds a minimal, CI-friendly interface for:

1) One-shot generation (single prompt -> text)
2) Chunked continuation for large outputs using the user-required rule:
   "Provide next part after <last 5 words received from previous part>".

Auth:
  - GOOGLE_API_KEY (GitHub secret)

Notes:
  - We intentionally keep the implementation conservative and dependency-light.
  - Chunking writes are handled by callers; this module only returns strings.
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Tuple


logger = logging.getLogger(__name__)


def _is_gemini_model(model: str) -> bool:
    return str(model or "").strip().lower().startswith("gemini-")


def _last_n_words(text: str, n: int = 5) -> str:
    words = re.findall(r"\S+", (text or "").strip())
    if not words:
        return ""
    return " ".join(words[-n:]) if len(words) >= n else " ".join(words)


def _tail(text: str, n_chars: int) -> str:
    t = text or ""
    return t[-n_chars:] if len(t) > n_chars else t


def _get_client():
    """Create a google-genai client using GOOGLE_API_KEY."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Add it as an env var / GitHub secret.")

    try:
        from google import genai  # type: ignore
    except Exception as e:
        raise ImportError(
            "google-genai is required for Gemini support. Install with: pip install google-genai"
        ) from e

    return genai.Client(api_key=api_key)


def gemini_generate_once(
    *,
    model: str,
    prompt: str,
    max_output_tokens: int,
    temperature: float = 0.2,
) -> str:
    """Single request to Gemini Developer API."""
    if not _is_gemini_model(model):
        raise ValueError(f"Not a Gemini model: {model}")

    client = _get_client()

    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "max_output_tokens": int(max_output_tokens),
            "temperature": float(temperature),
        },
    )

    # SDK exposes `text` for convenient access.
    txt = getattr(resp, "text", None)
    return (txt or "").strip()


def gemini_generate_chunked(
    *,
    model: str,
    base_prompt: str,
    max_output_tokens_per_part: int,
    max_parts: int = 80,
    tail_chars_for_context: int = 1400,
    temperature: float = 0.2,
) -> Tuple[str, List[str]]:
    """Generate a large output in multiple small parts.

    Returns:
      (full_text, parts)

    Continuation rule is fixed to the user's requested wording.
    """
    parts: List[str] = []
    full = ""

    prompt = base_prompt
    for i in range(1, max_parts + 1):
        chunk = gemini_generate_once(
            model=model,
            prompt=prompt,
            max_output_tokens=max_output_tokens_per_part,
            temperature=temperature,
        )
        if not chunk:
            break

        parts.append(chunk)
        full = (full + ("\n" if full else "") + chunk)

        # If the model ended cleanly and output looks complete, callers can still validate.
        if full.strip().endswith("}"):
            break

        anchor = _last_n_words(full, 5)
        ctx_tail = _tail(full, tail_chars_for_context)

        # Conservative continuation prompt to minimize repetition.
        prompt = (
            "You are continuing the SAME output, without restarting or repeating.\n"
            "Do NOT add commentary. Output ONLY the next text segment.\n"
            "Continue EXACTLY where you left off.\n\n"
            f"LAST_OUTPUT_TAIL:\n{ctx_tail}\n\n"
            f"Provide next part after '{anchor}'."
        )

    return full, parts
