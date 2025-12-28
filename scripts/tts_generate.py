#!/usr/bin/env python3
"""Generate TTS audio for podcast script."""
import argparse
import json
import sys
import os
import hashlib
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import glob
import re

from config import load_topic_config, get_output_dir, get_repo_root
from global_config import (
    TTS_CACHE_ENABLED, TTS_SAMPLE_RATE, TTS_USE_CHUNKING,
    GOOGLE_TTS_SAMPLE_RATE, GOOGLE_TTS_LANGUAGE_CODE,
    resolve_voice_for_gender, get_available_voice_for_gender
)

# Caption shaping
from global_config import (
    CAPTIONS_WORDS_PER_LINE,
    CAPTIONS_MAX_LINES,
    CAPTIONS_TARGET_LINES,
)

# Import TTS chunker for long-form audio
try:
    from tts_chunker import generate_tts_with_chunking
    TTS_CHUNKER_AVAILABLE = True
except ImportError:
    TTS_CHUNKER_AVAILABLE = False
    print("Warning: tts_chunker not available - long-form audio may have issues")

# TTS cache version - increment to invalidate all TTS caches
TTS_CACHE_VERSION = "1.0"


def get_cache_dir() -> Path:
    """Get or create TTS cache directory."""
    cache_dir = get_repo_root() / '.cache' / 'tts'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def compute_tts_cache_key(provider: str, voice: str, text: str) -> str:
    """Compute cache key for TTS chunk."""
    combined = f"{provider}|{voice}|{text}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def generate_tts_gemini(text: str, voice: str, output_path: Path) -> bool:
    """
    Generate TTS using Google Cloud Text-to-Speech API.
    
    Requires GOOGLE_API_KEY environment variable to be set.
    """
    try:
        # Try using Google Cloud TTS
        try:
            from google.cloud import texttospeech
            
            # Initialize client (will use credentials from environment)
            client = texttospeech.TextToSpeechClient()
            
            # Set up synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Set up voice parameters
            # Map Gemini voice names to Google Cloud TTS voices
            voice_params = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name=voice
            )
            
            # Set up audio config
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=GOOGLE_TTS_SAMPLE_RATE
            )
            
            # Perform TTS request
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )
            
            # Write audio to file
            with open(output_path, 'wb') as f:
                f.write(response.audio_content)
            
            return True
            
        except ImportError:
            print(f"Google Cloud TTS library not available")
            raise
    
    except Exception as e:
        print(f"Error generating Google Cloud TTS: {e}")
        print(f"FAILED: Google Cloud TTS is unavailable or misconfigured.")
        print(f"Please ensure GOOGLE_API_KEY is set correctly.")
        print(f"Also verify the Google Cloud Text-to-Speech API is enabled for your project.")
        return False


def generate_tts_piper(text: str, voice: str, output_path: Path) -> bool:
    """
    Generate TTS using Piper (local).
    
    Uses piper binary to generate speech from text.
    Voice models should be available in ~/.local/share/piper-tts/voices/ (cached).
    """
    try:
        # Check for voice model at expected location
        voice_path = Path.home() / '.local' / 'share' / 'piper-tts' / 'voices' / f'{voice}.onnx'
        config_path = Path.home() / '.local' / 'share' / 'piper-tts' / 'voices' / f'{voice}.onnx.json'
        
        # If voice doesn't exist, provide helpful error message
        if not voice_path.exists() or not config_path.exists():
            print(f"Voice model not found: {voice}")
            print(f"Voice models should be available in: {voice_path.parent}")
            raise FileNotFoundError(f"Piper voice model not found: {voice}")
        
        # Use piper binary directly to avoid Python library file handling issues
        # The piper binary properly handles binary model files
        # Try to find piper binary in common locations
        piper_binary = None
        piper_dir = None
        possible_paths = [
            get_repo_root() / 'piper' / 'piper',  # Cached location in repo
            Path('/usr/local/bin/piper'),
            Path('/usr/bin/piper'),
        ]
        for path in possible_paths:
            if path.exists():
                piper_binary = str(path)
                piper_dir = str(path.parent)
                break
        
        if not piper_binary:
            raise FileNotFoundError("Piper binary not found in expected locations")
        
        # Set up environment for piper binary (add lib directory to LD_LIBRARY_PATH)
        env = os.environ.copy()
        if piper_dir:
            ld_library_path = env.get('LD_LIBRARY_PATH', '')
            env['LD_LIBRARY_PATH'] = f"{piper_dir}:{ld_library_path}" if ld_library_path else piper_dir
        
        result = subprocess.run([
            piper_binary,
            '--model', str(voice_path),
            '--output_file', str(output_path)
        ], input=text.encode('utf-8'), capture_output=True, env=env, timeout=60)
        
        if result.returncode == 0:
            return True
        else:
            error_msg = result.stderr.decode('utf-8', errors='replace') if result.stderr else "Unknown error"
            raise Exception(f"Piper binary failed: {error_msg}")
    
    except Exception as e:
        print(f"Error generating Piper TTS: {e}")
        print(f"FAILED: Piper TTS is unavailable or misconfigured.")
        print(f"Please ensure voice models are available in: ~/.local/share/piper-tts/voices/")
        return False


def trim_silence(audio_path: Path) -> bool:
    """Trim silence from audio file."""
    try:
        temp_path = audio_path.with_suffix('.tmp.wav')
        subprocess.run([
            'ffmpeg', '-i', str(audio_path),
            '-af', 'silenceremove=1:0:-50dB',
            '-y', str(temp_path)
        ], check=True, capture_output=True)
        temp_path.replace(audio_path)
        return True
    except Exception:
        return False


def _probe_duration_seconds(media_path: Path) -> float:
    """Return media duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(media_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000.0))
    hh = ms // 3_600_000
    ms -= hh * 3_600_000
    mm = ms // 60_000
    ms -= mm * 60_000
    ss = ms // 1000
    ms -= ss * 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _shape_caption_lines(words: List[str]) -> str:
    """Shape caption block into 2-3 lines, 4-5 words per line."""
    if not words:
        return ""

    wpl = max(3, CAPTIONS_WORDS_PER_LINE)

    # Prefer 2 lines, allow up to CAPTIONS_MAX_LINES.
    target_lines = max(1, min(CAPTIONS_TARGET_LINES, CAPTIONS_MAX_LINES))
    max_lines = max(1, CAPTIONS_MAX_LINES)

    # Compute a reasonable per-line word count to keep within max lines.
    total = len(words)
    # If short, keep as 1-2 lines.
    if total <= wpl:
        lines = [' '.join(words)]
        return '\n'.join(lines)

    # Determine number of lines for this block.
    # Start with 2 lines, expand to 3 if needed.
    lines_count = target_lines
    if total > wpl * target_lines and max_lines >= 3:
        lines_count = 3

    # Derive per-line chunk sizes (balanced, but capped to wpl).
    base = (total + lines_count - 1) // lines_count
    per_line = min(wpl, max(4, base))

    lines = []
    idx = 0
    for _ in range(lines_count):
        if idx >= total:
            break
        lines.append(' '.join(words[idx: idx + per_line]))
        idx += per_line
    if idx < total:
        # Append remaining words to last line if any
        lines[-1] = (lines[-1] + ' ' + ' '.join(words[idx:])).strip()
    return '\n'.join(lines[:max_lines])


def _write_captions_srt(captions: List[Dict[str, Any]], srt_path: Path) -> None:
    """Write captions list to an SRT file."""
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, cap in enumerate(captions, start=1):
            f.write(f"{i}\n")
            f.write(f"{_format_srt_timestamp(cap['start'])} --> {_format_srt_timestamp(cap['end'])}\n")
            f.write(f"{cap['text']}\n\n")


def generate_tts_chunk(text: str, voice: str, premium: bool, cache_dir: Path) -> Path:
    """
    Generate or retrieve cached TTS for a text chunk.
    
    Raises an exception if TTS generation fails, ensuring fail-fast behavior.
    """
    # Force Piper when premium parameter is False, regardless of GOOGLE_API_KEY presence
    # This ensures we use local TTS for non-premium topics (controlled by premium_tts config field)
    provider = 'gemini' if premium else 'piper'
    cache_key = compute_tts_cache_key(provider, voice, text)
    cache_path = cache_dir / f"{cache_key}.wav"
    meta_path = cache_dir / f"{cache_key}.meta.json"
    
    # Check if cache exists and is valid
    if cache_path.exists() and meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            # Validate cache version
            if meta.get('version') == TTS_CACHE_VERSION:
                return cache_path
            else:
                # Invalid version, regenerate
                print(f"  Cache version mismatch, regenerating...")
        except Exception:
            # Corrupt metadata, regenerate
            pass
    
    if cache_path.exists() and not meta_path.exists():
        # Old cache without metadata, still valid
        return cache_path
    
    # Generate new TTS - always use Piper for non-premium topics
    if premium:
        # Only attempt Google Cloud TTS (via Gemini API) if explicitly premium
        success = generate_tts_gemini(text, voice, cache_path)
        if not success:
            raise Exception(
                f"Failed to generate TTS using Google Cloud TTS for voice '{voice}'. "
                "Ensure GOOGLE_API_KEY is set and the Google Cloud Text-to-Speech API is enabled."
            )
    else:
        # Force Piper TTS for non-premium topics (local, offline TTS)
        success = generate_tts_piper(text, voice, cache_path)
        if not success:
            raise Exception(
                f"Failed to generate TTS using Piper for voice '{voice}'. "
                "Ensure voice models are available in ~/.local/share/piper-tts/voices/"
            )
    
    # Save metadata for cache validation
    try:
        meta_data = {
            'version': TTS_CACHE_VERSION,
            'provider': provider,
            'voice': voice,
            'timestamp': datetime.now().isoformat()
        }
        with open(meta_path, 'w') as f:
            json.dump(meta_data, f, indent=2)
    except Exception as e:
        print(f"  Warning: Failed to save cache metadata: {e}")
    
    trim_silence(cache_path)
    return cache_path


def _build_concat_filter(audio_files: List[Path], gap_sec: float) -> tuple:
    """
    Build filter components for audio concatenation.
    
    Returns:
        tuple: (inputs, filter_parts, concat_inputs)
    """
    inputs = []
    filter_parts = []
    concat_inputs = []
    
    for i, audio_file in enumerate(audio_files):
        inputs.extend(['-i', str(audio_file)])
        if i < len(audio_files) - 1:  # Add gap to all but last
            filter_parts.append(f'[{i}:a]apad=pad_dur={gap_sec}[a{i}]')
            concat_inputs.append(f'[a{i}]')
        else:  # Last one without gap
            concat_inputs.append(f'[{i}:a]')
    
    return inputs, filter_parts, concat_inputs


def _format_filter_complex(filter_parts: List[str], concat_inputs: List[str], num_files: int) -> str:
    """
    Format complete FFmpeg filter complex string.
    
    Format: [0:a]apad=pad_dur={gap}[a0]; [1:a]apad=pad_dur={gap}[a1]; ... [a0][a1]...concat=n={N}:v=0:a=1[out]
    """
    filter_str = ''
    if filter_parts:
        filter_str = '; '.join(filter_parts) + '; '
    
    filter_str += ''.join(concat_inputs) + f'concat=n={num_files}:v=0:a=1[out]'
    return filter_str


def concatenate_audio_files(audio_files: List[Path], output_path: Path, gap_ms: int = 500) -> bool:
    """Concatenate audio files with gaps."""
    try:
        if not audio_files:
            return False
        
        # If only one file, just copy it
        if len(audio_files) == 1:
            subprocess.run([
                'ffmpeg', '-i', str(audio_files[0]), '-y', str(output_path)
            ], check=True, capture_output=True)
            return True
        
        # Build filter complex for concatenation with gaps
        gap_sec = gap_ms / 1000.0
        
        inputs, filter_parts, concat_inputs = _build_concat_filter(
            audio_files, gap_sec
        )
        
        filter_complex = _format_filter_complex(filter_parts, concat_inputs, len(audio_files))
        
        # Run ffmpeg
        cmd = ['ffmpeg'] + inputs + [
            '-filter_complex', filter_complex,
            '-map', '[out]',
            '-y', str(output_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return True
        
    except Exception as e:
        print(f"Error concatenating audio: {e}")
        return False


def convert_to_aac(wav_path: Path, aac_path: Path) -> bool:
    """Convert WAV to AAC with 44.1 kHz sample rate and 128 kbps stereo bitrate."""
    try:
        from global_config import TTS_AUDIO_CODEC, TTS_AUDIO_BITRATE, TTS_SAMPLE_RATE
        subprocess.run([
            'ffmpeg',
            '-i', str(wav_path),
            '-codec:a', TTS_AUDIO_CODEC,
            '-b:a', TTS_AUDIO_BITRATE,
            '-ar', str(TTS_SAMPLE_RATE),
            '-ac', '2',  # Stereo
            '-y', str(aac_path)
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Error converting to AAC: {e}")
        return False


def split_into_chunks(text: str, max_chars: int = 500) -> List[str]:
    """Split text into chunks for TTS."""
    chunks = []
    words = text.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        if current_length + word_length > max_chars and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def tts_chunks_to_audio(dialogue_chunks: List[Dict[str, str]], audio_path: Path, 
                        config: Dict[str, Any]) -> bool:
    """
    Generate TTS for dialogue chunks and create audio file (AAC/M4A format).
    
    Uses chunking strategy or single run based on configuration.
    
    Args:
        dialogue_chunks: List of {'speaker': 'A'|'B', 'text': '...'}
        audio_path: Output audio file path (M4A with AAC codec)
        config: Topic configuration
    """
    premium = config.get('premium_tts', False)
    
    # Check if chunking is enabled (from topic config or global default)
    # Topic config takes precedence over global default
    use_chunking = config.get('tts_use_chunking', TTS_USE_CHUNKING)
    
    # Calculate total character count for logging
    total_chars = sum(len(chunk.get('text', '')) for chunk in dialogue_chunks)
    
    # Use chunking strategy if enabled and available
    if use_chunking and TTS_CHUNKER_AVAILABLE:
        print(f"Using chunking strategy ({total_chars} chars)")
        return _tts_with_chunking(dialogue_chunks, audio_path, config)
    elif use_chunking and not TTS_CHUNKER_AVAILABLE:
        # Warn if chunking was requested but unavailable
        print(f"⚠ Warning: Chunking requested but tts_chunker not available")
        print(f"Falling back to single run strategy ({total_chars} chars)")
        return _tts_traditional(dialogue_chunks, audio_path, config)
    else:
        # Use single run approach (traditional)
        print(f"Using single run strategy ({total_chars} chars)")
        return _tts_traditional(dialogue_chunks, audio_path, config)


# Backward compatibility alias for tests
def tts_chunks_to_mp3(dialogue_chunks: List[Dict[str, str]], audio_path: Path, 
                      config: Dict[str, Any]) -> bool:
    """
    DEPRECATED: Backward compatibility wrapper for tts_chunks_to_audio.
    
    NOTE: Despite the function name, this now generates M4A files with AAC codec,
    not MP3 files. The function name is kept for backward compatibility with
    existing tests and code.
    
    Deprecation: This function will be removed in a future version. 
    New code should use tts_chunks_to_audio instead.
    
    Args:
        dialogue_chunks: List of {'speaker': 'A'|'B', 'text': '...'}
        audio_path: Output audio file path (M4A with AAC codec)
        config: Topic configuration
        
    Returns:
        True if successful, False otherwise
    """
    return tts_chunks_to_audio(dialogue_chunks, audio_path, config)


def _tts_with_chunking(dialogue_chunks: List[Dict[str, str]], audio_path: Path,
                       config: Dict[str, Any]) -> bool:
    """
    Generate TTS using advanced chunking strategy.
    
    This function delegates to tts_chunker module for reliable long-form synthesis.
    """
    # Get voice configuration (same as traditional approach)
    voice_a_gender = config.get('voice_a_gender', None)
    voice_b_gender = config.get('voice_b_gender', None)
    voice_quality = config.get('voice_quality', None)
    premium = config.get('premium_tts', False)
    
    # Get voices
    if voice_a_gender:
        voice_a, _, _ = get_available_voice_for_gender(voice_a_gender, voice_quality, premium)
    else:
        voice_a = config.get('tts_voice_a', 'en_US-ryan-high')
    
    if voice_b_gender:
        voice_b, _, _ = get_available_voice_for_gender(voice_b_gender, voice_quality, premium)
    else:
        voice_b = config.get('tts_voice_b', 'en_US-lessac-high')
    
    print(f"Using voices with chunking: A={voice_a}, B={voice_b}")
    
    # Determine primary voice (use voice A for mixed content)
    primary_voice = voice_a
    
    # Generate to temporary WAV first
    temp_wav = audio_path.with_suffix('.wav')
    
    # Use tts_chunker module
    success = generate_tts_with_chunking(
        dialogue=dialogue_chunks,
        voice=primary_voice,
        output_file=temp_wav,
        speed=1.0
    )
    
    if not success:
        print("Chunking strategy failed")
        return False
    
    # Convert to AAC
    success = convert_to_aac(temp_wav, audio_path)

    # Captions for chunked mode (best-effort).
    # We allocate the final audio duration across dialogue chunks using word-count weighting.
    try:
        if success:
            total_dur = probe_duration_seconds(audio_path)
            if total_dur > 0:
                captions = build_captions_from_dialogue_estimate(
                    dialogue_chunks=dialogue_chunks,
                    total_duration_s=total_dur,
                    gap_ms=500,
                    max_words_per_line=CAPTIONS_WORDS_PER_LINE,
                    target_lines=CAPTIONS_TARGET_LINES,
                    max_lines=CAPTIONS_MAX_LINES,
                )
                if captions:
                    srt_path = audio_path.with_suffix('.captions.srt')
                    json_path = audio_path.with_suffix('.captions.json')
                    write_captions_srt(captions, srt_path)
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump({'captions': captions, 'dialogue_chunks': dialogue_chunks}, f, indent=2, ensure_ascii=False)
                    print(f"  ✓ Captions generated (chunked): {srt_path.name}")
    except Exception as e:
        print(f"  ⚠ Caption generation failed in chunked mode (non-fatal): {e}")

    # Clean up temp file
    if temp_wav.exists():
        temp_wav.unlink()

    return success


def _tts_traditional(dialogue_chunks: List[Dict[str, str]], audio_path: Path,
                    config: Dict[str, Any]) -> bool:
    """
    Generate TTS using single run approach (non-chunked).
    
    This is the default implementation used when tts_use_chunking is False.
    Processes all dialogue in a single run per content type without splitting
    into smaller chunks. Suitable for most content types.
    """
    premium = config.get('premium_tts', False)
    
    # Get voice configuration - support both legacy and new gender-based system
    # Legacy: explicit tts_voice_a and tts_voice_b fields
    # New: voice_a_gender/voice_b_gender with optional voice_quality field
    
    # Try to get gender-based voices first (new system)
    voice_a_gender = config.get('voice_a_gender', None)
    voice_b_gender = config.get('voice_b_gender', None)
    voice_quality = config.get('voice_quality', None)  # Optional quality: high/medium/low
    
    # Initialize voices and warnings
    voice_a_warnings = []
    voice_b_warnings = []
    
    if voice_a_gender:
        # Use new gender-based system for voice A
        voice_a, is_fallback, warning = get_available_voice_for_gender(
            voice_a_gender, voice_quality, premium
        )
        if warning:
            voice_a_warnings.append(warning)
    else:
        # Fallback to legacy explicit voice configuration
        if premium:
            # For premium, use explicit config or default (no availability check needed)
            voice_a = config.get('tts_voice_a', 'en-US-Journey-D')
        else:
            # For Piper, check if explicit voice is provided
            if 'tts_voice_a' in config:
                explicit_voice = config['tts_voice_a']
                # Check if explicit voice is available
                from global_config import check_voice_availability
                if check_voice_availability(explicit_voice):
                    voice_a = explicit_voice
                else:
                    # Explicit voice not available, use gender-based fallback (assume male default)
                    voice_a, is_fallback, warning = get_available_voice_for_gender(
                        'male', voice_quality, premium
                    )
                    voice_a_warnings.append(
                        f"⚠ Configured voice '{explicit_voice}' not available. Using fallback: '{voice_a}'"
                    )
                    if warning:
                        voice_a_warnings.append(warning)
            else:
                # No explicit voice, use gender-based default (male)
                voice_a, is_fallback, warning = get_available_voice_for_gender(
                    'male', voice_quality, premium
                )
                if warning:
                    voice_a_warnings.append(warning)
    
    if voice_b_gender:
        # Use new gender-based system for voice B
        voice_b, is_fallback, warning = get_available_voice_for_gender(
            voice_b_gender, voice_quality, premium
        )
        if warning:
            voice_b_warnings.append(warning)
    else:
        # Fallback to legacy explicit voice configuration
        if premium:
            # For premium, use explicit config or default (no availability check needed)
            voice_b = config.get('tts_voice_b', 'en-US-Journey-F')
        else:
            # For Piper, check if explicit voice is provided
            if 'tts_voice_b' in config:
                explicit_voice = config['tts_voice_b']
                # Check if explicit voice is available
                from global_config import check_voice_availability
                if check_voice_availability(explicit_voice):
                    voice_b = explicit_voice
                else:
                    # Explicit voice not available, use gender-based fallback (assume female default)
                    voice_b, is_fallback, warning = get_available_voice_for_gender(
                        'female', voice_quality, premium
                    )
                    voice_b_warnings.append(
                        f"⚠ Configured voice '{explicit_voice}' not available. Using fallback: '{voice_b}'"
                    )
                    if warning:
                        voice_b_warnings.append(warning)
            else:
                # No explicit voice, use gender-based default (female)
                voice_b, is_fallback, warning = get_available_voice_for_gender(
                    'female', voice_quality, premium
                )
                if warning:
                    voice_b_warnings.append(warning)
    
    # Print warnings if any
    for warning in voice_a_warnings:
        print(warning)
    for warning in voice_b_warnings:
        print(warning)
    
    print(f"Using voices: A={voice_a}, B={voice_b}")
    
    cache_dir = get_cache_dir()
    
    audio_files = []
    utterances = []  # [{speaker, text, audio_path}]
    
    for chunk in dialogue_chunks:
        speaker = chunk['speaker']
        text = chunk['text']
        voice = voice_a if speaker == 'A' else voice_b
        
        # Split long texts into smaller chunks
        text_chunks = split_into_chunks(text, max_chars=500)
        
        for text_chunk in text_chunks:
            # generate_tts_chunk will now raise an exception on failure
            audio_file = generate_tts_chunk(text_chunk, voice, premium, cache_dir)
            audio_files.append(audio_file)
            utterances.append({
                'speaker': speaker,
                'text': text_chunk,
                'audio_path': str(audio_file)
            })
    
    if not audio_files:
        print("No audio files generated")
        return False
    
    # Concatenate all audio files
    temp_wav = audio_path.with_suffix('.wav')
    gap_ms = 500
    if not concatenate_audio_files(audio_files, temp_wav, gap_ms=gap_ms):
        return False

    # Best-effort: generate captions based on *actual* cached chunk durations.
    # This gives tight sync between caption changes and the spoken audio.
    try:
        if utterances:
            captions = build_captions_from_utterances(
                utterances=utterances,
                gap_ms=gap_ms,
                max_words_per_line=CAPTIONS_WORDS_PER_LINE,
                target_lines=CAPTIONS_TARGET_LINES,
                max_lines=CAPTIONS_MAX_LINES,
            )
            if captions:
                srt_path = audio_path.with_suffix('.captions.srt')
                json_path = audio_path.with_suffix('.captions.json')
                write_captions_srt(captions, srt_path)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump({'captions': captions, 'utterances': utterances}, f, indent=2, ensure_ascii=False)
                print(f"  ✓ Captions generated: {srt_path.name}")
    except Exception as e:
        print(f"  ⚠ Caption generation failed (non-fatal): {e}")

    # Convert to AAC
    success = convert_to_aac(temp_wav, audio_path)

    # Clean up temp file
    if temp_wav.exists():
        temp_wav.unlink()

    return success


def probe_duration_seconds(path: Path) -> float:
    """Return media duration in seconds using ffprobe (best-effort)."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=nokey=1:noprint_wrappers=1',
            str(path)
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        return float(out) if out else 0.0
    except Exception:
        return 0.0


def _format_srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000.0))
    hh = millis // 3600000
    millis -= hh * 3600000
    mm = millis // 60000
    millis -= mm * 60000
    ss = millis // 1000
    ms = millis - ss * 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _split_words_into_blocks(
    words: List[str],
    words_per_line: int | None = None,
    target_lines: int = 2,
    max_lines: int = 2,
    # Backward-compatibility: some callers used `max_words_per_line=`.
    max_words_per_line: int | None = None,
) -> List[List[str]]:
    """Split words into caption blocks.

    Backward compatible with earlier call sites that passed `max_words_per_line=`.
    """
    if words_per_line is None:
        words_per_line = int(max_words_per_line) if max_words_per_line is not None else int(CAPTIONS_WORDS_PER_LINE)
    if not words:
        return []
    max_words_per_block = max(1, words_per_line * max_lines)
    blocks = []
    i = 0
    while i < len(words):
        block = words[i:i + max_words_per_block]
        blocks.append(block)
        i += max_words_per_block
    return blocks


def _render_block_text(block_words: List[str], words_per_line: int, target_lines: int, max_lines: int) -> str:
    """Render a caption block into 1..max_lines with ~target_lines preferred."""
    if not block_words:
        return ""

    # Prefer 2 lines of 4-5 words by default; fall back to 1 or extend to 3 when needed.
    lines = []
    idx = 0
    while idx < len(block_words) and len(lines) < max_lines:
        lines.append(" ".join(block_words[idx:idx + words_per_line]))
        idx += words_per_line

    # If we ended up with 3 short lines, try to rebalance into 2 if it still fits.
    if len(lines) > target_lines and len(block_words) <= words_per_line * target_lines:
        lines = []
        idx = 0
        while idx < len(block_words):
            lines.append(" ".join(block_words[idx:idx + words_per_line]))
            idx += words_per_line

    return "\n".join(lines)


def build_captions_from_utterances(
    utterances: List[Dict[str, Any]],
    gap_ms: int = 500,
    max_words_per_line: int = CAPTIONS_WORDS_PER_LINE,
    target_lines: int = CAPTIONS_TARGET_LINES,
    max_lines: int = CAPTIONS_MAX_LINES,
) -> List[Dict[str, Any]]:
    """Build tight-sync captions based on per-utterance audio durations.

    Output caption segments include a `speaker` field (A/B) when available so
    downstream burn-in can apply gender-based glow without showing names.
    """
    gap_s = max(0.0, gap_ms / 1000.0)
    t = 0.0
    captions: List[Dict[str, Any]] = []
    idx = 1

    for utt in utterances:
        text = (utt.get('text') or '').strip()
        speaker = (utt.get('speaker') or '').strip()  # expected 'A' or 'B'
        audio_path = Path(utt.get('audio_path', ''))

        # Advance even if empty (keeps timing stable)
        dur = probe_duration_seconds(audio_path) if audio_path.exists() else 0.0
        if dur <= 0:
            # Conservative fallback: ~2.4 w/s
            words_tmp = text.split()
            dur = max(1.2, len(words_tmp) / 2.4) if text else 0.0

        if not text:
            t += dur + gap_s
            continue

        words = text.split()
        total_words = max(1, len(words))

        blocks = _split_words_into_blocks(words, max_words_per_line, target_lines, max_lines)
        for block_words in blocks:
            block_text = _render_block_text(block_words, max_words_per_line, target_lines, max_lines)
            if not block_text:
                continue

            block_word_count = max(1, len(block_words))
            block_dur = dur * (block_word_count / total_words)

            start = t
            end = t + block_dur
            if end - start < 0.20:
                end = start + 0.20

            cap = {
                'index': idx,
                'start': start,
                'end': end,
                'text': block_text,
            }
            if speaker:
                cap['speaker'] = speaker
            captions.append(cap)

            idx += 1
            t = end

        # Advance past remaining part of utterance and the gap.
        if captions:
            t = max(t, captions[-1]['start'] + dur)
        else:
            t += dur
        t += gap_s

    return captions


def write_captions_srt(captions: List[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, c in enumerate(captions, start=1):
            start = _format_srt_time(float(c.get('start', 0.0)))
            end = _format_srt_time(float(c.get('end', 0.0)))
            text = (c.get('text') or '').strip()
            if not text:
                continue
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(text + "\n\n")


def build_captions_from_dialogue_estimate(
    dialogue_chunks: List[Dict[str, str]],
    total_duration_s: float,
    gap_ms: int = 500,
    max_words_per_line: int = CAPTIONS_WORDS_PER_LINE,
    target_lines: int = CAPTIONS_TARGET_LINES,
    max_lines: int = CAPTIONS_MAX_LINES,
) -> List[Dict[str, Any]]:
    """Build approximate captions for chunked TTS (single long run).

    We proportionally allocate the *known* final audio duration across dialogue chunks
    based on word counts, then format each chunk into 1..max_lines blocks.

    Captions include `speaker` (A/B) when available.
    """
    gap_s = max(0.0, gap_ms / 1000.0)

    # Filter to non-empty dialogue chunks
    filtered = []
    for ch in dialogue_chunks or []:
        sp = (ch.get('speaker') or '').strip()
        tx = (ch.get('text') or '').strip()
        if tx:
            filtered.append({'speaker': sp, 'text': tx})

    if not filtered or total_duration_s <= 0.0:
        return []

    # Speech time excludes inter-utterance gaps
    speech_time = max(0.5, total_duration_s - gap_s * max(0, len(filtered) - 1))

    # Weight by word count (fallback to char count)
    weights = []
    for ch in filtered:
        w = len(ch['text'].split())
        if w <= 0:
            w = max(1, len(ch['text']) // 4)
        weights.append(w)
    total_w = max(1, sum(weights))

    captions: List[Dict[str, Any]] = []
    t = 0.0
    idx = 1
    for ch, w in zip(filtered, weights):
        dur = speech_time * (w / total_w)

        # Ensure minimal duration so captions remain readable
        dur = max(1.0, dur)

        blocks = _split_words_into_blocks(
            ch['text'].split(),
            max_words_per_line=max_words_per_line,
            target_lines=target_lines,
            max_lines=max_lines,
        )
        if not blocks:
            blocks = [ch['text'].split()]

        # Allocate per block proportionally
        total_words = max(1, len(ch['text'].split()))
        for block_words in blocks:
            block_text = _render_block_text(block_words, max_words_per_line, target_lines, max_lines)
            if not block_text:
                continue
            block_w = max(1, len(block_words))
            block_dur = dur * (block_w / total_words)
            start = t
            end = t + block_dur
            if end - start < 0.20:
                end = start + 0.20

            cap = {'index': idx, 'start': start, 'end': end, 'text': block_text}
            if ch.get('speaker'):
                cap['speaker'] = ch['speaker']
            captions.append(cap)
            idx += 1
            t = end

        t += gap_s

    # Clamp last end to total duration (avoid overshoot from rounding)
    if captions:
        captions[-1]['end'] = min(float(captions[-1]['end']), float(total_duration_s))
    return captions

def generate_for_topic(topic_id: str, date_str: str = None) -> bool:
    """
    Generate TTS audio for a topic using multi-format generation.
    
    Note: Single-format generation has been removed. Topics must have the
    'content_types' field configured in their topic configuration.
    
    Args:
        topic_id: Topic identifier (e.g., 'topic-01')
        date_str: Date string in YYYYMMDD format (default: today)
        
    Returns:
        True if all audio files generated successfully, False otherwise
    """
    try:
        if date_str is None:
            date_str = datetime.now().strftime('%Y%m%d')
        
        config = load_topic_config(topic_id)
        output_dir = get_output_dir(topic_id)
        
        # Always use multi-format generation
        return generate_multi_format_for_topic(topic_id, date_str, config, output_dir)
        
    except Exception as e:
        print(f"Error generating TTS for {topic_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_multi_format_for_topic(topic_id: str, date_str: str,
                                     config: Dict[str, Any], output_dir: Path) -> bool:
    """
    Generate TTS for multi-format topic (15 audio files).
    Finds all script JSON files matching pattern: {topic}-{date}-*.script.json
    """
    print(f"Generating multi-format TTS for {topic_id}...")
    
    # Find all script JSON files
    pattern = str(output_dir / f"{topic_id}-{date_str}-*.script.json")
    script_files = glob.glob(pattern)
    
    if not script_files:
        print(f"No script JSON files found matching: {pattern}")
        return False
    
    print(f"Found {len(script_files)} script files to process")
    
    # Respect the topic's enabled content types and item counts.
    # This prevents generating audio for stale scripts from previous runs.
    allowed_prefixes = set()
    max_per_prefix: Dict[str, int] = {}
    try:
        from global_config import CONTENT_TYPES as _CT
        ct_cfg = config.get("content_types", {}) or {}
        for ct_key, ct_spec in ct_cfg.items():
            if not isinstance(ct_spec, dict) or not ct_spec.get("enabled", False):
                continue
            pfx = (_CT.get(ct_key, {}) or {}).get("code_prefix")
            if not pfx:
                continue
            p = str(pfx).upper()
            allowed_prefixes.add(p)
            try:
                items = int(ct_spec.get("items", 0))
            except Exception:
                items = 0
            if items > 0:
                max_per_prefix[p] = items
    except Exception:
        allowed_prefixes = set()
        max_per_prefix = {}

    seen_per_prefix: Dict[str, int] = {}
    success_count = 0
    fail_count = 0
    
    for script_json_path in sorted(script_files):
        script_path = Path(script_json_path)
        
        # Extract content code from filename (e.g., "L1", "M2", "S3", "R4")
        # Filename format: {topic}-{date}-{code}.script.json
        stem = script_path.stem  # e.g., "topic-01-20251216-L1.script"
        # Remove .script suffix if present to get clean stem
        script_suffix = '.script'
        if stem.endswith(script_suffix):
            stem = stem[:-len(script_suffix)]  # Remove '.script'
        parts = stem.split('-')
        if len(parts) >= 4:
            code = parts[3]  # Extract code (L1, M2, etc.)
        else:
            print(f"Warning: Unable to extract code from filename: {script_path.name}")
            continue
        
        code_prefix = code[0].upper() if code else ""
        if allowed_prefixes and code_prefix not in allowed_prefixes:
            print(f"Skipping {code}: content type not enabled")
            continue
        if code_prefix in max_per_prefix:
            n = seen_per_prefix.get(code_prefix, 0)
            if n >= max_per_prefix[code_prefix]:
                print(f"Skipping {code}: exceeds configured items for {code_prefix}")
                continue
            seen_per_prefix[code_prefix] = n + 1

        # Generate corresponding audio filename (M4A with AAC codec)
        base_name = f"{topic_id}-{date_str}-{code}"
        audio_path = output_dir / f"{base_name}.m4a"
        
        print(f"\nProcessing {code}: {script_path.name}")
        
        try:
            # Load script JSON
            with open(script_path, 'r', encoding='utf-8') as f:
                script = json.load(f)
            
            # Collect all dialogue chunks
            dialogue_chunks = []
            for segment in script['segments']:
                dialogue_chunks.extend(segment['dialogue'])
            
            print(f"  - {len(dialogue_chunks)} dialogue chunks")
            
            # Generate TTS
            if tts_chunks_to_audio(dialogue_chunks, audio_path, config):
                print(f"  ✓ Generated: {audio_path.name}")
                success_count += 1
            else:
                print(f"  ✗ Failed to generate TTS")
                fail_count += 1
                
        except Exception as e:
            print(f"  ✗ Error processing {code}: {e}")
            fail_count += 1
    
    print(f"\n{'='*60}")
    print(f"TTS Generation Summary:")
    print(f"  Success: {success_count}/{len(script_files)}")
    print(f"  Failed: {fail_count}/{len(script_files)}")
    print(f"{'='*60}")
    
    return fail_count == 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Generate TTS audio')
    parser.add_argument('--topic', required=True, help='Topic ID')
    parser.add_argument('--date', help='Date string (YYYYMMDD)')
    args = parser.parse_args()
    
    success = generate_for_topic(args.topic, args.date)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
