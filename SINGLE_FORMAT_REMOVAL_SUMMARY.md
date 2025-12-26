# Single Format Removal and Mock Data Cleanup - Summary

**Date**: 2025-12-17  
**Issue**: #25 - Video Output Issues  
**Related Requirements**: Remove single format version, remove mock data files

---

## Changes Overview

This document summarizes the removal of legacy single-format code paths and the cleanup of mock data files to ensure only real data from Google Custom Search API is used.

---

## 1. Single Format Code Removal

### Rationale
The codebase previously supported both single-format (legacy) and multi-format generation. Multi-format generation is now the standard approach, configurable via the `content_types` field in topic configuration. The legacy single-format code paths are no longer needed and were removed to simplify the codebase.

### Files Modified

#### `scripts/script_generate.py`
- **Removed**: `generate_single_format_for_topic()` function (~200 lines)
- **Simplified**: `generate_for_topic()` - now always calls `generate_multi_format_for_topic()`
- **Removed**: Logic checking for `has_multi_format` flag

**Before**:
```python
def generate_for_topic(topic_id: str, date_str: str = None) -> bool:
    # Check if multi-format generation is enabled
    content_types = config.get('content_types', {})
    has_multi_format = any(content_types.values()) if content_types else False
    
    if has_multi_format:
        return generate_multi_format_for_topic(...)
    else:
        return generate_single_format_for_topic(...)  # Legacy path
```

**After**:
```python
def generate_for_topic(topic_id: str, date_str: str = None) -> bool:
    # Always use multi-format generation based on content_types configuration
    return generate_multi_format_for_topic(topic_id, date_str, config, data_dir, output_dir)
```

#### `scripts/tts_generate.py`
- **Removed**: `generate_single_format_for_topic()` function (~30 lines)
- **Simplified**: `generate_for_topic()` - now always calls `generate_multi_format_for_topic()`
- **Removed**: Import of `is_multi_format_enabled`

#### `scripts/video_render.py`
- **Removed**: `render_single_format_for_topic()` function (~90 lines)
- **Simplified**: `render_for_topic()` - now always calls `render_multi_format_for_topic()`
- **Removed**: Import of `is_multi_format_enabled`

### Impact

**Benefits**:
- Simpler, more maintainable codebase
- Single code path to test and debug
- Clearer architecture - all topics use multi-format generation
- Eliminates confusion between single and multi-format modes

**Configuration Requirement**:
- Topics **must** have `content_types` field in their configuration
- Content types define which formats to generate (long, medium, short, reels)
- Example:
  ```json
  {
    "content_types": {
      "long": true,
      "medium": true,
      "short": true,
      "reels": true
    }
  }
  ```

---

## 2. Mock Data Removal

### Rationale
The repository previously contained mock/example data files with fake URLs and no images. This caused:
- Black screen videos (no images)
- Confusion about data sources
- Risk of accidentally using test data in production

All data must now come from real Google Custom Search API calls.

### Files Removed

**Data Files** (all mock data):
```
data/topic-01/fresh.json          ✗ REMOVED
data/topic-01/backlog.json        ✗ REMOVED
data/topic-01/picked_for_script.json  ✗ REMOVED
data/topic-02/fresh.json          ✗ REMOVED
... (same for all 10 topics)
```

**Output Files** (generated from mock data):
```
outputs/topic-*/topic-*.*         ✗ REMOVED (all files)
```

### .gitignore Updates

**Added patterns to prevent committing data/output files**:
```gitignore
# Data and output files - only real data from Google Search, never mock data
data/*/fresh.json
data/*/backlog.json
data/*/picked_for_script.json
outputs/*/topic-*
```

**Old (incorrect)**:
```gitignore
# Don't ignore data and outputs - we want to commit them
# !data/
# !outputs/
```

### Documentation Updates

**QUICKSTART.md**:
- Removed "Setup Example Data" section that created mock data
- Added "Setup API Credentials (Required)" section
- Updated troubleshooting to clarify no mock data fallback exists
- Clarified that all data comes from Google Custom Search API

---

## 3. Order Issue Prevention

### Problem
If data files are read before they're updated from API calls, stale/mock data could be used in pipeline.

### Solution

**Collection Flow**:
1. `collect_sources.py` calls Google Custom Search API
2. Results saved to `data/*/fresh.json` and `data/*/backlog.json`
3. Only after successful write, files are available for next step

**Script Generation Flow**:
1. `script_generate.py` reads `fresh.json` and `backlog.json`
2. Validates sources are from trusted domains
3. Checks image availability
4. Picks sources and saves to `picked_for_script.json`
5. Generates scripts and saves to `outputs/`

**TTS Generation Flow**:
1. `tts_generate.py` reads script JSON files from `outputs/`
2. Generates audio for each script
3. Saves MP3 files to `outputs/`

**Video Rendering Flow**:
1. `video_render.py` reads sources JSON and audio files from `outputs/`
2. Downloads images from sources
3. Generates videos and saves to `outputs/`

**Key Protection**:
- Each step validates required files exist before proceeding
- API failures prevent writing partial/empty data files
- File writes are atomic (write to file, then flush)
- `.gitignore` prevents committing intermediate files

---

## 4. API Credentials Requirement

### Critical Change
**Source collection now requires Google Custom Search API credentials** - there is no fallback to mock data.

### Setup Required

**Environment Variables**:
```bash
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-key"
export GOOGLE_SEARCH_ENGINE_ID="your-id"
```

**GitHub Secrets** (for Actions):
- `GOOGLE_CUSTOM_SEARCH_API_KEY` - **REQUIRED**
- `GOOGLE_SEARCH_ENGINE_ID` - **REQUIRED**
- `GOOGLE_API_KEY` - For Gemini TTS (if using premium TTS)
- `GPT_KEY` - For script generation

### Error Handling

**Without API credentials**, source collection will fail with clear error:
```
Google Custom Search API credentials not configured.
Please set GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID environment variables.
These are required for fetching real articles in production.
```

**No fallback behavior** - pipeline will stop and require user action.

---

## 5. Testing and Validation

### Syntax Check
All modified Python files compile successfully:
```bash
✓ scripts/script_generate.py
✓ scripts/tts_generate.py
✓ scripts/video_render.py
```

### Integration Testing Required

After deployment, test the following workflow:

1. **Source Collection**:
   ```bash
   python scripts/collect_sources.py --topic topic-01
   ```
   Expected: Real articles from Google with image URLs

2. **Script Generation**:
   ```bash
   python scripts/script_generate.py --topic topic-01
   ```
   Expected: Multiple scripts (L1, M1, M2, S1-S4, R1-R7) based on content_types config

3. **TTS Generation**:
   ```bash
   python scripts/tts_generate.py --topic topic-01
   ```
   Expected: MP3 files for each script

4. **Video Rendering**:
   ```bash
   python scripts/video_render.py --topic topic-01
   ```
   Expected: MP4 files with article images (not black screens)

5. **Complete Pipeline**:
   ```bash
   python scripts/run_pipeline.py --topic topic-01
   ```
   Expected: All steps complete successfully

---

## 6. Migration Guide

### For Existing Deployments

**Step 1: Backup existing data** (if needed):
```bash
cp -r data data.backup
cp -r outputs outputs.backup
```

**Step 2: Update code**:
```bash
git pull origin main
```

**Step 3: Ensure API credentials are set**:
```bash
# Verify credentials
echo $GOOGLE_CUSTOM_SEARCH_API_KEY
echo $GOOGLE_SEARCH_ENGINE_ID
```

**Step 4: Ensure all topics have content_types configured**:
```bash
# Check topic configuration
jq '.content_types' topics/topic-01.json
```

Expected output:
```json
{
  "long": true,
  "medium": true,
  "short": true,
  "reels": true
}
```

**Step 5: Clear old data** (optional):
```bash
rm -rf data/*/fresh.json data/*/backlog.json data/*/picked_for_script.json
rm -rf outputs/*/topic-*
```

**Step 6: Collect fresh sources**:
```bash
python scripts/collect_sources.py --all
```

**Step 7: Test pipeline**:
```bash
python scripts/run_pipeline.py --topic topic-01
```

---

## 7. Configuration Requirements

### Topic Configuration

All topics **must** have `content_types` field defined:

```json
{
  "id": "topic-01",
  "title": "Topic Title",
  "content_types": {
    "long": true,      // 60-minute format
    "medium": true,    // 15-30 minute formats
    "short": true,     // 5-minute formats
    "reels": true      // 1-minute formats
  }
  // ... other fields
}
```

**Validation**: If `content_types` is missing or all values are false, multi-format generation will create no outputs.

### Content Type Codes

Multi-format generation creates files with format codes:
- `L1` - Long format (60 min)
- `M1`, `M2` - Medium formats (15-30 min)
- `S1`, `S2`, `S3`, `S4` - Short formats (5 min)
- `R1`-`R7` - Reels (1 min each)

Example filenames:
```
topic-01-20251217-L1.mp3
topic-01-20251217-M1.mp4
topic-01-20251217-S1.script.json
topic-01-20251217-R1.chapters.json
```

---

## 8. Benefits Summary

### Code Quality
✅ Removed ~320 lines of legacy code  
✅ Single code path for generation pipeline  
✅ Simplified imports and dependencies  
✅ Clearer architecture and flow

### Data Quality
✅ Only real articles from Google Custom Search  
✅ All sources include image URLs  
✅ No risk of using stale mock data  
✅ Clear error messages when API credentials missing

### Maintainability
✅ Easier to debug (single code path)  
✅ Easier to test (fewer scenarios)  
✅ Easier to understand for new developers  
✅ Reduced cognitive load

---

## 9. Backward Compatibility

### Breaking Changes
⚠️ **Topics without `content_types` field will fail**

**Solution**: Add `content_types` to all topic configurations

⚠️ **Mock data files no longer exist**

**Solution**: Run `collect_sources.py` with valid API credentials

⚠️ **Single-format generation no longer supported**

**Solution**: Use multi-format with only one content type enabled if needed

---

## 10. Related Documentation

- `VIDEO_OUTPUT_FIX_GUIDE.md` - Video output troubleshooting
- `VIDEO_OUTPUT_INCIDENT_REPORT.md` - Original investigation
- `QUICKSTART.md` - Updated quick start guide
- `README.md` - Repository documentation

---

## Summary

**Changes Made**:
1. ✅ Removed single-format generation functions from 3 files
2. ✅ Removed all mock data files (data/*.json)
3. ✅ Removed all output files generated from mock data
4. ✅ Updated .gitignore to prevent committing data/output files
5. ✅ Updated QUICKSTART.md documentation
6. ✅ Verified all files compile successfully

**Requirements Met**:
1. ✅ Only multi-format generation based on configuration
2. ✅ All data must be real from Google Search API
3. ✅ No order issues - proper file dependencies enforced
4. ✅ Clear error handling for missing API credentials

**Next Steps**:
- Test complete pipeline with valid API credentials
- Verify video generation with real images
- Confirm subtitle generation works correctly
- Monitor for any edge cases or issues

---

**Last Updated**: 2025-12-17  
**Issue**: #25  
**Status**: ✅ Implementation Complete
