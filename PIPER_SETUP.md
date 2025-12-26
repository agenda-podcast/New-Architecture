# Piper TTS Setup Guide

This document explains how Piper TTS is configured and used in the podcast-maker pipeline.

## What is Piper TTS?

Piper is a fast, local text-to-speech system that runs offline without requiring cloud API calls. It provides high-quality neural TTS using ONNX models.

## Binary Location

The Piper binary and its dependencies are stored in the repository as `piper_linux_x86_64.tar.gz` in the root directory.

This archive contains:
- `piper/piper` - The Piper TTS binary
- `piper/libpiper_phonemize.so` - Phonemization library
- `piper/libonnxruntime.so` - ONNX Runtime library for model inference
- `piper/espeak-ng-data/` - Language data for text-to-phoneme conversion

## Setup in CI/CD

The GitHub Actions workflow automatically extracts the Piper binary during the pipeline run:

```yaml
- name: Setup Piper TTS
  run: |
    tar -xzf piper_linux_x86_64.tar.gz
    chmod +x piper/piper
```

## Voice Models

Voice models are downloaded separately from HuggingFace and cached:

- **Location**: `~/.local/share/piper-tts/voices/`
- **Models Used**:
  - `en_US-ryan-high` (male voice)
  - `en_US-lessac-high` (female voice)

The workflow caches these models to avoid re-downloading on every run.

## Usage in Python

The `tts_generate.py` script automatically locates and uses the Piper binary:

```python
# Piper binary search paths
possible_paths = [
    get_repo_root() / 'piper' / 'piper',  # Extracted from tar.gz
    Path('/usr/local/bin/piper'),         # System installation
    Path('/usr/bin/piper'),                # System installation
]
```

## Library Path Configuration

Piper requires its shared libraries to be in the library search path:

```bash
export LD_LIBRARY_PATH="$(pwd)/piper:$LD_LIBRARY_PATH"
```

This is automatically configured in:
- CI/CD workflows
- Python TTS generation scripts

## Chunking for Long-Form Audio

For audio longer than 30,000 characters, the `tts_chunker.py` module provides:

- Smart text chunking (respects sentence boundaries)
- Parallel synthesis with retry logic
- Deterministic stitching with configurable gaps
- Comprehensive telemetry

Configuration in `global_config.py`:
```python
TTS_MAX_CHARS_PER_CHUNK = 5000
TTS_MAX_SENTENCES_PER_CHUNK = 50
TTS_GAP_MS = 500
TTS_CONCURRENCY = 4
TTS_RETRY_ATTEMPTS = 3
```

## Troubleshooting

### Binary Not Found
Ensure `piper_linux_x86_64.tar.gz` exists in the repository root and extract it:
```bash
tar -xzf piper_linux_x86_64.tar.gz
```

### Library Errors
Set the library path before running:
```bash
export LD_LIBRARY_PATH="$(pwd)/piper:$LD_LIBRARY_PATH"
```

### Voice Models Missing
Download voice models manually:
```bash
mkdir -p ~/.local/share/piper-tts/voices
cd ~/.local/share/piper-tts/voices

# Download male voice
curl -L -o en_US-ryan-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx?download=true"
curl -L -o en_US-ryan-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json?download=true"

# Download female voice
curl -L -o en_US-lessac-high.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx?download=true"
curl -L -o en_US-lessac-high.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx.json?download=true"
```

## Performance

Piper TTS is significantly faster than cloud-based TTS:
- No network latency
- No API rate limits
- Parallel processing support
- Suitable for 60+ minute audio generation

For long-form content, the chunking module enables reliable synthesis by:
- Processing chunks in parallel (default: 4 concurrent)
- Retrying failed chunks (default: 3 attempts)
- Providing detailed telemetry for debugging

## References

- [Piper GitHub Repository](https://github.com/rhasspy/piper)
- [Available Voice Models](https://huggingface.co/rhasspy/piper-voices)
- [ONNX Runtime](https://onnxruntime.ai/)
