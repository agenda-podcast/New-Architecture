#!/usr/bin/env python3
"""
Test script to verify mock response functionality.

This tests the testing mode toggle without making real API calls.
"""
import json
import sys
import os
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and temporarily enable testing mode
import global_config
original_testing_mode = global_config.TESTING_MODE
global_config.TESTING_MODE = True

from responses_api_generator import (
    get_mock_response_path,
    save_mock_response,
    load_mock_response
)


def test_mock_response_paths():
    """Test that mock response paths are constructed correctly."""
    print("Testing mock response path construction...")
    
    pass_a_path = str(get_mock_response_path("pass_a"))
    pass_b_path = str(get_mock_response_path("pass_b"))
    
    assert "test_data/mock_responses" in pass_a_path, "Pass A path should include test_data/mock_responses"
    assert "pass_a.json" in pass_a_path, "Pass A path should end with pass_a.json"
    assert "test_data/mock_responses" in pass_b_path, "Pass B path should include test_data/mock_responses"
    assert "pass_b.json" in pass_b_path, "Pass B path should end with pass_b.json"
    
    print(f"✓ Pass A path: {pass_a_path}")
    print(f"✓ Pass B path: {pass_b_path}")
    return True


def test_load_existing_mock_responses():
    """Test loading the pre-created mock responses."""
    print("\nTesting loading of existing mock responses...")
    
    try:
        # Load Pass A mock response
        pass_a_data = load_mock_response("pass_a")
        
        assert "sources" in pass_a_data, "Pass A response should have sources"
        assert "canonical_pack" in pass_a_data, "Pass A response should have canonical_pack"
        assert "l1_content" in pass_a_data, "Pass A response should have l1_content"
        
        sources = pass_a_data["sources"]
        canonical_pack = pass_a_data["canonical_pack"]
        l1_content = pass_a_data["l1_content"]
        
        assert len(sources) > 0, "Should have at least one source"
        assert "timeline" in canonical_pack, "Canonical pack should have timeline"
        assert "code" in l1_content, "L1 content should have code"
        assert l1_content["code"] == "L1", "L1 content code should be 'L1'"
        
        print(f"✓ Pass A mock loaded: {len(sources)} sources, {l1_content.get('actual_words', 0)} words")
        
        # Load Pass B mock response
        pass_b_data = load_mock_response("pass_b")
        
        assert "content" in pass_b_data, "Pass B response should have content"
        
        content_list = pass_b_data["content"]
        assert len(content_list) == 14, f"Should have 14 content pieces (2 M + 4 S + 8 R), got {len(content_list)}"
        
        # Verify content codes
        codes = [item.get("code", "") for item in content_list]
        expected_codes = ["M1", "M2", "S1", "S2", "S3", "S4", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]
        assert codes == expected_codes, f"Content codes should match expected: {expected_codes}"
        
        print(f"✓ Pass B mock loaded: {len(content_list)} content pieces")
        print(f"  Codes: {', '.join(codes)}")
        
        return True
        
    except FileNotFoundError as e:
        print(f"✗ Mock response files not found: {e}")
        return False


def test_save_and_load_roundtrip():
    """Test saving and loading a mock response."""
    print("\nTesting save/load roundtrip...")
    
    import tempfile
    
    # Temporarily override the mock responses directory
    original_dir = global_config.MOCK_RESPONSES_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        global_config.MOCK_RESPONSES_DIR = tmpdir
        
        # Create test data
        test_data = {
            "test_field": "test_value",
            "test_number": 42,
            "test_list": [1, 2, 3]
        }
        
        # Save
        save_mock_response("test_pass", test_data)
        
        # Load
        loaded_data = load_mock_response("test_pass")
        
        # Verify
        assert loaded_data == test_data, "Loaded data should match saved data"
        
        print("✓ Save/load roundtrip successful")
    
    # Restore original directory
    global_config.MOCK_RESPONSES_DIR = original_dir
    return True


def test_testing_mode_flag():
    """Test that testing mode flag is accessible."""
    print("\nTesting TESTING_MODE flag...")
    
    # Should be True since we set it at the top
    assert global_config.TESTING_MODE is True, "Testing mode should be enabled for this test"
    
    print("✓ TESTING_MODE flag accessible and working")
    return True


def main():
    """Run all tests."""
    print("=" * 80)
    print("MOCK RESPONSE TESTING MODE TESTS")
    print("=" * 80)
    
    tests = [
        test_mock_response_paths,
        test_load_existing_mock_responses,
        test_save_and_load_roundtrip,
        test_testing_mode_flag
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"✗ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ Test error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    # Restore original testing mode
    global_config.TESTING_MODE = original_testing_mode
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
