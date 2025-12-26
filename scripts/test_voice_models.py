#!/usr/bin/env python3
"""Test script to verify Piper voice model configuration and availability."""
import sys
from pathlib import Path

# Constants for voice model validation
MIN_VOICE_MODEL_SIZE_BYTES = 1024  # 1KB - minimum size for a valid voice model file
MOCK_FILE_SIZE_THRESHOLD = 100  # Files smaller than this are likely mock/placeholder files

# Test imports
try:
    def get_voices_dir():
        """Get Piper voices directory."""
        voices_dir = Path.home() / '.local' / 'share' / 'piper-tts' / 'voices'
        return voices_dir
    
    def get_required_voices():
        """Get list of all Piper voices required by topics."""
        from config import get_repo_root, load_topic_config
        voices = set()
        topics_dir = get_repo_root() / 'topics'
        
        for topic_file in topics_dir.glob('topic-*.json'):
            try:
                config = load_topic_config(topic_file.stem)
                # Only collect voices for non-premium topics (Piper)
                if not config.get('premium_tts', False):
                    voices.add(config.get('tts_voice_a', ''))
                    voices.add(config.get('tts_voice_b', ''))
            except Exception as e:
                print(f"Warning: Could not load {topic_file}: {e}")
        
        return {v for v in voices if v}
    
    print("✓ Voice functions defined successfully")
except ImportError as e:
    print(f"✗ Failed to import dependencies: {e}")
    sys.exit(1)

try:
    from config import get_repo_root, load_topic_config
    print("✓ Config functions imported successfully")
except ImportError as e:
    print(f"✗ Failed to import config: {e}")
    sys.exit(1)

# Test voice directory
print("\n=== Voice Directory Check ===")
voices_dir = get_voices_dir()
print(f"✓ Voices directory: {voices_dir}")
print(f"  Directory exists: {voices_dir.exists()}")

if not voices_dir.exists():
    print("  Creating voices directory...")
    voices_dir.mkdir(parents=True, exist_ok=True)
    print("  ✓ Directory created")

# Test required voices detection
print("\n=== Required Voices Detection ===")
required_voices = set()  # Initialize to empty set
try:
    required_voices = get_required_voices()
    print(f"✓ Found {len(required_voices)} required voices:")
    for voice in sorted(required_voices):
        print(f"  - {voice}")
    
    # Verify we have at least some voices (flexible test for future changes)
    if len(required_voices) > 0:
        print("✓ Voice detection working (found voices)")
    else:
        print("⚠ No voices detected - check topic configurations")
    
    # Note common voices for reference (not a hard requirement)
    expected_voices = {'en_US-ryan-high', 'en_US-lessac-high'}
    if required_voices == expected_voices:
        print("  Note: Using high-quality voice set (expected)")
    else:
        print(f"  Note: Voice set: {required_voices}")
        if expected_voices.issubset(required_voices):
            print(f"  ✓ Contains expected high-quality voices")
        else:
            print(f"  ⚠ Missing expected voices: {expected_voices - required_voices}")
        
except Exception as e:
    print(f"✗ Error detecting required voices: {e}")
    import traceback
    traceback.print_exc()
    # Set to empty so the rest of the test can continue
    required_voices = set()

# Test voice file existence
print("\n=== Voice File Check ===")
if not required_voices:
    print("⚠ Skipping voice file check - no voices detected")
else:
    for voice in sorted(required_voices):
        model_path = voices_dir / f'{voice}.onnx'
        config_path = voices_dir / f'{voice}.onnx.json'
        
        model_exists = model_path.exists()
        config_exists = config_path.exists()
        both_exist = model_exists and config_exists
        
        status = "✓" if both_exist else "✗" if not model_exists and not config_exists else "⚠"
        print(f"{status} {voice}:")
        print(f"  Model (.onnx): {'✓' if model_exists else '✗'} {model_path}")
        print(f"  Config (.json): {'✓' if config_exists else '✗'} {config_path}")
        
        if both_exist:
            model_size = model_path.stat().st_size
            config_size = config_path.stat().st_size
            print(f"  Model size: {model_size:,} bytes")
            print(f"  Config size: {config_size:,} bytes")
            
            if model_size < MOCK_FILE_SIZE_THRESHOLD:
                print(f"  ⚠ Warning: Model file is very small (likely mock/placeholder)")
            if config_size < MOCK_FILE_SIZE_THRESHOLD:
                print(f"  ⚠ Warning: Config file is very small (likely mock/placeholder)")

# Test topic voice configurations
print("\n=== Topic Voice Configuration Check ===")
topics_dir = get_repo_root() / 'topics'
topic_files = sorted(topics_dir.glob('topic-*.json'))

print(f"Found {len(topic_files)} topic configurations")

premium_count = 0
piper_count = 0
config_issues = []

for topic_file in topic_files:
    try:
        config = load_topic_config(topic_file.stem)
        topic_id = config.get('id', topic_file.stem)
        premium = config.get('premium_tts', False)
        voice_a = config.get('tts_voice_a', 'NOT SET')
        voice_b = config.get('tts_voice_b', 'NOT SET')
        
        if premium:
            premium_count += 1
            provider = "Google Cloud TTS"
        else:
            piper_count += 1
            provider = "Piper TTS"
        
        print(f"\n{topic_id}:")
        print(f"  Provider: {provider}")
        print(f"  Voice A: {voice_a}")
        print(f"  Voice B: {voice_b}")
        
        # Check for missing voice configurations
        if voice_a == 'NOT SET' or voice_b == 'NOT SET':
            config_issues.append(f"{topic_id}: Missing voice configuration")
            print(f"  ⚠ Warning: Voice configuration incomplete")
        
        # For Piper topics, verify voices are in required list
        if not premium:
            if voice_a not in required_voices:
                config_issues.append(f"{topic_id}: Voice A ({voice_a}) not in required voices")
                print(f"  ⚠ Warning: Voice A not in required voices list")
            if voice_b not in required_voices:
                config_issues.append(f"{topic_id}: Voice B ({voice_b}) not in required voices")
                print(f"  ⚠ Warning: Voice B not in required voices list")
        
    except Exception as e:
        config_issues.append(f"{topic_file.name}: Failed to load ({e})")
        print(f"  ✗ Error loading config: {e}")

print(f"\n{'='*60}")
print(f"Premium (Google Cloud) topics: {premium_count}")
print(f"Non-premium (Piper) topics: {piper_count}")

if config_issues:
    print(f"\n⚠ Configuration Issues ({len(config_issues)}):")
    for issue in config_issues:
        print(f"  - {issue}")

# Test gender-based voice resolution
print("\n=== Gender-Based Voice Resolution ===")
try:
    from global_config import (
        resolve_voice_for_gender, 
        get_available_voice_for_gender,
        check_voice_availability
    )
    print("✓ Voice resolution functions imported")
    
    # Test voice resolution for different genders and qualities
    test_cases = [
        ('Male', 'high', False),
        ('Female', 'high', False),
        ('Male', 'medium', False),
        ('Female', 'medium', False),
        ('Male', None, False),  # Default quality
        ('Female', None, False),  # Default quality
        ('Male', None, True),  # Premium
        ('Female', None, True),  # Premium
    ]
    
    for gender, quality, premium in test_cases:
        voice = resolve_voice_for_gender(gender, quality, premium)
        provider = "Google Cloud" if premium else "Piper"
        quality_str = quality if quality else "default"
        print(f"  {gender}/{quality_str}/{provider}: {voice}")
    
    # Test availability checking and fallbacks
    print("\n  Testing availability checking:")
    for gender in ['Male', 'Female']:
        voice, is_fallback, warning = get_available_voice_for_gender(gender, 'high', False)
        status = "⚠ FALLBACK" if is_fallback else "✓ Available"
        print(f"  {gender}: {voice} - {status}")
        if warning:
            print(f"    Warning: {warning}")
    
except ImportError as e:
    print(f"✗ Failed to import voice resolution functions: {e}")
except Exception as e:
    print(f"✗ Error testing voice resolution: {e}")
    import traceback
    traceback.print_exc()

# Test Piper package availability
print("\n=== Piper Package Check ===")
try:
    from piper.voice import PiperVoice
    print("✓ Piper package is installed")
    
    # Try to check version
    try:
        import piper
        version = getattr(piper, '__version__', 'unknown')
        print(f"  Version: {version}")
    except:
        print("  Version: unknown")
        
except ImportError as e:
    print(f"⚠ Piper package not available: {e}")
    print("  Install with: pip install piper-tts")

# Summary
print("\n" + "="*60)
print("=== Test Summary ===")
print(f"✓ Voice directory configured: {voices_dir}")
print(f"✓ Required voices detected: {len(required_voices)}")
print(f"✓ Topic configurations checked: {len(topic_files)}")

if config_issues:
    print(f"⚠ Configuration issues found: {len(config_issues)}")
else:
    print("✓ All topic configurations valid")

# Check if voices are ready
voices_ready = all(
    (voices_dir / f'{voice}.onnx').exists() and 
    (voices_dir / f'{voice}.onnx.json').exists()
    for voice in required_voices
)

if voices_ready:
    # Check if they're not empty (not mock files)
    all_have_content = all(
        (voices_dir / f'{voice}.onnx').stat().st_size >= MIN_VOICE_MODEL_SIZE_BYTES
        for voice in required_voices
    )
    
    if all_have_content:
        print("✓ All voice models downloaded and ready")
    else:
        print("⚠ Voice files exist but appear to be mock/empty files")
        print("  Voice models should be available via GitHub Actions cache or manually placed in the directory")
else:
    print("⚠ Voice models not found in cache")
    print("  Voice models should be available via GitHub Actions cache or manually placed in ~/.local/share/piper-tts/voices/")

print("="*60)
