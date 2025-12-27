#!/usr/bin/env python3
"""
Render video for podcast with automatic image slideshow generation.

This module creates videos by combining:
- All available images from a configured directory (auto-discovered)
- Audio narration track (optional, can generate video-only)

Images are displayed as a slideshow with configurable duration per image.
Video duration matches the audio duration, looping images if needed.

Transition type: Hard cuts between images (simplest option, no fades).
Image scaling: Center crop to fill frame (no black bars).
"""
import argparse
import json
import os
import sys
import subprocess
import tempfile
import urllib.request
import glob
import shutil
import math
import errno
import hashlib
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from image_preprocess_cache import restore_images_cache_from_release, publish_images_cache_to_release, get_tenant_id
from captions_subflow import maybe_burn_captions
from datetime import datetime

import yaml
from config import load_topic_config, get_output_dir, get_data_dir
from global_config import (
    IMAGE_TRANSITION_MIN_SEC, IMAGE_TRANSITION_MAX_SEC,
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    IMAGES_SUBDIR, ENABLE_IMAGE_CLEANUP,
    CONTENT_TYPES, get_video_resolution_for_code,
    ALLOWED_IMAGE_EXTENSIONS, VIDEO_RENDERER,
    ENABLE_VIDEO_GENERATION, ENABLE_VIDEO_AUDIO_MUX,
    ENABLE_SOCIAL_EFFECTS, SOCIAL_EFFECTS_STYLE,
    ENABLE_FFMPEG_EFFECTS, FFMPEG_EFFECTS_CONFIG,
    VIDEO_CODEC, VIDEO_CODEC_PROFILE, VIDEO_BITRATE_SETTINGS,
    TTS_AUDIO_BITRATE, VIDEO_KEYFRAME_INTERVAL_SEC,
    ENABLE_BURN_IN_CAPTIONS, CAPTIONS_BOTTOM_MARGIN_FRACTION
)

# Sidecar metadata written by image_collector.py
IMAGES_METADATA_FILENAME = "images_metadata.json"

from multi_format_generator import get_enabled_content_types

# Video rendering configuration (internal defaults)
# These can be overridden from global_config if needed
DEFAULT_IMAGE_DURATION_SECONDS = IMAGE_TRANSITION_MIN_SEC  # Default duration per image
BACKGROUND_COLOR = 'black'  # Background color (used for legacy functions)
ENOTSUP_FALLBACK = 95  # Fallback errno value when errno.ENOTSUP is unavailable

# File size thresholds for output verification
MIN_OUTPUT_SIZE_BYTES = 100_000  # 100KB - minimum size for valid Blender output
MIN_FALLBACK_GUARD_SIZE_BYTES = 1_000_000  # 1MB - minimum size to skip FFmpeg fallback

# Log output configuration
LOG_TAIL_LENGTH = 4000  # Number of characters to show from end of Blender logs when debugging
LOG_TAIL_LINES = 100  # Maximum number of lines to show from end of logs

# Image processing configuration
BLUR_SIGMA = 20  # Gaussian blur sigma for background layer
BACKGROUND_BRIGHTNESS = -0.3  # Brightness adjustment for blurred background (-1.0 to 1.0)
VIGNETTE_ANGLE = math.pi / 4  # Vignette angle in radians (PI/4 = 45 degrees)
GRAIN_INTENSITY = 5  # Noise/grain intensity for texture (0-100)


def load_video_template_config(repo_root: Path) -> dict:
    """
    Load video template configuration from config/video_templates.yml.
    
    Args:
        repo_root: Repository root directory
        
    Returns:
        Configuration dictionary with the following structure:
        {
            'version': int,
            'selection': {
                'default_strategy': str,
                'fallback_to_none': bool,
                'fallback_template_id': str,
                'by_content_type': {
                    '<content_type>': {
                        'strategy': str,
                        'candidates': list[str]
                    }
                }
            }
        }
        Returns empty dict if file not found.
    """
    cfg_path = repo_root / "config" / "video_templates.yml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_ffmpeg_effects_config() -> dict:
    """
    Load FFmpeg effects configuration from config file.
    
    Returns:
        Configuration dictionary with the following structure:
        {
            'transitions': {
                '<content_type>': {
                    'transitions': list[str],
                    'duration': float
                }
            },
            'kenburns': {
                'enabled': bool,
                'max_zoom': float,
                'zoom_per_frame': float,
                'pan_enabled': bool,
                'pan_speed': float
            },
            'still_duration': {
                '<content_type>': {
                    'min': float,
                    'max': float
                }
            },
            'finishing': {
                'vignette': {'enabled': bool, 'angle': float},
                'grain': {'enabled': bool, 'intensity': int}
            }
        }
        Returns empty dict if file not found or error occurs.
    """
    try:
        # Resolve config path relative to repo root
        repo_root = Path(__file__).parent.parent
        config_path = repo_root / FFMPEG_EFFECTS_CONFIG
        
        if not config_path.exists():
            print(f"  ⚠ Warning: FFmpeg effects config not found: {config_path}")
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        
        return config
    except Exception as e:
        print(f"  ⚠ Warning: Failed to load FFmpeg effects config: {e}")
        return {}


def get_available_xfade_transitions() -> list:
    """
    Get list of available xfade transitions from FFmpeg build.
    
    Parses output of: ffmpeg -h filter=xfade
    
    Returns:
        List of available transition names (e.g., ['fade', 'wipeleft', ...])
        Returns common default set if parsing fails.
    """
    import re
    
    try:
        result = subprocess.run(
            ['ffmpeg', '-h', 'filter=xfade'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            # xfade filter not available, return empty list
            return []
        
        # Parse transitions from help output using regex for more robust parsing
        # Format: "transition         <int>   E..V....... transition (from 0 to N) (default fade)"
        # Followed by list like: "fade            0       E..V......."
        transitions = []
        in_transition_list = False
        
        # Pattern to match transition enum values (indented lines with transition names)
        transition_pattern = re.compile(r'^\s+([a-z]+)\s+\d+\s+E\.\.V')
        
        for line in result.stdout.splitlines():
            # Look for the transition parameter definition line
            if re.search(r'transition\s+<int>\s+E\.\.V', line):
                in_transition_list = True
                continue
            
            # Parse transition names while in the list
            if in_transition_list:
                # Stop at empty line or next parameter (non-indented line)
                if not line.strip() or (line and not line[0].isspace()):
                    break
                
                # Extract transition name using regex
                match = transition_pattern.match(line)
                if match:
                    transitions.append(match.group(1))
        
        return transitions if transitions else [
            'fade', 'wipeleft', 'wiperight', 'wipeup', 'wipedown',
            'slideleft', 'slideright', 'slideup', 'slidedown',
            'smoothleft', 'smoothright', 'smoothup', 'smoothdown',
            'circleopen', 'circleclose', 'dissolve', 'pixelize', 'radial'
        ]
    except Exception as e:
        print(f"  ⚠ Warning: Could not detect xfade transitions: {e}")
        # Return common default transitions
        return [
            'fade', 'wipeleft', 'wiperight', 'wipeup', 'wipedown',
            'slideleft', 'slideright', 'slideup', 'slidedown',
            'smoothleft', 'smoothright', 'smoothup', 'smoothdown',
            'circleopen', 'circleclose', 'dissolve', 'pixelize', 'radial'
        ]


def infer_content_type_from_code(content_code: str) -> str:
    """
    Infer content type from content code.
    
    Args:
        content_code: Content code (e.g., 'L1', 'M2', 'S3', 'R8')
    
    Returns:
        Content type string ('long', 'medium', 'short', 'reels')
        Defaults to 'long' if code is unknown.
    """
    if not content_code:
        return 'long'
    
    code_prefix = content_code[0].upper()
    code_map = {
        'L': 'long',
        'M': 'medium',
        'S': 'short',
        'R': 'reels'
    }
    
    return code_map.get(code_prefix, 'long')


def estimate_ffmpeg_effects_slot_count(
    duration: float,
    content_type: str,
    seed: str,
    effects_config: dict | None = None,
) -> int:
    """Estimate the exact number of image slots used by `render_slideshow_ffmpeg_effects`.

    We replicate the schedule-building loop (including RNG consumption) so we can allocate
    enough *unique* images per slot across sequential renders.
    """
    try:
        if duration <= 0:
            return 1

        if effects_config is None:
            effects_config = load_ffmpeg_effects_config() or {}

        available_transitions = get_available_xfade_transitions()
        transitions_config = effects_config.get('transitions', {}).get(content_type, {})
        still_config = effects_config.get('still_duration', {}).get(content_type, {})

        configured_transitions = transitions_config.get(
            'types',
            ['fade', 'dissolve', 'slideleft', 'slideright', 'circleopen', 'circleclose', 'radial', 'pixelize']
        )
        transition_duration = float(transitions_config.get('duration', 1.0))

        # Fast mode defaults to enabled for reels/shorts unless explicitly overridden.
        fast_default = 'true' if content_type in ('reels', 'short') else 'false'
        fast_mode = os.environ.get('FFMPEG_FAST_MODE', fast_default).strip().lower() in ('1', 'true', 'yes', 'on')
        if fast_mode:
            configured_transitions = [t for t in configured_transitions if t in ('fade', 'dissolve')]
            if not configured_transitions:
                configured_transitions = ['fade']
            transition_duration = max(0.2, min(transition_duration, 0.35))

        supported_transitions = [t for t in configured_transitions if t in available_transitions]
        if not supported_transitions:
            supported_transitions = ['fade'] if 'fade' in available_transitions else available_transitions[:1]

        DEFAULT_STILL_MIN = 3.0
        DEFAULT_STILL_MAX = 6.0
        still_min = float(still_config.get('min', DEFAULT_STILL_MIN))
        still_max = float(still_config.get('max', DEFAULT_STILL_MAX))
        if still_max < still_min:
            still_min, still_max = still_max, still_min
        still_min = max(0.1, still_min)
        still_max = max(still_min, still_max)
        transition_duration = max(0.0, transition_duration)

        random.seed(seed)
        total_time = 0.0
        slots = 0
        while total_time < duration:
            still_duration = random.uniform(still_min, still_max)
            if total_time + still_duration + transition_duration > duration:
                still_duration = max(0.1, duration - total_time - transition_duration)

            # Consume transition RNG to stay aligned with the renderer.
            _ = random.choice(supported_transitions)

            total_time += still_duration + transition_duration
            slots += 1
            if total_time >= duration:
                break

        return max(1, int(slots))
    except Exception:
        return 1


def render_slideshow_ffmpeg_effects(
    images: List[Path],
    output_path: Path,
    duration: float,
    width: int,
    height: int,
    fps: int,
    content_type: str = 'long',
    seed: str = None
) -> bool:
    """
    Render slideshow with FFmpeg effects (Ken Burns + xfade transitions).
    
    This function builds a complex FFmpeg filtergraph with:
    - Ken Burns motion effects (zoom + pan)
    - xfade transitions between images
    - Optional vignette and grain finishing pass
    
    Args:
        images: List of image paths for slideshow
        output_path: Path to save output video
        duration: Total video duration in seconds
        width: Target video width
        height: Target video height
        fps: Frames per second
        content_type: Content type ('long', 'medium', 'short', 'reels')
        seed: Random seed for deterministic output (uses output path stem if None)
    
    Returns:
        True if successful, False otherwise (falls back to legacy concat mode)
    """
    try:
        # Load effects configuration
        effects_config = load_ffmpeg_effects_config()
        if not effects_config:
            print("  ⚠ FFmpeg effects config not available, falling back to legacy mode")
            return False
        
        # Get available transitions from FFmpeg
        available_transitions = get_available_xfade_transitions()
        if not available_transitions:
            print("  ⚠ xfade filter not available in FFmpeg, falling back to legacy mode")
            return False
        
        # Get content type configuration
        transitions_config = effects_config.get('transitions', {}).get(content_type, {})
        kenburns_config = effects_config.get('kenburns', {})
        still_config = effects_config.get('still_duration', {}).get(content_type, {})
        finishing_config = effects_config.get('finishing', {})

        # Optional performance mode (trade some visual complexity for speed)
        fast_default = 'true' if content_type in ('reels', 'short') else 'false'
        fast_mode = os.environ.get('FFMPEG_FAST_MODE', fast_default).strip().lower() in ('1', 'true', 'yes', 'on')
        
        # Get transition settings
        configured_transitions = transitions_config.get('transitions', ['fade'])
        transition_duration = transitions_config.get('duration', 1.0)

        if fast_mode:
            # Prefer lightweight transitions in fast mode.
            configured_transitions = [t for t in configured_transitions if t in ('fade', 'dissolve')]
            if not configured_transitions:
                configured_transitions = ['fade']
            transition_duration = max(0.2, min(transition_duration, 0.35))
        
        # Filter to only supported transitions
        supported_transitions = [t for t in configured_transitions if t in available_transitions]
        if not supported_transitions:
            print(f"  ⚠ No configured transitions available, using 'fade'")
            supported_transitions = ['fade'] if 'fade' in available_transitions else available_transitions[:1]
        
        # Deterministic seed for stable output
        # This sets the global random state, making all subsequent random.choice() 
        # and random.uniform() calls deterministic for reproducible output
        if seed is None:
            seed = output_path.stem
        random.seed(seed)
        
        # Get still duration range (with dedicated defaults for effects mode)
        # These defaults are independent of IMAGE_TRANSITION_MIN_SEC/MAX_SEC (legacy concat mode)
        DEFAULT_STILL_MIN = 3.0
        DEFAULT_STILL_MAX = 6.0
        still_min = still_config.get('min', DEFAULT_STILL_MIN)
        still_max = still_config.get('max', DEFAULT_STILL_MAX)
        
        # Build slideshow schedule
        schedule = []
        total_time = 0.0
        image_index = 0
        
        while total_time < duration:
            # Random still duration
            still_duration = random.uniform(still_min, still_max)
            
            # Don't exceed total duration
            if total_time + still_duration + transition_duration > duration:
                still_duration = max(0.1, duration - total_time - transition_duration)
            
            # Select image (cycle if needed)
            image = images[image_index % len(images)]
            
            # Select transition
            transition = random.choice(supported_transitions)
            
            schedule.append({
                'image': image,
                'still_duration': still_duration,
                'transition': transition,
                'transition_duration': transition_duration
            })
            
            total_time += still_duration + transition_duration
            image_index += 1
            
            # Break if we've covered the duration
            if total_time >= duration:
                break
        
        if not schedule:
            print("  ✗ Failed to build slideshow schedule")
            return False

        # Write image-title timeline sidecar for post-processing overlays.
        # This intentionally happens outside the slideshow filtergraph so titles do not move
        # with Ken Burns / pan-zoom.
        try:
            title_map = _load_image_title_map([Path(s['image']) for s in schedule])
            segs: List[Dict[str, Any]] = []
            t0 = 0.0
            for idx, it in enumerate(schedule):
                img_p = Path(it['image'])
                title = title_map.get(img_p.name, "").strip()
                still_dur = float(it.get('still_duration', 0.0) or 0.0)
                if title and still_dur > 0:
                    segs.append(
                        {
                            "start": round(t0, 3),
                            "end": round(min(duration, t0 + still_dur), 3),
                            "text": title,
                            "filename": img_p.name,
                            "index": idx,
                        }
                    )
                t0 += still_dur
            _write_image_titles_sidecar(output_path, segs)
        except Exception:
            pass
        
        print(f"  Building FFmpeg effects slideshow:")
        print(f"    Images: {len(schedule)} slots from {len(images)} source images")
        print(f"    Duration: {duration:.2f}s")
        print(f"    Still duration: {still_min:.1f}-{still_max:.1f}s")
        print(f"    Transition duration: {transition_duration:.1f}s")
        print(f"    Transitions: {', '.join(set(s['transition'] for s in schedule))}")
        
        # Ken Burns configuration
        kenburns_enabled = kenburns_config.get('enabled', True)
        max_zoom = kenburns_config.get('max_zoom', 1.15)
        zoom_per_frame = kenburns_config.get('zoom_per_frame', 0.002)
        pan_enabled = kenburns_config.get('pan_enabled', True)
        pan_speed = kenburns_config.get('pan_speed', 0.5)
        
        # Finishing pass configuration
        vignette_enabled = finishing_config.get('vignette', {}).get('enabled', False)
        vignette_angle = finishing_config.get('vignette', {}).get('angle', math.pi / 4)
        grain_enabled = finishing_config.get('grain', {}).get('enabled', False)
        grain_intensity = finishing_config.get('grain', {}).get('intensity', 5)
        
        # Build FFmpeg filtergraph
        filter_complex = []
        input_labels = []
        
        # Step 1: Normalize each image (scale to cover + crop + fps + format)
        # and optionally apply Ken Burns motion
        for i, item in enumerate(schedule):
            img_path = item['image']
            still_dur = item['still_duration']
            trans_dur = item['transition_duration']
            
            # Total duration for this clip (still + transition overlap)
            # Note: transitions overlap, so we need still_dur + trans_dur for each clip
            clip_duration = still_dur + trans_dur
            
            # Input label for this image
            input_label = f'[{i}:v]'
            input_labels.append(input_label)
            
            # Normalization: scale to cover, crop to exact size, set fps, format
            # Use 'increase' to ensure image covers the entire frame (may crop edges)
            normalize_filter = (
                f'{input_label}'
                f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                f'crop={width}:{height},'
                f'fps={fps},'
                f'format=yuv420p'
            )
            
            # Ken Burns motion (zoompan)
            if kenburns_enabled:
                # Calculate number of frames for this clip
                num_frames = int(clip_duration * fps)
                
                # Randomize zoom direction (in or out)
                zoom_in = random.choice([True, False])
                
                # Calculate zoom parameters
                if zoom_in:
                    # Zoom in: start at 1.0, end at max_zoom
                    zoom_expr = f'min(zoom+{zoom_per_frame},{max_zoom})'
                else:
                    # Zoom out: start at max_zoom, end at 1.0
                    zoom_expr = f'if(eq(on,1),{max_zoom},max(zoom-{zoom_per_frame},1.0))'
                
                # Pan parameters (if enabled)
                if pan_enabled:
                    # Random pan direction
                    pan_x_dir = random.choice([-1, 0, 1])  # left, center, right
                    pan_y_dir = random.choice([-1, 0, 1])  # up, center, down
                    
                    # Pan expressions (move within the zoomed frame)
                    if pan_x_dir == -1:
                        x_expr = f'iw/2-(iw/zoom/2)*{pan_speed}'
                    elif pan_x_dir == 1:
                        x_expr = f'iw/2+(iw/zoom/2)*{pan_speed}'
                    else:
                        x_expr = 'iw/2-(iw/zoom/2)'
                    
                    if pan_y_dir == -1:
                        y_expr = f'ih/2-(ih/zoom/2)*{pan_speed}'
                    elif pan_y_dir == 1:
                        y_expr = f'ih/2+(ih/zoom/2)*{pan_speed}'
                    else:
                        y_expr = 'ih/2-(ih/zoom/2)'
                else:
                    # Center crop only (no pan)
                    x_expr = 'iw/2-(iw/zoom/2)'
                    y_expr = 'ih/2-(ih/zoom/2)'
                
                # Apply zoompan filter
                # Quote expressions to handle commas in FFmpeg filter syntax
                # The expressions are programmatically generated from numeric values and don't contain quotes
                kb_filter = (
                    f',zoompan='
                    f"z='{zoom_expr}':"
                    f"x='{x_expr}':"
                    f"y='{y_expr}':"
                    f'd={num_frames}:'
                    f's={width}x{height}:'
                    f'fps={fps}'
                )
                
                normalize_filter += kb_filter
            else:
                # No Ken Burns, just set duration using loop filter
                num_frames = int(clip_duration * fps)
                normalize_filter += f',loop=loop={num_frames}:size=1:start=0'
            
            # Output label for normalized clip
            out_label = f'[v{i}]'
            filter_complex.append(f'{normalize_filter}{out_label}')
        
        # Step 2: Chain xfade transitions between clips
        # Cumulative timing: each transition starts at the end of the previous still duration
        if len(schedule) == 1:
            # Single image, no transitions needed
            current_label = '[v0]'
        else:
            current_label = '[v0]'
            offset = 0.0
            
            for i in range(1, len(schedule)):
                prev_item = schedule[i - 1]
                curr_item = schedule[i]
                
                # Transition starts after the still duration of the previous clip
                offset += prev_item['still_duration']
                
                transition_type = curr_item['transition']
                transition_dur = curr_item['transition_duration']
                
                # Next clip label
                next_label = f'[v{i}]'
                
                # Output label for this transition
                if i == len(schedule) - 1:
                    # Last transition outputs to 'out' label
                    out_label = '[out]'
                else:
                    out_label = f'[t{i}]'
                
                # xfade filter
                xfade_filter = (
                    f'{current_label}{next_label}'
                    f'xfade='
                    f'transition={transition_type}:'
                    f'duration={transition_dur}:'
                    f'offset={offset}'
                    f'{out_label}'
                )
                
                filter_complex.append(xfade_filter)
                current_label = out_label
        
        # Step 3: Apply finishing passes (vignette + grain)
        if vignette_enabled or grain_enabled:
            finishing_filters = []
            
            if vignette_enabled:
                finishing_filters.append(f'vignette=angle={vignette_angle}')
            
            if grain_enabled:
                finishing_filters.append(f'noise=alls={grain_intensity}:allf=t+u')
            
            # Apply finishing filters
            finishing_chain = ','.join(finishing_filters)
            
            if len(schedule) == 1:
                # Single image case
                filter_complex.append(f'[v0]{finishing_chain}[final]')
            else:
                # Multiple images with transitions
                filter_complex.append(f'[out]{finishing_chain}[final]')
            
            output_map = '[final]'
        else:
            # No finishing passes
            if len(schedule) == 1:
                output_map = '[v0]'
            else:
                output_map = '[out]'
        
        # Build FFmpeg command
        ffmpeg_cmd = ['ffmpeg', '-y']
        
        # Add input files
        for item in schedule:
            ffmpeg_cmd.extend(['-loop', '1', '-i', str(item['image'])])
        
        # Add filter_complex
        filter_complex_str = ';'.join(filter_complex)
        ffmpeg_cmd.extend(['-filter_complex', filter_complex_str])
        
        # Map output
        ffmpeg_cmd.extend(['-map', output_map])
        
        # Video encoding settings
        # Determine video format
        aspect_ratio = width / height if height > 0 else 1.0
        video_format = 'vertical' if aspect_ratio < 1.0 else 'horizontal'
        bitrate_config = VIDEO_BITRATE_SETTINGS[video_format]
        
        # Encoding tuning: allow preset/CRF overrides for faster social renders.
        preset = os.environ.get('FFMPEG_PRESET', 'veryfast').strip()
        crf = os.environ.get('FFMPEG_CRF', '').strip()
        # In FAST mode, default to CRF if user did not provide explicit rate control.
        if (not crf) and fast_mode:
            crf = '23'

        ffmpeg_cmd.extend([
            '-c:v', VIDEO_CODEC,
            '-profile:v', VIDEO_CODEC_PROFILE,
        ])

        # If CRF is provided, prefer CRF mode (faster, simpler rate control).
        if crf:
            ffmpeg_cmd.extend(['-preset', preset, '-crf', crf])
        else:
            ffmpeg_cmd.extend([
                '-b:v', bitrate_config['bitrate'],
                '-maxrate', bitrate_config['maxrate'],
                '-bufsize', bitrate_config['bufsize'],
                '-preset', preset,
            ])

        ffmpeg_cmd.extend([
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-threads', '0',
            '-movflags', '+faststart',
            '-t', str(duration),  # Exact duration
            str(output_path)
        ])
        
        # Execute FFmpeg command
        print(f"  Executing FFmpeg filtergraph rendering...")
        try:
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=600  # 10 minute timeout
            )
            print(f"  ✓ FFmpeg rendering completed")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ FFmpeg command failed (exit code {e.returncode})")
            if e.stderr:
                stderr_lines = e.stderr.strip().split('\n')
                print(f"  FFmpeg stderr (last 20 lines):")
                for line in stderr_lines[-20:]:
                    print(f"    {line}")
            return False
        except subprocess.TimeoutExpired:
            print(f"  ✗ FFmpeg rendering timed out (10 minutes)")
            return False
        
        # Validate output using ffprobe
        print(f"  Validating output with ffprobe...")
        try:
            # Get video duration and resolution
            probe_result = subprocess.run([
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration',
                '-show_entries', 'format=duration',
                '-of', 'json',
                str(output_path)
            ], capture_output=True, text=True, check=True)
            
            probe_data = json.loads(probe_result.stdout)
            
            # Extract stream info
            streams = probe_data.get('streams', [])
            if not streams:
                print(f"  ✗ No video stream found in output")
                return False
            
            stream = streams[0]
            output_width = stream.get('width')
            output_height = stream.get('height')
            
            # Get duration (try stream first, then format)
            output_duration = stream.get('duration')
            if output_duration is None:
                format_info = probe_data.get('format', {})
                output_duration = format_info.get('duration')
            
            if output_duration is not None:
                output_duration = float(output_duration)
            
            # Validate resolution
            if output_width != width or output_height != height:
                print(f"  ✗ Resolution mismatch: expected {width}x{height}, got {output_width}x{output_height}")
                return False
            
            # Validate duration (allow 5% tolerance)
            if output_duration is not None:
                duration_diff = abs(output_duration - duration)
                duration_tolerance = duration * 0.05  # 5% tolerance
                
                if duration_diff > duration_tolerance:
                    print(f"  ✗ Duration mismatch: expected {duration:.2f}s, got {output_duration:.2f}s")
                    return False
                
                print(f"  ✓ Output validated: {output_width}x{output_height}, {output_duration:.2f}s")
            else:
                print(f"  ⚠ Could not determine output duration, skipping duration check")
                print(f"  ✓ Output resolution validated: {output_width}x{output_height}")
            
            # Get file size
            file_size = output_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"  ✓ Output file size: {file_size_mb:.2f} MB")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"  ✗ ffprobe validation failed: {e}")
            return False
        except Exception as e:
            print(f"  ⚠ Validation error (output may still be valid): {e}")
            # Don't fail if validation has issues, output might still be good
            return True
        
    except Exception as e:
        print(f"  ✗ FFmpeg effects rendering failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_safe_file_size(path: Path) -> Optional[int]:
    """
    Get file size safely, handling race conditions and errors.
    
    Args:
        path: Path to check
    
    Returns:
        File size in bytes, or None if file doesn't exist or error occurs
    """
    try:
        if path.exists():
            return path.stat().st_size
    except (OSError, IOError):
        pass
    return None


def get_log_tail(log_text: str, max_chars: int = LOG_TAIL_LENGTH, max_lines: int = LOG_TAIL_LINES) -> str:
    """
    Get tail of log text, respecting line boundaries.
    
    Args:
        log_text: Full log text
        max_chars: Maximum characters to return (approximate)
        max_lines: Maximum lines to return
    
    Returns:
        Tail of log text, respecting line boundaries
    """
    if not log_text:
        return ""
    
    lines = log_text.splitlines()
    
    # Take last N lines
    tail_lines = lines[-max_lines:]
    tail_text = '\n'.join(tail_lines)
    
    # If still too long, truncate to max_chars but keep whole lines
    if len(tail_text) > max_chars:
        # Take characters from the end
        approx_tail = tail_text[-max_chars:]
        # Find the first newline to avoid truncating mid-line
        first_newline = approx_tail.find('\n')
        if first_newline != -1:
            tail_text = approx_tail[first_newline + 1:]
        else:
            # If no newline found, just use the approximate tail
            tail_text = approx_tail
    
    return tail_text


def get_blender_output_path(video_path: Path) -> Path:
    """
    Get the Blender output path for a given video path.
    
    Ensures .blender.mp4 suffix is applied idempotently.
    
    Args:
        video_path: The intended video output path
    
    Returns:
        Path with .blender.mp4 extension
    """
    if not video_path.stem.endswith('.blender'):
        return video_path.parent / f"{video_path.stem}.blender{video_path.suffix}"
    return video_path


def get_audio_duration(audio_path: Path) -> float:
    """Return audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(audio_path)
        ], capture_output=True, text=True, check=True)
        value = result.stdout.strip()
        if not value:
            raise RuntimeError("ffprobe returned empty duration")
        return float(value)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed (exit {e.returncode}): {e.stderr.strip()}")
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found - install FFmpeg to continue")
    except ValueError as e:
        raise RuntimeError(f"Invalid duration from ffprobe: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to read audio duration with ffprobe: {e}")


def _find_images_metadata(start_dir: Path) -> Optional[Path]:
    """Locate images_metadata.json near the rendered assets (best-effort).

    We check:
      1) start_dir itself
      2) common subdirs (images/, assets/, _assets/) under start_dir
      3) parent directories (bounded)
    This makes title burn-in resilient when images live in nested folders.
    """
    # Direct + common children
    candidates: List[Path] = []
    candidates.append(start_dir / IMAGES_METADATA_FILENAME)
    for child in ("images", "Images", "assets", "Assets", "_assets"):
        candidates.append(start_dir / child / IMAGES_METADATA_FILENAME)

    for p in candidates:
        if p.exists():
            return p

    # Walk parents (bounded)
    d = start_dir
    for _ in range(6):
        p = d / IMAGES_METADATA_FILENAME
        if p.exists():
            return p
        for child in ("images", "Images", "assets", "Assets", "_assets"):
            p2 = d / child / IMAGES_METADATA_FILENAME
            if p2.exists():
                return p2
        if d.parent == d:
            break
        d = d.parent
    return None


def _load_image_title_map(images: List[Path]) -> Dict[str, str]:
    """Map a variety of image filenames to cleaned titles.

    The pipeline may render from:
      - original downloaded images (names match images_metadata.json)
      - processed composites (processed/ composite_*.jpg)
      - symlinked/materialized images (00001.jpg -> processed/original)

    We therefore:
      1) Load the base metadata map: original filename -> title
      2) If a prepared-images manifest is present, extend the map so composite out_file -> title(source_name)
      3) Extend the map so any symlink/materialized filename -> title(resolved filename)
    """
    if not images:
        return {}

    # Locate images_metadata.json (usually under <topic>/images/).
    meta_path = _find_images_metadata(images[0].parent) or _find_images_metadata(images[0].resolve().parent)
    if not meta_path:
        return {}

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("images", []) if isinstance(data, dict) else []
        base: Dict[str, str] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            fn = str(it.get("filename", "")).strip()
            title = str(it.get("title_clean") or it.get("title") or "").strip()
            if fn and title:
                base[fn] = title

        if not base:
            return {}

        out: Dict[str, str] = dict(base)

        # Try to load prepared-images manifest(s) to map processed out_file back to source_name.
        def _load_manifest_map(dir_path: Path) -> Dict[str, str]:
            m: Dict[str, str] = {}
            try:
                for mf in sorted(dir_path.glob("manifest_*x*.json")):
                    try:
                        d = json.loads(mf.read_text(encoding="utf-8"))
                        for e in d.get("entries", []) if isinstance(d, dict) else []:
                            if not isinstance(e, dict):
                                continue
                            out_file = e.get("out_file")
                            src_name = e.get("source_name")
                            if out_file and src_name:
                                m[str(out_file)] = str(src_name)
                    except Exception:
                        continue
            except Exception:
                pass
            return m

        manifest_out_to_src: Dict[str, str] = {}
        dirs = set()
        for img in images:
            try:
                dirs.add(img.resolve().parent)
            except Exception:
                dirs.add(img.parent)
        # Also consider parent dirs (e.g., processed/ -> <res>/).
        for d in list(dirs):
            try:
                dirs.add(d.parent)
            except Exception:
                pass

        for d in dirs:
            mm = _load_manifest_map(Path(d))
            if mm:
                manifest_out_to_src.update(mm)

        # Extend mapping for processed out_files (e.g., composite_00001.jpg).
        for out_file, src_name in manifest_out_to_src.items():
            title = base.get(src_name)
            if title and out_file not in out:
                out[out_file] = title

        # Extend mapping for symlink/materialized filenames (e.g., 00001.jpg).
        for img in images:
            try:
                resolved_name = img.resolve().name
            except Exception:
                resolved_name = img.name
            title = out.get(resolved_name) or out.get(img.name)
            if title:
                out[img.name] = title
                out[resolved_name] = title

        return out
    except Exception:
        return {}



def _write_image_titles_sidecar(video_out: Path, segments: List[Dict[str, Any]]) -> None:
    """Write a sidecar file consumed by post-processing overlays."""
    try:
        sidecar = video_out.with_suffix(".image_titles.json")
        payload = {"version": 1, "segments": segments}
        sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass



def _escape_filter_path(p: str) -> str:
    """Escape a filesystem path for use inside an FFmpeg filter argument."""
    return p.replace('\\', r'\\\\').replace(':', r'\\:').replace("'", r"\\'")

def _parse_srt_simple(srt_text: str):
    """Parse a simple SRT into (start_sec, end_sec, text) entries."""
    entries = []
    blocks = re.split(r"\n\s*\n", srt_text.strip(), flags=re.MULTILINE)
    for b in blocks:
        lines = [ln.strip('\r') for ln in b.splitlines() if ln.strip('\r').strip() != '']
        if len(lines) < 2:
            continue
        time_line = None
        for ln in lines[:3]:
            if '-->' in ln:
                time_line = ln
                break
        if not time_line:
            continue
        m = re.match(r"(?P<s>\d\d:\d\d:\d\d,\d\d\d)\s*-->\s*(?P<e>\d\d:\d\d:\d\d,\d\d\d)", time_line)
        if not m:
            continue

        def _t(ts: str) -> float:
            hh, mm, rest = ts.split(':')
            ss, ms = rest.split(',')
            return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0

        start = _t(m.group('s'))
        end = _t(m.group('e'))
        ti = lines.index(time_line)
        cap_text = '\n'.join(lines[ti + 1:])
        if cap_text:
            entries.append((start, end, cap_text))
    return entries

def _escape_drawtext_text(s: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    s = s.replace('\\', r'\\\\')
    s = s.replace(':', r'\\:')
    s = s.replace("'", r"\\'")
    s = s.replace('\n', r'\\n')
    return s

def _build_drawtext_vf(captions, font_size: int, margin_v: int, margin_lr: int) -> str:
    """Build a drawtext filterchain that overlays captions with tight timing."""
    filters = []
    filters.append('format=yuv420p')
    for (start, end, cap_text) in captions:
        cap_text = cap_text.strip()
        if not cap_text or end <= start:
            continue
        esc = _escape_drawtext_text(cap_text)
        draw = (
            "drawtext="
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='{esc}':"
            f"fontsize={font_size}:"
            "fontcolor=white:"
            "borderw=3:"
            "shadowx=1:shadowy=1:"
            "box=1:boxcolor=black@0.35:boxborderw=18:"
            "x=(w-text_w)/2:"
            f"y=h-{margin_v}-text_h:"
            f"enable='between(t,{start:.3f},{end:.3f})'"
        )
        filters.append(draw)
    return ','.join(filters)


def burn_in_captions_if_present(
    input_video: Path,
    audio_path: Optional[Path],
    width: int,
    height: int,
    fps: int,
) -> bool:
    """Burn-in captions from a sibling .captions.srt file (best-effort).

    Strategy:
      1) Prefer libass subtitles filter (fast, supports multi-line + styling).
      2) If subtitles filter is unavailable (common on minimal ffmpeg builds), fall back to drawtext.
    """
    if not ENABLE_BURN_IN_CAPTIONS:
        return True

    # Captions are generated during TTS as: <audio>.captions.srt
    captions_srt: Optional[Path] = None
    captions_json: Optional[Path] = None

    if audio_path is not None:
        candidate = Path(str(audio_path)).with_suffix('.captions.srt')
        if candidate.exists():
            captions_srt = candidate
            cj = Path(str(audio_path)).with_suffix('.captions.json')
            if cj.exists():
                captions_json = cj

    if captions_srt is None:
        candidate = input_video.with_suffix('.captions.srt')
        if candidate.exists():
            captions_srt = candidate
            cj = input_video.with_suffix('.captions.json')
            if cj.exists():
                captions_json = cj

    if captions_srt is None:
        return True

    print(f"  Captions detected: {captions_srt.name}")

    # Place captions in the bottom 1/5 of the frame (MarginV ~ 20% of height).
    margin_v = max(24, int(height * CAPTIONS_BOTTOM_MARGIN_FRACTION))
    margin_lr = max(24, int(width * 0.05))
    font_size = max(24, int(height * 0.033))  # scaled for 1080x1920 and 1920x1080

    # Force a readable style (white text with boxed background). libass uses ASS style syntax.
    # BorderStyle=3 creates a boxed background, BackColour alpha channel (&H80000000) creates semi-transparency
    force_style = (
        f"FontName=DejaVu Sans,FontSize={font_size},"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,"
        f"BorderStyle=3,Outline=3,Shadow=1,Alignment=2,"
        f"MarginV={margin_v},MarginL={margin_lr},MarginR={margin_lr}"
    )

    tmp_out = input_video.parent / f"{input_video.stem}.captions.mp4"

    def _run_ffmpeg_with_vf(vf: str) -> bool:
        cmd = [
            'ffmpeg', '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-i', str(input_video),
            '-vf', vf,
            # Map video and optionally audio (if present)
            '-map', '0:v:0',
            '-map', '0:a?',
            '-c:v', VIDEO_CODEC,
            '-profile:v', VIDEO_CODEC_PROFILE,
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-movflags', '+faststart',
            '-c:a', 'copy',
        ]

        # Match bitrate profile heuristically based on aspect ratio
        aspect_ratio = width / height if height > 0 else 1.0
        fmt = 'vertical' if aspect_ratio < 1.0 else 'horizontal'
        br = VIDEO_BITRATE_SETTINGS.get(fmt, VIDEO_BITRATE_SETTINGS['vertical'])
        cmd.extend([
            '-b:v', br['bitrate'],
            '-maxrate', br['maxrate'],
            '-bufsize', br['bufsize'],
        ])
        cmd.append(str(tmp_out))

        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True

    # 1) Attempt libass subtitles filter
    try:
        # Escape quotes in style string (don't use _escape_filter_path which is for file paths)
        # Note: The force_style string is programmatically generated and doesn't contain quotes
        # or other special characters, but we escape quotes as a precaution for FFmpeg filter syntax
        safe_style = force_style.replace("'", "\\'")
        vf = f"subtitles=filename='{_escape_filter_path(str(captions_srt))}':force_style='{safe_style}'"
        _run_ffmpeg_with_vf(vf)
        os.replace(str(tmp_out), str(input_video))
        print(f"  ✓ Burned captions (subtitles filter)")
        return True
    except subprocess.CalledProcessError as e:
        err = (e.stderr or '').strip()
        # If subtitles filter is missing or failed to init, try drawtext fallback.
        if ('No such filter' in err and 'subtitles' in err) or ('Error initializing filter' in err and 'subtitles' in err) or ('subtitles' in err and 'not found' in err):
            print(f"  ⚠ subtitles filter unavailable; falling back to drawtext captions")
        else:
            print(f"  ⚠ Caption burn-in failed (subtitles filter). Falling back if possible.")
            if err:
                for line in err.splitlines()[-10:]:
                    print(f"    {line}")
        # fall through to drawtext
    except Exception as e:
        print(f"  ⚠ Caption burn-in failed (subtitles filter): {e} — falling back to drawtext")

    # 2) Drawtext fallback (no libass)
    try:
        captions = None
        if captions_json and captions_json.exists():
            import json as _json
            payload = _json.loads(captions_json.read_text(encoding='utf-8'))
            # payload['captions'] is a list of {start,end,text} dicts
            captions = [(c['start'], c['end'], c['text']) for c in payload.get('captions', []) if 'start' in c and 'end' in c and 'text' in c]
        if not captions:
            captions = _parse_srt_simple(captions_srt.read_text(encoding='utf-8'))

        if not captions:
            print("  ⚠ No captions parsed; skipping burn-in")
            return True

        vf2 = _build_drawtext_vf(captions, font_size=font_size, margin_v=margin_v, margin_lr=margin_lr)
        _run_ffmpeg_with_vf(vf2)
        os.replace(str(tmp_out), str(input_video))
        print(f"  ✓ Burned captions (drawtext fallback)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ Caption burn-in failed (drawtext fallback) (non-fatal): ffmpeg exit {e.returncode}")
        if e.stderr:
            for line in e.stderr.strip().splitlines()[-10:]:
                print(f"    {line}")
        return False
    except Exception as e:
        print(f"  ⚠ Caption burn-in failed (drawtext fallback) (non-fatal): {e}")
        return False
    finally:
        if tmp_out.exists():
            try:
                tmp_out.unlink()
            except Exception:
                pass


def check_renderer_available(renderer_type: str = None) -> tuple[bool, str]:
    """
    Check if the specified video renderer is available.
    
    Args:
        renderer_type: 'blender' or 'ffmpeg' (default: use VIDEO_RENDERER from config)
        
    Returns:
        Tuple of (available: bool, path: str or error_msg: str)
    """
    if renderer_type is None:
        renderer_type = VIDEO_RENDERER
    
    if renderer_type == 'blender':
        blender_paths = [
            '../blender-4.5.0-linux-x64/blender',  # Relative from scripts/ directory
            './blender-4.5.0-linux-x64/blender',   # Relative from repo root
            'blender',
            '/usr/bin/blender',
            '/usr/local/bin/blender',
        ]
        for path in blender_paths:
            try:
                result = subprocess.run([path, '--version'],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return True, path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return False, "Blender not found in any standard location"
    
    elif renderer_type == 'ffmpeg':
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return True, 'ffmpeg'
            return False, f"FFmpeg returned non-zero exit code: {result.returncode}"
        except FileNotFoundError:
            return False, "FFmpeg not found - install with: sudo apt-get install ffmpeg"
        except subprocess.TimeoutExpired:
            return False, "FFmpeg check timed out"
        except Exception as e:
            return False, f"FFmpeg check failed: {e}"
    
    return False, f"Unknown renderer type: {renderer_type}"


def download_image(url: str, output_path: Path) -> bool:
    """Download image from URL."""
    try:
        urllib.request.urlretrieve(url, output_path)
        return True
    except Exception as e:
        print(f"Failed to download image from {url}: {e}")
        return False


def discover_images(images_dir: Path) -> List[Path]:
    """
    Discover all images in a directory with supported extensions.
    
    Supported extensions: from ALLOWED_IMAGE_EXTENSIONS
    Sorting: Lexicographic order by filename (e.g., 001.png, 002.png, ...)
    
    Args:
        images_dir: Directory to search for images
        
    Returns:
        List of image paths, sorted lexicographically by filename
    """
    image_files = []
    
    for ext in ALLOWED_IMAGE_EXTENSIONS:
        # Create glob pattern (extensions already include the dot)
        pattern = f'*{ext}'
        image_files.extend(images_dir.glob(pattern))
    
    # Sort by filename (deterministic order)
    return sorted(image_files, key=lambda p: p.name)


def collect_topic_images(topic_config: Dict[str, Any], output_dir: Path) -> Path:
    """
    Collect images for a topic using Google Custom Search API.
    
    This function uses the dedicated image_collector module to fetch images
    from Google Custom Search API based on the topic's queries.
    
    Args:
        topic_config: Topic configuration dictionary
        output_dir: Output directory for the topic
        
    Returns:
        Path to images directory with collected images
    """
    images_dir = output_dir / IMAGES_SUBDIR
    images_dir.mkdir(exist_ok=True)
    
    print("\n" + "="*70)
    print("IMAGE COLLECTION DIAGNOSTIC")
    print("="*70)
    
    # Check if images already collected
    DIAGNOSTIC_IMAGE_DISPLAY_LIMIT = 5
    existing_images = discover_images(images_dir)  # Use discover_images to check all supported extensions
    if existing_images:
        print(f"✓ Using {len(existing_images)} existing images from {images_dir}")
        for img in existing_images[:DIAGNOSTIC_IMAGE_DISPLAY_LIMIT]:
            print(f"  - {img.name}")
        if len(existing_images) > DIAGNOSTIC_IMAGE_DISPLAY_LIMIT:
            print(f"  ... and {len(existing_images) - DIAGNOSTIC_IMAGE_DISPLAY_LIMIT} more")
        print("="*70 + "\n")
        return images_dir
    
    print(f"No existing images found in {images_dir}")
    print(f"Attempting to collect images using Google Custom Search API...")
    print("")
    
    # Early credential check
    import os
    api_key = os.environ.get('GOOGLE_CUSTOM_SEARCH_API_KEY')
    search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
    
    print("1. Checking Google API Credentials:")
    credentials_valid = True
    
    if not api_key:
        print("   ✗ GOOGLE_CUSTOM_SEARCH_API_KEY environment variable NOT SET")
        credentials_valid = False
    else:
        # Validate API key format
        if api_key.startswith('AIza') and len(api_key) > 30:
            print(f"   ✓ GOOGLE_CUSTOM_SEARCH_API_KEY is set (length: {len(api_key)}, format: OK)")
        else:
            print(f"   ⚠️ GOOGLE_CUSTOM_SEARCH_API_KEY is set but format looks unusual")
            print(f"     Expected format: AIza... (typically 39 characters)")
            print(f"     Got: {api_key[:10]}... with {len(api_key)} characters")
    
    if not search_engine_id:
        print("   ✗ GOOGLE_SEARCH_ENGINE_ID environment variable NOT SET")
        credentials_valid = False
    else:
        # Validate search engine ID format
        if ':' in search_engine_id and len(search_engine_id) > 10:
            print(f"   ✓ GOOGLE_SEARCH_ENGINE_ID is set: {search_engine_id} (format: OK)")
        else:
            print(f"   ⚠️  GOOGLE_SEARCH_ENGINE_ID is set but format looks unusual")
            print(f"     Expected format: xxxxx:xxxxx")
            print(f"     Got: {search_engine_id}")
    
    print("")
    
    if not credentials_valid:
        print("ERROR: Missing or invalid Google Custom Search API credentials")
        print("")
        print("To fix this issue:")
        print("  1. Get API key from: https://console.cloud.google.com/apis/credentials")
        print("  2. Create search engine at: https://programmablesearchengine.google.com/")
        print("  3. Set environment variables:")
        print("     export GOOGLE_CUSTOM_SEARCH_API_KEY='AIza...'")
        print("     export GOOGLE_SEARCH_ENGINE_ID='xxxxx:xxxxx'")
        print("")
        print("For GitHub Actions, add these as repository secrets in:")
        print("  Settings > Secrets and variables > Actions")
        print("")
        # Skip collection attempt if credentials are invalid
    
    # Try to collect images using Google Custom Search API (only if credentials are valid)
    if credentials_valid:
        try:
            print("2. Checking google-api-python-client package:")
            from image_collector import collect_images_for_topic, GOOGLE_API_AVAILABLE
            
            if not GOOGLE_API_AVAILABLE:
                print("   ✗ google-api-python-client is NOT available")
                print("   Install with: pip install google-api-python-client")
                raise ImportError("google-api-python-client package not installed")
            else:
                print("   ✓ google-api-python-client is available")
            
            print("")
            
            # Get topic queries
            topic_queries = topic_config.get('queries', [topic_config.get('title', '')])
            print(f"3. Collecting images:")
            print(f"   Topic: {topic_config.get('title', 'Unknown Topic')}")
            print(f"   Queries: {topic_queries}")
            print("")
            
            # Collect images (10 images by default)
            downloaded_images = collect_images_for_topic(
                topic_title=topic_config.get('title', 'Unknown Topic'),
                topic_queries=topic_queries,
                output_dir=images_dir,
                num_images=10
            )
            
            if downloaded_images:
                print(f"\n✓ Successfully collected {len(downloaded_images)} images")
                print("="*70 + "\n")
                return images_dir
            else:
                print("\n⚠️  No images were downloaded from API")
                print("   This may indicate:")
                print("   - Network connectivity issues")
                print("   - API quota exhausted")
                print("   - Invalid search queries")
                print("   - Search engine misconfiguration")
                    
        except ImportError as e:
            print(f"\n✗ Image collection disabled: {e}")
            print("  Solution: pip install google-api-python-client")
        except Exception as e:
            print(f"\n✗ Unexpected error collecting images: {e}")
            import traceback
            traceback.print_exc()
    
    # Fallback: Create a solid color placeholder image
    print("\n" + "="*70)
    print("⚠️  FALLING BACK TO PLACEHOLDER IMAGE")
    print("="*70)
    print("REASON: Image collection failed or no images downloaded")
    print("RESULT: Videos will show black screen (placeholder color)")
    print("FIX: Set GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID")
    print("="*70 + "\n")
    
    fallback_path = images_dir / 'fallback_000.jpg'
    try:
        subprocess.run([
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'color=c=0x1a1a1a:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=1',
            '-frames:v', '1',
            '-y', str(fallback_path)
        ], check=True, capture_output=True)
        print(f"Created fallback image: {fallback_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create fallback image using FFmpeg.")
        print(f"Command: ffmpeg -f lavfi -i color=c=0x1a1a1a:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:d=1")
        print(f"Error: {e}")
        print(f"Please ensure FFmpeg is installed and available in PATH")
    except Exception as e:
        print(f"Unexpected error creating fallback image: {e}")
    
    return images_dir


# DEPRECATED: Old image collection from sources - no longer used
# Images are now collected using Google Custom Search API via image_collector.py
def _deprecated_collect_from_sources(sources: List[Dict[str, Any]], output_dir: Path) -> Path:
    """
    DEPRECATED: This function attempted to collect images from source objects.
    Images are now collected using Google Custom Search API.
    
    Kept for reference only - do not use.
    """
    images_dir = output_dir / IMAGES_SUBDIR
    images_dir.mkdir(exist_ok=True)
    
    print(f"Collecting images from {len(sources)} sources...")
    image_urls = []
    sources_with_image_field = 0
    
    # Collect ALL image URLs from sources (no limit)
    for source in sources:
        if 'image' in source:
            sources_with_image_field += 1
            if source['image']:
                image_urls.append(source['image'])
    
    # Report statistics
    print(f"  Sources with 'image' field: {sources_with_image_field}/{len(sources)}")
    print(f"  Sources with non-null images: {len(image_urls)}/{len(sources)}")
    print(f"  Images to collect: {len(image_urls)}")
    
    if not image_urls:
        return images_dir
    
    print(f"Found {len(image_urls)} images to download...")
    
    # Download images
    downloaded_count = 0
    for i, url in enumerate(image_urls):
        image_path = images_dir / f'image_{i:03d}.jpg'
        
        # Skip if already exists
        if image_path.exists():
            downloaded_count += 1
            continue
        
        # Download image
        if download_image(url, image_path):
            downloaded_count += 1
    
    print(f"Collected {downloaded_count}/{len(image_urls)} images in {images_dir}")
    return images_dir





def create_background_with_overlay(input_image: Path, output_image: Path, 
                                   width: int = VIDEO_WIDTH, height: int = VIDEO_HEIGHT) -> bool:
    """
    LEGACY FUNCTION - Not currently used in the rendering pipeline.
    
    This function remains for backward compatibility only.
    
    Uses fit-and-pad approach (letterbox/pillarbox):
    - Scales image to fit within frame while preserving aspect ratio
    - Adds black padding bars if needed (letterbox for wide images, pillarbox for tall)
    
    Args:
        input_image: Path to source image
        output_image: Path to save processed image
        width: Target width (default: VIDEO_WIDTH)
        height: Target height (default: VIDEO_HEIGHT)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use 'decrease' to fit image inside frame (letterbox/pillarbox)
        # Then pad with black color to reach target dimensions
        # No blur or darkening effects applied
        video_filter = (
            f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
            f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={BACKGROUND_COLOR}'
        )
        
        subprocess.run([
            'ffmpeg',
            '-i', str(input_image),
            '-vf', video_filter,
            '-y', str(output_image)
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Error creating background: {e}")
        return False


def cleanup_images(output_dir: Path) -> bool:
    """
    Clean up images directory after all videos are generated.
    Only deletes if ENABLE_IMAGE_CLEANUP is True in global config.
    """
    if not ENABLE_IMAGE_CLEANUP:
        print("Image cleanup disabled in configuration")
        return False
    
    success = True
    
    # Clean up original images directory
    images_dir = output_dir / IMAGES_SUBDIR
    if images_dir.exists():
        try:
            shutil.rmtree(images_dir)
            print(f"✓ Cleaned up images directory: {images_dir}")
        except Exception as e:
            print(f"Failed to cleanup images: {e}")
            success = False
    
    return success


def get_image_dimensions(image_path: Path) -> tuple:
    """
    Get image dimensions using ffprobe.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Tuple of (width, height) or (None, None) on error
    """
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=s=x:p=0',
            str(image_path)
        ], capture_output=True, text=True, check=True)
        
        dimensions = result.stdout.strip()
        if 'x' in dimensions:
            width, height = dimensions.split('x')
            return (int(width), int(height))
    except Exception as e:
        print(f"  Warning: Could not get dimensions for {image_path.name}: {e}")
    
    return (None, None)


def create_blurred_background_composite(input_image: Path, output_image: Path,
                                       target_width: int, target_height: int) -> bool:
    """
    Create composite image with blurred background and centered foreground.
    
    For images smaller than target resolution:
    1. Background layer: Image scaled to cover, blurred (sigma=20), and darkened (brightness=-0.3)
    2. Foreground layer: Image scaled to contain (no crop), centered
    3. Add subtle vignette (darken edges)
    4. Add subtle grain for texture
    
    Args:
        input_image: Path to source image
        output_image: Path to save composite
        target_width: Target video width
        target_height: Target video height
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Complex filter for blurred background + centered foreground:
        # 1. [0:v] - split input into two streams
        # 2. Background: scale to cover, blur heavily, and darken
        # 3. Foreground: scale to contain within target, pad to center
        # 4. Overlay foreground on background
        # 5. Add vignette effect (darken edges)
        # 6. Add subtle grain
        
        video_filter = (
            # Split input into background and foreground streams
            f'[0:v]split=2[bg][fg];'
            
            # Background: scale to cover, blur heavily, and darken
            f'[bg]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,'
            f'crop={target_width}:{target_height},'
            f'gblur=sigma={BLUR_SIGMA},'
            f'eq=brightness={BACKGROUND_BRIGHTNESS}[blurred_bg];'
            
            # Foreground: scale to fit within frame (contain), then pad to center
            f'[fg]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
            f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black@0[fg_centered];'
            
            # Overlay centered foreground on blurred background
            f'[blurred_bg][fg_centered]overlay=0:0[composed];'
            
            # Add vignette effect (darken edges at 45-degree angle)
            f'[composed]vignette=angle={VIGNETTE_ANGLE}:mode=forward[vignetted];'
            
            # Add subtle grain for texture
            f'[vignetted]noise=alls={GRAIN_INTENSITY}:allf=t+u[final]'
        )
        
        subprocess.run([
            'ffmpeg', '-y',
            '-i', str(input_image),
            '-filter_complex', video_filter,
            '-map', '[final]',
            '-frames:v', '1',
            '-q:v', '2',  # High quality
            str(output_image)
        ], check=True, capture_output=True, text=True)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Error creating blurred background composite: {e}")
        if e.stderr:
            print(f"    FFmpeg error: {e.stderr[:200]}")
        return False
    except Exception as e:
        print(f"  Error creating blurred background composite: {e}")
        return False


def process_images_for_video(
    images: List[Path],
    target_width: int,
    target_height: int,
    output_dir: Path,
    *,
    min_required_images: int | None = None,
) -> List[Path]:
    """
    Process images for video rendering, creating blurred background composites for undersized images.
    
    Args:
        images: List of input image paths
        target_width: Target video width
        target_height: Target video height
        output_dir: Directory to save processed images
        
    Returns:
        List of processed image paths (mix of originals and composites)
    """
    processed_images: List[Path] = []

    # Resolution-specific cache folder. This is designed to be called *once* per
    # resolution (e.g., 1080x1920 for S/R and 1920x1080 for M/L) before per-item
    # rendering begins.
    processed_dir = output_dir / 'processed'
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Optional fast-path: if processed dir already contains enough images, reuse it.
    allow_partial = os.environ.get("ALLOW_PARTIAL_PREPARED_CACHE", "true").strip().lower() in (
        "1", "true", "yes", "y", "on"
    )
    if allow_partial and min_required_images and min_required_images > 0:
        try:
            existing = [p for p in processed_dir.iterdir() if p.is_file() and not p.name.startswith("manifest_")]
            existing = [p for p in existing if p.stat().st_size > 0]
            if len(existing) >= min_required_images:
                pool = sorted(existing)
                combined = pool + images
                seen = set()
                uniq: List[Path] = []
                for p in combined:
                    rp = str(p.resolve())
                    if rp not in seen:
                        seen.add(rp)
                        uniq.append(p)
                print(f"  ✓ Using existing prepared images cache (partial) for {target_width}x{target_height}: {len(pool)} >= {min_required_images}")
                return uniq
        except Exception:
            pass

    # Manifest-based cache: if present and valid, skip expensive preprocessing.
    manifest_path = processed_dir / f"manifest_{target_width}x{target_height}.json"

    def _manifest_valid() -> bool:
        try:
            import json as _json
            if not manifest_path.exists():
                return False
            data = _json.loads(manifest_path.read_text(encoding="utf-8"))
            by_name = {e.get("source_name"): e for e in data.get("entries", [])}
            if len(by_name) < len(images):
                return False
            for src in images:
                st = src.stat()
                e = by_name.get(src.name)
                if not e:
                    return False
                if int(e.get("source_size", -1)) != int(st.st_size):
                    return False
                if abs(float(e.get("source_mtime", -1.0)) - float(st.st_mtime)) > 1.0:
                    return False
                if e.get("mode") == "composite":
                    out_file = e.get("out_file")
                    if not out_file:
                        return False
                    outp = processed_dir / out_file
                    if not outp.exists() or outp.stat().st_size == 0:
                        return False
            return True
        except Exception:
            return False

    if not _manifest_valid():
        # Attempt restore from tenant assets release (persistent cache)
        try:
            restored = restore_images_cache_from_release(images, target_width, target_height, processed_dir)
            if restored:
                print(f"  ✓ Restored prepared images from tenant assets (tenant={get_tenant_id()})")
        except Exception as e:
            print(f"  ⓘ Tenant assets restore attempt failed: {e}")

    if _manifest_valid():
        # Build processed list from manifest without invoking FFmpeg.
        import json as _json
        data = _json.loads(manifest_path.read_text(encoding="utf-8"))
        by_name = {e.get("source_name"): e for e in data.get("entries", [])}
        for src in images:
            e = by_name.get(src.name, {})
            if e.get("mode") == "composite":
                processed_images.append(processed_dir / e["out_file"])
            else:
                processed_images.append(src)
        print(f"  ✓ Using cached prepared images (manifest) for {target_width}x{target_height}; skipping preprocessing")
        return processed_images

    total = len(images)
    print(f"  Processing {total} images for {target_width}x{target_height} video...")

    undersized_count = 0
    cached_count = 0
    passthrough_count = 0
    unknown_dim_count = 0

    # Collect manifest entries so we can skip preprocessing next runs (local or restored from Release assets).
    manifest_entries: List[dict] = []

    for i, img_path in enumerate(images):
        img_width, img_height = get_image_dimensions(img_path)

        # Default output is the original image (passthrough)
        out_path: Path = img_path

        if img_width is None or img_height is None:
            unknown_dim_count += 1
            status = "using original (dimensions unknown)"
        elif img_width < target_width or img_height < target_height:
            undersized_count += 1
            composite_path = processed_dir / f'composite_{i:05d}{img_path.suffix}'

            # Reuse cache if the composite exists and is newer than the source.
            try:
                if composite_path.exists() and composite_path.stat().st_mtime >= img_path.stat().st_mtime:
                    cached_count += 1
                    out_path = composite_path
                    status = f"{img_width}x{img_height} - cached composite"
                else:
                    status = f"{img_width}x{img_height} - creating composite"
                    if create_blurred_background_composite(img_path, composite_path, target_width, target_height):
                        out_path = composite_path
                    else:
                        status = f"{img_width}x{img_height} - composite failed, using original"
                        out_path = img_path
            except Exception as e:
                status = f"{img_width}x{img_height} - composite error ({e}), using original"
                out_path = img_path
        else:
            passthrough_count += 1
            status = f"{img_width}x{img_height} - ok"

        print(f"    Image {i+1}/{total}: {img_path.name} - {status}")
        processed_images.append(out_path)

        # Add manifest entry for cache validation
        try:
            st = img_path.stat()
            entry = {
                'source_name': img_path.name,
                'source_size': int(st.st_size),
                'source_mtime': float(st.st_mtime),
                'mode': 'composite' if (out_path != img_path) else 'passthrough',
                'out_file': (out_path.name if (out_path != img_path) else None),
            }
            manifest_entries.append(entry)
        except Exception:
            pass

    # Summary
    if undersized_count > 0:
        created_count = max(0, undersized_count - cached_count)
        print(
            "  ✓ Preprocess summary: "
            f"undersized={undersized_count} (created={created_count}, cached={cached_count}), "
            f"ok={passthrough_count}, unknown_dims={unknown_dim_count}"
        )
    else:
        print(f"  ✓ Preprocess summary: all images are adequate size (ok={passthrough_count}, unknown_dims={unknown_dim_count})")

    # Write manifest for cache validation / reuse (local + tenant release restore)
    try:
        import json as _json
        manifest_payload = {
            'target_width': int(target_width),
            'target_height': int(target_height),
            'entries': manifest_entries,
        }
        manifest_path.write_text(_json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  ✓ Wrote preprocess manifest: {manifest_path.name}")
    except Exception as e:
        print(f"  ⚠ Failed to write preprocess manifest (non-fatal): {e}")

    # Publish prepared images to tenant assets release immediately after processing
    try:
        published = publish_images_cache_to_release(images, target_width, target_height, processed_dir)
        if not published:
            print("  ⓘ Prepared images not published (cache disabled or GH CLI unavailable)")
    except Exception as e:
        print(f"  ⚠ Failed to publish prepared images cache (non-fatal): {e}")

    return processed_images



def render_with_blender(images_dir: Path, audio_path: Path, output_path: Path,
                       content_type: str, seed: str = None,
                       audio_duration: float = None, template_path: Path = None) -> bool:
    """
    Render video using Blender 4.5 LTS pipeline.
    
    Args:
        images_dir: Directory containing images
        audio_path: Path to audio file
        output_path: Path to output video
        content_type: Content type (long, medium, short, reels)
        seed: Random seed for template selection (optional)
        audio_duration: Audio duration in seconds (optional)
        template_path: Path to Blender template file (optional)
        
    Returns:
        True if successful, False otherwise
    """
    blender_output = get_blender_output_path(output_path)
    try:
        # Check if Blender is available
        blender_paths = [
            '../blender-4.5.0-linux-x64/blender',  # Relative from scripts/ directory (CI downloaded version)
            './blender-4.5.0-linux-x64/blender',   # Relative from repo root
            'blender',  # System blender
            '/usr/bin/blender',
            '/usr/local/bin/blender',
            str(Path.home() / 'blender' / 'blender'),
        ]
        
        blender_cmd = None
        for path in blender_paths:
            try:
                result = subprocess.run([path, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    blender_cmd = path
                    print(f"  Found Blender: {path}")
                    break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        if not blender_cmd:
            print("  ✗ Blender not found - falling back to FFmpeg")
            return False
        
        # Generate seed if not provided
        if not seed:
            import hashlib
            topic_id = str(output_path.parent.name)
            date_str = datetime.now().strftime('%Y%m%d')
            code = str(output_path.stem.split('-')[-1])
            seed_input = f"{topic_id}-{date_str}-{code}"
            seed = hashlib.sha256(seed_input.encode()).hexdigest()[:12]
        
        # Template path is now passed in from the caller
        # Log template usage
        if template_path:
            print(f"  Using template: {template_path.name}")
        else:
            print(f"  No template specified (minimal rendering)")
        
        # Build Blender command
        script_path = Path(__file__).parent / 'blender' / 'build_video.py'
        
        if not script_path.exists():
            print(f"  ✗ Blender script not found: {script_path}")
            return False
        
        cmd = [
            blender_cmd,
            '--background',
            '--python', str(script_path),
            '--',
            '--images', str(images_dir),
            '--audio', str(audio_path),
            '--output', str(blender_output),
            '--profile', content_type,
            '--seed', seed
        ]
        
        # Add template if selected
        if template_path:
            cmd.extend(['--template', str(template_path)])
        
        # Force deterministic timeline and skip Blender audio to avoid codec issues
        if audio_duration:
            cmd += ['--duration', str(audio_duration)]
        cmd += ['--no-audio']
        
        print(f"  Rendering with Blender (seed: {seed})...")
        print(f"  Images directory: {images_dir}")
        print(f"  Audio file: {audio_path}")
        print(f"  Blender output file: {blender_output}")
        print(f"  Final output file: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            print(f"  ✗ Blender render failed (exit code {result.returncode}):")
            stderr_out = result.stderr.strip()
            stdout_out = result.stdout.strip()
            if stderr_out:
                print(f"    stderr: {stderr_out[:500]}")
            if stdout_out:
                print(f"    stdout: {stdout_out[:500]}")
            if not stderr_out and not stdout_out:
                print("    No output captured from Blender.")
            return False
        
        print(f"  ⓘ Blender process completed (exit code 0). Validating output file...")
        
        # Diagnostic: List MP4 files in output directory to see what Blender actually created
        print(f"\n  === MP4 FILES DIAGNOSTIC ===")
        try:
            output_dir_path = output_path.parent
            mp4_files = sorted(output_dir_path.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
            print(f"  MP4s in output dir after Blender:")
            for p in mp4_files[:10]:
                file_stat = p.stat()
                file_size_mb = file_stat.st_size / (1024 * 1024)
                print(f"    {p.name} ({file_size_mb:.2f} MB)")
            if len(mp4_files) == 0:
                print(f"    No MP4 files found")
        except Exception as e:
            print(f"  Warning: Could not list MP4 files: {e}")
        print(f"  === END MP4 FILES DIAGNOSTIC ===\n")
        
        # Verify Blender output file exists
        # In video-only mode, Blender may write directly to output_path instead of blender_output
        blender_size = get_safe_file_size(blender_output)
        blender_ok = blender_size is not None and blender_size > MIN_OUTPUT_SIZE_BYTES
        
        final_size = get_safe_file_size(output_path)
        final_ok = final_size is not None and final_size > MIN_OUTPUT_SIZE_BYTES
        
        produced = None
        if blender_ok:
            produced = blender_output
            print(f"  ✓ Blender output verified: {blender_output.name} ({blender_size / (1024*1024):.2f} MB)")
        elif final_ok:
            produced = output_path
            print(f"  ✓ Blender output verified (final path): {output_path.name} ({final_size / (1024*1024):.2f} MB)")
            # Normalize to .blender.mp4 convention for consistency
            if not blender_output.exists():
                try:
                    shutil.copy2(output_path, blender_output)
                    print(f"  ⓘ Copied to .blender.mp4 convention: {blender_output.name}")
                    produced = blender_output
                except (OSError, IOError) as e:
                    print(f"  ⚠ Warning: Could not copy to .blender.mp4: {e}")
                    # Continue with final_ok path; copy is for normalization only
        else:
            print(f"  ⚠ Expected output file not found: {blender_output}")
            if not final_ok:
                print(f"  ⚠ Final output file also not found: {output_path}")
            print(f"  ✗ Blender output file missing - cannot proceed with mux")
            # Surface Blender logs even on exit code 0
            stdout_out = (result.stdout or "").strip()
            stderr_out = (result.stderr or "").strip()
            if stdout_out:
                print("  --- Blender stdout (tail) ---")
                print(get_log_tail(stdout_out))
            if stderr_out:
                print("  --- Blender stderr (tail) ---")
                print(get_log_tail(stderr_out))
            if not stdout_out and not stderr_out:
                print("  (No stdout/stderr captured from Blender.)")
            print(f"  This indicates Blender did not write the expected output.")
            return False
        
        # Check if audio muxing is enabled
        if not ENABLE_VIDEO_AUDIO_MUX:
            print(f"  ⓘ Audio muxing disabled (ENABLE_VIDEO_AUDIO_MUX=False)")
            print(f"  ✓ Video-only output: {blender_output}")
            return True
        
        # Mux original AAC audio with Blender video output
        # Use temporary output file to avoid input == output issues
        mux_temp_output = output_path.parent / f"{output_path.stem}.mux.mp4"
        
        mux_cmd = [
            'ffmpeg', '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-i', str(blender_output),
            '-i', str(audio_path),
            '-map', '0:v:0',  # Map first video stream from first input
            '-map', '1:a:0',  # Map first audio stream from second input
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-shortest',
            '-movflags', '+faststart',
            str(mux_temp_output)
        ]
        print(f"  Muxing audio with FFmpeg...")
        try:
            try:
                subprocess.run(mux_cmd, capture_output=True, text=True, check=True)
                print(f"  ✓ Audio mux complete")
                
                # Verify mux output file exists and has content
                try:
                    if not mux_temp_output.exists():
                        print(f"  ✗ Mux output file not found: {mux_temp_output}")
                        return False
                    
                    mux_size = mux_temp_output.stat().st_size
                    if mux_size == 0:
                        print(f"  ✗ Mux output file is empty: {mux_temp_output}")
                        return False
                except (OSError, FileNotFoundError) as e:
                    print(f"  ✗ Error verifying mux output: {e}")
                    return False
                
                # Atomically move temp file to final output path (keep .blender.mp4 extension)
                os.replace(str(mux_temp_output), str(blender_output))
                print(f"  ✓ Final output: {blender_output}")
                
            except subprocess.CalledProcessError as e:
                print(f"  ✗ FFmpeg mux failed with exit code {e.returncode}")
                if e.stderr:
                    print(f"    FFmpeg error output:")
                    print(f"    {e.stderr.strip()}")
                if e.stdout:
                    print(f"    FFmpeg stdout:")
                    print(f"    {e.stdout.strip()}")
                return False
            except Exception as e:
                print(f"  ✗ Unexpected error during mux: {e}")
                return False
        finally:
            # Clean up temp file if it still exists (only happens on error)
            # On success, os.replace() moves the file, so exists() returns False
            if mux_temp_output.exists():
                try:
                    mux_temp_output.unlink()
                except (OSError, FileNotFoundError) as cleanup_err:
                    print(f"    Warning: Failed to clean up temp file: {cleanup_err}")
        
        return True
            
    except subprocess.TimeoutExpired:
        print(f"  ✗ Blender render timed out (10 minutes)")
        return False
    except Exception as e:
        print(f"  ✗ Blender render error: {e}")
        return False
    # Note: blender_output is now the final output file and should not be deleted


def create_video_from_images(background_images: List[Path], audio_path: Optional[Path], 
                            output_path: Path, config: Dict[str, Any],
                            chapters: List[Dict[str, Any]], 
                            content_code: str = None,
                            script_path: Path = None,
                            video_duration: float = None) -> bool:
    """
    Create video from images, optionally with audio.
    
    The video is a slideshow of images with variable duration per image.
    Video duration matches audio duration (or provided video_duration), looping images if necessary.
    
    Args:
        background_images: List of image paths for the slideshow
        audio_path: Path to audio file (can be None if video_duration is provided)
        output_path: Path to save output video
        config: Video configuration dict (width, height, fps, etc.)
        chapters: Chapter metadata (optional)
        content_code: Content code (e.g., 'L1', 'M2')
        script_path: Script path (optional, currently unused)
        video_duration: Duration in seconds (used when audio_path is None or ENABLE_VIDEO_AUDIO_MUX is False)
    
    Returns:
        True if successful, False otherwise
    """
    import random
    
    try:
        # Early validation: Check parameter combinations
        if ENABLE_VIDEO_AUDIO_MUX and audio_path is None:
            raise ValueError("audio_path is required when ENABLE_VIDEO_AUDIO_MUX is True")
        
        if video_duration is None and audio_path is None:
            raise ValueError("Either video_duration or audio_path must be provided")
        
        # Ensure target dimensions are even for codec compatibility
        width = int(config.get('video_width', VIDEO_WIDTH))
        height = int(config.get('video_height', VIDEO_HEIGHT))
        video_width = width + (width % 2)  # Add 1 if odd to keep encoder-friendly dimensions
        video_height = height + (height % 2)  # Add 1 if odd to keep encoder-friendly dimensions
        fps = config.get('video_fps', VIDEO_FPS)
        
        # Determine duration: use video_duration if provided, otherwise get from audio file
        if video_duration is not None:
            audio_duration = video_duration
            print(f"  Video configuration:")
            print(f"    Resolution: {video_width}x{video_height}")
            print(f"    FPS: {fps}")
            print(f"    Duration: {audio_duration:.2f}s (specified)")
            print(f"    Available images: {len(background_images)}")
        elif audio_path and ENABLE_VIDEO_AUDIO_MUX:
            # Get audio duration from file only if we're muxing audio
            audio_duration = get_audio_duration(audio_path)
            print(f"  Video configuration:")
            print(f"    Resolution: {video_width}x{video_height}")
            print(f"    FPS: {fps}")
            print(f"    Audio duration: {audio_duration:.2f}s")
            print(f"    Available images: {len(background_images)}")
        else:
            raise ValueError("Either video_duration or audio_path (with ENABLE_VIDEO_AUDIO_MUX=True) must be provided")
        
        # Try FFmpeg effects mode if enabled (Ken Burns + xfade transitions)
        effects_success = False
        if ENABLE_FFMPEG_EFFECTS and VIDEO_RENDERER == 'ffmpeg':
            print(f"  Attempting FFmpeg effects mode (Ken Burns + xfade)...")
            
            # Infer content type from content code
            content_type = infer_content_type_from_code(content_code) if content_code else 'long'
            
            # Generate seed for deterministic output
            seed = output_path.stem if output_path else None
            
            # Try rendering with effects
            # Note: This creates video-only output, audio muxing happens separately
            effects_success = render_slideshow_ffmpeg_effects(
                images=background_images,
                output_path=output_path,
                duration=audio_duration,
                width=video_width,
                height=video_height,
                fps=fps,
                content_type=content_type,
                seed=seed
            )
            
            if effects_success:
                print(f"  ✓ FFmpeg effects mode succeeded")
                
                # If audio muxing is enabled and we have an audio file, mux it now
                if ENABLE_VIDEO_AUDIO_MUX and audio_path:
                    print(f"  Muxing audio with FFmpeg...")
                    mux_temp_output = output_path.parent / f"{output_path.stem}.mux.mp4"
                    
                    try:
                        mux_cmd = [
                            'ffmpeg', '-y',
                            '-hide_banner',
                            '-loglevel', 'error',
                            '-i', str(output_path),
                            '-i', str(audio_path),
                            '-map', '0:v:0',
                            '-map', '1:a:0',
                            '-c:v', 'copy',
                            '-c:a', 'copy',
                            '-shortest',
                            '-movflags', '+faststart',
                            str(mux_temp_output)
                        ]
                        subprocess.run(mux_cmd, capture_output=True, text=True, check=True)
                        os.replace(str(mux_temp_output), str(output_path))
                        print(f"  ✓ Audio mux complete")
                    except Exception as e:
                        print(f"  ✗ Audio mux failed: {e}")
                        # Clean up temp file
                        if mux_temp_output.exists():
                            mux_temp_output.unlink()
                        effects_success = False
                
                if effects_success:
                    # Captions burn-in is a dedicated subflow.
                    if not maybe_burn_captions(audio_path=audio_path, video_path=output_path):
                        return False

                    # Success - skip legacy concat mode
                    return True
            else:
                print(f"  ⓘ FFmpeg effects mode failed or unavailable, falling back to legacy concat mode")
        
        # Legacy concat mode (fallback or default when effects disabled)
        print(f"  Using legacy FFmpeg concat mode (hard cuts)...")
        
        # Calculate dynamic image durations with random timing (3-8 seconds per image)
        # Cycle through images if needed to cover full video duration
        image_durations = []
        total_time = 0
        image_index = 0
        
        while total_time < audio_duration:
            # Random duration between 3-8 seconds
            duration = random.uniform(IMAGE_TRANSITION_MIN_SEC, IMAGE_TRANSITION_MAX_SEC)
            
            # Don't exceed audio duration on last image
            if total_time + duration > audio_duration:
                duration = audio_duration - total_time
            
            image_durations.append((background_images[image_index % len(background_images)], duration))
            total_time += duration
            image_index += 1
        
        # Log slideshow schedule
        images_used = len(image_durations)
        images_looped = images_used > len(background_images)
        print(f"    Slideshow schedule: {images_used} image slots")
        if images_looped:
            loops = images_used // len(background_images)
            print(f"    Images looped {loops}x to cover audio duration")
        print(f"    Image duration range: {IMAGE_TRANSITION_MIN_SEC}-{IMAGE_TRANSITION_MAX_SEC}s per image")

        # Write image-title timeline sidecar for post-processing overlays.
        try:
            title_map = _load_image_title_map([img for img, _ in image_durations])
            segs: List[Dict[str, Any]] = []
            t0 = 0.0
            for idx, (img, dur) in enumerate(image_durations):
                title = title_map.get(Path(img).name, "").strip()
                d = float(dur or 0.0)
                if title and d > 0:
                    segs.append(
                        {
                            "start": round(t0, 3),
                            "end": round(min(audio_duration, t0 + d), 3),
                            "text": title,
                            "filename": Path(img).name,
                            "index": idx,
                        }
                    )
                t0 += d
            _write_image_titles_sidecar(output_path, segs)
        except Exception:
            pass
        
        # Create concat file for images with variable durations
        concat_file = output_path.parent / 'images_concat.txt'
        with open(concat_file, 'w') as f:
            for img, duration in image_durations[:-1]:  # All but last
                # Use absolute paths with single quotes for -safe 0 compatibility
                f.write(f"file '{img.absolute()}'\n")
                f.write(f"duration {duration}\n")
            # Add last image without duration (it will play until end)
            if image_durations:
                f.write(f"file '{image_durations[-1][0].absolute()}'\n")
        
        # Create video from images
        print(f"  Generating video: {output_path.name}")
        
        # Determine video format (horizontal or vertical) based on aspect ratio
        # Vertical: 9:16 aspect ratio (height > width, specifically 1080x1920)
        # Horizontal: 16:9 aspect ratio (width > height, specifically 1920x1080)
        aspect_ratio = video_width / video_height if video_height > 0 else 1.0
        video_format = 'vertical' if aspect_ratio < 1.0 else 'horizontal'
        bitrate_config = VIDEO_BITRATE_SETTINGS[video_format]
        
        # Calculate keyframe interval in frames
        keyframe_interval_frames = int(fps * VIDEO_KEYFRAME_INTERVAL_SEC)
        
        scale_filter = (
            f"scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,"
            f"pad={video_width}:{video_height}:(ow-iw)/2:(oh-ih)/2"
        )
        
        # Build FFmpeg command based on whether audio muxing is enabled
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
        ]
        
        # Add audio input only if muxing is enabled (validation already done at function start)
        if ENABLE_VIDEO_AUDIO_MUX:
            ffmpeg_cmd.extend(['-i', str(audio_path)])
        
        # Add video filters and encoding options
        ffmpeg_cmd.extend([
            '-vf', scale_filter,
            '-c:v', VIDEO_CODEC,
            '-profile:v', VIDEO_CODEC_PROFILE,
            '-b:v', bitrate_config['bitrate'],
            '-maxrate', bitrate_config['maxrate'],
            '-bufsize', bitrate_config['bufsize'],
            '-g', str(keyframe_interval_frames),  # Keyframe interval
        ])
        
        # Add audio encoding options only if muxing is enabled
        if ENABLE_VIDEO_AUDIO_MUX:
            ffmpeg_cmd.extend([
                '-c:a', 'aac',
                '-b:a', TTS_AUDIO_BITRATE,
                '-shortest',
            ])
        else:
            # For video-only, use exact duration from concat file
            ffmpeg_cmd.extend([
                '-t', str(audio_duration),
            ])
        
        # Add final output options
        ffmpeg_cmd.extend([
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),
            '-y', str(output_path)
        ])
        
        print(f"  Executing FFmpeg command...")
        print(f"    Input: {len(image_durations)} image slots from {concat_file}")
        if ENABLE_VIDEO_AUDIO_MUX:
            print(f"    Audio: {audio_path}")
        else:
            print(f"    Audio: DISABLED (video-only mode)")
            print(f"    Duration: {audio_duration:.2f}s")
        print(f"    Output: {output_path}")
        
        try:
            result = subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"  ✗ FFmpeg command failed with exit code {e.returncode}")
            if e.stderr:
                print(f"  FFmpeg error output:")
                # Print last 20 lines of stderr for debugging
                stderr_lines = e.stderr.strip().split('\n')
                for line in stderr_lines[-20:]:
                    print(f"    {line}")
            if e.stdout:
                print(f"  FFmpeg stdout (last 10 lines):")
                stdout_lines = e.stdout.strip().split('\n')
                for line in stdout_lines[-10:]:
                    print(f"    {line}")
            raise
        
        # Get final video info
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration,size',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(output_path)
            ], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                video_duration = float(lines[0])
                video_size_bytes = int(lines[1])
                video_size_mb = video_size_bytes / (1024 * 1024)
                print(f"  ✓ Video created: {output_path.name}")
                print(f"    Duration: {video_duration:.2f}s, Size: {video_size_mb:.2f}MB")
        except:
            print(f"  ✓ Video created: {output_path.name}")

        # Captions burn-in is a dedicated subflow.
        if not maybe_burn_captions(audio_path=audio_path, video_path=output_path):
            return False
        
        # Cleanup temporary files
        concat_file.unlink()
        
        return True
        
    except Exception as e:
        print(f"Error creating video: {e}")
        import traceback
        traceback.print_exc()
        return False


def render_for_topic(topic_id: str, date_str: str = None) -> bool:
    """
    Render video(s) for a topic using multi-format generation.
    
    Note: Single-format generation has been removed. Topics must have the
    'content_types' field configured in their topic configuration to specify
    which formats to generate (long, medium, short, reels).
    
    Args:
        topic_id: Topic identifier (e.g., 'topic-01')
        date_str: Date string in YYYYMMDD format (default: today)
        
    Returns:
        True if all videos rendered successfully, False otherwise
    """
    try:
        if date_str is None:
            date_str = datetime.now().strftime('%Y%m%d')
        
        config = load_topic_config(topic_id)
        output_dir = get_output_dir(topic_id)
        
        # Always use multi-format rendering
        return render_multi_format_for_topic(topic_id, date_str, config, output_dir)
        
    except Exception as e:
        print(f"Error rendering video for {topic_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def render_multi_format_for_topic(topic_id: str, date_str: str,
                                  config: Dict[str, Any], output_dir: Path) -> bool:
    """
    Render videos for multi-format topic (15 videos).
    
    Process:
    1. Collect 50+ images for the topic (shared across all videos)
    2. Find all audio files matching pattern: {topic}-{date}-*.m4a
    3. Render video for each audio file
    4. Clean up images after all videos complete
    """
    print(f"Rendering multi-format videos for {topic_id}...")
    print(f"Video Renderer: {VIDEO_RENDERER}")
    print(f"Video Generation: {'Enabled' if ENABLE_VIDEO_GENERATION else 'Disabled'}")
    print(f"Video-Audio Muxing: {'Enabled' if ENABLE_VIDEO_AUDIO_MUX else 'Disabled (video-only mode)'}")
    
    # Check if video generation is enabled
    if not ENABLE_VIDEO_GENERATION:
        print("Video generation is disabled (ENABLE_VIDEO_GENERATION = False)")
        print("Skipping video rendering")
        return True
    
    # Pre-flight check: Verify renderer is available
    available, result = check_renderer_available(VIDEO_RENDERER)
    if not available:
        print(f"\n✗ ERROR: Video renderer '{VIDEO_RENDERER}' is not available")
        print(f"  {result}")
        
        # Try fallback to FFmpeg if primary renderer was Blender
        if VIDEO_RENDERER == 'blender':
            print(f"\n  Checking FFmpeg as fallback...")
            ffmpeg_available, ffmpeg_result = check_renderer_available('ffmpeg')
            if ffmpeg_available:
                print(f"  ✓ FFmpeg is available as fallback: {ffmpeg_result}")
            else:
                print(f"  ✗ FFmpeg fallback also unavailable: {ffmpeg_result}")
                print(f"\n  FATAL: No video renderer available. Cannot proceed with video rendering.")
                print(f"  Please install FFmpeg: sudo apt-get install ffmpeg")
                return False
        else:
            print(f"\n  FATAL: No video renderer available. Cannot proceed with video rendering.")
            return False
    else:
        print(f"  ✓ Renderer available: {result}")
    
    # Additional check for ffprobe (required for audio duration detection)
    try:
        probe_result = subprocess.run(['ffprobe', '-version'],
                                     capture_output=True, text=True, timeout=5)
        if probe_result.returncode == 0:
            print(f"  ✓ ffprobe is available")
        else:
            print(f"  ⚠ Warning: ffprobe returned non-zero exit code")
    except FileNotFoundError:
        print(f"  ✗ ERROR: ffprobe not found - required for audio duration detection")
        print(f"  Please install FFmpeg (includes ffprobe): sudo apt-get install ffmpeg")
        return False
    except Exception as e:
        print(f"  ⚠ Warning: ffprobe check failed: {e}")
    
    # Step 1: Collect images using Google Custom Search API
    print(f"\nStep 1: Collecting images using Google Custom Search API...")
    images_dir = collect_topic_images(config, output_dir)
    
    # Get all images for video rendering (auto-discover with supported extensions)
    image_files = discover_images(images_dir)
    if not image_files:
        print(f"Error: No images found in {images_dir}")
        print(f"  Supported formats: .jpg, .jpeg, .png, .webp")
        return False
    
    print(f"✓ Discovered {len(image_files)} images for video rendering (sorted by filename)")
    
    # Verify all images are accessible and have content
    print(f"Verifying image files are readable...")
    verified_images = []
    for img_file in image_files:
        try:
            file_size = img_file.stat().st_size
            if file_size > 0:
                verified_images.append(img_file)
            else:
                print(f"  Warning: Empty file skipped: {img_file.name}")
        except Exception as e:
            print(f"  Warning: Cannot access file {img_file.name}: {e}")
    
    if not verified_images:
        print(f"Error: No valid images available for video rendering")
        return False
    
    if len(verified_images) != len(image_files):
        print(f"  Warning: Only {len(verified_images)}/{len(image_files)} images are valid")
    else:
        print(f"  ✓ All {len(verified_images)} images verified")
    
    image_files = verified_images
    
    # Step 2: Find all audio files (M4A with AAC codec)
    print(f"\nStep 2: Finding audio files...")
    pattern = str(output_dir / f"{topic_id}-{date_str}-*.m4a")
    audio_files = glob.glob(pattern)
    
    if not audio_files:
        print(f"No audio files found matching: {pattern}")
        return False
    
    print(f"Found {len(audio_files)} audio files to render")
    print(f"✓ Using {len(image_files)} images directly for video rendering")
    
    # Allocate images consecutively across videos.
    # For FFmpeg effects mode, we allocate based on the *actual* slot count per video
    # (duration + still range + transition duration). This avoids hardcoding a fixed
    # number of images per video and prevents unnecessary image repetition.
    image_cursor = 0
    fallback_images_per_video = max(1, math.ceil(len(image_files) / max(1, len(audio_files))))
    if VIDEO_RENDERER == 'ffmpeg' and ENABLE_FFMPEG_EFFECTS:
        print("Image allocation: dynamic (per-video slot count; consecutive rotation across renders)")
    else:
        print(f"Image allocation: {fallback_images_per_video} images per video (consecutive slices)")
    
    # Load video template configuration
    repo_root = Path(__file__).parent.parent
    tpl_cfg = load_video_template_config(repo_root)
    
    # Initialize template selector if templates are available
    templates_dir = repo_root / "templates"
    inventory_path = templates_dir / "inventory.yml"
    selector = None
    
    if inventory_path.exists():
        try:
            # Import template selector
            import sys
            blender_dir = Path(__file__).parent / 'blender'
            if str(blender_dir) not in sys.path:
                sys.path.insert(0, str(blender_dir))
            from template_selector import TemplateSelector
            
            selector = TemplateSelector(templates_dir=templates_dir, inventory_path=inventory_path)
            print(f"✓ Template selector initialized")
        except Exception as e:
            print(f"⚠ Warning: Could not initialize template selector: {e}")
            selector = None
    else:
        print(f"⚠ Warning: Template inventory not found at {inventory_path}")
    
    # Initialize rotation counters per content type
    rotation_idx = {}  # content_type -> int
    
    # Step 3: Render video for each audio
    print(f"\nStep 3: Rendering videos...")
    success_count = 0
    fail_count = 0
    

    # Build list of audio render jobs for enabled content types
    # Determine which content types are enabled for this topic. The `config` object
    # passed into this function is the topic configuration.
    enabled_specs = get_enabled_content_types(config)
    # Extract code prefixes from the 'code' field (e.g., 'R1' -> 'R')
    enabled_prefixes = {spec['code'][0].upper() for spec in enabled_specs if spec.get('code') and len(spec['code']) > 0}
    if not enabled_prefixes:
        enabled_prefixes = {spec.get('code_prefix', '').upper() for spec in CONTENT_TYPES.values()}

    audio_jobs = []
    for audio_file_path in sorted(audio_files):
        audio_path = Path(audio_file_path)

        # Extract content code from filename
        stem = audio_path.stem  # e.g., "topic-01-20251216-L1" or "topic-01-20251216-L1.script"
        script_suffix = '.script'
        if stem.endswith(script_suffix):
            stem = stem[:-len(script_suffix)]
        parts = stem.split('-')
        if len(parts) < 4:
            print(f"Warning: Unable to extract code from filename: {audio_path.name}")
            continue

        date_str = parts[2]
        code = parts[3]
        if not code or len(code) < 2:
            print(f"Warning: Invalid content code for filename: {audio_path.name}")
            continue

        code_prefix = code[0].upper()
        if code_prefix not in enabled_prefixes:
            print(f"Skipping {audio_path.name}: content type {code_prefix} is not enabled")
            continue

        video_width, video_height = get_video_resolution_for_code(code)
        audio_jobs.append({
            'audio_path': audio_path,
            'code': code,
            'date_str': date_str,
            'video_width': video_width,
            'video_height': video_height,
        })

    if not audio_jobs:
        print("No audio files for enabled content types. Nothing to render.")
        return False

    # Pre-process images once per required target resolution to avoid repeating composite work per item
    needed_resolutions = sorted({(j['video_width'], j['video_height']) for j in audio_jobs})
    prepared_images_by_res = {}
    try:
        min_pool_default = int(os.environ.get("PREPARED_IMAGES_MIN_COUNT", "60"))
    except Exception:
        min_pool_default = 60

    for w, h in needed_resolutions:
        cache_dir = output_dir / '_prepared_images' / f"{w}x{h}"
        # Keep cache between runs; composites are invalidated automatically when sources change.
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nPre-processing images for {w}x{h} video (one-time cache; {len(image_files)} source images)...")
        prepared_images_by_res[(w, h)] = process_images_for_video(
            image_files, w, h, cache_dir, min_required_images=min_pool_default
        )

    for job in audio_jobs:
        audio_path = job['audio_path']
        code = job['code']
        date_str = job['date_str']
        video_width = job['video_width']
        video_height = job['video_height']

        # Generate corresponding video filename
        video_path = output_dir / f"{topic_id}-{date_str}-{code}.mp4"

        # Load corresponding chapters
        chapters_path = output_dir / f"{topic_id}-{date_str}-{code}.chapters.json"
        chapters = []
        if chapters_path.exists():
            with open(chapters_path, 'r', encoding='utf-8') as f:
                chapters = json.load(f)

        # Note: Script loading for subtitles removed per requirements

        print(f"\n{'='*60}")
        print(f"Rendering {code}: {audio_path.name}")
        print(f"{'='*60}")

        video_images_dir = None
        try:
            # Compute audio duration once for determinism
            audio_duration = get_audio_duration(audio_path)

            # Select consecutive images for this video from the pre-processed pool.
            # In FFmpeg effects mode, allocate images by *slot count* so we do not under-feed
            # the transition schedule (which otherwise forces cycling a tiny set of images).
            prepared_pool = prepared_images_by_res.get((video_width, video_height), image_files)
            if not prepared_pool:
                raise RuntimeError('No images available for rendering')

            # Determine the number of images needed for this render.
            # - FFmpeg effects mode: use estimated slot count (deterministic by seed)
            # - Otherwise: use fallback slice size
            code_prefix = code[0].upper() if code else 'L'
            content_type_map = {'L': 'long', 'M': 'medium', 'S': 'short', 'R': 'reels'}
            ct_for_alloc = content_type_map.get(code_prefix, 'long')

            if VIDEO_RENDERER == 'ffmpeg' and ENABLE_FFMPEG_EFFECTS:
                effects_cfg = load_ffmpeg_effects_config() or {}
                needed_images = estimate_ffmpeg_effects_slot_count(
                    duration=float(audio_duration),
                    content_type=ct_for_alloc,
                    seed=video_path.stem,
                    effects_config=effects_cfg,
                )
            else:
                needed_images = fallback_images_per_video

            needed_images = max(1, int(needed_images))
            needed_images = min(needed_images, len(prepared_pool))

            # Round-robin selection across all renders.
            selected_images = [
                prepared_pool[(image_cursor + i) % len(prepared_pool)]
                for i in range(needed_images)
            ]
            image_cursor = (image_cursor + needed_images) % len(prepared_pool)

            # Materialize selected images into a dedicated directory to preserve order
            video_images_dir = output_dir / f"{code}_images"
            if video_images_dir.exists():
                shutil.rmtree(video_images_dir)
            video_images_dir.mkdir(parents=True, exist_ok=True)

            materialized_images = []
            for idx, img in enumerate(selected_images, start=1):
                target = video_images_dir / f"{idx:05d}{img.suffix.lower()}"
                try:
                    target.symlink_to(img.resolve())
                except OSError as e:
                    if e.errno in (
                        errno.EPERM,
                        errno.EACCES,
                        getattr(errno, 'EOPNOTSUPP', ENOTSUP_FALLBACK),
                        getattr(errno, 'ENOTSUP', ENOTSUP_FALLBACK),
                    ):
                        shutil.copy2(img, target)
                    else:
                        raise
                materialized_images.append(target)

            print(f"  Target resolution: {video_width}x{video_height}")
            print(f"  Audio file: {audio_path}")
            print(f"  Output file: {video_path}")
            print(f"  Images available: {len(image_files)} (using {len(materialized_images)} for this render)")
            print(f"  Audio duration: {audio_duration:.2f}s")

            # Images are already pre-processed (blurred background composites cached by resolution)
            processed_images = materialized_images

            # Determine content type from code prefix
            code_prefix = code[0].upper()
            content_type_map = {'L': 'long', 'M': 'medium', 'S': 'short', 'R': 'reels'}
            content_type = content_type_map.get(code_prefix, 'long')
            
            # Select template for this video based on content type
            template_path = None
            
            # Blender templates are only relevant when VIDEO_RENDERER is Blender.
            # When using FFmpeg, skip template selection/validation to avoid misleading warnings.
            if VIDEO_RENDERER == 'blender' and selector and ENABLE_SOCIAL_EFFECTS:
                try:
                    # Get content type settings from config
                    selection_cfg = tpl_cfg.get("selection", {})
                    by_content_type = selection_cfg.get("by_content_type", {}) or {}
                    content_settings = by_content_type.get(content_type, {})
                    
                    strategy = content_settings.get("strategy") or selection_cfg.get("default_strategy", "sequential")
                    candidates = content_settings.get("candidates") or []
                    
                    if candidates:
                        # Initialize rotation counter for this content type if needed
                        rotation_idx.setdefault(content_type, 0)
                        
                        if strategy == "sequential":
                            # Sequential selection: rotate through candidates
                            current_position = rotation_idx[content_type]
                            tpl_id = candidates[current_position % len(candidates)]
                            rotation_idx[content_type] += 1
                            print(f"  Template selection (sequential): {tpl_id} (position {current_position + 1} in {content_type} rotation)")
                        else:
                            # Weighted or auto: use existing selector's stable randomized choice
                            seed_input = f"{topic_id}-{date_str}-{code}"
                            seed = hashlib.sha256(seed_input.encode()).hexdigest()[:12]
                            tpl = selector.select_template(seed=seed, style="auto")
                            tpl_id = tpl["id"] if tpl else None
                            print(f"  Template selection (weighted/auto): {tpl_id}")
                        
                        # Validate and get template path
                        if tpl_id and selector.validate_template(tpl_id):
                            template_path = selector.get_template_path(tpl_id)
                            print(f"  ✓ Template validated: {template_path}")
                        else:
                            print(f"  ⚠ Template validation failed: {tpl_id}")
                    else:
                        print(f"  ⓘ No template candidates configured for content type '{content_type}'")
                    
                    # Apply fallback if no template selected
                    if template_path is None:
                        fallback_none = selection_cfg.get("fallback_to_none", True)
                        fallback_id = selection_cfg.get("fallback_template_id", "minimal")
                        
                        if not fallback_none and selector.validate_template(fallback_id):
                            template_path = selector.get_template_path(fallback_id)
                            print(f"  Using fallback template: {fallback_id}")
                        else:
                            print(f"  No template will be used (fallback_to_none={fallback_none})")
                            
                except Exception as e:
                    print(f"  ⚠ Template selection error: {e}")
                    template_path = None
            elif VIDEO_RENDERER != 'blender':
                print(f"  Template selection skipped (renderer={VIDEO_RENDERER})")
            elif not ENABLE_SOCIAL_EFFECTS:
                print(f"  Social effects disabled (ENABLE_SOCIAL_EFFECTS=False)")
            else:
                print(f"  Template selector not available")
            
            # Choose renderer based on configuration
            rendered = False
            renderer_used = None
            
            if VIDEO_RENDERER == 'blender':
                # Try Blender first
                print(f"  Attempting Blender renderer...")
                try:
                    rendered = render_with_blender(video_images_dir, audio_path, video_path, content_type,
                                                   seed=None, audio_duration=audio_duration, template_path=template_path)
                    if rendered:
                        renderer_used = 'blender'
                        # Update video_path to reflect the actual Blender output path (.blender.mp4)
                        video_path = get_blender_output_path(video_path)
                        print(f"  ✓ Rendered with Blender")

                        # Ensure an image-title timeline sidecar exists for the Blender output,
                        # so post-processing can burn top-of-screen titles deterministically.
                        try:
                            per_img = float(os.environ.get("BLENDER_IMAGE_DURATION_SEC", "5.0"))
                            title_map = _load_image_title_map(materialized_images)
                            segs: List[Dict[str, Any]] = []
                            t0 = 0.0
                            for idx_img, img in enumerate(materialized_images):
                                start = t0
                                end = min(audio_duration, t0 + per_img)
                                if end <= start:
                                    break

                                title = title_map.get(Path(img).name, "").strip()
                                if not title:
                                    try:
                                        title = title_map.get(Path(img).resolve().name, "").strip()
                                    except Exception:
                                        title = ""

                                if title:
                                    segs.append(
                                        {
                                            "start": round(float(start), 3),
                                            "end": round(float(end), 3),
                                            "text": title,
                                            "filename": Path(img).name,
                                            "index": int(idx_img),
                                        }
                                    )
                                t0 += per_img
                                if t0 >= audio_duration:
                                    break

                            _write_image_titles_sidecar(video_path, segs)
                        except Exception:
                            pass

                        # Burn captions/titles/frame overlays for Blender output (in-place).
                        if not maybe_burn_captions(audio_path=audio_path, video_path=video_path):
                            print("  ✗ Overlay burn-in failed for Blender output")
                            rendered = False

                except Exception as e:
                    print(f"  ✗ Blender rendering failed: {e}")
                    rendered = False
                
                # Fallback to FFmpeg if Blender fails
                if not rendered:
                    # Guard: Check if a good video already exists before overwriting
                    blender_video_path = get_blender_output_path(video_path)
                    
                    # Check both output paths for existing good video
                    blender_guard_size = get_safe_file_size(blender_video_path)
                    final_guard_size = get_safe_file_size(video_path)
                    
                    if blender_guard_size and blender_guard_size > MIN_FALLBACK_GUARD_SIZE_BYTES:
                        print(f"  ⚠ Blender output already exists ({blender_guard_size / (1024*1024):.2f} MB)")
                        print(f"  ⓘ Skipping FFmpeg fallback to avoid overwriting good video")
                        rendered = True
                        renderer_used = 'blender'
                        video_path = blender_video_path
                    elif final_guard_size and final_guard_size > MIN_FALLBACK_GUARD_SIZE_BYTES:
                        print(f"  ⚠ Final output already exists ({final_guard_size / (1024*1024):.2f} MB)")
                        print(f"  ⓘ Skipping FFmpeg fallback to avoid overwriting good video")
                        rendered = True
                        renderer_used = 'blender'
                    else:
                        print(f"  Falling back to FFmpeg renderer...")
                        video_config = config.copy()
                        video_config['video_width'] = video_width
                        video_config['video_height'] = video_height
                        
                        try:
                            # Pass video_duration for video-only mode, audio_path for muxing mode
                            rendered = create_video_from_images(
                                processed_images, 
                                audio_path if ENABLE_VIDEO_AUDIO_MUX else None,
                                video_path, 
                                video_config, 
                                chapters, 
                                content_code=code, 
                                script_path=None,
                                video_duration=audio_duration
                            )
                            if rendered:
                                renderer_used = 'ffmpeg'
                                print(f"  ✓ Rendered with FFmpeg (fallback)")
                        except Exception as e:
                            print(f"  ✗ FFmpeg rendering failed: {e}")
                            rendered = False
            
            elif VIDEO_RENDERER == 'ffmpeg':
                # Use FFmpeg directly (no Blender attempt)
                print(f"  Attempting FFmpeg renderer...")
                video_config = config.copy()
                video_config['video_width'] = video_width
                video_config['video_height'] = video_height
                
                try:
                    # Pass video_duration for video-only mode, audio_path for muxing mode
                    rendered = create_video_from_images(
                        processed_images, 
                        audio_path if ENABLE_VIDEO_AUDIO_MUX else None,
                        video_path, 
                        video_config, 
                        chapters, 
                        content_code=code, 
                        script_path=None,
                        video_duration=audio_duration
                    )
                    if rendered:
                        renderer_used = 'ffmpeg'
                        print(f"  ✓ Rendered with FFmpeg")
                except Exception as e:
                    print(f"  ✗ FFmpeg rendering failed: {e}")
                    rendered = False
            
            if rendered:
                # Validate Blender output if available and Blender was used
                if renderer_used == 'blender':
                    try:
                        from output_validator import validate_video_output
                        is_valid, report = validate_video_output(video_path, content_type)
                        if not is_valid:
                            print(f"  ⚠ Warning: Output validation failed")
                            for error in report.get('errors', []):
                                print(f"    - {error}")
                    except ImportError:
                        pass  # Validator not available, skip validation
                
                print(f"  ✓ Generated: {video_path.name} (using {renderer_used})")
                success_count += 1
            else:
                print(f"  ✗ Failed to render video with any available renderer")
                fail_count += 1
                
        except Exception as e:
            print(f"  ✗ Unexpected error rendering {code}: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1
        finally:
            if video_images_dir and video_images_dir.exists():
                try:
                    shutil.rmtree(video_images_dir)
                except (FileNotFoundError, PermissionError):
                    pass
    
    # Step 4: Clean up images
    print(f"\nStep 4: Cleaning up images...")
    cleanup_images(output_dir)
    
    print(f"\n{'='*60}")
    print(f"Video Rendering Summary:")
    print(f"  Success: {success_count}/{len(audio_jobs)}")
    print(f"  Failed: {fail_count}/{len(audio_jobs)}")
    if fail_count > 0 and success_count > 0:
        print(f"  Note: Some items failed to render, but at least one video was generated.")
    print(f"{'='*60}")

    # CI should only fail if we generated *zero* videos for the enabled content types.
    # Individual item failures are reported above but should not stop the pipeline.
    return success_count > 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Render podcast video')
    parser.add_argument('--topic', required=True, help='Topic ID')
    parser.add_argument('--date', help='Date string (YYYYMMDD)')
    args = parser.parse_args()
    
    success = render_for_topic(args.topic, args.date)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
