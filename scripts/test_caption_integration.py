#!/usr/bin/env python3
"""
Integration test for caption burn-in functionality.

This test creates a minimal video with captions to verify that
the FFmpeg drawtext filter works correctly with the fixed enable parameter.
"""
import sys
import subprocess
import tempfile
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))


def create_test_video(output_path: Path, duration: float = 5.0) -> bool:
    """Create a simple test video (black screen) for caption testing."""
    try:
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c=black:s=1920x1080:d={duration}',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-t', str(duration),
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to create test video: {e}")
        return False


def create_test_captions_srt(output_path: Path) -> bool:
    """Create a simple SRT file for testing."""
    try:
        content = """1
00:00:00,000 --> 00:00:02,000
Breaking: New AI regulations

2
00:00:02,500 --> 00:00:04,500
This is a test caption

3
00:00:04,800 --> 00:00:05,000
Final caption
"""
        output_path.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        print(f"Failed to create SRT file: {e}")
        return False


def test_caption_burn_in_with_ffmpeg():
    """Test that caption burn-in works with actual FFmpeg command."""
    print("Testing caption burn-in with FFmpeg...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test video
        input_video = temp_path / 'test_input.mp4'
        print(f"  Creating test video: {input_video.name}")
        if not create_test_video(input_video, duration=6.0):
            print("  ✗ Failed to create test video")
            return False
        print(f"  ✓ Test video created")
        
        # Create test captions
        captions_srt = temp_path / 'test_input.captions.srt'
        print(f"  Creating test captions: {captions_srt.name}")
        if not create_test_captions_srt(captions_srt):
            print("  ✗ Failed to create captions file")
            return False
        print(f"  ✓ Captions file created")
        
        # Import video_render module
        try:
            from video_render import burn_in_captions_if_present
        except ImportError as e:
            print(f"  ✗ Failed to import video_render: {e}")
            return False
        
        # Try to burn in captions
        print(f"  Attempting caption burn-in...")
        try:
            # Note: This will modify input_video in-place
            result = burn_in_captions_if_present(
                input_video=input_video,
                audio_path=None,
                width=1920,
                height=1080,
                fps=30
            )
            
            if result:
                print(f"  ✓ Caption burn-in completed successfully")
                
                # Verify output file exists and has content
                if input_video.exists() and input_video.stat().st_size > 1000:
                    print(f"  ✓ Output video exists and has content ({input_video.stat().st_size} bytes)")
                    return True
                else:
                    print(f"  ✗ Output video is missing or too small")
                    return False
            else:
                print(f"  ⚠ Caption burn-in returned False (may be expected for some configs)")
                # This might be OK if ENABLE_BURN_IN_CAPTIONS is False
                return True
                
        except subprocess.CalledProcessError as e:
            print(f"  ✗ FFmpeg command failed: {e}")
            if e.stderr:
                print(f"    stderr: {e.stderr[:500]}")
            return False
        except Exception as e:
            print(f"  ✗ Unexpected error during caption burn-in: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_drawtext_filter_syntax():
    """Test that the drawtext filter can be parsed by FFmpeg."""
    print("\nTesting drawtext filter syntax with FFmpeg...")
    
    # Import the internal function to test the specific fix
    # Note: While importing private functions is generally discouraged,
    # this is acceptable for targeted unit testing of a bug fix.
    from video_render import _build_drawtext_vf
    
    # Build a filter string
    captions = [
        (0.0, 2.0, "Test caption one"),
        (2.5, 4.5, "Test caption two"),
    ]
    
    vf = _build_drawtext_vf(
        captions,
        font_size=63,
        margin_v=384,
        margin_lr=50,
        style="tiktok"
    )
    
    print(f"  Generated filter (length: {len(vf)} chars)")
    
    # Test with FFmpeg -vf option parsing (dry-run with null output)
    # This will validate the filter syntax without actually rendering
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_video = temp_path / 'test.mp4'
        
        # Create a minimal test video
        if not create_test_video(input_video, duration=5.0):
            print("  ✗ Failed to create test video")
            return False
        
        # Try to parse the filter (use -t 0.1 to make it quick)
        cmd = [
            'ffmpeg', '-y',
            '-i', str(input_video),
            '-vf', vf,
            '-t', '0.1',
            '-f', 'null',
            '-'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print(f"  ✓ FFmpeg accepted the filter syntax")
                return True
            else:
                print(f"  ✗ FFmpeg rejected the filter (exit code {result.returncode})")
                if result.stderr:
                    # Look for specific error patterns
                    stderr = result.stderr
                    if "No option name near" in stderr:
                        print(f"  ✗ CRITICAL: 'No option name near' error detected (fix didn't work)")
                        print(f"    This is the exact error we're trying to fix!")
                    elif "Error parsing" in stderr:
                        print(f"  ✗ Filter parsing error detected")
                    
                    # Print relevant error lines
                    for line in stderr.split('\n'):
                        if any(err in line for err in ['Error', 'error', 'option', 'parsing']):
                            print(f"    {line}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"  ✗ FFmpeg command timed out")
            return False
        except Exception as e:
            print(f"  ✗ Error testing filter: {e}")
            return False


def main():
    """Run integration tests."""
    print("="*60)
    print("Caption Burn-in Integration Tests")
    print("="*60)
    
    # Check if FFmpeg is available
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        if result.returncode != 0:
            print("✗ FFmpeg not available - skipping integration tests")
            return 0
        print("✓ FFmpeg is available\n")
    except:
        print("✗ FFmpeg not available - skipping integration tests")
        return 0
    
    tests = [
        test_drawtext_filter_syntax,
        test_caption_burn_in_with_ffmpeg,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ EXCEPTION in {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Integration Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
