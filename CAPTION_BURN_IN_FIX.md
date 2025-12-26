# Caption Burn-in Fix - Technical Documentation

## Problem Statement

FFmpeg caption burn-in was failing with the error:
```
[AVFilterGraph @ 0x5651f1d0ef80] No option name near '63:fontcolor=white@0.18:borderw=20:bordercolor=cyan@0.25:shadowx=0:shadowy=0:x=(w-text_w)/2:y=h-384-text_h:enable=between(t\,18.057\,22.892)'
[AVFilterGraph @ 0x5651f1d0ef80] Error parsing a filter description around: ...
```

## Root Cause

The `_enable_between()` function in `video_render.py` was wrapping the `between()` expression in single quotes:

```python
def _enable_between(t0: float, t1: float) -> str:
    # INCORRECT - outer quotes break FFmpeg parsing
    return f"'between(t\\,{t0:.3f}\\,{t1:.3f})'"
```

This generated filter strings like:
```
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Breaking: New AI regulations':fontsize=63:fontcolor=white@0.18:borderw=20:bordercolor=cyan@0.25:shadowx=0:shadowy=0:x=(w-text_w)/2:y=h-384-text_h:enable='between(t\,0.000\,2.655)'
                                                                                                                                                                                              ↑                         ↑
                                                                                                                                                                              Quotes here break FFmpeg parsing
```

FFmpeg expects the `enable` parameter value to be an unquoted expression with escaped commas.

## Solution

Remove the outer quotes from the `_enable_between()` function:

```python
def _enable_between(t0: float, t1: float) -> str:
    # CORRECT - no outer quotes, just escaped commas
    return f"between(t\\,{t0:.3f}\\,{t1:.3f})"
```

This generates correct filter strings:
```
drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='Breaking: New AI regulations':fontsize=63:fontcolor=white@0.18:borderw=20:bordercolor=cyan@0.25:shadowx=0:shadowy=0:x=(w-text_w)/2:y=h-384-text_h:enable=between(t\,0.000\,2.655)
                                                                                                                                                                                              ↑                        ↑
                                                                                                                                                                              No quotes - FFmpeg parses correctly
```

## Changes Made

### File: `scripts/video_render.py`

1. **Fixed `_enable_between()` function** (line 850-853):
   - Removed outer single quotes
   - Kept backslash-escaped commas (required by FFmpeg)
   - Updated comment to clarify correct format

2. **Fixed docstring** (line 839):
   - Changed to raw string literal (`r"""...`)
   - Prevents Python escape sequence warning

## Testing

Created comprehensive test suite to verify the fix:

1. **test_caption_burn_in_fix.py** - Unit tests
   - Tests TikTok-style captions
   - Tests boxed-style captions  
   - Tests multiple captions
   - All tests pass ✓

2. **test_caption_integration.py** - Integration tests
   - Tests actual FFmpeg command execution (requires FFmpeg)
   - Validates filter syntax parsing

3. **demonstrate_caption_fix.py** - Demonstration
   - Shows before/after comparison
   - Explains the technical details

## Verification

```bash
# Run unit tests
python3 scripts/test_caption_burn_in_fix.py

# Run demonstration
python3 scripts/demonstrate_caption_fix.py

# Verify existing tests still pass
python3 scripts/test_video_render.py
```

All tests pass ✓

## FFmpeg Filter Syntax Reference

For the `drawtext` filter:
- Options are separated by colons (`:`)
- Option values with special characters need escaping
- The `enable` option expects an expression like `between(t,start,end)`
- Commas in expressions MUST be escaped: `between(t\,0.0\,2.5)`
- The entire expression should NOT be quoted

### Correct Format
```
enable=between(t\,0.000\,2.655)
```

### Incorrect Format (before fix)
```
enable='between(t\,0.000\,2.655)'
       ^                        ^
       Quotes break parsing
```

## Impact

This fix enables caption burn-in to work correctly for all video formats:
- TikTok-style captions (with glow effect)
- Boxed captions (classic style)
- Multiple timed captions in a single video

The error no longer occurs and captions are successfully overlaid on videos.
