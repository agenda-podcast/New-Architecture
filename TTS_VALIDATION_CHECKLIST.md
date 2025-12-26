# TTS Workflow Validation Checklist

This document provides a comprehensive checklist for validating the TTS (Text-to-Speech) workflow and related components in the podcast-maker system.

## Pre-Flight Checks

Before running the podcast generation pipeline, ensure all of the following checks pass:

### 1. System Dependencies

- [ ] **Python 3.8+** installed and available
  ```bash
  python3 --version  # Should show 3.8 or higher
  ```

- [ ] **FFmpeg** installed (required for audio processing)
  ```bash
  ffmpeg -version  # Should show FFmpeg version
  ```

- [ ] **Git** installed (for repository operations)
  ```bash
  git --version
  ```

### 2. Python Dependencies

- [ ] All required packages installed
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **Required packages:**
  - `requests` - Core HTTP library
  - `openai` - ChatGPT script generation
  - `feedgen` - RSS feed generation

- [ ] **Optional packages:**
  - `piper-tts` - Local TTS (not needed if using binary)
  - `google-cloud-texttospeech` - Premium TTS
  - `beautifulsoup4` - HTML parsing (deprecated in v2)

### 3. Environment Variables

- [ ] **GPT_KEY** or **OPENAI_API_KEY** - Required for script generation
  ```bash
  echo $GPT_KEY  # Should output key (not empty)
  ```

- [ ] **GOOGLE_API_KEY** - Required for premium TTS topics (optional)
  ```bash
  echo $GOOGLE_API_KEY  # Should output key or be empty
  ```

### 4. TTS Binaries

- [ ] **Piper tarball exists** in repository root
  ```bash
  ls -lh piper_linux_x86_64.tar.gz  # Should show ~25MB file
  ```

- [ ] **Piper binary extracted** (or will be extracted during setup)
  ```bash
  ls -lh piper/piper  # Should show executable binary
  ```

- [ ] **Piper libraries present**
  ```bash
  ls -lh piper/libpiper_phonemize.so
  ls -lh piper/libonnxruntime.so
  ```

- [ ] **Piper binary is executable**
  ```bash
  chmod +x piper/piper  # Ensure executable
  export LD_LIBRARY_PATH="$(pwd)/piper:$LD_LIBRARY_PATH"
  ./piper/piper --version  # Should output version number
  ```

### 5. Voice Models

- [ ] **Voice models downloaded** (will be cached after first run)
  ```bash
  ls -lh ~/.local/share/piper-tts/voices/
  ```

- [ ] **Required voices:**
  - `en_US-ryan-high.onnx` (male voice)
  - `en_US-ryan-high.onnx.json`
  - `en_US-lessac-high.onnx` (female voice)
  - `en_US-lessac-high.onnx.json`

### 6. Topic Configuration

- [ ] **At least one topic enabled**
  ```bash
  python3 scripts/test_enabled_topics.py
  ```

- [ ] **Topic configs are valid**
  ```bash
  python3 scripts/system_validator.py
  ```

### 7. Mock Data Quality (for testing mode)

- [ ] **Mock data meets word count targets**
  ```bash
  python3 scripts/validate_mock_data.py
  ```

- [ ] All content types should be within ±10% of target:
  - L1: 10,000 words
  - M1, M2: 2,500 words each
  - S1-S4: 1,000 words each
  - R1-R8: 80 words each

### 8. RSS Feed Generation

- [ ] **FeedGenerator module available**
  ```bash
  python3 scripts/test_rss_dependencies.py
  ```

- [ ] All 4 RSS tests should pass

### 9. Disk Space

- [ ] **Sufficient disk space available** (minimum 5GB recommended)
  ```bash
  df -h .  # Check available space
  ```

### 10. File Permissions

- [ ] **Output directory writable**
  ```bash
  mkdir -p outputs/test && rmdir outputs/test
  ```

- [ ] **Cache directory writable**
  ```bash
  mkdir -p .cache/tts && rmdir .cache/tts
  ```

## Validation Commands

### Run All Validations

```bash
# Complete system validation
cd scripts
python3 system_validator.py
```

### Individual Component Checks

```bash
# Check RSS dependencies
python3 scripts/test_rss_dependencies.py

# Validate mock data
python3 scripts/validate_mock_data.py

# Validate script JSON files (if any exist)
python3 scripts/validate_script_json.py

# Check enabled topics
python3 scripts/test_enabled_topics.py
```

## Troubleshooting

### Piper Binary Not Found

**Symptoms:** Error about missing piper binary

**Solutions:**
1. Extract the tarball:
   ```bash
   tar -xzf piper_linux_x86_64.tar.gz
   ```

2. Make binary executable:
   ```bash
   chmod +x piper/piper
   ```

3. Test binary:
   ```bash
   export LD_LIBRARY_PATH="$(pwd)/piper:$LD_LIBRARY_PATH"
   ./piper/piper --version
   ```

### Voice Models Missing

**Symptoms:** Error about missing .onnx files

**Solutions:**
Voice models are downloaded automatically during workflow execution. To download manually:

```bash
mkdir -p ~/.local/share/piper-tts/voices
cd ~/.local/share/piper-tts/voices

# Male voice
curl -L -o en_US-ryan-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx?download=true"
curl -L -o en_US-ryan-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json?download=true"

# Female voice
curl -L -o en_US-lessac-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx?download=true"
curl -L -o en_US-lessac-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx.json?download=true"
```

### RSS Feed Generation Fails

**Symptoms:** Import error for FeedGenerator

**Solutions:**
```bash
pip install feedgen
python3 scripts/test_rss_dependencies.py
```

### Script JSON Validation Errors

**Symptoms:** TTS fails with missing segments or dialogue

**Solutions:**
1. Validate script files:
   ```bash
   python3 scripts/validate_script_json.py --topic topic-01
   ```

2. Check script structure - should have:
   - `segments` array
   - Each segment has `dialogue` array
   - Each dialogue has `speaker` and `text`

### Library Path Issues

**Symptoms:** Error loading shared libraries

**Solutions:**
```bash
export LD_LIBRARY_PATH="$(pwd)/piper:$LD_LIBRARY_PATH"
```

Add this to your shell profile or workflow environment.

## CI/CD Integration

### GitHub Actions Workflow

The workflow includes comprehensive validation:

1. **Setup Piper TTS** (5-step validation)
   - Check tarball exists
   - Extract if needed
   - Verify required files
   - Set executable permissions
   - Test binary functionality

2. **Voice Model Management**
   - Download from HuggingFace
   - Verify file sizes
   - Cache for future runs

3. **Python Integration Check**
   - Verify TTS code can locate binary
   - Test configuration lookups

See `.github/workflows/daily.yml` for complete workflow.

### Adding Validation to CI

Add these steps to your workflow:

```yaml
- name: Validate System
  run: |
    cd scripts
    python3 system_validator.py

- name: Validate Mock Data
  run: |
    cd scripts
    python3 validate_mock_data.py

- name: Test RSS Dependencies
  run: |
    cd scripts
    python3 test_rss_dependencies.py
```

## Best Practices

### Before Making Changes

1. Run system validation: `python3 scripts/system_validator.py`
2. Ensure all tests pass
3. Check mock data quality if in testing mode

### After Making Changes

1. Re-run system validation
2. Test affected components individually
3. Run script JSON validation if scripts were generated
4. Check CI/CD workflow succeeds

### Regular Maintenance

1. **Weekly:** Verify voice model cache is intact
2. **Monthly:** Update dependencies: `pip install -U -r requirements.txt`
3. **As needed:** Update Piper binary to latest version
4. **As needed:** Expand mock data to meet targets

## Reference Documentation

- [TTS Troubleshooting Guide](TTS_TROUBLESHOOTING_GUIDE.md)
- [Piper Setup Guide](PIPER_SETUP.md)
- [Testing Guide](TESTING.md)
- [Mock Data Improvements](MOCK_DATA_IMPROVEMENTS.md)
- [TTS Workflow Improvements Summary](TTS_WORKFLOW_IMPROVEMENTS_SUMMARY.md)

## Quick Reference

### Essential Commands

```bash
# Full system check
python3 scripts/system_validator.py

# Test individual components
python3 scripts/test_rss_dependencies.py
python3 scripts/validate_mock_data.py
python3 scripts/validate_script_json.py

# Test Piper binary
export LD_LIBRARY_PATH="$(pwd)/piper:$LD_LIBRARY_PATH"
./piper/piper --version

# Generate test output
cd scripts
python3 run_pipeline.py --topic topic-01
```

### Exit Codes

- `0` - All checks passed
- `1` - Validation failed (errors present)

### Support

For issues or questions:
1. Check troubleshooting sections above
2. Review related documentation
3. Check GitHub workflow logs
4. Open an issue in the repository
