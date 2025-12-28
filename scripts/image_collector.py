#!/usr/bin/env python3
"""
Image collection using Google Custom Search API.

This module collects images related to a topic using Google Custom Search API.
Images are downloaded and saved to the topic's images directory for video generation.

Usage:
    GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID must be set as environment variables.
"""
import os
import logging
import urllib.request
import urllib.error
import json
from pathlib import Path
from datetime import date
from typing import List, Dict, Any, Optional, Union

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
DEFAULT_NUM_IMAGES = 50  # Number of images to collect per topic
MAX_NUM_IMAGES = 50  # Maximum images to collect
IMAGE_SEARCH_TIMEOUT = 10  # Timeout for image downloads in seconds

# Metadata sidecar saved next to downloaded images.
IMAGES_METADATA_FILENAME = "images_metadata.json"

# Import allowed extensions and search limits from global config
from global_config import (
    ALLOWED_IMAGE_EXTENSIONS,
    GOOGLE_SEARCH_DAILY_LIMIT,
    GOOGLE_SEARCH_MAX_RESULTS_PER_QUERY,
    GOOGLE_SEARCH_RESULTS_PER_PAGE
)

# Daily usage tracking file
USAGE_TRACKING_FILE = Path.home() / '.podcast-maker' / 'google_search_usage.json'


def get_daily_usage() -> Dict[str, Union[str, int]]:
    """
    Get the current daily usage count from the tracking file.
    
    Returns:
        Dictionary with 'date' (YYYY-MM-DD string) and 'count' (int)
    """
    today = date.today().isoformat()
    
    # Create directory if it doesn't exist
    USAGE_TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing usage data
    if USAGE_TRACKING_FILE.exists():
        try:
            with open(USAGE_TRACKING_FILE, 'r') as f:
                data = json.load(f)
                # Reset count if it's a new day
                if data.get('date') != today:
                    return {'date': today, 'count': 0}
                return data
        except Exception as e:
            logger.warning(f"Error reading usage tracking file: {e}")
            return {'date': today, 'count': 0}
    
    return {'date': today, 'count': 0}


def update_daily_usage(results_used: int) -> None:
    """
    Update the daily usage count in the tracking file.
    
    Args:
        results_used: Number of results used in the last API call
    """
    usage = get_daily_usage()
    usage['count'] += results_used
    
    # Write updated usage data
    try:
        USAGE_TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_TRACKING_FILE, 'w') as f:
            json.dump(usage, f)
    except Exception as e:
        logger.warning(f"Error updating usage tracking file: {e}")


def check_daily_limit(requested_results: int) -> tuple[bool, int]:
    """
    Check if the requested number of results would exceed the daily limit.
    
    Args:
        requested_results: Number of results requested
        
    Returns:
        Tuple of (can_proceed, available_results)
        - can_proceed: True if we can make the request
        - available_results: Number of results available within the daily limit
    """
    usage = get_daily_usage()
    used = usage['count']
    available = max(0, GOOGLE_SEARCH_DAILY_LIMIT - used)
    
    if available == 0:
        return False, 0
    
    # Return the minimum of requested and available
    return True, min(requested_results, available)


def _clean_google_visible_title(raw_title: str, display_link: str | None = None) -> str:
    """Clean Google-visible titles so we can use them as on-screen overlays.

    Goal: remove hostnames / source suffixes like " - example.com" or " | Example".
    """
    t = (raw_title or "").strip()
    if not t:
        return ""

    # Common suffix separators.
    for sep in (" - ", " | ", " — "):
        if sep in t:
            # If the last chunk looks like a host, drop it.
            left, right = t.rsplit(sep, 1)
            r = right.strip().lower()
            if "." in r or "www" in r or (display_link and display_link.lower() in r):
                t = left.strip()
                break

    # Remove explicit host if still present at end.
    if display_link:
        dl = display_link.strip()
        for sep in (" - ", " | "):
            suffix = f"{sep}{dl}".lower()
            if t.lower().endswith(suffix):
                t = t[: -len(suffix)].strip()

    return t


def _load_images_metadata(images_dir: Path) -> Dict[str, Any]:
    p = images_dir / IMAGES_METADATA_FILENAME
    if not p.exists():
        return {"version": 1, "images": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"version": 1, "images": []}
        if "images" not in data or not isinstance(data.get("images"), list):
            data["images"] = []
        data.setdefault("version", 1)
        return data
    except Exception:
        return {"version": 1, "images": []}


def _write_images_metadata(images_dir: Path, data: Dict[str, Any]) -> None:
    p = images_dir / IMAGES_METADATA_FILENAME
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to write images metadata: {e}")


def collect_images_for_topic(
    topic_title: str,
    topic_queries: List[str],
    output_dir: Path,
    num_images: int = DEFAULT_NUM_IMAGES,
    api_key: Optional[str] = None,
    search_engine_id: Optional[str] = None
) -> List[Path]:
    """
    Collect images for a topic using Google Custom Search API.
    
    This function:
    1. Validates API credentials before making requests
    2. Queries Google Custom Search API for images related to the topic
    3. Downloads the images to the output directory with retry logic
    4. Returns list of downloaded image paths
    
    Best Practices Implemented:
    - Validates credentials before making API calls
    - Uses specific image search parameters (safe search, large images)
    - Handles API errors gracefully
    - Implements retry logic for failed downloads
    - Removes duplicate URLs
    - Validates image URLs before downloading
    
    Args:
        topic_title: Title of the topic
        topic_queries: List of search queries for the topic
        output_dir: Directory to save images (should be topic's images subdirectory)
        num_images: Number of images to collect (default: 10, max: 50)
        api_key: Google Custom Search API key (or use GOOGLE_CUSTOM_SEARCH_API_KEY env var)
        search_engine_id: Google Search Engine ID (or use GOOGLE_SEARCH_ENGINE_ID env var)
        
    Returns:
        List of paths to downloaded images
        
    Raises:
        ValueError: If API credentials are not provided or invalid
        ImportError: If google-api-python-client is not installed
    """
    # Limit num_images to max
    if num_images > MAX_NUM_IMAGES:
        logger.warning(f"Requested {num_images} images, limiting to max: {MAX_NUM_IMAGES}")
        num_images = MAX_NUM_IMAGES
    
    # Store original target for later reporting
    original_num_images = num_images
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if images already exist BEFORE checking API availability
    # This allows the function to work with existing images even if API is not configured
    existing_images = []
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        # Use glob with filter to ensure extension is at the end of filename
        existing_images.extend([p for p in output_dir.glob(f'*{ext}') if p.suffix == ext])
    
    # If we have enough images, return them without making API calls
    if len(existing_images) >= num_images:
        logger.info("="*80)
        logger.info(f"SUFFICIENT IMAGES ALREADY EXIST")
        logger.info("="*80)
        logger.info(f"Found {len(existing_images)} existing images in {output_dir}")
        logger.info(f"Required: {num_images} images")
        logger.info(f"Skipping Google Custom Search API calls")
        logger.info("="*80)
        # Ensure metadata sidecar exists even when we skip API calls.
        images_dir = output_dir
        meta = _load_images_metadata(images_dir)
        known = {str(it.get("filename")) for it in meta.get("images", []) if isinstance(it, dict)}
        for p in sorted(existing_images)[:num_images]:
            if p.name not in known:
                meta["images"].append(
                    {
                        "filename": p.name,
                        "title": "",
                        "title_clean": "",
                        "url": "",
                        "displayLink": "",
                        "query": "",
                    }
                )
        _write_images_metadata(images_dir, meta)
        return sorted(existing_images)[:num_images]
    
    # If we have some images but not enough, calculate how many more we need
    images_needed = num_images - len(existing_images)
    if len(existing_images) > 0:
        logger.info("="*80)
        logger.info(f"PARTIAL IMAGES FOUND")
        logger.info("="*80)
        logger.info(f"Existing images: {len(existing_images)}")
        logger.info(f"Required images: {num_images}")
        logger.info(f"Additional images needed: {images_needed}")
        logger.info(f"Will request only {images_needed} new images from API")
        logger.info("="*80)
        # Update num_images to only request what we need
        num_images = images_needed
    
    logger.info("="*80)
    logger.info(f"COLLECTING IMAGES FOR: {topic_title}")
    logger.info("="*80)
    logger.info(f"Target: {num_images} images")
    logger.info(f"Queries: {topic_queries}")
    logger.info(f"Output: {output_dir}")
    logger.info("="*80)
    
    # Now check if Google API is available (only needed if we need to download images)
    if not GOOGLE_API_AVAILABLE:
        raise ImportError(
            "google-api-python-client package is required for image collection. "
            "Install with: pip install google-api-python-client"
        )
    
    # Get API credentials
    api_key = api_key or os.environ.get('GOOGLE_CUSTOM_SEARCH_API_KEY')
    search_engine_id = search_engine_id or os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
    
    # Validate credentials
    if not api_key:
        raise ValueError(
            "Google Custom Search API key not found. "
            "Please set GOOGLE_CUSTOM_SEARCH_API_KEY environment variable. "
            "Get your API key from: https://console.cloud.google.com/apis/credentials"
        )
    
    if not search_engine_id:
        raise ValueError(
            "Google Search Engine ID not found. "
            "Please set GOOGLE_SEARCH_ENGINE_ID environment variable. "
            "Create a search engine at: https://programmablesearchengine.google.com/"
        )
    
    # Validate API key format (basic check)
    if not api_key.startswith('AIza'):
        logger.warning(f"API key format looks unusual. Expected format: AIza...")
    
    # Validate search engine ID format (basic check)
    if ':' not in search_engine_id:
        logger.warning(f"Search Engine ID format looks unusual. Expected format: xxxxx:xxxxx (got: {search_engine_id})")
    
    # Build Google Custom Search API service
    try:
        service = build('customsearch', 'v1', developerKey=api_key)
        logger.info("✓ Successfully connected to Google Custom Search API")
    except Exception as e:
        logger.error(f"Failed to build Google Custom Search API service: {e}")
        logger.error("Possible causes:")
        logger.error("  1. Invalid API key")
        logger.error("  2. API not enabled in Google Cloud Console")
        logger.error("  3. Network connectivity issues")
        logger.error(f"Verify your setup at: https://console.cloud.google.com/apis/library/customsearch.googleapis.com")
        raise
    
    # Check daily limit before starting
    usage = get_daily_usage()
    logger.info(f"Daily usage: {usage['count']}/{GOOGLE_SEARCH_DAILY_LIMIT} results used today")
    
    can_proceed, available_results = check_daily_limit(num_images)
    if not can_proceed:
        logger.error("="*80)
        logger.error("DAILY LIMIT REACHED")
        logger.error("="*80)
        logger.error(f"Daily limit of {GOOGLE_SEARCH_DAILY_LIMIT} results has been reached.")
        logger.error(f"Current usage: {usage['count']} results")
        logger.error("The limit will reset at midnight.")
        logger.error("="*80)
        return []
    
    if available_results < num_images:
        logger.warning(f"Only {available_results} results available within daily limit (requested: {num_images})")
        num_images = available_results
    
    # Collect image metadata from search results with pagination
    # We keep Google-visible titles for later burned overlays.
    image_items: List[Dict[str, Any]] = []
    images_per_query = max(1, num_images // len(topic_queries)) if topic_queries else num_images
    total_api_results = 0  # Track total API results for daily limit
    
    for query in topic_queries[:5]:  # Limit to first 5 queries
        logger.info(f"Searching for images: '{query}'")
        
        # Calculate how many results we need for this query
        query_target = min(images_per_query, GOOGLE_SEARCH_MAX_RESULTS_PER_QUERY)
        query_results: List[Dict[str, Any]] = []
        start_index = 1  # Start at 1 (Google API convention)
        
        # Paginate through results until we have enough or reach the limit
        while len(query_results) < query_target and start_index <= 91:  # Max start is 91 (to get results 91-100)
            # Check if we still have quota available
            can_proceed, remaining = check_daily_limit(GOOGLE_SEARCH_RESULTS_PER_PAGE)
            if not can_proceed:
                logger.warning(f"  Daily limit reached during pagination for query '{query}'")
                break
            
            try:
                # Search for images using Google Custom Search API with pagination
                result = service.cse().list(
                    q=query,
                    cx=search_engine_id,
                    searchType='image',
                    imgType='photo',  # Only photos (excludes clipart, line drawings, etc.)
                    num=GOOGLE_SEARCH_RESULTS_PER_PAGE,  # Always request 10 (API max)
                    start=start_index,  # Pagination parameter
                    safe='active',  # Safe search
                    imgSize='LARGE'  # Prefer large images (uppercase required by API)
                ).execute()
                
                # Extract image URLs from this page
                page_items = result.get('items', [])
                if page_items:
                    for item in page_items:
                        link = item.get('link')
                        if not link:
                            continue
                        query_results.append(
                            {
                                "url": link,
                                "title": item.get("title", ""),
                                "displayLink": item.get("displayLink", ""),
                                "snippet": item.get("snippet", ""),
                                "contextLink": (item.get("image") or {}).get("contextLink", ""),
                                "query": query,
                            }
                        )
                        logger.info(f"  Found image {len(query_results)}: {str(item.get('title', 'No title'))[:50]}")
                    
                    # Update daily usage counter
                    total_api_results += len(page_items)
                    update_daily_usage(len(page_items))
                    
                    logger.info(f"  Page results: {len(page_items)} images (start={start_index})")
                else:
                    logger.info(f"  No more results available for this query")
                    break
                
                # Check if we have enough results for this query
                if len(query_results) >= query_target:
                    logger.info(f"  Collected {len(query_results)} images for query (target: {query_target})")
                    break
                
                # Get next page start index from API response
                next_page = result.get('queries', {}).get('nextPage', [])
                if next_page and 'startIndex' in next_page[0]:
                    start_index = next_page[0]['startIndex']
                    logger.info(f"  Moving to next page (start={start_index})")
                else:
                    logger.info(f"  No more pages available")
                    break
                
            except HttpError as e:
                logger.error(f"Google API error for query '{query}': {e}")
                if e.resp.status == 403:
                    logger.error("  ✗ API key or quota issue - check your Google Cloud Console")
                    logger.error("    Verify API is enabled: https://console.cloud.google.com/apis/library/customsearch.googleapis.com")
                    logger.error("    Check quota: https://console.cloud.google.com/apis/api/customsearch.googleapis.com/quotas")
                elif e.resp.status == 400:
                    logger.error("  ✗ Invalid request - check search engine ID and query parameters")
                elif e.resp.status == 429:
                    logger.error("  ✗ Rate limit exceeded - too many requests")
                break
            except Exception as e:
                logger.error(f"Error searching for images with query '{query}': {e}")
                import traceback
                logger.debug(traceback.format_exc())
                break
        
        # Add this query's results to the overall collection
        image_items.extend(query_results)
        logger.info(f"  Total images collected for query '{query}': {len(query_results)}")
        
        # Stop if we have enough images overall
        if len(image_items) >= num_images:
            logger.info(f"Collected sufficient images: {len(image_items)}/{num_images}")
            break
    
    logger.info(f"Total API results used: {total_api_results}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_items: List[Dict[str, Any]] = []
    for it in image_items:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url", ""))
        if not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        unique_items.append(it)
    
    logger.info(f"Total unique image URLs collected: {len(unique_items)}")
    
    if not unique_items:
        logger.warning("="*80)
        logger.warning("NO IMAGES FOUND")
        logger.warning("="*80)
        logger.warning("Possible causes:")
        logger.warning("  1. Search queries too specific or no matching images")
        logger.warning("  2. Network issues or API rate limiting")
        logger.warning("  3. Search engine configuration issues")
        logger.warning(f"Troubleshooting:")
        logger.warning(f"  - Try broader search terms")
        logger.warning(f"  - Verify search engine at: https://programmablesearchengine.google.com/")
        logger.warning(f"  - Check API quota at: https://console.cloud.google.com/apis/dashboard")
        logger.warning("="*80)
        return []
    
    # Download images
    # Start numbering from the count of existing images to avoid conflicts
    start_index = len(existing_images)
    downloaded_images = []
    # Load existing metadata so we can append to it.
    meta = _load_images_metadata(output_dir)
    known_filenames = {str(it.get("filename")) for it in meta.get("images", []) if isinstance(it, dict)}

    for i, it in enumerate(unique_items[:num_images]):
        url = str(it.get("url", ""))
        raw_title = str(it.get("title", ""))
        display_link = str(it.get("displayLink", ""))
        cleaned_title = _clean_google_visible_title(raw_title, display_link=display_link)
        # Validate extension before download
        url_lower = url.lower()
        ext = '.jpg'  # Default
        is_allowed = False
        
        for allowed_ext in ALLOWED_IMAGE_EXTENSIONS:
            if url_lower.endswith(allowed_ext):
                ext = allowed_ext
                is_allowed = True
                break
        
        # Skip if extension is not in allowed list
        if not is_allowed:
            # Check if URL might still be an image (no extension in URL)
            # Allow if URL doesn't have a clear non-image extension
            has_non_image_ext = url_lower.endswith(('.html', '.htm', '.php', '.asp', '.txt', '.pdf'))
            if has_non_image_ext:
                logger.warning(f"    ✗ Skipping URL with unsupported extension: {url[:60]}")
                continue
        
        # Use start_index + i to avoid conflicts with existing images
        image_path = output_dir / f'image_{start_index + i:03d}{ext}'
        
        # Skip if already exists
        if image_path.exists():
            logger.info(f"  Image {start_index + i + 1}/{original_num_images} already exists: {image_path.name}")
            downloaded_images.append(image_path)
            continue
        
        # Validate URL before downloading
        if not url.startswith(('http://', 'https://')):
            logger.warning(f"    ✗ Skipping invalid URL: {url[:60]}")
            continue
        
        # Download image with retry logic
        max_retries = 2
        for retry in range(max_retries + 1):
            try:
                if retry > 0:
                    logger.info(f"  Retry {retry}/{max_retries} for image {start_index + i + 1}/{original_num_images}...")
                else:
                    logger.info(f"  Downloading image {start_index + i + 1}/{original_num_images}: {url[:60]}...")
                
                # Set headers to mimic a browser request
                req = urllib.request.Request(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
                    }
                )
                
                with urllib.request.urlopen(req, timeout=IMAGE_SEARCH_TIMEOUT) as response:
                    image_data = response.read()
                    
                # Validate image data
                if len(image_data) < 1024:  # Less than 1KB is suspicious
                    logger.warning(f"    ✗ Image too small ({len(image_data)} bytes), skipping")
                    break
                
                # Save image
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                    os.fsync(f.fileno())  # Ensure OS writes data to disk (includes flush)
                
                downloaded_images.append(image_path)
                logger.info(f"    ✓ Saved: {image_path.name} ({len(image_data) / 1024:.1f} KB)")

                # Persist Google-visible title metadata for later video overlays.
                try:
                    if image_path.name not in known_filenames:
                        meta["images"].append(
                            {
                                "filename": image_path.name,
                                "url": url,
                                "title": raw_title,
                                "title_clean": cleaned_title,
                                "displayLink": display_link,
                                "contextLink": str(it.get("contextLink", "")),
                                "query": str(it.get("query", "")),
                            }
                        )
                        known_filenames.add(image_path.name)
                except Exception:
                    pass

                break  # Success - exit retry loop
                
            except urllib.error.HTTPError as e:
                if retry < max_retries and e.code in [429, 503, 504]:  # Rate limit or server errors
                    logger.warning(f"    ⚠ HTTP {e.code} - retrying...")
                    import time
                    time.sleep(1)  # Brief delay before retry
                    continue
                logger.warning(f"    ✗ HTTP error downloading image: {e.code} {e.reason}")
                break  # Exit retry loop
            except urllib.error.URLError as e:
                if retry < max_retries:
                    logger.warning(f"    ⚠ Network error - retrying...")
                    import time
                    time.sleep(1)
                    continue
                logger.warning(f"    ✗ URL error downloading image: {e.reason}")
                break
            except Exception as e:
                logger.warning(f"    ✗ Error downloading image: {e}")
                break
    
    logger.info("="*80)
    logger.info(f"IMAGE COLLECTION COMPLETE: {len(downloaded_images)}/{num_images} images")
    
    # Verify all downloaded images exist and are readable
    logger.info("Verifying downloaded images...")
    verified_images = []
    for img_path in downloaded_images:
        if img_path.exists():
            try:
                # Verify file is readable and has content
                file_size = img_path.stat().st_size
                if file_size > 0:
                    verified_images.append(img_path)
                    logger.debug(f"  ✓ Verified: {img_path.name} ({file_size} bytes)")
                else:
                    logger.warning(f"  ✗ File is empty: {img_path.name}")
            except Exception as e:
                logger.warning(f"  ✗ Cannot read file {img_path.name}: {e}")
        else:
            logger.warning(f"  ✗ File does not exist: {img_path.name}")
    
    if len(verified_images) != len(downloaded_images):
        logger.warning(f"Only {len(verified_images)}/{len(downloaded_images)} images verified successfully")
        downloaded_images = verified_images
    else:
        logger.info(f"✓ All {len(verified_images)} images verified successfully")
    
    # Combine existing images with newly downloaded images
    all_images = list(existing_images) + downloaded_images
    total_images = len(all_images)

    # Ensure metadata is complete and written to disk.
    try:
        known_filenames = {str(it.get("filename")) for it in meta.get("images", []) if isinstance(it, dict)}
        for p in sorted(all_images)[:original_num_images]:
            if p.name not in known_filenames:
                meta["images"].append(
                    {
                        "filename": p.name,
                        "title": "",
                        "title_clean": "",
                        "url": "",
                        "displayLink": "",
                        "query": "",
                    }
                )
                known_filenames.add(p.name)
        meta.setdefault("topic_title", topic_title)
        meta.setdefault("generated_on", date.today().isoformat())
        _write_images_metadata(output_dir, meta)
    except Exception:
        pass
    
    # Provide feedback and recommendations
    if len(downloaded_images) == 0 and len(existing_images) == 0:
        logger.error("NO IMAGES DOWNLOADED")
        logger.error("Recommendations:")
        logger.error("  1. Verify API credentials are correct")
        logger.error("  2. Check API quota and billing status")
        logger.error("  3. Try different search queries")
        logger.error("  4. Test API manually: https://developers.google.com/custom-search/v1/using_rest")
    elif total_images < original_num_images:
        logger.warning(f"Only {total_images}/{original_num_images} images available")
        if len(existing_images) > 0:
            logger.info(f"  Existing images: {len(existing_images)}")
        if len(downloaded_images) > 0:
            logger.info(f"  Newly downloaded: {len(downloaded_images)}")
        # If we attempted downloads but didn't get all we needed, show recommendations
        images_attempted = original_num_images - len(existing_images)
        if len(downloaded_images) < images_attempted:
            logger.warning("To improve results:")
            logger.warning("  - Use more varied search queries")
            logger.warning("  - Try broader search terms")
            logger.warning("  - Check if images are publicly accessible")
    else:
        logger.info(f"✓ SUCCESS: All {original_num_images} images available")
        if len(existing_images) > 0:
            logger.info(f"  Existing images: {len(existing_images)}")
        if len(downloaded_images) > 0:
            logger.info(f"  Newly downloaded: {len(downloaded_images)}")
    
    logger.info("="*80)
    
    return sorted(all_images)[:original_num_images]


def main():
    """Command-line interface for image collection."""
    import argparse
    from config import load_topic_config, get_output_dir
    from global_config import IMAGES_SUBDIR
    
    parser = argparse.ArgumentParser(description='Collect images for a topic using Google Custom Search API')
    parser.add_argument('--topic', required=True, help='Topic ID (e.g., topic-01)')
    parser.add_argument('--num-images', type=int, default=DEFAULT_NUM_IMAGES, help=f'Number of images to collect (default: {DEFAULT_NUM_IMAGES})')
    args = parser.parse_args()
    
    # Load topic configuration
    config = load_topic_config(args.topic)
    output_dir = get_output_dir(args.topic)
    images_dir = output_dir / IMAGES_SUBDIR
    
    # Collect images
    try:
        downloaded_images = collect_images_for_topic(
            topic_title=config['title'],
            topic_queries=config.get('queries', [config['title']]),
            output_dir=images_dir,
            num_images=args.num_images
        )
        
        print(f"\n✓ Successfully collected {len(downloaded_images)} images")
        print(f"  Images saved to: {images_dir}")
        
    except Exception as e:
        print(f"\n✗ Error collecting images: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
