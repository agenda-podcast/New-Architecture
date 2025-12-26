# Quick Start Guide

Get started with the Podcast Maker in 5 minutes!

## Prerequisites

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install FFmpeg (Ubuntu/Debian)
sudo apt-get install -y ffmpeg

# Or on macOS
brew install ffmpeg
```

## 1. Setup API Credentials (Required)

Before you can collect sources and generate podcasts, you must configure Google Custom Search API credentials:

```bash
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-api-key-here"
export GOOGLE_SEARCH_ENGINE_ID="your-search-engine-id-here"
```

Then collect real article sources for topics:

```bash
python3 scripts/collect_sources.py --topic topic-01
```

## 2. Generate Your First Podcast (1-2 minutes)

```bash
cd scripts
python3 run_pipeline.py --topic topic-02 --skip-video
```

**Note**: Use topic-02 (or any non-premium topic) for local TTS with Piper. Topic-01 requires `GOOGLE_API_KEY` for premium Google Cloud TTS.

**Output files** in `outputs/topic-02/`:
- `topic-02-YYYYMMDD.script.txt` - Full dialogue script
- `topic-02-YYYYMMDD.mp3` - Audio file (generated with Piper TTS)
- `topic-02-YYYYMMDD.chapters.json` - Chapter markers
- `topic-02-YYYYMMDD.sources.json` - Source metadata

## 3. View the Results

```bash
# Read the script
cat outputs/topic-02/topic-02-*.script.txt

# Check chapters
jq . outputs/topic-02/topic-02-*.chapters.json

# View sources
jq '.picked | length' outputs/topic-02/topic-02-*.sources.json
```

## 4. Customize Your Topic

Edit `topics/topic-01.json`:

```json
{
  "enabled": true,
  "title": "Your Custom Topic",
  "description": "Your description",
  "queries": ["your search terms"],
  "premium_tts": false,
  "tts_voice_a": "en_US-lessac-medium",
  "tts_voice_b": "en_US-libritts_r-medium",
  "duration_sec": 1800
}
```

**Topic Control:**
- `enabled: true` - Include topic in automated workflows and `--all` operations
- `enabled: false` - Skip topic (useful for cost control during testing)
- `queries` - Array of search terms; reduce to 1 query for minimal API costs

**TTS Configuration:**
- `premium_tts: true` - Use Google Cloud TTS (requires `GOOGLE_API_KEY`)
  - Voices: `en-US-Journey-D`, `en-US-Journey-F`, etc.
- `premium_tts: false` - Use Piper TTS (local, no API key)
  - Voices: `en_US-lessac-medium`, `en_US-libritts_r-medium`, etc.
  - Voice models are cached and available in the system

Then regenerate:

```bash
cd scripts
python3 collect_sources.py --topic topic-01
python3 run_pipeline.py --topic topic-01
```

## 5. Deploy to GitHub Actions

1. **Set secrets**:
   - Go to: Settings → Secrets and variables → Actions → Secrets
   - Add **Secret**: `GOOGLE_CUSTOM_SEARCH_API_KEY` (**required** for real article fetching with images)
   - Add **Secret**: `GOOGLE_SEARCH_ENGINE_ID` (**required** - your custom search engine ID)
   - Add **Secret**: `GOOGLE_API_KEY` (for Gemini TTS, only if using premium TTS)
   - Add **Secret**: `GPT_KEY` (**required** for ChatGPT script generation)

2. **Configure topics**:
   - Set `enabled: true` only for topics you want to process (all others should be `enabled: false`)
   - For cost control: use single query per topic and `premium_tts: false`
   - **Source collection requires Google Custom Search API credentials** - without them, source collection will fail
   - All source data comes from real Google Custom Search API calls - no mock data is used
   - Premium topics (`premium_tts: true`) require `GOOGLE_API_KEY`
   - Non-premium topics (`premium_tts: false`) use Piper TTS locally (no API key needed)
   - Piper voices are automatically cached in GitHub Actions
   - Only enabled topics will be processed in the workflow matrix

3. **Trigger workflow**:
   - Go to: Actions → Daily Podcast Generation
   - Click: "Run workflow"
   - Select topics or use "all"

4. **Check results**:
   - Workflow completes in ~15 minutes per topic
   - Artifacts uploaded to repository
   - Releases created for each topic

## Architecture Overview

```
┌─────────────┐
│   collect   │ → Gather sources
└──────┬──────┘
       ↓ (artifact)
┌─────────────┐
│     run     │ → Generate script/audio/video (parallel for 10 topics)
│  (matrix)   │
└──────┬──────┘
       ↓ (artifacts)
┌─────────────┐
│  finalize   │ → Commit & create releases
└─────────────┘
```

## Component Overview

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `collect_sources.py` | Gather articles | `topics/*.json` | `data/*/fresh.json` |
| `script_generate.py` | Create dialogue | `data/*/fresh.json` | `outputs/*/*.script.*` |
| `tts_generate.py` | Synthesize audio | `*.script.json` | `outputs/*/*.mp3` |
| `video_render.py` | Render video | `*.mp3` + sources | `outputs/*/*.mp4` |
| `run_pipeline.py` | Orchestrate all | Topic ID | All outputs |

## Next Steps

- **Read**: [README.md](README.md) - Full documentation
- **Test**: [TESTING.md](TESTING.md) - Testing guide
- **Contribute**: [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guide
- **Customize**: Edit topic configs and scripts

## Common Commands

```bash
# Collect sources for all topics
python3 scripts/collect_sources.py --all

# Generate podcast for specific topic
python3 scripts/run_pipeline.py --topic topic-02

# Generate for specific date
python3 scripts/run_pipeline.py --topic topic-01 --date 20241215

# Skip video (faster)
python3 scripts/run_pipeline.py --topic topic-01 --skip-video

# Test individual components
python3 scripts/script_generate.py --topic topic-01
python3 scripts/tts_generate.py --topic topic-01
python3 scripts/video_render.py --topic topic-01
```

## Troubleshooting

**"Not enough fresh sources"**
→ Lower `min_fresh_sources` in `topics/topic-XX.json`

**"FFmpeg not found"**
→ Install: `sudo apt-get install ffmpeg`

**"Google Custom Search API credentials not configured"**
→ Add `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID` secrets - **required for source collection**
→ Source collection will fail without valid API credentials - no fallback to mock data

**"GOOGLE_API_KEY not set"**
→ Set `premium_tts: false` or add API key to secrets

**"GPT_KEY not set" or script generation fails**
→ Add `GPT_KEY` repository secret - **required for script generation**

**Git push fails in workflow**
→ Check logs - workflow auto-retries 3 times

## Getting Help

- **Issues**: [GitHub Issues](../../issues)
- **Discussions**: [GitHub Discussions](../../discussions)
- **Docs**: Check README, TESTING, and CONTRIBUTING

---

Happy podcasting! 🎙️
