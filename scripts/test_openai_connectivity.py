#!/usr/bin/env python3
"""
Test OpenAI API connectivity.

This script tests the OpenAI API connection using minimal tokens to avoid unnecessary costs.
It validates credentials and endpoint connectivity without generating full content.
"""
import os
import sys
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.error("openai package not installed. Install with: pip install openai")

def test_openai_connectivity() -> Dict[str, Any]:
    """
    Test OpenAI API connectivity using a minimal request.
    
    Uses the cheapest available model and minimal tokens to verify:
    - API credentials are valid
    - OpenAI service is accessible
    - Client can make successful requests
    
    Returns:
        Dictionary with test results including status, message, and details
    """
    result = {
        'service': 'OpenAI API',
        'status': 'FAILED',
        'message': '',
        'details': {}
    }
    
    if not OPENAI_AVAILABLE:
        result['message'] = 'OpenAI package not installed'
        result['details']['error'] = 'Missing dependency'
        return result
    
    # Get API key
    api_key = os.environ.get('GPT_KEY') or os.environ.get('OPENAI_API_KEY')
    
    if not api_key:
        result['message'] = 'API key not found in environment variables'
        result['details']['error'] = 'Set GPT_KEY or OPENAI_API_KEY environment variable'
        return result
    
    # Log API key presence (without exposing any part of the key)
    logger.info(f"API key found (length: {len(api_key)} characters)")
    
    try:
        # Initialize OpenAI client
        client = OpenAI(
            api_key=api_key,
            timeout=30.0,
            max_retries=0
        )
        logger.info("✓ OpenAI client initialized")
        
        # Test with minimal request using gpt-3.5-turbo (cheapest model)
        # This is a connectivity test, not a real generation
        logger.info("Testing API connectivity with minimal request...")
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Hi"}
            ],
            max_tokens=5,  # Minimal tokens to reduce cost
            temperature=0.0
        )
        
        # Extract response details
        if response.choices and len(response.choices) > 0:
            message_content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            has_usage = hasattr(response, 'usage')
            
            result['status'] = 'SUCCESS'
            result['message'] = 'OpenAI API connection successful'
            result['details'] = {
                'model': response.model,
                'response_preview': message_content[:50] if message_content else '',
                'finish_reason': finish_reason,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens if has_usage else 'N/A',
                    'completion_tokens': response.usage.completion_tokens if has_usage else 'N/A',
                    'total_tokens': response.usage.total_tokens if has_usage else 'N/A'
                }
            }
            
            logger.info("✓ API request completed successfully")
            logger.info(f"  Model: {response.model}")
            logger.info(f"  Response preview: {message_content[:50] if message_content else 'Empty'}")
            if has_usage:
                logger.info(f"  Tokens used: {response.usage.total_tokens} (prompt: {response.usage.prompt_tokens}, completion: {response.usage.completion_tokens})")
        else:
            result['message'] = 'Unexpected response format'
            result['details']['error'] = 'No choices in response'
            
    except Exception as e:
        result['message'] = f'API request failed: {str(e)}'
        result['details']['error'] = str(e)
        result['details']['error_type'] = type(e).__name__
        logger.error(f"✗ API request failed: {e}")
        
        # Provide specific guidance for common errors
        error_str = str(e).lower()
        if 'api key' in error_str or 'authentication' in error_str or '401' in error_str:
            logger.error("  → Check that your API key is correct and active")
            logger.error("  → Get your API key from: https://platform.openai.com/api-keys")
        elif 'rate limit' in error_str or '429' in error_str:
            logger.error("  → Rate limit exceeded. Wait a moment and try again")
        elif 'timeout' in error_str or 'connection' in error_str:
            logger.error("  → Network connectivity issue. Check your internet connection")
        elif 'model' in error_str:
            logger.error("  → Model access issue. Ensure you have access to the specified model")
    
    return result


def main():
    """Main entry point for OpenAI connectivity test."""
    logger.info("=" * 80)
    logger.info("OPENAI API CONNECTIVITY TEST")
    logger.info("=" * 80)
    logger.info("This test uses minimal tokens to verify API connectivity")
    logger.info("Cost: ~$0.0001 (1 request with ~10 tokens using gpt-3.5-turbo)")
    logger.info("=" * 80)
    
    result = test_openai_connectivity()
    
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
            if isinstance(value, dict):
                logger.info(f"  {key}:")
                for sub_key, sub_value in value.items():
                    logger.info(f"    {sub_key}: {sub_value}")
            else:
                logger.info(f"  {key}: {value}")
    
    logger.info("=" * 80)
    
    # Return exit code based on status
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())
