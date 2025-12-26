# Blender Video Rendering Scripts

This directory contains Python scripts that run inside Blender to generate videos with cinematic effects.

## Overview

The Blender rendering system replaces FFmpeg-based composition while preserving output quality and specifications. Blender handles:

- Image composition and sequencing
- Cinematic effects (color grading, grain, transitions)
- Audio integration
- Video encoding (via Blender's built-in FFmpeg)

## Scripts

### `build_video.py`

Main video builder script that runs inside Blender.

**Usage**:
```bash
blender --background \
  --python scripts/blender/build_video.py \
  -- \
  --images outputs/topic-01/images \
  --audio outputs/topic-01/topic-01-20251219-L1.m4a \
  --output outputs/topic-01/topic-01-20251219-L1.mp4 \
  --profile long \
  --template templates/safe/minimal.blend \
  --seed a3f9b2c1d5e6
```

**Arguments**:
- `--images`: Directory containing images
- `--audio`: Path to audio file (.m4a)
- `--output`: Path to output video file (.mp4)
- `--profile`: Output profile (long, medium, short, reels)
- `--template`: Path to Blender template file (optional)
- `--seed`: Random seed for effects (optional, auto-generated if not provided)
- `--duration`: Audio duration in seconds (optional, used to set timeline length)
- `--no-audio`: Skip loading audio into Blender for video-only rendering (optional, requires --duration)

**Process**:
1. Load output profile from `config/output_profiles.yml`
2. Load Blender template (if provided)
3. Configure scene (resolution, FPS, codec, audio settings)
4. Load images into VSE
5. Load audio into VSE (skipped when --no-audio is used)
6. Apply template effects
7. Render video with FFmpeg encoder (video-only when --no-audio is used)
8. Save render manifest

**Video-Only Rendering**:
When using `--no-audio` flag (used by `video_render.py` for the two-step render process):
- Blender renders only the video track without audio
- Audio codec is set to 'NONE' to prevent FFmpeg encoding errors
- Timeline duration must be specified with `--duration`
- The video-only output is later muxed with audio using external FFmpeg

**Output**:
- Video file (e.g., `topic-01-20251219-L1.mp4`)
- Render manifest (e.g., `topic-01-20251219-L1.manifest.json`)

### `template_selector.py`

Template selection module with weighted randomness.

**Usage**:
```python
from template_selector import TemplateSelector, generate_deterministic_seed

# Initialize selector
selector = TemplateSelector(templates_dir, inventory_path)

# Generate seed
seed = generate_deterministic_seed('topic-01', '20251219', 'L1')

# Select template
template = selector.select_template(seed, style='auto')
template_path = selector.get_template_path(template['id'])
```

**Features**:
- Weighted random selection (60% safe, 30% cinematic, 10% experimental)
- Deterministic based on seed
- Avoids recently used templates
- Effect compatibility checking
- Style forcing (`none`, `safe`, `cinematic`, `experimental`)

**Test**:
```bash
cd scripts/blender
python template_selector.py
```

## Integration with video_render.py

The existing `video_render.py` script can be updated to use Blender:

```python
# Instead of create_text_overlay_video() with FFmpeg
# Use Blender builder:

from blender.template_selector import TemplateSelector, generate_deterministic_seed

# Select template
seed = generate_deterministic_seed(topic_id, date_str, content_code)
selector = TemplateSelector(templates_dir, inventory_path)
template = selector.select_template(seed, style='auto')
template_path = selector.get_template_path(template['id'])

# Build video with Blender
subprocess.run([
    'blender', '--background',
    '--python', 'scripts/blender/build_video.py',
    '--',
    '--images', str(images_dir),
    '--audio', str(audio_path),
    '--output', str(video_path),
    '--profile', content_type,
    '--template', str(template_path),
    '--seed', seed
], check=True)
```

## Output Validation

After rendering, validate output:

```bash
python scripts/output_validator.py \
  outputs/topic-01/topic-01-20251219-L1.mp4 \
  --type long
```

This ensures the video meets exact specifications:
- Resolution (1920x1080 or 1080x1920)
- FPS (30)
- Codec (libx264, aac)
- Duration (within expected range)

## Render Manifest

Each video produces a manifest file:

```json
{
  "video_path": "outputs/topic-01/topic-01-20251219-L1.mp4",
  "resolution": "1920x1080",
  "fps": 30,
  "duration": 2438.5,
  "template": {
    "path": "templates/safe/minimal.blend",
    "name": "minimal"
  },
  "effects": [],
  "seed": "a3f9b2c1d5e6",
  "render_time": 325.7,
  "blender_version": "4.5.0",
  "timestamp": "2025-12-19T03:45:00Z"
}
```

**Uses**:
- Debugging render issues
- Tracking which effects were used
- Reproducibility (re-render with same seed)
- Performance monitoring
- Effect analytics

## Dependencies

**Blender**: 4.5 LTS or higher

**Python packages** (must be available to Blender's Python):
- `yaml` (PyYAML)
- Standard library modules

**Note**: Blender comes with its own Python interpreter. You may need to install packages into Blender's Python:

```bash
# Linux
/path/to/blender/4.5/python/bin/python3.11 -m pip install PyYAML

# macOS
/Applications/Blender.app/Contents/Resources/4.5/python/bin/python3.11 -m pip install PyYAML
```

## Troubleshooting

### "Blender Python API not available"

**Problem**: Script imported outside of Blender

**Solution**: Only run scripts using `blender --background --python`

### "Output profiles not found"

**Problem**: Cannot locate `config/output_profiles.yml`

**Solution**: Ensure you run from repository root or update path resolution

### "Template file not found"

**Problem**: Template `.blend` file doesn't exist

**Solution**: 
1. Check `templates/inventory.yml` for correct path
2. Create template following `templates/TEMPLATE_CREATION_GUIDE.md`
3. Use `--template` argument to specify existing template

### "Render failed with codec error"

**Problem**: Unsupported codec or format

**Solution**:
1. Verify Blender was compiled with FFmpeg support
2. Check `output_profiles.yml` codec settings
3. Ensure system FFmpeg libraries are available

### "No images found"

**Problem**: Images directory is empty or path is wrong

**Solution**:
1. Verify images were collected by `image_collector.py`
2. Check `--images` path is correct
3. Ensure images have supported extensions (.jpg, .png, .webp)

### "Audio duration mismatch"

**Problem**: Video shorter/longer than audio

**Solution**: This is handled automatically - VSE sets end frame to audio duration

### "FFmpeg mux failed with exit code 254"

**Problem**: Blender's internal FFmpeg fails when trying to encode audio that doesn't exist

**Solution**: This issue has been fixed. When using `--no-audio` flag, the audio codec is now set to 'NONE' to prevent FFmpeg from attempting to encode audio. If you still encounter this error:
1. Ensure you're using the latest version of `build_video.py`
2. Verify that `--duration` is specified when using `--no-audio`
3. Check that the audio codec is set to 'NONE' in Blender's render settings

## Performance

**Render times** (approximate on modern hardware):

- Short (5 min): ~2-3 minutes
- Medium (15 min): ~5-8 minutes
- Long (45 min): ~15-20 minutes
- Reels (30 sec): ~30-60 seconds

**Factors affecting performance**:
- Number of effects enabled
- Resolution (1080p vs vertical)
- Compositor complexity
- Hardware (CPU, GPU if supported)

**Optimization tips**:
- Use minimal templates for faster renders
- Disable unused effect nodes
- Render on machines with more CPU cores
- Use GPU acceleration if available (CUDA/OptiX)

## Future Enhancements

Planned features:

- **Audio-reactive effects**: Sync visuals to audio beats
- **Text animations**: Animated titles, lower thirds
- **Transitions**: Cross-fade, zoom transitions between images
- **Ken Burns motion**: Pan and zoom on static images
- **GPU acceleration**: Use GPU for faster rendering
- **Preview mode**: Quick low-res preview before final render
- **Batch rendering**: Render multiple videos in parallel

## References

- [Blender Python API](https://docs.blender.org/api/current/)
- [Blender VSE Documentation](https://docs.blender.org/manual/en/latest/video_editing/index.html)
- [Blender Compositor](https://docs.blender.org/manual/en/latest/compositing/index.html)
- [FFmpeg in Blender](https://docs.blender.org/manual/en/latest/render/output/properties/output.html)
