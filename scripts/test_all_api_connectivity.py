#!/usr/bin/env python3
"""
Test all API connectivity.

This script runs all API connectivity tests and reports the results.
It can be used to verify that all API credentials are correctly configured.
"""
import sys
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Import individual test modules
try:
    from test_openai_connectivity import test_openai_connectivity
    from test_google_search_connectivity import test_google_search_connectivity
    from test_google_tts_connectivity import test_google_tts_connectivity
except ImportError as e:
    logger.error(f"Failed to import test modules: {e}")
    logger.error("Ensure all test scripts are in the same directory")
    sys.exit(1)


def run_all_tests() -> List[Dict[str, Any]]:
    """
    Run all API connectivity tests.
    
    Returns:
        List of test results from each API test
    """
    results = []
    
    # Test 1: OpenAI API
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 1/3: OpenAI API")
    logger.info("=" * 80)
    try:
        result = test_openai_connectivity()
        results.append(result)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results.append({
            'service': 'OpenAI API',
            'status': 'FAILED',
            'message': f'Test exception: {str(e)}',
            'details': {'error': str(e)}
        })
    
    # Test 2: Google Custom Search API
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 2/3: Google Custom Search API")
    logger.info("=" * 80)
    try:
        result = test_google_search_connectivity()
        results.append(result)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results.append({
            'service': 'Google Custom Search API',
            'status': 'FAILED',
            'message': f'Test exception: {str(e)}',
            'details': {'error': str(e)}
        })
    
    # Test 3: Google Cloud TTS API
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 3/3: Google Cloud Text-to-Speech API")
    logger.info("=" * 80)
    try:
        result = test_google_tts_connectivity()
        results.append(result)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results.append({
            'service': 'Google Cloud Text-to-Speech API',
            'status': 'FAILED',
            'message': f'Test exception: {str(e)}',
            'details': {'error': str(e)}
        })
    
    return results


def print_summary(results: List[Dict[str, Any]]) -> None:
    """
    Print a summary of all test results.
    
    Args:
        results: List of test results from each API test
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("API CONNECTIVITY TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = 0
    failed = 0
    
    for result in results:
        status_symbol = "✓" if result['status'] == 'SUCCESS' else "✗"
        logger.info(f"{status_symbol} {result['service']}: {result['status']}")
        logger.info(f"  Message: {result['message']}")
        
        if result['status'] == 'SUCCESS':
            passed += 1
        else:
            failed += 1
            # Show help if available
            if 'details' in result and 'help' in result['details']:
                logger.info(f"  Help: {result['details']['help']}")
    
    logger.info("")
    logger.info("-" * 80)
    logger.info(f"TOTAL: {len(results)} tests")
    logger.info(f"PASSED: {passed}")
    logger.info(f"FAILED: {failed}")
    logger.info("-" * 80)
    
    if failed == 0:
        logger.info("✓ All API connectivity tests passed!")
        logger.info("✓ All credentials are properly configured")
    else:
        logger.error(f"✗ {failed} API connectivity test(s) failed")
        logger.error("✗ Please check the error messages above and configure the required credentials")
    
    logger.info("=" * 80)


def main():
    """Main entry point for all API connectivity tests."""
    logger.info("=" * 80)
    logger.info("API CONNECTIVITY TEST SUITE")
    logger.info("=" * 80)
    logger.info("This suite tests all API connections used by the podcast maker")
    logger.info("Each test uses minimal resources to verify connectivity only")
    logger.info("")
    logger.info("APIs being tested:")
    logger.info("  1. OpenAI API (for script generation)")
    logger.info("  2. Google Custom Search API (for image collection)")
    logger.info("  3. Google Cloud Text-to-Speech API (for premium TTS)")
    logger.info("")
    logger.info("Total estimated cost: < $0.001 (less than one tenth of a cent)")
    logger.info("=" * 80)
    
    # Run all tests
    results = run_all_tests()
    
    # Print summary
    print_summary(results)
    
    # Return exit code based on results
    failed_count = sum(1 for r in results if r['status'] != 'SUCCESS')
    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
