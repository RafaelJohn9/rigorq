# src/rigorq/engine.py
"""
Orchestrator core — executes all quality checks in sequence and aggregates results.

Execution flow:
  1. Discover Python files (respecting .gitignore/standard exclusions)
  2. If --fix: delegate auto-fixing to Ruff first
  3. Run Ruff style checks (E/W/D/N rules + PLC3002)
  4. Run custom docstring validator (72-char precision via AST)
  5. Aggregate violations → unified reporter
  6. Return Unix-compliant exit code

Exit code semantics:
  0 = All checks passed (clean)
  1 = Style violations found (fixable or not)
  2 = Runtime errors (Ruff missing, invalid paths, etc.)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from .checks.docstrings import validate_docstrings, Violation as DocstringViolation
from .checks.style import run_ruff, Violation as StyleViolation, RuffError
from .reporter import Reporter, ViolationLike
from .utils import find_python_files


class Engine:
    """
    Quality gate orchestrator — executes all checks and aggregates results.
    
    Usage:
        engine = Engine()
        exit_code = engine.validate(Path("."), fix=False, checks=["ruff", "docstring"])
        sys.exit(exit_code)
    """

    def __init__(self, reporter: Reporter | None = None, checks: List[str] = None):
        self.reporter = reporter or Reporter()
        self.default_checks = checks or ["ruff", "docstring"]

    def __init__(self, reporter: Reporter | None = None):
        self.reporter = reporter or Reporter()

    def validate(self, target: Path, fix: bool = False, checks: List[str] = None) -> int:
        """
        Execute full quality gate validation.
        
        Args:
            target: File or directory to validate
            fix: Whether to auto-fix violations before validation
            checks: List of checks to run (e.g., ["ruff", "docstring"])
        
        Returns:
            Unix exit code (0 = clean, 1 = violations, 2 = errors)
        """
        checks = checks or ["ruff", "docstring"]  # Default checks

        # Validate target exists
        if not target.exists():
            self.reporter.add_error(f"Path does not exist: {target}")
            self.reporter.print()
            return self.reporter.exit_code()

        # Discover Python files
        try:
            files = find_python_files(target)
        except Exception as e:
            self.reporter.add_error(f"File discovery failed: {e}")
            self.reporter.print()
            return 2

        if not files:
            if not self.reporter._quiet:
                print(f"✓ No Python files found in {target}", file=sys.stderr)
            return 0

        # Phase 0: Auto-fix (if requested)
        if fix and "ruff" in checks:
            self._run_fix_phase(files)

        # Run specified checks
        if "ruff" in checks:
            self._run_ruff_phase(files)
        if "docstring" in checks:
            self._run_docstring_phase(files)

        # Report results
        self.reporter.print()
        return self.reporter.exit_code()

    def _run_fix_phase(self, files: List[Path]) -> None:
        """Delegate auto-fixing to Ruff before validation."""
        if not self.reporter._quiet:
            print("🔧 Auto-fixing violations...", file=sys.stderr)

        try:
            run_ruff(files, fix=True)
        except RuffError as e:
            self.reporter.add_error(str(e))
        except Exception as e:
            self.reporter.add_error(f"Auto-fix failed: {e}")

    def _run_ruff_phase(self, files: List[Path]) -> None:
        """Execute Ruff checks and aggregate violations."""
        try:
            violations: List[StyleViolation] = run_ruff(files, fix=False)
            for v in violations:
                self.reporter.add_violation(v)
        except RuffError as e:
            self.reporter.add_error(str(e))
        except Exception as e:
            self.reporter.add_error(f"Ruff check failed: {e}")

    def _run_docstring_phase(self, files: List[Path]) -> None:
        """
        Execute custom docstring validator — enforces 72-char limit
        *only* on true docstrings (not comments or regular strings).
        """
        for file in files:
            try:
                violations: List[DocstringViolation] = validate_docstrings(file)
                for v in violations:
                    self.reporter.add_violation(v)
            except Exception as e:
                self.reporter.add_error(f"Docstring validation failed for {file}: {e}")

def validate(target: Path, fix: bool = False, checks: List[str] = None) -> int:
    """
    CLI entry point for validation.
    
    Args:
        target: File or directory to validate
        fix: Whether to auto-fix violations before validation
        checks: List of checks to run (e.g., ["ruff", "docstring"])
    
    Returns:
        Unix exit code (0 = clean, 1 = violations, 2 = errors)
    """
    engine = Engine()
    return engine.validate(target, fix, checks)
