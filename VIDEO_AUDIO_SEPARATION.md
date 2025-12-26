# Video-Audio Separation Feature

## Overview

This feature allows video generation to be separated from audio muxing, enabling:
- Generation of video-only files as final output
- Optional combination of video with audio in a separate step
- Reuse of the same video with different audio tracks

## Configuration Settings

Two new settings have been added to `scripts/global_config.py`:

### ENABLE_VIDEO_GENERATION
- **Type:** Boolean
- **Default:** `True`
- **Purpose:** Controls whether video generation is enabled
- **Usage:** Set to `False` to skip video rendering entirely

### ENABLE_VIDEO_AUDIO_MUX
- **Type:** Boolean  
- **Default:** `False`
- **Purpose:** Controls whether video and audio are combined (muxed) together
- **Usage:**
  - `False` (default): Generates video-only files without audio track
  - `True`: Combines video with audio to create final output with both tracks

## Default Behavior

As requested, the default settings are:
- **video = yes** (`ENABLE_VIDEO_GENERATION = True`)
- **video_with_audio = no** (`ENABLE_VIDEO_AUDIO_MUX = False`)

This means by default, the system generates **video-only files** without audio.

## Workflow

### Video-Only Mode (Default: ENABLE_VIDEO_AUDIO_MUX = False)

1. **Script Generation**: Creates podcast script
2. **TTS Generation**: Creates audio file (e.g., `topic-01-20231219-L1.m4a`)
3. **Video Generation**: Creates video-only file (e.g., `topic-01-20231219-L1.blender.mp4`)
   - Uses audio duration to determine video length
   - Does NOT include audio track in the output
   - Audio file is only used to calculate duration

**Output:** Video file without audio track

### Video-with-Audio Mode (ENABLE_VIDEO_AUDIO_MUX = True)

1. **Script Generation**: Creates podcast script
2. **TTS Generation**: Creates audio file (e.g., `topic-01-20231219-L1.m4a`)
3. **Video Generation**: Creates video-only file from Blender
4. **Audio Muxing**: Combines video with audio using FFmpeg
   - Input: Video-only file + Audio file
   - Output: Final video with both video and audio tracks

**Output:** Video file with audio track

## Implementation Details

### Blender Renderer
- Always generates video-only output using `--no-audio` flag
- Audio path is passed only to determine duration
- Output: `.blender.mp4` file without audio track

### FFmpeg Renderer
- Can generate video-only or video-with-audio depending on `ENABLE_VIDEO_AUDIO_MUX`
- When `ENABLE_VIDEO_AUDIO_MUX = False`:
  - Does not add audio input to FFmpeg command
  - Uses `-t <duration>` to set video length
- When `ENABLE_VIDEO_AUDIO_MUX = True`:
  - Adds audio input with `-i <audio_path>`
  - Uses `-shortest` to match video/audio lengths
  - Encodes audio with AAC codec

### Function Signature Changes

The `create_video_from_images()` function now accepts:
- `audio_path`: Optional, can be `None` when generating video-only
- `video_duration`: Duration in seconds, used when audio_path is None or ENABLE_VIDEO_AUDIO_MUX is False

## Usage Examples

### Example 1: Generate Video-Only (Default)

```python
# In scripts/global_config.py
ENABLE_VIDEO_GENERATION = True
ENABLE_VIDEO_AUDIO_MUX = False

# Run pipeline
python scripts/run_pipeline.py --topic topic-01
```

**Result:** Video files without audio tracks

### Example 2: Generate Video with Audio

```python
# In scripts/global_config.py
ENABLE_VIDEO_GENERATION = True
ENABLE_VIDEO_AUDIO_MUX = True

# Run pipeline
python scripts/run_pipeline.py --topic topic-01
```

**Result:** Video files with audio tracks

### Example 3: Skip Video Generation

```python
# In scripts/global_config.py
ENABLE_VIDEO_GENERATION = False
# ENABLE_VIDEO_AUDIO_MUX setting is ignored when video generation is disabled

# Run pipeline
python scripts/run_pipeline.py --topic topic-01
```

**Result:** Only script and audio files, no video

## Benefits

1. **Faster Workflow**: Video-only generation is faster without audio encoding
2. **Flexibility**: Can generate video once and combine with different audio tracks later
3. **Debugging**: Easier to debug video rendering issues without audio complexity
4. **Storage**: Video-only files can be stored and audio added later as needed
5. **Customization**: Different audio tracks (languages, versions) can be muxed with same video

## Testing

Three test files verify the implementation:

1. **test_video_audio_settings.py**: Validates settings exist and have correct defaults
2. **test_video_workflow.py**: Demonstrates the two-step workflow
3. **test_video_render.py**: Tests the refactored video generation function

Run tests:
```bash
cd scripts
python3 test_video_audio_settings.py
python3 test_video_workflow.py
python3 test_video_render.py
```

## Migration Notes

### Breaking Changes
- Function `create_text_overlay_video()` renamed to `create_video_from_images()`
- Function signature now includes optional `video_duration` parameter
- When `ENABLE_VIDEO_AUDIO_MUX = False`, audio_path can be None

### Backward Compatibility
- Existing code passing audio_path will continue to work
- Tests updated to use new function name
- Old references to "overlay" removed from documentation

## Future Enhancements

Potential future improvements:
- Per-topic video settings in topic configuration files
- Separate script to mux existing video-only files with audio
- Support for multiple audio tracks (multi-language)
- Video-only rendering with custom duration (no audio reference needed)
