"""
rigorq CLI — mechanical precision for Python quality gates.

Philosophy:
  Enforce all *mechanically checkable* PEP 8 rules to the last detail.
  Document unenforceable rules explicitly — no false promises.

Usage:
  rigorq [PATH] [--fix] [--quiet] [--version]

Examples:
  rigorq .                 # Validate entire project
  rigorq src/utils.py      # Validate single file
  rigorq --fix .           # Auto-fix violations where possible
  rigorq --quiet .         # CI/CD mode (violations only, no summaries)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rigorq import __version__
from rigorq.engine import validate


def _build_parser() -> argparse.ArgumentParser:
    """Construct argument parser with precise help text."""
    parser = argparse.ArgumentParser(
        prog="rigorq",
        description="Mechanical precision for Python quality gates",
        epilog=(
            "Exit codes:\n"
            "  0 = All checks passed\n"
            "  1 = Style violations found\n"
            "  2 = Runtime errors (missing Ruff, invalid paths, etc.)\n\n"
            "Philosophy: Enforces all mechanically checkable PEP 8 rules.\n"
            "Subjective rules (e.g., 'readability counts') require human judgment.\n"
            "See: https://peps.python.org/pep-0008/#a-foolish-consistency-is-the-hobgoblin-of-little-minds"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="File or directory to validate (default: current directory)",
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix violations where mechanically possible (via Ruff)",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress human-friendly summaries (CI/CD mode)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"rigorq {__version__}",
        help="Show version and exit",
    )

    parser.add_argument(
        "--checks",
        nargs='*',
        default=["ruff", "docstring"],
        help="List of checks to run (e.g., ['ruff', 'docstring'])",
    )

    return parser

def _validate_path(path: Path) -> None:
    """Early validation of target path with helpful error messages."""
    if not path.exists():
        print(f"error: Path does not exist: {path}", file=sys.stderr)
        sys.exit(2)

    if path.is_file() and path.suffix != ".py":
        print(f"error: Not a Python file: {path}", file=sys.stderr)
        sys.exit(2)

def main() -> None:
    """CLI entry point — validates arguments and delegates to engine."""
    parser = _build_parser()

    # Special case: `rigorq --` should show help (argparse handles this)
    args = parser.parse_args()

    # Early path validation (fail fast)
    try:
        _validate_path(args.path)
    except SystemExit as e:
        sys.exit(e.code)

    # Execute quality gate
    try:
        exit_code = validate(
            target=args.path,
            fix=args.fix,
            checks=args.checks,
        )
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nerror: Interrupted by user", file=sys.stderr)
        sys.exit(130)  # 128 + SIGINT
    except Exception as e:
        # Unexpected errors — show traceback only in debug mode
        if "--debug" in sys.argv or "-d" in sys.argv:
            raise
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        print("Run with --debug for full traceback", file=sys.stderr)
        sys.exit(2)
    main()
