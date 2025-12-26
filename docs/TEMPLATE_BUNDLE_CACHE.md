# Template Bundle Cache and Selection System

This document describes the template bundle cache and deterministic selection system for Blender video rendering.

## Overview

The template system ensures that Blender templates are available in CI and provides deterministic, configurable template selection for different content types.

## Components

### 1. Template Verification Script

**File**: `scripts/ensure_blender_templates.py`

This script verifies that all required template files exist and downloads them if necessary.

#### Usage

```bash
# Check if templates exist (doesn't fail if missing)
python3 scripts/ensure_blender_templates.py

# Fail if templates are missing and cannot be downloaded (CI mode)
python3 scripts/ensure_blender_templates.py --required

# Specify custom bundle URL
python3 scripts/ensure_blender_templates.py --bundle-url https://example.com/templates.zip
```

#### Environment Variables

- `BLENDER_TEMPLATES_BUNDLE_URL`: URL to download template bundle ZIP file
- Default: Empty (no automatic download)

#### Exit Codes

- `0`: Success (all templates present)
- `1`: Invalid inventory file
- `2`: Templates missing and no bundle URL provided (with `--required`)
- `3`: Template download/extraction completed but files still missing

### 2. Template Configuration

**File**: `config/video_templates.yml`

Defines template selection strategies per content type.

#### Configuration Structure

```yaml
version: 1

selection:
  # Default strategy for all content types
  default_strategy: sequential
  
  # Fallback behavior when templates are missing
  fallback_to_none: true
  fallback_template_id: "minimal"
  
  # Per-content-type configuration
  by_content_type:
    long:
      strategy: weighted  # or sequential
      candidates: ["neutral", "clean", "teal-orange"]
    medium:
      strategy: sequential
      candidates: ["clean", "neutral", "teal-orange"]
    # ... etc
```

#### Selection Strategies

- **sequential**: Rotates through candidates in order (deterministic)
  - Video 1 uses candidate 1
  - Video 2 uses candidate 2
  - Video 3 uses candidate 3
  - Video 4 uses candidate 1 (wraps around)
  
- **weighted**: Uses weighted random selection based on template categories
  - Safe templates: 60% weight
  - Cinematic templates: 30% weight
  - Experimental templates: 10% weight

### 3. GitHub Actions Integration

**File**: `.github/workflows/daily.yml`

The workflow includes template caching and verification steps.

#### Cache Configuration

Templates are cached using `actions/cache@v4` with a key that includes:
- Template version (`BLENDER_TEMPLATES_VERSION`)
- Hash of `templates/inventory.yml`

This ensures the cache is invalidated when templates change.

#### Workflow Steps

1. **Cache Blender Templates** - Restores cached templates if available
2. **Install Python dependencies** - Installs PyYAML and other requirements
3. **Verify/Download Blender Templates** - Runs verification script

#### Required Secrets

Set these in GitHub repository settings (Settings > Secrets and variables > Actions):

- `BLENDER_TEMPLATES_BUNDLE_URL`: URL to download template bundle ZIP

### 4. Video Rendering Integration

**File**: `scripts/video_render.py`

Template selection is integrated into the video rendering pipeline.

#### How It Works

1. Load template configuration from `config/video_templates.yml`
2. Initialize `TemplateSelector` with inventory
3. Maintain per-content-type rotation counters
4. For each video:
   - Determine content type (long/medium/short/reels)
   - Select template based on strategy and candidates
   - Pass template path to Blender renderer
5. Blender opens template and applies effects

## Template Bundle Structure

The template bundle ZIP should contain all files referenced in `templates/inventory.yml`:

```
templates/
├── base_template.blend
├── safe/
│   ├── minimal.blend
│   ├── neutral.blend
│   ├── clean.blend
│   └── previews/
│       ├── minimal.jpg
│       ├── neutral.jpg
│       └── clean.jpg
├── cinematic/
│   ├── film-noir.blend
│   ├── golden-hour.blend
│   ├── teal-orange.blend
│   ├── vintage-film.blend
│   └── previews/
│       └── ...
└── experimental/
    ├── neon-glow.blend
    ├── glitch.blend
    ├── high-contrast.blend
    └── previews/
        └── ...
```

## Testing

Three test scripts are provided:

### 1. Template Verification Test

```bash
python3 scripts/test_ensure_blender_templates.py
```

Tests the template verification script functionality.

### 2. Configuration Validation Test

```bash
python3 scripts/test_video_templates_config.py
```

Validates the `video_templates.yml` configuration file.

### 3. Integration Test

```bash
python3 scripts/test_template_selection_integration.py
```

Tests the template selection logic and integration with video rendering.

## Workflow Example

### Local Development

1. **Without templates** (video-only mode):
   ```bash
   # Templates not available, rendering proceeds without effects
   python3 scripts/video_render.py --topic topic-01
   ```

2. **With templates** (after downloading bundle):
   ```bash
   # Download and extract template bundle manually
   wget https://example.com/templates.zip
   unzip templates.zip
   
   # Verify templates
   python3 scripts/ensure_blender_templates.py
   
   # Render with templates
   python3 scripts/video_render.py --topic topic-01
   ```

### CI/CD (GitHub Actions)

1. Workflow runs and checks template cache
2. If cache miss, downloads bundle from `BLENDER_TEMPLATES_BUNDLE_URL`
3. Verification script validates all files present
4. Video rendering uses templates with sequential rotation
5. Each content type maintains independent rotation

## Updating Templates

To update the template bundle:

1. Update template files locally
2. Update `templates/inventory.yml` if adding/removing templates
3. Create new ZIP bundle with all template files
4. Upload ZIP to hosting location (e.g., GitHub Release)
5. Update `BLENDER_TEMPLATES_BUNDLE_URL` secret
6. Increment `BLENDER_TEMPLATES_VERSION` in workflow
7. Clear GitHub Actions cache (Settings > Actions > Caches)

## Troubleshooting

### Templates not downloading in CI

- Check that `BLENDER_TEMPLATES_BUNDLE_URL` secret is set
- Verify the URL is accessible from GitHub Actions runners
- Check workflow logs for download errors

### Template selection not working

- Verify `config/video_templates.yml` exists and is valid YAML
- Check that candidate template IDs exist in `templates/inventory.yml`
- Ensure `ENABLE_SOCIAL_EFFECTS=True` in `global_config.py`

### Cache not invalidating

- Increment `BLENDER_TEMPLATES_VERSION` in workflow
- Update `templates/inventory.yml` (even a comment change)
- Manually clear cache in GitHub Settings

## Performance Notes

- Template cache significantly reduces CI build time
- First run downloads ~100MB bundle (one-time cost)
- Subsequent runs restore from cache (seconds)
- Sequential rotation ensures consistent output across runs
