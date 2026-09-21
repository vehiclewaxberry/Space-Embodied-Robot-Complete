"""Extract four source-bound single-body shoe witnesses for durable measurement.

This is not a redesign.  It rebuilds only the four rectangular shoe bodies
from the hash-locked B5.1 geometry source, preserves each original product
label, and exports one STEP per body so SOLIDWORKS does not need to traverse
the problematic multi-body saddle import.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from build123d import export_step


CANDIDATE = Path(__file__).resolve().parent.parent
REPO = CANDIDATE.parents[2]
SOURCE_ROOT = (
    REPO
    / "20_engineering"
    / "cad"
    / "B5_1_B601_interface_closure_candidate"
)
GEOMETRY_ROOT = SOURCE_ROOT / "02_DESIGN" / "geometry"
COMMON_SOURCE = GEOMETRY_ROOT / "b51_geometry_common.py"
G07_SOURCE = GEOMETRY_ROOT / "b51_g07_main_saddle.py"
G08_SOURCE = GEOMETRY_ROOT / "b51_g08_grip_saddle.py"
G07_STEP = SOURCE_ROOT / "03_CAD" / "step" / "B51_G07_MAIN_SADDLE.step"
G08_STEP = SOURCE_ROOT / "03_CAD" / "step" / "B51_G08_GRIP_SADDLE.step"
OUT_ROOT = CANDIDATE / "01_MEASUREMENT" / "SHOE_WITNESS_STEPS"
RECEIPT = CANDIDATE / "01_MEASUREMENT" / "B51R1_SHOE_WITNESS_EXTRACTION.json"

EXPECTED = {
    COMMON_SOURCE: "D3181C889FEFFD8FFFB2492E5F8B9601D803D8259F992849B45FECD8C896DACA",
    G07_SOURCE: "385E8E41BFA1216C63FB43C45BD93FC73DD57CFCEB246D1A598C6BF7628E87FB",
    G08_SOURCE: "D4CDEF2EF5274309903DC7C3B87E447B4383B9BB673064D468703D626452F1BD",
    G07_STEP: "937F28359D257890E4F14B71B64B27A46D468505F3343CDE191C9739D4CE26BE",
    G08_STEP: "027C7646088838C3FC1E7E7F823D8093A332CDC6BD64270BCC3A6A98100585D4",
}

TARGET_LABELS = {
    "B51_G07_MAIN_LONGERON_SHOE_NY_CANDIDATE_HOLD":
        "B51R1_G07_SHOE_NY_SOURCE_BOUND.step",
    "B51_G07_MAIN_LONGERON_SHOE_PY_CANDIDATE_HOLD":
        "B51R1_G07_SHOE_PY_SOURCE_BOUND.step",
    "B51_G08_GRIP_LONGERON_SHOE_NY_CANDIDATE_HOLD":
        "B51R1_G08_SHOE_NY_SOURCE_BOUND.step",
    "B51_G08_GRIP_LONGERON_SHOE_PY_CANDIDATE_HOLD":
        "B51R1_G08_SHOE_PY_SOURCE_BOUND.step",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bbox_record(shape) -> dict:
    box = shape.bounding_box()
    return {
        "min_mm": [box.min.X, box.min.Y, box.min.Z],
        "max_mm": [box.max.X, box.max.Y, box.max.Z],
        "center_mm": [
            0.5 * (box.min.X + box.max.X),
            0.5 * (box.min.Y + box.max.Y),
            0.5 * (box.min.Z + box.max.Z),
        ],
        "size_mm": [
            box.max.X - box.min.X,
            box.max.Y - box.min.Y,
            box.max.Z - box.min.Z,
        ],
    }


def main() -> int:
    if RECEIPT.exists():
        raise RuntimeError(f"append-only receipt already exists: {RECEIPT}")
    for path, expected in EXPECTED.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"source hash drift: {path}: {actual} != {expected}")

    sys.path.insert(0, str(GEOMETRY_ROOT))
    common = load_module("b51_geometry_common_phase1_witness", COMMON_SOURCE)
    models = [
        common.build_saddle(common.MAIN_SADDLE),
        common.build_saddle(common.GRIP_SADDLE),
    ]
    common.assert_bounds_and_validity(models[0], common.MAIN_SADDLE.x_window)
    common.assert_bounds_and_validity(models[1], common.GRIP_SADDLE.x_window)
    common.assert_pairwise_no_volume_overlap(models[0])
    common.assert_pairwise_no_volume_overlap(models[1])

    by_label = {
        str(child.label): child
        for model in models
        for child in list(model.children or [])
    }
    missing = sorted(set(TARGET_LABELS) - set(by_label))
    if missing:
        raise RuntimeError(f"source-bound shoe labels missing: {missing}")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    fixed_timestamp = "2026-07-29T00:00:00"
    for label, filename in TARGET_LABELS.items():
        shape = by_label[label]
        if not shape.is_valid:
            raise RuntimeError(f"invalid shoe body: {label}")
        target = OUT_ROOT / filename
        if target.exists():
            raise RuntimeError(f"immutable witness STEP exists: {target}")
        if not export_step(shape, target, timestamp=fixed_timestamp):
            raise RuntimeError(f"STEP export failed: {target}")
        box = bbox_record(shape)
        expected_side = -105.65 if "_NY_" in label else 105.65
        if abs(box["center_mm"][1] - expected_side) > 1.0e-9:
            raise RuntimeError(
                f"shoe centre mismatch: {label}: {box['center_mm'][1]}"
            )
        if abs(box["min_mm"][2] - 113.15) > 1.0e-9:
            raise RuntimeError(
                f"shoe bottom mismatch: {label}: {box['min_mm'][2]}"
            )
        records.append(
            {
                "original_product_label": label,
                "source_common": str(COMMON_SOURCE.resolve()),
                "source_common_sha256": EXPECTED[COMMON_SOURCE],
                "source_full_step": str(
                    (G07_STEP if "_G07_" in label else G08_STEP).resolve()
                ),
                "source_full_step_sha256": EXPECTED[
                    G07_STEP if "_G07_" in label else G08_STEP
                ],
                "output": str(target.resolve()),
                "output_sha256": sha256(target),
                "is_valid": bool(shape.is_valid),
                "volume_mm3": float(shape.volume),
                "bbox": box,
                "binding": (
                    "LOCKED_SOURCE_HASH+ORIGINAL_PRODUCT_LABEL+"
                    "GEOMETRY_SIGNATURE"
                ),
                "claim_limit": "MEASUREMENT_WITNESS_ONLY",
            }
        )

    payload = {
        "schema": "SER_B51R1_SHOE_WITNESS_EXTRACTION_V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": "COMP-PROT-03-A4-B5.1R1-PHASE1",
        "status": "PASS_FOUR_SOURCE_BOUND_SINGLE_BODY_STEPS",
        "method": "HASH_LOCKED_SOURCE_REBUILD_NO_GEOMETRY_EDIT",
        "records": records,
        "prohibitions": [
            "NOT_MATE_REFERENCE",
            "NOT_DETAIL_REDESIGN",
            "NOT_ATTACHMENT_OR_LOAD_PATH_CREDIT",
            "NOT_MANUFACTURING_OR_FLIGHT_GEOMETRY",
        ],
    }
    with RECEIPT.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "receipt": str(RECEIPT),
                "status": payload["status"],
                "outputs": len(records),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
