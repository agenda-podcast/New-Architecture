# TTS and Video Rendering Settings Update Summary

This document summarizes the changes made to TTS and video rendering settings per the requirements.

## TTS Settings Updates

### Audio Codec and Format
- **Codec**: Changed from MP3 (libmp3lame) to **AAC**
- **Container**: Changed from .mp3 to **.m4a**
- **Sample Rate**: Changed from 24,000 Hz to **44,100 Hz (44.1 kHz)**
- **Bitrate**: Set to **128 kbps stereo**
- **Channels**: 2 (stereo)

### Configuration Changes
- `TTS_SAMPLE_RATE`: 24000 → **44100**
- `GOOGLE_TTS_SAMPLE_RATE`: 24000 → **44100**
- New: `TTS_AUDIO_CODEC`: **'aac'**
- New: `TTS_AUDIO_BITRATE`: **'128k'**
- `AUDIO_PATTERN`: "{topic}-{date}-{code}.mp3" → **"{topic}-{date}-{code}.m4a"**

### Code Changes
- `convert_to_mp3()` → `convert_to_aac()` with AAC codec settings
- `tts_chunks_to_mp3()` → `tts_chunks_to_audio()` (with backward compatibility wrapper)
- All file references updated from .mp3 to .m4a

## Video Rendering Settings Updates

### Video Codec Settings
- **Codec**: H.264 (libx264) - already configured
- **Profile**: Added **High** profile
- **Keyframe Interval**: Added **2 seconds**

### Configuration Changes
- New: `VIDEO_CODEC`: **'libx264'**
- New: `VIDEO_CODEC_PROFILE`: **'high'**
- New: `VIDEO_KEYFRAME_INTERVAL_SEC`: **2**
- New: `VIDEO_BITRATE_SETTINGS` dictionary with format-specific settings

### Bitrate Settings by Content Type

#### Short and Reel Content (Vertical Format)
- **Resolution**: 1080 × 1920 pixels (9:16 aspect ratio) - already configured
- **Frame Rate**: 30 fps - already configured
- **Format**: MP4 with H.264 codec - already configured
- **Bitrate**: **8 Mbps** (within 6-10 Mbps range)
- **Maxrate**: **10 Mbps**
- **Bufsize**: **20 Mbps**

#### Long and Medium Content (Horizontal Format)
- **Resolution**: 1920 × 1080 pixels (16:9 aspect ratio) - already configured
- **Frame Rate**: 30 fps - already configured
- **Format**: MP4 with H.264 codec - already configured
- **Profile**: **High**
- **Keyframe Interval**: **2 seconds** (60 frames at 30 fps)
- **Bitrate**: **10 Mbps** (within 8-12 Mbps range for 1080p/30fps SDR)
- **Maxrate**: **12 Mbps**
- **Bufsize**: **24 Mbps**

### FFmpeg Command Updates

The video rendering now includes:
```bash
-c:v libx264           # H.264 video codec
-profile:v high        # H.264 High profile
-b:v <bitrate>         # Video bitrate (8M or 10M depending on format)
-maxrate <maxrate>     # Maximum bitrate
-bufsize <bufsize>     # Buffer size
-g <keyframe_frames>   # Keyframe interval in frames (fps * 2 seconds)
-c:a aac               # AAC audio codec
-b:a 128k              # Audio bitrate 128 kbps
```

## Files Modified

1. `scripts/global_config.py`
   - Updated TTS sample rates
   - Added TTS audio codec and bitrate settings
   - Added video codec profile and keyframe settings
   - Added video bitrate configuration dictionary
   - Changed audio pattern from .mp3 to .m4a

2. `scripts/tts_generate.py`
   - Renamed `convert_to_mp3()` to `convert_to_aac()`
   - Updated FFmpeg command to use AAC codec with proper settings
   - Renamed `tts_chunks_to_mp3()` to `tts_chunks_to_audio()`
   - Added backward compatibility wrapper
   - Updated all references to use .m4a extension

3. `scripts/video_render.py`
   - Updated FFmpeg command with H.264 profile
   - Added video bitrate settings (format-dependent)
   - Added keyframe interval calculation and setting
   - Added audio bitrate setting for AAC
   - Updated to look for .m4a audio files instead of .mp3

4. `scripts/release_uploader.py`
   - Updated file patterns from .mp3 to .m4a
   - Updated file category detection for .m4a files
   - Updated documentation comments

## Backward Compatibility

To maintain compatibility with existing tests and code:
- Added `tts_chunks_to_mp3()` as a wrapper function that calls `tts_chunks_to_audio()`
- The wrapper accepts the same parameters and maintains the same behavior
- Tests using the old function name will continue to work

## Verification

All settings have been verified:
- ✓ TTS sample rate: 44,100 Hz
- ✓ TTS codec: AAC
- ✓ TTS bitrate: 128 kbps stereo
- ✓ Audio file format: M4A
- ✓ Video codec: H.264 (libx264)
- ✓ Video profile: High
- ✓ Keyframe interval: 2 seconds
- ✓ Video bitrates: 8 Mbps (vertical), 10 Mbps (horizontal)
- ✓ All files compile without syntax errors
- ✓ All functions import correctly
- ✓ Backward compatibility maintained
