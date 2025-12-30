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
import httpx
import os
import json
import re
from typing import List, Optional, Tuple


logger = logging.getLogger(__name__)


def _is_gemini_model(model: str) -> bool:
    return str(model or "").strip().lower().startswith("gemini-")


def _normalize_model(model: str) -> str:
    """Normalize friendly model aliases to official Gemini API model codes.

    Gemini 3 models are currently exposed as *preview* model IDs in the
    Gemini Developer API (v1beta). If callers specify the "clean" ID (e.g.,
    `gemini-3-flash`), we map it to the documented preview ID
    (`gemini-3-flash-preview`) to avoid 404 NOT_FOUND.
    """

    m = str(model or "").strip()
    ml = m.lower()

    # Common Gemini 3 aliases -> preview IDs
    aliases = {
        "gemini-3-flash": "gemini-3-flash-preview",
        "gemini-3-pro": "gemini-3-pro-preview",
        "gemini-3-pro-image": "gemini-3-pro-image-preview",
    }

    return aliases.get(ml, m)


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


def gemini_model_max_output_tokens(model: str) -> int:
    """Best-effort maximum output tokens per model id (Gemini Developer API / v1beta)."""
    m = _normalize_model(model)
    # Known limits (as of Dec 2025): Gemini 3 Flash/Pro preview support up to 65,536 output tokens.
    # If the model is unknown, choose a conservative high value; the API will enforce its own cap.
    if m.startswith("gemini-3-"):
        return 65536
    # Older generations often cap lower; still allow a large value and let API clamp.
    return 8192


def gemini_generate_once(
    *,
    model: str,
    prompt: str = "",
    max_output_tokens: int = 0,
    temperature: float = 0.2,
    json_mode: bool = False,
    **kwargs,
) -> str:
    """
    Single request to Gemini Developer API (v1beta) via raw HTTP.
    This intentionally avoids the python-genai AFC/agentic loop behavior to guarantee:
      - exactly ONE HTTP request per call
      - no automatic tool calls / remote call chains
    """
    if not _is_gemini_model(model):
        raise ValueError(f"Not a Gemini model: {model}")

    model = _normalize_model(model)
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY (Gemini Developer API key).")

    # If caller did not specify, default to the model maximum.
    mot = int(max_output_tokens) if int(max_output_tokens or 0) > 0 else gemini_model_max_output_tokens(model)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json"}

    payload = {
        "contents": [{"role": "user", "parts": [{"text": str(prompt)}]}],
        "generationConfig": {
            "maxOutputTokens": mot,
            "temperature": float(temperature),
            **({"responseMimeType": "application/json"} if json_mode else {}),
        },
    }

    # Single, non-streaming request.
    # Default timeout is intentionally high because long-form generation can take minutes.
    timeout_s = float(os.getenv("GEMINI_HTTP_TIMEOUT_S", os.getenv("OPENAI_TIMEOUT", "1600")))
    connect_s = float(os.getenv("GEMINI_HTTP_CONNECT_TIMEOUT_S", "30"))
    timeout = httpx.Timeout(
        timeout_s,
        connect=min(connect_s, timeout_s),
        read=timeout_s,
        write=timeout_s,
        pool=timeout_s,
    )

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, params={"key": api_key}, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:500]}")

        data = resp.json()

    # Fail fast on tool-call / malformed function call responses.
    try:
        cand0 = (data.get("candidates") or [{}])[0]
        finish_reason = str(cand0.get("finishReason") or "").upper()
        if finish_reason in {"MALFORMED_FUNCTION_CALL", "RECITATION", "SAFETY"}:
            msg = cand0.get("finishMessage") or ""
            raise RuntimeError(f"Gemini generation failed: {finish_reason}: {msg}")
    except Exception:
        # If parsing fails, continue to text extraction below.
        pass

    # Extract text from first candidate.
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text_out = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        if not (text_out or "").strip():
            raise RuntimeError("Gemini returned empty text output")
        return text_out
    except Exception as e:
        raise RuntimeError(f"Gemini response parsing failed: {e}. Raw: {json.dumps(data)[:1000]}")


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
