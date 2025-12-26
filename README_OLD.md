# Podcast Maker - Automated Analytical Digest Pipeline

Fully automated pipeline for generating daily analytical digest podcasts with multiple topics, script generation, dual TTS providers, video rendering, and GitHub Releases integration.

## 🎯 Overview

This system automatically:
1. **Collects** fresh content from open sources based on search queries
2. **Curates** a corpus of sources (fresh/backlog) with deduplication
3. **Generates** conversational scripts in deep-dive format with multiple segments
4. **Synthesizes** audio with two voices using premium (Gemini TTS) or basic (Piper) providers
5. **Renders** videos with background images, blur/overlay effects, titles, and chapters
6. **Publishes** artifacts (mp3/mp4/script/chapters/sources) to GitHub Releases

## 🏗️ Architecture

### Components

```
.
├── topics/              # Topic configurations (topic-01.json ... topic-10.json)
├── data/                # Source storage per topic
│   └── topic-XX/
│       ├── fresh.json           # Fresh sources (within freshness window)
│       ├── backlog.json         # Historical sources archive
│       └── picked_for_script.json  # Sources used in current episode
├── outputs/             # Generated artifacts per topic
│   └── topic-XX/
│       ├── topic-XX-YYYYMMDD.script.txt
│       ├── topic-XX-YYYYMMDD.chapters.json
│       ├── topic-XX-YYYYMMDD.sources.json
│       ├── topic-XX-YYYYMMDD.mp3
│       └── topic-XX-YYYYMMDD.mp4
├── scripts/             # Pipeline scripts
│   ├── collect_sources.py    # Source collection
│   ├── script_generate.py    # Script generation with LLM
│   ├── tts_generate.py       # Dual TTS provider (Gemini/Piper)
│   ├── video_render.py       # Video rendering
│   ├── run_pipeline.py       # Complete pipeline orchestration
│   ├── config.py             # Configuration utilities
│   └── dedup.py              # Deduplication logic
└── .github/workflows/
    └── daily.yml             # GitHub Actions workflow

```

### Data Contracts

#### Topic Configuration (`topics/topic-XX.json`)
```json
{
  "id": "topic-01",
  "enabled": true,
  "title": "Technology & AI News Digest",
  "description": "Daily deep dive...",
  "language": "en",
  "duration_sec": 1800,
  "num_segments": 5,
  "queries": ["AI news", "tech innovation"],
  "search_languages": ["en"],
  "search_regions": ["us", "uk"],
  "min_fresh_sources": 5,
  "freshness_hours": 24,
  "max_backlog_items": 100,
  "max_fresh_items": 50,
  "premium_tts": true,
  "tts_voice_a": "en-US-Journey-D",
  "tts_voice_b": "en-US-Journey-F",
  "voice_a_name": "Alex",
  "voice_a_gender": "Male",
  "voice_a_bio": "Tech analyst with 15+ years experience...",
  "voice_a_intro": "Hello and welcome to...",
  "voice_a_outro": "That's all for today...",
  "voice_b_name": "Sarah",
  "voice_b_gender": "Female",
  "voice_b_bio": "Technology journalist specializing in...",
  "voice_b_intro": "Hi everyone, I'm Sarah...",
  "voice_b_outro": "Thanks for joining us...",
  "gpt_prompt": "Focus on practical implications and trends...",
  "script_length": "long",
  "llm_model": "gemini-1.5-flash",
  "video_width": 1920,
  "video_height": 1080,
  "trusted_image_sources": ["reuters.com", "bbc.com"]
}
```

**Topic Control Fields:**
- `enabled`: Boolean flag to include/exclude topic from processing (default: `true`)
  - Set to `false` to skip this topic in automated workflows and batch operations
  - Useful for cost control during testing or temporarily disabling topics
- `queries`: Array of search queries for source collection
  - Reduce to a single query for minimal API costs during testing

**Voice Configuration Fields:**
- `voice_a_name` / `voice_b_name`: Host names (used in transcripts and RSS)
- `voice_a_gender` / `voice_b_gender`: Host gender (Male/Female)
- `voice_a_bio` / `voice_b_bio`: Host biography/description for context
- `voice_a_intro` / `voice_b_intro`: Opening statements for episode intro
- `voice_a_outro` / `voice_b_outro`: Closing statements for episode outro

**TTS Configuration Fields:**
- `premium_tts`: Boolean flag to use premium TTS (Google) or free TTS (Piper)
  - Set to `false` to use free Piper TTS and avoid API costs
  - Set to `true` to use premium Google Cloud TTS for higher quality

**Script Generation Fields:**
- `gpt_prompt`: Custom instructions for ChatGPT (focus, tone, main ideas)
- `script_length`: "short" (15 min), "medium" (20-25 min), or "long" (30 min)

## 🚀 Usage

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
sudo apt-get install ffmpeg  # For audio/video processing
```

2. **Collect sources:**
```bash
cd scripts
python collect_sources.py --all
# or for specific topic:
python collect_sources.py --topic topic-01
```

3. **Run full pipeline:**
```bash
python run_pipeline.py --topic topic-01
# Skip video rendering:
python run_pipeline.py --topic topic-01 --skip-video
```

### GitHub Actions Workflow

The pipeline runs automatically via `.github/workflows/daily.yml`:

- **Schedule**: Daily at 06:00 UTC
- **Manual trigger**: Via `workflow_dispatch` with topic selection
- **Architecture**: Single-writer pattern (fail-safe for concurrent jobs)

#### Workflow Jobs:

1. **setup-piper**: Extracts and caches Piper TTS modules
2. **collect**: Collects sources for all topics → artifact
3. **prepare-matrix**: Generates topic matrix for processing
4. **run**: Matrix job (topic-01...topic-10) generates content → artifacts
5. **finalize**: Single job that:
   - Downloads all artifacts
   - Commits to repository (with rebase/retry)
   - Creates/updates GitHub Releases per topic

#### Environment Variables:
- `GOOGLE_CUSTOM_SEARCH_API_KEY`: Google Custom Search API key for fetching real articles (set in repo secrets)
- `GOOGLE_SEARCH_ENGINE_ID`: Google Custom Search Engine ID (set in repo secrets)
- `GOOGLE_API_KEY`: Google API key for Gemini TTS (set in repo secrets)
- `GPT_KEY`: OpenAI API key for ChatGPT script generation (set in repo secrets)

## 🎨 Features

### ChatGPT Script Generation
- **Deep Thinking**: Uses OpenAI's gpt-5-mini model for advanced reasoning
- **Conversational Analysis**: Generates natural dialogue between two hosts
- **30-Minute Format**: Targets 1800 seconds of engaging discussion
- **Source Integration**: Analyzes fresh sources to create insightful content
- **Fail-Safe**: Falls back to mock scripts if GPT_KEY is not available

### Dual TTS Provider System
- **Premium** (`premium_tts: true`): Google Cloud TTS (Gemini) - higher quality, cloud-based
  - Requires `GOOGLE_API_KEY` environment variable
  - Uses voices like `en-US-Journey-D`, `en-US-Journey-F`
- **Basic** (`premium_tts: false`): Piper TTS - local, unlimited, offline
  - No API key required
  - Uses local voice models like `en_US-lessac-medium`, `en_US-libritts_r-medium`
  - Voice models are cached in the system
- **Caching**: TTS chunks cached by `(provider, voice, text)` hash
- **Chunking**: Splits long text to avoid API limits
- **Silence trimming**: Natural dialogue flow with configurable gaps

### Video Rendering
- Background images from **trusted sources** (Reuters, BBC, NYT, FT, WSJ)
- Blur + dark overlay for text readability
- Title and timer overlays
- Chapter markers
- No audio waveforms (clean analytical look)

### Voice Configuration & Host Personas
- **Named Hosts**: Each topic has two named hosts (e.g., Alex & Sarah)
- **Gender Specification**: Male/Female designation for each host
- **Host Biographies**: Detailed background and expertise for context
- **Intro/Outro Scripts**: Custom opening and closing statements per host
- **Contextual Dialogue**: ChatGPT generates conversations appropriate to host expertise
- **Transcript Format**: Scripts use host names (not "Speaker A/B")
- **RSS Integration**: Host information and bios included in episode descriptions

### Source Management

#### Trusted Source Tiers (3-Tier Quality System)

The pipeline uses a sophisticated 3-tier system to prioritize high-quality, recent news sources:

**Tier 1 - Most Trusted (10 domains):**
- Premium news sources with highest editorial standards
- Examples: Reuters, AP News, BBC, NY Times, WSJ, Financial Times, The Guardian, The Economist, Bloomberg, Nature
- Can be up to **7 days old**
- Priority weight: **100 points**

**Tier 2 - Reputable (10 domains):**
- Well-regarded technology and business publications
- Examples: TechCrunch, Wired, The Verge, Ars Technica, CNET, ZDNet, VentureBeat, Engadget, Mashable, Business Insider
- Can be up to **3 days old**
- Priority weight: **50 points**

**Tier 3 - Acceptable (10 domains):**
- Valid but lower-priority sources
- Examples: Forbes, Medium, HackerNoon, Dev.to, Towards Data Science, ScienceDaily, Phys.org, TNW, Digital Trends, Slashdot
- Can be up to **1 day old**
- Priority weight: **25 points**

**Source Prioritization:**
- Sources ranked by: **tier weight + recency score**
- Newer articles within tier limits get higher priority
- Untrusted sources filtered out unless very recent (< 1 day)
- All sources validated against age thresholds before use

**Quality Gates:**
- Minimum **5 fresh sources** required to generate scripts
- Fresh sources must be within **24-hour freshness window**
- Sources deduplicated by `url/title/date` hash
- Full tier breakdown tracked in `collect_run_summary.json`

**Configuration:**
All tier domains and thresholds are configurable in `scripts/global_config.py`:
- `TRUSTED_SOURCES_TIER1`, `TRUSTED_SOURCES_TIER2`, `TRUSTED_SOURCES_TIER3`
- `SOURCE_MAX_AGE_TIER1`, `SOURCE_MAX_AGE_TIER2`, `SOURCE_MAX_AGE_TIER3`
- `MIN_FRESH_SOURCES_FOR_SCRIPT`, `FRESHNESS_WINDOW_HOURS`

**Storage:**
- **Fresh sources** (`data/topic-XX/fresh.json`): Prioritized sources within freshness window
- **Backlog** (`data/topic-XX/backlog.json`): Historical archive for context
- **Picked sources** (`data/topic-XX/picked_for_script.json`): Sources used in current episode

**Traceability:**
- Full source metadata preserved including tier, priority score, and age validation
- Source lineage tracked in `outputs/topic-XX/topic-XX-YYYYMMDD.sources.json`

### Fail-Soft Design
- Topics fail independently (matrix jobs)
- Video failure doesn't block audio/script
- TTS provider fallback (if quota exceeded)
- Artifacts preserved even without git push

## 📋 Topic Configuration

Topics are in `topics/topic-XX.json`. To add a new topic:

1. Copy existing config: `cp topics/topic-01.json topics/topic-11.json`
2. Update fields: `id`, `title`, `description`, `queries`
3. Add to workflow matrix in `.github/workflows/daily.yml`

## 🔒 Security & Secrets

Required secrets and variables (set in GitHub repo settings):

### Repository Secrets (Settings → Secrets and variables → Actions → Secrets)

- **`GOOGLE_CUSTOM_SEARCH_API_KEY`**: Google Custom Search API key for fetching real articles
  - Used by `collect_sources.py` to dynamically fetch articles based on search queries
  - Get from: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
  - Enable the [Custom Search API](https://console.cloud.google.com/apis/library/customsearch.googleapis.com)
  - Optional: System falls back to mock data if not set

- **`GOOGLE_SEARCH_ENGINE_ID`**: Google Custom Search Engine ID
  - Create a custom search engine at: [Programmable Search Engine](https://programmablesearchengine.google.com/)
  - Configure to search the entire web or specific sites
  - Get the Search Engine ID from the setup page
  - Optional: System uses mock data if not set

- **`GOOGLE_API_KEY`**: Google API key for Gemini TTS (Text-to-Speech)
  - Used for topics with `"premium_tts": true`
  - Get from: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
  - Enable the [Cloud Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
  - Optional: System falls back to Piper TTS if not set

- **`GPT_KEY`**: OpenAI API key for ChatGPT script generation
  - Used by `gpt-5-mini` model for deep conversational script generation
  - Get from: [OpenAI API Keys](https://platform.openai.com/api-keys)
  - Optional: System generates mock scripts if not set

**Local Development:**
Set environment variables before running scripts:
```bash
export GOOGLE_CUSTOM_SEARCH_API_KEY="your-google-custom-search-api-key"
export GOOGLE_SEARCH_ENGINE_ID="your-search-engine-id"
export GOOGLE_API_KEY="your-google-api-key"
export GPT_KEY="your-openai-api-key"
```

## 📦 Outputs

Each topic generates daily artifacts:

```
outputs/topic-XX/
├── topic-XX-20241216.script.txt    # Full dialogue script with host names (for RSS & subtitles)
├── topic-XX-20241216.chapters.json # Chapter metadata
├── topic-XX-20241216.ffmeta        # FFmpeg chapters
├── topic-XX-20241216.sources.json  # Source lineage
├── topic-XX-20241216.script.json   # Structured script for TTS
├── topic-XX-20241216.mp3           # Audio (15-30 min depending on script_length)
└── topic-XX-20241216.mp4           # Video with overlays
```

**File Descriptions:**
- **script.txt**: Human-readable transcript with host names (e.g., "Alex:", "Sarah:") - can be used directly in RSS episode descriptions and for video subtitles
- **script.json**: Structured JSON for TTS processing (dialogue by speaker A/B)
- **chapters.json**: Chapter markers with titles and timestamps
- **sources.json**: Metadata about sources used (fresh, backlog, picked)

### GitHub Releases

Each topic has a rolling release with tag `topic-XX-latest`:
- Stable URLs for latest episode
- Assets auto-updated daily
- Historical versions in commit history

## 🧪 Testing

To test the pipeline locally:

```bash
# Test source collection
cd scripts
python collect_sources.py --topic topic-01

# Test script generation
python script_generate.py --topic topic-01

# Test TTS (requires ffmpeg)
python tts_generate.py --topic topic-01

# Test video rendering (requires ffmpeg)
python video_render.py --topic topic-01
```

## 🛠️ Development

### Script Generation with ChatGPT

The script generation uses OpenAI's ChatGPT API with the gpt-5-mini model for deep thinking:

**How it works:**
1. Loads fresh sources from `data/topic-XX/fresh.json`
2. Sends sources to ChatGPT gpt-5-mini with detailed prompt
3. Requests 30-minute conversational dialogue between two hosts
4. Divides content into configurable segments (default: 5)
5. Generates natural, flowing conversation with deep analysis

**API Configuration:**
```python
# Environment variable: GPT_KEY or OPENAI_API_KEY
# Model: gpt-5-mini (deep thinking capability)
# Target: ~1800 seconds (30 minutes) of dialogue
# Output: JSON with segments and dialogue structure
```

**Testing locally:**
```bash
# Without API key (uses mock data)
cd scripts
python script_generate.py --topic topic-01

# With API key
export GPT_KEY="your-api-key"
python script_generate.py --topic topic-01
```

### Key Principles

1. **Deterministic**: Every episode is traceable (sources → script → audio → video)
2. **Fail-soft**: Component failures don't break entire pipeline
3. **Separation of concerns**: Collection → Script → TTS → Video → Publish
4. **Caching**: Speed through TTS cache and artifacts
5. **Single writer**: Avoid git conflicts in concurrent workflow

### Adding Features

- **New TTS provider**: Extend `tts_generate.py` with provider logic
- **New source**: Add collector to `collect_sources.py`
- **Custom script format**: Modify `script_generate.py`
- **Video effects**: Extend FFmpeg filters in `video_render.py`

## 📝 License

MIT

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Test locally with `run_pipeline.py`
4. Submit pull request

---

**Built for automated, scalable, and reproducible podcast production** 🎙️