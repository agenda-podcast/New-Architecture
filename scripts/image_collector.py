#!/usr/bin/env python3
"""Image collection using Google Custom Search API.

Collects images for a topic and stores them under outputs/<topic>/images/.

Key behaviors:
- Uses Google Programmable Search (Custom Search API) for image search.
- Avoids API calls if sufficient images already exist.
- Tracks daily API usage locally to prevent burning quota.

Metadata (added):
- Writes outputs/<topic>/images/metadata.json containing:
  - Google-visible title (item.title)
  - htmlTitle/snippet/displayLink
  - context page URL (image.contextLink when available)
  - original image URL
  - local filename

Downstream modules can burn these titles into images and/or video overlays.

Environment:
  GOOGLE_CUSTOM_SEARCH_API_KEY
  GOOGLE_SEARCH_ENGINE_ID
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Google API client
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.warning("google-api-python-client not available - image collection disabled")

# Configuration
DEFAULT_NUM_IMAGES = 50
MAX_NUM_IMAGES = 50
IMAGE_SEARCH_TIMEOUT = 10

from global_config import (
    ALLOWED_IMAGE_EXTENSIONS,
    GOOGLE_SEARCH_DAILY_LIMIT,
    GOOGLE_SEARCH_MAX_RESULTS_PER_QUERY,
    GOOGLE_SEARCH_RESULTS_PER_PAGE,
)

# Daily usage tracking file
USAGE_TRACKING_FILE = Path.home() / ".podcast-maker" / "google_search_usage.json"

# Metadata file stored next to images
IMAGES_METADATA_FILENAME = "metadata.json"


@dataclass
class GoogleImageItem:
    """Normalized Google Custom Search item for images."""

    query: str
    image_url: str
    title: str = ""
    html_title: str = ""
    snippet: str = ""
    display_link: str = ""
    context_link: str = ""  # page where image appears
    mime: str = ""

    @classmethod
    def from_api_item(cls, query: str, item: Dict[str, Any]) -> "GoogleImageItem":
        img = item.get("image", {}) or {}
        return cls(
            query=query,
            image_url=str(item.get("link") or ""),
            title=str(item.get("title") or ""),
            html_title=str(item.get("htmlTitle") or ""),
            snippet=str(item.get("snippet") or ""),
            display_link=str(item.get("displayLink") or ""),
            context_link=str(img.get("contextLink") or ""),
            mime=str(item.get("mime") or ""),
        )


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _safe_bool_env(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _metadata_path(images_dir: Path) -> Path:
    return images_dir / IMAGES_METADATA_FILENAME


def _load_metadata(images_dir: Path) -> Dict[str, Any]:
    p = _metadata_path(images_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning(f"Could not read images metadata {p}: {e}")
        return {}


def _write_metadata(images_dir: Path, data: Dict[str, Any]) -> None:
    p = _metadata_path(images_dir)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _ensure_metadata_for_existing_images(
    images_dir: Path,
    topic_title: str,
    topic_queries: List[str],
    existing_images: List[Path],
) -> None:
    """Ensure metadata.json exists and contains entries for all existing images.

    If we don't know the Google title (because images were downloaded earlier
    without metadata), we fall back to topic_title.
    """
    meta = _load_metadata(images_dir)
    items: List[Dict[str, Any]] = list(meta.get("items") or [])

    by_file = {str((it.get("local_file") or "")).strip(): it for it in items}

    changed = False
    for img in sorted(existing_images, key=lambda p: p.name):
        if img.name in by_file:
            continue
        items.append(
            {
                "local_file": img.name,
                "google_title": topic_title,
                "google_htmlTitle": "",
                "snippet": "",
                "displayLink": "",
                "contextLink": "",
                "image_url": "",
                "query": (topic_queries[0] if topic_queries else topic_title),
                "mime": "",
                "downloaded_at": "",
                "source": "existing",
            }
        )
        changed = True

    if not meta:
        meta = {
            "version": 1,
            "created_at": _now_iso(),
            "topic_title": topic_title,
            "queries": topic_queries,
            "items": [],
        }
        changed = True

    if changed:
        meta["updated_at"] = _now_iso()
        meta["topic_title"] = topic_title
        meta["queries"] = topic_queries
        meta["items"] = sorted(items, key=lambda it: str(it.get("local_file") or ""))
        _write_metadata(images_dir, meta)


def get_daily_usage() -> Dict[str, Union[str, int]]:
    """Get the current daily usage count from the tracking file."""
    today = date.today().isoformat()

    USAGE_TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)

    if USAGE_TRACKING_FILE.exists():
        try:
            data = json.loads(USAGE_TRACKING_FILE.read_text(encoding="utf-8"))
            if data.get("date") != today:
                return {"date": today, "count": 0}
            return {"date": today, "count": int(data.get("count", 0))}
        except Exception as e:
            logger.warning(f"Error reading usage tracking file: {e}")

    return {"date": today, "count": 0}


def update_daily_usage(results_used: int) -> None:
    """Update the daily usage count in the tracking file."""
    usage = get_daily_usage()
    usage["count"] = int(usage.get("count", 0)) + int(results_used)
    try:
        USAGE_TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
        USAGE_TRACKING_FILE.write_text(json.dumps(usage), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Error updating usage tracking file: {e}")


def check_daily_limit(requested_results: int) -> Tuple[bool, int]:
    """Check if the requested number of results would exceed the daily limit."""
    usage = get_daily_usage()
    used = int(usage.get("count", 0))
    available = max(0, int(GOOGLE_SEARCH_DAILY_LIMIT) - used)
    if available == 0:
        return False, 0
    return True, min(int(requested_results), available)


def _discover_existing_images(images_dir: Path) -> List[Path]:
    existing: List[Path] = []
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        existing.extend([p for p in images_dir.glob(f"*{ext}") if p.suffix == ext])
    return sorted(existing)


def collect_images_for_topic(
    topic_title: str,
    topic_queries: List[str],
    output_dir: Path,
    num_images: int = DEFAULT_NUM_IMAGES,
    api_key: Optional[str] = None,
    search_engine_id: Optional[str] = None,
) -> List[Path]:
    """Collect images for a topic using Google Custom Search API."""

    if num_images > MAX_NUM_IMAGES:
        logger.warning(f"Requested {num_images} images, limiting to max: {MAX_NUM_IMAGES}")
        num_images = MAX_NUM_IMAGES

    original_num_images = num_images

    output_dir.mkdir(parents=True, exist_ok=True)

    # Existing images short-circuit (also ensures metadata exists for existing images)
    existing_images = _discover_existing_images(output_dir)
    if existing_images:
        _ensure_metadata_for_existing_images(output_dir, topic_title, topic_queries, existing_images)

    if len(existing_images) >= num_images:
        logger.info("=" * 80)
        logger.info("SUFFICIENT IMAGES ALREADY EXIST")
        logger.info("=" * 80)
        logger.info(f"Found {len(existing_images)} existing images in {output_dir}")
        logger.info(f"Required: {num_images} images")
        logger.info("Skipping Google Custom Search API calls")
        logger.info("=" * 80)
        return existing_images[:num_images]

    # Partial images: only request what we still need
    images_needed = num_images - len(existing_images)
    if existing_images:
        logger.info("=" * 80)
        logger.info("PARTIAL IMAGES FOUND")
        logger.info("=" * 80)
        logger.info(f"Existing images: {len(existing_images)}")
        logger.info(f"Required images: {num_images}")
        logger.info(f"Additional images needed: {images_needed}")
        logger.info(f"Will request only {images_needed} new images from API")
        logger.info("=" * 80)
        num_images = images_needed

    logger.info("=" * 80)
    logger.info(f"COLLECTING IMAGES FOR: {topic_title}")
    logger.info("=" * 80)
    logger.info(f"Target: {num_images} images")
    logger.info(f"Queries: {topic_queries}")
    logger.info(f"Output: {output_dir}")
    logger.info("=" * 80)

    if not GOOGLE_API_AVAILABLE:
        raise ImportError(
            "google-api-python-client package is required for image collection. "
            "Install with: pip install google-api-python-client"
        )

    api_key = api_key or os.environ.get("GOOGLE_CUSTOM_SEARCH_API_KEY")
    search_engine_id = search_engine_id or os.environ.get("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key:
        raise ValueError(
            "Google Custom Search API key not found. "
            "Please set GOOGLE_CUSTOM_SEARCH_API_KEY environment variable."
        )

    if not search_engine_id:
        raise ValueError(
            "Google Search Engine ID not found. "
            "Please set GOOGLE_SEARCH_ENGINE_ID environment variable."
        )

    try:
        service = build("customsearch", "v1", developerKey=api_key)
        logger.info("✓ Successfully connected to Google Custom Search API")
    except Exception as e:
        logger.error(f"Failed to build Google Custom Search API service: {e}")
        raise

    usage = get_daily_usage()
    logger.info(f"Daily usage: {usage['count']}/{GOOGLE_SEARCH_DAILY_LIMIT} results used today")

    can_proceed, available_results = check_daily_limit(num_images)
    if not can_proceed:
        logger.error("=" * 80)
        logger.error("DAILY LIMIT REACHED")
        logger.error("=" * 80)
        logger.error(f"Daily limit of {GOOGLE_SEARCH_DAILY_LIMIT} results has been reached.")
        logger.error(f"Current usage: {usage['count']} results")
        logger.error("The limit will reset at midnight.")
        logger.error("=" * 80)
        return []

    if available_results < num_images:
        logger.warning(f"Only {available_results} results available within daily limit (requested: {num_images})")
        num_images = available_results

    # Collect items (with metadata) from search results with pagination
    collected: List[GoogleImageItem] = []
    images_per_query = max(1, num_images // max(1, len(topic_queries))) if topic_queries else num_images

    for query in (topic_queries or [topic_title])[:5]:
        logger.info(f"Searching for images: '{query}'")

        query_target = min(images_per_query, GOOGLE_SEARCH_MAX_RESULTS_PER_QUERY)
        query_items: List[GoogleImageItem] = []
        start_index = 1

        while len(query_items) < query_target and start_index <= 91:
            can_proceed, _remaining = check_daily_limit(GOOGLE_SEARCH_RESULTS_PER_PAGE)
            if not can_proceed:
                logger.warning(f"  Daily limit reached during pagination for query '{query}'")
                break

            try:
                result = (
                    service.cse()
                    .list(
                        q=query,
                        cx=search_engine_id,
                        searchType="image",
                        imgType="photo",
                        num=GOOGLE_SEARCH_RESULTS_PER_PAGE,
                        start=start_index,
                        safe="active",
                        imgSize="XLARGE",
                    )
                    .execute()
                )

                page_items = result.get("items", []) or []
                if not page_items:
                    logger.info("  No more results available for this query")
                    break

                # Update daily usage counter based on returned items
                update_daily_usage(len(page_items))

                for item in page_items:
                    if not item.get("link"):
                        continue
                    gi = GoogleImageItem.from_api_item(query=query, item=item)
                    if not gi.image_url:
                        continue
                    query_items.append(gi)
                    logger.info(f"  Found image {len(query_items)}: {gi.title[:50] if gi.title else 'No title'}")

                # Next page
                next_page = (result.get("queries", {}) or {}).get("nextPage", [])
                if next_page and "startIndex" in next_page[0]:
                    start_index = int(next_page[0]["startIndex"])
                    logger.info(f"  Moving to next page (start={start_index})")
                else:
                    break

            except HttpError as e:
                logger.error(f"Google API error for query '{query}': {e}")
                break
            except Exception as e:
                logger.error(f"Error searching for images with query '{query}': {e}")
                break

        collected.extend(query_items)
        logger.info(f"  Total images collected for query '{query}': {len(query_items)}")

        if len(collected) >= num_images:
            break

    # Deduplicate by image_url preserving order
    seen = set()
    unique: List[GoogleImageItem] = []
    for it in collected:
        if it.image_url in seen:
            continue
        seen.add(it.image_url)
        unique.append(it)

    if not unique:
        logger.warning("=" * 80)
        logger.warning("NO IMAGES FOUND")
        logger.warning("=" * 80)
        return []

    # Download images and build new metadata entries
    start_idx = len(existing_images)
    downloaded_images: List[Path] = []

    meta = _load_metadata(output_dir)
    meta_items: List[Dict[str, Any]] = list(meta.get("items") or [])
    meta_by_file = {str((it.get("local_file") or "")).strip(): it for it in meta_items}

    for i, it in enumerate(unique[:num_images]):
        url = it.image_url
        url_lower = url.lower()

        ext = ".jpg"
        is_allowed = False
        for allowed_ext in ALLOWED_IMAGE_EXTENSIONS:
            if url_lower.endswith(allowed_ext):
                ext = allowed_ext
                is_allowed = True
                break

        if not is_allowed:
            # Allow URLs without an image suffix; skip clear non-image content
            if url_lower.endswith((".html", ".htm", ".php", ".asp", ".txt", ".pdf")):
                logger.warning(f"    ✗ Skipping URL with unsupported extension: {url[:60]}")
                continue

        image_path = output_dir / f"image_{start_idx + i:03d}{ext}"

        if image_path.exists() and image_path.stat().st_size > 0:
            downloaded_images.append(image_path)
            # Ensure metadata entry exists
            if image_path.name not in meta_by_file:
                meta_items.append(
                    {
                        "local_file": image_path.name,
                        "google_title": it.title,
                        "google_htmlTitle": it.html_title,
                        "snippet": it.snippet,
                        "displayLink": it.display_link,
                        "contextLink": it.context_link,
                        "image_url": it.image_url,
                        "query": it.query,
                        "mime": it.mime,
                        "downloaded_at": "",
                        "source": "existing",
                    }
                )
            continue

        if not url.startswith(("http://", "https://")):
            logger.warning(f"    ✗ Skipping invalid URL: {url[:60]}")
            continue

        max_retries = 2
        for retry in range(max_retries + 1):
            try:
                if retry > 0:
                    logger.info(f"  Retry {retry}/{max_retries} for image {start_idx + i + 1}/{original_num_images}...")
                else:
                    logger.info(f"  Downloading image {start_idx + i + 1}/{original_num_images}: {url[:60]}...")

                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                    },
                )
                with urllib.request.urlopen(req, timeout=IMAGE_SEARCH_TIMEOUT) as resp:
                    image_data = resp.read()

                if len(image_data) < 1024:
                    logger.warning(f"    ✗ Image too small ({len(image_data)} bytes), skipping")
                    break

                with open(image_path, "wb") as f:
                    f.write(image_data)
                    os.fsync(f.fileno())

                downloaded_images.append(image_path)
                logger.info(f"    ✓ Saved: {image_path.name} ({len(image_data) / 1024:.1f} KB)")

                meta_items.append(
                    {
                        "local_file": image_path.name,
                        "google_title": it.title,
                        "google_htmlTitle": it.html_title,
                        "snippet": it.snippet,
                        "displayLink": it.display_link,
                        "contextLink": it.context_link,
                        "image_url": it.image_url,
                        "query": it.query,
                        "mime": it.mime,
                        "downloaded_at": _now_iso(),
                        "source": "google_custom_search",
                    }
                )

                break

            except urllib.error.HTTPError as e:
                if retry < max_retries and getattr(e, "code", None) in [429, 503, 504]:
                    logger.warning(f"    ⚠ HTTP {e.code} - retrying...")
                    time.sleep(1)
                    continue
                logger.warning(f"    ✗ HTTP error downloading image: {getattr(e, 'code', '?')} {getattr(e, 'reason', '')}")
                break
            except urllib.error.URLError as e:
                if retry < max_retries:
                    logger.warning("    ⚠ Network error - retrying...")
                    time.sleep(1)
                    continue
                logger.warning(f"    ✗ URL error downloading image: {getattr(e, 'reason', '')}")
                break
            except Exception as e:
                logger.warning(f"    ✗ Error downloading image: {e}")
                break

    logger.info("=" * 80)
    logger.info(f"IMAGE COLLECTION COMPLETE: {len(downloaded_images)}/{num_images} images")

    # Verify downloaded images
    verified_downloads: List[Path] = []
    for p in downloaded_images:
        try:
            if p.exists() and p.stat().st_size > 0:
                verified_downloads.append(p)
        except Exception:
            pass

    if len(verified_downloads) != len(downloaded_images):
        logger.warning(f"Only {len(verified_downloads)}/{len(downloaded_images)} newly downloaded images verified")
        downloaded_images = verified_downloads

    # Merge and persist metadata
    if not meta:
        meta = {
            "version": 1,
            "created_at": _now_iso(),
            "topic_title": topic_title,
            "queries": topic_queries,
            "items": [],
        }

    # Ensure entries for all existing images too
    all_images = _discover_existing_images(output_dir)
    _ensure_metadata_for_existing_images(output_dir, topic_title, topic_queries, all_images)

    # Reload (it may have been written)
    meta = _load_metadata(output_dir) or meta
    existing_meta_items = list(meta.get("items") or [])

    # Add/merge new items (avoid duplicates by local_file)
    by_file2 = {str((it.get("local_file") or "")).strip(): it for it in existing_meta_items}
    for it in meta_items:
        lf = str(it.get("local_file") or "").strip()
        if not lf:
            continue
        by_file2[lf] = {**by_file2.get(lf, {}), **it}

    meta["updated_at"] = _now_iso()
    meta["topic_title"] = topic_title
    meta["queries"] = topic_queries
    meta["items"] = [by_file2[k] for k in sorted(by_file2.keys())]
    _write_metadata(output_dir, meta)

    # Return combined existing + downloads (sorted)
    final_images = _discover_existing_images(output_dir)
    return final_images[: original_num_images]
