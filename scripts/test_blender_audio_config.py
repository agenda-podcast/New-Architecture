#!/usr/bin/env python3
"""
Test for Blender audio codec configuration fix.

This test verifies that the configure_scene() method correctly handles
the video_only parameter to disable audio encoding when rendering
video-only output.
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Mock Blender imports before importing build_video
sys.modules['bpy'] = MagicMock()
sys.modules['bpy.types'] = MagicMock()

# Add blender directory to path
blender_dir = Path(__file__).parent / 'blender'
sys.path.insert(0, str(blender_dir))

try:
    import build_video
except ImportError as e:
    print(f"Error importing build_video: {e}")
    sys.exit(1)


def create_test_profile():
    """Create a test profile dictionary for testing."""
    return {
        'resolution': {'width': 1920, 'height': 1080},
        'fps': 30,
        'container': 'mp4',
        'codec': {
            'name': 'libx264',
            'crf': 23,
            'preset': 'medium',
            'keyframe_interval': 60
        },
        'audio_policy': {
            'codec': 'aac',
            'bitrate': '128k',
            'sample_rate': 44100,
            'channels': 2
        }
    }


def create_mock_scene():
    """Create a mock Blender scene for testing."""
    mock_scene = MagicMock()
    mock_render = MagicMock()
    mock_ffmpeg = MagicMock()
    
    mock_scene.render = mock_render
    mock_render.ffmpeg = mock_ffmpeg
    
    return mock_scene, mock_ffmpeg


def test_configure_scene_with_audio():
    """Test that configure_scene sets audio codec when video_only=False."""
    print("\nTest 1: configure_scene with audio (video_only=False)")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        # Call configure_scene with video_only=False (default)
        builder.configure_scene(video_only=False)
    
    # Verify audio codec was set to AAC
    assert mock_ffmpeg.audio_codec == 'AAC', \
        f"Expected audio_codec='AAC', got '{mock_ffmpeg.audio_codec}'"
    assert mock_ffmpeg.audio_bitrate == 128, \
        f"Expected audio_bitrate=128, got {mock_ffmpeg.audio_bitrate}"
    assert mock_ffmpeg.audio_mixrate == 44100, \
        f"Expected audio_mixrate=44100, got {mock_ffmpeg.audio_mixrate}"
    assert mock_ffmpeg.audio_channels == 'STEREO', \
        f"Expected audio_channels='STEREO', got '{mock_ffmpeg.audio_channels}'"
    
    print("  ✓ Audio codec configured correctly (AAC)")
    print("  ✓ Audio bitrate set to 128")
    print("  ✓ Audio sample rate set to 44100")
    print("  ✓ Audio channels set to STEREO")


def test_configure_scene_video_only():
    """Test that configure_scene disables audio codec when video_only=True."""
    print("\nTest 2: configure_scene video-only (video_only=True)")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        # Call configure_scene with video_only=True
        builder.configure_scene(video_only=True)
    
    # Verify audio codec was set to NONE
    assert mock_ffmpeg.audio_codec == 'NONE', \
        f"Expected audio_codec='NONE', got '{mock_ffmpeg.audio_codec}'"
    
    print("  ✓ Audio codec set to NONE (disabled)")
    print("  ✓ Audio encoding disabled for video-only render")


def test_configure_scene_default_parameter():
    """Test that configure_scene defaults to video_only=False."""
    print("\nTest 3: configure_scene default parameter")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        # Call configure_scene without parameter (should default to False)
        builder.configure_scene()
    
    # Verify audio codec was set (should use default audio configuration)
    assert mock_ffmpeg.audio_codec == 'AAC', \
        f"Expected audio_codec='AAC' by default, got '{mock_ffmpeg.audio_codec}'"
    
    print("  ✓ Default parameter (video_only=False) works correctly")
    print("  ✓ Audio codec configured when parameter omitted")


def test_configure_scene_missing_audio_policy():
    """Test that configure_scene raises error when audio_policy is missing and video_only=False."""
    print("\nTest 4: configure_scene with missing audio_policy")
    
    # Create profile without audio_policy
    profile = {
        'resolution': {'width': 1920, 'height': 1080},
        'fps': 30,
        'container': 'mp4',
        'codec': {
            'name': 'libx264',
            'crf': 23,
            'preset': 'medium',
            'keyframe_interval': 60
        }
        # Note: no audio_policy
    }
    
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    # Should raise ValueError when trying to configure audio without audio_policy
    with patch('bpy.context.scene', mock_scene):
        try:
            builder.configure_scene(video_only=False)
            assert False, "Expected ValueError when audio_policy is missing"
        except ValueError as e:
            assert "audio_policy" in str(e).lower(), \
                f"Expected error message to mention 'audio_policy', got: {e}"
            print("  ✓ Raises ValueError when audio_policy is missing")
    
    # Should work fine when video_only=True (doesn't need audio_policy)
    with patch('bpy.context.scene', mock_scene):
        builder.configure_scene(video_only=True)
        assert mock_ffmpeg.audio_codec == 'NONE', \
            "Expected audio_codec='NONE' when video_only=True"
        print("  ✓ Works correctly with video_only=True even without audio_policy")


def main():
    """Run all tests."""
    print("="*60)
    print("Blender Audio Configuration Tests")
    print("="*60)
    
    try:
        test_configure_scene_with_audio()
        test_configure_scene_video_only()
        test_configure_scene_default_parameter()
        test_configure_scene_missing_audio_policy()
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
        print("\nSummary:")
        print("  - configure_scene(video_only=False) sets audio codec to AAC")
        print("  - configure_scene(video_only=True) sets audio codec to NONE")
        print("  - Default parameter behavior works correctly")
        print("  - Proper error handling for missing audio_policy")
        print("\nThis fix ensures Blender renders video-only output without")
        print("attempting to encode audio, avoiding FFmpeg exit code 254.")
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
