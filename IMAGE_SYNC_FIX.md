# Image Synchronization Fix for Black Screen Issue

## Problem Statement

Videos were showing black screens instead of images because of a race condition between image downloading and video rendering. The video generation process was attempting to use images before they were fully written to disk.

## Root Cause

When Python writes files using `write()`, the data may be buffered at multiple levels:
1. **Python's internal buffer**: File object maintains its own buffer
2. **OS buffer cache**: Operating system buffers writes before committing to disk

Without explicit synchronization, files appear "written" from Python's perspective but may not yet be physically on disk. This created a timing window where:
1. Image collector writes image data
2. Image collector returns success
3. Video renderer starts immediately
4. OS hasn't finished writing images to disk yet
5. Video renderer finds no images or incomplete images → black screen

## Solution Implementation

### 1. File Synchronization (`scripts/image_collector.py`)

**Change**: Added `os.fsync()` after writing each image

```python
# Before (race condition exists)
with open(image_path, 'wb') as f:
    f.write(image_data)
    # File might not be on disk yet!

# After (synchronized)
with open(image_path, 'wb') as f:
    f.write(image_data)
    os.fsync(f.fileno())  # Force OS to write to disk
```

**Effect**: Creates a synchronization barrier ensuring each image is physically on disk before continuing.

### 2. Post-Download Verification (`scripts/image_collector.py`)

**Change**: Added verification loop after downloading all images

```python
# Verify all downloaded images exist and are readable
logger.info("Verifying downloaded images...")
verified_images = []
for img_path in downloaded_images:
    if img_path.exists():
        file_size = img_path.stat().st_size
        if file_size > 0:
            verified_images.append(img_path)
```

**Effect**: Double-checks that all images are accessible and non-empty before returning.

### 3. Image Discovery Fix (`scripts/video_render.py`)

**Change**: Fixed existing bug where only `.jpg` and `.png` were checked

```python
# Before (missing .jpeg and .webp)
existing_images = list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.png'))

# After (all supported formats)
existing_images = discover_images(images_dir)  # Checks .jpg, .jpeg, .png, .webp
```

**Effect**: Correctly detects all downloaded images, preventing unnecessary re-downloads.

### 4. Pre-Rendering Verification (`scripts/video_render.py`)

**Change**: Added verification before starting video rendering

```python
# Verify all images are accessible and have content
print(f"Verifying image files are readable...")
verified_images = []
for img_file in image_files:
    file_size = img_file.stat().st_size
    if file_size > 0:
        verified_images.append(img_file)
```

**Effect**: Final safety check ensures only valid images are used for video generation.

## Testing

Created `scripts/test_image_sync.py` with comprehensive tests:
- ✅ File sync operations work correctly
- ✅ Verification logic filters invalid files
- ✅ Empty files are properly detected and skipped

All existing tests continue to pass:
- ✅ `scripts/test_video_render.py` - Video rendering tests
- ✅ `scripts/test_image_sync.py` - Image sync tests

## Technical Benefits

1. **Eliminates Race Condition**: Synchronization barrier ensures images are on disk
2. **Multiple Verification Layers**: Catches issues at download, post-download, and pre-render stages
3. **Better Error Messages**: Clear warnings when images fail verification
4. **Maintains Performance**: Only one `fsync()` per image, minimal overhead
5. **Robust**: Handles edge cases like empty files, permission errors, etc.

## How to Verify the Fix

1. **Run the pipeline**:
   ```bash
   python scripts/run_pipeline.py --topic topic-01
   ```

2. **Check for verification messages**:
   ```
   IMAGE COLLECTION COMPLETE: 10/10 images
   Verifying downloaded images...
   ✓ All 10 images verified successfully
   
   Verifying image files are readable...
   ✓ All 10 images verified
   ```

3. **Verify video has images** (not black screen):
   ```bash
   ffmpeg -i outputs/topic-01/topic-01-YYYYMMDD-L1.mp4 -vframes 1 test.jpg
   ```
   The extracted frame should show an actual image, not black screen.

## Related Files

- `scripts/image_collector.py` - Downloads and verifies images
- `scripts/video_render.py` - Renders videos using images
- `scripts/test_image_sync.py` - Tests for the fix
- `scripts/test_video_render.py` - Existing video tests

## Performance Impact

**Minimal**: `os.fsync()` adds ~1-10ms per image on modern SSDs. For 10 images, total overhead is ~10-100ms, which is negligible compared to:
- Image download time: ~500-2000ms per image
- Video rendering time: ~30-120 seconds per video

The reliability gained far outweighs the minimal performance cost.
