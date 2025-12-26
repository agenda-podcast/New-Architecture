"""
Global configuration for podcast maker system.
Contains all constants and shared settings used across scripts.
"""

import os
from pathlib import Path


# ============================================================================
# ChatGPT / Script Generation Settings
# ============================================================================

# Testing Configuration
TESTING_MODE = False  # When True, use saved mock responses instead of calling OpenAI API

# Resolve repo-rooted paths robustly (GitHub Actions may run scripts from ./scripts, so relative paths break)
REPO_ROOT = Path(os.environ.get('GITHUB_WORKSPACE', Path(__file__).resolve().parents[1])).resolve()
MOCK_RESPONSES_DIR = str(REPO_ROOT / 'test_data' / 'mock_responses')  # Directory for saved API responses
MOCK_SOURCE_TEXT_DIR = str(REPO_ROOT / 'test_data' / 'mock_source_text')  # Directory for Pass-B source text fallback files

# OpenAI Model Configuration
GPT_MODEL = "gpt-5.2-pro"  # Model for Pass A in two-pass architecture (with web search)
MAX_COMPLETION_TOKENS = 1000000  # Maximum tokens per API response

# DEPRECATED: The following constants are kept for backwards compatibility but are no longer used
# in the two-pass architecture. They will be removed in a future version.
MAX_CONTINUATION_ATTEMPTS = 100  # DEPRECATED - Two-pass architecture replaced continuation logic

# Script Generation Prompts
# DEPRECATED: The following marker is kept for backwards compatibility but is no longer used
# in the two-pass architecture. It will be removed in a future version.
END_OF_TOPIC_MARKER = "End of Topic"  # DEPRECATED - Two-pass architecture does not use markers

# OpenAI API Endpoint Configuration
# Maps model names to their appropriate API endpoints
# - Chat models (gpt-3.5-turbo, gpt-4, etc.) use /v1/chat/completions
# - Responses models (gpt-5.2-pro, etc.) use /v1/responses
OPENAI_MODEL_ENDPOINTS = {
    "gpt-3.5-turbo": "chat",
    "gpt-3.5-turbo-16k": "chat",
    "gpt-4": "chat",
    "gpt-4-turbo": "chat",
    "gpt-4-turbo-preview": "chat",
    "gpt-4o": "chat",
    "gpt-4o-mini": "chat",
    "gpt-4.1-nano": "responses",  # Uses /v1/responses endpoint (Responses API-only)
    # GPT-5 family uses the Responses API
    "gpt-5-nano": "responses",
    "gpt-5-mini": "responses",
    "gpt-5": "responses",
    "gpt-5.2-nano": "responses",  # Uses /v1/responses endpoint (Responses API-only)
    "gpt-5.2-pro": "responses",  # Uses /v1/responses endpoint (Responses API-only)
}

def get_openai_endpoint_type(model: str) -> str:
    """
    Get the OpenAI API endpoint type for a given model.
    
    Args:
        model: Model name (e.g., "gpt-5.2-pro", "gpt-4")
        
    Returns:
        "chat" for chat completion models, "responses" for responses models,
        or "completion" for legacy completion models.
        Defaults to "chat" for unknown models
    """
    return OPENAI_MODEL_ENDPOINTS.get(model, "chat")

# Article Fetching Configuration (DEPRECATED - removed in architecture v2)
# The new architecture uses OpenAI's web_search tool directly instead of pre-fetching articles

# ============================================================================
# Source Collection Settings (DEPRECATED - removed in architecture v2)
# ============================================================================
# The new architecture uses OpenAI's web_search tool which handles source discovery
# and validation internally. No pre-collection or trusted domain validation needed.

# Content Type Specifications
# NOTE: Only target_words should be used for generation. 
# Duration is computed internally but not exposed to prompts.
CONTENT_TYPES = {
    'long': {
        'count': 1,
        'target_words': 10000,  # Full deep dive content (~40-45 minute podcast)
        'code_prefix': 'L',
        'description': 'Full deep dive',
        'include_intro_outro': True,
        'video_format': 'horizontal'  # Desktop/TV viewing
    },
    'medium': {
        'count': 2,
        'target_words': 2500,
        'code_prefix': 'M',
        'description': 'Focused segments',
        'include_intro_outro': True,
        'video_format': 'horizontal'  # Desktop/TV viewing
    },
    'short': {
        'count': 4,
        'target_words': 1000,
        'code_prefix': 'S',
        'description': 'Quick updates',
        'include_intro_outro': False,
        'video_format': 'vertical'  # Mobile/social media
    },
    'reels': {
        'count': 8,
        'target_words': 80,
        'code_prefix': 'R',
        'description': 'Social media clips',
        'include_intro_outro': False,
        'video_format': 'vertical'  # Mobile/social media
    }
}

# ============================================================================
# TTS (Text-to-Speech) Settings
# ============================================================================

# TTS Provider Settings
TTS_CACHE_ENABLED = False  # Enable caching of TTS outputs
TTS_SAMPLE_RATE = 44100  # Sample rate for audio output (44.1 kHz)
TTS_AUDIO_CODEC = 'aac'  # Audio codec: AAC
TTS_AUDIO_BITRATE = '128k'  # Bitrate: 128 kbps stereo

# Piper TTS Settings (Local)
PIPER_VOICE_DIR = "~/.local/share/piper-tts/voices/"  # Voice model storage location

# TTS Chunking Configuration (for long-form audio generation)
TTS_USE_CHUNKING = False  # Default: Use single run per content type (False), or use chunking logic (True)
TTS_MAX_CHARS_PER_CHUNK = 5000  # Maximum characters per chunk (Piper limit ~5000)
TTS_MAX_SENTENCES_PER_CHUNK = 50  # Maximum sentences per chunk
TTS_GAP_MS = 500  # Gap between chunks in milliseconds (0.5 seconds)
TTS_CONCURRENCY = 4  # Number of parallel TTS processes
TTS_RETRY_ATTEMPTS = 3  # Number of retry attempts for failed chunks

# Gender-based Voice Mapping for Piper TTS
# Maps gender to voice model names with quality variants
# Note: Voice names are based on the speaker's name, not gender indicators
#   - ryan: Male voice (Ryan)
#   - lessac: Female voice (Ellen Lessac)
#   - amy: Female voice (Amy)
PIPER_VOICE_MAP = {
    'male': {
        'high': 'en_US-ryan-high',
        'medium': 'en_US-ryan-medium',
        'low': 'en_US-ryan-low',
        'default': 'en_US-ryan-high'  # Default quality for male voice
    },
    'female': {
        'high': 'en_US-lessac-high',  # Ellen Lessac - female voice
        'medium': 'en_US-lessac-medium',
        'low': 'en_US-lessac-low',
        'default': 'en_US-lessac-high'  # Default quality for female voice
    }
}

# Fallback voices if preferred voices are not available
# Note: Fallbacks stay within same gender for voice consistency
PIPER_VOICE_FALLBACKS = {
    'male': ['en_US-ryan-high', 'en_US-ryan-medium', 'en_US-ryan-low'],
    'female': ['en_US-lessac-high', 'en_US-lessac-medium', 'en_US-lessac-low', 'en_US-amy-medium']
}

# Google Cloud TTS Settings (Premium)
GOOGLE_TTS_SAMPLE_RATE = 44100  # 44.1 kHz
GOOGLE_TTS_LANGUAGE_CODE = "en-US"

# Google Cloud TTS Gender-based Voice Mapping
GOOGLE_VOICE_MAP = {
    'male': 'en-US-Journey-D',
    'female': 'en-US-Journey-F'
}

# ============================================================================
# Image Collection Settings (DEPRECATED - removed in architecture v2)
# ============================================================================
# Images are no longer pre-collected. Video generation uses fallback visuals.
# Image Display Settings (kept for video rendering fallback)
IMAGE_TRANSITION_MIN_SEC = 3  # Minimum seconds to display each image
IMAGE_TRANSITION_MAX_SEC = 8  # Maximum seconds to display each image
# Note: Images cycle through randomly with variable timing (3-8 seconds per image)

# Google Custom Search API Settings
GOOGLE_SEARCH_DAILY_LIMIT = 1000  # Maximum API results per day (up to 1000)
GOOGLE_SEARCH_MAX_RESULTS_PER_QUERY = 100  # Maximum results per query (API limit)
GOOGLE_SEARCH_RESULTS_PER_PAGE = 10  # Results per page (API hard limit)

# ============================================================================
# Video Rendering Settings
# ============================================================================

# Video Resolution Configurations
VIDEO_RESOLUTIONS = {
    'horizontal': {
        'width': 1920,
        'height': 1080,
        'description': 'Horizontal format for desktop/TV viewing'
    },
    'vertical': {
        'width': 1080,
        'height': 1920,
        'description': 'Vertical format for mobile (Instagram, TikTok, YouTube Shorts)'
    }
}

# Default video settings (horizontal format for backward compatibility)
VIDEO_WIDTH = VIDEO_RESOLUTIONS['horizontal']['width']
VIDEO_HEIGHT = VIDEO_RESOLUTIONS['horizontal']['height']
VIDEO_FPS = 30  # Frames per second

# Video codec and encoding settings
VIDEO_CODEC = 'libx264'  # H.264 codec
VIDEO_CODEC_PROFILE = 'high'  # H.264 profile: High (applied to all content types for optimal quality)
VIDEO_KEYFRAME_INTERVAL_SEC = 2  # Keyframe interval: 2 seconds (optimal for streaming and seeking)

# Video bitrate settings by content type
VIDEO_BITRATE_SETTINGS = {
    'horizontal': {  # Long and Medium (16:9, 1920x1080, 30fps)
        'bitrate': '10M',  # 8-12 Mbps range, using 10M as middle value
        'maxrate': '12M',
        'bufsize': '24M'
    },
    'vertical': {  # Short and Reels (9:16, 1080x1920, 30fps)
        'bitrate': '8M',  # 6-10 Mbps range, using 8M for good quality
        'maxrate': '10M',
        'bufsize': '20M'
    }
}

# Video Renderer Selection
# Options: 'ffmpeg' (legacy, direct FFmpeg composition) or 'blender' (Blender VSE with FFmpeg encoder)
# Can be overridden with VIDEO_RENDERER environment variable
import os
VIDEO_RENDERER = os.environ.get('VIDEO_RENDERER', 'blender')  # Default to FFmpeg for backward compatibility
# Set VIDEO_RENDERER='blender' environment variable to use Blender 4.5 LTS rendering pipeline

# Social Media Visual Effects (Blender templates)
# Controls whether to apply social media style visual effects using Blender templates
ENABLE_SOCIAL_EFFECTS = os.environ.get('ENABLE_SOCIAL_EFFECTS', 'true').lower() in ('true', '1', 'yes')
# Template selection style options:
#   'auto' - Weighted random selection (60% safe, 30% cinematic, 10% experimental)
#   'none' - Minimal template with no effects
#   'safe' - Professional, subtle effects (clean grade, minimal grain, subtle vignette)
#   'cinematic' - Film-quality effects (noir, golden hour, vintage film, teal & orange)
#   'experimental' - Bold, artistic effects (neon glow, glitch, high contrast)
SOCIAL_EFFECTS_STYLE = os.environ.get('SOCIAL_EFFECTS_STYLE', 'auto')

# FFmpeg Effects Configuration
# Controls whether to use FFmpeg effects mode (Ken Burns + xfade transitions)
# When enabled and VIDEO_RENDERER='ffmpeg', uses advanced filtergraph-based rendering
# Falls back to legacy concat mode if effects pipeline fails
ENABLE_FFMPEG_EFFECTS = os.environ.get('ENABLE_FFMPEG_EFFECTS', 'true').lower() in ('true', '1', 'yes')
FFMPEG_EFFECTS_CONFIG = os.environ.get('FFMPEG_EFFECTS_CONFIG', 'config/video_effects_ffmpeg.yml')

# Burn-in captions/subtitles (FFmpeg only)
# If enabled and a matching .captions.srt file exists next to the audio/video outputs,
# captions will be burned into the final MP4 using libass.
ENABLE_BURN_IN_CAPTIONS = os.environ.get('ENABLE_BURN_IN_CAPTIONS', 'true').lower() in ('true', '1', 'yes')

# Caption layout targets
# "4th/5 of the screen" interpreted as the lower 20% of the frame.
CAPTIONS_BOTTOM_MARGIN_FRACTION = float(os.environ.get('CAPTIONS_BOTTOM_MARGIN_FRACTION', '0.20'))

# Caption text shaping
CAPTIONS_WORDS_PER_LINE = int(os.environ.get('CAPTIONS_WORDS_PER_LINE', '5'))
CAPTIONS_MAX_LINES = int(os.environ.get('CAPTIONS_MAX_LINES', '3'))
CAPTIONS_TARGET_LINES = int(os.environ.get('CAPTIONS_TARGET_LINES', '2'))  # preferred 2, allow up to CAPTIONS_MAX_LINES

# Video Text Overlay Settings
VIDEO_TITLE_FONT_SIZE = 72
VIDEO_TIMER_FONT_SIZE = 48
VIDEO_TITLE_COLOR = "white"
VIDEO_TIMER_COLOR = "white"

# ============================================================================
# File System Settings
# ============================================================================

# File Naming Patterns
SCRIPT_TXT_PATTERN = "{topic}-{date}-{code}.txt"
SCRIPT_JSON_PATTERN = "{topic}-{date}-{code}.json"
CHAPTERS_JSON_PATTERN = "{topic}-{date}-{code}.chapters.json"
FFMETA_PATTERN = "{topic}-{date}-{code}.ffmeta"
AUDIO_PATTERN = "{topic}-{date}-{code}.m4a"
VIDEO_PATTERN = "{topic}-{date}-{code}.mp4"
SOURCES_JSON_PATTERN = "{topic}-{date}.sources.json"

# Image Storage
IMAGES_SUBDIR = "images"  # Subdirectory for temporary images within topic folder

# Allowed Image Extensions for Download
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']

# ============================================================================
# RSS Feed Settings - REMOVED
# RSS generation has been removed from the project per requirements
# ============================================================================

# ============================================================================
# Pipeline Settings
# ============================================================================

# Workflow Stages
ENABLE_SCRIPT_GENERATION = True
ENABLE_TTS_GENERATION = True
ENABLE_VIDEO_RENDERING = False
ENABLE_VIDEO_GENERATION = True  # Generate video (visual component)
ENABLE_VIDEO_AUDIO_MUX = True  # Combine video with audio (when False, outputs video-only)
ENABLE_IMAGE_CLEANUP = False  # Clean up images after video generation

# Error Handling
MAX_ERROR_MESSAGE_LENGTH = 500  # Maximum length for sanitized error messages

# Validation Settings
REQUIRE_GPT_KEY = True  # Whether to fail if GPT_KEY not available (required for production)
REQUIRE_GOOGLE_API_KEY_FOR_PREMIUM = True  # Whether to fail if GOOGLE_API_KEY not available for premium topics
# Note: MIN_SOURCES_REQUIRED removed - no source pre-validation in v2 architecture

# ============================================================================
# Voice Download Settings
# ============================================================================

# Piper Voice Download Sources (tried in order)
VOICE_DOWNLOAD_SOURCES = [
    {
        'name': 'JSDelivr CDN',
        'url_template': 'https://cdn.jsdelivr.net/gh/rhasspy/piper-voices@v1.0.0/{voice_path}',
        'description': 'Fast global CDN, excellent firewall compatibility'
    },
    {
        'name': 'Statically CDN',
        'url_template': 'https://cdn.statically.io/gh/rhasspy/piper-voices/v1.0.0/{voice_path}',
        'description': 'Alternative CDN with good availability'
    },
    {
        'name': 'GitHub Raw',
        'url_template': 'https://raw.githubusercontent.com/rhasspy/piper-voices/v1.0.0/{voice_path}',
        'description': 'Direct GitHub raw content access'
    },
    {
        'name': 'GitHack CDN',
        'url_template': 'https://raw.githack.com/rhasspy/piper-voices/v1.0.0/{voice_path}',
        'description': 'GitHub proxy service for better access'
    },
    {
        'name': 'Hugging Face',
        'url_template': 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/{voice_path}',
        'description': 'AI model repository mirror'
    },
    {
        'name': 'GitHub Tagged Release',
        'url_template': 'https://github.com/rhasspy/piper-voices/raw/v1.0.0/{voice_path}',
        'description': 'Stable versioned release'
    },
    {
        'name': 'Hugging Face Raw',
        'url_template': 'https://huggingface.co/rhasspy/piper-voices/resolve/main/{voice_path}',
        'description': 'Alternative Hugging Face endpoint'
    }
]

# HTTP Settings for Downloads
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
DOWNLOAD_TIMEOUT = 30  # Timeout for downloads in seconds

# ============================================================================
# Helper Functions
# ============================================================================

def get_content_code(content_type: str, index: int) -> str:
    """
    Generate content code for a specific format and index.
    
    Args:
        content_type: Type of content ('long', 'medium', 'short', 'reels')
        index: Zero-based index of the content
        
    Returns:
        Content code string (e.g., 'L1', 'M2', 'S3', 'R4')
    """
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"Unknown content type: {content_type}")
    
    prefix = CONTENT_TYPES[content_type]['code_prefix']
    return f"{prefix}{index + 1}"


def get_video_resolution_for_content_type(content_type: str) -> tuple:
    """
    Get video resolution (width, height) for a content type.
    
    Args:
        content_type: Type of content ('long', 'medium', 'short', 'reels')
        
    Returns:
        Tuple of (width, height) for the content type's video format
    """
    if content_type not in CONTENT_TYPES:
        raise ValueError(f"Unknown content type: {content_type}")
    
    video_format = CONTENT_TYPES[content_type].get('video_format', 'horizontal')
    resolution = VIDEO_RESOLUTIONS[video_format]
    return (resolution['width'], resolution['height'])


def get_video_resolution_for_code(content_code: str) -> tuple:
    """
    Get video resolution (width, height) from a content code.
    
    Args:
        content_code: Content code string (e.g., 'L1', 'M2', 'S3', 'R4')
        
    Returns:
        Tuple of (width, height) for the content code's video format
    """
    # Extract content type from code prefix
    prefix = content_code[0].upper()
    
    for content_type, spec in CONTENT_TYPES.items():
        if spec['code_prefix'] == prefix:
            return get_video_resolution_for_content_type(content_type)
    
    # Default to horizontal format if unknown code
    return (VIDEO_RESOLUTIONS['horizontal']['width'], VIDEO_RESOLUTIONS['horizontal']['height'])


def get_all_content_codes(content_types_enabled: dict) -> list:
    """
    Get list of all content codes based on enabled types.
    
    Args:
        content_types_enabled: Dict with boolean flags for each type
        
    Returns:
        List of content codes (e.g., ['L1', 'M1', 'M2', 'S1', ...])
    """
    codes = []
    
    for content_type in ['long', 'medium', 'short', 'reels']:
        if content_types_enabled.get(content_type, True):
            spec = CONTENT_TYPES[content_type]
            for i in range(spec['count']):
                codes.append(get_content_code(content_type, i))
    
    return codes


def is_multi_format_enabled(config: dict) -> bool:
    """
    Check if multi-format generation is enabled in config.
    
    Args:
        config: Topic configuration dictionary
        
    Returns:
        True if content_types is configured, False for legacy single format
    """
    return 'content_types' in config


# ============================================================================
# Validation Functions
# ============================================================================

def validate_environment() -> dict:
    """
    Validate that all required environment variables and settings are configured.
    
    Returns:
        Dictionary with validation results including warnings and errors
    """
    import os
    
    results = {
        'errors': [],
        'warnings': [],
        'status': 'ok'
    }
    
    # Check for GPT_KEY
    if not os.getenv('GPT_KEY'):
        if REQUIRE_GPT_KEY:
            results['errors'].append("GPT_KEY environment variable not set (required for script generation)")
        else:
            results['warnings'].append("GPT_KEY not set")
    
    # Check for GOOGLE_API_KEY (for premium topics)
    if not os.getenv('GOOGLE_API_KEY'):
        if REQUIRE_GOOGLE_API_KEY_FOR_PREMIUM:
            results['errors'].append("GOOGLE_API_KEY not set (required for premium TTS topics)")
        else:
            results['warnings'].append("GOOGLE_API_KEY not set - premium TTS will be unavailable")
    
    # Check Python packages
    try:
        import openai
    except ImportError:
        results['errors'].append("openai package not installed (pip install openai>=1.0.0)")
    
    try:
        import requests
    except ImportError:
        results['errors'].append("requests package not installed (pip install requests>=2.31.0)")
    
    # Determine overall status
    if results['errors']:
        results['status'] = 'error'
    elif results['warnings']:
        results['status'] = 'warning'
    
    return results


def validate_topic_config(config: dict) -> dict:
    """
    Validate a topic configuration dictionary.
    
    Args:
        config: Topic configuration to validate
        
    Returns:
        Dictionary with validation results
    """
    results = {
        'errors': [],
        'warnings': [],
        'status': 'ok'
    }
    
    # Required fields
    required_fields = ['id', 'title', 'queries']
    for field in required_fields:
        if field not in config:
            results['errors'].append(f"Missing required field: {field}")
    
    # Check enabled field
    if 'enabled' in config and not isinstance(config['enabled'], bool):
        results['errors'].append("enabled field must be a boolean (true/false)")
    
    # Voice / Roles configuration
    # Backwards compatible:
    # - If use_roles is true, prefer config['roles'].
    # - If use_roles is missing, legacy voice_a/voice_b fields are accepted.
    use_roles = config.get('use_roles', None)
    roles = config.get('roles', None)

    if use_roles is True:
        if not isinstance(roles, list) or not roles:
            results['warnings'].append("use_roles=true but roles[] not configured - will fall back to voice_a/voice_b")
    elif use_roles is False:
        # Explicitly no roles/personas.
        pass
    else:
        # Legacy behavior
        if 'voice_a_name' not in config:
            results['warnings'].append("voice_a_name not configured - will use default")
        if 'voice_b_name' not in config:
            results['warnings'].append("voice_b_name not configured - will use default")
    
    # TTS voices
    if config.get('premium_tts'):
        if 'tts_voice_a' not in config:
            results['warnings'].append("premium_tts enabled but tts_voice_a not specified")
        if 'tts_voice_b' not in config:
            results['warnings'].append("premium_tts enabled but tts_voice_b not specified")
    
    # TTS chunking configuration
    if 'tts_use_chunking' in config and not isinstance(config['tts_use_chunking'], bool):
        results['errors'].append("tts_use_chunking field must be a boolean (true/false)")
    
    # Content types (for multi-format)
    # Backwards compatible:
    # - V1: {"long": true, "medium": false, ...}
    # - V2: {"long": {"enabled": true, "items": 1, "max_words": 20000}, ...}
    if 'content_types' in config and isinstance(config['content_types'], dict):
        content_types = config['content_types']
        any_enabled = False

        for k, v in content_types.items():
            if isinstance(v, bool):
                any_enabled = any_enabled or v
            elif isinstance(v, dict):
                enabled_val = v.get('enabled', False)
                if not isinstance(enabled_val, bool):
                    results['errors'].append(f"content_types.{k}.enabled must be boolean")
                else:
                    any_enabled = any_enabled or enabled_val

                if 'items' in v and (not isinstance(v['items'], int) or v['items'] < 0):
                    results['errors'].append(f"content_types.{k}.items must be a non-negative integer")
                if 'max_words' in v and (not isinstance(v['max_words'], int) or v['max_words'] <= 0):
                    results['errors'].append(f"content_types.{k}.max_words must be a positive integer")
            else:
                results['errors'].append(f"content_types.{k} must be boolean or object")

        if not any_enabled:
            results['errors'].append("content_types configured but all types disabled")
    
    # Determine overall status
    if results['errors']:
        results['status'] = 'error'
    elif results['warnings']:
        results['status'] = 'warning'
    
    return results


def resolve_voice_for_gender(gender: str, quality: str = None, premium: bool = False) -> str:
    """
    Resolve voice model name based on gender and quality.
    
    Args:
        gender: 'Male' or 'Female' (case-insensitive)
        quality: 'high', 'medium', 'low', or None for default (Piper only)
        premium: Whether to use Google Cloud TTS voices
        
    Returns:
        Voice model name string
    """
    gender_lower = gender.lower() if gender else 'male'
    
    if premium:
        # Use Google Cloud TTS voices
        return GOOGLE_VOICE_MAP.get(gender_lower, GOOGLE_VOICE_MAP['male'])
    else:
        # Use Piper TTS voices
        if gender_lower not in PIPER_VOICE_MAP:
            gender_lower = 'male'  # Default to male if invalid
        
        gender_voices = PIPER_VOICE_MAP[gender_lower]
        
        if quality and quality.lower() in gender_voices:
            return gender_voices[quality.lower()]
        else:
            return gender_voices['default']


def check_voice_availability(voice_name: str) -> bool:
    """
    Check if a Piper voice model is available on disk.
    
    Args:
        voice_name: Name of the voice model (e.g., 'en_US-ryan-high')
        
    Returns:
        True if both .onnx and .onnx.json files exist, False otherwise
    """
    from pathlib import Path
    
    voice_path = Path.home() / '.local' / 'share' / 'piper-tts' / 'voices' / f'{voice_name}.onnx'
    config_path = Path.home() / '.local' / 'share' / 'piper-tts' / 'voices' / f'{voice_name}.onnx.json'
    
    return voice_path.exists() and config_path.exists()


def get_available_voice_for_gender(gender: str, quality: str = None, premium: bool = False) -> tuple:
    """
    Get an available voice for the specified gender, with fallback logic.
    
    Args:
        gender: 'Male' or 'Female' (case-insensitive)
        quality: 'high', 'medium', 'low', or None for default (Piper only)
        premium: Whether to use Google Cloud TTS voices
        
    Returns:
        Tuple of (voice_name, is_fallback, warning_message)
        - voice_name: The selected voice model name
        - is_fallback: True if fallback was used
        - warning_message: None if primary voice found, warning string if fallback used
    """
    # For premium TTS, always return the mapped voice (no file checking needed)
    if premium:
        voice = resolve_voice_for_gender(gender, quality, premium=True)
        return (voice, False, None)
    
    # For Piper TTS, check availability and use fallbacks if needed
    primary_voice = resolve_voice_for_gender(gender, quality, premium=False)
    
    # Check if primary voice is available
    if check_voice_availability(primary_voice):
        return (primary_voice, False, None)
    
    # Try fallbacks
    gender_lower = gender.lower() if gender else 'male'
    if gender_lower not in PIPER_VOICE_FALLBACKS:
        gender_lower = 'male'
    
    fallbacks = PIPER_VOICE_FALLBACKS[gender_lower]
    for fallback_voice in fallbacks:
        if check_voice_availability(fallback_voice):
            warning = (
                f"⚠ Voice '{primary_voice}' not found. "
                f"Using fallback: '{fallback_voice}'. "
                f"Please ensure voice models are cached in ~/.local/share/piper-tts/voices/"
            )
            return (fallback_voice, True, warning)
    
    # No voices available - return primary and let the error be handled downstream
    warning = (
        f"⚠ CRITICAL: No voice models found for gender '{gender}'. "
        f"Attempted: {primary_voice} and fallbacks {fallbacks}. "
        f"Voice models must be available in ~/.local/share/piper-tts/voices/"
    )
    return (primary_voice, True, warning)


# ============================================================================
# Output Profiles (for Blender video rendering)
# ============================================================================

def load_output_profiles() -> dict:
    """
    Load output profiles from config/output_profiles.yml.
    
    Returns:
        Dictionary of output profiles
    """
    try:
        import yaml
        from pathlib import Path
        
        config_dir = Path(__file__).parent.parent / 'config'
        profiles_path = config_dir / 'output_profiles.yml'
        
        if not profiles_path.exists():
            # Return empty dict if file doesn't exist (not critical for now)
            return {}
        
        with open(profiles_path, 'r') as f:
            config = yaml.safe_load(f)
        
        return config.get('profiles', {})
    except Exception as e:
        # Log error but don't fail - profiles are optional for now
        print(f"Warning: Failed to load output profiles: {e}")
        return {}


def get_output_profile(content_type: str) -> dict:
    """
    Get output profile for a specific content type.
    
    Args:
        content_type: Content type ('long', 'medium', 'short', 'reels')
        
    Returns:
        Profile dictionary or empty dict if not found
    """
    profiles = load_output_profiles()
    return profiles.get(content_type, {})
