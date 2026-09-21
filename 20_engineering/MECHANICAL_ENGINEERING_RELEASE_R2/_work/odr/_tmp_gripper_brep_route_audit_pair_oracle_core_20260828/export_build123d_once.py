#!/usr/bin/env python3
"""One-shot STEP re-export used to test fresh-process determinism."""

from __future__ import annotations

import argparse
from pathlib import Path

from OCP.Font import Font_FontMgr
from OCP.TCollection import TCollection_AsciiString

manager = Font_FontMgr.GetInstance_s()
manager.AddFontAlias(TCollection_AsciiString("singleline"), TCollection_AsciiString("Arial"))

from build123d import export_step, import_step


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("label")
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing overwrite: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shape = import_step(args.source)
    shape.label = args.label
    export_step(shape, args.output, timestamp="2026-08-28T00:00:00+00:00")


if __name__ == "__main__":
    main()
