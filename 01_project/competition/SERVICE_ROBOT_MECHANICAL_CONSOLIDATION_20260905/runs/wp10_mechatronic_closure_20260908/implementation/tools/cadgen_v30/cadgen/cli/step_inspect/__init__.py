"""Selector reference inspection — the `cad inspect` / `cadgen step inspect` command.

Kept as a package rather than one module because the parser (`cli`) and the analysis it
drives (`inspect`) are independently useful and independently large.
"""

from cadgen.cli.step_inspect.cli import DEFAULT_PROG, build_parser, main

__all__ = ["DEFAULT_PROG", "build_parser", "main"]
