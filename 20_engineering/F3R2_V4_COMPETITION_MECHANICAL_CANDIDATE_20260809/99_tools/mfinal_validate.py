# -*- coding: utf-8 -*-
"""Independent static validation for the F3R2 V4 neutral CAD candidate."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer


ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
V4 = ROOT / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
F3R2 = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
F3R1 = ROOT / "20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806"
BUILD = V4 / "10_validation/MFINAL_FREECAD_BUILD_RECEIPT.json"
MANIFEST = V4 / "10_validation/MFINAL_NEUTRAL_CAD_MANIFEST_SHA256.txt"
BOM = V4 / "09_bom/MFINAL_PROVISIONAL_BOM.csv"
OUTPUT = V4 / "10_validation/MFINAL_INDEPENDENT_VALIDATION.json"

FROZEN_TOP_SHA = "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def load_step(path: Path):
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise ValueError(f"STEP read failed: {path}")
    roots = reader.TransferRoots()
    if roots < 1:
        raise ValueError(f"STEP transfer failed: {path}")
    return reader.OneShape()


def solid_count(shape) -> int:
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def volume(shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return float(props.Mass())


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    return [round(value, 6) for value in box.Get()]


def parse_manifest():
    rows = []
    for line_number, line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("  ", 2)
        if len(parts) != 3:
            raise ValueError(f"bad manifest line {line_number}")
        rows.append({"sha256": parts[0], "bytes": int(parts[1]), "path": parts[2]})
    return rows


def main():
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    manifest_rows = parse_manifest()
    manifest_failures = []
    seen = set()
    for row in manifest_rows:
        key = row["path"].lower()
        if key in seen:
            manifest_failures.append(f"duplicate:{row['path']}")
            continue
        seen.add(key)
        path = V4 / row["path"]
        if not path.is_file():
            manifest_failures.append(f"missing:{row['path']}")
        elif path.stat().st_size != row["bytes"]:
            manifest_failures.append(f"bytes:{row['path']}")
        elif sha256(path) != row["sha256"]:
            manifest_failures.append(f"sha256:{row['path']}")

    with BOM.open("r", encoding="utf-8-sig", newline="") as stream:
        bom_rows = list(csv.DictReader(stream))
    bom_keys = [row["part_number"] for row in bom_rows]
    bom_ok = len(bom_rows) == build["bom_rows"] and len(bom_keys) == len(set(bom_keys))

    step_results = []
    step_failures = []
    for package in build["packages"]:
        for part in package.get("parts", []):
            step_paths = [Path(path) for path in part.get("outputs", []) if str(path).lower().endswith(".step")]
            if len(step_paths) != 1:
                step_failures.append(f"{part['part_number']}:step_count={len(step_paths)}")
                continue
            path = step_paths[0]
            shape = load_step(path)
            measured_volume = volume(shape)
            measured_solids = solid_count(shape)
            measured_bounds = bounds(shape)
            volume_error = abs(measured_volume - float(part["volume_mm3"]))
            passed = measured_solids == 1 and volume_error <= max(1.0e-3, measured_volume * 1.0e-8)
            if not passed:
                step_failures.append(part["part_number"])
            step_results.append(
                {
                    "part_number": part["part_number"],
                    "step": path.relative_to(V4).as_posix(),
                    "solid_count": measured_solids,
                    "volume_mm3": round(measured_volume, 6),
                    "receipt_volume_mm3": part["volume_mm3"],
                    "volume_error_mm3": round(volume_error, 9),
                    "bounds_mm": measured_bounds,
                    "pass": passed,
                }
            )

    package_by_id = {package["package"]: package for package in build["packages"]}
    adapter = package_by_id["M-FINAL-01"]
    body = next(part for part in adapter["parts"] if "STAGE_B" in part["part_number"])
    adapter_checks = {
        "m6_pattern_is_140_square": sorted(adapter["m6_centres_xy_mm"])
        == [[-70.0, -70.0], [-70.0, 70.0], [70.0, -70.0], [70.0, 70.0]],
        "stage_b_local_extent_reaches_85_mm": abs(float(body["bounds_mm"][3]) - 85.0) < 1.0e-3,
        "net_hole_edge_ligament_at_least_10_mm": float(adapter["m6_net_hole_edge_ligament_mm"]) >= 10.0,
        "stage_a_stage_b_contact_without_volume_overlap": bool(adapter["assembly_contact"]["pass"]),
    }

    supports = package_by_id["M-FINAL-03"]
    support_checks = {}
    expected_faces = {"G07": 261.5016, "G08": 208.4929, "MID": 212.9189}
    expected_gaps = {"G07": 0.0, "G08": 0.0, "MID": 2.0}
    for station in supports["stations"]:
        tag = station["station"]
        support_checks[tag] = {
            "pad_face_z_match": abs(float(station["pad_face_z_mm"]) - expected_faces[tag]) <= 1.0e-6,
            "gap_match": abs(float(station["nominal_gap_mm"]) - expected_gaps[tag]) <= 1.0e-9,
            "mount_pattern_is_explicit_candidate": station["foot_pattern_status"]
            == "ENGINEERING_CANDIDATE_PENDING_NATIVE_MEASUREMENT",
        }

    hdrm = package_by_id["M-FINAL-04"]
    hdrm_checks = {
        "working_release_is_minus_x": hdrm["working_release_direction"] == "-X",
        "ground_removal_is_plus_z": hdrm["ground_removal_unlock_direction"] == "+Z",
        "stroke_is_6_mm": float(hdrm["release_stroke_mm"]) == 6.0,
        "physical_model_stays_hold": hdrm["physical_model_status"] == "HOLD_SKELETON_ONLY",
    }

    camera_harness = package_by_id["M-FINAL-05"]
    camera_harness_checks = {
        "bend_radius_at_least_25_mm": camera_harness["bend_radius_pass"]
        and float(camera_harness["computed_minimum_curve_radius_mm"]) >= 25.0,
        "envelopes_are_non_physical": camera_harness["classification"]
        == "NON_PHYSICAL_COLLISION_ENVELOPES",
    }

    gripper = package_by_id["M-FINAL-06"]
    gripper_checks = {
        "58_source_solids": int(gripper["count_total"]) == 58,
        "group_counts_10_24_24": gripper["counts"]
        == {"gripper_link": 10, "gripper_left": 24, "gripper_right": 24},
        "native_gate_is_hold": str(gripper["native_gate"]).startswith("HOLD_"),
    }

    native_extensions = {".sldprt", ".sldasm", ".slddrw"}
    native_files = [
        path.relative_to(V4).as_posix()
        for path in V4.rglob("*")
        if path.is_file() and path.suffix.lower() in native_extensions
    ]

    protected = []
    for path in (
        F3R2 / "03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM",
        F3R1 / "03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM",
    ):
        protected.append(
            {
                "path": str(path).replace("\\", "/"),
                "exists": path.is_file(),
                "sha256": sha256(path) if path.is_file() else None,
                "expected_sha256": FROZEN_TOP_SHA,
                "pass": path.is_file() and sha256(path) == FROZEN_TOP_SHA,
            }
        )

    check_groups = {
        "manifest": not manifest_failures and len(manifest_rows) == build["neutral_output_files"],
        "bom": bom_ok,
        "step_parts": not step_failures and len(step_results) == 20,
        "adapter": all(adapter_checks.values()),
        "supports": all(all(item.values()) for item in support_checks.values()),
        "hdrm": all(hdrm_checks.values()),
        "camera_harness": all(camera_harness_checks.values()),
        "gripper": all(gripper_checks.values()),
        "no_native_release_files_claimed": not native_files,
        "protected_frozen_tops": all(item["pass"] for item in protected),
    }
    report = {
        "schema": "MFINAL_INDEPENDENT_VALIDATION_V1",
        "build_receipt_sha256": sha256(BUILD),
        "neutral_manifest_sha256": sha256(MANIFEST),
        "manifest_rows": len(manifest_rows),
        "manifest_failures": manifest_failures,
        "bom_rows": len(bom_rows),
        "bom_unique_keys": len(set(bom_keys)),
        "step_part_results": step_results,
        "step_failures": step_failures,
        "adapter_checks": adapter_checks,
        "support_checks": support_checks,
        "hdrm_checks": hdrm_checks,
        "camera_harness_checks": camera_harness_checks,
        "gripper_checks": gripper_checks,
        "native_release_files_present": native_files,
        "protected_frozen_assets": protected,
        "check_groups": check_groups,
        "pass_count": sum(1 for value in check_groups.values() if value),
        "fail_count": sum(1 for value in check_groups.values() if not value),
        "explicit_holds": build["explicit_holds"],
        "verdict": (
            "MFINAL_STATIC_VALIDATION_PASS_WITH_EXPLICIT_NATIVE_AND_AUTHORITY_HOLDS"
            if all(check_groups.values())
            else "MFINAL_STATIC_VALIDATION_FAIL"
        ),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": report["verdict"],
        "pass_count": report["pass_count"],
        "fail_count": report["fail_count"],
        "manifest_rows": report["manifest_rows"],
        "step_parts": len(step_results),
        "output": str(OUTPUT),
    }, ensure_ascii=False, indent=2))
    return 0 if report["fail_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
