#!/usr/bin/env python3
"""Fresh-process B50→receipt/assignment→finger compound STEP exporter."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from OCP.Font import Font_FontMgr
from OCP.TCollection import TCollection_AsciiString

manager = Font_FontMgr.GetInstance_s()
manager.AddFontAlias(TCollection_AsciiString("singleline"), TCollection_AsciiString("Arial"))

from build123d import Compound, export_step, import_step


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
BUILDER_PATH = (
    ROOT
    / "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/99_tools"
    / "gripper_r1_build_and_validate.py"
)


def load_builder():
    spec = importlib.util.spec_from_file_location("frozen_gripper_r1_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load frozen R1 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("side", choices=("left", "right", "both"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sides = ("left", "right") if args.side == "both" else (args.side,)
    if args.side == "both":
        output_paths = {
            side: args.output / f"B601_GRIPPER_{side.upper()}_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE.step"
            for side in sides
        }
    else:
        output_paths = {args.side: args.output}
    existing = [str(path) for path in output_paths.values() if path.exists()]
    if existing:
        raise RuntimeError(f"refusing overwrite: {existing}")
    for path in output_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    builder = load_builder()
    receipt = json.loads(builder.V5_RECEIPT.read_text(encoding="utf-8"))
    model = import_step(builder.NEUTRAL_STEP)
    bound, _rows = builder.bind_neutral_solids(model, list(receipt["source_open"]["evidence"]))
    assignment, _semantic = builder.read_assignment()
    for side in sides:
        group = f"gripper_{side}"
        names = sorted(name for name, assigned in assignment.items() if assigned == group)
        if len(names) != 24:
            raise RuntimeError(f"unexpected {group} solid count: {len(names)}")
        shape = Compound(children=[bound[name] for name in names])
        shape.label = f"B601_GRIPPER_{side.upper()}_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE"
        export_step(shape, output_paths[side], timestamp="2026-08-28T00:00:00+00:00")


if __name__ == "__main__":
    main()
