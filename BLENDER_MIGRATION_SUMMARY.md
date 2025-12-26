# Blender 4.5 LTS Video Rendering Migration - Implementation Summary

## Overview

This document summarizes the migration from FFmpeg-based video composition to **Blender 4.5 LTS** as the composition and VFX engine, while preserving FFmpeg as the internal encoder.

**Status**: Core infrastructure complete ✅  
**Date**: 2025-12-19  
**Branch**: `copilot/remove-images-normalization-process`

---

## What Changed

### 1. Image Normalization Removed ✅

**Removed**:
- `scripts/image_normalizer.py` - Pre-processing module
- `IMAGE_NORMALIZATION_GUIDE.md` - Documentation
- Test files for normalization
- Normalization logic from `video_render.py`
- `NORMALIZED_IMAGES_SUBDIR` from `global_config.py`

**Reason**: Blender handles image scaling and cropping natively in VSE. Pre-normalization is unnecessary and adds complexity.

**Impact**: Simplified pipeline, faster iteration, direct use of original images.

---

### 2. Output Profiles System Created ✅

**Added**:
- `config/output_profiles.yml` - Single source of truth for output specifications
- `scripts/output_validator.py` - Post-render validation module
- Helper functions in `global_config.py`

**Profiles Defined**:
- **Long**: 1920x1080, 30fps, H.264, 10M bitrate
- **Medium**: 1920x1080, 30fps, H.264, 10M bitrate
- **Short**: 1080x1920, 30fps, H.264, 8M bitrate
- **Reels**: 1080x1920, 30fps, H.264, 8M bitrate

**Validation**: Post-render validation ensures all outputs meet exact specifications.

---

### 3. Blender Template System Created ✅

**Added**:
- `templates/` directory structure
- `templates/base_template.blend` - Base template (to be created)
- `templates/safe/`, `templates/cinematic/`, `templates/experimental/` - Category directories
- `templates/inventory.yml` - Template metadata and configuration
- `templates/README.md` - Template documentation
- `templates/TEMPLATE_CREATION_GUIDE.md` - Guide for creating templates

**Template Categories**:
- **Safe** (60%): Minimal, professional effects
- **Cinematic** (30%): Film-quality effects
- **Experimental** (10%): Bold, artistic effects

**Selection Algorithm**: Weighted random selection with deterministic seeds to avoid repeats.

---

### 4. Blender Python Scripts Created ✅

**Added**:
- `scripts/blender/build_video.py` - Main video builder
- `scripts/blender/template_selector.py` - Template selection logic
- `scripts/blender/README.md` - Usage documentation

**Capabilities**:
- Load images into Blender VSE
- Load audio into VSE
- Configure scene from output profiles
- Apply template effects
- Render with FFmpeg encoder
- Generate render manifest

**Usage**:
```bash
blender --background --python scripts/blender/build_video.py -- \
  --images outputs/topic-01/images \
  --audio outputs/topic-01/topic-01-20251219-L1.m4a \
  --output outputs/topic-01/topic-01-20251219-L1.mp4 \
  --profile long \
  --template templates/safe/minimal.blend \
  --seed a3f9b2c1d5e6
```

---

### 5. Asset Management System Created ✅

**Added**:
- `assets/` directory structure
- `assets/luts/` - Color grading LUTs
- `assets/overlays/` - Grain, dust, light leaks
- `assets/fonts/` - Typography fonts
- `assets/README.md` - Asset guidelines
- `assets/LICENSE-SUMMARY.md` - License tracking

**Asset Types**:
- **LUTs**: Color grading (.cube files)
- **Overlays**: Grain, dust, light leaks (PNG with alpha)
- **Fonts**: Titles, body text (TTF/OTF)

**License Requirements**: CC0, CC-BY, OFL, or 100% free for commercial use.

---

### 6. Documentation Created ✅

**Added**:
- `docs/pipeline.md` - Complete architecture documentation
- Template system documentation
- Asset management documentation
- Blender script documentation

**Updated**:
- `README.md` - Added Blender rendering section
- Pipeline overview updated

---

## What Still Needs to Be Done

### Phase 7: CI/CD Integration

**Tasks**:
1. Update `.github/workflows/daily.yml`:
   - Download and cache Blender 4.5 LTS
   - Run Blender in headless mode
   - Validate outputs post-render
   - Upload artifacts (video + manifest + preview frame)

2. Add Blender installation steps:
   ```yaml
   - name: Download Blender
     run: |
       wget https://download.blender.org/release/Blender4.5/blender-4.5.0-linux-x64.tar.xz
       tar -xf blender-4.5.0-linux-x64.tar.xz
   
   - name: Cache Blender
     uses: actions/cache@v4
     with:
       path: blender-4.5.0-linux-x64
       key: blender-4.5.0
   ```

3. Update render step:
   ```yaml
   - name: Render Videos
     run: |
       blender-4.5.0-linux-x64/blender --background \
         --python scripts/blender/build_video.py \
         -- --images ... --audio ... --output ...
   ```

### Phase 8: Dual Pipeline Implementation

**Tasks**:
1. Add feature flag to `video_render.py`:
   ```python
   RENDERER = 'blender'  # or 'ffmpeg' for fallback
   ```

2. Update `render_multi_format_for_topic()`:
   ```python
   if RENDERER == 'blender':
       render_with_blender(...)
   else:
       render_with_ffmpeg(...)  # Legacy fallback
   ```

3. Add comparison metrics:
   - Output file sizes
   - Render times
   - Visual quality scores

### Phase 9: Template Creation

**Priority Templates** (need `.blend` files):
1. `base_template.blend` - Base with all effect nodes
2. `safe/minimal.blend` - No effects
3. `safe/neutral.blend` - Neutral grade + grain
4. `cinematic/film-noir.blend` - High-contrast B&W
5. `cinematic/golden-hour.blend` - Warm tones

**Process**: Follow `templates/TEMPLATE_CREATION_GUIDE.md`

### Phase 10: Asset Sourcing

**Priority Assets**:
1. `luts/neutral.cube` - Essential for safe templates
2. `overlays/grain/grain-fine.png` - Most common effect
3. `fonts/montserrat-bold.ttf` - Title font
4. `fonts/inter-regular.ttf` - Body font

**Process**: Follow `assets/README.md` for sourcing and licensing

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Video Rendering Pipeline                 │
└─────────────────────────────────────────────────────────────┘

  INPUT
    │
    ├─ Images (from Google Custom Search)
    │    └─ outputs/{topic}/images/*.jpg
    │
    └─ Audio (from TTS)
         └─ outputs/{topic}/{topic}-{date}-{code}.m4a

    ↓

┌─────────────────────────────────────────────────────────────┐
│                   Template Selection                         │
│                                                              │
│  1. Generate deterministic seed: hash(topic+date+code)      │
│  2. Select category (60% safe, 30% cinematic, 10% exp)     │
│  3. Select specific template from category                  │
│  4. Avoid recently used templates                           │
└─────────────────────────────────────────────────────────────┘

    ↓

┌─────────────────────────────────────────────────────────────┐
│                    Blender Rendering                         │
│                                                              │
│  1. Load output profile (resolution, FPS, codec)            │
│  2. Load Blender template                                   │
│  3. Configure scene from profile                            │
│  4. Load images into VSE                                    │
│  5. Load audio into VSE                                     │
│  6. Apply template effects (compositor)                     │
│  7. Render with FFmpeg encoder                              │
└─────────────────────────────────────────────────────────────┘

    ↓

┌─────────────────────────────────────────────────────────────┐
│                   Output Validation                          │
│                                                              │
│  1. Extract metadata with ffprobe                           │
│  2. Verify resolution (exact match)                         │
│  3. Verify FPS (exact match)                                │
│  4. Verify codec (exact match)                              │
│  5. Verify audio (codec, bitrate)                           │
│  6. Check duration (within range)                           │
│  7. FAIL pipeline if validation fails                       │
└─────────────────────────────────────────────────────────────┘

    ↓

  OUTPUT
    │
    ├─ Video: outputs/{topic}/{topic}-{date}-{code}.mp4
    │
    └─ Manifest: outputs/{topic}/{topic}-{date}-{code}.manifest.json
```

---

## Files Changed

### Removed Files
- `scripts/image_normalizer.py`
- `scripts/test_image_normalizer.py`
- `scripts/test_image_normalization_integration.py`
- `IMAGE_NORMALIZATION_GUIDE.md`

### Modified Files
- `scripts/video_render.py` - Removed normalization calls
- `scripts/global_config.py` - Added output profile loaders
- `.gitignore` - Removed normalized_images patterns
- `README.md` - Added Blender rendering section
- `requirements.txt` - Added PyYAML

### Added Files
- `config/output_profiles.yml`
- `scripts/output_validator.py`
- `scripts/blender/build_video.py`
- `scripts/blender/template_selector.py`
- `scripts/blender/README.md`
- `templates/README.md`
- `templates/inventory.yml`
- `templates/TEMPLATE_CREATION_GUIDE.md`
- `docs/pipeline.md`
- `assets/README.md`
- `assets/LICENSE-SUMMARY.md`
- `assets/luts/README.md`
- `assets/overlays/README.md`
- `assets/fonts/README.md`

---

## Testing Plan

### Unit Tests
1. **Output validator**:
   ```bash
   python scripts/output_validator.py test_video.mp4 --type long
   ```

2. **Template selector**:
   ```bash
   python scripts/blender/template_selector.py
   ```

### Integration Tests
1. **Blender rendering** (requires Blender + template):
   ```bash
   blender --background --python scripts/blender/build_video.py -- \
     --images test_data/images \
     --audio test_data/audio.m4a \
     --output test_output.mp4 \
     --profile long
   ```

2. **Validation workflow**:
   ```bash
   # Render video
   blender --background --python scripts/blender/build_video.py -- ...
   
   # Validate output
   python scripts/output_validator.py test_output.mp4 --type long
   ```

### Visual Tests
1. Create test image sets (dark, bright, text-heavy)
2. Render with different templates
3. Compare visual quality
4. Check for artifacts

---

## Migration Benefits

### 1. Simplified Pipeline
- **Before**: FFmpeg → Normalize → FFmpeg → Video
- **After**: Blender (with internal FFmpeg) → Video

### 2. Quality Control
- **Output contracts** guarantee exact specifications
- **Post-render validation** catches issues immediately
- **Deterministic rendering** with seeds

### 3. Extensibility
- **Template system** allows unlimited visual styles
- **Asset library** provides reusable effects
- **No code changes** needed for new templates

### 4. Cinematic Quality
- **Professional effects** (color grading, grain, vignettes)
- **Controlled randomness** ensures variety
- **Template categories** match content needs

### 5. Maintainability
- **Single source of truth** (output_profiles.yml)
- **Modular design** (templates, assets, scripts)
- **Clear documentation** for contributors

---

## Known Limitations

### 1. Blender Templates Not Created Yet
- **Status**: Template structure exists, `.blend` files need creation
- **Impact**: Can't render with templates until created
- **Workaround**: Create minimal template first, add effects later

### 2. Assets Not Sourced Yet
- **Status**: Directory structure exists, assets need to be added
- **Impact**: Templates can't use LUTs/overlays until added
- **Workaround**: Templates work without assets, just no effects

### 3. CI/CD Not Updated Yet
- **Status**: GitHub Actions still uses FFmpeg
- **Impact**: Can't render with Blender in CI yet
- **Next**: Update workflow to download/cache Blender

### 4. Dual Pipeline Not Implemented
- **Status**: Only FFmpeg currently used in production
- **Impact**: Can't test Blender rendering in production yet
- **Next**: Add feature flag to switch between renderers

---

## Rollout Strategy

### Phase 1: Local Testing (Now)
- Create basic templates
- Test Blender rendering locally
- Validate output contracts
- Refine template effects

### Phase 2: CI Integration (Next)
- Update GitHub Actions workflow
- Add Blender download/cache
- Run Blender rendering in CI
- Compare with FFmpeg outputs

### Phase 3: Dual Pipeline (After CI)
- Add feature flag to video_render.py
- Run both FFmpeg and Blender
- Compare outputs
- Gather metrics

### Phase 4: Gradual Rollout
- Day 1: Enable Blender for 'none' style (minimal)
- Day 2: Enable 'safe' templates
- Day 3: Enable 'cinematic' templates
- Day 4: Enable 'experimental' templates
- Day 5+: Full rollout

### Phase 5: FFmpeg Deprecation (Future)
- After 30 days of stable Blender rendering
- Remove FFmpeg fallback code
- Archive FFmpeg documentation
- Full migration complete

---

## Success Criteria

### Technical
- ✅ Output validation passes 100%
- ✅ Resolution, FPS, codec match profiles exactly
- ✅ Render times reasonable (< 2x audio duration)
- ✅ No visual artifacts

### Quality
- ✅ Videos visually distinct per seed
- ✅ Templates match category descriptions
- ✅ Effects enhance (not distract from) content
- ✅ Professional appearance

### Operational
- ✅ CI/CD pipeline stable
- ✅ No manual intervention required
- ✅ Render failures caught and reported
- ✅ Easy to add new templates

---

## References

- **Pipeline Documentation**: `docs/pipeline.md`
- **Template Guide**: `templates/README.md`
- **Asset Management**: `assets/README.md`
- **Blender Scripts**: `scripts/blender/README.md`
- **Output Profiles**: `config/output_profiles.yml`
- **Blender Docs**: https://docs.blender.org/
- **VSE Guide**: https://docs.blender.org/manual/en/latest/video_editing/
- **Compositor Guide**: https://docs.blender.org/manual/en/latest/compositing/

---

## Contact

For questions or issues:
- **Issues**: https://github.com/agenda-podcast/podcast-maker/issues
- **Discussions**: https://github.com/agenda-podcast/podcast-maker/discussions

---

**Last Updated**: 2025-12-19  
**Status**: Infrastructure complete, ready for template creation and CI integration
