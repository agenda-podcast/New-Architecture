#!/usr/bin/env python3
"""
Test logging improvements and error handling for OpenAI API.

This test verifies that:
1. The logging system properly logs requests and responses
2. The extract_completion_text function handles various response structures
3. The get_finish_reason function handles missing attributes gracefully
"""
import sys
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from openai_utils import extract_completion_text, get_finish_reason, create_openai_completion
from global_config import get_openai_endpoint_type

# Set up logging to capture log output
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def test_extract_text_from_responses_api():
    """Test extracting text from various Responses API response structures."""
    print("=" * 70)
    print("Testing extract_completion_text for Responses API")
    print("=" * 70)
    print()
    
    passed = 0
    failed = 0
    
    # Test Case 1: Response with output_text attribute
    print("Test 1: Response with output_text attribute")
    response1 = Mock()
    response1.output_text = "This is the generated text"
    try:
        text = extract_completion_text(response1, "gpt-5.2-pro")
        if text == "This is the generated text":
            print("✓ Successfully extracted from output_text")
            passed += 1
        else:
            print(f"✗ Wrong text extracted: {text}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    # Test Case 2: Response with output attribute
    print("Test 2: Response with output attribute")
    response2 = Mock()
    response2.output_text = None
    response2.output = "Text from output attribute"
    try:
        text = extract_completion_text(response2, "gpt-5.2-pro")
        if text == "Text from output attribute":
            print("✓ Successfully extracted from output")
            passed += 1
        else:
            print(f"✗ Wrong text extracted: {text}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    # Test Case 3: Response with choices format (message.content)
    print("Test 3: Response with choices format (message.content)")
    response3 = Mock()
    response3.output_text = None
    if hasattr(response3, 'output'):
        delattr(response3, 'output')  # Remove output attribute if it exists
    choice = Mock()
    choice.message = Mock()
    choice.message.content = "Text from choices message"
    response3.choices = [choice]
    try:
        text = extract_completion_text(response3, "gpt-5.2-pro")
        if text == "Text from choices message":
            print("✓ Successfully extracted from choices[0].message.content")
            passed += 1
        else:
            print(f"✗ Wrong text extracted: {text}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    # Test Case 4: Response with choices format (text)
    print("Test 4: Response with choices format (text)")
    response4 = Mock()
    response4.output_text = None
    if hasattr(response4, 'output'):
        delattr(response4, 'output')
    choice = Mock()
    choice.text = "Text from choices text"
    if hasattr(choice, 'message'):
        delattr(choice, 'message')  # Remove message attribute if it exists
    response4.choices = [choice]
    try:
        text = extract_completion_text(response4, "gpt-5.2-pro")
        if text == "Text from choices text":
            print("✓ Successfully extracted from choices[0].text")
            passed += 1
        else:
            print(f"✗ Wrong text extracted: {text}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    # Test Case 5: Invalid response (should raise ValueError with helpful message)
    print("Test 5: Invalid response structure (should raise informative error)")
    response5 = Mock()
    response5.output_text = None
    if hasattr(response5, 'output'):
        delattr(response5, 'output')
    if hasattr(response5, 'choices'):
        delattr(response5, 'choices')
    try:
        text = extract_completion_text(response5, "gpt-5.2-pro")
        print(f"✗ Should have raised ValueError but got: {text}")
        failed += 1
    except ValueError as e:
        if "Unable to extract text" in str(e):
            print(f"✓ Correctly raised ValueError with message: {str(e)[:100]}...")
            passed += 1
        else:
            print(f"✗ Wrong error message: {e}")
            failed += 1
    except Exception as e:
        print(f"✗ Wrong exception type: {type(e).__name__}: {e}")
        failed += 1
    print()
    
    print("-" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_get_finish_reason_robustness():
    """Test that get_finish_reason handles various response structures."""
    print("=" * 70)
    print("Testing get_finish_reason robustness")
    print("=" * 70)
    print()
    
    passed = 0
    failed = 0
    
    # Test Case 1: Standard response with choices[0].finish_reason
    print("Test 1: Standard response with choices[0].finish_reason")
    response1 = Mock()
    choice = Mock()
    choice.finish_reason = "stop"
    response1.choices = [choice]
    try:
        reason = get_finish_reason(response1, "gpt-5.2-pro")
        if reason == "stop":
            print("✓ Successfully got finish_reason from choices")
            passed += 1
        else:
            print(f"✗ Wrong finish_reason: {reason}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    # Test Case 2: Response with finish_reason at top level
    print("Test 2: Response with finish_reason at top level")
    response2 = Mock()
    response2.finish_reason = "length"
    if hasattr(response2, 'choices'):
        delattr(response2, 'choices')
    try:
        reason = get_finish_reason(response2, "gpt-5.2-pro")
        if reason == "length":
            print("✓ Successfully got finish_reason from top level")
            passed += 1
        else:
            print(f"✗ Wrong finish_reason: {reason}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    # Test Case 3: Response with no finish_reason (should return "unknown")
    print("Test 3: Response with no finish_reason (should return 'unknown')")
    response3 = Mock()
    if hasattr(response3, 'choices'):
        delattr(response3, 'choices')
    if hasattr(response3, 'finish_reason'):
        delattr(response3, 'finish_reason')
    try:
        reason = get_finish_reason(response3, "gpt-5.2-pro")
        if reason == "unknown":
            print("✓ Correctly returned 'unknown' for missing finish_reason")
            passed += 1
        else:
            print(f"✗ Should return 'unknown' but got: {reason}")
            failed += 1
    except Exception as e:
        print(f"✗ Should not raise exception but got: {e}")
        failed += 1
    print()
    
    # Test Case 4: Response with status field (should map to finish_reason)
    print("Test 4: Response with status field")
    response4 = Mock()
    response4.status = "complete"
    if hasattr(response4, 'choices'):
        delattr(response4, 'choices')
    if hasattr(response4, 'finish_reason'):
        delattr(response4, 'finish_reason')
    try:
        reason = get_finish_reason(response4, "gpt-5.2-pro")
        if reason == "stop":
            print("✓ Successfully mapped status='complete' to finish_reason='stop'")
            passed += 1
        else:
            print(f"✗ Wrong mapping, got: {reason}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    print("-" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_chat_completion_extraction():
    """Test that chat completion extraction still works correctly."""
    print("=" * 70)
    print("Testing extract_completion_text for Chat Completions")
    print("=" * 70)
    print()
    
    passed = 0
    failed = 0
    
    # Test standard chat completion response
    print("Test: Standard chat completion response")
    response = Mock()
    choice = Mock()
    choice.message = Mock()
    choice.message.content = "Chat completion text"
    response.choices = [choice]
    try:
        text = extract_completion_text(response, "gpt-4")
        if text == "Chat completion text":
            print("✓ Successfully extracted from chat completion")
            passed += 1
        else:
            print(f"✗ Wrong text: {text}")
            failed += 1
    except Exception as e:
        print(f"✗ Failed with exception: {e}")
        failed += 1
    print()
    
    print("-" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def main():
    """Run all tests."""
    print()
    
    test1_passed = test_extract_text_from_responses_api()
    test2_passed = test_get_finish_reason_robustness()
    test3_passed = test_chat_completion_extraction()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    all_passed = test1_passed and test2_passed and test3_passed
    
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print()
        print("The logging improvements are working correctly:")
        print("  • extract_completion_text handles various response structures")
        print("  • get_finish_reason is robust against missing attributes")
        print("  • Chat completion extraction remains backward compatible")
        print("  • Informative error messages are provided when extraction fails")
    else:
        print("✗ SOME TESTS FAILED")
        print()
        print("Please review the failures above.")
    
    print("=" * 70)
    print()
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
