#!/usr/bin/env python3
"""
Integration test for Blender codec mapping in configure_scene().

This test verifies that the configure_scene() method correctly translates
FFmpeg CLI-style codec settings to Blender enum values when configuring
the scene for rendering.
"""
import sys
import copy
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    """Create a test profile dictionary matching output_profiles.yml."""
    return {
        'resolution': {'width': 1920, 'height': 1080},
        'fps': 30,
        'container': 'mp4',
        'codec': {
            'name': 'libx264',
            'profile': 'high',
            'preset': 'medium',
            'crf': 23,
            'keyframe_interval': 60,
            'pix_fmt': 'yuv420p'
        },
        'bitrate_policy': {
            'target': '10M',
            'max': '12M',
            'buffer': '24M'
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


def test_codec_translation():
    """Test that FFmpeg codec names are translated to Blender enums."""
    print("\nTest 1: Codec name translation (libx264 -> H264)")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        builder.configure_scene(video_only=True)
    
    # Verify codec was translated from 'libx264' to 'H264'
    assert mock_ffmpeg.codec == 'H264', \
        f"Expected codec='H264', got '{mock_ffmpeg.codec}'"
    print("  ✓ Codec translated correctly: libx264 -> H264")


def test_container_translation():
    """Test that FFmpeg container names are translated to Blender enums."""
    print("\nTest 2: Container name translation (mp4 -> MPEG4)")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        builder.configure_scene(video_only=True)
    
    # Verify container was translated from 'mp4' to 'MPEG4'
    assert mock_ffmpeg.format == 'MPEG4', \
        f"Expected format='MPEG4', got '{mock_ffmpeg.format}'"
    print("  ✓ Container translated correctly: mp4 -> MPEG4")


def test_preset_translation():
    """Test that FFmpeg preset names are translated to Blender enums."""
    print("\nTest 3: Preset name translation (medium -> GOOD)")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        builder.configure_scene(video_only=True)
    
    # Verify preset was translated from 'medium' to 'GOOD'
    assert mock_ffmpeg.ffmpeg_preset == 'GOOD', \
        f"Expected ffmpeg_preset='GOOD', got '{mock_ffmpeg.ffmpeg_preset}'"
    print("  ✓ Preset translated correctly: medium -> GOOD")


def test_crf_translation():
    """Test that numeric CRF values are translated to Blender enums."""
    print("\nTest 4: CRF value translation (23 -> MEDIUM)")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        builder.configure_scene(video_only=True)
    
    # Verify CRF was translated from numeric 23 to 'MEDIUM' enum
    assert mock_ffmpeg.constant_rate_factor == 'MEDIUM', \
        f"Expected constant_rate_factor='MEDIUM', got '{mock_ffmpeg.constant_rate_factor}'"
    print("  ✓ CRF translated correctly: 23 -> MEDIUM")


def test_bitrate_parsing():
    """Test that bitrate values are parsed correctly."""
    print("\nTest 5: Bitrate parsing (10M -> 10000 kbps)")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        builder.configure_scene(video_only=True)
    
    # Verify bitrate was parsed correctly
    assert mock_ffmpeg.video_bitrate == 10000, \
        f"Expected video_bitrate=10000, got {mock_ffmpeg.video_bitrate}"
    assert mock_ffmpeg.maxrate == 12000, \
        f"Expected maxrate=12000, got {mock_ffmpeg.maxrate}"
    assert mock_ffmpeg.buffersize == 24000, \
        f"Expected buffersize=24000, got {mock_ffmpeg.buffersize}"
    print("  ✓ Bitrate parsed correctly: 10M -> 10000 kbps, 12M -> 12000 kbps, 24M -> 24000 kbps")


def test_use_sequencer_flag():
    """Test that use_sequencer flag is set."""
    print("\nTest 6: use_sequencer flag is set")
    
    profile = create_test_profile()
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    with patch('bpy.context.scene', mock_scene):
        builder.configure_scene(video_only=True)
    
    # Verify use_sequencer was set to True
    assert mock_scene.render.use_sequencer == True, \
        "Expected use_sequencer=True"
    print("  ✓ use_sequencer flag is set correctly")


def test_different_codecs():
    """Test translation of different codec types."""
    print("\nTest 7: Different codec translations")
    
    test_cases = [
        ('libx264', 'H264'),
        ('h264', 'H264'),
        ('mpeg4', 'MPEG4'),
    ]
    
    for input_codec, expected_blender_codec in test_cases:
        # Create fresh profile for each test to avoid interference
        profile = create_test_profile()
        profile['codec']['name'] = input_codec
        builder = build_video.BlenderVideoBuilder(profile, seed='test123')
        
        mock_scene, mock_ffmpeg = create_mock_scene()
        
        with patch('bpy.context.scene', mock_scene):
            builder.configure_scene(video_only=True)
        
        assert mock_ffmpeg.codec == expected_blender_codec, \
            f"Expected codec='{expected_blender_codec}' for input '{input_codec}', got '{mock_ffmpeg.codec}'"
        print(f"  ✓ {input_codec} -> {expected_blender_codec}")


def test_different_presets():
    """Test translation of different preset types."""
    print("\nTest 8: Different preset translations")
    
    test_cases = [
        ('slow', 'SLOWEST'),
        ('medium', 'GOOD'),
        ('fast', 'REALTIME'),
        ('veryfast', 'REALTIME'),
    ]
    
    for input_preset, expected_blender_preset in test_cases:
        # Create fresh profile for each test to avoid interference
        profile = create_test_profile()
        profile['codec']['preset'] = input_preset
        builder = build_video.BlenderVideoBuilder(profile, seed='test123')
        
        mock_scene, mock_ffmpeg = create_mock_scene()
        
        with patch('bpy.context.scene', mock_scene):
            builder.configure_scene(video_only=True)
        
        assert mock_ffmpeg.ffmpeg_preset == expected_blender_preset, \
            f"Expected preset='{expected_blender_preset}' for input '{input_preset}', got '{mock_ffmpeg.ffmpeg_preset}'"
        print(f"  ✓ {input_preset} -> {expected_blender_preset}")


def test_different_crf_values():
    """Test translation of different CRF values."""
    print("\nTest 9: Different CRF value translations")
    
    test_cases = [
        (0, 'LOSSLESS'),
        (17, 'PERC_LOSSLESS'),
        (20, 'HIGH'),
        (23, 'MEDIUM'),
        (26, 'LOW'),
        (29, 'VERYLOW'),
        (35, 'LOWEST'),
    ]
    
    for input_crf, expected_blender_crf in test_cases:
        # Create fresh profile for each test to avoid interference
        profile = create_test_profile()
        profile['codec']['crf'] = input_crf
        builder = build_video.BlenderVideoBuilder(profile, seed='test123')
        
        mock_scene, mock_ffmpeg = create_mock_scene()
        
        with patch('bpy.context.scene', mock_scene):
            builder.configure_scene(video_only=True)
        
        assert mock_ffmpeg.constant_rate_factor == expected_blender_crf, \
            f"Expected CRF='{expected_blender_crf}' for input {input_crf}, got '{mock_ffmpeg.constant_rate_factor}'"
        print(f"  ✓ {input_crf} -> {expected_blender_crf}")


def test_unsupported_codec_error():
    """Test that unsupported codecs raise an error."""
    print("\nTest 10: Unsupported codec raises error")
    
    profile = create_test_profile()
    profile['codec']['name'] = 'unsupported_codec'
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    try:
        with patch('bpy.context.scene', mock_scene):
            builder.configure_scene(video_only=True)
        assert False, "Should have raised ValueError for unsupported codec"
    except ValueError as e:
        assert "Unsupported codec" in str(e)
        print(f"  ✓ Unsupported codec correctly raises ValueError: {e}")


def test_unsupported_container_error():
    """Test that unsupported containers raise an error."""
    print("\nTest 11: Unsupported container raises error")
    
    profile = create_test_profile()
    profile['container'] = 'unsupported_container'
    builder = build_video.BlenderVideoBuilder(profile, seed='test123')
    
    mock_scene, mock_ffmpeg = create_mock_scene()
    
    try:
        with patch('bpy.context.scene', mock_scene):
            builder.configure_scene(video_only=True)
        assert False, "Should have raised ValueError for unsupported container"
    except ValueError as e:
        assert "Unsupported container" in str(e)
        print(f"  ✓ Unsupported container correctly raises ValueError: {e}")


if __name__ == '__main__':
    print("=== Integration Test: Blender Codec Mapping in configure_scene() ===")
    
    test_codec_translation()
    test_container_translation()
    test_preset_translation()
    test_crf_translation()
    test_bitrate_parsing()
    test_use_sequencer_flag()
    test_different_codecs()
    test_different_presets()
    test_different_crf_values()
    test_unsupported_codec_error()
    test_unsupported_container_error()
    
    print("\n=== All integration tests passed! ===")
