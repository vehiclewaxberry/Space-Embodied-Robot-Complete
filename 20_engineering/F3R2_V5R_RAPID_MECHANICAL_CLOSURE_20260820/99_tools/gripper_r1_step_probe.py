#!/usr/bin/env python3
"""Read-only OpenCascade probe for the isolated frozen gripper STEP.

This utility deliberately has no SolidWorks or win32com imports.  It prints
the imported solid labels, volumes, and link-6-local bounding boxes so the
derived R1 build can be bound to the existing V5 body fingerprint evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build123d import import_step


DEFAULT_STEP = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\cad\B5_0_B601_space_manipulator_candidate"
    r"\02_DESIGN\vendor_reference_linklocal\B50_REF_gripper_detail_LINKLOCAL.step"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=Path, default=DEFAULT_STEP)
    args = parser.parse_args()

    model = import_step(args.step)
    rows = []
    for index, solid in enumerate(model.solids()):
        box = solid.bounding_box()
        rows.append(
            {
                "index": index,
                "label": getattr(solid, "label", ""),
                "volume_mm3": float(solid.volume),
                "bbox_mm": [
                    float(box.min.X),
                    float(box.min.Y),
                    float(box.min.Z),
                    float(box.max.X),
                    float(box.max.Y),
                    float(box.max.Z),
                ],
                "face_count": len(solid.faces()),
            }
        )
    print(json.dumps({"step": str(args.step), "solid_count": len(rows), "solids": rows}, indent=2))


if __name__ == "__main__":
    main()
