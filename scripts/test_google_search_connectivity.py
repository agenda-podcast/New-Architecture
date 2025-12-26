#!/usr/bin/env python3
"""
Test Google Custom Search API connectivity.

This script tests the Google Custom Search API connection using a minimal request
to avoid unnecessary costs. It validates credentials and endpoint connectivity.
"""
import os
import sys
import logging
import urllib.request
from pathlib import Path
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Constants for image download testing
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
MIN_IMAGE_SIZE_BYTES = 1024  # Minimum valid image size (1KB)
IMAGE_DOWNLOAD_TIMEOUT = 10  # Timeout for image download test in seconds

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.error("google-api-python-client package not installed. Install with: pip install google-api-python-client")


def test_google_search_connectivity() -> Dict[str, Any]:
    """
    Test Google Custom Search API connectivity using a minimal request.
    
    Uses a simple query with minimal results to verify:
    - API credentials are valid
    - Search Engine ID is valid
    - Google Custom Search service is accessible
    
    Returns:
        Dictionary with test results including status, message, and details
    """
    result = {
        'service': 'Google Custom Search API',
        'status': 'FAILED',
        'message': '',
        'details': {}
    }
    
    if not GOOGLE_API_AVAILABLE:
        result['message'] = 'Google API client package not installed'
        result['details']['error'] = 'Missing dependency'
        return result
    
    # Get API credentials
    api_key = os.environ.get('GOOGLE_CUSTOM_SEARCH_API_KEY')
    search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
    
    if not api_key:
        result['message'] = 'GOOGLE_CUSTOM_SEARCH_API_KEY not found in environment variables'
        result['details']['error'] = 'Set GOOGLE_CUSTOM_SEARCH_API_KEY environment variable'
        result['details']['help'] = 'Get your API key from: https://console.cloud.google.com/apis/credentials'
        return result
    
    if not search_engine_id:
        result['message'] = 'GOOGLE_SEARCH_ENGINE_ID not found in environment variables'
        result['details']['error'] = 'Set GOOGLE_SEARCH_ENGINE_ID environment variable'
        result['details']['help'] = 'Create a search engine at: https://programmablesearchengine.google.com/'
        return result
    
    # Log credentials presence (without exposing actual values)
    logger.info(f"API key found (length: {len(api_key)} characters)")
    logger.info(f"Search Engine ID found: {search_engine_id}")
    
    try:
        # Build Google Custom Search API service
        logger.info("Building Google Custom Search API service...")
        service = build('customsearch', 'v1', developerKey=api_key)
        logger.info("✓ API service built successfully")
        
        # Test 1: Basic connectivity with minimal request
        logger.info("Test 1: Testing API connectivity with minimal search query...")
        
        response = service.cse().list(
            q='test',  # Simple query
            cx=search_engine_id,
            num=1  # Request only 1 result to minimize quota usage
        ).execute()
        
        # Extract response details
        search_info = response.get('searchInformation', {})
        total_results = search_info.get('totalResults', '0')
        search_time = search_info.get('searchTime', 'N/A')
        items = response.get('items', [])
        
        logger.info("✓ Basic search test completed successfully")
        logger.info(f"  Total results found: {total_results}")
        logger.info(f"  Search time: {search_time} seconds")
        logger.info(f"  Results returned: {len(items)}")
        
        if items:
            first_item = items[0]
            logger.info(f"  First result title: {first_item.get('title', 'N/A')[:60]}")
        
        # Test 2: Image search test (critical for podcast maker)
        logger.info("")
        logger.info("Test 2: Testing IMAGE search capability...")
        
        image_response = service.cse().list(
            q='nature landscape',  # Generic query likely to have images
            cx=search_engine_id,
            searchType='image',  # Request image results
            num=3,  # Request 3 images
            safe='active',
            imgSize='LARGE'  # Test the correct lowercase parameter
        ).execute()
        
        image_items = image_response.get('items', [])
        logger.info(f"✓ Image search completed: {len(image_items)} images found")
        
        # Test 3: Verify image URLs are downloadable and save to disk
        image_download_test = False
        if image_items:
            logger.info("")
            logger.info("Test 3: Testing image download capability and saving to disk...")
            
            # Try to download the first image to verify it's accessible
            test_image_url = image_items[0].get('link')
            if test_image_url:
                try:
                    logger.info(f"  Testing download from: {test_image_url[:60]}...")
                    req = urllib.request.Request(
                        test_image_url,
                        headers={
                            'User-Agent': USER_AGENT,
                            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
                        }
                    )
                    with urllib.request.urlopen(req, timeout=IMAGE_DOWNLOAD_TIMEOUT) as response:
                        image_data = response.read()
                    
                    if len(image_data) > MIN_IMAGE_SIZE_BYTES:
                        logger.info(f"✓ Successfully downloaded test image ({len(image_data) / 1024:.1f} KB)")
                        
                        # Save image to repository for manual verification
                        # Get repository root (parent of scripts directory)
                        script_dir = Path(__file__).parent
                        repo_root = script_dir.parent
                        test_data_dir = repo_root / 'test_data'
                        test_data_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Use a consistent filename (overwrite on each run) for easy manual verification
                        test_image_path = test_data_dir / 'test_google_search_image.jpg'
                        try:
                            with open(test_image_path, 'wb') as f:
                                f.write(image_data)
                                f.flush()
                                os.fsync(f.fileno())  # Force write to disk
                            logger.info(f"✓ Test image saved to: {test_image_path}")
                            logger.info(f"  Verify the image exists: ls -lh {test_image_path}")
                            image_download_test = True
                        except Exception as e:
                            logger.warning(f"⚠ Failed to save test image to disk: {e}")
                    else:
                        logger.warning(f"⚠ Image downloaded but seems too small ({len(image_data)} bytes)")
                except Exception as e:
                    logger.warning(f"⚠ Image download test failed: {e}")
            else:
                logger.warning("⚠ No image URL found in first result")
        
        result['status'] = 'SUCCESS'
        result['message'] = 'Google Custom Search API connection and image search successful'
        result['details'] = {
            'basic_search': 'PASSED',
            'basic_search_results': total_results,
            'search_time': f"{search_time} seconds",
            'image_search': 'PASSED',
            'images_found': len(image_items),
            'image_download_test': 'PASSED' if image_download_test else 'FAILED',
            'quota_cost': '2 API queries used (basic search + image search)',
            'note': 'Image download test uses no additional API quota (downloads from URLs)'
        }
        
        if not image_download_test:
            result['message'] += ' (Warning: Image download test failed)'
            logger.warning("")
            logger.warning("⚠ WARNING: Image search works but image download failed")
            logger.warning("  This may indicate network issues or image URL accessibility problems")
            
    except HttpError as e:
        result['message'] = f'API request failed: HTTP {e.resp.status}'
        result['details']['error'] = str(e)
        result['details']['error_type'] = 'HttpError'
        result['details']['status_code'] = e.resp.status
        logger.error(f"✗ API request failed: HTTP {e.resp.status}")
        
        # Provide specific guidance for common errors
        if e.resp.status == 403:
            logger.error("  → API key or quota issue")
            logger.error("  → Check that Custom Search API is enabled: https://console.cloud.google.com/apis/library/customsearch.googleapis.com")
            logger.error("  → Verify quota: https://console.cloud.google.com/apis/api/customsearch.googleapis.com/quotas")
            result['details']['help'] = 'Enable Custom Search API and check quota'
        elif e.resp.status == 400:
            logger.error("  → Invalid request - check search engine ID and query parameters")
            result['details']['help'] = 'Verify your search engine ID at: https://programmablesearchengine.google.com/'
        elif e.resp.status == 429:
            logger.error("  → Rate limit exceeded - too many requests")
            result['details']['help'] = 'Wait a moment before retrying'
        elif e.resp.status == 401:
            logger.error("  → Authentication failed - check API key")
            result['details']['help'] = 'Verify your API key at: https://console.cloud.google.com/apis/credentials'
            
    except Exception as e:
        result['message'] = f'API request failed: {str(e)}'
        result['details']['error'] = str(e)
        result['details']['error_type'] = type(e).__name__
        logger.error(f"✗ API request failed: {e}")
        
        # Provide generic guidance
        error_str = str(e).lower()
        if 'timeout' in error_str or 'connection' in error_str:
            logger.error("  → Network connectivity issue. Check your internet connection")
            result['details']['help'] = 'Check network connectivity'
    
    return result


def main():
    """Main entry point for Google Custom Search connectivity test."""
    logger.info("=" * 80)
    logger.info("GOOGLE CUSTOM SEARCH API CONNECTIVITY TEST")
    logger.info("=" * 80)
    logger.info("This test uses 1 query to verify API connectivity")
    logger.info("Cost: Free (uses 1 of 100 free daily queries)")
    logger.info("=" * 80)
    
    result = test_google_search_connectivity()
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"TEST RESULT: {result['status']}")
    logger.info("=" * 80)
    logger.info(f"Service: {result['service']}")
    logger.info(f"Status: {result['status']}")
    logger.info(f"Message: {result['message']}")
    
    if result['details']:
        logger.info("Details:")
        for key, value in result['details'].items():
            logger.info(f"  {key}: {value}")
    
    logger.info("=" * 80)
    
    # Return exit code based on status
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())
