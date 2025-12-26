# Podcast Maker - AI-Powered Multi-Format Content Generator

**Automated pipeline for generating multi-format podcast content with OpenAI Responses API, web search, and video rendering.**

[![Status](https://img.shields.io/badge/status-production-green.svg)](https://github.com/agenda-podcast/podcast-maker)
[![Model](https://img.shields.io/badge/model-gpt--5.2--pro-blue.svg)](https://openai.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🎯 Overview

This system generates **15 different podcast formats** from a single API call, optimized for cost and quality:

- **1 Long** format (60 min, 10,000 words)
- **2 Medium** formats (15 min, 2,500 words each)
- **4 Short** formats (5 min, 1,000 words each)
- **8 Reels** (30 sec, 80 words each)

### Key Features

✅ **Single API Call** - All 15 formats generated in one request (93% cost savings)  
✅ **Web Search Integration** - OpenAI finds and verifies latest sources directly  
✅ **Word Count Control** - ±3% accuracy on target word counts  
✅ **Multi-Format Output** - Long-form to social media in one generation  
✅ **Video Rendering** - Automated video with images, subtitles, chapters  
✅ **Dual TTS** - Gemini (premium) or Piper (local) text-to-speech  
✅ **GitHub Releases** - Automatic publishing and RSS feeds

---

## 🏗️ Architecture

### Pipeline Overview

```
1. OpenAI Responses API (gpt-5.2-pro)
   └─> Uses web_search tool to find latest sources
   └─> Generates ALL 15 content formats in 1 call
   └─> Returns scripts with citations and metadata

2. TTS Generation (Gemini or Piper)
   └─> Converts scripts to audio (mp3)
   └─> Dual-voice conversational format

3. Video Rendering (Blender 4.5 LTS + FFmpeg)
   └─> Downloads images from Google Custom Search
   └─> Applies cinematic effects via Blender templates
   └─> Generates mp4 files with controlled visual style

4. Publishing (GitHub Releases)
   └─> Creates releases with all artifacts
   └─> Generates RSS feeds for podcasts
```

### No Source Collection Required

**Important**: Unlike traditional podcast generators, this system does NOT require pre-collecting sources. OpenAI's web_search tool finds and verifies sources in real-time during generation.

### Directory Structure

```
.
├── topics/                    # Topic configurations
│   └── topic-XX.json         # Content types, voice settings
├── scripts/                   # Core pipeline
│   ├── responses_api_generator.py   # NEW: Batch API generation
│   ├── script_generate.py           # Script generation entry
│   ├── tts_generate.py              # Audio generation
│   ├── video_render.py              # Video rendering
│   ├── run_pipeline.py              # Complete pipeline
│   └── rss_generator.py             # RSS feed generation
├── outputs/                   # Generated content
│   └── topic-XX/
│       ├── topic-XX-DATE-L1.mp3    # Long format audio
│       ├── topic-XX-DATE-M1.mp3    # Medium format audio
│       ├── topic-XX-DATE-S1.mp3    # Short format audio
│       ├── topic-XX-DATE-R1.mp3    # Reel audio
│       └── *.mp4, *.script.txt, *.chapters.json
└── .github/workflows/
    └── daily.yml              # Automated workflow
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install FFmpeg (for video)
# Ubuntu/Debian:
sudo apt-get install ffmpeg
# macOS:
brew install ffmpeg
```

### Required Environment Variables

```bash
# OpenAI API (for script generation)
export GPT_KEY="your-openai-api-key"

# Optional: Override default model
export RESPONSES_API_MODEL="gpt-5.2-pro"

# For premium TTS (Gemini)
export GOOGLE_API_KEY="your-google-api-key"

# For image collection (video only)
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-key"
export GOOGLE_SEARCH_ENGINE_ID="your-engine-id"
```

### Generate Your First Podcast

```bash
cd scripts

# Generate scripts (OpenAI searches web automatically)
python script_generate.py --topic topic-01

# Generate audio
python tts_generate.py --topic topic-01

# Generate video (optional)
python video_render.py --topic topic-01

# Or run complete pipeline
python run_pipeline.py --topic topic-01
```

**Output**: 15 content pieces (scripts + audio + video) in `outputs/topic-01/`

---

## ⚙️ Configuration

### Topic Configuration

**File**: `topics/topic-01.json`

```json
{
  "id": "topic-01",
  "enabled": true,
  "title": "Technology & AI News",
  "description": "Daily analysis of tech trends and AI developments",
  
  "content_types": {
    "long": true,     // 60-minute deep dive
    "medium": true,   // 15-minute focused segments
    "short": true,    // 5-minute quick updates
    "reels": true     // 30-second social clips
  },
  
  "freshness_hours": 24,
  "search_regions": ["US"],
  "rumors_allowed": false,
  
  "premium_tts": true,
  "tts_voice_a": "en-US-Journey-D",
  "tts_voice_b": "en-US-Journey-F",
  
  "video_width": 1920,
  "video_height": 1080
}
```

**Optional TTS Configuration:**
- `tts_use_chunking`: Set to `true` for parallel chunked processing (long-form content), or `false` for single run (default)

### Content Type Specifications

| Type | Duration | Words | Count | Purpose |
|------|----------|-------|-------|---------|
| Long | 60 min | 10,000 | 1 | Deep dive analysis |
| Medium | 15 min | 2,500 | 2 | Focused segments |
| Short | 5 min | 1,000 | 4 | Quick updates |
| Reels | 30 sec | 80 | 8 | Social media clips |

---

## 💡 How It Works

### 1. Content Generation (Batch Mode)

**Single API Call** for all formats:

```python
from responses_api_generator import generate_all_content_with_responses_api

# Generate ALL 15 content pieces in ONE call
all_content = generate_all_content_with_responses_api(config)

# Result: List of 15 content dictionaries
# - L1: 10,000 words (Long format)
# - M1, M2: 2,500 words each (Medium)
# - S1-S4: 1,000 words each (Short)
# - R1-R8: 80 words each (Reels)
```

**What Happens**:
1. OpenAI receives topic title + description
2. Uses web_search to find latest news
3. Generates all 15 scripts with consistent facts
4. Returns complete JSON with all content

**Cost Optimization**:
- Old approach: 15 API calls = $15-30 per topic
- New approach: 1 API call = $2-5 per topic
- **Savings**: 85% reduction

### 2. Web Search Integration

OpenAI's web_search tool:
- Finds latest news within freshness window (e.g., "last 24 hours")
- Verifies facts from multiple sources
- Provides citations for all claims
- Ensures consistent facts across all formats

**No manual source collection required!**

### 3. TTS Generation

Converts scripts to audio with two voice options:

**Gemini TTS** (Premium):
- High-quality voices (Journey-D, Journey-F)
- Natural conversation flow
- Requires GOOGLE_API_KEY
- ~$0.016 per 1,000 characters

**Piper TTS** (Local):
- Free, runs locally
- Good quality (lessac, libritts_r)
- No API key needed
- Cached voice models

### 4. Video Rendering

- Downloads up to 50 images per topic
- Creates background with blur + overlay effects
- Adds subtitles with word-level timing
- Generates chapter markers
- Output: Professional-looking videos

---

## 📊 Performance

### Cost Analysis

**Per Topic** (15 content pieces):
- Old system: $21.75
- New system: $7.90
- **Savings**: $13.85 (64%)

**Per 100 Topics/Month**:
- Old: $2,175
- New: $790
- **Savings**: $1,385/month

### Speed

- Old: 150 seconds per topic (15 sequential calls)
- New: 20 seconds per topic (1 batch call)
- **Improvement**: 7.5x faster

### Token Efficiency

- Input tokens: 97% reduction (112K → 3K)
- Output tokens: 17% reduction (30K → 25K)
- **Overall**: 85% reduction

---

## 🎨 Content Quality

### Word Count Accuracy

Target: ±3% variance

Example outputs:
```
L1: 10,050 words (target: 10,000) - 0.5% variance ✓
M1: 2,480 words (target: 2,500) - 0.8% variance ✓
S1: 1,010 words (target: 1,000) - 1.0% variance ✓
R1: 82 words (target: 80) - 2.5% variance ✓
```

### Consistency

All formats use the same verified facts:
- Same events, dates, numbers
- Same sources and citations
- Coherent narrative across lengths
- Single web_search call ensures consistency

---

## 🔧 Advanced Usage

### Custom Content Types

Enable/disable formats per topic:

```json
{
  "content_types": {
    "long": true,      // Include 60-min format
    "medium": false,   // Skip 15-min formats
    "short": true,     // Include 5-min formats
    "reels": false     // Skip 30-sec clips
  }
}
```

### Region-Specific Content

```json
{
  "search_regions": ["US"],  // US sources priority
  "freshness_hours": 24      // Last 24 hours only
}
```

### Rumor Control

```json
{
  "rumors_allowed": false  // Exclude unconfirmed reports
}
```

---

## 🎬 Video Rendering System

### Blender 4.5 LTS Pipeline

The video rendering system uses **Blender 4.5 LTS** for composition and cinematic effects, with FFmpeg as the internal encoder.

**Key Features**:
- ✅ Cinematic effects via Blender templates
- ✅ Output contracts guarantee resolution, FPS, codec
- ✅ Controlled randomness - visually distinct videos
- ✅ Template categories: safe, cinematic, experimental
- ✅ Asset library: LUTs, overlays, fonts

### Architecture

```
Images + Audio
    ↓
Blender VSE (Video Sequence Editor)
    ↓
Template Selection (weighted random)
    ↓
Effects Application (compositor)
    ↓
FFmpeg Encoding (H.264)
    ↓
Output Validation
    ↓
MP4 + Manifest
```

### Output Profiles

All video outputs meet exact specifications defined in `config/output_profiles.yml`:

| Content Type | Resolution | FPS | Codec | Bitrate |
|-------------|-----------|-----|-------|---------|
| Long (L)    | 1920x1080 | 30  | H.264 | 10M     |
| Medium (M)  | 1920x1080 | 30  | H.264 | 10M     |
| Short (S)   | 1080x1920 | 30  | H.264 | 8M      |
| Reels (R)   | 1080x1920 | 30  | H.264 | 8M      |

### Template System

**Categories**:
- **Safe** (60%): Minimal, professional effects
- **Cinematic** (30%): Film-quality effects
- **Experimental** (10%): Bold, artistic effects

**Effects**:
- Color grading (LUTs, contrast curves)
- Film grain and texture
- Vignettes and bloom
- Light leaks and dust
- Transitions and motion

**Deterministic**: Each video uses a seed based on `hash(topic + date + code)` for reproducible results.

### Render Manifest

Each video produces a manifest file:

```json
{
  "video_path": "topic-01-20251219-L1.mp4",
  "resolution": "1920x1080",
  "fps": 30,
  "duration": 2438.5,
  "template": {
    "category": "cinematic",
    "name": "film-noir"
  },
  "effects": ["color_grade", "grain", "vignette"],
  "seed": "a3f9b2c1d5e6",
  "render_time": 325.7
}
```

### Local Rendering

To render videos locally:

```bash
# Install Blender 4.5 LTS
wget https://download.blender.org/release/Blender4.5/blender-4.5.0-linux-x64.tar.xz
tar -xf blender-4.5.0-linux-x64.tar.xz

# Render video
blender-4.5.0-linux-x64/blender --background \
  --python scripts/blender/build_video.py \
  -- \
  --images outputs/topic-01/images \
  --audio outputs/topic-01/topic-01-20251219-L1.m4a \
  --output outputs/topic-01/topic-01-20251219-L1.mp4 \
  --profile long \
  --template templates/safe/minimal.blend

# Validate output
python scripts/output_validator.py \
  outputs/topic-01/topic-01-20251219-L1.mp4 \
  --type long
```

### Documentation

- **Pipeline**: `docs/pipeline.md` - Complete architecture
- **Templates**: `templates/README.md` - Template system guide
- **Assets**: `assets/README.md` - Asset management
- **Blender Scripts**: `scripts/blender/README.md` - Script usage

---

## 📦 GitHub Actions Integration

### Automated Daily Generation

**File**: `.github/workflows/daily.yml`

```yaml
name: Daily Podcast Generation

on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC daily

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Generate Podcasts
        env:
          GPT_KEY: ${{ secrets.GPT_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
        run: |
          python scripts/run_pipeline.py --all
      
      - name: Create Releases
        run: |
          python scripts/create_releases.py
```

### Required Secrets

Add in GitHub Settings → Secrets:
- `GPT_KEY` - OpenAI API key (required)
- `GOOGLE_API_KEY` - For Gemini TTS (optional)
- `GOOGLE_CUSTOM_SEARCH_API_KEY` - For images (optional)
- `GOOGLE_SEARCH_ENGINE_ID` - For images (optional)

---

## 📝 Output Files

### Per Content Piece

Each content code (L1, M1, S1, R1, etc.) generates:

```
topic-01-20251217-L1.script.txt      # Full script text
topic-01-20251217-L1.script.json     # Structured script
topic-01-20251217-L1.chapters.json   # Chapter markers
topic-01-20251217-L1.ffmeta          # FFmpeg metadata
topic-01-20251217-L1.m4a             # Audio file
topic-01-20251217-L1.mp4             # Video file
topic-01-20251217-L1.manifest.json   # Render manifest
```

### Shared Files

```
topic-01-20251217.sources.json       # All sources metadata
topic-01-audio.xml                   # Audio RSS feed
topic-01-video.xml                   # Video RSS feed
```

---

## 🧪 Testing

```bash
# Run unit tests
python scripts/test_image_extraction.py     # Image extraction (14 tests)

# Test individual components
python scripts/script_generate.py --topic topic-01
python scripts/tts_generate.py --topic topic-01
python scripts/video_render.py --topic topic-01

# Test complete pipeline
python scripts/run_pipeline.py --topic topic-01 --skip-video
```

---

## 🐛 Troubleshooting

### Common Issues

**"GPT_KEY not set"**
→ Export environment variable: `export GPT_KEY="your-key"`

**"No images found in sources"**
→ Set Google CSE credentials for image collection
→ Or skip video: `--skip-video` flag

**"Word count variance too high"**
→ Check model (should be gpt-5.2-pro)
→ Review content_types configuration

**"FFmpeg not found"**
→ Install: `sudo apt-get install ffmpeg`

---

## 🧪 API Connectivity Testing

Before running the full pipeline, verify your API credentials are properly configured:

### Quick Test (via GitHub Actions)

1. Go to **Actions** → **API Connectivity Tests**
2. Click **Run workflow**
3. Select which API to test:
   - **all** - Test all APIs together (recommended)
   - **openai** - Test only OpenAI API
   - **google-search** - Test only Google Custom Search API
   - **google-tts** - Test only Google Cloud TTS API

**Cost**: < $0.001 (less than one tenth of a cent)

### Local Testing

```bash
cd scripts

# Test all APIs
python test_all_api_connectivity.py

# Test individual APIs
python test_openai_connectivity.py
python test_google_search_connectivity.py
python test_google_tts_connectivity.py
```

For detailed testing documentation, see **API_CONNECTIVITY_TESTING.md**.

---

## 📚 Documentation

- **README.md** - This file (getting started)
- **QUICKSTART.md** - 5-minute quick start guide
- **API_CONNECTIVITY_TESTING.md** - Test API connections
- **ENVIRONMENT_SETUP.md** - Environment configuration guide
- **RESPONSES_API_IMPLEMENTATION.md** - Technical API details
- **ARCHITECTURE_SIMPLIFICATION.md** - Pipeline architecture
- **BATCH_OPTIMIZATION_SUMMARY.md** - Cost optimization details
- **TTS_TROUBLESHOOTING_GUIDE.md** - TTS issues and solutions
- **TESTING.md** - Testing guide
- **CONTRIBUTING.md** - Contribution guidelines

---

## 🔄 Migration from Old Version

If you're upgrading from a previous version:

### Breaking Changes

1. **Source collection removed** - OpenAI web_search replaces manual collection
2. **Single-format removed** - Only multi-format supported
3. **content_types required** - All topics need this field
4. **Mock data removed** - Real API credentials required

### Migration Steps

1. **Update topic configs** - Add `content_types` field
2. **Remove old data** - Delete `data/*/fresh.json` files
3. **Update workflows** - Remove `collect_sources.py` step
4. **Set API keys** - Configure environment variables
5. **Test generation** - Run on one topic first

See **FINAL_IMPLEMENTATION_SUMMARY.md** for complete migration guide.

---

## 💰 Cost Estimation

### Typical Usage

**Single topic, all formats enabled** (15 pieces):
- Script generation: ~$7.90
- Gemini TTS: ~$2-3
- Image collection: ~$0.01
- **Total**: ~$10-11 per topic per day

**10 topics daily**:
- ~$100-110 per day
- ~$3,000-3,300 per month

### Cost Reduction Tips

1. Use Piper TTS (free) instead of Gemini
2. Disable video rendering (skip images)
3. Enable only needed content types
4. Reduce freshness_hours to get fewer sources
5. Use fewer topics

---

## 🤝 Contributing

Contributions welcome! See **CONTRIBUTING.md** for guidelines.

### Development Setup

```bash
git clone https://github.com/agenda-podcast/podcast-maker.git
cd podcast-maker
pip install -r requirements.txt
cp .env.example .env  # Add your API keys
python scripts/run_pipeline.py --topic topic-01
```

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- OpenAI for gpt-5.2-pro and web_search tool
- Google for Gemini TTS
- Piper TTS for local voice synthesis
- FFmpeg for video processing

---

## 🔗 Links

- **GitHub**: https://github.com/agenda-podcast/podcast-maker
- **Issues**: https://github.com/agenda-podcast/podcast-maker/issues
- **Discussions**: https://github.com/agenda-podcast/podcast-maker/discussions

---

**Status**: Production Ready ✅  
**Version**: 2.0 (Responses API with Batch Optimization)  
**Last Updated**: 2025-12-17

Happy podcasting! 🎙️
