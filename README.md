# rigorq
A Py CLI that enforces strict PEP8 and other Coding Guidelines that I use.


```
rigorq/
├── pyproject.toml                 # Build + embedded default config
├── README.md                      # Philosophy + usage
├── LICENSE
├── .gitignore
├── src/
│   └── rigorq/
│       ├── __init__.py            # __version__
│       ├── __main__.py            # Enables `python -m rigorq`
│       ├── cli.py                 # Argument parsing + execution flow
│       ├── config.py              # Default config (no file required)
│       ├── engine.py              # Orchestration core (phases)
│       ├── checks/
│       │   ├── __init__.py
│       │   ├── style.py           # Ruff subprocess wrapper
│       │   └── docstrings.py      # 72-char docstring validator (AST-based)
│       ├── reporter.py            # Unified violation formatting
│       └── utils.py               # File discovery, path resolution
├── tests/
│   ├── __init__.py
│   ├── test_cli.py
│   ├── test_docstring_validator.py  # Critical path test
│   └── fixtures/
│       ├── compliant/
│       │   ├── docstrings.py      # Valid 72-char docstrings
│       │   └── style.py           # PEP 8 compliant code
│       └── violations/
│           ├── long_docstring.py  # 73+ char docstring lines
│           └── style_violations.py
└── scripts/
    └── validate-stdlib.sh         # Test against CPython samples
```
