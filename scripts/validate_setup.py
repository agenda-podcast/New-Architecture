#!/usr/bin/env python3
"""
Validate podcast-maker setup and generate comprehensive report.

This script checks:
- System dependencies (FFmpeg, Blender)
- Python dependencies
- Configuration files
- Pipeline functionality
"""
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import json

class SetupValidator:
    """Validates the complete setup."""
    
    def __init__(self):
        self.results = {
            'system_deps': {},
            'python_deps': {},
            'config_files': {},
            'blender_setup': {},
            'summary': {}
        }
        self.errors = []
        self.warnings = []
    
    def check_command(self, command: str, min_version: str = None) -> Tuple[bool, str]:
        """Check if a command is available and get version."""
        try:
            result = subprocess.run(
                [command, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                return True, version
            return False, ''
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, ''
    
    def check_system_dependencies(self):
        """Check system-level dependencies."""
        print("Checking system dependencies...")
        
        # Check FFmpeg
        has_ffmpeg, ffmpeg_version = self.check_command('ffmpeg')
        self.results['system_deps']['ffmpeg'] = {
            'installed': has_ffmpeg,
            'version': ffmpeg_version if has_ffmpeg else 'Not found'
        }
        if not has_ffmpeg:
            self.errors.append("FFmpeg not installed")
        else:
            print(f"  ✓ FFmpeg: {ffmpeg_version}")
        
        # Check Blender (optional)
        blender_found = False
        blender_paths = [
            'blender',
            '/usr/bin/blender',
            './blender-4.5.0-linux-x64/blender'
        ]
        
        for blender_path in blender_paths:
            has_blender, blender_version = self.check_command(blender_path)
            if has_blender:
                self.results['system_deps']['blender'] = {
                    'installed': True,
                    'path': blender_path,
                    'version': blender_version
                }
                print(f"  ✓ Blender: {blender_version} ({blender_path})")
                blender_found = True
                break
        
        if not blender_found:
            self.results['system_deps']['blender'] = {
                'installed': False,
                'version': 'Not found'
            }
            self.warnings.append("Blender not installed (optional for enhanced video rendering)")
            print(f"  ⚠ Blender: Not found (optional)")
    
    def check_python_dependencies(self):
        """Check Python package dependencies."""
        print("\nChecking Python dependencies...")
        
        required_packages = [
            'requests',
            'yaml',
            'openai',
            'PIL',  # Pillow
        ]
        
        optional_packages = [
            'google.cloud.texttospeech',
            'googleapiclient',
            'feedgen',
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                self.results['python_deps'][package] = {
                    'installed': True,
                    'required': True
                }
                print(f"  ✓ {package}")
            except ImportError:
                self.results['python_deps'][package] = {
                    'installed': False,
                    'required': True
                }
                self.errors.append(f"Required Python package missing: {package}")
                print(f"  ✗ {package} (required)")
        
        for package in optional_packages:
            try:
                __import__(package)
                self.results['python_deps'][package] = {
                    'installed': True,
                    'required': False
                }
                print(f"  ✓ {package} (optional)")
            except ImportError:
                self.results['python_deps'][package] = {
                    'installed': False,
                    'required': False
                }
                self.warnings.append(f"Optional Python package missing: {package}")
                print(f"  ⚠ {package} (optional)")
    
    def check_config_files(self):
        """Check required configuration files."""
        print("\nChecking configuration files...")
        
        repo_root = Path(__file__).parent.parent
        
        required_files = [
            'config/output_profiles.yml',
            'scripts/global_config.py',
            'scripts/video_render.py',
            'scripts/blender/build_video.py',
            'scripts/blender/template_selector.py',
        ]
        
        for file_path in required_files:
            full_path = repo_root / file_path
            exists = full_path.exists()
            self.results['config_files'][file_path] = {
                'exists': exists,
                'path': str(full_path)
            }
            if exists:
                print(f"  ✓ {file_path}")
            else:
                self.errors.append(f"Required file missing: {file_path}")
                print(f"  ✗ {file_path}")
    
    def check_blender_setup(self):
        """Check Blender-specific setup."""
        print("\nChecking Blender setup...")
        
        repo_root = Path(__file__).parent.parent
        
        # Check templates directory
        templates_dir = repo_root / 'templates'
        self.results['blender_setup']['templates_dir'] = {
            'exists': templates_dir.exists()
        }
        
        if templates_dir.exists():
            print(f"  ✓ Templates directory exists")
            
            # Check for template files
            blend_files = list(templates_dir.rglob('*.blend'))
            self.results['blender_setup']['template_count'] = len(blend_files)
            
            if blend_files:
                print(f"  ✓ Found {len(blend_files)} template(s)")
            else:
                self.warnings.append("No .blend template files found (will use procedural rendering)")
                print(f"  ⚠ No .blend templates (will use procedural rendering)")
        else:
            self.warnings.append("Templates directory not found")
            print(f"  ⚠ Templates directory not found")
        
        # Check assets directory
        assets_dir = repo_root / 'assets'
        self.results['blender_setup']['assets_dir'] = {
            'exists': assets_dir.exists()
        }
        
        if assets_dir.exists():
            print(f"  ✓ Assets directory exists")
            
            # Count assets
            luts = list((assets_dir / 'luts').rglob('*.cube')) if (assets_dir / 'luts').exists() else []
            overlays = list((assets_dir / 'overlays').rglob('*.png')) if (assets_dir / 'overlays').exists() else []
            fonts = list((assets_dir / 'fonts').rglob('*.ttf')) + list((assets_dir / 'fonts').rglob('*.otf')) if (assets_dir / 'fonts').exists() else []
            
            self.results['blender_setup']['asset_counts'] = {
                'luts': len(luts),
                'overlays': len(overlays),
                'fonts': len(fonts)
            }
            
            if luts or overlays or fonts:
                print(f"  ✓ Found assets: {len(luts)} LUTs, {len(overlays)} overlays, {len(fonts)} fonts")
            else:
                self.warnings.append("No assets found (templates will use basic rendering)")
                print(f"  ⚠ No assets found (basic rendering only)")
        else:
            self.warnings.append("Assets directory not found")
            print(f"  ⚠ Assets directory not found")
    
    def generate_summary(self):
        """Generate summary statistics."""
        self.results['summary'] = {
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings),
            'can_run_pipeline': len(self.errors) == 0,
            'can_use_blender': self.results['system_deps'].get('blender', {}).get('installed', False),
            'ffmpeg_available': self.results['system_deps'].get('ffmpeg', {}).get('installed', False)
        }
    
    def print_report(self):
        """Print comprehensive validation report."""
        print("\n" + "="*70)
        print("SETUP VALIDATION REPORT")
        print("="*70)
        
        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        summary = self.results['summary']
        print(f"Errors: {summary['total_errors']}")
        print(f"Warnings: {summary['total_warnings']}")
        print(f"Can run pipeline: {'✓ Yes' if summary['can_run_pipeline'] else '✗ No'}")
        print(f"FFmpeg available: {'✓ Yes' if summary['ffmpeg_available'] else '✗ No'}")
        print(f"Blender available: {'✓ Yes' if summary['can_use_blender'] else '⚠ No (optional)'}")
        
        if summary['can_run_pipeline']:
            print("\n✓ Setup is valid! Pipeline can run.")
            if not summary['can_use_blender']:
                print("  Note: Using FFmpeg renderer (Blender renderer unavailable)")
        else:
            print("\n✗ Setup is incomplete. Please fix errors above.")
        
        print("="*70)
    
    def save_report(self, output_path: Path):
        """Save detailed report as JSON."""
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nDetailed report saved to: {output_path}")
    
    def run(self):
        """Run all validation checks."""
        self.check_system_dependencies()
        self.check_python_dependencies()
        self.check_config_files()
        self.check_blender_setup()
        self.generate_summary()
        self.print_report()
        
        # Save detailed report
        repo_root = Path(__file__).parent.parent
        report_path = repo_root / 'setup_validation_report.json'
        self.save_report(report_path)
        
        return len(self.errors) == 0


def main():
    """Main entry point."""
    print("Podcast Maker - Setup Validation")
    print("="*70 + "\n")
    
    validator = SetupValidator()
    success = validator.run()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
