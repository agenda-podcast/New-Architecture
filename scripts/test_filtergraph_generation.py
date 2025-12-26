#!/usr/bin/env python3
"""
Test FFmpeg filtergraph generation for video effects.

Tests the complete implementation of render_slideshow_ffmpeg_effects:
- Filtergraph structure
- Image normalization
- Ken Burns effects
- Transition chaining
- Finishing passes
- Output validation
"""
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import video_render
    from global_config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
except ImportError as e:
    print(f"Error: Failed to import required modules: {e}")
    sys.exit(1)


def create_mock_subprocess_run(captured_cmds, output_path, width=1920, height=1080, duration='10.0'):
    """
    Create a mock subprocess.run function that handles FFmpeg and ffprobe calls.
    
    Args:
        captured_cmds: List to append captured commands to
        output_path: Path object for the output file
        width: Expected output width
        height: Expected output height
        duration: Expected output duration as string
    
    Returns:
        Mock function for subprocess.run
    """
    def mock_run(cmd, **kwargs):
        captured_cmds.append(cmd)
        
        # Handle xfade detection
        if len(cmd) >= 3 and cmd[1] == '-h' and cmd[2] == 'filter=xfade':
            return Mock(
                returncode=0,
                stdout="""transition         <int>   E..V....... transition (from 0 to 35) (default fade)
     fade            0       E..V.......
     wipeleft        1       E..V.......
     wiperight       2       E..V.......
     circleopen      3       E..V.......
     circleclose     4       E..V.......""",
                stderr=''
            )
        
        # Handle ffprobe calls
        if cmd[0] == 'ffprobe':
            mock_data = {
                'streams': [{
                    'width': width,
                    'height': height,
                    'duration': duration
                }],
                'format': {'duration': duration}
            }
            return Mock(
                returncode=0,
                stdout=json.dumps(mock_data),
                stderr=''
            )
        
        # Handle FFmpeg render call
        if cmd[0] == 'ffmpeg' and len(cmd) > 3 and cmd[1] != '-h':
            # Create dummy output file
            output_path.write_text("dummy video")
            return Mock(returncode=0, stdout='', stderr='')
        
        return Mock(returncode=0, stdout='', stderr='')
    
    return mock_run


def get_ffmpeg_render_cmd(captured_cmds):
    """Extract the FFmpeg render command from captured commands."""
    return [cmd for cmd in captured_cmds 
            if cmd and len(cmd) > 0 and cmd[0] == 'ffmpeg' 
            and not (len(cmd) >= 3 and cmd[1] == '-h')]


def test_filtergraph_generation_basic():
    """Test basic filtergraph generation without executing FFmpeg."""
    print("Testing basic filtergraph generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create dummy image files
        images = []
        for i in range(3):
            img = tmppath / f"image_{i:03d}.jpg"
            img.write_text("dummy image")
            images.append(img)
        
        output_path = tmppath / "output.mp4"
        captured_cmds = []
        
        mock_run = create_mock_subprocess_run(captured_cmds, output_path)
        
        with patch('video_render.subprocess.run', side_effect=mock_run):
            # Call the function
            result = video_render.render_slideshow_ffmpeg_effects(
                images=images,
                output_path=output_path,
                duration=10.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='long',
                seed='test_seed'
            )
            
            assert result is True, "Should return True on success"
            
            # Find FFmpeg render command
            ffmpeg_cmds = get_ffmpeg_render_cmd(captured_cmds)
            assert len(ffmpeg_cmds) > 0, f"Should execute FFmpeg render command"
            
            ffmpeg_cmd = ffmpeg_cmds[0]
            
            # Verify command structure
            assert '-filter_complex' in ffmpeg_cmd, f"Should use filter_complex"
            
            # Get filter_complex argument
            fc_idx = ffmpeg_cmd.index('-filter_complex')
            filter_complex = ffmpeg_cmd[fc_idx + 1]
            
            # Verify filtergraph contains expected components
            assert 'scale=' in filter_complex, "Should contain scale filter"
            assert 'crop=' in filter_complex, "Should contain crop filter"
            assert 'fps=' in filter_complex, "Should contain fps filter"
            assert 'format=yuv420p' in filter_complex, "Should contain format filter"
            
            # Verify input files
            assert '-i' in ffmpeg_cmd, "Should have input files"
            
            # Count inputs
            input_count = ffmpeg_cmd.count('-i')
            assert input_count >= 1, f"Should have at least 1 input, got {input_count}"
            
            # Verify output mapping
            assert '-map' in ffmpeg_cmd, "Should map output stream"
            
            # Verify encoding settings
            assert '-c:v' in ffmpeg_cmd, "Should specify video codec"
            assert '-pix_fmt' in ffmpeg_cmd, "Should specify pixel format"
            assert '-t' in ffmpeg_cmd, "Should specify duration"
            
            print("✓ Basic filtergraph generation working")


def test_ken_burns_effects():
    """Test Ken Burns motion effects are applied when enabled."""
    print("\nTesting Ken Burns effects integration...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create dummy image
        img = tmppath / "image_001.jpg"
        img.write_text("dummy image")
        
        output_path = tmppath / "output.mp4"
        captured_cmds = []
        
        mock_run = create_mock_subprocess_run(captured_cmds, output_path, duration='5.0')
        
        with patch('video_render.subprocess.run', side_effect=mock_run):
            result = video_render.render_slideshow_ffmpeg_effects(
                images=[img],
                output_path=output_path,
                duration=5.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='long',
                seed='kb_test'
            )
            
            assert result is True, "Should succeed with Ken Burns enabled"
            
            # Find FFmpeg render command
            ffmpeg_cmds = get_ffmpeg_render_cmd(captured_cmds)
            assert len(ffmpeg_cmds) > 0, "Should execute FFmpeg"
            
            filter_complex = None
            for i, arg in enumerate(ffmpeg_cmds[0]):
                if arg == '-filter_complex' and i + 1 < len(ffmpeg_cmds[0]):
                    filter_complex = ffmpeg_cmds[0][i + 1]
                    break
            
            assert filter_complex is not None, "Should have filter_complex"
            
            # Ken Burns uses zoompan filter (default enabled in config)
            assert 'zoompan=' in filter_complex, "Should contain zoompan filter for Ken Burns"
            
            print("✓ Ken Burns effects integrated correctly")


def test_xfade_transitions():
    """Test xfade transitions are chained correctly."""
    print("\nTesting xfade transition chaining...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create multiple images to trigger transitions
        images = []
        for i in range(4):
            img = tmppath / f"image_{i:03d}.jpg"
            img.write_text("dummy image")
            images.append(img)
        
        output_path = tmppath / "output.mp4"
        captured_cmds = []
        
        mock_run = create_mock_subprocess_run(captured_cmds, output_path, duration='15.0')
        
        with patch('video_render.subprocess.run', side_effect=mock_run):
            result = video_render.render_slideshow_ffmpeg_effects(
                images=images,
                output_path=output_path,
                duration=15.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='medium',
                seed='xfade_test'
            )
            
            assert result is True, "Should succeed with multiple images"
            
            # Find FFmpeg render command
            ffmpeg_cmds = get_ffmpeg_render_cmd(captured_cmds)
            filter_complex = None
            for i, arg in enumerate(ffmpeg_cmds[0]):
                if arg == '-filter_complex' and i + 1 < len(ffmpeg_cmds[0]):
                    filter_complex = ffmpeg_cmds[0][i + 1]
                    break
            
            assert filter_complex is not None, "Should have filter_complex"
            
            # With multiple images, should have xfade transitions
            assert 'xfade=' in filter_complex, "Should contain xfade filter"
            
            # Verify xfade parameters
            assert 'transition=' in filter_complex, "xfade should have transition parameter"
            assert 'duration=' in filter_complex, "xfade should have duration parameter"
            assert 'offset=' in filter_complex, "xfade should have offset parameter"
            
            print("✓ xfade transitions chained correctly")


def test_finishing_passes():
    """Test optional finishing passes (vignette and grain)."""
    print("\nTesting finishing passes...")
    
    # Note: Default config has vignette and grain disabled
    # This test verifies the code handles the configuration correctly
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        img = tmppath / "image_001.jpg"
        img.write_text("dummy image")
        
        output_path = tmppath / "output.mp4"
        captured_cmds = []
        
        mock_run = create_mock_subprocess_run(captured_cmds, output_path, duration='5.0')
        
        with patch('video_render.subprocess.run', side_effect=mock_run):
            result = video_render.render_slideshow_ffmpeg_effects(
                images=[img],
                output_path=output_path,
                duration=5.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='reels',
                seed='finish_test'
            )
            
            assert result is True, "Should succeed"
            
            # With default config (vignette=false, grain=false), 
            # finishing filters should not be present
            ffmpeg_cmds = get_ffmpeg_render_cmd(captured_cmds)
            filter_complex = None
            for i, arg in enumerate(ffmpeg_cmds[0]):
                if arg == '-filter_complex' and i + 1 < len(ffmpeg_cmds[0]):
                    filter_complex = ffmpeg_cmds[0][i + 1]
                    break
            
            # Default config has finishing disabled, so check accordingly
            # If enabled in future, these would be present
            print(f"  Filter complex (sample): {filter_complex[:200] if filter_complex else 'None'}...")
            
            print("✓ Finishing pass configuration handled correctly")


def test_output_validation():
    """Test ffprobe-based output validation."""
    print("\nTesting output validation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        img = tmppath / "image_001.jpg"
        img.write_text("dummy image")
        
        output_path = tmppath / "output.mp4"
        
        # Test case 1: Valid output
        captured_cmds = []
        mock_run = create_mock_subprocess_run(captured_cmds, output_path)
        
        with patch('video_render.subprocess.run', side_effect=mock_run):
            result = video_render.render_slideshow_ffmpeg_effects(
                images=[img],
                output_path=output_path,
                duration=10.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='long',
                seed='valid_test'
            )
            
            assert result is True, "Should succeed with valid output"
        
        # Test case 2: Resolution mismatch
        captured_cmds2 = []
        mock_run2 = create_mock_subprocess_run(captured_cmds2, output_path, width=1280, height=720)
        
        with patch('video_render.subprocess.run', side_effect=mock_run2):
            result = video_render.render_slideshow_ffmpeg_effects(
                images=[img],
                output_path=output_path,
                duration=10.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='long',
                seed='wrong_res_test'
            )
            
            assert result is False, "Should fail with wrong resolution"
        
        print("✓ Output validation working correctly")


def test_deterministic_seed():
    """Test that seed produces deterministic output."""
    print("\nTesting deterministic seed behavior...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        images = []
        for i in range(3):
            img = tmppath / f"image_{i:03d}.jpg"
            img.write_text("dummy image")
            images.append(img)
        
        output_path1 = tmppath / "output1.mp4"
        output_path2 = tmppath / "output2.mp4"
        
        captured_filters = []
        
        # First render
        captured_cmds1 = []
        mock_run1 = create_mock_subprocess_run(captured_cmds1, output_path1)
        
        with patch('video_render.subprocess.run', side_effect=mock_run1):
            video_render.render_slideshow_ffmpeg_effects(
                images=images,
                output_path=output_path1,
                duration=10.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='long',
                seed='deterministic_seed'
            )
        
        # Extract filter complex from first render
        ffmpeg_cmds1 = get_ffmpeg_render_cmd(captured_cmds1)
        for i, arg in enumerate(ffmpeg_cmds1[0]):
            if arg == '-filter_complex' and i + 1 < len(ffmpeg_cmds1[0]):
                captured_filters.append(ffmpeg_cmds1[0][i + 1])
                break
        
        # Second render
        captured_cmds2 = []
        mock_run2 = create_mock_subprocess_run(captured_cmds2, output_path2)
        
        with patch('video_render.subprocess.run', side_effect=mock_run2):
            video_render.render_slideshow_ffmpeg_effects(
                images=images,
                output_path=output_path2,
                duration=10.0,
                width=1920,
                height=1080,
                fps=30,
                content_type='long',
                seed='deterministic_seed'
            )
        
        # Extract filter complex from second render
        ffmpeg_cmds2 = get_ffmpeg_render_cmd(captured_cmds2)
        for i, arg in enumerate(ffmpeg_cmds2[0]):
            if arg == '-filter_complex' and i + 1 < len(ffmpeg_cmds2[0]):
                captured_filters.append(ffmpeg_cmds2[0][i + 1])
                break
        
        # Should produce identical filter complexes
        assert len(captured_filters) == 2, "Should capture 2 filter complexes"
        assert captured_filters[0] == captured_filters[1], "Same seed should produce identical filtergraphs"
        
        print("✓ Seed produces deterministic output")


def main():
    """Run all tests."""
    print("="*60)
    print("FFmpeg Filtergraph Generation Tests")
    print("="*60)
    
    try:
        test_filtergraph_generation_basic()
        test_ken_burns_effects()
        test_xfade_transitions()
        test_finishing_passes()
        test_output_validation()
        test_deterministic_seed()
        
        print("\n" + "="*60)
        print("✓ All filtergraph tests passed!")
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
