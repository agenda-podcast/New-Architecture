#!/usr/bin/env python3
"""
System validation module.
Validates environment, dependencies, configurations, and system state before pipeline execution.
"""
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from global_config import (
    validate_environment, validate_topic_config,
    REQUIRE_GPT_KEY, REQUIRE_GOOGLE_API_KEY_FOR_PREMIUM
)


class ValidationResult:
    """Container for validation results."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.checks_passed: int = 0
        self.checks_total: int = 0
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        logger.error(f"✗ {message}")
    
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(f"⚠ {message}")
    
    def add_info(self, message: str):
        """Add an info message."""
        self.info.append(message)
        logger.info(f"ℹ {message}")
    
    def add_success(self, message: str):
        """Add a success message."""
        self.checks_passed += 1
        logger.info(f"✓ {message}")
    
    def increment_total(self):
        """Increment total checks count."""
        self.checks_total += 1
    
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 80)
        print("SYSTEM VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Checks: {self.checks_passed}/{self.checks_total} passed")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if self.info:
            print(f"\nℹ️  INFO ({len(self.info)}):")
            for info in self.info:
                print(f"  - {info}")
        
        print("\nSTATUS:", "✓ READY" if self.is_valid() else "✗ FAILED")
        print("=" * 80 + "\n")


def check_python_version(result: ValidationResult) -> None:
    """Validate Python version."""
    result.increment_total()
    version = sys.version_info
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        result.add_error(f"Python 3.8+ required, found {version.major}.{version.minor}")
    else:
        result.add_success(f"Python version: {version.major}.{version.minor}.{version.micro}")


def check_dependencies(result: ValidationResult) -> None:
    """Check required Python packages."""
    required_packages = {
        'requests': 'Core HTTP library',
        'openai': 'ChatGPT script generation'
    }
    
    optional_packages = {
        'piper': 'Local TTS (Piper)',
        'google.cloud.texttospeech': 'Premium TTS (Google Cloud)',
        'google.genai': 'Gemini Developer API (google-genai)',
        'bs4': 'HTML parsing (deprecated - not used in v2 architecture)'
    }
    
    # Check required packages
    for package, description in required_packages.items():
        result.increment_total()
        try:
            if package == 'requests':
                import requests
            elif package == 'openai':
                import openai
            elif package == 'bs4':
                import bs4
            result.add_success(f"Required: {package} ({description})")
        except ImportError:
            result.add_error(f"Missing required package: {package} ({description})")
    
    # Check optional packages
    for package, description in optional_packages.items():
        result.increment_total()
        try:
            if package == 'piper':
                import piper
            elif package == 'google.cloud.texttospeech':
                import google.cloud.texttospeech
            elif package == 'google.genai':
                from google import genai  # type: ignore
            elif package == 'bs4':
                import bs4
            result.add_success(f"Optional: {package} ({description})")
        except ImportError:
            result.add_warning(f"Optional package not installed: {package} ({description})")


def check_environment_variables(result: ValidationResult) -> None:
    """Check required and optional environment variables."""
    # Required (conditional)
    result.increment_total()
    gpt_key = os.getenv('GPT_KEY') or os.getenv('OPENAI_API_KEY')
    if gpt_key:
        result.add_success("GPT_KEY found (ChatGPT script generation enabled)")
    else:
        if REQUIRE_GPT_KEY:
            result.add_error("GPT_KEY not found (required for script generation)")
        else:
            result.add_warning("GPT_KEY not found")
    
    # Optional
    result.increment_total()
    if os.getenv('GOOGLE_API_KEY'):
        result.add_success("GOOGLE_API_KEY found (premium TTS enabled)")
    else:
        if REQUIRE_GOOGLE_API_KEY_FOR_PREMIUM:
            result.add_error("GOOGLE_API_KEY not found (required for premium topics)")
        else:
            result.add_warning("GOOGLE_API_KEY not found (premium TTS will fallback)")


def check_directories(result: ValidationResult) -> None:
    """Check required directory structure."""
    repo_root = Path(__file__).resolve().parent.parent
    
    required_dirs = {
        'topics': 'Topic configuration files',
        'scripts': 'Pipeline scripts'
    }
    
    for dir_name, description in required_dirs.items():
        result.increment_total()
        dir_path = repo_root / dir_name
        if dir_path.exists() and dir_path.is_dir():
            result.add_success(f"Directory: {dir_name}/ ({description})")
        else:
            result.add_error(f"Missing directory: {dir_name}/ ({description})")


def check_topic_configurations(result: ValidationResult) -> None:
    """Validate all topic configuration files."""
    from config import load_topic_config, get_enabled_topics, is_topic_enabled
    
    repo_root = Path(__file__).resolve().parent.parent
    topics_dir = repo_root / 'topics'
    
    if not topics_dir.exists():
        result.add_error("Topics directory not found")
        return
    
    topic_files = list(topics_dir.glob('topic-*.json'))
    
    if not topic_files:
        result.add_warning("No topic configuration files found")
        return
    
    # Get only enabled topics
    enabled_topics = get_enabled_topics()
    disabled_count = len(topic_files) - len(enabled_topics)
    
    result.add_info(f"Found {len(topic_files)} topic configurations ({len(enabled_topics)} enabled, {disabled_count} disabled)")
    
    for topic_file in topic_files:
        result.increment_total()
        topic_id = topic_file.stem
        
        try:
            config = load_topic_config(topic_id)
            
            # Skip disabled topics in validation
            if not is_topic_enabled(config):
                result.add_info(f"Topic config: {topic_id} (disabled, skipping validation)")
                continue
            
            # Validate config structure
            validation = validate_topic_config(config)
            
            if validation['status'] == 'ok':
                result.add_success(f"Topic config: {topic_id}")
            elif validation['status'] == 'warning':
                result.add_success(f"Topic config: {topic_id} (with warnings)")
                for warning in validation['warnings']:
                    result.add_warning(f"  {topic_id}: {warning}")
            else:  # error
                result.add_error(f"Topic config: {topic_id} (invalid)")
                for error in validation['errors']:
                    result.add_error(f"  {topic_id}: {error}")
        
        except Exception as e:
            result.add_error(f"Failed to load {topic_id}: {e}")


def check_data_sources(result: ValidationResult) -> None:
    """Check if topics have sufficient source data.
    
    Note: This check has been deprecated as the pipeline now uses OpenAI
    Responses API with web search capabilities directly, instead of
    pre-collected source data from the data/ directory.
    """
    # Skip source data validation - no longer required
    pass


def check_tts_binaries(result: ValidationResult) -> None:
    """Check if TTS binaries are available."""
    from config import get_repo_root
    
    repo_root = get_repo_root()
    
    # Check for Piper tarball
    result.increment_total()
    piper_tarball = repo_root / 'piper_linux_x86_64.tar.gz'
    if piper_tarball.exists():
        size_mb = piper_tarball.stat().st_size / (1024 * 1024)
        result.add_success(f"Piper tarball found ({size_mb:.1f} MB)")
    else:
        result.add_error("Piper tarball not found (piper_linux_x86_64.tar.gz)")
    
    # Check for extracted Piper binary
    result.increment_total()
    piper_binary = repo_root / 'piper' / 'piper'
    if piper_binary.exists():
        result.add_success("Piper binary extracted and ready")
        
        # Check if binary is executable
        result.increment_total()
        if os.access(piper_binary, os.X_OK):
            result.add_success("Piper binary has executable permissions")
        else:
            result.add_warning("Piper binary is not executable (may need chmod +x)")
        
        # Check for required libraries
        required_libs = [
            'libpiper_phonemize.so',
            'libonnxruntime.so'
        ]
        for lib in required_libs:
            result.increment_total()
            lib_path = repo_root / 'piper' / lib
            if lib_path.exists():
                result.add_success(f"Piper library found: {lib}")
            else:
                result.add_error(f"Missing Piper library: {lib}")
    else:
        result.add_warning("Piper binary not extracted (will be extracted during setup)")


def check_rss_dependencies(result: ValidationResult) -> None:
    """Check RSS feed generation dependencies."""
    result.increment_total()
    
    try:
        from feedgen.feed import FeedGenerator
        result.add_success("RSS feed generator (feedgen) available")
        
        # Test creating a feed
        result.increment_total()
        try:
            fg = FeedGenerator()
            fg.id('test')
            fg.title('Test')
            fg.description('Test')
            fg.link(href='http://example.com', rel='self')
            result.add_success("RSS FeedGenerator instantiation successful")
        except Exception as e:
            result.add_warning(f"RSS FeedGenerator test failed: {e}")
            
    except ImportError:
        result.add_error("feedgen not installed (pip install feedgen)")
        result.add_info("RSS feed generation will be disabled without feedgen")


def check_disk_space(result: ValidationResult) -> None:
    """Check available disk space."""
    import shutil
    
    result.increment_total()
    
    try:
        repo_root = Path(__file__).resolve().parent.parent
        stat = shutil.disk_usage(repo_root)
        
        free_gb = stat.free / (1024 ** 3)
        total_gb = stat.total / (1024 ** 3)
        percent_free = (stat.free / stat.total) * 100
        
        if free_gb < 1:
            result.add_error(f"Low disk space: {free_gb:.1f} GB free ({percent_free:.1f}%)")
        elif free_gb < 5:
            result.add_warning(f"Disk space: {free_gb:.1f} GB free ({percent_free:.1f}%)")
        else:
            result.add_success(f"Disk space: {free_gb:.1f} GB free ({percent_free:.1f}%)")
    
    except Exception as e:
        result.add_warning(f"Could not check disk space: {e}")


def validate_system(verbose: bool = True) -> Tuple[bool, ValidationResult]:
    """
    Run complete system validation.
    
    Args:
        verbose: Print detailed results
        
    Returns:
        Tuple of (is_valid, validation_result)
    """
    result = ValidationResult()
    
    if verbose:
        print("\n" + "=" * 80)
        print("PODCAST MAKER SYSTEM VALIDATION")
        print("=" * 80 + "\n")
    
    # Run all validation checks
    check_python_version(result)
    check_dependencies(result)
    check_environment_variables(result)
    check_directories(result)
    check_topic_configurations(result)
    check_data_sources(result)
    check_tts_binaries(result)
    check_rss_dependencies(result)
    check_disk_space(result)
    
    # Use global_config validation
    env_validation = validate_environment()
    for error in env_validation.get('errors', []):
        result.add_error(f"Environment: {error}")
    for warning in env_validation.get('warnings', []):
        result.add_warning(f"Environment: {warning}")
    
    # Print summary
    if verbose:
        result.print_summary()
    
    return result.is_valid(), result


if __name__ == '__main__':
    """
    Run validation when executed directly.
    
    Executes complete system validation and exits with appropriate status code.
    Exit code 0 indicates validation passed, 1 indicates failures detected.
    """
    is_valid, result = validate_system(verbose=True)
    
    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)
