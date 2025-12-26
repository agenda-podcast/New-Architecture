# Quick Reference: Video-Audio Separation

## Default Settings ✓

```python
ENABLE_VIDEO_GENERATION = True   # video = yes
ENABLE_VIDEO_AUDIO_MUX = False    # video_with_audio = no
```

**Result:** Video-only files (no audio track) 🎬

## How It Works

### Video-Only Mode (Default)
```
Script → Audio → Video (no audio track)
                    ↓
              topic-01-L1.blender.mp4 (video-only)
```

### Video-with-Audio Mode
```
Script → Audio → Video (no audio) → Mux with Audio
                                          ↓
                            topic-01-L1.blender.mp4 (video+audio)
```

## Changing Settings

### To generate video WITH audio:
Edit `scripts/global_config.py`:
```python
ENABLE_VIDEO_AUDIO_MUX = True
```

### To skip video generation entirely:
Edit `scripts/global_config.py`:
```python
ENABLE_VIDEO_GENERATION = False
```

## Key Implementation Details

1. **Blender renderer:** Always creates video-only
2. **FFmpeg renderer:** Creates video-only OR video+audio based on settings
3. **Audio path:** Only used for duration calculation in video-only mode
4. **Function:** `create_video_from_images()` accepts optional `video_duration` parameter

## Files Modified

- ✅ `scripts/global_config.py` - Added settings
- ✅ `scripts/video_render.py` - Updated video generation logic
- ✅ `scripts/test_video_render.py` - Updated tests
- ✅ `scripts/test_video_audio_settings.py` - New test for settings
- ✅ `scripts/test_video_workflow.py` - New workflow test
- ✅ `VIDEO_AUDIO_SEPARATION.md` - Full documentation

## Testing

```bash
cd scripts
python3 test_video_audio_settings.py  # Verify settings
python3 test_video_workflow.py        # See workflow explanation
python3 test_video_render.py          # Test rendering functions
```

All tests pass! ✅
