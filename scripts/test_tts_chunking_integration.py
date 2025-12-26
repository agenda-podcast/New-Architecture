#!/usr/bin/env python3
"""Integration test for TTS chunking configuration with actual logic flow."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from global_config import TTS_USE_CHUNKING


def test_tts_logic_flow():
    """Test that the TTS logic correctly routes based on configuration."""
    print("\n=== Integration Test: TTS Logic Flow ===")
    
    # Import after ensuring path is set
    import tts_generate
    
    # Mock the actual TTS generation functions to avoid needing real audio engines
    with patch.object(tts_generate, '_tts_with_chunking') as mock_chunking, \
         patch.object(tts_generate, '_tts_traditional') as mock_traditional:
        
        mock_chunking.return_value = True
        mock_traditional.return_value = True
        
        # Test 1: Default configuration (should use single run)
        print("\n  Test 1: Default config (no tts_use_chunking specified)")
        config_default = {
            'premium_tts': False,
            'voice_a_gender': 'Male',
            'voice_b_gender': 'Female'
        }
        dialogue = [
            {'speaker': 'A', 'text': 'Test content ' * 1000}  # Short content
        ]
        mp3_path = Path('/tmp/test_default.mp3')
        
        result = tts_generate.tts_chunks_to_mp3(dialogue, mp3_path, config_default)
        
        # Since TTS_USE_CHUNKING is False by default, should call traditional
        assert result == True, "Should succeed"
        assert mock_traditional.called, "Should call _tts_traditional with default config"
        assert not mock_chunking.called, "Should not call _tts_with_chunking with default config"
        print("    ✓ Default config uses single run (_tts_traditional)")
        
        # Reset mocks
        mock_chunking.reset_mock()
        mock_traditional.reset_mock()
        
        # Test 2: Explicit chunking disabled
        print("\n  Test 2: Explicit tts_use_chunking=False")
        config_no_chunking = {
            'premium_tts': False,
            'tts_use_chunking': False,
            'voice_a_gender': 'Male',
            'voice_b_gender': 'Female'
        }
        
        result = tts_generate.tts_chunks_to_mp3(dialogue, mp3_path, config_no_chunking)
        
        assert result == True, "Should succeed"
        assert mock_traditional.called, "Should call _tts_traditional when tts_use_chunking=False"
        assert not mock_chunking.called, "Should not call _tts_with_chunking when tts_use_chunking=False"
        print("    ✓ tts_use_chunking=False uses single run (_tts_traditional)")
        
        # Reset mocks
        mock_chunking.reset_mock()
        mock_traditional.reset_mock()
        
        # Test 3: Explicit chunking enabled
        print("\n  Test 3: Explicit tts_use_chunking=True")
        config_chunking = {
            'premium_tts': False,
            'tts_use_chunking': True,
            'voice_a_gender': 'Male',
            'voice_b_gender': 'Female'
        }
        
        result = tts_generate.tts_chunks_to_mp3(dialogue, mp3_path, config_chunking)
        
        assert result == True, "Should succeed"
        assert mock_chunking.called, "Should call _tts_with_chunking when tts_use_chunking=True"
        assert not mock_traditional.called, "Should not call _tts_traditional when tts_use_chunking=True"
        print("    ✓ tts_use_chunking=True uses chunking strategy (_tts_with_chunking)")
        
        # Reset mocks
        mock_chunking.reset_mock()
        mock_traditional.reset_mock()
        
        # Test 4: Large content with chunking disabled (should still use traditional)
        print("\n  Test 4: Large content with tts_use_chunking=False")
        large_dialogue = [
            {'speaker': 'A', 'text': 'Test content ' * 10000}  # Very large content for testing
        ]
        
        result = tts_generate.tts_chunks_to_mp3(large_dialogue, mp3_path, config_no_chunking)
        
        assert result == True, "Should succeed"
        assert mock_traditional.called, "Should call _tts_traditional even for large content when disabled"
        assert not mock_chunking.called, "Should not auto-switch to chunking based on size"
        print("    ✓ Large content still uses single run when tts_use_chunking=False")
        
        print("\n  ✓ All integration tests passed!")


def test_config_precedence():
    """Test that topic config takes precedence over global config."""
    print("\n=== Integration Test: Config Precedence ===")
    
    import tts_generate
    
    # The topic config should override the global default
    with patch.object(tts_generate, '_tts_with_chunking') as mock_chunking, \
         patch.object(tts_generate, '_tts_traditional') as mock_traditional:
        
        mock_chunking.return_value = True
        mock_traditional.return_value = True
        
        # Even though global default is False, topic config True should take precedence
        config = {
            'premium_tts': False,
            'tts_use_chunking': True,  # Override global default
            'voice_a_gender': 'Male',
            'voice_b_gender': 'Female'
        }
        dialogue = [{'speaker': 'A', 'text': 'Test'}]
        mp3_path = Path('/tmp/test.mp3')
        
        result = tts_generate.tts_chunks_to_mp3(dialogue, mp3_path, config)
        
        assert mock_chunking.called, "Topic config should override global default"
        assert not mock_traditional.called, "Should use chunking when topic config says so"
        print("  ✓ Topic config correctly overrides global default")


def test_chunking_unavailable_warning():
    """Test that warning is shown when chunking is requested but unavailable."""
    print("\n=== Integration Test: Chunking Unavailable Warning ===")
    
    import tts_generate
    
    # Mock TTS_CHUNKER_AVAILABLE as False
    with patch.object(tts_generate, 'TTS_CHUNKER_AVAILABLE', False), \
         patch.object(tts_generate, '_tts_traditional') as mock_traditional:
        
        mock_traditional.return_value = True
        
        config = {
            'premium_tts': False,
            'tts_use_chunking': True,  # Request chunking
            'voice_a_gender': 'Male',
            'voice_b_gender': 'Female'
        }
        dialogue = [{'speaker': 'A', 'text': 'Test'}]
        mp3_path = Path('/tmp/test.mp3')
        
        # Capture output
        from io import StringIO
        import sys
        captured_output = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output
        
        try:
            result = tts_generate.tts_chunks_to_mp3(dialogue, mp3_path, config)
            output = captured_output.getvalue()
        finally:
            sys.stdout = old_stdout
        
        assert result == True, "Should succeed with fallback"
        assert mock_traditional.called, "Should fall back to traditional"
        assert "Warning" in output or "⚠" in output, "Should show warning about unavailable chunking"
        assert "Falling back" in output, "Should mention fallback"
        print("  ✓ Warning shown when chunking unavailable but requested")


def main():
    """Run all integration tests."""
    print("="*60)
    print("TTS Chunking Configuration - Integration Tests")
    print("="*60)
    
    try:
        test_tts_logic_flow()
        test_config_precedence()
        test_chunking_unavailable_warning()
        
        print("\n" + "="*60)
        print("All integration tests passed!")
        print("="*60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
