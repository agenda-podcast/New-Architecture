#!/usr/bin/env python3
"""
Output validation module for video rendering.

Validates that rendered videos meet the exact specifications defined
in output_profiles.yml. Used for post-render validation to ensure
quality and consistency.
"""
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import yaml

# Path to output profiles configuration
CONFIG_DIR = Path(__file__).parent.parent / 'config'
OUTPUT_PROFILES_PATH = CONFIG_DIR / 'output_profiles.yml'

# Codec name mapping: encoder name -> codec name
# ffprobe reports codec_name (e.g., 'h264') while encoder is 'libx264'
CODEC_NAME_MAP = {
    'libx264': 'h264',
    'libx265': 'hevc',
    'libvpx': 'vp8',
    'libvpx-vp9': 'vp9'
}


def load_output_profiles() -> Dict[str, Any]:
    """
    Load output profiles from YAML configuration.
    
    Returns:
        Dictionary of output profiles
    """
    if not OUTPUT_PROFILES_PATH.exists():
        raise FileNotFoundError(f"Output profiles not found: {OUTPUT_PROFILES_PATH}")
    
    with open(OUTPUT_PROFILES_PATH, 'r') as f:
        config = yaml.safe_load(f)
    
    return config.get('profiles', {})


def get_profile_for_content_type(content_type: str) -> Optional[Dict[str, Any]]:
    """
    Get output profile for a specific content type.
    
    Args:
        content_type: Content type ('long', 'medium', 'short', 'reels')
        
    Returns:
        Profile dictionary or None if not found
    """
    profiles = load_output_profiles()
    return profiles.get(content_type)


def get_video_metadata(video_path: Path) -> Dict[str, Any]:
    """
    Extract video metadata using ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with video metadata
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        str(video_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    
    # Extract relevant information
    video_stream = None
    audio_stream = None
    
    for stream in data.get('streams', []):
        if stream.get('codec_type') == 'video' and video_stream is None:
            video_stream = stream
        elif stream.get('codec_type') == 'audio' and audio_stream is None:
            audio_stream = stream
    
    format_info = data.get('format', {})
    
    return {
        'video': video_stream,
        'audio': audio_stream,
        'format': format_info
    }


def validate_video_output(video_path: Path, content_type: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate video output against profile requirements.
    
    Args:
        video_path: Path to video file
        content_type: Content type ('long', 'medium', 'short', 'reels')
        
    Returns:
        Tuple of (is_valid, validation_report)
    """
    if not video_path.exists():
        return False, {
            'status': 'error',
            'message': f'Video file not found: {video_path}',
            'errors': ['File not found']
        }
    
    # Load profile
    profile = get_profile_for_content_type(content_type)
    if not profile:
        return False, {
            'status': 'error',
            'message': f'Unknown content type: {content_type}',
            'errors': ['Profile not found']
        }
    
    # Get video metadata
    try:
        metadata = get_video_metadata(video_path)
    except Exception as e:
        return False, {
            'status': 'error',
            'message': f'Failed to read video metadata: {e}',
            'errors': ['Metadata extraction failed']
        }
    
    # Validation report
    report = {
        'status': 'pass',
        'content_type': content_type,
        'video_path': str(video_path),
        'checks': {},
        'errors': [],
        'warnings': []
    }
    
    video_stream = metadata.get('video')
    audio_stream = metadata.get('audio')
    format_info = metadata.get('format')
    
    if not video_stream:
        report['errors'].append('No video stream found')
        report['status'] = 'fail'
        return False, report
    
    if not audio_stream:
        report['errors'].append('No audio stream found')
        report['status'] = 'fail'
        return False, report
    
    # Check resolution
    expected_width = profile['resolution']['width']
    expected_height = profile['resolution']['height']
    actual_width = int(video_stream.get('width', 0))
    actual_height = int(video_stream.get('height', 0))
    
    resolution_match = (actual_width == expected_width and actual_height == expected_height)
    report['checks']['resolution'] = {
        'expected': f"{expected_width}x{expected_height}",
        'actual': f"{actual_width}x{actual_height}",
        'pass': resolution_match
    }
    
    if not resolution_match:
        report['errors'].append(
            f"Resolution mismatch: expected {expected_width}x{expected_height}, "
            f"got {actual_width}x{actual_height}"
        )
        report['status'] = 'fail'
    
    # Check FPS
    expected_fps = profile['fps']
    fps_str = video_stream.get('r_frame_rate', '0/1')
    if '/' in fps_str:
        num, den = map(int, fps_str.split('/'))
        actual_fps = num / den if den != 0 else 0
    else:
        actual_fps = float(fps_str)
    
    fps_match = abs(actual_fps - expected_fps) < 0.1
    report['checks']['fps'] = {
        'expected': expected_fps,
        'actual': round(actual_fps, 2),
        'pass': fps_match
    }
    
    if not fps_match:
        report['errors'].append(
            f"FPS mismatch: expected {expected_fps}, got {actual_fps:.2f}"
        )
        report['status'] = 'fail'
    
    # Check video codec
    # Note: ffprobe reports codec_name as 'h264' while encoder name is 'libx264'
    # We need to normalize the comparison using the module-level mapping
    expected_codec = profile['codec']['name']
    actual_codec = video_stream.get('codec_name', '')
    
    expected_codec_normalized = CODEC_NAME_MAP.get(expected_codec, expected_codec)
    codec_match = (actual_codec == expected_codec_normalized)
    
    report['checks']['video_codec'] = {
        'expected': expected_codec_normalized,
        'actual': actual_codec,
        'pass': codec_match
    }
    
    if not codec_match:
        report['errors'].append(
            f"Video codec mismatch: expected {expected_codec_normalized}, got {actual_codec}"
        )
        report['status'] = 'fail'
    
    # Check pixel format
    expected_pix_fmt = profile['codec']['pix_fmt']
    actual_pix_fmt = video_stream.get('pix_fmt', '')
    
    pix_fmt_match = (actual_pix_fmt == expected_pix_fmt)
    report['checks']['pixel_format'] = {
        'expected': expected_pix_fmt,
        'actual': actual_pix_fmt,
        'pass': pix_fmt_match
    }
    
    if not pix_fmt_match:
        report['warnings'].append(
            f"Pixel format mismatch: expected {expected_pix_fmt}, got {actual_pix_fmt}"
        )
    
    # Check audio codec
    expected_audio_codec = profile['audio_policy']['codec']
    actual_audio_codec = audio_stream.get('codec_name', '')
    
    audio_codec_match = (actual_audio_codec == expected_audio_codec)
    report['checks']['audio_codec'] = {
        'expected': expected_audio_codec,
        'actual': actual_audio_codec,
        'pass': audio_codec_match
    }
    
    if not audio_codec_match:
        report['errors'].append(
            f"Audio codec mismatch: expected {expected_audio_codec}, got {actual_audio_codec}"
        )
        report['status'] = 'fail'
    
    # Check duration (if validation rules exist)
    if 'validation' in profile:
        duration_str = format_info.get('duration', '0')
        duration = float(duration_str)
        
        min_duration = profile['validation'].get('min_duration', 0)
        max_duration = profile['validation'].get('max_duration', float('inf'))
        
        duration_valid = (min_duration <= duration <= max_duration)
        report['checks']['duration'] = {
            'expected_range': f"{min_duration}-{max_duration}s",
            'actual': f"{duration:.2f}s",
            'pass': duration_valid
        }
        
        if not duration_valid:
            report['warnings'].append(
                f"Duration outside expected range: {duration:.2f}s "
                f"(expected {min_duration}-{max_duration}s)"
            )
    
    # Check container format
    expected_container = profile['container']
    actual_container = format_info.get('format_name', '').split(',')[0]
    
    container_match = (actual_container == expected_container)
    report['checks']['container'] = {
        'expected': expected_container,
        'actual': actual_container,
        'pass': container_match
    }
    
    if not container_match:
        report['warnings'].append(
            f"Container mismatch: expected {expected_container}, got {actual_container}"
        )
    
    # Set final status
    if report['errors']:
        report['status'] = 'fail'
    elif report['warnings']:
        report['status'] = 'pass_with_warnings'
    
    is_valid = (report['status'] in ['pass', 'pass_with_warnings'])
    return is_valid, report


def print_validation_report(report: Dict[str, Any]) -> None:
    """
    Print validation report in a human-readable format.
    
    Args:
        report: Validation report dictionary
    """
    status_symbol = {
        'pass': '✓',
        'pass_with_warnings': '⚠',
        'fail': '✗',
        'error': '✗'
    }
    
    symbol = status_symbol.get(report['status'], '?')
    print(f"\n{symbol} Validation Status: {report['status'].upper()}")
    print(f"Content Type: {report.get('content_type', 'unknown')}")
    print(f"Video: {report.get('video_path', 'unknown')}")
    
    if report.get('checks'):
        print("\nChecks:")
        for check_name, check_data in report['checks'].items():
            check_symbol = '✓' if check_data.get('pass') else '✗'
            print(f"  {check_symbol} {check_name.replace('_', ' ').title()}:")
            print(f"     Expected: {check_data.get('expected')}")
            print(f"     Actual:   {check_data.get('actual')}")
    
    if report.get('errors'):
        print("\nErrors:")
        for error in report['errors']:
            print(f"  ✗ {error}")
    
    if report.get('warnings'):
        print("\nWarnings:")
        for warning in report['warnings']:
            print(f"  ⚠ {warning}")


def main():
    """Command-line interface for video validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate video output against profile')
    parser.add_argument('video', help='Path to video file')
    parser.add_argument('--type', required=True, 
                       choices=['long', 'medium', 'short', 'reels'],
                       help='Content type')
    parser.add_argument('--json', action='store_true',
                       help='Output report as JSON')
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    is_valid, report = validate_video_output(video_path, args.type)
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_validation_report(report)
    
    return 0 if is_valid else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
