"""
Unified violation reporter — formats violations from all checks into a
consistent, tooling-friendly output matching compiler conventions.

Output format (compatible with editors/CI):
  path/to/file.py:10:5: RQ200 Docstring line too long (73 > 72)

Features:
  - Standard compiler format (file:line:col: code message)
  - Automatic colorization (TTY detection)
  - Summary statistics with severity breakdown
  - Exit code semantics (0 = clean, 1 = violations, 2 = errors)
  - Quiet mode for CI/CD pipelines
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, runtime_checkable


@runtime_checkable
class ViolationLike(Protocol):
    """
    Minimal protocol for violation objects — enables duck typing across checks.
    
    Required attributes (all checks must provide these):
      - path: Path | str
      - line: int
      - column: int
      - code: str  (e.g., "E501", "RQ200")
      - message: str
      - tool: str  (optional, defaults to "rigorq")
    """

    path: Path | str
    line: int
    column: int
    code: str
    message: str
    tool: str


@dataclass(frozen=True)
class ViolationSummary:
    """Aggregated statistics for reporting."""

    total: int
    by_tool: dict[str, int]
    files_affected: int


class Reporter:
    """
    Unified violation reporter with intelligent output formatting.
    
    Usage:
        reporter = Reporter()
        reporter.add_violations(ruff_violations)
        reporter.add_violations(docstring_violations)
        reporter.print()
        exit_code = reporter.exit_code()
    """

    def __init__(self, *, color: bool | None = None, quiet: bool = False):
        """
        Initialize reporter.
        
        Args:
            color: Enable/disable color output. None = auto-detect TTY.
            quiet: Suppress all output except violations (for CI/CD).
        """
        self._violations: List[ViolationLike] = []
        self._errors: List[str] = []  # Runtime errors (not style violations)
        self._color = sys.stdout.isatty() if color is None else color
        self._quiet = quiet

    def add_violation(self, violation: ViolationLike) -> None:
        """Register a single violation."""
        self._violations.append(violation)

    def add_violations(self, violations: List[ViolationLike]) -> None:
        """Register multiple violations."""
        self._violations.extend(violations)

    def add_error(self, message: str) -> None:
        """Register a runtime error (e.g., file not found)."""
        self._errors.append(message)

    def is_clean(self) -> bool:
        """Return True if no violations or errors exist."""
        return len(self._violations) == 0 and len(self._errors) == 0

    def exit_code(self) -> int:
        """
        Determine exit code per Unix conventions:
          0 = clean (no violations/errors)
          1 = style violations found
          2 = runtime errors (e.g., invalid paths, tool failures)
        """
        if self._errors:
            return 2
        return 0 if self._violations else 0

    def _format_violation(self, v: ViolationLike) -> str:
        """
        Format violation in standard compiler format:
          file.py:10:5: CODE message
        
        Colorization:
          path       → dim white
          line:col   → bold yellow
          code       → bold cyan (Ruff) / bold magenta (rigorq custom)
          message    → default
        """
        path = str(v.path)
        line = v.line
        col = v.column
        code = v.code
        msg = v.message

        # Color codes (ANSI)
        if self._color:
            DIM = "\033[2m"
            BOLD_YELLOW = "\033[1;33m"
            BOLD_CYAN = "\033[1;36m"
            BOLD_MAGENTA = "\033[1;35m"
            RESET = "\033[0m"

            # Tool-specific code coloring
            if code.startswith(("E", "W", "D", "N")):  # Ruff rules
                code_fmt = f"{BOLD_CYAN}{code}{RESET}"
            else:  # rigorq custom rules (RQxxx)
                code_fmt = f"{BOLD_MAGENTA}{code}{RESET}"

            return (
                f"{DIM}{path}{RESET}:{BOLD_YELLOW}{line}{RESET}:"
                f"{BOLD_YELLOW}{col}{RESET}: {code_fmt} {msg}"
            )
        else:
            return f"{path}:{line}:{col}: {code} {msg}"

    def _generate_summary(self) -> ViolationSummary:
        """Aggregate violation statistics."""
        by_tool = {}
        files = set()

        for v in self._violations:
            tool = getattr(v, "tool", "rigorq")
            by_tool[tool] = by_tool.get(tool, 0) + 1
            files.add(str(v.path))

        return ViolationSummary(
            total=len(self._violations),
            by_tool=by_tool,
            files_affected=len(files)
        )

    def print(self) -> None:
        """Render all violations and summary to stdout/stderr."""
        # Print violations first (tooling expects these on stdout)
        for v in sorted(self._violations, key=lambda x: (str(x.path), x.line, x.column)):
            print(self._format_violation(v))

        # Print runtime errors to stderr
        if self._errors:
            for err in self._errors:
                print(f"error: {err}", file=sys.stderr)

        # Print summary unless quiet mode
        if not self._quiet and (self._violations or self._errors):
            self._print_summary()

    def _print_summary(self) -> None:
        """Render human-friendly summary after violations."""
        if not self._violations and not self._errors:
            # Clean run — only show success in non-quiet mode
            if not self._quiet:
                icon = "✓" if self._color else "PASS"
                color = "\033[1;32m" if self._color else ""
                reset = "\033[0m" if self._color else ""
                print(f"\n{color}{icon}{reset} rigorq: All checks passed", file=sys.stderr)
            return

        summary = self._generate_summary()

        # Build summary lines
        lines = []

        if self._violations:
            lines.append(f"Found {summary.total} violation{'s' if summary.total != 1 else ''} in {summary.files_affected} file{'s' if summary.files_affected != 1 else ''}")

            # Breakdown by tool
            for tool, count in sorted(summary.by_tool.items()):
                tool_name = "ruff" if tool == "ruff" else "rigorq"
                lines.append(f"  → {count:3d} {tool_name}")

        if self._errors:
            lines.append(f"Encountered {len(self._errors)} runtime error{'s' if len(self._errors) != 1 else ''}")

        # Format with colors
        if self._color:
            BOLD_RED = "\033[1;31m"
            BOLD_WHITE = "\033[1;37m"
            DIM = "\033[2m"
            RESET = "\033[0m"

            icon = f"{BOLD_RED}ⅹ{RESET}"
            header = f"\n{icon} rigorq: Quality checks failed"
            detail_lines = [f"{DIM}{line}{RESET}" for line in lines]
        else:
            icon = "ⅹ"
            header = f"\n{icon} rigorq: Quality checks failed"
            detail_lines = lines

        print(header, file=sys.stderr)
        for line in detail_lines:
            print(line, file=sys.stderr)

    def print_fix_summary(self, fixed: int, remaining: int) -> None:
        """
        Print auto-fix summary after --fix run.
        
        Args:
            fixed: Number of violations auto-fixed
            remaining: Number of violations that couldn't be fixed
        """
        if self._quiet:
            return

        if self._color:
            GREEN = "\033[32m"
            YELLOW = "\033[33m"
            RESET = "\033[0m"
            BOLD = "\033[1m"
        else:
            GREEN = YELLOW = BOLD = RESET = ""

        if fixed > 0 and remaining == 0:
            print(f"\n{GREEN}{BOLD}✓{RESET} Fixed {fixed} violation{'s' if fixed != 1 else ''}", file=sys.stderr)
        elif fixed > 0 and remaining > 0:
            print(
                f"\n{YELLOW}{BOLD}⚠{RESET} Fixed {fixed} violation{'s' if fixed != 1 else ''}, "
                f"{remaining} remaining",
                file=sys.stderr
            )
        elif remaining > 0:
            print(
                f"\n{YELLOW}{BOLD}ⅹ{RESET} Could not auto-fix {remaining} violation{'s' if remaining != 1 else ''}",
                file=sys.stderr
            )
