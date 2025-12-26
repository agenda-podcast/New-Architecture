# Architecture - Podcast Maker v2.0

**Modern AI-powered podcast generation with batch optimization and web search**

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Podcast Maker Pipeline                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐
│ Topic Config     │  topics/topic-XX.json
│ - Title          │  - Content type flags
│ - Description    │  - Voice settings
│ - Content Types  │  - Search parameters
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                 1. Content Generation                        │
│                    (responses_api_generator.py)              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ OpenAI gpt-5.2-pro + web_search                       │ │
│  │                                                        │ │
│  │ Input: Topic title + description                      │ │
│  │                                                        │ │
│  │ Process:                                              │ │
│  │  1. Use web_search to find latest news              │ │
│  │  2. Verify facts from search results                │ │
│  │  3. Generate ALL 15 formats in 1 call              │ │
│  │     - L1: 10,000 words                              │ │
│  │     - M1, M2: 2,500 words each                      │ │
│  │     - S1-S4: 1,000 words each                       │ │
│  │     - R1-R8: 80 words each                          │ │
│  │                                                        │ │
│  │ Output: 15 complete scripts with citations           │ │
│  └────────────────────────────────────────────────────────┘ │
└────────┬──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    2. TTS Generation                         │
│                        (tts_generate.py)                     │
│                                                              │
│  ┌─────────────────────┐        ┌──────────────────────┐   │
│  │  Gemini TTS         │   OR   │  Piper TTS          │   │
│  │  (Premium)          │        │  (Local/Free)       │   │
│  │                     │        │                     │   │
│  │  - High quality     │        │  - Good quality     │   │
│  │  - Cloud API        │        │  - Runs locally     │   │
│  │  - $0.016/1K chars  │        │  - No cost          │   │
│  │  - Natural voices   │        │  - Cached models    │   │
│  └─────────────────────┘        └──────────────────────┘   │
│                                                              │
│  Output: 15 MP3 files (one per content piece)              │
└────────┬──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                  3. Image Collection                         │
│                    (OPTIONAL - for video only)               │
│                                                              │
│  Google Custom Search API                                   │
│  - Searches for articles on topic                          │
│  - Extracts OpenGraph images                               │
│  - Downloads up to 50 images                               │
│  - Stores in outputs/topic-XX/images/                     │
└────────┬──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                   4. Video Rendering                         │
│                      (video_render.py)                       │
│                       OPTIONAL                               │
│                                                              │
│  FFmpeg processing:                                         │
│  - Load images (max 50)                                    │
│  - Apply blur + overlay effects                            │
│  - Generate subtitles from script                          │
│  - Add chapter markers                                     │
│  - Render video with audio                                 │
│                                                              │
│  Output: 15 MP4 files                                       │
└────────┬──────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                   5. RSS Generation                          │
│                     (rss_generator.py)                       │
│                                                              │
│  Creates podcast feeds:                                     │
│  - topic-XX-audio.xml (audio podcast feed)                │
│  - topic-XX-video.xml (video podcast feed)                │
│  - Includes all 15 items per feed                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Responses API Generator (`responses_api_generator.py`)

**Purpose**: Generate all content formats in a single API call

**Key Innovation**: Batch generation
- Old: 15 separate API calls
- New: 1 API call with all formats
- Savings: 93% reduction in calls, 85% cost reduction

**Functions**:
```python
generate_batch_responses_api_input()
  - Creates prompt requesting all 15 formats
  - Includes content type specifications
  - No sources passed (OpenAI searches directly)

generate_all_content_batch()
  - Makes single API call to gpt-5.2-pro
  - Enables web_search tool
  - Parses batch response with all content
  
generate_all_content_with_responses_api()
  - Main entry point
  - Returns list of 15 content dictionaries
```

**Input**:
- Topic title
- Topic description
- Freshness window (e.g., "last 24 hours")
- Region (global, US, EU)
- Rumors allowed flag
- Content type specifications

**Output**:
```json
[
  {
    "code": "L1",
    "type": "long",
    "target_words": 10000,
    "actual_words": 10050,
    "script": {
      "duration_sec": 3600,
      "segments": [...]
    }
  },
  // ... M1, M2, S1-S4, R1-R8
]
```

### 2. Web Search Integration

**OpenAI web_search tool**:
- Finds latest news sources
- Verifies facts
- Provides citations
- No manual source collection needed

**How it works**:
1. OpenAI receives topic prompt
2. Automatically searches web for relevant news
3. Filters by freshness window
4. Verifies facts from multiple sources
5. Includes citations in generated content

**Benefits**:
- Always fresh (real-time search)
- Reduced tokens (no sources sent)
- Better quality (OpenAI's search)
- Automatic fact verification

### 3. Content Type Specifications

**Defined in**: `global_config.py`

```python
CONTENT_TYPES = {
    'long': {
        'count': 1,
        'duration_minutes': 60,
        'target_words': 10000,
        'code_prefix': 'L'
    },
    'medium': {
        'count': 2,
        'duration_minutes': 15,
        'target_words': 2500,
        'code_prefix': 'M'
    },
    'short': {
        'count': 4,
        'duration_minutes': 5,
        'target_words': 1000,
        'code_prefix': 'S'
    },
    'reels': {
        'count': 8,
        'duration_minutes': 0.5,
        'target_words': 80,
        'code_prefix': 'R'
    }
}
```

**Content codes**: L1, M1, M2, S1-S4, R1-R8

### 4. Multi-Format Generation

**Script Generation** (`script_generate.py`):
- Entry point for content generation
- Routes to `responses_api_generator.py`
- Handles file I/O for all 15 formats
- Saves scripts, chapters, metadata

**TTS Generation** (`tts_generate.py`):
- Processes all 15 scripts
- Converts to audio (mp3)
- Dual TTS provider support
- Caching for efficiency

**Video Rendering** (`video_render.py`):
- Optional video generation
- Processes all 15 audio files
- Downloads images (max 50 per topic)
- Creates professional videos

---

## Data Flow

### Input Data

**Topic Configuration** (`topics/topic-XX.json`):
```json
{
  "id": "topic-01",
  "title": "Technology & AI News",
  "description": "Daily analysis...",
  "content_types": {
    "long": true,
    "medium": true,
    "short": true,
    "reels": true
  },
  "freshness_hours": 24,
  "search_regions": ["US"],
  "premium_tts": true,
  "tts_voice_a": "en-US-Journey-D",
  "tts_voice_b": "en-US-Journey-F"
}
```

### Intermediate Data

**Scripts** (`outputs/topic-XX/*.script.json`):
```json
{
  "duration_sec": 3600,
  "segments": [
    {
      "chapter": 1,
      "title": "Cold Open",
      "dialogue": [
        {"speaker": "A", "text": "..."},
        {"speaker": "B", "text": "..."}
      ]
    }
  ]
}
```

**Chapters** (`outputs/topic-XX/*.chapters.json`):
```json
[
  {
    "title": "Introduction",
    "start_ms": 0,
    "end_ms": 30000
  }
]
```

### Output Data

**Audio Files** (`*.mp3`):
- 15 files per topic
- Format: `topic-XX-YYYYMMDD-CODE.mp3`
- Dual-voice conversation
- Chapter markers embedded

**Video Files** (`*.mp4`, optional):
- 15 files per topic
- Format: `topic-XX-YYYYMMDD-CODE.mp4`
- Images with blur/overlay
- Subtitles embedded
- Chapter markers

**RSS Feeds** (`*.xml`):
- Audio podcast feed
- Video podcast feed
- All 15 items per feed

---

## Optimization Strategies

### 1. Batch Generation

**Problem**: 15 separate API calls expensive and slow

**Solution**: Single batch call

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| API Calls | 15 | 1 | 93% |
| Input Tokens | 112K | 3K | 97% |
| Time | 150s | 20s | 87% |
| Cost | $21.75 | $7.90 | 64% |

### 2. No Source Collection

**Problem**: Source collection adds complexity and staleness

**Solution**: OpenAI web_search

**Benefits**:
- Real-time fresh sources
- No storage/management overhead
- Reduced token usage (67%)
- Simpler pipeline

### 3. Image Limit

**Problem**: Too many images slow video rendering

**Solution**: Cap at 50 images per topic

**Config**: `MAX_IMAGES_PER_TOPIC = 50`

### 4. Content Reuse

**Problem**: Same facts repeated across formats wastes tokens

**Solution**: Single web_search, reuse verified facts

**Result**: Consistent narrative, reduced search overhead

---

## Scalability

### Horizontal Scaling

**Parallel topic processing**:
```bash
# Process multiple topics in parallel
python run_pipeline.py --topic topic-01 &
python run_pipeline.py --topic topic-02 &
python run_pipeline.py --topic topic-03 &
wait
```

### Resource Requirements

**Per topic generation**:
- CPU: Moderate (TTS and video rendering)
- Memory: ~2GB
- Network: API calls (OpenAI, Google)
- Storage: ~500MB per topic (all formats + video)

**Bottlenecks**:
- OpenAI API rate limits
- TTS generation time (3-5 min for Gemini)
- Video rendering time (1-2 min per video)

### Cost at Scale

**100 topics/day**:
- Script generation: $790/day
- Gemini TTS: $200-300/day
- Images: $1/day
- **Total**: ~$1,000-1,100/day (~$30K/month)

**Cost reduction**:
- Use Piper TTS: -$200-300/day
- Skip video: -$1/day + storage
- Selective content types: -50% script costs

---

## Error Handling

### Retry Logic

**API failures**: Exponential backoff
**Timeout**: 60s default, configurable
**Partial failures**: Continue with available content

### Validation

**Word count**: Check ±3% variance
**Citations**: Verify web_search sources present
**File output**: Validate all expected files created

### Logging

**Levels**:
- INFO: Progress updates
- WARNING: Non-critical issues
- ERROR: Failures requiring attention

**Output**:
- Console (stdout/stderr)
- Log files (optional)
- GitHub Actions logs

---

## Security

### API Key Management

**Environment variables** (recommended):
```bash
export GPT_KEY="..."
export GOOGLE_API_KEY="..."
```

**GitHub Secrets** (CI/CD):
- Never commit keys to repository
- Use GitHub encrypted secrets
- Rotate keys regularly

### Content Safety

**OpenAI moderation**: Built-in safety filters
**Fact verification**: Web search provides citations
**Rumor control**: Optional flag to exclude unconfirmed reports

---

## Monitoring

### Key Metrics

**Cost tracking**:
- API calls per topic
- Token usage (input/output)
- TTS character count

**Performance**:
- Generation time per topic
- Success/failure rate
- Word count accuracy

**Quality**:
- Citation count
- Source freshness
- Content consistency

### Alerts

**Threshold alerts**:
- Cost > $15 per topic
- Generation time > 60s
- Failure rate > 5%
- Word count variance > 5%

---

## Future Enhancements

### Planned

- [ ] Streaming responses for real-time generation
- [ ] Custom content type specifications per topic
- [ ] Multi-language support
- [ ] Voice cloning integration
- [ ] Enhanced video effects

### Under Consideration

- [ ] Real-time podcast generation API
- [ ] Web dashboard for management
- [ ] Advanced analytics
- [ ] Custom model fine-tuning

---

## Technical Stack

**Languages**:
- Python 3.10+ (primary)
- Shell scripts (automation)

**AI/ML**:
- OpenAI gpt-5.2-pro (script generation)
- OpenAI web_search (fact verification)
- Google Gemini TTS (premium audio)
- Piper TTS (local audio)

**Media Processing**:
- FFmpeg (video/audio)
- PIL/Pillow (image processing)

**Infrastructure**:
- GitHub Actions (CI/CD)
- GitHub Releases (artifact hosting)
- RSS feeds (podcast distribution)

---

## References

- **README.md** - User guide
- **QUICKSTART.md** - Getting started
- **RESPONSES_API_IMPLEMENTATION.md** - API details
- **BATCH_OPTIMIZATION_SUMMARY.md** - Performance optimization
- **SESSION_WORK_SUMMARY.md** - Implementation log

---

**Architecture Version**: 2.0  
**Last Updated**: 2025-12-17  
**Status**: Production Ready ✅
