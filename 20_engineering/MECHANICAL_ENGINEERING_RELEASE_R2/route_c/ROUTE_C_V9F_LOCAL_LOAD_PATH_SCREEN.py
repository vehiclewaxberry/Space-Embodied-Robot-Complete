"""Fail-closed local load-path screen for the Route-C V9F source model.

The screen proves only that the intended support chain is represented by
finite CAD solids and registered to Link-3.  It does not invent launch loads,
fastener properties, material allowables, boundary stiffness, or safety
factors; therefore it cannot emit a stress margin or qualification credit.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
BUILDER = HERE / "B601_ROUTE_C_BUILD_V9F.py"
RECEIPT = HERE / "B601_ROUTE_C_BUILD_RECEIPT_V9F.json"
CLAMPS = HERE / "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V9F.csv"
MESH_PACK = HERE / "ROUTE_C_SWEEP_MESH_PACK_V9F"
MESH_MANIFEST = MESH_PACK / "MANIFEST.json"
OUT = HERE / "ROUTE_C_V9F_LOCAL_LOAD_PATH_SCREEN.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def finite_positive_mass(value: object) -> tuple[bool, bool, bool]:
    """Return numeric, finite and strictly-positive states without zero fill."""
    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
    finite = bool(numeric and math.isfinite(float(value)))
    positive = bool(finite and float(value) > 0.0)
    return numeric, finite, positive


def bbox_from_hashed_mesh(entry: dict[str, object] | None) -> dict[str, object]:
    """Evaluate one manifest-pinned triangle bounding box fail-closed."""
    if entry is None:
        return {
            "evaluated": False,
            "state": "NOT_EVALUATED_MESH_MANIFEST_ENTRY_ABSENT",
            "file": None,
            "expected_sha256": None,
            "actual_sha256": None,
            "sha256_match": False,
            "bbox_min_mm": None,
            "bbox_max_mm": None,
        }
    filename = entry.get("file")
    expected = entry.get("sha256")
    if not isinstance(filename, str) or not isinstance(expected, str):
        return {
            "evaluated": False,
            "state": "NOT_EVALUATED_INVALID_MESH_MANIFEST_ENTRY",
            "file": filename,
            "expected_sha256": expected,
            "actual_sha256": None,
            "sha256_match": False,
            "bbox_min_mm": None,
            "bbox_max_mm": None,
        }
    path = MESH_PACK / filename
    if not path.is_file():
        return {
            "evaluated": False,
            "state": "NOT_EVALUATED_PINNED_MESH_FILE_ABSENT",
            "file": filename,
            "expected_sha256": expected,
            "actual_sha256": None,
            "sha256_match": False,
            "bbox_min_mm": None,
            "bbox_max_mm": None,
        }
    actual = sha(path)
    if actual != expected:
        return {
            "evaluated": False,
            "state": "NOT_EVALUATED_PINNED_MESH_HASH_MISMATCH",
            "file": filename,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "sha256_match": False,
            "bbox_min_mm": None,
            "bbox_max_mm": None,
        }
    try:
        triangles = np.load(path, allow_pickle=False)
    except Exception:
        return {
            "evaluated": False,
            "state": "NOT_EVALUATED_PINNED_MESH_PARSE_FAILURE",
            "file": filename,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "sha256_match": True,
            "bbox_min_mm": None,
            "bbox_max_mm": None,
        }
    if (triangles.ndim != 3 or triangles.shape[1:] != (3, 3)
            or triangles.shape[0] == 0 or not np.isfinite(triangles).all()):
        return {
            "evaluated": False,
            "state": "NOT_EVALUATED_PINNED_MESH_NONFINITE_OR_EMPTY",
            "file": filename,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "sha256_match": True,
            "bbox_min_mm": None,
            "bbox_max_mm": None,
        }
    points = triangles.reshape((-1, 3))
    return {
        "evaluated": True,
        "state": "EVALUATED_HASH_PINNED_TRIANGLE_BBOX",
        "file": filename,
        "expected_sha256": expected,
        "actual_sha256": actual,
        "sha256_match": True,
        "bbox_min_mm": [float(value) for value in points.min(axis=0)],
        "bbox_max_mm": [float(value) for value in points.max(axis=0)],
    }


def bbox_interface_check(interface_id: str, branch: str, part_a: str,
                         part_b: str,
                         boxes: dict[str, dict[str, object]]) -> dict[str, object]:
    """Prove only zero positive separation of two declared interface bboxes."""
    box_a = boxes.get(part_a)
    box_b = boxes.get(part_b)
    if not box_a or not box_b or not box_a["evaluated"] or not box_b["evaluated"]:
        return {
            "interface_id": interface_id,
            "branch": branch,
            "part_a": part_a,
            "part_b": part_b,
            "method": "HASH_PINNED_AXIS_ALIGNED_TRIANGLE_BBOX_SEPARATION",
            "interface_tolerance_mm": 0.0,
            "tolerance_authority": "ZERO_POSITIVE_SEPARATION_ONLY__NO_POSITIVE_ACCEPTANCE_THRESHOLD_INVENTED",
            "evaluated": False,
            "axis_positive_separation_mm": None,
            "euclidean_positive_separation_mm": None,
            "within_declared_interface_tolerance": None,
            "state": "NOT_EVALUATED_REQUIRED_HASHED_BBOX_UNAVAILABLE",
        }
    amin = np.asarray(box_a["bbox_min_mm"], dtype=float)
    amax = np.asarray(box_a["bbox_max_mm"], dtype=float)
    bmin = np.asarray(box_b["bbox_min_mm"], dtype=float)
    bmax = np.asarray(box_b["bbox_max_mm"], dtype=float)
    axis_gap = np.maximum(np.maximum(amin - bmax, bmin - amax), 0.0)
    gap = float(np.linalg.norm(axis_gap))
    within = gap == 0.0
    return {
        "interface_id": interface_id,
        "branch": branch,
        "part_a": part_a,
        "part_b": part_b,
        "method": "HASH_PINNED_AXIS_ALIGNED_TRIANGLE_BBOX_SEPARATION",
        "interface_tolerance_mm": 0.0,
        "tolerance_authority": "ZERO_POSITIVE_SEPARATION_ONLY__NO_POSITIVE_ACCEPTANCE_THRESHOLD_INVENTED",
        "evaluated": True,
        "axis_positive_separation_mm": [float(value) for value in axis_gap],
        "euclidean_positive_separation_mm": gap,
        "within_declared_interface_tolerance": within,
        "state": (
            "PASS_ZERO_POSITIVE_BBOX_SEPARATION"
            if within else
            "FAIL_POSITIVE_BBOX_SEPARATION_NO_TOLERANCE_AVAILABLE"
        ),
    }


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    mesh_manifest = json.loads(MESH_MANIFEST.read_text(encoding="utf-8"))
    parts = {row["name"]: row for row in receipt["parts"]}
    required = [
        "RC-GDE-J4-ANNULAR-FOLLOWER",
        "RC-BRK-J4-ANN-SUPPORT-UPPER-SADDLE",
        "RC-BRK-J4-ANN-SUPPORT-UPPER-POST",
        "RC-BRK-J4-ANN-SUPPORT-UPPER-ARM",
        "RC-BRK-J4-ANN-SUPPORT-MID-SADDLE",
        "RC-BRK-J4-ANN-SUPPORT-MID-POST",
        "RC-BRK-J4-ANN-SUPPORT-MID-ARM",
        "RC-BRK-J4-ANN-SUPPORT-LOWER-SADDLE",
        "RC-BRK-J4-ANN-SUPPORT-LOWER-POST",
        "RC-BRK-J4-ANN-SUPPORT-LOWER-ARM",
        "RC-BRK-J4-ANN-SPINE-HUB",
        "RC-BRK-J4-ANN-MAIN-SPINE",
        "RC-BRK-J4-ANN-ROOT-NECK",
    ]
    checks = []
    for name in required:
        row = parts.get(name)
        mass_value = None if row is None else row.get("mass_g_estimate")
        mass_numeric, mass_finite, mass_positive = finite_positive_mass(mass_value)
        checks.append({
            "part": name,
            "present": row is not None,
            "valid_solid": bool(row and row.get("valid")),
            "positive_volume": bool(row and float(row.get("volume_mm3", 0.0)) > 0.0),
            "host_link": None if row is None else row.get("host_link"),
            "host_is_link3": bool(row and row.get("host_link") == "link3"),
            "mass_g_estimate": float(mass_value) if mass_finite else None,
            "mass_numeric": mass_numeric,
            "mass_finite": mass_finite,
            "mass_positive": mass_positive,
            "mass_evaluated": mass_finite,
        })
    geometry_present = all(
        c["present"] and c["valid_solid"] and c["positive_volume"]
        and c["host_is_link3"] for c in checks)

    mass_actual_evaluated = sum(c["mass_evaluated"] for c in checks)
    mass_passing = sum(c["mass_positive"] for c in checks)
    mass_evaluation = {
        "expected_count": len(required),
        "actual_evaluated_count": mass_actual_evaluated,
        "passing_count": mass_passing,
        "empty_comparison_count": int(mass_actual_evaluated == 0),
        "all_required_masses_finite_and_positive": (
            mass_actual_evaluated == len(required) and mass_passing == len(required)
        ),
        "invalid_or_unevaluated_parts": [
            c["part"] for c in checks if not c["mass_positive"]
        ],
        "null_nonfinite_or_nonpositive_is_zero_filled": False,
    }

    route_entries: dict[str, dict[str, object]] = {}
    for group in mesh_manifest.get("files", []):
        if group.get("group") == "route_c_parts":
            for entry in group.get("entries", []):
                entry_name = entry.get("name")
                if isinstance(entry_name, str) and entry_name not in route_entries:
                    route_entries[entry_name] = entry
    manifest_receipt_pin_match = (
        mesh_manifest.get("inputs", {}).get("route_c_build_receipt", {}).get("sha256")
        == sha(RECEIPT)
    )
    boxes = {name: bbox_from_hashed_mesh(route_entries.get(name)) for name in required}
    declared_interfaces = [
        ("IF-ROOT-NECK-TO-MAIN-SPINE", "ROOT", "RC-BRK-J4-ANN-ROOT-NECK", "RC-BRK-J4-ANN-MAIN-SPINE"),
        ("IF-MAIN-SPINE-TO-HUB", "ROOT", "RC-BRK-J4-ANN-MAIN-SPINE", "RC-BRK-J4-ANN-SPINE-HUB"),
    ]
    for branch in ("UPPER", "MID", "LOWER"):
        arm = f"RC-BRK-J4-ANN-SUPPORT-{branch}-ARM"
        post = f"RC-BRK-J4-ANN-SUPPORT-{branch}-POST"
        saddle = f"RC-BRK-J4-ANN-SUPPORT-{branch}-SADDLE"
        declared_interfaces.extend([
            (f"IF-HUB-TO-{branch}-ARM", branch, "RC-BRK-J4-ANN-SPINE-HUB", arm),
            (f"IF-{branch}-ARM-TO-POST", branch, arm, post),
            (f"IF-{branch}-POST-TO-SADDLE", branch, post, saddle),
            (f"IF-{branch}-SADDLE-TO-ANNULAR-GUIDE", branch, saddle, "RC-GDE-J4-ANNULAR-FOLLOWER"),
        ])
    interface_checks = [
        bbox_interface_check(interface_id, branch, part_a, part_b, boxes)
        for interface_id, branch, part_a, part_b in declared_interfaces
    ]
    interface_actual_evaluated = sum(row["evaluated"] for row in interface_checks)
    interface_passing = sum(
        row["within_declared_interface_tolerance"] is True
        for row in interface_checks
    )
    interface_chain_pass = (
        manifest_receipt_pin_match
        and interface_actual_evaluated == len(declared_interfaces)
        and interface_passing == len(declared_interfaces)
    )
    interface_chain = {
        "scope": "DECLARED_INTERFACE_ENDPOINT_CHAIN__BBOX_ZERO_POSITIVE_SEPARATION_ONLY",
        "proof_boundary": "BBOX_OVERLAP_OR_ABUTMENT_DOES_NOT_PROVE_SOLID_CONTACT_CONTINUITY_FASTENER_LOAD_TRANSFER_OR_STRENGTH",
        "interface_tolerance_mm": 0.0,
        "tolerance_authority": "ZERO_POSITIVE_SEPARATION_FROM_DECLARED_ANALYTIC_ABUTMENT_OR_BBOX_OVERLAP__NO_POSITIVE_THRESHOLD_INVENTED",
        "mesh_manifest_receipt_pin_matches_current_receipt": manifest_receipt_pin_match,
        "expected_count": len(declared_interfaces),
        "actual_evaluated_count": interface_actual_evaluated,
        "passing_count": interface_passing,
        "empty_comparison_count": int(interface_actual_evaluated == 0),
        "all_declared_interfaces_have_zero_positive_bbox_separation": interface_chain_pass,
        "checks": interface_checks,
        "source_part_bboxes": boxes,
        "solid_contact_continuity": "NOT_EVALUATED_BBOX_OVERLAP_OR_ABUTMENT_IS_NOT_A_SOLID_CONTACT_PROOF",
        "verdict": (
            "PASS_DECLARED_INTERFACE_BBOX_ZERO_POSITIVE_SEPARATION__NO_CONTACT_OR_STRENGTH_CREDIT"
            if interface_chain_pass else
            "NOT_EVALUATED_OR_FAIL_DECLARED_INTERFACE_BBOX_CHAIN__NO_POSITIVE_TOLERANCE_AVAILABLE"
        ),
    }

    missing_inputs = [
        {"id": "LP-I01", "quantity": "root fastener diameter/count/grade/preload and edge distances",
         "state": "UNKNOWN"},
        {"id": "LP-I02", "quantity": "Link-3 local attachment-surface thickness and bearing/pull-through allowable",
         "state": "UNKNOWN"},
        {"id": "LP-I03", "quantity": "support material certified yield/ultimate/fatigue allowables at temperature",
         "state": "UNKNOWN"},
        {"id": "LP-I04", "quantity": "launch random-vibration, sine, shock and quasi-static design loads",
         "state": "UNKNOWN"},
        {"id": "LP-I05", "quantity": "on-orbit follower contact/preload and jam load spectrum",
         "state": "UNKNOWN"},
        {"id": "LP-I06", "quantity": "root boundary stiffness and joint slip/friction model",
         "state": "UNKNOWN"},
        {"id": "LP-I07", "quantity": "program structural factors of safety and acceptance rule",
         "state": "UNKNOWN"},
        {"id": "LP-I08", "quantity": "as-built mass, tolerances, workmanship and proof/qualification test data",
         "state": "UNKNOWN"},
    ]

    support_mass_g = (
        sum(float(parts[name]["mass_g_estimate"]) for name in required)
        if mass_evaluation["all_required_masses_finite_and_positive"] else None
    )
    source_geometry_load_path_present = bool(
        geometry_present
        and mass_evaluation["all_required_masses_finite_and_positive"]
        and interface_chain_pass
    )
    doc = {
        "schema": "ROUTE_C_V9F_LOCAL_LOAD_PATH_SCREEN_V2",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "authority": "SOURCE_GEOMETRY_AND_ZERO_GAP_BBOX_CHAIN_SCREEN_ONLY__NO_CONTACT_STRENGTH_OR_QUALIFICATION_CREDIT",
        "input_pins": {
            "builder": {"path": BUILDER.name, "sha256": sha(BUILDER)},
            "build_receipt": {"path": RECEIPT.name, "sha256": sha(RECEIPT)},
            "clamp_register": {"path": CLAMPS.name, "sha256": sha(CLAMPS)},
            "mesh_manifest": {
                "path": MESH_MANIFEST.relative_to(HERE).as_posix(),
                "sha256": sha(MESH_MANIFEST),
                "manifest_receipt_pin_matches_current_receipt": manifest_receipt_pin_match,
            },
        },
        "load_path": [
            "R55 annular guide",
            "three removable guide saddles",
            "three axial posts",
            "three Y-yoke arms",
            "common hub",
            "180 mm-class main spine",
            "root neck",
            "candidate Link-3 attachment interface",
        ],
        "required_solid_checks": checks,
        "evaluation_accounting": {
            "solid_inventory": {
                "expected_count": len(required),
                "actual_evaluated_count": len(checks),
                "passing_count": sum(
                    c["present"] and c["valid_solid"] and c["positive_volume"]
                    and c["host_is_link3"] for c in checks
                ),
                "empty_comparison_count": int(len(checks) == 0),
            },
            "mass": mass_evaluation,
            "declared_interface_bbox_chain": {
                "expected_count": len(declared_interfaces),
                "actual_evaluated_count": interface_actual_evaluated,
                "passing_count": interface_passing,
                "empty_comparison_count": int(interface_actual_evaluated == 0),
            },
        },
        "declared_interface_geometry_chain": interface_chain,
        "source_geometry_load_path_present": source_geometry_load_path_present,
        "support_chain_candidate_mass_g": support_mass_g,
        "missing_structural_inputs": missing_inputs,
        "missing_structural_input_count": len(missing_inputs),
        "stress_analysis": "NOT_EVALUATED_MISSING_LOADS_BOUNDARY_ALLOWABLES_AND_ACCEPTANCE_RULE",
        "buckling_analysis": "NOT_EVALUATED_MISSING_LOADS_EFFECTIVE_LENGTH_BOUNDARY_AND_ACCEPTANCE_RULE",
        "fastener_margin": "NOT_EVALUATED_MISSING_FASTENER_AND_DONOR_INTERFACE_DEFINITION",
        "modal_credit": "NONE__SUPPORT_NOT_BOUND_IN_CURRENT_R2_FULL_FLEX_MODEL",
        "verdict": (
            "PASS_SOURCE_GEOMETRY_LOAD_PATH_PRESENCE__HOLD_NOT_STRUCTURALLY_QUALIFIED"
            if source_geometry_load_path_present else
            "FAIL_OR_NOT_EVALUATED_SOURCE_GEOMETRY_MASS_OR_DECLARED_INTERFACE_CHAIN"),
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    print(doc["verdict"])


if __name__ == "__main__":
    main()
