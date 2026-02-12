"""
Extensible docstring validator framework — enforces multiple PEP 257 and PEP 8 rules.

This module provides:
  - Precise docstring detection using AST + tokenization
  - Extensible validator system (line-by-line and whole-docstring)
  - Support for all docstring contexts (module/class/function/method)
  - Exact source line numbers and column positions
  
Key features:
  - Validates ONLY true docstrings (first statement of module/class/function)
  - Handles both \"\"\" and ''' delimiters with any indentation
  - Extensible rule system via BaseValidator abstract class
  - Reports precise violation locations with context

**IMPORTANT - Validates ALL Docstrings by Default:**
  By default, this validator checks EVERY docstring in your code, including:
    ✓ Public functions, classes, methods
    ✓ Private functions, classes, methods (starting with _)
    ✓ Dunder methods (__init__, __str__, etc.)
    ✓ Module-level docstrings
  
  To skip private items, use: validate_docstrings(path, skip_private=True)
  However, validating ALL docstrings is recommended for consistency!

PEP references:
  - PEP 8: Style Guide (line length limits)
  - PEP 257: Docstring Conventions
"""
from __future__ import annotations

import ast
import re
import tokenize
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .style import Violation

@dataclass
class DocstringInfo:
    """
    Complete information about a detected docstring.
    
    Parameters
    ----------
        node : ast.AST
            The AST node associated with the docstring

        token : tokenize.TokenInfo
            Tokenize info for the string token

        raw_lines : List[Tuple[int, str]]
            List of (line_number, raw_content) tuples

        content : str
            Cleaned docstring content (no delimiters)

        start_line : int
            First line number

        end_line : int
            Last line number

        indent_level : int
            Base indentation level (spaces)

        node_type : str
            Type of node (module/class/function/method)

        node_name : str
            Name of the node (or '<module>' for modules)
    """
    node: ast.AST
    token: tokenize.TokenInfo
    raw_lines: List[Tuple[int, str]]
    content: str
    start_line: int
    end_line: int
    indent_level: int
    node_type: str
    node_name: str


class BaseValidator(ABC):
    """
    Abstract base class for docstring validators.
    
    Subclasses must implement either validate_line() for line-by-line
    checks or validate_docstring() for whole-docstring checks, or both.
    """
    
    @property
    @abstractmethod
    def code(self) -> str:
        """Violation code (e.g., 'RQ200')."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the rule."""
        pass
    
    def validate_line(
        self,
        line_num: int,
        raw_line: str,
        docstring_info: DocstringInfo,
        path: Path
    ) -> Optional[Violation]:
        """
        Validate a single line of a docstring.
        
        Args:
            line_num: Source line number
            raw_line: Raw line content including indentation
            docstring_info: Complete docstring context
            path: File path for violation reporting
            
        Returns:
            Violation if rule is violated, None otherwise
        """
        return None
    
    def validate_docstring(
        self,
        docstring_info: DocstringInfo,
        path: Path
    ) -> List[Violation]:
        """
        Validate entire docstring as a whole.
        
        Args:
            docstring_info: Complete docstring information
            path: File path for violation reporting
            
        Returns:
            List of violations (may be empty)
        """
        return []


class MaxLineLengthValidator(BaseValidator):
    """Enforces maximum line length for docstrings (PEP 8)."""
    
    def __init__(self, max_length: int = 72):
        self.max_length = max_length
    
    @property
    def code(self) -> str:
        return "RQ200"
    
    @property
    def description(self) -> str:
        return f"Docstring line too long (max {self.max_length} chars)"
    
    def validate_line(
        self,
        line_num: int,
        raw_line: str,
        docstring_info: DocstringInfo,
        path: Path
    ) -> Optional[Violation]:
        """Check if line exceeds maximum length."""
        # Skip delimiter-only lines
        if raw_line in ('"""', "'''", '""""""', "''''''"):
            return None
        
        # Count visual line length (including indentation)
        # line_length = len(raw_line.rstrip('\n\r'))
        line_length = len(raw_line)
        
        if line_length > self.max_length:
            return Violation(
                path=path,
                line=line_num,
                column=0,
                code=self.code,
                message=f"{self.description} ({line_length} > "
                        f"{self.max_length})",
                tool="rigorq"
            )
        
        return None

class FirstLineSummaryValidator(BaseValidator):
    """
    Validates that docstring starts with a one-line summary (PEP 257)
    where it can occupy more than one line.
    
    Rules:
      - First line should be a brief summary
      - Should end with a period (optional enforcement)
      - Should fit on one line or multiple lines
    """
    
    def __init__(self, require_period: bool = True):
        self.require_period = require_period
    
    @property
    def code(self) -> str:
        return "RQ202"
    
    @property
    def description(self) -> str:
        return "Docstring must start with one-line summary"
    
    def validate_docstring(
        self,
        docstring_info: DocstringInfo,
        path: Path
    ) -> List[Violation]:
        """Check that first line is a proper summary."""
        violations = []
        
        # Get first content lines (skip opening delimiters)
        first_lines = []
        for _, raw_line in docstring_info.raw_lines:
            stripped = raw_line.strip()
            # Break on empty line
            if len(stripped) == 0:
                break

            if stripped.startswith(('"""', "'''")):
                # One-line docstring: """summary."""
                if stripped.endswith(('"""', "'''")) and len(stripped) > 6:
                    inner = stripped[3:-3].strip()
                    if inner:
                        first_lines.append(inner)
                    break

                # Multi-line opening delimiter
                content_after_delim = stripped[3:].strip()
                if content_after_delim:
                    first_lines.append(content_after_delim)
                continue
            else:
                first_lines.append(stripped)


        if not first_lines:
            violations.append(Violation(
                path=path,
                line=docstring_info.start_line,
                column=0,
                code=self.code,
                message="Docstring is empty or has no summary line",
                tool="rigorq"
            ))
            return violations
        
        # Check if the last line ends with a period (if required)
        if first_lines and self.require_period and not first_lines[-1].rstrip().endswith('.'):
            violations.append(Violation(
            path=path,
            line=docstring_info.start_line,
            column=0,
            code="RQ203",
            message="Last line of summary should end with a period",
            tool="rigorq"
            ))
        
        return violations


class ParameterReturnDefinitionValidator(BaseValidator):
    """Ensures strict NumPy-style parameter/return sections."""

    @property
    def code(self) -> str:
        return "RQ206"

    @property
    def description(self) -> str:
        """Docstring must define parameters and return values in strict NumPy format."""
        return "Docstring must follow strict NumPy parameter/return format"

    def validate_docstring(
        self,
        docstring_info: DocstringInfo,
        path: Path
    ) -> List[Violation]:
        """Validate NumPy-style parameter and return sections."""

        valid_nodes = {
            "function", "async_function", "method",
            "async_method", "class",
        }

        violations: List[Violation] = []

        if docstring_info.node_type not in valid_nodes:
            return violations


        # Check if node type has parameters/returns
        # For classes, only validate __init__ method parameters
        if docstring_info.node_type == "class":
            # Find __init__ method in class body
            has_init = any(
            isinstance(item, ast.FunctionDef) and item.name == "__init__"
            for item in docstring_info.node.body
            )
            if not has_init:
                return violations
            
            # Get __init__ node to check for parameters
            init_node = next(
            item for item in docstring_info.node.body
            if isinstance(item, ast.FunctionDef) and item.name == "__init__"
            )
            has_params = len(init_node.args.args) > 1  # Skip 'self'
            if not has_params:
             return violations
        else:
            # For functions/methods, check if they have parameters
            is_method = False

            if docstring_info.node_type in {"function", "async_function"} and docstring_info.node.args.args:
                is_method = True if docstring_info.node.args.args[0].arg in {"self", "cls"} else False 

            # Methods have 'self' as first param, so check for > 1
            min_params = 2 if is_method else 1
            has_params = len(docstring_info.node.args.args) >= min_params
            
            if not has_params:
                return violations
        

        lines = [raw for _, raw in docstring_info.raw_lines]
        i = 0
        n = len(lines)

        def error(line: int, msg: str) -> None:
            violations.append(Violation(
                path=path,
                line=line,
                column=0,
                code=self.code,
                message=msg,
                tool="rigorq"
            ))

        # ---- Find Parameters ----
        while i < n and lines[i].strip() != "Parameters":
            i += 1


        if i == n:
            if docstring_info.node_type in valid_nodes:
                error(docstring_info.start_line,
                      "Missing 'Parameters' section in docstring")
            return violations

        # Expect underline
        if i + 1 >= n or lines[i + 1].strip() != "----------":
            error(docstring_info.start_line + i + 1,
                  "Missing dashed underline under 'Parameters'")
            return violations

        i += 2  # Move to first param line

        # ---- Parameter definition ----
        if i >= n or " : " not in lines[i]:
            error(docstring_info.start_line + i,
                  "Parameter must be in format '<name> : <type>'")
            return violations

        name, type_ = lines[i].strip().split(" : ", 1)
        if not name or not type_:
            error(docstring_info.start_line + i,
                  "Parameter must be in format '<name> : <type>'")
            return violations

        i += 1

        # ---- Parameter description ----
        if i >= n or not lines[i].startswith("    "):
            error(docstring_info.start_line + i,
                  "Parameter description must be indented by 4 spaces")
            return violations

        # Skip description block
        while i < n and lines[i].startswith("    "):
            i += 1

        if docstring_info.node_type != "class":
            # ---- Blank line ----
            if i < n and lines[i].strip() != "":
                error(docstring_info.start_line + i,
                    "Expected blank line after parameter block")
                return violations

            i += 1
            # ---- Returns ----
            if i >= n or lines[i].strip() != "Returns":
                error(docstring_info.start_line + i,
                "Missing 'Returns' section after parameters")
                return violations

            if i + 1 >= n or lines[i + 1].strip() != "-------":
                error(docstring_info.start_line + i + 1,
                "Missing dashed underline under 'Returns'")
                return violations

            i += 2

            # ---- Return type ----
            if i >= n or lines[i].strip() == "":
                error(docstring_info.start_line + i,
                "Return type must be specified")
                return violations

            i += 1

            # ---- Return description ----
            if i >= n or not lines[i].startswith("    "):
                error(docstring_info.start_line + i,
                "Return description must be indented by 4 spaces")
                return violations
        return violations


# --- Core Docstring Detection Logic ---

def _is_docstring_candidate(
    node: ast.AST,
    string_token: tokenize.TokenInfo,
    next_stmt: Optional[ast.stmt]
) -> bool:
    """
    Determine if a STRING token is a true docstring per PEP 257.
    
    Rules:
      - Must be first statement in module/class/function body
      - Must appear at column 0 or matching block indentation
      - Must be followed by actual code/statements (not just pass/...)
    """
    # Only these nodes can have docstrings
    if not isinstance(node, (
        ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef
    )):
        return False

    # Must be first statement in body
    body = node.body if hasattr(node, 'body') else []
    if not body or not isinstance(body[0], ast.Expr):
        return False

    # Must be a Constant/String
    expr = body[0]
    if not hasattr(expr, 'value'):
        return False

    value = expr.value
    is_string = (
        isinstance(value, str) or
        (hasattr(ast, 'Constant') and isinstance(value, ast.Constant) 
         and isinstance(value.value, str))
    )
    if not is_string:
        return False

    # Token must align with AST position
    node_start_line = node.lineno if hasattr(node, 'lineno') else 1
    token_line = string_token.start[0]

    # Module: allow shebang/encoding comments before docstring
    if isinstance(node, ast.Module):
        return token_line <= max(3, node_start_line + 2)

    # Class/Function: docstring typically on next line after def/class
    return abs(token_line - node_start_line) <= 2


def _extract_docstring_lines(
    token: tokenize.TokenInfo,
    source_lines: List[str]
) -> List[Tuple[int, str]]:
    """
    Extract raw lines belonging to a docstring token.
    
    Returns:
        List of (line_number, raw_line_content) tuples
    """
    start_line, start_col = token.start
    end_line, end_col = token.end

    lines = []

    # Single-line docstring
    if start_line == end_line:
        raw_line = source_lines[start_line - 1]
        string_content = token.string
        string_start_idx = raw_line.find(string_content)
        if string_start_idx != -1:
            for i, part in enumerate(string_content.splitlines()):
                lines.append((start_line + i, raw_line[:string_start_idx] + part))
        else:
            lines.append((start_line, raw_line))
    else:
        # Multi-line docstring
        for i in range(start_line - 1, end_line):
            if i < len(source_lines):
                lines.append((i + 1, source_lines[i]))

    return lines


def _get_docstring_content(token: tokenize.TokenInfo) -> str:
    """
    Extract clean docstring content (without delimiters).
    """
    content = token.string
    # Remove delimiters
    if content.startswith('"""') or content.startswith("'''"):
        content = content[3:]
    if content.endswith('"""') or content.endswith("'''"):
        content = content[:-3]
    return content


def _get_node_info(node: ast.AST) -> Tuple[str, str]:
    """
    Get node type and name.
    
    Returns:
        (node_type, node_name) tuple
    """
    if isinstance(node, ast.Module):
        return 'module', '<module>'
    elif isinstance(node, ast.ClassDef):
        return 'class', node.name
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return 'function', node.name
    else:
        return 'unknown', '<unknown>'


def _extract_docstring_info(
    node: ast.AST,
    token: tokenize.TokenInfo,
    source_lines: List[str]
) -> DocstringInfo:
    """Create complete DocstringInfo object."""
    raw_lines = _extract_docstring_lines(token, source_lines)
    content = _get_docstring_content(token)
    node_type, node_name = _get_node_info(node)
    
    # Calculate base indentation
    indent_level = 0
    if raw_lines:
        first_line = raw_lines[0][1]
        indent_level = len(first_line)
    
    return DocstringInfo(
        node=node,
        token=token,
        raw_lines=raw_lines,
        content=content,
        start_line=token.start[0],
        end_line=token.end[0],
        indent_level=indent_level,
        node_type=node_type,
        node_name=node_name
    )


def validate_docstrings(
    path: Path,
    validators: Optional[List[BaseValidator]] = None,
    skip_private: bool = False
) -> List[Violation]:
    """
    Validate docstrings using extensible validator framework.
    
    **IMPORTANT**: By default, this validates ALL docstrings including:
      - Public functions, classes, and methods
      - Private functions, classes, and methods (starting with _)
      - Dunder methods (__init__, __str__, etc.)
      - Module-level docstrings
    
    Set skip_private=True to skip validation of private items (not recommended).
    
    Args:
        path: Python source file to validate
        validators: List of validator instances (uses MaxLineLengthValidator if None)
        skip_private: If True, skip functions/classes/methods starting with _ 
                      (default: False - validates ALL docstrings)
    
    Returns:
        List of violations (empty if compliant)
    """
    if validators is None:
        # Default: Only line length validation (backward compatible)
        validators = [
            MaxLineLengthValidator(max_length=72),
            FirstLineSummaryValidator(),
            ParameterReturnDefinitionValidator(),
        ]
    
    try:
        source_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Cannot read {path} as UTF-8: {e}")
    
    source_lines = source_text.splitlines(keepends=False)

    # Parse AST
    try:
        tree = ast.parse(source_text, filename=str(path))
    except SyntaxError as e:
        raise e

    # Tokenize
    try:
        lines = iter(source_text.splitlines(True))
        tokens = list(tokenize.generate_tokens(lines.__next__))
    except (tokenize.TokenError, IndentationError) as e:
        raise e

    # Find STRING tokens
    string_tokens = [
        token for token in tokens
        if token.type == tokenize.STRING
    ]

    if not string_tokens:
        return []

    violations: List[Violation] = []
    validated_tokens = set()
    
    # Helper to process a docstring with all validators
    def process_docstring(node: ast.AST, token: tokenize.TokenInfo):
        token_id = (token.start, token.end)
        if token_id in validated_tokens:
            return
        
        docstring_info = _extract_docstring_info(node, token, source_lines)
        
        # Skip private items if requested
        if skip_private:
            name = docstring_info.node_name
            # Skip if name starts with _ but not dunder methods
            if name.startswith('_') and not (name.startswith('__') and name.endswith('__')):
                validated_tokens.add(token_id)
                return
        
        validated_tokens.add(token_id)
        
        # Run all validators
        for validator in validators:
            # Line-by-line validation
            for line_num, raw_line in docstring_info.raw_lines:
                violation = validator.validate_line(
                    line_num, raw_line, docstring_info, path
                )
                if violation:
                    violations.append(violation)
            
            # Whole-docstring validation
            whole_violations = validator.validate_docstring(
                docstring_info, path
            )
            violations.extend(whole_violations)
    
    # Check module-level docstring
    module_candidates = [
        token for token in string_tokens
        if token.start[0] <= 3
    ]
    
    for token in module_candidates:
        if _is_docstring_candidate(
            tree, token, tree.body[1] if len(tree.body) > 1 else None
        ):
            process_docstring(tree, token)
    
    # Check class/function docstrings
    for node in ast.walk(tree):
        if not isinstance(node, (
            ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef
        )):
            continue
        
        node_end_line = getattr(node, 'end_lineno', node.lineno)
        candidates = [
            token for token in string_tokens
            if node.lineno <= token.start[0] <= node_end_line + 2
        ]
        
        for token in candidates:
            body = node.body
            next_stmt = body[1] if len(body) > 1 else None
            
            if _is_docstring_candidate(node, token, next_stmt):
                process_docstring(node, token)
    
    return violations
