# Template Creation Guide

## Important Notice

**The actual `.blend` files must be created using Blender 4.5 LTS.**

This repository contains the configuration and metadata for templates, but the actual Blender files need to be created manually using Blender's GUI or scripting interface.

## Why Templates Are Not Included

`.blend` files are binary files that:
1. Cannot be created programmatically without Blender running
2. Require manual configuration of compositor nodes
3. Need visual testing and adjustment
4. Are relatively large (several MB each)

## Creating Templates

### Prerequisites

- Blender 4.5 LTS installed
- Basic understanding of Blender VSE and Compositor
- Access to this repository

### Step-by-Step Process

#### 1. Create Base Template First

```bash
# Launch Blender
blender
```

In Blender:
1. **Delete default scene** (cube, camera, light)
2. **Switch to Video Editing workspace**
3. **Enable Compositor**:
   - Window → Compositor
   - Check "Use Nodes"
4. **Create effect node groups**:
   - Color Grading node group
   - Film Grain node group
   - Vignette node group
   - Bloom/Glow node group
   - Sharpen/Soften node group
   - Chromatic Aberration node group
5. **Mute all effect nodes** (M key)
6. **Save as**: `templates/base_template.blend`

#### 2. Create Category-Specific Templates

For each template in `templates/inventory.yml`:

1. **Copy base template**:
   ```bash
   cp templates/base_template.blend templates/safe/minimal.blend
   ```

2. **Open in Blender**:
   ```bash
   blender templates/safe/minimal.blend
   ```

3. **Configure effects**:
   - Switch to Compositor workspace
   - Unmute required effect node groups
   - Adjust parameters per template spec
   - Test with sample images

4. **Save template**

5. **Generate preview**:
   - Render a test frame
   - Save as `templates/safe/previews/minimal.jpg`

#### 3. Test Template

```bash
# Test rendering with template
python scripts/test_template.py \
  --template templates/safe/minimal.blend \
  --images test_data/images \
  --audio test_data/audio.m4a \
  --profile long
```

#### 4. Validate Template

```bash
# Validate output contract compliance
python scripts/validate_template.py \
  templates/safe/minimal.blend
```

## Template Configuration Details

### Minimal Template (`safe/minimal.blend`)

**Effects**: None
**Purpose**: Clean, no-effects baseline

**Configuration**:
- All compositor nodes muted
- Direct pass-through from VSE to output

### Neutral Template (`safe/neutral.blend`)

**Effects**: Neutral color grade + light grain

**Configuration**:
1. Unmute "Color Grade" node group
2. Set to neutral preset (no strong adjustments)
3. Unmute "Grain" node group
4. Set grain intensity: 0.05-0.15
5. Set grain size: Fine

### Film Noir Template (`cinematic/film-noir.blend`)

**Effects**: Noir grade + vignette + medium grain + high contrast

**Configuration**:
1. Unmute "Color Grade" node group
2. Apply noir LUT or:
   - Desaturate to grayscale
   - Increase contrast (1.5x)
   - Crush blacks (lift shadows)
3. Unmute "Vignette" node group
4. Set vignette strength: 0.30-0.60
5. Unmute "Grain" node group
6. Set grain intensity: 0.20-0.40

### Golden Hour Template (`cinematic/golden-hour.blend`)

**Effects**: Warm color grade + soft bloom + light grain

**Configuration**:
1. Unmute "Color Grade" node group
2. Apply warm LUT or:
   - Shift hue toward orange/yellow
   - Increase warmth (+20%)
   - Boost highlights gently
3. Unmute "Bloom" node group
4. Set bloom threshold: 0.8
5. Set bloom intensity: 0.20-0.50
6. Unmute "Grain" node group
7. Set grain intensity: 0.10-0.20

## Compositor Node Setup

### Color Grading Node Group

```
Input → Color Balance (Lift/Gamma/Gain)
      → Hue/Saturation
      → RGB Curves (S-curve for contrast)
      → Color Correction
      → Output
```

### Film Grain Node Group

```
Input → Noise Texture (UV mapped)
      → Color Ramp (adjust grain look)
      → Mix RGB (overlay mode, low factor)
      → Output
```

### Vignette Node Group

```
Input → Ellipse Mask (feathered)
      → Color Ramp (black to white)
      → Mix RGB (multiply mode)
      → Output
```

### Bloom/Glow Node Group

```
Input → Glare Node (fog glow or simple star)
      → Blur (Gaussian, small radius)
      → Mix RGB (add mode, low factor)
      → Output
```

### Sharpen/Soften Node Group

```
Input → Filter Node (sharpen or soften)
      → Mix (control intensity)
      → Output
```

### Chromatic Aberration Node Group

```
Input → Separate RGBA
      → Transform Red channel (offset X: +2px)
      → Transform Blue channel (offset X: -2px)
      → Combine RGBA
      → Output
```

## Testing Checklist

Before marking a template as complete:

- [ ] Template loads without errors
- [ ] Effects apply correctly
- [ ] No hardcoded resolutions
- [ ] Works with 1920x1080 (horizontal)
- [ ] Works with 1080x1920 (vertical)
- [ ] Output passes validation
- [ ] Resolution matches profile exactly
- [ ] FPS matches profile exactly
- [ ] Codec matches profile exactly
- [ ] Duration is reasonable
- [ ] Visual quality is acceptable
- [ ] Effects intensity is appropriate
- [ ] No visual artifacts
- [ ] Preview image generated
- [ ] Metadata updated in inventory.yml

## Placeholder Files

Until templates are created in Blender, placeholder files can be used:

```bash
# Create placeholder .blend files (empty)
touch templates/base_template.blend
touch templates/safe/minimal.blend
touch templates/safe/neutral.blend
touch templates/safe/clean.blend
touch templates/cinematic/film-noir.blend
touch templates/cinematic/golden-hour.blend
touch templates/cinematic/teal-orange.blend
touch templates/cinematic/vintage-film.blend
touch templates/experimental/neon-glow.blend
touch templates/experimental/glitch.blend
touch templates/experimental/high-contrast.blend
```

**Note**: These placeholders won't work for rendering. They serve as documentation of which templates need to be created.

## Contributing Templates

If you create templates:

1. **Test thoroughly** with multiple image sets
2. **Validate** output contracts
3. **Document** in `inventory.yml`
4. **Provide previews** (1920x1080 JPG)
5. **Submit PR** with:
   - `.blend` files
   - Preview images
   - Updated `inventory.yml`
   - Any custom assets with licenses

## Getting Help

- **Blender documentation**: https://docs.blender.org/
- **VSE tutorials**: https://www.youtube.com/results?search_query=blender+vse+tutorial
- **Compositor tutorials**: https://www.youtube.com/results?search_query=blender+compositor+tutorial

## Next Steps

After creating templates:

1. Test with `scripts/test_template.py`
2. Validate with `scripts/output_validator.py`
3. Update this guide with any learnings
4. Create more templates as needed
5. Document best practices

---

**Status**: Templates need to be created in Blender 4.5 LTS  
**Priority**: Medium (Blender scripts can work with simple templates initially)
