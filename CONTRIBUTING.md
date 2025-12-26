# Contributing Guide

Thank you for contributing to the Podcast Maker project! This guide will help you understand how to contribute effectively.

## Getting Started

### Prerequisites
- Python 3.11+
- Git
- FFmpeg (for local testing)
- GitHub account

### Initial Setup
1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/podcast-maker.git
   cd podcast-maker
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up example data:
   ```bash
   python3 scripts/setup_example.py
   ```

## How to Contribute

### Types of Contributions

1. **New Features**
   - New TTS providers
   - Additional source collectors
   - Video effects and filters
   - RSS feed generation
   - Analytics and monitoring

2. **Bug Fixes**
   - Pipeline failures
   - Data quality issues
   - Workflow errors
   - Edge cases

3. **Documentation**
   - README improvements
   - Code comments
   - Tutorial videos
   - Example configurations

4. **Testing**
   - Unit tests
   - Integration tests
   - Performance benchmarks
   - Quality checks

### Development Workflow

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Make Changes**
   - Follow the code style (PEP 8 for Python)
   - Add docstrings to functions
   - Keep changes focused and minimal
   - Test locally before committing

3. **Test Your Changes**
   ```bash
   # Test specific component
   cd scripts
   python3 collect_sources.py --topic topic-01
   
   # Test full pipeline
   python3 run_pipeline.py --topic topic-01 --skip-video
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "Brief description of changes"
   ```
   
   **Commit message guidelines:**
   - Use present tense: "Add feature" not "Added feature"
   - Be specific: "Fix TTS caching bug" not "Fix bug"
   - Reference issues: "Fix #123: Resolve audio sync issue"

5. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill out the PR template
   - Link related issues

## Code Style Guidelines

### Python

Follow PEP 8 with these specifics:

```python
# Good: Clear function names with docstrings
def generate_script_with_llm(config: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate podcast script using LLM.
    
    Args:
        config: Topic configuration
        sources: List of source articles
    
    Returns:
        Structured script with segments and dialogue
    """
    pass

# Good: Type hints
def process_sources(sources: List[Dict[str, Any]], max_items: int = 10) -> List[Dict[str, Any]]:
    pass

# Good: Meaningful variable names
fresh_sources = filter_by_freshness(all_sources, hours=24)
picked_sources = select_for_script(fresh_sources, num_items=10)

# Avoid: Generic names
data = get_data()
result = process(data)
```

### Error Handling

```python
# Good: Specific error handling with logging
try:
    script = generate_script_with_llm(config, sources)
except LLMAPIError as e:
    print(f"LLM API failed: {e}")
    return None
except Exception as e:
    print(f"Unexpected error in script generation: {e}")
    import traceback
    traceback.print_exc()
    return None

# Avoid: Bare except
try:
    do_something()
except:
    pass
```

### File Organization

```
scripts/
├── __init__.py           # Package marker
├── config.py             # Configuration utilities
├── dedup.py              # Deduplication logic
├── collect_sources.py    # Source collection
├── script_generate.py    # Script generation
├── tts_generate.py       # TTS synthesis
├── video_render.py       # Video rendering
└── run_pipeline.py       # Orchestration
```

## Adding New Features

### Adding a New TTS Provider

1. Edit `scripts/tts_generate.py`
2. Add provider function:
   ```python
   def generate_tts_provider_name(text: str, voice: str, output_path: Path) -> bool:
       """Generate TTS using ProviderName."""
       # Implementation
       return True
   ```
3. Update `generate_tts_chunk()` to support new provider
4. Add provider config option to topic JSON
5. Update README with new provider docs
6. Test with all voice types

### Adding a New Source Collector

1. Edit `scripts/collect_sources.py`
2. Add collector function:
   ```python
   def search_sources_provider(query: str, languages: List[str]) -> List[Dict[str, Any]]:
       """Search sources using ProviderName API."""
       # Implementation
       return sources
   ```
3. Update `collect_for_topic()` to use new collector
4. Add API credentials to secrets (if needed)
5. Update README with setup instructions
6. Test with various queries

### Adding New Video Effects

1. Edit `scripts/video_render.py`
2. Add effect function:
   ```python
   def apply_effect_name(input_path: Path, output_path: Path, **params) -> bool:
       """Apply specific effect to video."""
       # Use FFmpeg filters
       return True
   ```
3. Update `create_text_overlay_video()` to apply effect
4. Add effect parameters to topic config
5. Test visual output quality

## Testing Requirements

### Before Submitting PR

- [ ] Code runs without errors
- [ ] All existing tests pass (if any)
- [ ] New features have example usage
- [ ] Documentation is updated
- [ ] No secrets or credentials committed
- [ ] Git history is clean (squash if needed)

### Local Testing Checklist

```bash
# 1. Test source collection
python3 scripts/collect_sources.py --all

# 2. Test script generation for multiple topics
for topic in topic-01 topic-02 topic-03; do
    python3 scripts/script_generate.py --topic $topic
done

# 3. Test pipeline (without video if FFmpeg unavailable)
python3 scripts/run_pipeline.py --topic topic-01 --skip-video

# 4. Verify output structure
ls -lh outputs/topic-01/
jq . outputs/topic-01/topic-01-*.sources.json

# 5. Check data integrity
jq 'length' data/topic-01/fresh.json
jq 'length' data/topic-01/backlog.json
```

## Pull Request Guidelines

### PR Template

When creating a PR, include:

1. **Description**: What does this PR do?
2. **Related Issues**: Link to issue numbers (#123)
3. **Changes Made**: Bullet list of changes
4. **Testing Done**: How was this tested?
5. **Screenshots**: For UI/visual changes
6. **Breaking Changes**: Any breaking changes?
7. **Checklist**: Confirm all requirements met

### Example PR

```markdown
## Description
Add support for ElevenLabs TTS provider as alternative to Gemini and Piper.

## Related Issues
Closes #45

## Changes Made
- Added `generate_tts_elevenlabs()` function in `tts_generate.py`
- Updated topic config schema to support `elevenlabs` as TTS provider
- Added API key handling for ElevenLabs
- Updated README with ElevenLabs setup instructions

## Testing Done
- Tested with topics 01, 02, 03
- Verified audio quality comparable to Gemini
- Confirmed caching works correctly
- Tested API error handling

## Breaking Changes
None - backwards compatible with existing configs.

## Checklist
- [x] Code follows project style guidelines
- [x] Documentation updated
- [x] Tested locally
- [x] No secrets committed
```

### Review Process

1. Maintainer reviews code
2. CI/CD runs automated checks (if configured)
3. Request changes or approve
4. Merge when approved

## Code of Conduct

### Expected Behavior

- Be respectful and inclusive
- Provide constructive feedback
- Accept constructive criticism
- Focus on what's best for the project
- Show empathy towards others

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or inflammatory comments
- Publishing others' private information
- Other unethical or unprofessional conduct

## Getting Help

### Questions?

- Open a [GitHub Discussion](../../discussions)
- Check existing [Issues](../../issues)
- Review [README.md](README.md) and [TESTING.md](TESTING.md)

### Reporting Bugs

Use the issue template and include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Minimal steps to reproduce
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: OS, Python version, FFmpeg version
6. **Logs**: Relevant error messages or logs
7. **Configuration**: Relevant topic config (sanitized)

### Security Issues

For security vulnerabilities:
- **Do NOT** open a public issue
- Email maintainers privately
- Include detailed description and steps
- Allow time for fix before disclosure

## Release Process

(For maintainers)

1. Update version in relevant files
2. Update CHANGELOG.md
3. Create release branch: `release/vX.Y.Z`
4. Test thoroughly
5. Merge to main
6. Create GitHub release with tag
7. Update documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to make automated podcast generation better! 🎙️
