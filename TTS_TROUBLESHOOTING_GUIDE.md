# TTS Troubleshooting Guide

This guide helps diagnose and fix Text-to-Speech (TTS) issues in the podcast generation pipeline.

## Overview

The system supports two TTS providers:
1. **Piper TTS** (Local): Open-source, offline TTS for non-premium topics
2. **Google Cloud TTS** (Premium): Cloud-based TTS for premium topics

## Common Issues

### 1. Voice Model Not Found

**Symptoms:**
```
Voice model not found: en_US-lessac-medium
```

**Solutions:**

#### A. Verify Models Exist
```bash
ls -lah ~/.local/share/piper-tts/voices/
```

Expected files:
```
en_US-lessac-medium.onnx
en_US-lessac-medium.onnx.json
en_US-amy-medium.onnx
en_US-amy-medium.onnx.json
```

#### B. Manual Download (if needed)

1. Visit: https://github.com/rhasspy/piper/releases
2. Download voice archives for:
   - `en_US-lessac-medium`
   - `en_US-amy-medium`
3. Extract `.onnx` and `.onnx.json` files to:
   - `~/.local/share/piper-tts/voices/`

### 2. FFmpeg Concatenation Error

**Symptoms:**
```
ffmpeg ... returned non-zero exit status 183
```

**Causes:**
- Invalid audio files (empty or corrupted)
- Filter syntax error
- Incompatible audio formats
- Missing audio stream

**Solutions:**

#### A. Check Audio Files
```bash
# Verify audio files exist and have content
ls -lh .cache/tts/
ffmpeg -i .cache/tts/somefile.wav
```

#### B. Verify FFmpeg Installation
```bash
ffmpeg -version
```

#### C. Test Simple Concatenation
```bash
# Test with two files
ffmpeg -i file1.wav -i file2.wav \
  -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[out]" \
  -map "[out]" output.wav
```

### 3. Piper Package Not Available

**Symptoms:**
```
ImportError: No module named 'piper'
```

**Solutions:**

#### A. Install Piper TTS
```bash
pip install piper-tts
```

#### B. Verify Installation
```python
python -c "from piper.voice import PiperVoice; print('Piper installed')"
```

#### C. Check Requirements
```bash
pip install -r requirements.txt
```

### 4. Mock Audio Fallback

**Symptoms:**
```
Falling back to mock audio generation...
```

**Causes:**
- API keys missing (for premium)
- Voice models missing (for Piper)
- Network issues

**Solutions:**

#### A. For Premium Topics (Google Cloud TTS)
```bash
# Set API key
export GOOGLE_API_KEY="your-api-key"

# Or in GitHub Actions secrets
# Settings → Secrets → Actions → GOOGLE_API_KEY
```

#### B. For Non-Premium Topics (Piper)
```bash
# Verify voices exist
ls ~/.local/share/piper-tts/voices/
```

## Voice Configuration

### Current Voice Assignments

#### Premium Topics (Topic 01)
- **Voice A**: `en-US-Journey-D` (Google Cloud TTS)
- **Voice B**: `en-US-Journey-F` (Google Cloud TTS)
- **Required**: `GOOGLE_API_KEY` environment variable

#### Non-Premium Topics (Topics 02-10)
- **Voice A**: `en_US-lessac-medium` (Piper TTS)
- **Voice B**: `en_US-amy-medium` (Piper TTS)
- **Required**: Downloaded voice models

### Changing Voices

To use different voices, edit topic configuration:

```json
{
  "id": "topic-02",
  "premium_tts": false,
  "tts_voice_a": "en_US-lessac-medium",
  "tts_voice_b": "en_US-amy-medium"
}
```

Available Piper voices:
- `en_US-lessac-low`, `en_US-lessac-medium`, `en_US-lessac-high`
- `en_US-amy-low`, `en_US-amy-medium`
- `en_US-ryan-low`, `en_US-ryan-medium`, `en_US-ryan-high`
- `en_US-danny-low`
- `en_US-kathleen-low`

After changing voices, ensure the voice models are available in `~/.local/share/piper-tts/voices/` or cached in GitHub Actions.

## GitHub Actions Integration

### Workflow Configuration

The workflow automatically:
1. Downloads Python dependencies
2. Restores Piper voice models from cache
3. Uses cached voices for TTS generation

```yaml
- name: Cache Piper voices
  uses: actions/cache@v4
  with:
    path: ~/.local/share/piper-tts/voices
    key: piper-voices-${{ hashFiles('topics/*.json') }}
```

### Debugging in GitHub Actions

#### Check Cache Status
Look for cache hit message:
```
Cache restored from key: piper-voices-abc123
```

Or cache miss:
```
Cache not found for input keys: piper-voices-abc123
```



## TTS Cache

### Location
- **Local**: `.cache/tts/`
- **GitHub Actions**: Cached per topic

### Cache Key Format
```
tts-cache-{topic-id}-{data-hash}
```

### Clear Cache
```bash
# Local
rm -rf .cache/tts/

# GitHub Actions
# Delete cache via GitHub UI or API
```

## Performance Optimization

### 1. Enable Caching
```python
TTS_CACHE_ENABLED = True  # In global_config.py
```

### 2. Use Appropriate Quality
- **Low**: Faster, smaller files, lower quality
- **Medium**: Balanced (recommended)
- **High**: Slower, larger files, better quality

### 3. Batch Processing
The system automatically batches TTS requests to:
- Reuse cached audio
- Minimize API calls
- Optimize processing time

## Testing TTS

### Test Single Voice
```python
from tts_generate import generate_tts_piper

test_text = "Hello, this is a test."
voice = "en_US-lessac-medium"
output_path = "/tmp/test.wav"

success = generate_tts_piper(test_text, voice, output_path)
print(f"TTS test: {'✓ Success' if success else '✗ Failed'}")
```

### Test Voice Availability
```bash
python -c "
from pathlib import Path
voices_dir = Path.home() / '.local' / 'share' / 'piper-tts' / 'voices'
voices = list(voices_dir.glob('*.onnx'))
print(f'Found {len(voices)} voice models:')
for v in voices:
    print(f'  - {v.stem}')
"
```

### Test Full Pipeline
```bash
cd scripts
python tts_generate.py --topic topic-02 --date 20231216
```

## Advanced Troubleshooting

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Audio Properties
```bash
# For any generated audio file
ffprobe -i output.mp3 -show_format -show_streams
```

### Validate ONNX Models
```python
import onnxruntime as ort

model_path = "~/.local/share/piper-tts/voices/en_US-lessac-medium.onnx"
session = ort.InferenceSession(model_path)
print("Model loaded successfully")
```

### Monitor System Resources
```bash
# During TTS generation
htop  # or top
watch -n 1 'du -sh .cache/tts'
```

## Common Questions

### Q: Why do voice downloads fail in sandbox/offline environments?
**A:** Voice downloads require internet access to CDNs and GitHub. In offline or restricted environments, manually download voices and place them in `~/.local/share/piper-tts/voices/`.

### Q: Can I use custom voices?
**A:** Yes, place custom ONNX voice models in the voices directory and update topic configs to reference them.

### Q: How much disk space do voices need?
**A:** Each voice model is typically 30-100 MB. For 2 voices = ~60-200 MB total.

### Q: Can I use different TTS engines?
**A:** Yes, but requires code modifications to `tts_generate.py`. The system is designed to support multiple providers.

### Q: Why does TTS generation take so long?
**A:** First run downloads voices and generates audio. Subsequent runs use cached audio, making them much faster.

## See Also

- [QUICKSTART.md](QUICKSTART.md) - Getting started guide
- [README.md](README.md) - Project overview
- [TESTING.md](TESTING.md) - Testing procedures
- [.github/workflows/daily.yml](.github/workflows/daily.yml) - CI/CD configuration
