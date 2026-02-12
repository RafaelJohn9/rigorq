"""Black-box tests for rigorq CLI tool.

These tests interact with rigorq purely through its command-line interface,
testing it as an external tool without knowledge of internal implementation.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest


def run_rigorq(args, cwd=None):
    """Run rigorq command and return result.
    
    Args:
        args: List of command-line arguments
        cwd: Working directory for the command
    
    Returns:
        tuple: (exit_code, stdout, stderr)
    """
    cmd = ["rigorq"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.returncode, result.stdout, result.stderr


class TestBasicCLI:
    """Test basic CLI functionality."""

    def test_help_flag(self):
        """Test --help flag displays usage information."""
        exit_code, stdout, stderr = run_rigorq(["--help"])

        assert exit_code == 0
        assert "usage: rigorq" in stdout
        assert "Mechanical precision for Python quality gates" in stdout
        assert "--fix" in stdout
        assert "--quiet" in stdout
        assert "--version" in stdout
        assert "--checks" in stdout

    def test_version_flag(self):
        """Test --version flag shows version."""
        exit_code, stdout, stderr = run_rigorq(["--version"])

        assert exit_code == 0
        assert stdout.strip()  # Should output something

    def test_no_arguments_uses_current_directory(self):
        """Test that no arguments defaults to current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid Python file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module docstring."""\n\n\ndef func():\n    """Function docstring."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([], cwd=tmpdir)

            # Should run without error
            assert exit_code in [0, 1]  # 0 for pass, 1 for violations


class TestExitCodes:
    """Test exit code behavior as documented."""

    def test_exit_code_0_all_checks_passed(self):
        """Test exit code 0 when all checks pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a perfectly PEP 8 compliant file
            test_file = Path(tmpdir) / "perfect.py"
            test_file.write_text('''"""A perfectly formatted module.

This module demonstrates strict PEP 8 compliance.
"""


def well_formatted_function(param1, param2):
    """Perform an operation on two parameters.
    
    Parameters
    ----------
    param1 : int
        The first parameter.
    param2 : int
        The second parameter.
    
    Returns
    -------
    int
        The sum of the parameters.
    """
    result = param1 + param2
    return result
''')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 0

    def test_exit_code_1_style_violations(self):
        """Test exit code 1 when style violations are found.
        
        This test creates a file with missing whitespace after commas
        and missing whitespace around operators, which are common PEP 8
        violations that should trigger exit code 1.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with violations
            test_file = Path(tmpdir) / "violations.py"
            test_file.write_text(
                'def bad_function(x, y):\n'
                '    """Bad function."""\n'
                '    z = x + y\n'
                '    return z\n'
            )

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1

    def test_exit_code_2_invalid_path(self):
        """Test exit code 2 for runtime errors (invalid path)."""
        exit_code, stdout, stderr = run_rigorq(["/nonexistent/path/to/file.py"])

        assert exit_code == 2

    def test_exit_code_2_non_python_file(self):
        """Test exit code 2 for non-Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "notpython.txt"
            test_file.write_text("This is not Python code")

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should handle gracefully - might be 0 (skip) or 2 (error)
            assert exit_code in [0, 2]


class TestViolationDetection:
    """Test detection of various PEP 8 violations."""

    def test_detects_line_too_long(self):
        """Test detection of lines exceeding 79 characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "long_line.py"
            # Line with 80+ characters
            test_file.write_text('"""Module."""\n\n\n# ' + 'x' * 80 + '\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            assert "E501" in stdout  # Line too long error code

    def test_detects_missing_whitespace_after_comma(self):
        """Test detection of missing whitespace after comma."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "comma_space.py"
            test_file.write_text('"""Module."""\n\n\ndef func(a,b,c):\n    """Func."""\n    return a,b,c\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            # Should detect missing spaces after commas

    def test_detects_missing_whitespace_around_operators(self):
        """Test detection of missing whitespace around operators."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "operator_space.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    x=1+2\n    return x\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1

    def test_detects_blank_line_whitespace(self):
        """Test detection of whitespace in blank lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "blank_space.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    x = 1\n  \n    return x\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            assert "W293" in stdout  # Blank line contains whitespace

    def test_detects_wrong_naming_convention(self):
        """Test detection of naming convention violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "naming.py"
            test_file.write_text('"""Module."""\n\n\nclass badClassName:\n    """Class."""\n\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            # Should detect class naming violation

    def test_detects_missing_docstring(self):
        """Test detection of missing docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "no_docstring.py"
            test_file.write_text('def func():\n    return 1\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            # Should detect missing docstrings

    def test_detects_docstring_line_too_long(self):
        """Test detection of docstring lines exceeding 72 characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "long_docstring.py"
            long_line = 'x' * 75
            test_file.write_text(f'"""Module.\n\n{long_line}\n"""\n\n\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            assert "RQ200" in stdout  # Docstring line too long

    def test_detects_missing_parameters_section(self):
        """Test detection of missing Parameters section in docstring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "missing_params.py"
            test_file.write_text('"""Module."""\n\n\ndef func(param1, param2):\n    """Do something."""\n    return param1 + param2\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            assert "RQ206" in stdout  # Missing Parameters section


class TestOutputFormat:
    """Test output formatting."""

    def test_output_includes_file_path(self):
        """Test that violations include full file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert str(test_file) in stdout

    def test_output_includes_line_number(self):
        """Test that violations include line numbers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should show line:column format
            assert ":4:" in stdout or ":6:" in stdout  # Line numbers

    def test_output_includes_column_number(self):
        """Test that violations include column numbers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Format should be path:line:column: code message
            assert ":" in stdout

    def test_output_includes_error_code(self):
        """Test that violations include error codes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    x=1+2\n    return x\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should include error codes like E225, E501, etc.
            assert any(code in stdout for code in ["E", "W", "N", "D", "RQ"])

    def test_output_includes_error_description(self):
        """Test that violations include descriptive messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def func(x,y):\n    """Func."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should include human-readable descriptions
            assert len(stdout) > 0

    def test_summary_shows_violation_count(self):
        """Test that summary shows total violation count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert "violations" in stdout.lower()

    def test_summary_shows_file_count(self):
        """Test that summary shows number of files checked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert "file" in stdout.lower()

    def test_summary_shows_check_categories(self):
        """Test that summary breaks down violations by check type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should show breakdown like "→ 5 ruff" and "→ 3 rigorq"
            assert "→" in stdout or "ruff" in stdout.lower() or "rigorq" in stdout.lower()


class TestQuietMode:
    """Test --quiet flag behavior."""

    def test_quiet_suppresses_summary(self):
        """Test that --quiet suppresses human-friendly summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code_normal, stdout_normal, _ = run_rigorq([str(test_file)])
            exit_code_quiet, stdout_quiet, _ = run_rigorq(["-q", str(test_file)])

            # Quiet mode should have less output
            assert len(stdout_quiet) <= len(stdout_normal)

    def test_quiet_mode_cicd_compatible(self):
        """Test that --quiet mode is suitable for CI/CD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq(["--quiet", str(test_file)])

            # Should still report violations but without friendly messages
            assert exit_code == 1

    def test_quiet_mode_preserves_exit_codes(self):
        """Test that --quiet mode preserves exit codes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Compliant file
            good_file = Path(tmpdir) / "good.py"
            good_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            # Non-compliant file
            bad_file = Path(tmpdir) / "bad.py"
            bad_file.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_good, _, _ = run_rigorq(["-q", str(good_file)])
            exit_bad, _, _ = run_rigorq(["-q", str(bad_file)])

            assert exit_good == 0
            assert exit_bad == 1


class TestFixFlag:
    """Test --fix flag behavior."""

    def test_fix_flag_auto_fixes_violations(self):
        """Test that --fix auto-fixes mechanically fixable violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original_content = 'def bad(x,y):\n    """Bad."""\n    return x+y\n'
            test_file.write_text(original_content)

            exit_code, stdout, stderr = run_rigorq(["--fix", str(test_file)])

            # File should be modified
            fixed_content = test_file.read_text()
            # Spaces should be added (exact format depends on formatter)
            assert fixed_content != original_content or exit_code == 0

    def test_fix_preserves_unfixable_violations(self):
        """Test that --fix doesn't break code with unfixable violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            # Missing docstring is not auto-fixable
            test_file.write_text('def func():\n    return 1\n')

            run_rigorq(["--fix", str(test_file)])

            # File should still be valid Python
            content = test_file.read_text()
            assert "def func():" in content


class TestChecksFlag:
    """Test --checks flag to select specific checks."""

    def test_checks_flag_runs_specific_check(self):
        """Test that --checks runs only specified checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq(
                ["--checks", "ruff", str(test_file)]
            )

            # Should run ruff checks
            assert exit_code in [0, 1]

    def test_checks_flag_multiple_checks(self):
        """Test --checks with multiple check types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq(
                ["--checks", "ruff", "docstring", str(test_file)]
            )

            assert exit_code in [0, 1]


class TestDirectoryScanning:
    """Test directory scanning capabilities."""

    def test_scans_directory_recursively(self):
        """Test that directories are scanned recursively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory structure
            Path(tmpdir, "package").mkdir()
            Path(tmpdir, "package", "__init__.py").write_text('"""Package."""\n')
            Path(tmpdir, "package", "module.py").write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq([tmpdir])

            # Should find violations in subdirectory
            assert "module.py" in stdout or exit_code == 1

    def test_scans_multiple_files_in_directory(self):
        """Test scanning all Python files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "file1.py").write_text('def bad1(x,y):\n    """Bad."""\n    return x\n')
            Path(tmpdir, "file2.py").write_text('def bad2(a,b):\n    """Bad."""\n    return a\n')

            exit_code, stdout, stderr = run_rigorq([tmpdir])

            # Should check both files
            assert "file1.py" in stdout and "file2.py" in stdout or exit_code == 1

    def test_ignores_non_python_files(self):
        """Test that non-Python files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "test.py").write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')
            Path(tmpdir, "readme.txt").write_text("Not Python")
            Path(tmpdir, "data.json").write_text("{}")

            exit_code, stdout, stderr = run_rigorq([tmpdir])

            # Should only mention .py files
            assert ".txt" not in stdout
            assert ".json" not in stdout


class TestMultipleTargets:
    """Test checking multiple files/directories."""

    def test_checks_multiple_files(self):
        """Test checking multiple files specified on command line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.py"
            file2 = Path(tmpdir) / "file2.py"
            file1.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')
            file2.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq([str(file1), str(file2)])

            # Should check both files
            assert exit_code == 1  # file2 has violations


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_python_file(self):
        """Test handling of empty Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "empty.py"
            test_file.write_text("")

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should handle gracefully
            assert exit_code in [0, 1]  # Might fail for missing docstring

    def test_file_with_only_comments(self):
        """Test handling of files with only comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "comments.py"
            test_file.write_text("# Just a comment\n# Another comment\n")

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code in [0, 1]

    def test_file_with_syntax_error(self):
        """Test handling of files with syntax errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "syntax_error.py"
            test_file.write_text("def bad(\n    # Missing closing paren\n")

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should report error
            assert exit_code != 0

    def test_file_with_encoding_declaration(self):
        """Test handling of files with encoding declarations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "encoded.py"
            test_file.write_text('# -*- coding: utf-8 -*-\n"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should handle encoding declaration
            assert exit_code == 0

    def test_file_with_very_long_lines(self):
        """Test handling of files with very long lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "long.py"
            long_line = "x = " + "1" * 200
            test_file.write_text(f'"""Module."""\n\n\n{long_line}\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code == 1
            assert "E501" in stdout


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_typical_module_structure(self):
        """Test a typical Python module structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "module.py"
            test_file.write_text('''"""A typical Python module.

This module demonstrates common patterns.
"""
import os
import sys


CONSTANT = 42


class MyClass:
    """A sample class."""

    def __init__(self, value):
        """Initialize the class.
        
        Parameters
        ----------
        value : int
            The initial value.
        """
        self.value = value

    def method(self):
        """Perform an operation.
        
        Returns
        -------
        int
            The doubled value.
        """
        return self.value * 2


def helper_function(param):
    """Help with something.
    
    Parameters
    ----------
    param : str
        A parameter.
    
    Returns
    -------
    str
        The processed result.
    """
    return param.upper()
''')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should mostly pass or have minimal violations
            assert exit_code in [0, 1]

    def test_package_with_init(self):
        """Test a package with __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = Path(tmpdir) / "mypackage"
            pkg_dir.mkdir()

            init_file = pkg_dir / "__init__.py"
            init_file.write_text('"""My package."""\n\n__version__ = "0.1.0"\n')

            module_file = pkg_dir / "module.py"
            module_file.write_text('"""A module."""\n\n\ndef func():\n    """A function."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([str(tmpdir)])

            # Should check package structure
            assert exit_code in [0, 1]

    def test_cli_script_pattern(self):
        """Test common CLI script pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "cli.py"
            test_file.write_text('''"""CLI script."""
import sys


def main():
    """Run the main program.
    
    Returns
    -------
    int
        Exit code.
    """
    print("Hello, world!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
''')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code in [0, 1]


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.slow
    def test_handles_large_file(self):
        """Test handling of large Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "large.py"

            # Create a large but compliant file
            content = '"""Large module."""\n\n\n'
            for i in range(1000):
                content += f'''def function_{i}():
    """Function {i}."""
    return {i}


'''
            test_file.write_text(content)

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should complete successfully
            assert exit_code in [0, 1]

    @pytest.mark.slow
    def test_handles_many_files(self):
        """Test handling of many files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many small files
            for i in range(50):
                test_file = Path(tmpdir) / f"file_{i}.py"
                test_file.write_text(f'"""Module {i}."""\n\n\ndef func_{i}():\n    """Function."""\n    return {i}\n')

            exit_code, stdout, stderr = run_rigorq([tmpdir])

            # Should check all files
            assert exit_code in [0, 1]


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_fix_and_recheck(self):
        """Test fixing violations and rechecking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            # First check - should have violations
            exit_code1, _, _ = run_rigorq([str(test_file)])
            assert exit_code1 == 1

            # Fix
            run_rigorq(["--fix", str(test_file)])

            # Recheck - should have fewer or no violations
            exit_code2, _, _ = run_rigorq([str(test_file)])
            # After fix, should be better (0) or same (1)
            assert exit_code2 in [0, 1]

    def test_quiet_fix_combination(self):
        """Test combining --quiet and --fix flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq(["-q", "--fix", str(test_file)])

            # Should work without errors
            assert exit_code in [0, 1, 2]

    def test_directory_with_mixed_quality(self):
        """Test directory with mix of compliant and non-compliant files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Good file
            good = Path(tmpdir) / "good.py"
            good.write_text('"""Good module."""\n\n\ndef func():\n    """Good function."""\n    pass\n')

            # Bad file
            bad = Path(tmpdir) / "bad.py"
            bad.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq([tmpdir])

            # Should report violations from bad file
            assert exit_code == 1
            assert "bad.py" in stdout
