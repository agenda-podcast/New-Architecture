#!/usr/bin/env python3
"""
Blender video builder script.

This script runs inside Blender (headless mode) to generate videos
from images and audio with cinematic effects.

Usage:
    blender --background --python build_video.py -- \
        --images path/to/images \
        --audio path/to/audio.m4a \
        --output path/to/output.mp4 \
        --profile long \
        --template path/to/template.blend \
        --seed abc123
"""
import sys
import argparse
import copy
import json
import hashlib
import math
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Blender imports (only available when running inside Blender)
try:
    import bpy
    import bpy.types
    BLENDER_AVAILABLE = True
except ImportError:
    BLENDER_AVAILABLE = False
    print("Warning: Blender Python API not available. This script must run inside Blender.")

# Translation mappings from FFmpeg CLI names to Blender enum values
BLENDER_CONTAINER_MAP = {
    "mp4": "MPEG4",       # Blender "MPEG-4"
    "mov": "QUICKTIME",
    "mkv": "MATROSKA",
    "webm": "WEBM",
    "ogg": "OGG",
}

BLENDER_CODEC_MAP = {
    "libx264": "H264",    # Blender "H.264"
    "h264": "H264",
    "mpeg4": "MPEG4",
    "theora": "THEORA",
    "vp9": "VP9",
    "libvpx-vp9": "VP9",
    "vp8": "VP8",
    "libvpx": "VP8",
    "png": "PNG",
}

# Blender presets are (commonly) Slowest / Good / Realtime
BLENDER_PRESET_MAP = {
    "veryslow": "SLOWEST",
    "slow": "SLOWEST",
    "slower": "SLOWEST",
    "medium": "GOOD",
    "fast": "REALTIME",
    "faster": "REALTIME",
    "veryfast": "REALTIME",
    "superfast": "REALTIME",
    "ultrafast": "REALTIME",
}

# Regex pattern for parsing bitrate values (e.g., "10M", "10m", "8000k", "5000")
# Supports optional 'b' suffix (e.g., "10Mb", "8000kb")
# Input is converted to lowercase before matching, so both "10M" and "10m" are accepted
BITRATE_PATTERN = r"^(\d+(?:\.\d+)?)([km]?)b?$"


def _parse_rate_to_kbps(val: str) -> int:
    """
    Parse bitrate value to kbps for Blender.
    Supports formats like "10M", "10Mb", "8000k", "8000kb", "5000" (kbps assumed if no unit).
    Case-insensitive for units.
    
    Args:
        val: Bitrate value as string
        
    Returns:
        Bitrate in kbps
        
    Raises:
        ValueError: If format is unrecognized
    """
    s = str(val).strip().lower()
    m = re.match(BITRATE_PATTERN, s)
    if not m:
        raise ValueError(f"Unrecognized bitrate value: {val}")
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "m":
        return int(num * 1000)
    if unit == "k":
        return int(num)
    # Assume kbps if no unit
    return int(num)


def _crf_to_blender_enum(crf: int) -> str:
    """
    Convert numeric CRF value to Blender's CRF quality enum.
    Based on Blender's CRF buckets mapping (Medium≈23, High≈20, etc.).
    
    Args:
        crf: Numeric CRF value (0-51, lower is better quality)
        
    Returns:
        Blender CRF enum string
    """
    if crf <= 0:
        return "LOSSLESS"
    if crf <= 17:
        return "PERC_LOSSLESS"
    if crf <= 20:
        return "HIGH"
    if crf <= 23:
        return "MEDIUM"
    if crf <= 26:
        return "LOW"
    if crf <= 29:
        return "VERYLOW"
    return "LOWEST"


DEFAULT_OUTPUT_PROFILES: Dict[str, Any] = {
    "long": {
        "description": "Full deep dive podcast - Desktop/TV viewing",
        "resolution": {"width": 1920, "height": 1080},
        "aspect_ratio": "16:9",
        "fps": 30,
        "color_space": "sRGB",
        "audio_policy": {"codec": "aac", "bitrate": "128k", "sample_rate": 44100, "channels": 2},
        "bitrate_policy": {"target": "10M", "max": "12M", "buffer": "24M"},
        "container": "mp4",
        "codec": {
            "name": "libx264",
            "profile": "high",
            "preset": "medium",
            "crf": 23,
            "keyframe_interval": 60,
            "pix_fmt": "yuv420p",
        },
        "validation": {"min_duration": 600, "max_duration": 3600},
    },
    "medium": {
        "description": "Focused segment - Desktop/TV viewing",
        "resolution": {"width": 1920, "height": 1080},
        "aspect_ratio": "16:9",
        "fps": 30,
        "color_space": "sRGB",
        "audio_policy": {"codec": "aac", "bitrate": "128k", "sample_rate": 44100, "channels": 2},
        "bitrate_policy": {"target": "10M", "max": "12M", "buffer": "24M"},
        "container": "mp4",
        "codec": {
            "name": "libx264",
            "profile": "high",
            "preset": "medium",
            "crf": 23,
            "keyframe_interval": 60,
            "pix_fmt": "yuv420p",
        },
        "validation": {"min_duration": 300, "max_duration": 1200},
    },
    "short": {
        "description": "Quick update - Mobile/social media",
        "resolution": {"width": 1080, "height": 1920},
        "aspect_ratio": "9:16",
        "fps": 30,
        "color_space": "sRGB",
        "audio_policy": {"codec": "aac", "bitrate": "128k", "sample_rate": 44100, "channels": 2},
        "bitrate_policy": {"target": "8M", "max": "10M", "buffer": "20M"},
        "container": "mp4",
        "codec": {
            "name": "libx264",
            "profile": "high",
            "preset": "medium",
            "crf": 23,
            "keyframe_interval": 60,
            "pix_fmt": "yuv420p",
        },
        "validation": {"min_duration": 120, "max_duration": 600},
    },
    "reels": {
        "description": "Social media clip - Instagram/TikTok/YouTube Shorts",
        "resolution": {"width": 1080, "height": 1920},
        "aspect_ratio": "9:16",
        "fps": 30,
        "color_space": "sRGB",
        "audio_policy": {"codec": "aac", "bitrate": "128k", "sample_rate": 44100, "channels": 2},
        "bitrate_policy": {"target": "8M", "max": "10M", "buffer": "20M"},
        "container": "mp4",
        "codec": {
            "name": "libx264",
            "profile": "high",
            "preset": "medium",
            "crf": 23,
            "keyframe_interval": 60,
            "pix_fmt": "yuv420p",
        },
        "validation": {"min_duration": 15, "max_duration": 90},
    },
    "master": {
        "description": "High-bitrate mezzanine format for re-encoding",
        "resolution": {"width": 1920, "height": 1080},
        "aspect_ratio": "16:9",
        "fps": 30,
        "color_space": "sRGB",
        "audio_policy": {"codec": "pcm_s16le", "sample_rate": 48000, "channels": 2},
        "bitrate_policy": {"target": "50M", "max": "100M", "buffer": "200M"},
        "container": "mov",
        "codec": {"name": "prores_ks", "profile": "standard", "pix_fmt": "yuv422p10le"},
        "validation": {"min_duration": 0, "max_duration": 7200},
    },
}


class BlenderVideoBuilder:
    """
    Video builder using Blender VSE and Compositor.
    """
    
    def __init__(self, output_profile: Dict[str, Any], seed: str):
        """
        Initialize video builder.
        
        Args:
            output_profile: Output profile from output_profiles.yml
            seed: Random seed for deterministic effects
        """
        self.profile = output_profile
        self.seed = seed
        self.manifest = {
            'seed': seed,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'blender_version': bpy.app.version_string if BLENDER_AVAILABLE else 'unknown',
            'effects': []
        }
    
    def load_template(self, template_path: Path) -> bool:
        """
        Load Blender template file.
        
        Args:
            template_path: Path to .blend template file
            
        Returns:
            True if successful
        """
        if not template_path.exists():
            print(f"Error: Template not found: {template_path}")
            return False
        
        try:
            # Load template blend file
            bpy.ops.wm.open_mainfile(filepath=str(template_path))
            print(f"Loaded template: {template_path}")
            
            self.manifest['template'] = {
                'path': str(template_path),
                'name': template_path.stem
            }
            
            return True
        except Exception as e:
            print(f"Error loading template: {e}")
            return False
    
    def configure_scene(self, video_only: bool = False) -> None:
        """
        Configure scene settings from output profile.
        Settings include resolution, FPS, color space, etc.
        
        Args:
            video_only: If True, disable audio encoding (video-only output)
        """
        scene = bpy.context.scene
        
        # Set resolution from profile
        width = self.profile['resolution']['width']
        height = self.profile['resolution']['height']
        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = 100
        
        print(f"Configured resolution: {width}x{height}")
        
        # Set FPS
        fps = self.profile['fps']
        scene.render.fps = fps
        scene.render.fps_base = 1.0
        
        print(f"Configured FPS: {fps}")
        
        # Set color management
        scene.view_settings.view_transform = 'Standard'
        scene.sequencer_colorspace_settings.name = 'sRGB'
        
        # Configure render output
        scene.render.image_settings.file_format = 'FFMPEG'
        
        # Translate container and codec from FFmpeg CLI names to Blender enums
        container = (self.profile.get("container") or "").lower()
        codec_name = (self.profile.get("codec", {}).get("name") or "").lower()
        
        blender_format = BLENDER_CONTAINER_MAP.get(container)
        blender_codec = BLENDER_CODEC_MAP.get(codec_name)
        if not blender_format:
            raise ValueError(f"Unsupported container for Blender: {container}")
        if not blender_codec:
            raise ValueError(f"Unsupported codec for Blender: {codec_name}")
        
        scene.render.ffmpeg.format = blender_format
        scene.render.ffmpeg.codec = blender_codec
        
        # Ensure sequencer output is used (we're building in VSE)
        scene.render.use_sequencer = True
        
        # Set video codec options
        codec_settings = self.profile['codec']
        
        # Convert CRF from numeric value to Blender enum
        crf = int(codec_settings.get("crf", 23))
        scene.render.ffmpeg.constant_rate_factor = _crf_to_blender_enum(crf)
        
        # Convert preset from FFmpeg name to Blender enum
        preset = str(codec_settings.get("preset", "medium")).lower()
        scene.render.ffmpeg.ffmpeg_preset = BLENDER_PRESET_MAP.get(preset, "GOOD")
        
        scene.render.ffmpeg.gopsize = codec_settings.get('keyframe_interval', 60)
        
        # Apply bitrate policy if present (values in kbps for Blender fields)
        bp = self.profile.get("bitrate_policy") or {}
        if "target" in bp:
            scene.render.ffmpeg.video_bitrate = _parse_rate_to_kbps(bp["target"])
        if "max" in bp:
            scene.render.ffmpeg.maxrate = _parse_rate_to_kbps(bp["max"])
        if "buffer" in bp:
            scene.render.ffmpeg.buffersize = _parse_rate_to_kbps(bp["buffer"])
        
        # Set audio codec - disable for video-only rendering
        if video_only:
            # Disable audio encoding entirely for video-only output
            scene.render.ffmpeg.audio_codec = 'NONE'
            print(f"Configured codecs: video={blender_codec} (from {codec_name}), audio=NONE (video-only)")
        else:
            # Configure audio encoding from profile
            audio_settings = self.profile.get('audio_policy')
            if not audio_settings:
                raise ValueError("Profile must contain 'audio_policy' for audio rendering")
            
            scene.render.ffmpeg.audio_codec = audio_settings['codec'].upper()
            scene.render.ffmpeg.audio_bitrate = int(audio_settings['bitrate'].replace('k', ''))
            scene.render.ffmpeg.audio_mixrate = audio_settings['sample_rate']
            scene.render.ffmpeg.audio_channels = 'STEREO' if audio_settings['channels'] == 2 else 'MONO'
            print(f"Configured codecs: video={blender_codec} (from {codec_name}), audio={audio_settings['codec']}")
    
    def load_images_to_vse(self, images: List[Path], image_duration: float = 5.0) -> bool:
        """
        Load images into Video Sequence Editor.
        
        Args:
            images: List of image file paths
            image_duration: Duration per image in seconds
            
        Returns:
            True if successful
        """
        if not images:
            print("Error: No images provided")
            return False
        
        scene = bpy.context.scene
        seq_editor = scene.sequence_editor
        
        if not seq_editor:
            seq_editor = scene.sequence_editor_create()
        
        fps = scene.render.fps
        frame_duration = int(image_duration * fps)
        
        current_frame = 1
        
        for i, image_path in enumerate(images):
            try:
                # Add image as image sequence strip
                strip = seq_editor.sequences.new_image(
                    name=f"Image_{i:03d}",
                    filepath=str(image_path),
                    channel=1,
                    frame_start=current_frame
                )
                
                # Set strip duration
                strip.frame_final_duration = frame_duration
                
                # Scale and position image to fit frame
                strip.transform.scale_x = 1.0
                strip.transform.scale_y = 1.0
                
                current_frame += frame_duration
                
            except Exception as e:
                print(f"Warning: Failed to load image {image_path}: {e}")
                continue
        
        print(f"Loaded {len(images)} images to VSE")
        return True
    
    def load_audio_to_vse(self, audio_path: Path, duration_frames: Optional[int] = None) -> bool:
        """
        Load audio file into Video Sequence Editor.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            True if successful
        """
        if not audio_path.exists():
            print(f"Error: Audio file not found: {audio_path}")
            return False
        
        scene = bpy.context.scene
        seq_editor = scene.sequence_editor
        
        if not seq_editor:
            seq_editor = scene.sequence_editor_create()
        
        try:
            # Add audio strip
            audio_strip = seq_editor.sequences.new_sound(
                name="Audio",
                filepath=str(audio_path),
                channel=2,
                frame_start=1
            )
            
            # Set scene end frame to match audio duration
            audio_duration_frames = audio_strip.frame_final_duration
            target_frames = duration_frames if duration_frames is not None else audio_duration_frames
            scene.frame_end = target_frames
            
            print(f"Loaded audio: {audio_path}")
            print(f"Audio duration (frames): {audio_duration_frames}")
            print(f"Timeline frames set to: {target_frames} ({target_frames / scene.render.fps:.2f}s)")
            
            return True
            
        except Exception as e:
            print(f"Error loading audio: {e}")
            return False
    
    def apply_template_effects(self) -> None:
        """
        Apply effects from template (compositor nodes).
        Effects are configured in the template but can be
        adjusted based on seed for controlled randomness.
        """
        # Check if compositor is enabled
        scene = bpy.context.scene
        scene.use_nodes = True
        
        print("Template effects ready (configured in template)")
        
        # In the future, this function can:
        # - Unmute specific effect nodes based on template config
        # - Adjust effect intensities based on seed
        # - Apply random variations within intensity ranges
    
    def render_video(self, output_path: Path) -> bool:
        """
        Render video to output file.
        
        Args:
            output_path: Path to output video file
            
        Returns:
            True if successful
        """
        scene = bpy.context.scene
        
        # Ensure output directory exists and control whether Blender appends its own extension
        output_path.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(output_path)
        # If the caller provided an explicit filename (with extension), avoid Blender adding another extension.
        # Otherwise, allow Blender to append the appropriate extension for the selected container.
        scene.render.use_file_extension = not bool(output_path.suffix)
        
        # Diagnostic output: Print actual Blender render settings
        print(f"\n=== BLENDER RENDER SETTINGS DIAGNOSTIC ===")
        print(f"BLENDER_RENDER_FILEPATH = {scene.render.filepath}")
        print(f"BLENDER_FILE_FORMAT = {scene.render.image_settings.file_format}")
        print(f"BLENDER_USE_FILE_EXT = {scene.render.use_file_extension}")
        print(f"BLENDER_FFMPEG_FORMAT = {scene.render.ffmpeg.format}")
        print(f"BLENDER_FFMPEG_CODEC = {scene.render.ffmpeg.codec}")
        print(f"BLENDER_FFMPEG_AUDIO_CODEC = {scene.render.ffmpeg.audio_codec}")
        print(f"=== END DIAGNOSTIC ===\n")
        
        print(f"\nRendering video to: {output_path}")
        print(f"  Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
        print(f"  FPS: {scene.render.fps}")
        print(f"  Duration: {scene.frame_end} frames ({scene.frame_end / scene.render.fps:.2f}s)")
        print(f"  Codec: {scene.render.ffmpeg.codec}")
        print()
        
        start_time = datetime.now()
        
        try:
            # Render animation
            bpy.ops.render.render(animation=True, write_still=False)
            
            end_time = datetime.now()
            render_time = (end_time - start_time).total_seconds()
            
            print(f"\nRender complete in {render_time:.1f}s")
            
            self.manifest['render_time'] = render_time
            
            return True
            
        except Exception as e:
            print(f"\nError during render: {e}")
            return False
    
    def save_manifest(self, output_path: Path) -> None:
        """
        Save render manifest as JSON.
        
        Args:
            output_path: Path to video file (manifest will be .json)
        """
        manifest_path = output_path.with_suffix('.manifest.json')
        
        # Add final metadata
        self.manifest['video_path'] = str(output_path)
        self.manifest['resolution'] = f"{self.profile['resolution']['width']}x{self.profile['resolution']['height']}"
        self.manifest['fps'] = self.profile['fps']
        
        scene = bpy.context.scene
        self.manifest['duration'] = scene.frame_end / scene.render.fps
        
        with open(manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)
        
        print(f"Saved manifest: {manifest_path}")


def load_output_profile(profile_name: str) -> Optional[Dict[str, Any]]:
    """
    Load output profile from config/output_profiles.yml.
    
    Args:
        profile_name: Profile name (long, medium, short, reels)
        
    Returns:
        Profile dictionary or None if not found
    """
    # Find config directory (relative to this script)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    config_path = repo_root / 'config' / 'output_profiles.yml'
    
    profiles: Dict[str, Any] = {}
    
    try:
        import yaml
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            profiles = config.get('profiles', {})
        else:
            print(f"Error: Output profiles not found: {config_path}")
    except ModuleNotFoundError:
        print("PyYAML not available in Blender runtime; using bundled output profiles.")
    except Exception as e:
        print(f"Error loading output profiles: {e}")
    
    if not profiles:
        profiles = DEFAULT_OUTPUT_PROFILES
    
    profile = profiles.get(profile_name)
    
    if not profile:
        print(f"Error: Profile '{profile_name}' not found")
        print(f"Available profiles: {list(profiles.keys())}")
        return None
    
    return copy.deepcopy(profile)


def discover_images(images_dir: Path) -> List[Path]:
    """
    Discover all image files in directory.
    
    Args:
        images_dir: Directory containing images
        
    Returns:
        List of image paths, sorted by filename
    """
    if not images_dir.exists():
        print(f"Error: Images directory not found: {images_dir}")
        return []
    
    # Supported image formats
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
    
    images = []
    for ext in extensions:
        images.extend(images_dir.glob(f'*{ext}'))
        images.extend(images_dir.glob(f'*{ext.upper()}'))
    
    # Sort by filename
    images = sorted(images, key=lambda p: p.name)
    
    return images


def generate_seed(topic_id: str, date_str: str, content_code: str) -> str:
    """
    Generate deterministic seed from topic metadata.
    
    Args:
        topic_id: Topic ID (e.g., 'topic-01')
        date_str: Date string (YYYYMMDD)
        content_code: Content code (e.g., 'L1', 'M2')
        
    Returns:
        Hex seed string
    """
    seed_input = f"{topic_id}-{date_str}-{content_code}"
    seed_hash = hashlib.sha256(seed_input.encode()).hexdigest()
    return seed_hash[:12]  # Use first 12 characters


def main():
    """
    Main entry point for Blender video builder.
    
    This function parses command-line arguments and orchestrates
    the video building process.
    """
    # Parse arguments after '--' separator
    argv = sys.argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    else:
        argv = []
    
    parser = argparse.ArgumentParser(description='Build video using Blender')
    parser.add_argument('--images', required=True, help='Path to images directory')
    parser.add_argument('--audio', required=True, help='Path to audio file')
    parser.add_argument('--output', required=True, help='Path to output video file')
    parser.add_argument('--profile', required=True, 
                       choices=['long', 'medium', 'short', 'reels', 'master'],
                       help='Output profile')
    parser.add_argument('--template', help='Path to Blender template file (optional)')
    parser.add_argument('--seed', help='Random seed (optional, auto-generated if not provided)')
    parser.add_argument('--duration', type=float,
                       help='Audio duration in seconds (used to set frame_end)')
    parser.add_argument('--no-audio', action='store_true',
                       help='Skip loading audio into Blender (video-only output)')
    
    args = parser.parse_args(argv)
    
    if args.no_audio and not args.duration:
        print("Error: --no-audio requires --duration to set timeline length. Use --duration <seconds> to specify the video length.")
        return 1
    
    # Check Blender availability
    if not BLENDER_AVAILABLE:
        print("Error: This script must be run inside Blender")
        print("Usage: blender --background --python build_video.py -- [args]")
        return 1
    
    # Convert paths
    images_dir = Path(args.images)
    audio_path = Path(args.audio)
    output_path = Path(args.output)
    
    # Load output profile
    print(f"Loading output profile: {args.profile}")
    profile = load_output_profile(args.profile)
    if not profile:
        return 1
    
    # Generate seed if not provided
    seed = args.seed
    if not seed:
        # Try to extract metadata from paths for seed generation
        # For now, use a simple timestamp-based seed
        seed = hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:12]
    
    print(f"Using seed: {seed}")
    
    # Discover images
    print(f"Discovering images in: {images_dir}")
    images = discover_images(images_dir)
    if not images:
        print("Error: No images found")
        return 1
    print(f"Found {len(images)} images")
    
    # Initialize builder
    builder = BlenderVideoBuilder(profile, seed)
    
    # Load template if provided
    if args.template:
        template_path = Path(args.template)
        if not builder.load_template(template_path):
            return 1
    else:
        print("No template specified, using default scene")
    
    # Configure scene from profile
    print("Configuring scene from output profile...")
    builder.configure_scene(video_only=args.no_audio)
    
    # Set deterministic frame range from provided duration (if any)
    duration_frames = None
    if args.duration:
        duration_frames = math.ceil(args.duration * profile['fps'])
        scene = bpy.context.scene
        scene.frame_start = 1
        scene.frame_end = duration_frames
        print(f"Timeline set from duration: {duration_frames} frames ({args.duration:.2f}s)")
    
    # Load images to VSE
    print("Loading images to Video Sequence Editor...")
    if not builder.load_images_to_vse(images):
        return 1
    
    if not args.no_audio:
        # Load audio to VSE
        print("Loading audio to Video Sequence Editor...")
        if not builder.load_audio_to_vse(audio_path, duration_frames):
            return 1
    else:
        print("Skipping audio load (video-only render)")
    
    # Apply template effects
    print("Applying template effects...")
    builder.apply_template_effects()
    
    # Render video
    if not builder.render_video(output_path):
        return 1
    
    # Save manifest
    builder.save_manifest(output_path)
    
    print("\nVideo build complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
