# Quick Start Guide - Podcast Maker

**Get your first AI-generated podcast in 5 minutes!**

---

## Prerequisites (2 minutes)

### 1. Install Python & FFmpeg

```bash
# Python 3.10+ required
python3 --version

# Install FFmpeg (for video)
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# Download from https://ffmpeg.org/download.html
```

### 2. Clone Repository

```bash
git clone https://github.com/agenda-podcast/podcast-maker.git
cd podcast-maker
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Set API Keys (1 minute)

### Required

```bash
# OpenAI API (for script generation)
export GPT_KEY="sk-your-key-here"
```

### Optional (for enhanced features)

```bash
# For premium TTS (Gemini voices)
export GOOGLE_API_KEY="your-google-api-key"

# For video images only
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-key"
export GOOGLE_SEARCH_ENGINE_ID="your-engine-id"
```

**Note**: Without Google keys, you'll get:
- Basic TTS (Piper, still good quality)
- No video images (audio only)

---

## Generate Your First Podcast (2 minutes)

### Option 1: Quick Test (Audio Only)

```bash
cd scripts

# Generate scripts (OpenAI searches web automatically)
python script_generate.py --topic topic-01

# Generate audio
python tts_generate.py --topic topic-01
```

**Output**: Check `outputs/topic-01/` folder
- 15 audio files (L1, M1-M2, S1-S4, R1-R8)
- 15 script files
- Chapter markers
- Source citations

### Option 2: Full Pipeline (With Video)

```bash
cd scripts

# Run everything
python run_pipeline.py --topic topic-01
```

**Output**: Audio + Video + RSS feeds

### Option 3: Skip Video (Faster)

```bash
cd scripts
python run_pipeline.py --topic topic-01 --skip-video
```

---

## What Just Happened?

### 1. Script Generation (10-20 seconds)

OpenAI (gpt-5.2-pro):
- Searched the web for latest news on "Technology & AI"
- Found and verified sources
- Generated **15 different scripts** in ONE call:
  - 1 × 60-minute deep dive (10,000 words)
  - 2 × 15-minute segments (2,500 words each)
  - 4 × 5-minute updates (1,000 words each)
  - 8 × 30-second clips (80 words each)

### 2. Audio Generation (30-60 seconds)

TTS (Gemini or Piper):
- Converted each script to audio
- Two voices in conversation
- Natural dialogue flow

### 3. Video Generation (1-2 minutes, if enabled)

FFmpeg:
- Downloaded images (max 50)
- Created videos with blur effects
- Added subtitles and chapters

---

## Check Your Results

### Audio Files

```bash
ls outputs/topic-01/*.mp3

# You should see:
# topic-01-20251217-L1.mp3   (60 min)
# topic-01-20251217-M1.mp3   (15 min)
# topic-01-20251217-M2.mp3   (15 min)
# topic-01-20251217-S1.mp3   (5 min)
# topic-01-20251217-S2.mp3   (5 min)
# ... and more
```

### Video Files (if generated)

```bash
ls outputs/topic-01/*.mp4
```

### Scripts & Metadata

```bash
ls outputs/topic-01/*.txt      # Human-readable scripts
ls outputs/topic-01/*.json     # Structured data
```

---

## Customize Your Topic

### Edit Configuration

**File**: `topics/topic-01.json`

```json
{
  "title": "Your Topic Title",
  "description": "Detailed topic description",
  
  "content_types": {
    "long": true,     // Enable/disable 60-min format
    "medium": true,   // Enable/disable 15-min formats
    "short": true,    // Enable/disable 5-min formats
    "reels": false    // Disable 30-sec clips
  },
  
  "freshness_hours": 24,        // Last 24 hours of news
  "search_regions": ["US"],     // US sources priority
  "rumors_allowed": false        // Exclude rumors
}
```

### Regenerate

```bash
cd scripts
python run_pipeline.py --topic topic-01
```

---

## Generate Multiple Topics

### All Enabled Topics

```bash
cd scripts
python run_pipeline.py --all
```

This processes all topics with `"enabled": true`

### Specific Topics

```bash
cd scripts
python run_pipeline.py --topics topic-01 topic-02 topic-03
```

---

## Cost Estimate

### Per Topic (15 formats)

| Component | Cost |
|-----------|------|
| Script generation (OpenAI) | ~$7.90 |
| Gemini TTS | ~$2-3 |
| Images (Google CSE) | ~$0.01 |
| **Total** | **~$10-11** |

### Save Money

```bash
# Use free local TTS
# Edit topics/topic-01.json:
{
  "premium_tts": false  // Uses Piper instead of Gemini
}

# Skip video (no image costs)
python run_pipeline.py --topic topic-01 --skip-video

# Enable only needed formats
{
  "content_types": {
    "long": true,
    "medium": false,  // Disable medium
    "short": false,   // Disable short
    "reels": false    // Disable reels
  }
}
# Cost: ~$3-4 per topic (1 format only)
```

---

## Common Issues

### "GPT_KEY not set"

```bash
export GPT_KEY="sk-your-openai-api-key"
```

### "No module named 'openai'"

```bash
pip install -r requirements.txt
```

### "FFmpeg not found"

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

### "No images found in sources"

This is normal if you haven't set Google CSE credentials.

**Options**:
1. Skip video: `python run_pipeline.py --skip-video`
2. Or add credentials for image collection

### "Word count variance too high"

Make sure you're using gpt-5.2-pro:

```bash
export RESPONSES_API_MODEL="gpt-5.2-pro"
```

---

## Next Steps

### Automate Daily Generation

See `.github/workflows/daily.yml` for GitHub Actions setup

### Create Custom Topics

Copy `topics/topic-01.json` to `topics/topic-11.json` and customize

### Publish to Podcast Platforms

Use generated RSS feeds in `outputs/topic-XX/*.xml`

### Advanced Configuration

See **README.md** for complete documentation

---

## Need Help?

- **Documentation**: See README.md and other guides
- **Issues**: https://github.com/agenda-podcast/podcast-maker/issues
- **Discussions**: https://github.com/agenda-podcast/podcast-maker/discussions

---

## What's New in v2.0?

✅ **Single API Call** - All 15 formats in one request (85% cost savings)  
✅ **Web Search** - OpenAI finds sources automatically  
✅ **No Source Collection** - Simpler pipeline, always fresh  
✅ **Batch Optimization** - 7.5x faster generation  
✅ **gpt-5.2-pro** - Latest model with web search

**Migration**: See FINAL_IMPLEMENTATION_SUMMARY.md if upgrading

---

**Time to First Podcast**: 5 minutes  
**Cost per Topic**: ~$10-11 (or $3-4 without video/premium TTS)  
**Formats Generated**: 15 different lengths  

Happy podcasting! 🎙️
