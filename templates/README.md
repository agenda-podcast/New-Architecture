# Blender Templates for Video Rendering

This directory contains Blender template files (`.blend`) used for video composition and effects application.

## Directory Structure

```
templates/
├── base_template.blend       # Base template (never modified by CI)
├── safe/                      # Minimal, professional templates (60% selection weight)
├── cinematic/                 # Film-quality templates (30% selection weight)
├── experimental/              # Bold, artistic templates (10% selection weight)
├── inventory.yml              # Template metadata and configuration
└── README.md                  # This file
```

## Configuration

### Social Effects Toggle

Social media style visual effects can be controlled via environment variables:

```bash
# Enable/disable social effects (default: enabled)
export ENABLE_SOCIAL_EFFECTS=true

# Set template selection style (default: auto)
# Options: 'auto', 'none', 'safe', 'cinematic', 'experimental'
export SOCIAL_EFFECTS_STYLE=auto
```

**Effect Styles**:
- `auto` - Weighted random selection (60% safe, 30% cinematic, 10% experimental)
- `none` - No effects, minimal template only
- `safe` - Forces safe category (professional, subtle effects)
- `cinematic` - Forces cinematic category (film-quality effects)
- `experimental` - Forces experimental category (bold, artistic effects)

### Graceful Degradation

When `ENABLE_SOCIAL_EFFECTS=false` or template files are missing:
- System falls back to minimal rendering
- No effects applied
- Videos still render successfully
- No errors or failures

This ensures the pipeline works even when template `.blend` files are not available.

## Image Processing

### Blurred Background Composites

For images smaller than target video resolution, the system automatically creates enhanced composites:

1. **Background Layer**: Image scaled to cover, blurred (sigma=20), darkened (brightness=-0.3)
2. **Foreground Layer**: Image scaled to contain (no crop), centered
3. **Vignette Effect**: Applied to darken edges
4. **Subtle Grain**: Added for texture

This feature is automatic and requires no configuration. It ensures all images look professional regardless of their original resolution.

**Example**:
- Target video: 1920x1080
- Source image: 640x480
- Output: Blurred background fills frame, original image centered, vignette and grain applied

## Template Categories

### Safe Templates (`safe/`)

**Purpose**: Minimal, professional effects suitable for all content types.

**Characteristics**:
- Subtle color correction
- Light film grain
- Smooth transitions
- No aggressive effects

**Selection Weight**: 60%

**Use Cases**:
- Corporate content
- Educational material
- News and information
- Default fallback

### Cinematic Templates (`cinematic/`)

**Purpose**: Film-quality effects for engaging, high-production content.

**Characteristics**:
- Dramatic color grading
- Ken Burns motion effects
- Film burns and light leaks
- Vignettes and bloom
- Moderate grain

**Selection Weight**: 30%

**Use Cases**:
- Entertainment content
- Storytelling
- Documentary-style
- Premium podcasts

### Experimental Templates (`experimental/`)

**Purpose**: Bold, artistic effects for creative and avant-garde content.

**Characteristics**:
- Strong color shifts
- Heavy vignettes
- Chromatic aberration
- Aggressive transitions
- High contrast

**Selection Weight**: 10%

**Use Cases**:
- Artistic projects
- Experimental content
- Niche creative work
- Special episodes

## Template Requirements

All templates must:

1. **Preserve Output Contract**:
   - Never modify resolution
   - Never modify FPS
   - Never modify codec settings

2. **Use Compositor Nodes**:
   - All effects via node groups
   - Effects must be toggleable (muted/unmuted)
   - No destructive operations

3. **Support Multiple Resolutions**:
   - Templates adapt to any resolution
   - No hardcoded dimensions
   - Aspect ratio aware

4. **Include Metadata**:
   - Template name
   - Category
   - Effect list
   - Intensity ranges

5. **Be Deterministic**:
   - Given the same seed, produce identical results
   - No random nodes without seed control

## Base Template

The `base_template.blend` file provides:

- **VSE Setup**: Empty sequence editor
- **Compositor Nodes**:
  - Color grading node group
  - Film grain node group
  - Vignette node group
  - Bloom/glow node group
  - Sharpen/soften node group
  - Chromatic aberration node group
- **Scene Settings**: Placeholder (overridden by output profile)
- **Custom Properties**: Template metadata

**Important**: The base template is NEVER modified by CI. It serves as a stable reference for creating new templates.

## Creating New Templates

### Step 1: Start from Base

```bash
# Copy base template
cp templates/base_template.blend templates/safe/my-new-template.blend
```

### Step 2: Open in Blender

```bash
blender templates/safe/my-new-template.blend
```

### Step 3: Configure Effects

1. Open Compositor workspace
2. Unmute desired effect node groups
3. Adjust effect parameters
4. Add custom nodes (optional)

### Step 4: Test

```bash
# Render test video
blender --background templates/safe/my-new-template.blend \
  --python scripts/blender/build_video.py \
  -- \
  --images test_data/images \
  --audio test_data/audio.m4a \
  --output test_output.mp4 \
  --profile long \
  --seed test123
```

### Step 5: Validate

```bash
# Validate output contract
python scripts/output_validator.py test_output.mp4 --type long
```

### Step 6: Document

Add template metadata to `templates/inventory.yml`:

```yaml
my-new-template:
  name: "My New Template"
  category: safe
  description: "A clean, minimal template with subtle effects"
  effects:
    - color_grade: "neutral"
    - grain: "light"
    - vignette: "subtle"
  intensity_range:
    min: 0.10
    max: 0.30
  incompatibilities: []
  preview: "templates/safe/previews/my-new-template.jpg"
```

## Effect Guidelines

### Do's ✓

- Use node groups for reusability
- Mute effects by default (unmute via script)
- Use relative intensities (0.0-1.0)
- Support seed-based randomization
- Provide intensity ranges
- Test with multiple resolutions
- Document incompatibilities

### Don'ts ✗

- Don't hardcode resolutions
- Don't modify FPS
- Don't change codec settings
- Don't use non-deterministic random nodes
- Don't create destructive operations
- Don't exceed 2-3 strong effects per template
- Don't ignore asset licenses

## Testing Templates

### Visual Smoke Test

```bash
# Test with sample images
python scripts/test_templates.py \
  --template templates/safe/my-template.blend \
  --images test_data/images \
  --output test_output/
```

### Validation Test

```bash
# Ensure output contract compliance
python scripts/validate_template.py \
  templates/safe/my-template.blend
```

### Regression Test

```bash
# Compare output with reference
python scripts/compare_template_output.py \
  templates/safe/my-template.blend \
  reference_outputs/my-template-reference.mp4
```

## Template Selection Algorithm

Templates are selected using weighted randomness:

```python
def select_template(seed, last_n_used):
    """
    Select template using weighted random selection.
    
    Args:
        seed: Deterministic seed
        last_n_used: List of recently used templates (avoid repeats)
    
    Returns:
        Selected template path
    """
    random.seed(seed)
    
    # Weighted category selection
    category = random.choices(
        ['safe', 'cinematic', 'experimental'],
        weights=[0.60, 0.30, 0.10]
    )[0]
    
    # Get available templates in category
    templates = list_templates(f'templates/{category}')
    
    # Exclude recently used
    templates = [t for t in templates if t not in last_n_used]
    
    # Select random template
    return random.choice(templates)
```

## Effect Incompatibilities

Some effects should not be combined:

| Effect 1          | Effect 2            | Reason                        |
|-------------------|---------------------|-------------------------------|
| Heavy glow        | Heavy sharpen       | Visual conflict               |
| Strong vignette   | Dark color grade    | Excessive darkness            |
| Film burn         | Light leaks         | Overexposure                  |
| High grain        | Chromatic aberr.    | Too many texture effects      |
| Fast transitions  | Ken Burns motion    | Motion sickness risk          |
| Strong blur       | High detail images  | Defeats purpose of details    |

Define incompatibilities in template metadata to prevent combinations.

## Troubleshooting

### Template Not Loading

**Problem**: Blender fails to load template

**Solution**:
1. Check file exists and is readable
2. Verify `.blend` file is not corrupted
3. Ensure Blender version compatibility (4.5+)
4. Check file permissions

### Effects Not Applying

**Problem**: Template effects don't appear in output

**Solution**:
1. Verify effects are unmuted in compositor
2. Check effect intensity is not zero
3. Ensure compositor is enabled
3. Verify node connections are correct

### Output Contract Violation

**Problem**: Validation fails after rendering

**Solution**:
1. Remove any hardcoded resolution settings
2. Don't modify scene FPS in template
3. Ensure render settings come from profile
4. Check for destructive scaling operations

### Inconsistent Results

**Problem**: Same template produces different outputs

**Solution**:
1. Verify seed is being passed correctly
2. Check for non-deterministic random nodes
3. Ensure no timestamp-based operations
4. Review effect randomization logic

## Contributing Templates

To contribute a new template:

1. **Create template** following guidelines above
2. **Test thoroughly** with multiple resolutions
3. **Validate output** meets contracts
4. **Document effects** in `inventory.yml`
5. **Provide preview** image (1920x1080)
6. **Submit PR** with template and documentation

### Template Review Checklist

- [ ] Template based on `base_template.blend`
- [ ] All effects via compositor nodes
- [ ] No hardcoded resolutions
- [ ] Output contract compliance verified
- [ ] Tested with horizontal and vertical formats
- [ ] Effects documented in `inventory.yml`
- [ ] Preview image provided
- [ ] Incompatibilities noted
- [ ] License compliance (if using assets)

## License

All templates in this directory are licensed under the MIT License unless otherwise specified.

See individual template directories for asset licenses.
