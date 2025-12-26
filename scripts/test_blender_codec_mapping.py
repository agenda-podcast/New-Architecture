#!/usr/bin/env python3
"""
Test to verify Blender codec mapping functions.

This test validates that:
1. Container names are correctly mapped from FFmpeg to Blender enums
2. Codec names are correctly mapped from FFmpeg to Blender enums
3. Preset names are correctly mapped from FFmpeg to Blender enums
4. CRF values are correctly mapped to Blender quality enums
5. Bitrate values are correctly parsed to kbps
"""
import sys
from pathlib import Path

# Add the blender directory to the path to import the module
sys.path.insert(0, str(Path(__file__).parent / 'blender'))

# Import the mapping functions (these don't require Blender to be available)
from build_video import (
    BLENDER_CONTAINER_MAP,
    BLENDER_CODEC_MAP,
    BLENDER_PRESET_MAP,
    _crf_to_blender_enum,
    _parse_rate_to_kbps,
)


def test_container_mapping():
    """Test that container names are correctly mapped."""
    print("Testing container name mapping...")
    
    # Test common containers
    assert BLENDER_CONTAINER_MAP.get("mp4") == "MPEG4", "mp4 should map to MPEG4"
    assert BLENDER_CONTAINER_MAP.get("mov") == "QUICKTIME", "mov should map to QUICKTIME"
    assert BLENDER_CONTAINER_MAP.get("mkv") == "MATROSKA", "mkv should map to MATROSKA"
    assert BLENDER_CONTAINER_MAP.get("webm") == "WEBM", "webm should map to WEBM"
    
    print("  ✓ Container mapping works correctly")


def test_codec_mapping():
    """Test that codec names are correctly mapped."""
    print("\nTesting codec name mapping...")
    
    # Test common codecs
    assert BLENDER_CODEC_MAP.get("libx264") == "H264", "libx264 should map to H264"
    assert BLENDER_CODEC_MAP.get("h264") == "H264", "h264 should map to H264"
    assert BLENDER_CODEC_MAP.get("mpeg4") == "MPEG4", "mpeg4 should map to MPEG4"
    assert BLENDER_CODEC_MAP.get("vp9") == "VP9", "vp9 should map to VP9"
    assert BLENDER_CODEC_MAP.get("libvpx-vp9") == "VP9", "libvpx-vp9 should map to VP9"
    
    print("  ✓ Codec mapping works correctly")


def test_preset_mapping():
    """Test that preset names are correctly mapped."""
    print("\nTesting preset name mapping...")
    
    # Test common presets
    assert BLENDER_PRESET_MAP.get("medium") == "GOOD", "medium should map to GOOD"
    assert BLENDER_PRESET_MAP.get("slow") == "SLOWEST", "slow should map to SLOWEST"
    assert BLENDER_PRESET_MAP.get("slower") == "SLOWEST", "slower should map to SLOWEST"
    assert BLENDER_PRESET_MAP.get("veryslow") == "SLOWEST", "veryslow should map to SLOWEST"
    assert BLENDER_PRESET_MAP.get("fast") == "REALTIME", "fast should map to REALTIME"
    assert BLENDER_PRESET_MAP.get("faster") == "REALTIME", "faster should map to REALTIME"
    assert BLENDER_PRESET_MAP.get("veryfast") == "REALTIME", "veryfast should map to REALTIME"
    
    print("  ✓ Preset mapping works correctly")


def test_crf_to_enum():
    """Test that CRF values are correctly converted to Blender enums."""
    print("\nTesting CRF to enum conversion...")
    
    # Test various CRF values
    assert _crf_to_blender_enum(0) == "LOSSLESS", "CRF 0 should be LOSSLESS"
    assert _crf_to_blender_enum(17) == "PERC_LOSSLESS", "CRF 17 should be PERC_LOSSLESS"
    assert _crf_to_blender_enum(20) == "HIGH", "CRF 20 should be HIGH"
    assert _crf_to_blender_enum(23) == "MEDIUM", "CRF 23 should be MEDIUM"
    assert _crf_to_blender_enum(26) == "LOW", "CRF 26 should be LOW"
    assert _crf_to_blender_enum(29) == "VERYLOW", "CRF 29 should be VERYLOW"
    assert _crf_to_blender_enum(35) == "LOWEST", "CRF 35 should be LOWEST"
    
    # Test boundary conditions
    assert _crf_to_blender_enum(18) == "HIGH", "CRF 18 should be HIGH"
    assert _crf_to_blender_enum(21) == "MEDIUM", "CRF 21 should be MEDIUM"
    assert _crf_to_blender_enum(24) == "LOW", "CRF 24 should be LOW"
    
    print("  ✓ CRF to enum conversion works correctly")


def test_bitrate_parsing():
    """Test that bitrate values are correctly parsed to kbps."""
    print("\nTesting bitrate parsing...")
    
    # Test various formats
    assert _parse_rate_to_kbps("10M") == 10000, "10M should parse to 10000 kbps"
    assert _parse_rate_to_kbps("8M") == 8000, "8M should parse to 8000 kbps"
    assert _parse_rate_to_kbps("128k") == 128, "128k should parse to 128 kbps"
    assert _parse_rate_to_kbps("8000k") == 8000, "8000k should parse to 8000 kbps"
    assert _parse_rate_to_kbps("5000") == 5000, "5000 should parse to 5000 kbps (no unit)"
    
    # Test with 'b' suffix (should be stripped)
    assert _parse_rate_to_kbps("10Mb") == 10000, "10Mb should parse to 10000 kbps"
    assert _parse_rate_to_kbps("128kb") == 128, "128kb should parse to 128 kbps"
    
    # Test decimal values
    assert _parse_rate_to_kbps("2.5M") == 2500, "2.5M should parse to 2500 kbps"
    assert _parse_rate_to_kbps("1.5k") == 1, "1.5k should parse to 1 kbps (rounded down)"
    
    print("  ✓ Bitrate parsing works correctly")


def test_invalid_bitrate():
    """Test that invalid bitrate values raise errors."""
    print("\nTesting invalid bitrate handling...")
    
    try:
        _parse_rate_to_kbps("invalid")
        assert False, "Should have raised ValueError for invalid bitrate"
    except ValueError as e:
        assert "Unrecognized bitrate value" in str(e)
        print("  ✓ Invalid bitrate correctly raises ValueError")
    
    try:
        _parse_rate_to_kbps("10G")  # Invalid unit
        assert False, "Should have raised ValueError for invalid unit"
    except ValueError as e:
        assert "Unrecognized bitrate value" in str(e)
        print("  ✓ Invalid unit correctly raises ValueError")


def test_profile_values():
    """Test that common profile values from output_profiles.yml work."""
    print("\nTesting common profile values...")
    
    # Values from the 'long' profile in output_profiles.yml
    container = "mp4"
    codec = "libx264"
    preset = "medium"
    crf = 23
    target_bitrate = "10M"
    max_bitrate = "12M"
    buffer_bitrate = "24M"
    
    # Test translations
    assert BLENDER_CONTAINER_MAP.get(container.lower()) == "MPEG4"
    assert BLENDER_CODEC_MAP.get(codec.lower()) == "H264"
    assert BLENDER_PRESET_MAP.get(preset.lower()) == "GOOD"
    assert _crf_to_blender_enum(crf) == "MEDIUM"
    assert _parse_rate_to_kbps(target_bitrate) == 10000
    assert _parse_rate_to_kbps(max_bitrate) == 12000
    assert _parse_rate_to_kbps(buffer_bitrate) == 24000
    
    print("  ✓ Common profile values translate correctly")


if __name__ == '__main__':
    print("=== Testing Blender Codec Mapping Functions ===\n")
    
    test_container_mapping()
    test_codec_mapping()
    test_preset_mapping()
    test_crf_to_enum()
    test_bitrate_parsing()
    test_invalid_bitrate()
    test_profile_values()
    
    print("\n=== All tests passed! ===")
