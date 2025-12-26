# Video Rendering Pipeline Documentation

## Architecture Overview

The video rendering pipeline has migrated from FFmpeg-based composition to **Blender 4.5 LTS** as the composition and VFX engine, while preserving FFmpeg as the internal encoder backend (via Blender's FFmpeg integration).

### Key Principles

1. **Output Contract First**: All video outputs must meet exact specifications defined in `config/output_profiles.yml`
2. **Templates Define Appearance**: Blender templates control visual style without affecting resolution, FPS, or codec
3. **Controlled Randomness**: Each video is visually distinct but follows quality guidelines
4. **Validation Required**: Post-render validation ensures output contracts are met

---

## Pipeline Stages

### Stage 1: Input Preparation

**Purpose**: Organize and validate inputs for video generation

**Inputs**:
- Images (from `outputs/{topic}/images/`)
- Audio file (`.m4a` format)
- Chapters metadata (optional)

**Process**:
1. Discover and verify all image files
2. Sort images lexicographically by filename
3. Validate audio file exists and is readable
4. Load chapter metadata if available

**Outputs**:
- List of validated image paths
- Audio file path
- Chapter data (if available)

---

### Stage 2: Blender Build

**Purpose**: Generate video using Blender VSE (Video Sequence Editor) with cinematic effects

**Inputs**:
- Validated images and audio
- Output profile from `output_profiles.yml`
- Selected template (safe/cinematic/experimental)
- Random seed (for deterministic randomness)

**Process**:
1. Load Blender template (`.blend` file)
2. Configure scene from output profile:
   - Set resolution (width × height)
   - Set FPS
   - Set color space
3. Load images into VSE
4. Fit/crop images to target aspect ratio
5. Apply template effects:
   - Transitions (cross-zoom, film burn, whip, hard cut)
   - Motion (Ken Burns, micro-shake)
   - Color grading (LUTs, contrast)
   - Overlays (grain, dust, light leaks)
6. Add audio track
7. Render animation using profile codec settings
8. Generate `render_manifest.json`

**Outputs**:
- Rendered video (`.mp4`)
- Render manifest (metadata, effects used, seed)

**Script**: `scripts/blender/build_video.py`

---

### Stage 3: Post-Render Validation

**Purpose**: Verify output meets exact specifications

**Inputs**:
- Rendered video
- Content type (long/medium/short/reels)

**Process**:
1. Extract video metadata using `ffprobe`
2. Compare against profile requirements:
   - Resolution (exact match)
   - FPS (exact match)
   - Video codec (exact match)
   - Audio codec (exact match)
   - Pixel format
   - Duration (within range)
   - Container format
3. Generate validation report

**Outputs**:
- Validation status (pass/fail/pass_with_warnings)
- Detailed validation report

**Script**: `scripts/output_validator.py`

**Failure Handling**: If validation fails, the pipeline should fail and not proceed

---

## Blender Template System

### Template Structure

Each template is a `.blend` file containing:

1. **VSE Setup**: Empty sequence editor ready for image/audio import
2. **Compositor Nodes**: Pre-configured effect nodes (muted by default)
3. **Scene Settings**: Placeholder settings (overridden by profile)
4. **Custom Properties**: Template metadata and configuration

### Template Categories

#### 1. Safe Templates (`templates/safe/`)

**Purpose**: Minimal, professional effects that work for all content

**Characteristics**:
- Subtle color correction
- Light film grain
- Smooth transitions
- No aggressive effects

**Use Case**: Default for most content, corporate/professional use

**Selection Weight**: 60%

#### 2. Cinematic Templates (`templates/cinematic/`)

**Purpose**: Film-quality effects for engaging content

**Characteristics**:
- Dramatic color grading
- Ken Burns motion
- Film burns and light leaks
- Vignettes and bloom
- Moderate grain

**Use Case**: Entertainment, storytelling, high-production content

**Selection Weight**: 30%

#### 3. Experimental Templates (`templates/experimental/`)

**Purpose**: Bold, artistic effects for creative content

**Characteristics**:
- Strong color shifts
- Heavy vignettes
- Chromatic aberration
- Aggressive transitions
- High contrast

**Use Case**: Avant-garde, artistic, experimental content

**Selection Weight**: 10%

### Base Template (`templates/base_template.blend`)

The base template provides the foundation for all other templates.

**Features**:
- VSE enabled
- Empty scene (no fixed resolution)
- Compositor enabled with node groups:
  - Color grading node group
  - Film grain node group
  - Vignette node group
  - Bloom/glow node group
  - Sharpen/soften node group
  - Chromatic aberration node group

**All effects are toggleable** (muted/unmuted) via Blender's node muting system.

**The base template is never modified by CI** - it serves as a stable reference.

---

## Cinematic Effects Library

### 1. Transitions

**Cross-Zoom**:
- Smooth zoom-in/zoom-out between images
- Duration: 0.5-1.0 seconds
- Intensity: Configurable

**Film Burn**:
- Vintage film transition effect
- Simulates overexposed film
- Duration: 0.3-0.8 seconds

**Whip Pan**:
- Fast horizontal/vertical swipe
- Motion blur effect
- Duration: 0.2-0.5 seconds

**Hard Cut** (default):
- Instant transition
- No motion
- Duration: 0 seconds

### 2. Motion Effects

**Ken Burns**:
- Slow pan and zoom on static images
- Simulates camera movement
- Duration: Per image (3-8 seconds)
- Direction: Random (left/right/up/down)

**Micro-Shake**:
- Subtle camera shake
- Adds organic feel
- Amplitude: 1-3 pixels

### 3. Color Grading

**LUTs** (Look-Up Tables):
- Film emulation LUTs
- Color grading presets
- Format: `.cube` files

**Contrast Models**:
- S-curve contrast
- Lift/gamma/gain adjustments
- Saturation control

### 4. Overlays

**Film Grain**:
- Adds organic texture
- Grain size: Configurable
- Intensity: 5-20%

**Dust/Scratches**:
- Vintage film artifacts
- Opacity: 10-30%

**Light Leaks**:
- Colored lens flares
- Simulates light hitting film
- Intensity: 20-50%

### 5. Typography (Future)

**Titles**:
- Opening title cards
- Font: Configurable
- Animation: Fade in/out

**Lower Thirds**:
- Speaker names, topics
- Position: Bottom 1/3 of frame
- Style: Minimal, clean

---

## Controlled Randomness

### Deterministic Seeds

Each video gets a unique seed based on:
```
seed = hash(topic_id + date + content_code + index)
```

**Benefits**:
- Reproducible results
- Consistent behavior in CI
- Debugging-friendly

### Template Selection Algorithm

```python
def select_template(seed, last_n_templates):
    random.seed(seed)
    
    # Weighted random selection
    weights = {
        'safe': 0.60,      # 60%
        'cinematic': 0.30,  # 30%
        'experimental': 0.10 # 10%
    }
    
    # Select category
    category = random.choices(
        list(weights.keys()),
        weights=list(weights.values())
    )[0]
    
    # Select specific template from category
    available_templates = list_templates(category)
    
    # Exclude recently used templates
    available_templates = [
        t for t in available_templates
        if t not in last_n_templates
    ]
    
    return random.choice(available_templates)
```

### Effect Intensity Randomization

Within a template, effect intensities are randomized:

```python
grain_intensity = random.uniform(0.05, 0.20)  # 5-20%
vignette_strength = random.uniform(0.10, 0.30)  # 10-30%
```

**Constraints**:
- Max 2-3 strong effects per video
- Always include one stabilizing element (neutral grade)
- Respect incompatibilities

### Template Incompatibilities

Some effects shouldn't be combined:

| Effect 1          | Effect 2         | Reason                    |
|-------------------|------------------|---------------------------|
| Heavy glow        | Heavy sharpen    | Visual conflict           |
| Strong vignette   | Dark images      | Too much darkness         |
| Film burn         | Light leaks      | Overexposure overkill     |
| High grain        | Chromatic aberr. | Too many texture effects  |

---

## Asset Management

### Asset Categories

1. **LUTs** (`assets/luts/`)
   - Film emulation LUTs
   - Creative color grades
   - Format: `.cube` files

2. **Overlays** (`assets/overlays/`)
   - Film grain textures
   - Dust/scratch overlays
   - Light leak effects
   - Format: `.png` (with alpha channel)

3. **Fonts** (`assets/fonts/`)
   - Title fonts
   - Body fonts
   - Format: `.ttf`, `.otf`

4. **SFX** (`assets/sfx/` - optional)
   - Transition sounds
   - Ambient effects
   - Format: `.wav`, `.mp3`

### Asset Requirements

1. **Open or Permissive Licenses**:
   - CC0 (Public Domain)
   - CC-BY (Attribution)
   - MIT/BSD-style licenses

2. **Quality Standards**:
   - LUTs: Industry-standard `.cube` format
   - Overlays: High resolution (≥1920px)
   - Fonts: Professional quality

3. **Metadata**:
   - License file (`LICENSE.txt` per asset)
   - Source attribution (`ATTRIBUTION.txt`)
   - Usage notes (`README.md`)

### Asset Directory Structure

```
assets/
├── luts/
│   ├── film-emulation/
│   │   ├── kodak-5219.cube
│   │   ├── fuji-eterna.cube
│   │   └── LICENSE.txt
│   ├── creative/
│   │   ├── cinematic-teal-orange.cube
│   │   ├── vintage-warm.cube
│   │   └── LICENSE.txt
│   └── README.md
├── overlays/
│   ├── grain/
│   │   ├── grain-fine.png
│   │   ├── grain-medium.png
│   │   ├── grain-coarse.png
│   │   └── LICENSE.txt
│   ├── dust/
│   │   ├── dust-light.png
│   │   ├── dust-heavy.png
│   │   └── LICENSE.txt
│   ├── light-leaks/
│   │   ├── leak-warm.png
│   │   ├── leak-cool.png
│   │   └── LICENSE.txt
│   └── README.md
├── fonts/
│   ├── montserrat/
│   │   ├── Montserrat-Regular.ttf
│   │   ├── Montserrat-Bold.ttf
│   │   └── LICENSE.txt
│   └── README.md
└── LICENSE-SUMMARY.md
```

---

## Output Guarantees

### Non-Negotiable Requirements

Templates and effects **MUST NOT**:
1. Change resolution
2. Change FPS
3. Change aspect ratio
4. Modify codec settings

### What Templates CAN Do

Templates **MAY**:
1. Apply color grading
2. Add overlays and textures
3. Animate images (pan, zoom)
4. Add transitions
5. Apply filters (blur, sharpen, etc.)

### Validation Enforcement

Post-render validation checks:
- Resolution: **Exact match required**
- FPS: **Exact match required**
- Codec: **Exact match required**
- Pixel format: **Warning if mismatch**
- Duration: **Warning if outside range**

**If validation fails, CI must fail.**

---

## Render Manifest

Each video produces a `render_manifest.json` file:

```json
{
  "video_path": "outputs/topic-01/topic-01-20251219-L1.mp4",
  "content_type": "long",
  "resolution": "1920x1080",
  "fps": 30,
  "duration": 2438.5,
  "template": {
    "category": "cinematic",
    "name": "film-noir",
    "path": "templates/cinematic/film-noir.blend"
  },
  "effects": [
    {
      "type": "color_grade",
      "name": "kodak-5219",
      "intensity": 0.75
    },
    {
      "type": "grain",
      "intensity": 0.15
    },
    {
      "type": "vignette",
      "strength": 0.25
    },
    {
      "type": "transition",
      "name": "cross-zoom",
      "duration": 0.8
    }
  ],
  "seed": "a3f9b2c1d5e6",
  "render_time": 325.7,
  "blender_version": "4.5.0",
  "timestamp": "2025-12-19T03:42:15Z"
}
```

**Uses**:
- Debugging
- Quality control
- A/B testing
- Effect analytics
- Reproducibility

---

## Implementation Notes

### Blender Headless Mode

Blender runs in headless mode (no GUI) on CI:

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

### CI Integration

GitHub Actions workflow steps:

1. **Download Blender 4.5 LTS**:
   ```bash
   wget https://download.blender.org/release/Blender4.5/blender-4.5.0-linux-x64.tar.xz
   tar -xf blender-4.5.0-linux-x64.tar.xz
   ```

2. **Cache Blender**:
   - Use GitHub Actions cache
   - Key: `blender-4.5.0-linux-x64`

3. **Render Video**:
   ```bash
   ./blender-4.5.0-linux-x64/blender --background --python ...
   ```

4. **Validate Output**:
   ```bash
   python scripts/output_validator.py \
     outputs/topic-01/topic-01-20251219-L1.mp4 \
     --type long
   ```

5. **Upload Artifacts**:
   - Video file
   - Render manifest
   - Preview frame (first frame as `.jpg`)

---

## Future Enhancements

### Phase 2+ Features

- **Audio-reactive effects**: Sync visuals to audio beats
- **Text animations**: Animated titles and lower thirds
- **3D elements**: Camera moves, depth effects
- **ML-based framing**: Smart crop based on image content
- **Multi-track audio**: Background music, SFX layers
- **Real-time previews**: Web-based preview system
- **Template marketplace**: Community-contributed templates

---

## References

- [Blender VSE Documentation](https://docs.blender.org/manual/en/latest/video_editing/index.html)
- [Blender Python API](https://docs.blender.org/api/current/)
- [FFmpeg Encoding Guide](https://trac.ffmpeg.org/wiki/Encode/H.264)
- [Color Grading with LUTs](https://en.wikipedia.org/wiki/3D_lookup_table)
