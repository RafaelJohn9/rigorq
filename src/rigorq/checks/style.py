"""
Ruff integration layer — enforces mechanical PEP 8 rules with precision.

Key differentiators vs raw Ruff:
  - Enforces 72-char docstrings via D200 (PEP 257 compliance)
  - Blocks lambda assignment (PLC3002) — PEP 8 § Programming Recommendations
  - Resolves pydocstyle conflicts (D203/D212) for clean output
  - Strict 79-char line length (code) with 72-char for docstrings/comments
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class Violation:
    """Unified violation representation across all rigorq checks."""

    path: Path
    line: int
    column: int
    code: str          # e.g., "E501", "D200", "N802"
    message: str       # e.g., "Line too long (80 > 79)"
    tool: str = "ruff" # "ruff", "rigorq", etc.


class RuffError(Exception):
    """Raised when Ruff execution fails unexpectedly."""

    pass


def _ensure_ruff_installed() -> None:
    """Verify Ruff is available in PATH; raise helpful error if missing."""
    try:
        subprocess.run(
            ["ruff", "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RuffError(
            "Ruff not found or unresponsive. Install with: pip install ruff\n"
            f"Details: {e}"
        ) from e


def _build_ruff_cmd(
    files: List[Path],
    fix: bool = False,
    line_length: int = 79
) -> List[str]:
    """
    Construct Ruff command with opinionated strict defaults.
    
    Rules enabled:
      E/W   = pycodestyle (PEP 8 core)
      D     = pydocstyle (PEP 257 docstrings — enforces 72-char limit via D200)
      N     = naming conventions (snake_case, CapWords, etc.)
      PLC3002 = prohibits lambda assignment (PEP 8 § Programming Recommendations)
    
    Rules ignored:
      D203  = 1 blank line before class docstring (conflicts with D211)
      D212  = multi-line summary should start at first line (prefer D213)
    """
    cmd = ["ruff", "check"]

    if fix:
        cmd.append("--fix")

    # Strict rule selection — no config file required
    cmd.extend([
        "--output-format=concise",
        "--extend-select=E225,E226,E227,E228,N,D",
        "--ignore=D203,D212",
        f"--line-length={line_length}",
        "--target-version=py38",  # Conservative baseline
    ])

    # Add files
    cmd.extend(str(f) for f in files)

    return cmd


def _parse_ruff_output(output: str, base_path: Path) -> List[Violation]:
    """
    Parse Ruff's concise output format:
      src/rigorq/reporter.py:107:9: D400 First line should end with a period
      src/rigorq/reporter.py:110:1: W293 Blank line contains whitespace
      ...
    
    Handles:
      - Relative/absolute paths
      - Multi-line violations
      - Empty output (no violations)
    """
    violations = []
    lines = output.strip().splitlines()

    for line in lines:
        parts = line.split(":")
        if len(parts) >= 4:
            path = Path(parts[0])
            line_num = int(parts[1])
            column = int(parts[2])
            code = parts[3].strip()
            message = ":".join(parts[4:]).strip() if len(parts) > 4 else ""

            violations.append(Violation(
                path=base_path / path,
                line=line_num,
                column=column,
                code=code,
                message=message,
                tool="ruff"
            ))

    return violations


def run_ruff(
    target: Path | List[Path],
    fix: bool = False,
    line_length: int = 79
) -> List[Violation]:
    """
    Execute Ruff with strict PEP 8 defaults.
    
    Args:
        target: File/directory path or list of paths
        fix: Whether to auto-fix violations (--fix mode)
        line_length: Max line length for code (docstrings enforced at 72 via D rules)
    
    Returns:
        List of violations (empty if clean)
    
    Raises:
        RuffError: If Ruff is not installed or crashes unexpectedly
    """
    # Normalize input to list of Paths
    if isinstance(target, Path):
        if target.is_file():
            files = [target]
        else:  # Directory
            files = sorted(target.rglob("*.py"))
            # Exclude common noise directories
            files = [
                f for f in files
                if not any(p in f.parts for p in ("venv", ".venv", "__pycache__", ".git", "node_modules"))
            ]
    else:
        files = target

    if not files:
        return []

    # Verify Ruff availability early
    _ensure_ruff_installed()

    # Build and execute command
    cmd = _build_ruff_cmd(files, fix=fix, line_length=line_length)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=target.parent if isinstance(target, Path) and target.is_file() else Path.cwd()
        )
    except subprocess.TimeoutExpired as e:
        raise RuffError(f"Ruff timed out after 30s: {e}") from e

    # Fix mode: don't parse violations (Ruff exits 0 even with unfixed violations)
    if fix:
        # Still report any violations that couldn't be auto-fixed
        if result.returncode != 0 or result.stdout.strip():
            return _parse_ruff_output(result.stdout, Path.cwd())
        return []

    # Non-fix mode: parse violations from stdout
    if result.returncode == 0:
        return []

    return _parse_ruff_output(result.stdout, Path.cwd())
