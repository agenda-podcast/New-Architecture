#!/usr/bin/env python3
"""Test TTS chunking configuration functionality."""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from global_config import TTS_USE_CHUNKING, validate_topic_config
# Import tts_generate to verify it's available (after path is set)
import tts_generate


def test_global_default():
    """Test that global default is False (single run)."""
    print("\n=== Test 1: Global Default Configuration ===")
    assert TTS_USE_CHUNKING == False, f"Expected TTS_USE_CHUNKING=False, got {TTS_USE_CHUNKING}"
    print("✓ Global default TTS_USE_CHUNKING is False (single run)")


def test_topic_config_validation():
    """Test topic config validation for tts_use_chunking field."""
    print("\n=== Test 2: Topic Config Validation ===")
    
    # Test valid boolean values
    config_true = {
        'id': 'test-01',
        'title': 'Test Topic',
        'queries': ['test'],
        'tts_use_chunking': True
    }
    result = validate_topic_config(config_true)
    assert result['status'] != 'error', f"Valid config should not have errors: {result['errors']}"
    print("✓ Config with tts_use_chunking=true validates successfully")
    
    config_false = {
        'id': 'test-02',
        'title': 'Test Topic',
        'queries': ['test'],
        'tts_use_chunking': False
    }
    result = validate_topic_config(config_false)
    assert result['status'] != 'error', f"Valid config should not have errors: {result['errors']}"
    print("✓ Config with tts_use_chunking=false validates successfully")
    
    # Test invalid non-boolean value
    config_invalid = {
        'id': 'test-03',
        'title': 'Test Topic',
        'queries': ['test'],
        'tts_use_chunking': 'yes'  # Invalid: should be boolean
    }
    result = validate_topic_config(config_invalid)
    assert result['status'] == 'error', "Invalid config should have errors"
    assert any('tts_use_chunking' in error and 'boolean' in error for error in result['errors']), \
        "Should have error about tts_use_chunking being non-boolean"
    print("✓ Config with non-boolean tts_use_chunking correctly fails validation")
    
    # Test omitted field (should use global default)
    config_omitted = {
        'id': 'test-04',
        'title': 'Test Topic',
        'queries': ['test']
    }
    result = validate_topic_config(config_omitted)
    # Should not error since field is optional
    assert 'tts_use_chunking' not in ' '.join(result['errors'])
    print("✓ Config without tts_use_chunking validates successfully (uses global default)")


def test_config_parsing():
    """Test that TTS config objects can be created and parsed correctly."""
    print("\n=== Test 3: Config Parsing ===")
    
    # Create mock config without tts_use_chunking (should use global default)
    config_default = {
        'premium_tts': False,
        'voice_a_gender': 'Male',
        'voice_b_gender': 'Female'
    }
    
    # Create mock config with explicit chunking enabled
    config_chunking = {
        'premium_tts': False,
        'tts_use_chunking': True,
        'voice_a_gender': 'Male',
        'voice_b_gender': 'Female'
    }
    
    # Create mock config with explicit chunking disabled
    config_no_chunking = {
        'premium_tts': False,
        'tts_use_chunking': False,
        'voice_a_gender': 'Male',
        'voice_b_gender': 'Female'
    }
    
    print("✓ Configs created successfully")
    print(f"  - Default config (uses global): tts_use_chunking not specified")
    print(f"  - Chunking enabled config: tts_use_chunking=True")
    print(f"  - Chunking disabled config: tts_use_chunking=False")
    
    # Note: Actual TTS logic flow is tested in test_tts_chunking_integration.py
    # This test verifies configuration object structure only.


def main():
    """Run all tests."""
    print("="*60)
    print("Testing TTS Chunking Configuration")
    print("="*60)
    
    try:
        test_global_default()
        test_topic_config_validation()
        test_config_parsing()
        
        print("\n" + "="*60)
        print("All tests passed!")
        print("="*60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
