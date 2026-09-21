"""``cadgen dxf snapshot`` — render a drawing as its 3D flat pattern.

A GENERATED CLI over :func:`cadgen.dxf.snapshot`. There is no parser here on
purpose: everything the command accepts is derived from the verb function's
signature by :mod:`cadgen._internal.cli_from_function`, so a flag cannot drift
from a parameter (design/format-doors.md). Which input kinds the door accepts
is declared once, beside the verb, in
:data:`cadgen._internal.snapshot_door.DOOR_KINDS`.

A drawing carries no assembly topology, so this door binds the same reduced
MESH shape the mesh doors do: a drawing is parameterized by its source, not by
``--kinematics``.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from cadgen._internal.cli_from_function import generated_main, generated_parser

DEFAULT_PROG = "cadgen dxf snapshot"
VERB = ("cadgen.dxf", "snapshot")


def build_parser(prog: str = DEFAULT_PROG) -> argparse.ArgumentParser:
    return generated_parser(VERB, prog=prog)


def main(argv: Sequence[str] | None = None, *, prog: str = DEFAULT_PROG) -> int:
    return generated_main(VERB, argv, prog=prog)


if __name__ == "__main__":
    raise SystemExit(main())
