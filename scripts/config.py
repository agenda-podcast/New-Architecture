"""Configuration utilities.

This repository supports a multi-tenant outputs layout intended for CI usage
where outputs may be committed back into the repository after each module.

Default behavior:
  - If TENANT_ID is set (or USE_TENANT_OUTPUTS=true), write outputs under:
        tenants/<TENANT_ID>/outputs/<topic_id>/
    This path is commit-friendly.

Backwards compatibility:
  - If TENANT_ID is not set and USE_TENANT_OUTPUTS is not enabled,
    outputs go to the legacy:
        outputs/<topic_id>/
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional


def get_repo_root() -> Path:
    """Get the repository root directory."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent


def get_tenant_id(default: str = "0000000001") -> str:
    """Return active tenant id."""
    tid = os.environ.get("TENANT_ID", "").strip()
    return tid or default


def use_tenant_outputs() -> bool:
    """Whether outputs should be written to tenants/<TENANT_ID>/outputs/..."""
    v = os.environ.get("USE_TENANT_OUTPUTS")
    if v is not None:
        return str(v).strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(os.environ.get("TENANT_ID", "").strip())


def get_tenant_root(tenant_id: Optional[str] = None) -> Path:
    repo_root = get_repo_root()
    tid = (tenant_id or get_tenant_id()).strip() or get_tenant_id()
    return repo_root / "tenants" / tid


def load_topic_config(topic_id: str) -> Dict[str, Any]:
    """Load topic configuration from JSON file."""
    repo_root = get_repo_root()
    config_path = repo_root / 'topics' / f'{topic_id}.json'
    
    if not config_path.exists():
        raise FileNotFoundError(f"Topic config not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_data_dir(topic_id: str, tenant_id: Optional[str] = None) -> Path:
    """Get data directory for a topic.

    When tenant outputs are enabled, keep per-tenant data separation:
      tenants/<TENANT_ID>/data/<topic_id>/
    """
    repo_root = get_repo_root()
    if use_tenant_outputs():
        base = get_tenant_root(tenant_id) / "data"
    else:
        base = repo_root / "data"
    data_dir = base / topic_id
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_output_dir(topic_id: str, tenant_id: Optional[str] = None) -> Path:
    """Get output directory for a topic.

    Tenant outputs (recommended):
      tenants/<TENANT_ID>/outputs/<topic_id>/

    Legacy:
      outputs/<topic_id>/
    """
    repo_root = get_repo_root()
    if use_tenant_outputs():
        out_root = get_tenant_root(tenant_id) / "outputs"
    else:
        out_root = repo_root / "outputs"
    output_dir = out_root / topic_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def is_topic_enabled(config: Dict[str, Any]) -> bool:
    """
    Check if a topic is enabled based on its configuration.
    
    Args:
        config: Topic configuration dictionary
        
    Returns:
        True if topic is enabled or enabled field is not set (defaults to True for backward compatibility)
    """
    return config.get('enabled', True)


def get_enabled_topics() -> List[str]:
    """
    Get list of all enabled topic IDs.
    
    Returns:
        List of topic IDs that have enabled=true or don't have the enabled field
        (defaults to True for backward compatibility)
    """
    repo_root = get_repo_root()
    topics_dir = repo_root / 'topics'
    enabled_topics = []
    
    for topic_file in sorted(topics_dir.glob('topic-*.json')):
        try:
            config = load_topic_config(topic_file.stem)
            if is_topic_enabled(config):
                enabled_topics.append(config['id'])
        except Exception:
            # Skip topics that can't be loaded
            pass
    
    return enabled_topics
