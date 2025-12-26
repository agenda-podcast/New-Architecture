#!/usr/bin/env python3
"""Git helper used by CI to commit outputs after each module.

Best-effort behavior:
  - Stages provided paths (directories are OK)
  - Commits only if there are staged changes
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List, Optional


def _run(cmd: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def git_available(repo_root: Path) -> bool:
    p = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    return p.returncode == 0 and p.stdout.strip() == "true"


def has_staged_changes(repo_root: Path) -> bool:
    p = _run(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    return p.returncode == 0 and bool(p.stdout.strip())


def stage_paths(repo_root: Path, paths: Iterable[Path]) -> None:
    # Stage paths. Directories are ok; git will add recursively.
    rels: List[str] = []
    for p in paths:
        pp = Path(p)
        if not pp.exists():
            continue
        try:
            rels.append(str(pp.relative_to(repo_root)))
        except Exception:
            rels.append(str(pp))
    if not rels:
        return
    _run(["git", "add", "-A", "--"] + rels, cwd=repo_root)


def commit(repo_root: Path, message: str) -> bool:
    if not git_available(repo_root):
        return False
    if not has_staged_changes(repo_root):
        return False
    p = _run(["git", "commit", "-m", message], cwd=repo_root)
    return p.returncode == 0


def commit_paths(repo_root: Path, paths: Iterable[Path], message: str) -> bool:
    stage_paths(repo_root, paths)
    return commit(repo_root, message)
