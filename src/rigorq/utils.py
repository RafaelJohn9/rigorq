"""
File discovery utilities — intelligently locate Python files while respecting
standard project exclusions (venv, .git, etc.) without requiring .gitignore parsing.

Design principles:
  - Zero external dependencies (pure pathlib)
  - Fast traversal (avoids unnecessary stat calls)
  - Respects universal Python project conventions
  - Graceful degradation on permission errors
  - Cross-platform (Windows/Linux/macOS)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Set


# Standard exclusion patterns matching Python project conventions
_EXCLUDE_DIRS: Set[str] = {
    # Virtual environments
    "venv", ".venv", "env", ".env", "virtualenv",
    # Version control
    ".git", ".hg", ".svn", ".bzr",
    # Build artifacts
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "build", "dist", "egg-info", ".eggs",
    # Dependency directories
    "node_modules", "bower_components",
    # IDE/editor artifacts
    ".vscode", ".idea", ".vs", ".sublime-project", ".sublime-workspace",
    # OS artifacts
    ".DS_Store", "Thumbs.db",
}

_EXCLUDE_FILES: Set[str] = {
    # Bytecode
    "*.pyc", "*.pyo", "*.pyd",
    # Lockfiles (not Python source)
    "Pipfile.lock", "poetry.lock", "package-lock.json",
}


def _is_excluded(path: Path, base: Path) -> bool:
    """
    Determine if a path should be excluded from traversal.
    
    Checks:
      - Direct name matches in _EXCLUDE_DIRS/_EXCLUDE_FILES
      - Hidden directories/files (starting with .)
      - Symlinks (avoid traversal loops)
      - Non-regular files (sockets, devices, etc.)
    
    Args:
        path: Absolute path to check
        base: Project root (for relative path calculations)
    
    Returns:
        True if path should be skipped
    """
    try:
        # Resolve symlink status without following
        if path.is_symlink():
            return True

        # Skip non-regular files (devices, sockets, etc.)
        if path.exists() and not (path.is_file() or path.is_dir()):
            return True

        # Check direct name matches
        name = path.name

        # Hidden files/dirs (except .git which is already in _EXCLUDE_DIRS)
        if name.startswith(".") and name != ".git":
            return True

        # Explicit dir exclusions
        if path.is_dir() and name in _EXCLUDE_DIRS:
            return True

        # Explicit file pattern exclusions
        if path.is_file():
            for pattern in _EXCLUDE_FILES:
                if pattern.startswith("*."):
                    suffix = pattern[1:]  # ".pyc"
                    if name.endswith(suffix):
                        return True
                elif name == pattern:
                    return True

        return False
    except (OSError, PermissionError):
        # Skip unreadable paths gracefully
        return True


def find_python_files(target: Path | str) -> List[Path]:
    """
    Discover all .py files recursively from target path.
    
    Behavior:
      - File target: returns single-item list if .py, else empty
      - Directory target: recursively finds all .py files respecting exclusions
      - Skips unreadable paths silently (avoids crashing on permission errors)
      - Returns absolute, resolved paths sorted lexicographically
    
    Args:
        target: Path to file or directory
    
    Returns:
        Sorted list of absolute Python file paths
    
    Raises:
        ValueError: If target doesn't exist
    """
    target = Path(target).resolve()

    if not target.exists():
        raise ValueError(f"Path does not exist: {target}")

    # Single file target
    if target.is_file():
        if target.suffix == ".py":
            return [target]
        return []

    # Directory target — recursive discovery
    python_files: List[Path] = []

    try:
        # Walk manually for precise control over exclusions
        for root, dirs, files in os.walk(target, topdown=True):
            root_path = Path(root)

            # Modify dirs in-place to prune excluded directories
            dirs[:] = [
                d for d in dirs
                if not _is_excluded(root_path / d, target)
            ]

            # Collect .py files
            for filename in files:
                file_path = root_path / filename
                if file_path.suffix == ".py" and not _is_excluded(file_path, target):
                    python_files.append(file_path.resolve())

    except (OSError, PermissionError) as e:
        raise RuntimeError(f"Failed to traverse {target}: {e}") from e

    # Return sorted for deterministic output
    return sorted(python_files)


def get_project_root(path: Path | str) -> Path:
    """
    Heuristically determine project root by searching upward for markers.
    
    Search markers (in order):
      1. pyproject.toml
      2. setup.py / setup.cfg
      3. .git directory
      4. Current directory (fallback)
    
    Args:
        path: Starting path for search
    
    Returns:
        Absolute path to detected project root
    """
    current = Path(path).resolve()

    # Search upward to filesystem root
    while current != current.parent:
        if any((current / marker).exists() for marker in [
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            ".git",
        ]):
            return current
        current = current.parent

    # Fallback to original path's parent
    return Path(path).resolve().parent


def is_python_file(path: Path | str) -> bool:
    """
    Quick check if path is a Python source file.
    
    Args:
        path: File path to check
    
    Returns:
        True if file has .py extension and isn't excluded
    """
    path = Path(path)
    return (
        path.is_file()
        and path.suffix == ".py"
        and not _is_excluded(path.resolve(), path.resolve().parent)
    )
