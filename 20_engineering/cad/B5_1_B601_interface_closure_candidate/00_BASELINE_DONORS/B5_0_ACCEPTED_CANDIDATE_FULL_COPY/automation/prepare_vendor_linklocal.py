"""Create B5.0 link-local STEP references from the frozen vendor-group evidence.

Each invocation processes one semantic group so memory use and failures remain
bounded.  The source group and transform ledger are read-only.  Output is a
geometry reference only; accepted URDF frames remain authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Trsf


CANDIDATE = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[4]
VENDOR_STAGE = (
    WORKSPACE
    / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2"
    / "130_B601_Vendor_CAD_Direct_Integration_03"
)
TRANSFORMS = VENDOR_STAGE / "design/group_link_transforms.json"
SOURCE_DIR = VENDOR_STAGE / "vendor_groups"
OUT_DIR = CANDIDATE / "02_DESIGN/vendor_reference_linklocal"
EXPECTED_TRANSFORM_SHA256 = (
    "856BFEFEEABF27A74BD07D3E513C70812DEDA0841E88FEB91DA3B27B93CCC2F0"
)
GROUP_OUTPUT = {
    "G01": "B50_REF_link1_LINKLOCAL.step",
    "G02": "B50_REF_link2_LINKLOCAL.step",
    "G03": "B50_REF_link3_LINKLOCAL.step",
    "G04": "B50_REF_link4_LINKLOCAL.step",
    "G05": "B50_REF_link6_LINKLOCAL.step",
    "G06": "B50_REF_base_link_LINKLOCAL.step",
    "G07": "B50_REF_link5_LINKLOCAL.step",
    "G08": "B50_REF_gripper_detail_LINKLOCAL.step",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_record(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(WORKSPACE).as_posix()
        if str(path).lower().startswith(str(WORKSPACE).lower())
        else path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_step(path: Path):
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {path}")
    roots = int(reader.TransferRoots())
    shape = reader.OneShape()
    if roots <= 0 or shape.IsNull():
        raise RuntimeError(f"STEP transfer failed: {path}")
    return shape, roots


def transformed(shape, rotation: np.ndarray, translation_mm: np.ndarray):
    trsf = gp_Trsf()
    trsf.SetValues(
        float(rotation[0, 0]), float(rotation[0, 1]), float(rotation[0, 2]),
        float(translation_mm[0]),
        float(rotation[1, 0]), float(rotation[1, 1]), float(rotation[1, 2]),
        float(translation_mm[1]),
        float(rotation[2, 0]), float(rotation[2, 1]), float(rotation[2, 2]),
        float(translation_mm[2]),
    )
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def stats(shape) -> dict[str, object]:
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    bounds = [float(value) for value in box.Get()]
    solids = 0
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solids += 1
        explorer.Next()
    return {
        "solid_count": solids,
        "bbox_mm": {
            "min": bounds[:3],
            "max": bounds[3:],
        },
    }


def process_group(group: str) -> None:
    transform_hash = sha256(TRANSFORMS)
    if transform_hash != EXPECTED_TRANSFORM_SHA256:
        raise SystemExit(
            f"transform ledger drift: {transform_hash} != "
            f"{EXPECTED_TRANSFORM_SHA256}"
        )
    ledger = json.loads(TRANSFORMS.read_text(encoding="utf-8"))
    adopted = ledger["adopted"][group]
    source_name = (
        "G06_Base_FILTERED.step"
        if group == "G06"
        else adopted["extracted_step"]
    )
    source = SOURCE_DIR / source_name
    output = OUT_DIR / GROUP_OUTPUT[group]
    receipt = OUT_DIR / "evidence" / f"{group}_receipt.json"
    for path in (output, receipt):
        if path.exists():
            raise SystemExit(f"overwrite forbidden: {path}")

    shape, roots = load_step(source)
    source_stats = stats(shape)
    rotation = np.asarray(adopted["R_rows"], dtype=float)
    translation = np.asarray(adopted["t_mm"], dtype=float)
    if abs(np.linalg.det(rotation) - 1.0) > 1e-5:
        raise SystemExit(f"{group} rotation determinant is not +1")
    link_local = transformed(shape, rotation, translation)
    output_stats = stats(link_local)
    if output_stats["solid_count"] != source_stats["solid_count"]:
        raise SystemExit(f"{group} solid count changed during rigid transform")

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPControl_Writer()
    if writer.Transfer(link_local, STEPControl_AsIs) != IFSelect_RetDone:
        raise SystemExit(f"{group} STEP transfer to writer failed")
    write_status = writer.Write(str(output))
    if write_status != IFSelect_RetDone or not output.is_file():
        raise SystemExit(f"{group} STEP write failed: {write_status!r}")
    cold_shape, cold_roots = load_step(output)
    cold_stats = stats(cold_shape)
    if cold_stats["solid_count"] != output_stats["solid_count"]:
        raise SystemExit(f"{group} cold-read solid count changed")

    receipt_payload = {
        "receipt_id": f"B5_0_VENDOR_LINKLOCAL_{group}",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "group": group,
        "accepted_link_frame": adopted["urdf_link_frame"],
        "method": adopted["method"],
        "status": (
            "CHAIN_DERIVED_HOLD"
            if adopted["method"] == "CHAIN_DERIVED"
            else "DIRECT_GEOMETRY_REFERENCE"
        ),
        "convention": "p_link_mm = R_rows @ p_vendor_mm + t_mm",
        "rotation_rows": adopted["R_rows"],
        "translation_mm": adopted["t_mm"],
        "direct_nn_mm": adopted["direct_nn_mm"],
        "direct_margin_mm": adopted["direct_margin_mm"],
        "note": adopted["note"],
        "source": file_record(source),
        "source_roots": roots,
        "source_stats": source_stats,
        "transform_ledger": {
            **file_record(TRANSFORMS),
            "expected_sha256": EXPECTED_TRANSFORM_SHA256,
        },
        "output": file_record(output),
        "output_stats": output_stats,
        "cold_read": {
            "roots": cold_roots,
            "stats": cold_stats,
            "pass": True,
        },
        "mass_authority": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "license": "CERN-OHL-W-2.0_INTERNAL_RESEARCH_NO_REDISTRIBUTION",
        "verdict": f"B5_0_VENDOR_LINKLOCAL_{group}_PASS",
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(receipt_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, receipt)
    print(
        json.dumps(
            {
                "group": group,
                "verdict": receipt_payload["verdict"],
                "solids": cold_stats["solid_count"],
                "output_bytes": output.stat().st_size,
                "sha256": sha256(output),
            },
            ensure_ascii=False,
        )
    )


def finalize() -> None:
    ledger_path = CANDIDATE / "02_DESIGN/vendor_registration_ledger.json"
    if ledger_path.exists():
        raise SystemExit(f"overwrite forbidden: {ledger_path}")
    receipts = []
    for group in GROUP_OUTPUT:
        path = OUT_DIR / "evidence" / f"{group}_receipt.json"
        if not path.is_file():
            raise SystemExit(f"missing receipt: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["verdict"] != f"B5_0_VENDOR_LINKLOCAL_{group}_PASS":
            raise SystemExit(f"non-pass receipt: {path}")
        receipts.append(payload)
    payload = {
        "ledger_id": "B5_0_VENDOR_LINKLOCAL_REGISTRATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "truth_hierarchy": {
            "kinematics_and_mass": "accepted arm_b601_v1.urdf",
            "geometry": "vendor group STEP references only",
            "candidate_native": "later SolidWorks imports of these link-local STEP files",
        },
        "groups": receipts,
        "direct_groups": [
            item["group"] for item in receipts
            if item["status"] == "DIRECT_GEOMETRY_REFERENCE"
        ],
        "hold_groups": [
            item["group"] for item in receipts
            if item["status"] == "CHAIN_DERIVED_HOLD"
        ],
        "b106": "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH",
        "verdict": "B5_0_VENDOR_LINKLOCAL_REGISTRATION_PASS_WITH_G05_G08_HOLD",
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"verdict": payload["verdict"], "groups": len(receipts)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=tuple(GROUP_OUTPUT))
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if bool(args.group) == bool(args.finalize):
        raise SystemExit("choose exactly one of --group or --finalize")
    if args.group:
        process_group(args.group)
    else:
        finalize()


if __name__ == "__main__":
    main()
