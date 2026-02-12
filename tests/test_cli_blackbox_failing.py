"""Black-box tests for rigorq CLI tool - EXPECTED FAILURES.

These tests document known issues, limitations, and unimplemented features.
They are expected to fail until the corresponding issues are resolved.

Mark tests with @pytest.mark.xfail(reason="...") to document why they fail.
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


class TestKnownBugs:
    """Tests documenting known bugs that need fixing."""

    @pytest.mark.xfail(reason="Unicode handling not implemented")
    def test_unicode_in_docstrings(self):
        """Test handling of Unicode characters in docstrings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "unicode.py"
            test_file.write_text('''"""Module with émojis 🎉 and spëcial chars."""


def func():
    """Function with Über cool Unicode: café, naïve."""
    pass
''', encoding='utf-8')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should handle Unicode gracefully
            assert exit_code == 0
            assert "UnicodeDecodeError" not in stderr

    @pytest.mark.xfail(reason="Symbolic links not properly resolved")
    def test_follows_symbolic_links(self):
        """Test that symbolic links to Python files are followed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            real_file = Path(tmpdir) / "real.py"
            real_file.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            link_file = Path(tmpdir) / "link.py"
            link_file.symlink_to(real_file)

            exit_code, stdout, stderr = run_rigorq([str(link_file)])

            # Should check the linked file
            assert exit_code == 1
            assert "link.py" in stdout or "real.py" in stdout

    @pytest.mark.xfail(reason="Empty directory handling broken")
    def test_empty_directory(self):
        """Test handling of empty directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "empty"
            empty_dir.mkdir()

            exit_code, stdout, stderr = run_rigorq([str(empty_dir)])

            # Should complete successfully with no files to check
            assert exit_code == 0
            assert "0 files" in stdout or "No Python files" in stdout.lower()

    @pytest.mark.xfail(reason="Race condition with concurrent writes")
    def test_concurrent_file_modification(self):
        """Test behavior when file is modified during checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            # Note: This test would need threading to properly test
            # For now, just verify basic operation doesn't crash
            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            assert exit_code in [0, 1, 2]
            assert "error" not in stderr.lower()


class TestUnimplementedFeatures:
    """Tests for features that should exist but aren't implemented yet."""

    @pytest.mark.xfail(reason="Configuration file support not implemented")
    def test_respects_pyproject_toml_config(self):
        """Test that rigorq respects pyproject.toml configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config file
            config = Path(tmpdir) / "pyproject.toml"
            config.write_text('''[tool.rigorq]
line-length = 100
checks = ["ruff"]
''')

            # Create file with 90-char line (should pass with config)
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\n# ' + 'x' * 85 + '\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)], cwd=tmpdir)

            # Should pass because line-length is configured to 100
            assert exit_code == 0

    @pytest.mark.xfail(reason="Exclude patterns not implemented")
    def test_exclude_patterns(self):
        """Test --exclude flag to ignore certain files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            build_file = Path(tmpdir) / "build.py"
            build_file.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq(
                ["--exclude", "build.py", tmpdir]
            )

            # Should check test.py but not build.py
            assert "test.py" in stdout
            assert "build.py" not in stdout
            assert exit_code == 1

    @pytest.mark.xfail(reason="Include patterns not implemented")
    def test_include_patterns(self):
        """Test --include flag to check only certain files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "test_one.py").write_text('def bad(x,y):\n    """Bad."""\n    return x\n')
            Path(tmpdir, "test_two.py").write_text('def bad(x,y):\n    """Bad."""\n    return x\n')
            Path(tmpdir, "main.py").write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq(
                ["--include", "test_*.py", tmpdir]
            )

            # Should only check test_*.py files
            assert "test_one.py" in stdout
            assert "test_two.py" in stdout
            assert "main.py" not in stdout

    @pytest.mark.xfail(reason="Diff mode not implemented")
    def test_diff_mode_shows_only_changes(self):
        """Test --diff flag to show only modified lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x+y\n')

            exit_code, stdout, stderr = run_rigorq(["--diff", str(test_file)])

            # Should show diff-style output
            assert "+++" in stdout or "---" in stdout
            assert exit_code == 1

    @pytest.mark.xfail(reason="JSON output format not implemented")
    def test_json_output_format(self):
        """Test --format json flag for machine-readable output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq(
                ["--format", "json", str(test_file)]
            )

            # Should output valid JSON
            import json
            data = json.loads(stdout)
            assert "violations" in data
            assert len(data["violations"]) > 0

    @pytest.mark.xfail(reason="Parallel processing not implemented")
    def test_parallel_processing(self):
        """Test --parallel flag for checking multiple files concurrently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files
            for i in range(20):
                Path(tmpdir, f"file_{i}.py").write_text(
                    f'"""Module {i}."""\n\n\ndef func():\n    """Func."""\n    pass\n'
                )

            # Time parallel vs sequential
            import time

            start = time.time()
            run_rigorq(["--parallel", tmpdir])
            parallel_time = time.time() - start

            start = time.time()
            run_rigorq([tmpdir])
            sequential_time = time.time() - start

            # Parallel should be faster (or at least not slower)
            assert parallel_time <= sequential_time * 1.1

    @pytest.mark.xfail(reason="Watch mode not implemented")
    def test_watch_mode(self):
        """Test --watch flag for continuous monitoring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            # Note: This would need subprocess management to test properly
            # For now, just verify the flag is recognized
            exit_code, stdout, stderr = run_rigorq(["--watch", tmpdir])

            # Should not exit with "unknown flag" error
            assert "unrecognized" not in stderr.lower()


class TestEdgeCaseFailures:
    """Edge cases that currently fail but should be handled."""

    @pytest.mark.xfail(reason="Binary file detection broken")
    def test_skips_binary_files(self):
        """Test that binary files with .py extension are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "binary.py"
            # Write binary content
            test_file.write_bytes(b'\x00\x01\x02\x03\xff\xfe')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should skip gracefully, not crash
            assert exit_code in [0, 2]
            assert "binary" in stdout.lower() or "skip" in stdout.lower()

    @pytest.mark.xfail(reason="Circular symlink handling broken")
    def test_handles_circular_symlinks(self):
        """Test handling of circular symbolic links."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_a = Path(tmpdir) / "a"
            dir_b = Path(tmpdir) / "b"
            dir_a.mkdir()
            dir_b.mkdir()

            # Create circular symlinks
            (dir_a / "link_to_b").symlink_to(dir_b)
            (dir_b / "link_to_a").symlink_to(dir_a)

            exit_code, stdout, stderr = run_rigorq([tmpdir])

            # Should detect and skip circular references
            assert exit_code in [0, 2]
            assert "circular" in stderr.lower() or exit_code == 0

    @pytest.mark.xfail(reason="Permission error handling incomplete")
    def test_handles_permission_denied(self):
        """Test handling of files without read permission."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            # Remove read permission
            test_file.chmod(0o000)

            try:
                exit_code, stdout, stderr = run_rigorq([str(test_file)])

                # Should report error gracefully
                assert exit_code == 2
                assert "permission" in stderr.lower()
            finally:
                # Restore permission for cleanup
                test_file.chmod(0o644)

    @pytest.mark.xfail(reason="Very large line handling broken")
    def test_handles_extremely_long_line(self):
        """Test handling of lines exceeding buffer size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "huge_line.py"
            # Create a line with 100k characters
            huge_line = "x = '" + "a" * 100000 + "'"
            test_file.write_text(f'"""Module."""\n\n\n{huge_line}\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should handle without crashing
            assert exit_code in [0, 1, 2]
            assert "MemoryError" not in stderr

    @pytest.mark.xfail(reason="Null byte handling broken")
    def test_handles_null_bytes_in_file(self):
        """Test handling of null bytes in Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "null_bytes.py"
            test_file.write_text('"""Module."""\n\x00\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq([str(test_file)])

            # Should report error appropriately
            assert exit_code == 2
            assert "null" in stderr.lower() or "invalid" in stderr.lower()


class TestOutputFormatIssues:
    """Tests for output formatting issues."""

    @pytest.mark.xfail(reason="Color output not working in non-TTY")
    def test_color_output_in_terminal(self):
        """Test that --color flag produces colored output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq(["--color", str(test_file)])

            # Should contain ANSI color codes
            assert "\033[" in stdout

    @pytest.mark.xfail(reason="Progress bar interferes with output")
    def test_progress_bar_with_quiet(self):
        """Test that progress bar is suppressed in quiet mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files
            for i in range(100):
                Path(tmpdir, f"file_{i}.py").write_text('"""Module."""\n\n\ndef f():\n    """F."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq(["-q", tmpdir])

            # Should not contain progress bar artifacts
            assert "[" not in stdout or "100%" not in stdout

    @pytest.mark.xfail(reason="Relative paths not consistently shown")
    def test_relative_paths_in_output(self):
        """Test that relative paths are shown when using relative input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            test_file = subdir / "test.py"
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq(
                ["subdir/test.py"],
                cwd=tmpdir
            )

            # Should show relative path, not absolute
            assert "subdir/test.py" in stdout
            assert tmpdir not in Path(stdout).parts


class TestFixFlagIssues:
    """Tests for --fix flag issues."""

    @pytest.mark.xfail(reason="Fix breaks docstring formatting")
    def test_fix_preserves_docstring_quotes(self):
        """Test that --fix doesn't change docstring quote style."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            original = 'def func(x,y):\n    """Docstring."""\n    return x + y\n'
            test_file.write_text(original)

            run_rigorq(["--fix", str(test_file)])
            fixed = test_file.read_text()

            # Should preserve triple quotes
            assert '"""' in fixed
            assert "'''" not in fixed

    @pytest.mark.xfail(reason="Fix creates invalid Python")
    def test_fix_maintains_syntax_validity(self):
        """Test that --fix never creates syntax errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def bad(x,y,z):\n    """Bad."""\n    return x+y+z\n')

            run_rigorq(["--fix", str(test_file)])
            fixed = test_file.read_text()

            # Should compile without errors
            compile(fixed, str(test_file), 'exec')

    @pytest.mark.xfail(reason="Fix doesn't preserve trailing newline")
    def test_fix_preserves_trailing_newline(self):
        """Test that --fix preserves file's trailing newline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def func(x,y):\n    """Func."""\n    return x+y\n')

            run_rigorq(["--fix", str(test_file)])
            fixed = test_file.read_text()

            # Should end with newline
            assert fixed.endswith('\n')

    @pytest.mark.xfail(reason="Fix mode doesn't handle multiple fixes correctly")
    def test_fix_applies_multiple_fixes(self):
        """Test that --fix applies all fixable violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            # Multiple fixable issues
            test_file.write_text('def bad(x,y):\n    """Bad."""\n    a=1+2\n    b=3+4\n    return x+y+a+b\n')

            run_rigorq(["--fix", str(test_file)])

            # Check again - should have fewer violations
            exit_code, _, _ = run_rigorq([str(test_file)])

            # Should fix spacing around operators
            fixed = test_file.read_text()
            assert 'a = 1 + 2' in fixed
            assert 'b = 3 + 4' in fixed


class TestChecksFlagIssues:
    """Tests for --checks flag issues."""

    @pytest.mark.xfail(reason="Invalid check name doesn't error properly")
    def test_invalid_check_name(self):
        """Test that invalid check names are reported."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq(
                ["--checks", "nonexistent_check", str(test_file)]
            )

            # Should error with clear message
            assert exit_code == 2
            assert "unknown check" in stderr.lower() or "invalid" in stderr.lower()

    @pytest.mark.xfail(reason="Check categories not properly isolated")
    def test_checks_isolation(self):
        """Test that --checks properly isolates check types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            # Has both ruff and docstring violations
            test_file.write_text('def func(x,y):\n    return x+y\n')

            # Run only ruff checks
            exit_code, stdout, stderr = run_rigorq(
                ["--checks", "ruff", str(test_file)]
            )

            # Should only report ruff violations, not missing docstring
            assert exit_code == 1
            assert "D" not in stdout  # Docstring codes start with D
            assert "RQ" not in stdout  # Custom codes


class TestIntegrationIssues:
    """Integration issues between different components."""

    @pytest.mark.xfail(reason="Fix + checks interaction broken")
    def test_fix_with_specific_checks(self):
        """Test that --fix respects --checks limitation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('def func(x,y):\n    return x+y\n')

            # Fix only ruff issues, not docstrings
            run_rigorq(["--fix", "--checks", "ruff", str(test_file)])

            fixed = test_file.read_text()

            # Should fix spacing but not add docstring
            assert 'x + y' in fixed
            assert '"""' not in fixed

    @pytest.mark.xfail(reason="Quiet mode still shows some output")
    def test_quiet_completely_silent_on_success(self):
        """Test that --quiet produces no output on success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "perfect.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq(["-q", str(test_file)])

            assert exit_code == 0
            assert stdout == ""
            assert stderr == ""

    @pytest.mark.xfail(reason="Directory + file args don't mix well")
    def test_mixed_directory_and_file_args(self):
        """Test checking both directories and specific files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "dir1"
            dir1.mkdir()
            Path(dir1, "file1.py").write_text('"""Module."""\n\n\ndef f():\n    """F."""\n    pass\n')

            file2 = Path(tmpdir) / "file2.py"
            file2.write_text('def bad(x,y):\n    """Bad."""\n    return x\n')

            exit_code, stdout, stderr = run_rigorq([str(dir1), str(file2)])

            # Should check both dir1 and file2
            assert "file1.py" in stdout or "dir1" in stdout
            assert "file2.py" in stdout
            assert exit_code == 1


class TestDocumentationDiscrepancies:
    """Tests where actual behavior differs from documentation."""

    @pytest.mark.xfail(reason="Exit code 3 not implemented per docs")
    def test_exit_code_3_configuration_error(self):
        """Test exit code 3 for configuration errors (per docs)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create invalid config
            config = Path(tmpdir) / "pyproject.toml"
            config.write_text('[tool.rigorq]\ninvalid_option = true\n')

            exit_code, stdout, stderr = run_rigorq([tmpdir])

            # According to docs, should exit with 3
            assert exit_code == 3
            assert "configuration" in stderr.lower()

    @pytest.mark.xfail(reason="Documented flags not implemented")
    def test_verbose_flag(self):
        """Test --verbose flag mentioned in docs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('"""Module."""\n\n\ndef func():\n    """Func."""\n    pass\n')

            exit_code, stdout, stderr = run_rigorq(["-v", str(test_file)])

            # Should provide verbose output
            assert exit_code == 0
            assert len(stdout) > 0
