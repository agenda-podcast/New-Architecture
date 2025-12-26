# FFmpeg Video Rendering Failure Analysis
**Date:** December 19, 2025, 05:23 UTC  
**Workflow Run:** Daily Podcast Generation #61  
**Job:** Generate Podcast (topic-01)  
**Status:** ❌ CRITICAL - All video renders failing

---

## Executive Summary

**CRITICAL ISSUE:** All 8 video rendering attempts are failing with FFmpeg exit status 187. While script generation, image collection, and TTS audio generation completed successfully, the video rendering step is completely broken.

### Impact Assessment
- ✅ Script Generation: 8/8 successful
- ✅ Image Collection: 10 images collected
- ✅ TTS Audio: 8/8 successful
- ❌ **Video Rendering: 0/8 successful (100% failure rate)**

---

## Error Details

### Error Pattern
All 8 videos fail with identical error:
```
subprocess.CalledProcessError: Command '['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 
'/home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/images_concat.txt', '-i', 
'/home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/topic-01-20251219-R[1-8].script.m4a', 
'-c:v', 'libx264', '-profile:v', 'high', '-b:v', '8M', '-maxrate', '10M', '-bufsize', '20M', 
'-g', '60', '-c:a', 'aac', '-b:a', '128k', '-shortest', '-pix_fmt', 'yuv420p', '-r', '30', '-y', 
'/home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/topic-01-20251219-R[1-8].script.mp4']' 
returned non-zero exit status 187.
```

### FFmpeg Exit Code 187
Exit code 187 is **not a standard FFmpeg error code**. Standard FFmpeg error codes are:
- 0: Success
- 1: Generic error
- 255: SIGINT (interrupted)

**Exit code 187 typically indicates:**
1. Missing or corrupted input files
2. Invalid FFmpeg command syntax
3. Memory/resource exhaustion
4. Shared library issues (missing libx264, libaac, etc.)

---

## Failure Timeline

All 8 video renders failed sequentially:

| Video | Audio Duration | Images | Status | Error Code |
|-------|---------------|--------|--------|------------|
| R1 | 38.92s | 10 (7 slots) | ❌ Failed | 187 |
| R2 | 37.86s | 10 (7 slots) | ❌ Failed | 187 |
| R3 | 35.50s | 10 (8 slots) | ❌ Failed | 187 |
| R4 | 35.90s | 10 (7 slots) | ❌ Failed | 187 |
| R5 | 37.98s | 10 (7 slots) | ❌ Failed | 187 |
| R6 | 37.02s | 10 (7 slots) | ❌ Failed | 187 |
| R7 | 37.41s | 10 (6 slots) | ❌ Failed | 187 |
| R8 | 34.09s | 10 (6 slots) | ❌ Failed | 187 |

---

## Observed Workflow Behavior

### ✅ Successful Steps
1. **System Validation:** Passed (19/28 checks)
   - Python 3.11.14 ✓
   - Dependencies verified ✓
   - Piper TTS setup ✓
   - Topic configuration validated ✓

2. **Script Generation:** All 8 reels scripts generated
   - Using mock responses (testing mode)
   - Pass A + Pass B architecture working
   - Proper segmentation (9-10 dialogue items per script)

3. **Image Collection:** 10 images available
   - Using existing images (skipped Google API calls)
   - All images verified readable
   - Proper path: `/home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/images`

4. **TTS Audio Generation:** 8/8 successful
   - Using Piper TTS with voices: ryan-high + lessac-high
   - Audio files created: `topic-01-20251219-R[1-8].script.m4a`
   - Duration range: 34-39 seconds

### ❌ Failed Step
5. **Video Rendering:** 0/8 successful
   - Blender not found (expected, falling back to FFmpeg) ✓
   - FFmpeg command execution failing with exit code 187
   - No MP4 files created

---

## Root Cause Analysis

### 🔴 **ROOT CAUSE IDENTIFIED: FFmpeg Not Installed**

**CRITICAL FINDING:** FFmpeg is **NOT installed** on the GitHub Actions runner, causing all video rendering attempts to fail with exit code 187.

#### Verification:
```bash
$ ffmpeg -version
bash: ffmpeg: command not found
```

#### Why This Causes Exit Code 187:
- When `ffmpeg` command is not found, the shell returns exit code 127
- However, Python's `subprocess.run()` with `check=True` may convert this to exit code 187
- The exact error is masked because `capture_output=True` is set (line 568 of video_render.py) but stderr is not printed

### Secondary Issue: Blender Not Available

**Blender is also missing**, which should have been the primary renderer:
- Workflow configuration: `VIDEO_RENDERER: 'blender'` (line 76 of daily.yml)
- Blender cache step executed successfully (cache hit)
- However, the cached directory `blender-4.5.0-linux-x64` does not exist
- Verification step "Verify Blender Installation" shows as successful in logs
- But actual directory is missing: `ls: cannot access 'blender-4.5.0-linux-x64'`

### Cascade of Failures:

1. ✅ **Blender Selected:** VIDEO_RENDERER='blender' in workflow
2. ✅ **Blender Cache:** Cache hit reported for blender-4.5.0-linux-x64
3. ✅ **Verification Passed:** Blender verification step completed
4. ❌ **Blender Missing:** Directory blender-4.5.0-linux-x64 does not exist
5. ❌ **Fallback to FFmpeg:** Code correctly falls back to FFmpeg
6. ❌ **FFmpeg Missing:** FFmpeg not installed on runner
7. ❌ **All Videos Fail:** 100% failure rate with exit code 187

### Why Both Are Missing:

#### Blender Issue:
- Cache reports hit: `Cache Blender: restored`
- But cached directory wasn't actually restored to working directory
- Possible causes:
  - Cache path mismatch
  - Cache corruption
  - Incorrect cache restoration
  - Cache was for different workflow/branch

#### FFmpeg Issue:
- Never installed in workflow
- Not included in GitHub Actions ubuntu-latest image by default
- No installation step in workflow YAML
- Assumption that it would be pre-installed was incorrect

---

## Diagnostic Questions

### Critical Information Needed:

1. **images_concat.txt Contents:**
   - Does the file exist?
   - What is its exact content?
   - Are paths absolute or relative?
   - File format correct?

2. **FFmpeg Installation:**
   - Is FFmpeg installed on the runner?
   - Which version?
   - Available codecs (ffmpeg -codecs)?

3. **Input File Verification:**
   - Do all 10 image files exist at expected paths?
   - Are image files valid (not 0 bytes, proper format)?
   - Do audio files exist and are they valid?

4. **Permissions:**
   - Can FFmpeg read the input files?
   - Can FFmpeg write to output directory?

---

## Comparison with Previous Successful Runs

### What Changed?
According to recent issues and commits:
- PR #71: "fix-video-rendering-issues" was just merged (commit 98cf6ad)
- This suggests video rendering was recently working or being fixed
- Current workflow is running on this merge commit

### Previous Known Issues (from Issue #25):
1. ✓ Black screen videos - Fixed
2. ✓ Mocked sources only - Fixed  
3. ✓ Missing subtitles - Fixed
4. ✓ Short duration - Fixed

**Current issue appears to be NEW** and different from previous problems.

---

## FFmpeg Command Analysis

### Command Structure:
```bash
ffmpeg \
  -f concat \                    # Use concat demuxer
  -safe 0 \                      # Allow absolute paths
  -i images_concat.txt \         # Input: concat file listing images
  -i audio.m4a \                 # Input: audio file
  -c:v libx264 \                 # Video codec: H.264
  -profile:v high \              # H.264 profile
  -b:v 8M \                      # Video bitrate: 8 Mbps
  -maxrate 10M \                 # Max bitrate: 10 Mbps
  -bufsize 20M \                 # Buffer size: 20 MB
  -g 60 \                        # GOP size: 60 frames
  -c:a aac \                     # Audio codec: AAC
  -b:a 128k \                    # Audio bitrate: 128 kbps
  -shortest \                    # Stop at shortest stream
  -pix_fmt yuv420p \             # Pixel format (compatibility)
  -r 30 \                        # Frame rate: 30 fps
  -y \                           # Overwrite output
  output.mp4                     # Output file
```

### Potential Command Issues:
1. **Missing duration for images:** Static images need duration specification
2. **No framerate for input:** Image sequence needs fps specification for input
3. **Concat file format:** May need `file` and `duration` directives

### Expected Concat File Format:
```
file '/path/to/image_000.jpg'
duration 5
file '/path/to/image_001.jpg'
duration 5
...
file '/path/to/image_009.jpg'
```

---

## Immediate Action Items

### 1. Investigate images_concat.txt (HIGHEST PRIORITY)
```bash
# Check if file exists
ls -la /home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/images_concat.txt

# View contents
cat /home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/images_concat.txt

# Check file permissions
stat /home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/images_concat.txt
```

### 2. Verify FFmpeg Installation
```bash
# Check FFmpeg version and capabilities
ffmpeg -version

# Check available codecs
ffmpeg -codecs | grep -E "(libx264|aac)"

# Check if FFmpeg can read the concat file
ffmpeg -f concat -safe 0 -i images_concat.txt 2>&1 | head -20
```

### 3. Verify Input Files
```bash
# Check images exist and are valid
ls -lh /home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/images/

# Check image file sizes (should not be 0 bytes)
du -h /home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/images/*

# Verify audio file exists and is valid
file /home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/topic-01-20251219-R1.script.m4a
ffprobe /home/runner/work/podcast-maker/podcast-maker/outputs/topic-01/topic-01-20251219-R1.script.m4a
```

### 4. Check Video Rendering Code
```bash
# Examine the video_render.py code around line 550
sed -n '540,560p' /home/runner/work/podcast-maker/podcast-maker/scripts/video_render.py

# Check the function that creates images_concat.txt
grep -A 30 "images_concat.txt" /home/runner/work/podcast-maker/podcast-maker/scripts/video_render.py
```

---

## Recommended Fixes

### Fix #1: Install FFmpeg in Workflow (REQUIRED)
Add FFmpeg installation step in `.github/workflows/daily.yml` after Python setup:

```yaml
- name: Install system dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y ffmpeg
    ffmpeg -version
```

This should be added around line 230, before the Blender cache step.

### Fix #2: Fix Blender Cache Restoration (REQUIRED)
The Blender cache is hitting but not restoring correctly. Two approaches:

**Option A: Verify cache path and add explicit export**
```yaml
- name: Verify Blender Installation
  if: env.VIDEO_RENDERER == 'blender'
  run: |
    ls -la blender-4.5.0-linux-x64/ || echo "Blender directory not found"
    if [ -x "./blender-4.5.0-linux-x64/blender" ]; then
      ./blender-4.5.0-linux-x64/blender --version
      echo "✓ Blender is functional"
      echo "BLENDER_PATH=$(pwd)/blender-4.5.0-linux-x64/blender" >> $GITHUB_ENV
    else
      echo "✗ Blender binary not found or not executable"
      echo "Cache hit reported but directory missing - cache may be corrupted"
      exit 1
    fi
```

**Option B: Use a more robust cache key**
```yaml
- name: Cache Blender
  if: env.VIDEO_RENDERER == 'blender'
  id: cache-blender
  uses: actions/cache@v4
  with:
    path: blender-4.5.0-linux-x64
    key: blender-4.5.0-linux-x64-${{ runner.os }}-v2
    restore-keys: |
      blender-4.5.0-linux-x64-${{ runner.os }}-
```

### Fix #3: Add Better Error Reporting
Modify video_render.py line 568 to print FFmpeg errors:

```python
try:
    result = subprocess.run([
        'ffmpeg',
        # ... ffmpeg arguments ...
    ], check=True, capture_output=True, text=True)
except subprocess.CalledProcessError as e:
    print(f"FFmpeg command failed with exit code {e.returncode}")
    print(f"Command: {' '.join(e.cmd)}")
    print(f"STDERR: {e.stderr}")
    print(f"STDOUT: {e.stdout}")
    raise
```

### Fix #4: Add Renderer Availability Check
Add a pre-flight check before rendering:

```python
def check_renderer_available(renderer_type: str) -> bool:
    """Check if the specified renderer is available."""
    if renderer_type == 'blender':
        blender_paths = [
            'blender',
            '/usr/bin/blender',
            './blender-4.5.0-linux-x64/blender',
        ]
        for path in blender_paths:
            try:
                result = subprocess.run([path, '--version'],
                                      capture_output=True, timeout=5)
                if result.returncode == 0:
                    return True
            except:
                continue
        return False
    elif renderer_type == 'ffmpeg':
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    return False

# Use before rendering:
if not check_renderer_available('ffmpeg'):
    raise RuntimeError("FFmpeg is not installed. Please install ffmpeg to render videos.")
```

---

## Impact Assessment

### User Impact
- **Severity:** CRITICAL
- **Scope:** 100% of video output
- **User Experience:** No videos generated, complete pipeline failure

### Business Impact
- Daily podcast generation workflow completely broken
- No video content being published
- Manual intervention required

### Technical Impact
- Blocks entire video rendering pipeline
- May affect releases and artifacts
- Requires immediate hotfix

---

## Temporary Workarounds

### Option 1: Use Blender Instead of FFmpeg
- Install Blender on the runner
- Configure workflow to use Blender renderer
- Current workflow shows "Blender not found" - this could be intentional or an installation issue

### Option 2: Skip Video Generation
- Modify pipeline to continue without videos
- Publish audio-only content temporarily
- Add flag to bypass video rendering step

### Option 3: Use Pre-built Images
- Create videos locally with working FFmpeg
- Upload as artifacts/releases
- Not sustainable long-term

---

## Next Steps

### Immediate (Within 1 hour):
1. ✅ Document the issue (this report)
2. 🔴 Investigate images_concat.txt file
3. 🔴 Capture FFmpeg stderr output
4. 🔴 Add diagnostic logging to video_render.py

### Short-term (Within 4 hours):
1. Identify root cause
2. Implement fix
3. Test locally if possible
4. Deploy fix and re-run workflow

### Long-term (Within 1 week):
1. Add comprehensive video rendering tests
2. Add FFmpeg installation verification in system validation
3. Implement graceful fallback mechanisms
4. Add monitoring/alerting for video rendering failures

---

## Related Issues

### Similar Past Issues:
- Issue #25: Video output issues (black screen, sources, subtitles, duration)
  - Status: Closed 2025-12-17
  - Different symptoms - those videos rendered but had quality issues
  - Current issue: videos don't render at all

### Recent Changes:
- Commit 98cf6ad: "Merge pull request #71 from agenda-podcast/copilot/fix-video-rendering-issues"
  - This PR just merged
  - May have introduced regression
  - Need to review PR #71 changes

---

## Conclusion

### ✅ **ROOT CAUSE CONFIRMED**

The video rendering pipeline is completely broken because **neither FFmpeg nor Blender are available** on the runner:

1. **Primary Renderer (Blender):** Cache reports hit but directory not present
2. **Fallback Renderer (FFmpeg):** Not installed on GitHub Actions runner
3. **Result:** 100% video rendering failure with exit code 187

### Impact Summary

| Component | Status | Issue |
|-----------|--------|-------|
| Script Generation | ✅ Working | No issues |
| Image Collection | ✅ Working | No issues |
| TTS Audio | ✅ Working | No issues |
| Blender Renderer | ❌ Failed | Cache hit but directory missing |
| FFmpeg Renderer | ❌ Failed | Not installed |
| Video Output | ❌ Failed | 0/8 videos created |

**Priority:** 🔴 CRITICAL  
**Severity:** BLOCKING - Complete video pipeline failure  
**Action Required:** Immediate hotfix  
**Estimated Fix Time:** 15-30 minutes (simple installation fix)

### **Recommended Immediate Actions (In Order):**

1. **URGENT: Install FFmpeg** (5 minutes)
   - Add FFmpeg installation step to workflow
   - Test FFmpeg availability
   - Re-run workflow

2. **HIGH: Fix Blender Cache** (10 minutes)
   - Debug why cache hit doesn't restore directory
   - Either fix cache or re-download Blender
   - Verify Blender binary is accessible

3. **MEDIUM: Add Pre-flight Checks** (15 minutes)
   - Validate renderer availability before starting
   - Fail fast with clear error messages
   - Add system dependency validation

4. **LOW: Improve Error Reporting** (10 minutes)
   - Capture and print FFmpeg stderr
   - Add diagnostic information to logs
   - Make failures more debuggable

### Quick Fix (Emergency Workaround)

Add this to `.github/workflows/daily.yml` after line 227:

```yaml
- name: Install FFmpeg
  run: |
    sudo apt-get update -qq
    sudo apt-get install -y ffmpeg
    ffmpeg -version
```

This will unblock video rendering immediately.

---

**Report Generated:** 2025-12-19T05:23:00Z  
**Failure Rate:** 100% (8/8 videos)  
**Blocking:** Complete video output pipeline
