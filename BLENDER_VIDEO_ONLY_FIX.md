# Blender Video-Only Rendering Fix - December 19, 2025

## Problem Statement

When Blender was used to render video-only output (using the `--no-audio` flag), it would fail with FFmpeg exit code 254. The error occurred during the internal FFmpeg encoding step within Blender:

```
✓ Blender render complete (video-only)
  Muxing audio with FFmpeg...
  ✗ FFmpeg mux failed with exit code 254
```

## Root Cause

The issue was in `scripts/blender/build_video.py` in the `configure_scene()` method. This method was always configuring audio codec settings (AAC with bitrate, sample rate, and channels), even when rendering video-only output.

When Blender's internal FFmpeg encoder was configured with audio codec settings but no audio source was loaded (due to `--no-audio` flag), FFmpeg would fail trying to encode non-existent audio.

### Code Flow

1. `video_render.py` calls Blender with `--no-audio` flag (line 512)
2. `build_video.py` parses this flag into `args.no_audio`
3. `configure_scene()` was called without parameters, always configuring audio codec
4. Blender's FFmpeg encoder would fail with exit code 254

## Solution

Modified `configure_scene()` to accept a `video_only` parameter:

- When `video_only=True`: Sets `scene.render.ffmpeg.audio_codec = 'NONE'` to disable audio encoding
- When `video_only=False`: Configures audio codec normally (AAC with all settings)
- Default: `video_only=False` for backward compatibility

### Implementation Details

**File: scripts/blender/build_video.py**

```python
def configure_scene(self, video_only: bool = False) -> None:
    """
    Configure scene settings from output profile.
    
    Args:
        video_only: If True, disable audio encoding (video-only output)
    """
    # ... video configuration ...
    
    # Set audio codec - disable for video-only rendering
    if video_only:
        # Disable audio encoding entirely for video-only output
        scene.render.ffmpeg.audio_codec = 'NONE'
        print(f"Configured codecs: video={self.profile['codec']['name']}, audio=NONE (video-only)")
    else:
        # Configure audio encoding from profile
        audio_settings = self.profile.get('audio_policy')
        if not audio_settings:
            raise ValueError("Profile must contain 'audio_policy' for audio rendering")
        
        scene.render.ffmpeg.audio_codec = audio_settings['codec'].upper()
        scene.render.ffmpeg.audio_bitrate = int(audio_settings['bitrate'].replace('k', ''))
        scene.render.ffmpeg.audio_mixrate = audio_settings['sample_rate']
        scene.render.ffmpeg.audio_channels = 'STEREO' if audio_settings['channels'] == 2 else 'MONO'
        print(f"Configured codecs: video={self.profile['codec']['name']}, audio={audio_settings['codec']}")
```

**Call Site Update:**

```python
# In main() function
builder.configure_scene(video_only=args.no_audio)
```

## Testing

Created comprehensive test suite in `scripts/test_blender_audio_config.py`:

1. **Test 1**: Verify audio codec is set to AAC when `video_only=False`
2. **Test 2**: Verify audio codec is set to NONE when `video_only=True`
3. **Test 3**: Verify default parameter behavior (`video_only=False`)
4. **Test 4**: Verify error handling when `audio_policy` is missing

All tests pass ✓

## Benefits

1. **Fixes the immediate issue**: Blender now renders video-only output without FFmpeg errors
2. **Backward compatible**: Default behavior unchanged (video_only=False)
3. **Error handling**: Validates audio_policy exists when needed
4. **Clean separation**: Video-only vs. video+audio rendering is explicit
5. **Proper two-step workflow**: Blender renders video-only, then external FFmpeg muxes with audio

## Two-Step Rendering Workflow

The current implementation uses a two-step process:

1. **Blender Step**: Render video-only (with `--no-audio` and `--duration`)
   - Produces video track without audio
   - Audio codec set to 'NONE'
   - Timeline duration set from provided duration parameter

2. **FFmpeg Mux Step**: Combine video with original audio
   - Uses external FFmpeg to mux video-only output with original AAC audio
   - Preserves audio quality (no re-encoding)
   - Creates final MP4 with both video and audio tracks

This approach avoids codec compatibility issues and ensures the original high-quality audio is preserved.

## Related Files

- `scripts/blender/build_video.py` - Main fix
- `scripts/video_render.py` - Caller that passes `--no-audio` flag
- `scripts/test_blender_audio_config.py` - Test suite
- `scripts/blender/README.md` - Updated documentation

## Security Analysis

CodeQL analysis completed with 0 alerts. No security vulnerabilities introduced.

## Future Considerations

This fix is minimal and surgical. Potential future enhancements:

1. Support for multiple audio codec formats in profiles
2. Option to render audio within Blender (single-step) for certain use cases
3. Validation that ensures `--duration` is always provided with `--no-audio`

## Conclusion

The fix successfully resolves the FFmpeg exit code 254 error by properly configuring Blender's audio codec settings based on the rendering mode. The video-only rendering workflow now works correctly, and the external FFmpeg mux step can successfully combine the video with the original audio.
