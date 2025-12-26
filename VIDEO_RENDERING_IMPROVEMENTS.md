# Video Rendering Improvements

## Summary

This document describes the improvements made to the video rendering system to address black screen issues and add support for multiple video formats (horizontal and vertical).

## Changes Made

### 1. Image Collection Diagnostics

**Problem**: Videos showing black screens - unclear if images weren't downloading or overlay was too dark.

**Solution**: Enhanced diagnostic logging in `video_render.py` to clearly identify:
- Whether images exist in the output directory
- API credentials status (GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID)
- Image download success/failure
- When fallback placeholder images are used

**Result**: Clear diagnostic messages help identify the root cause:
```
IMAGE COLLECTION DIAGNOSTIC
======================================================================
✓ GOOGLE_CUSTOM_SEARCH_API_KEY is set (length: XX)
✓ GOOGLE_SEARCH_ENGINE_ID is set: YOUR_ID
✓ Successfully collected 10 images
```

or

```
⚠️  FALLING BACK TO PLACEHOLDER IMAGE
======================================================================
REASON: Image collection failed or no images downloaded
RESULT: Videos will show black screen (placeholder color)
FIX: Set GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID
```

### 2. Removed Dark Overlay Effects

**Problem**: Dark overlay (blur + darkening) was hiding images completely or making them too dark.

**Solution**: Removed blur and darkening effects from video backgrounds:
- **Before**: Applied `gblur`, `brightness=-0.3`, and `contrast=0.8`
- **After**: Only scales and pads images to fit frame (letterbox/pillarbox)

**Files Changed**:
- `scripts/video_render.py`: `create_background_with_overlay()` function
- `scripts/global_config.py`: Marked `VIDEO_BLUR_SIGMA`, `VIDEO_BRIGHTNESS`, `VIDEO_CONTRAST` as DEPRECATED

**Result**: Images are now clearly visible in videos without any darkening effects.

### 3. Removed Topic Title Text Overlay

**Problem**: Topic name was displayed on screen unnecessarily.

**Solution**: Removed topic title text overlay from videos, keeping only the timer.

**Before**:
```python
drawtext=text='Topic Title':fontsize=60:...,
drawtext=text='%{pts\:hms}':fontsize=40:...
```

**After**:
```python
drawtext=text='%{pts\:hms}':fontsize=40:...
```

**Files Changed**:
- `scripts/video_render.py`: `create_text_overlay_video()` function

**Result**: Cleaner video display with only timer in bottom-right corner.

### 4. Multiple Video Resolution Formats

**Problem**: All videos used the same 1920x1080 resolution, not suitable for mobile/social media.

**Solution**: Added two video format configurations:
- **Horizontal** (1920x1080): For desktop/TV viewing
- **Vertical** (1080x1920): For mobile (Instagram, TikTok, YouTube Shorts)

**Configuration** (`scripts/global_config.py`):
```python
VIDEO_RESOLUTIONS = {
    'horizontal': {
        'width': 1920,
        'height': 1080,
        'description': 'Horizontal format for desktop/TV viewing'
    },
    'vertical': {
        'width': 1080,
        'height': 1920,
        'description': 'Vertical format for mobile (Instagram, TikTok, YouTube Shorts)'
    }
}
```

### 5. Content Type to Video Format Mapping

**Problem**: Need to automatically select appropriate video format for each content type.

**Solution**: Mapped content types to video formats:
- **Long (L)** → Horizontal 1920x1080 (desktop/TV viewing)
- **Medium (M)** → Horizontal 1920x1080 (desktop/TV viewing)
- **Short (S)** → Vertical 1080x1920 (mobile/social media)
- **Reel (R)** → Vertical 1080x1920 (mobile/social media)

**Configuration** (`scripts/global_config.py`):
```python
CONTENT_TYPES = {
    'long': {
        'video_format': 'horizontal',
        ...
    },
    'medium': {
        'video_format': 'horizontal',
        ...
    },
    'short': {
        'video_format': 'vertical',
        ...
    },
    'reels': {
        'video_format': 'vertical',
        ...
    }
}
```

**Helper Functions**:
```python
get_video_resolution_for_content_type('long')  # Returns (1920, 1080)
get_video_resolution_for_content_type('short')  # Returns (1080, 1920)
get_video_resolution_for_code('L1')  # Returns (1920, 1080)
get_video_resolution_for_code('S3')  # Returns (1080, 1920)
```

### 6. Automatic Resolution Selection

**Problem**: Need to automatically use correct resolution when rendering videos.

**Solution**: Video rendering now automatically selects resolution based on content code:
- Extracts content type from code (e.g., 'L1' → 'L' → 'long' → horizontal)
- Uses appropriate resolution for processing images and creating video

**Files Changed**:
- `scripts/video_render.py`: `render_multi_format_for_topic()` function

**Result**: Each video is automatically rendered at the correct resolution:
```
Rendering L1: topic-01-20231218-L1.mp3
  Using resolution: 1920x1080
  
Rendering S3: topic-01-20231218-S3.mp3
  Using resolution: 1080x1920
```

### 7. Removed Per-Topic Video Configuration

**Problem**: Video resolution was duplicated in every topic configuration file.

**Solution**: Removed `video_width`, `video_height`, and `video_fps` from all topic configs:
- Resolution now determined by content type
- Global defaults used from `global_config.py`

**Files Changed**: All topic configuration files (`topics/topic-*.json`)

**Result**: Cleaner topic configs, single source of truth for video settings.

## Testing

### Automated Tests

Updated `scripts/test_video_render.py` with new test:
```python
def test_video_resolution_configuration():
    """Test video resolution configuration for different content types."""
```

**Test Coverage**:
- ✓ Horizontal and vertical resolutions defined correctly
- ✓ Content types mapped to correct formats
- ✓ Resolution lookup by content type works
- ✓ Resolution lookup by content code works

### Running Tests

```bash
cd scripts
python test_video_render.py
```

All tests pass successfully.

## Usage

### Setting Up Image Collection

To avoid black screens, ensure Google Custom Search API is configured:

```bash
export GOOGLE_CUSTOM_SEARCH_API_KEY="your_api_key_here"
export GOOGLE_SEARCH_ENGINE_ID="your_search_engine_id_here"
```

Without these credentials, videos will use black placeholder images.

### Rendering Videos

No changes needed to existing workflows:

```bash
# Render videos for a topic
python scripts/video_render.py --topic topic-01 --date 20231218
```

The system automatically:
1. Collects images (with diagnostics if it fails)
2. Selects correct resolution for each content type
3. Renders videos without overlay effects
4. Shows only timer (no title) on videos

### Expected Output

For each content code:
- **L1** (Long): 1920x1080 horizontal video
- **M1, M2** (Medium): 1920x1080 horizontal videos
- **S1, S2, S3, S4** (Short): 1080x1920 vertical videos
- **R1-R8** (Reels): 1080x1920 vertical videos

## Troubleshooting

### Black Screens

If videos show black screens:

1. Check diagnostic output from video rendering
2. Look for "FALLING BACK TO PLACEHOLDER IMAGE" message
3. Set Google Custom Search API credentials
4. Or manually add images to `outputs/{topic}/images/` directory

### Wrong Resolution

If videos have wrong resolution:

1. Check content code (L, M, S, R)
2. Verify mapping in `global_config.py` → `CONTENT_TYPES`
3. Check for any per-topic overrides (should not exist)

## Benefits

1. **Clear Visibility**: Images are no longer hidden by dark overlays
2. **Mobile Optimized**: Short and Reel videos use vertical format for social media
3. **Desktop Optimized**: Long and Medium videos use horizontal format
4. **Easy Troubleshooting**: Clear diagnostics for image collection issues
5. **Cleaner Display**: No topic title cluttering the screen
6. **Maintainable**: Single source of truth for video settings
