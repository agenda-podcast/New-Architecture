#!/usr/bin/env python3
"""
Test Google Cloud Text-to-Speech API connectivity.

This script tests the Google Cloud TTS API connection using a minimal request
to avoid unnecessary costs. It validates credentials and endpoint connectivity.
"""
import os
import sys
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from google.cloud import texttospeech
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False
    logger.error("google-cloud-texttospeech package not installed. Install with: pip install google-cloud-texttospeech")


def test_google_tts_connectivity() -> Dict[str, Any]:
    """
    Test Google Cloud Text-to-Speech API connectivity using a minimal request.
    
    Uses list_voices() method which is free and doesn't count against quota.
    This verifies:
    - API credentials are valid (via Application Default Credentials or service account)
    - Google Cloud TTS service is accessible
    - Client can make successful requests
    
    Note: list_voices() is a metadata API call that doesn't incur charges.
    
    Note: Google Cloud TTS uses Application Default Credentials (ADC) or service account
    credentials. The GOOGLE_API_KEY environment variable is checked for documentation
    compatibility, but the actual authentication uses ADC from the environment.
    
    Returns:
        Dictionary with test results including status, message, and details
    """
    result = {
        'service': 'Google Cloud Text-to-Speech API',
        'status': 'FAILED',
        'message': '',
        'details': {}
    }
    
    if not GOOGLE_TTS_AVAILABLE:
        result['message'] = 'Google Cloud TTS package not installed'
        result['details']['error'] = 'Missing dependency'
        return result
    
    # IMPORTANT: Google Cloud TTS uses Application Default Credentials (ADC), not API keys
    # The GOOGLE_API_KEY check below exists ONLY for project documentation compatibility
    # This environment variable is NOT used by the Google Cloud TTS client library
    # Authentication happens through ADC (see logging below for details)
    api_key = os.environ.get('GOOGLE_API_KEY')
    
    if api_key:
        logger.info("GOOGLE_API_KEY environment variable is set (for documentation reference)")
        logger.info("IMPORTANT: Google Cloud TTS will use ADC, not this API key")
    else:
        logger.info("GOOGLE_API_KEY not set")
        logger.info("This is OK - Google Cloud TTS uses Application Default Credentials (ADC)")
    
    logger.info("Attempting to authenticate using Application Default Credentials...")
    logger.info("ADC looks for credentials in this order:")
    logger.info("  1. GOOGLE_APPLICATION_CREDENTIALS environment variable")
    logger.info("  2. User credentials from gcloud CLI")
    logger.info("  3. Compute Engine/GKE metadata server")
    
    try:
        # Initialize Google Cloud TTS client
        # This uses Application Default Credentials (ADC) which looks for credentials in:
        # 1. GOOGLE_APPLICATION_CREDENTIALS environment variable (service account JSON)
        # 2. User credentials from gcloud CLI
        # 3. Compute Engine/GKE metadata server
        logger.info("Initializing Google Cloud TTS client (using ADC)...")
        client = texttospeech.TextToSpeechClient()
        logger.info("✓ TTS client initialized")
        
        # List available voices - this is a FREE metadata operation
        # It doesn't count against your synthesis quota and doesn't incur charges
        logger.info("Testing API connectivity by listing available voices...")
        logger.info("Note: list_voices() is a free metadata API call")
        
        request = texttospeech.ListVoicesRequest()
        response = client.list_voices(request=request)
        
        # Extract response details
        voices = response.voices
        
        # Count voices by language
        language_counts = {}
        for voice in voices:
            for language_code in voice.language_codes:
                language_counts[language_code] = language_counts.get(language_code, 0) + 1
        
        # Get sample of English voices
        en_voices = [v for v in voices if any(lc.startswith('en') for lc in v.language_codes)]
        
        result['status'] = 'SUCCESS'
        result['message'] = 'Google Cloud TTS API connection successful'
        result['details'] = {
            'total_voices': len(voices),
            'languages': len(language_counts),
            'english_voices': len(en_voices),
            'quota_cost': '0 (list_voices is free)',
            'sample_languages': ', '.join(sorted(language_counts.keys())[:10])
        }
        
        logger.info("✓ API request completed successfully")
        logger.info(f"  Total voices available: {len(voices)}")
        logger.info(f"  Languages available: {len(language_counts)}")
        logger.info(f"  English voices: {len(en_voices)}")
        
        # Show sample of English voices
        if en_voices:
            sample_voice = en_voices[0]
            logger.info(f"  Sample voice: {sample_voice.name} ({sample_voice.ssml_gender})")
            result['details']['sample_voice'] = f"{sample_voice.name} ({sample_voice.ssml_gender})"
            
    except Exception as e:
        result['message'] = f'API request failed: {str(e)}'
        result['details']['error'] = str(e)
        result['details']['error_type'] = type(e).__name__
        logger.error(f"✗ API request failed: {e}")
        
        # Provide specific guidance for common errors
        error_str = str(e).lower()
        if 'api key' in error_str or 'authentication' in error_str or '401' in error_str or '403' in error_str:
            logger.error("  → Check that your API key is correct and has proper permissions")
            logger.error("  → Ensure Cloud Text-to-Speech API is enabled: https://console.cloud.google.com/apis/library/texttospeech.googleapis.com")
            result['details']['help'] = 'Check API key and enable Cloud Text-to-Speech API'
        elif 'quota' in error_str or '429' in error_str:
            logger.error("  → Quota exceeded or rate limit hit")
            result['details']['help'] = 'Check quota at: https://console.cloud.google.com/apis/api/texttospeech.googleapis.com/quotas'
        elif 'timeout' in error_str or 'connection' in error_str:
            logger.error("  → Network connectivity issue. Check your internet connection")
            result['details']['help'] = 'Check network connectivity'
        else:
            logger.error("  → Unknown error. Check Google Cloud Console for details")
            result['details']['help'] = 'Check Google Cloud Console: https://console.cloud.google.com/'
    
    return result


def main():
    """Main entry point for Google Cloud TTS connectivity test."""
    logger.info("=" * 80)
    logger.info("GOOGLE CLOUD TEXT-TO-SPEECH API CONNECTIVITY TEST")
    logger.info("=" * 80)
    logger.info("This test uses list_voices() to verify API connectivity")
    logger.info("Cost: Free (metadata API call, no quota usage)")
    logger.info("=" * 80)
    
    result = test_google_tts_connectivity()
    
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
