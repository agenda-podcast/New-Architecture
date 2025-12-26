# Testing Guide

This document describes how to test the podcast maker pipeline locally and in GitHub Actions.

## Prerequisites

### System Requirements
- Python 3.11+
- FFmpeg (for audio/video processing)
- Git

### Python Dependencies
```bash
pip install -r requirements.txt
```

### System Dependencies (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## Local Testing

### 1. Quick Start - Setup Example Data

Generate mock data for all topics:
```bash
python3 scripts/setup_example.py
```

This will:
- Create `data/topic-XX/fresh.json` and `backlog.json` for all 10 topics
- Generate mock sources with realistic structure
- Create `collect_run_summary.json` with collection statistics

### 2. Test Individual Components

#### Source Collection
```bash
cd scripts
python3 collect_sources.py --topic topic-01
# or for all topics:
python3 collect_sources.py --all
```

**Expected output:**
- `data/topic-01/fresh.json` - Fresh sources
- `data/topic-01/backlog.json` - All sources
- `collect_run_summary.json` - Summary statistics

#### Script Generation
```bash
cd scripts
python3 script_generate.py --topic topic-01 --date 20241216
```

**Expected output:**
- `outputs/topic-01/topic-01-20241216.script.txt` - Human-readable script
- `outputs/topic-01/topic-01-20241216.script.json` - Structured script for TTS
- `outputs/topic-01/topic-01-20241216.chapters.json` - Chapter markers
- `outputs/topic-01/topic-01-20241216.ffmeta` - FFmpeg metadata
- `outputs/topic-01/topic-01-20241216.sources.json` - Source lineage
- `data/topic-01/picked_for_script.json` - Sources used

#### TTS Generation
```bash
cd scripts
python3 tts_generate.py --topic topic-01 --date 20241216
```

**Requirements:** FFmpeg must be installed

**Expected output:**
- `outputs/topic-01/topic-01-20241216.mp3` - Audio file
- `.cache/tts/*.wav` - Cached TTS chunks

#### Video Rendering
```bash
cd scripts
python3 video_render.py --topic topic-01 --date 20241216
```

**Requirements:** FFmpeg must be installed, MP3 must exist

**Expected output:**
- `outputs/topic-01/topic-01-20241216.mp4` - Video file

### 3. Test Full Pipeline

Run the complete pipeline for one topic:
```bash
cd scripts
python3 run_pipeline.py --topic topic-01

# Skip video rendering (faster):
python3 run_pipeline.py --topic topic-01 --skip-video
```

**Expected output:**
All files from previous steps in sequence.

## GitHub Actions Testing

### 1. Manual Workflow Dispatch

Trigger workflow manually from GitHub UI:
1. Go to **Actions** tab
2. Select **Daily Podcast Generation** workflow
3. Click **Run workflow**
4. Choose topics (default: "all") or specify: "topic-01,topic-02"
5. Click **Run workflow**

### 2. Scheduled Run

Workflow runs automatically daily at 06:00 UTC (configured in cron).

### 3. Workflow Structure

The workflow consists of 4 jobs:

#### Job 1: `collect`
- Runs `collect_sources.py --all`
- Uploads `data/` and summary as artifact
- **No git push** (fail-safe)

#### Job 2: `voices`
- Checks/caches Piper voices
- Uploads status marker as artifact

#### Job 3: `run` (matrix)
- Runs in parallel for topics 01-10
- Downloads collected data
- Runs full pipeline for each topic
- Uploads `outputs/topic-XX/` as artifact
- **No git push** (fail-safe)

#### Job 4: `finalize` (single writer)
- Downloads all artifacts
- Merges into working tree
- Commits and pushes (with rebase retry)
- Creates/updates GitHub Releases per topic

### 4. Checking Workflow Results

After workflow completion:

**In Repository:**
- `data/topic-XX/` should be updated
- `outputs/topic-XX/` should have new dated files
- `collect_run_summary.json` should show latest run

**In Releases:**
- Each topic has a release with tag `topic-XX-latest`
- Release assets: `.mp3`, `.mp4`, `.script.txt`, `.chapters.json`, `.sources.json`

**In Actions UI:**
- Workflow summary shows table of collected sources
- Job logs show pipeline progress
- Artifacts available for 90 days

### 5. Debugging Workflow Failures

#### Collect job fails
- Check source collection logic
- Review API rate limits (if using real sources)
- Check `collect_run_summary.json` artifact

#### Run job fails for specific topic
- Matrix jobs are independent
- Check specific topic's job log
- Review topic configuration in `topics/topic-XX.json`
- Download `outputs-topic-XX` artifact to inspect partial results

#### Finalize job fails
- Usually git push conflicts
- Check git rebase/retry logic
- Review commit history for conflicts

#### Release creation fails
- Check `GITHUB_TOKEN` permissions
- Ensure output files exist
- Review release creation logs

## Validating Output Quality

### Script Quality
```bash
# Check script structure
cat outputs/topic-01/topic-01-20241216.script.txt

# Verify JSON structure
jq . outputs/topic-01/topic-01-20241216.script.json
```

### Audio Quality
```bash
# Check audio duration
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  outputs/topic-01/topic-01-20241216.mp3

# Play audio
ffplay outputs/topic-01/topic-01-20241216.mp3
```

### Video Quality
```bash
# Check video properties
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,duration,r_frame_rate \
  outputs/topic-01/topic-01-20241216.mp4

# Play video
ffplay outputs/topic-01/topic-01-20241216.mp4
```

### Source Lineage
```bash
# Verify deduplication
jq '.picked | length' outputs/topic-01/topic-01-20241216.sources.json

# Check freshness
jq '.fresh[0]' outputs/topic-01/topic-01-20241216.sources.json
```

## Performance Testing

### TTS Cache Efficiency
```bash
# First run (cold cache)
time python3 scripts/tts_generate.py --topic topic-01

# Second run (warm cache)
time python3 scripts/tts_generate.py --topic topic-01
# Should be significantly faster
```

### Pipeline Timing
```bash
# Measure full pipeline
time python3 scripts/run_pipeline.py --topic topic-01
```

Expected times (with mock data, no real TTS/video):
- Collection: < 5s
- Script generation: < 5s
- TTS (mock): < 10s
- Video (mock): < 30s
- **Total: < 1 minute**

With real TTS and video rendering:
- TTS (Gemini): 2-5 minutes
- TTS (Piper): 5-10 minutes
- Video rendering: 1-2 minutes
- **Total: 8-17 minutes per topic**

## Common Issues

### "Not enough fresh sources"
**Cause:** Less than `min_fresh_sources` in fresh.json
**Fix:** Adjust `min_fresh_sources` in topic config or improve source collection

### "Script JSON not found"
**Cause:** Script generation failed or didn't run
**Fix:** Run `script_generate.py` before `tts_generate.py`

### "Audio file not found"
**Cause:** TTS generation failed or didn't run
**Fix:** Run `tts_generate.py` before `video_render.py`

### "FFmpeg not found"
**Cause:** FFmpeg not installed
**Fix:** `sudo apt-get install ffmpeg`

### "GOOGLE_API_KEY not set"
**Cause:** Missing API key for premium TTS
**Fix:** Set environment variable or use `premium_tts: false` in topic config

### Git push fails in finalize job
**Cause:** Race condition or stale branch
**Fix:** Workflow has automatic rebase retry (3 attempts)

## Integration Testing Checklist

- [ ] All 10 topics collect sources successfully
- [ ] Script generation produces valid dialogue
- [ ] Chapters have correct timestamps
- [ ] TTS cache reduces repeated generation time
- [ ] Video has readable text overlay
- [ ] Video duration matches audio duration
- [ ] GitHub Releases are created/updated
- [ ] Release assets are accessible via stable URLs
- [ ] Deduplication prevents duplicate sources
- [ ] Fresh/backlog split maintains correct boundaries
- [ ] Workflow completes without errors
- [ ] Git commits don't have conflicts
- [ ] Artifacts are properly merged in finalize job

## Continuous Monitoring

After deployment, monitor:
1. **Daily workflow runs**: Check Actions tab
2. **Source freshness**: Review `collect_run_summary.json`
3. **Output quality**: Spot-check random episodes
4. **Cache hit rate**: Monitor `.cache/tts/` growth
5. **API quotas**: Track Gemini API usage
6. **Storage**: Monitor repo size and artifact retention

---

For issues or questions, please open a GitHub issue with:
- Error message and full logs
- Topic configuration
- Workflow run URL (if applicable)
- Steps to reproduce
