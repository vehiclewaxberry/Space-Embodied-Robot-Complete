"""Exact-BREP diagnostic of B5.1 hardware against canonical native V2.2.

This script intentionally does not rewrite the 28-row inherited ledger.  It
separates the canonical primary load structure, removable panels, obsolete
B601 mount/support occurrences, and solar roots, then checks the current B5.1
STEP candidates against those groups.  The result is diagnostic evidence for
H10; zero common volume alone is never treated as an accepted attachment.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build123d import import_step


CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_COPY = (
    CANDIDATE_ROOT
    / "00_BASELINE_DONORS"
    / "V2_2_NATIVE_CANONICAL_108_FILE_COPY"
)
CANONICAL_STEP = (
    CANONICAL_COPY / "evidence" / "config_steps" / "native_STOWED.step"
)
STEP_ROOT = CANDIDATE_ROOT / "03_CAD" / "step"
CANDIDATE_STEPS = {
    "bridge_adapter": STEP_ROOT / "B51_BRIDGE_ADAPTER.step",
    "g07_main_saddle": STEP_ROOT / "B51_G07_MAIN_SADDLE.step",
    "g08_grip_saddle": STEP_ROOT / "B51_G08_GRIP_SADDLE.step",
}
OUTPUT = (
    CANDIDATE_ROOT
    / "07_VERIFICATION"
    / "interface"
    / "B51_CANONICAL_INTERFACE_BREP_AUDIT.json"
)
CANONICAL_SPEC = CANONICAL_COPY / "automation" / "native_spec.py"
B51_DATUM_REGISTER = (
    CANDIDATE_ROOT
    / "01_REQUIREMENTS"
    / "B51_MASTER_SKELETON_DATUM_REGISTER.yaml"
)
B51_GEOMETRY_SOURCE = (
    CANDIDATE_ROOT
    / "02_DESIGN"
    / "geometry"
    / "b51_geometry_common.py"
)

GROUP_LABELS = {
    "primary_structure": "01_Primary_Structure_V2_2",
    "removable_panels": "Removable_Panels",
    "obsolete_b601_mount": "02_B601_Mount_and_Load_Path",
    "obsolete_arm_stow_support": "04_ARM_STOW_SUPPORT",
    "solar_root_left": "05_Solar_Array_Root_Left",
    "solar_root_right": "06_Solar_Array_Root_Right",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def bbox(shape: Any) -> dict[str, list[float]]:
    box = shape.bounding_box()
    return {
        "min": [box.min.X, box.min.Y, box.min.Z],
        "max": [box.max.X, box.max.Y, box.max.Z],
        "size": [box.size.X, box.size.Y, box.size.Z],
    }


def brep_summary(shape: Any) -> dict[str, Any]:
    solids = list(shape.solids())
    invalid = [index for index, solid in enumerate(solids) if not solid.is_valid]
    return {
        "label": str(shape.label),
        "compound_is_valid": bool(shape.is_valid),
        "solid_count": len(solids),
        "invalid_solid_indices": invalid,
        "bbox_mm": bbox(shape),
    }


def pair_check(left: Any, right: Any) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        distance = float(left.distance_to(right))
        distance_record: dict[str, Any] = {
            "status": "COMPUTED",
            "minimum_distance_mm": distance,
        }
    except Exception as exc:
        distance_record = {
            "status": "NOT_COMPUTABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    try:
        common = left & right
        volume = float(sum(solid.volume for solid in common.solids()))
        common_record: dict[str, Any] = {
            "status": "COMPUTED",
            "common_volume_mm3": volume,
        }
    except Exception as exc:
        common_record = {
            "status": "NOT_COMPUTABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "minimum_distance": distance_record,
        "exact_common": common_record,
        "elapsed_s": time.perf_counter() - started,
        "interpretation": (
            "INTERSECTION_PRESENT"
            if common_record.get("common_volume_mm3", 0.0) > 1.0e-6
            else (
                "ZERO_COMMON_VOLUME_NOT_ATTACHMENT_PROOF"
                if common_record.get("status") == "COMPUTED"
                else "UNKNOWN_FAIL_CLOSED"
            )
        ),
    }


def selected_children(shape: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for child in shape.children:
        label = str(child.label)
        if "SHOE" in label:
            result[label] = child
    return result


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"append-only output already exists: {OUTPUT}")
    required = [
        CANONICAL_STEP,
        CANONICAL_SPEC,
        B51_DATUM_REGISTER,
        B51_GEOMETRY_SOURCE,
        *CANDIDATE_STEPS.values(),
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"required inputs missing: {missing}")

    canonical = import_step(CANONICAL_STEP)
    by_label = {str(child.label): child for child in canonical.children}
    absent_labels = sorted(
        label for label in GROUP_LABELS.values() if label not in by_label
    )
    if absent_labels:
        raise RuntimeError(f"canonical STEP groups missing: {absent_labels}")
    groups = {
        role: by_label[label] for role, label in GROUP_LABELS.items()
    }
    candidates = {
        role: import_step(path) for role, path in CANDIDATE_STEPS.items()
    }

    group_checks: dict[str, Any] = {}
    for candidate_role, candidate in candidates.items():
        group_checks[candidate_role] = {
            group_role: pair_check(candidate, group)
            for group_role, group in groups.items()
        }
    shoe_checks: dict[str, Any] = {}
    for candidate_role, candidate in candidates.items():
        shoe_checks[candidate_role] = {}
        for label, shoe in selected_children(candidate).items():
            shoe_checks[candidate_role][label] = {
                "bbox_mm": bbox(shoe),
                "vs_primary_structure": pair_check(
                    shoe, groups["primary_structure"]
                ),
                "vs_removable_panels": pair_check(
                    shoe, groups["removable_panels"]
                ),
            }

    g07_primary_distance = group_checks["g07_main_saddle"][
        "primary_structure"
    ]["minimum_distance"].get("minimum_distance_mm")
    g08_primary_distance = group_checks["g08_grip_saddle"][
        "primary_structure"
    ]["minimum_distance"].get("minimum_distance_mm")
    g07_panel_distance = group_checks["g07_main_saddle"][
        "removable_panels"
    ]["minimum_distance"].get("minimum_distance_mm")
    g08_panel_distance = group_checks["g08_grip_saddle"][
        "removable_panels"
    ]["minimum_distance"].get("minimum_distance_mm")
    diagnostic_reproduced = all(
        value is not None
        for value in (
            g07_primary_distance,
            g08_primary_distance,
            g07_panel_distance,
            g08_panel_distance,
        )
    ) and (
        abs(float(g07_primary_distance) - 3.0) <= 1.0e-6
        and abs(float(g08_primary_distance) - 3.0) <= 1.0e-6
        and abs(float(g07_panel_distance)) <= 1.0e-6
        and abs(float(g08_panel_distance)) <= 1.0e-6
    )

    payload = {
        "schema": "SER_B51_CANONICAL_INTERFACE_BREP_AUDIT_V1",
        "generated_utc": utc_now(),
        "status": (
            "H10_CANONICAL_BREP_DIAGNOSTIC_FEASIBLE_"
            "GEOMETRY_REDESIGN_REQUIRED"
        ),
        "source_hashes": {
            str(path.resolve()): sha256_file(path)
            for path in [CANONICAL_STEP, *CANDIDATE_STEPS.values()]
        },
        "canonical": {
            "step": str(CANONICAL_STEP.resolve()),
            "summary": brep_summary(canonical),
            "groups": {
                role: brep_summary(shape)
                for role, shape in groups.items()
            },
        },
        "candidates": {
            role: {
                "step": str(CANDIDATE_STEPS[role].resolve()),
                "summary": brep_summary(shape),
                "non_physical_children": [
                    str(child.label)
                    for child in shape.children
                    if "NON_PHYSICAL" in str(child.label)
                ],
            }
            for role, shape in candidates.items()
        },
        "exact_brep_group_checks": group_checks,
        "exact_brep_interface_shoe_checks": shoe_checks,
        "canonical_datum_conflict": {
            "canonical_source": str(CANONICAL_SPEC.resolve()),
            "canonical_longeron_center_abs_yz_mm": 101.65,
            "canonical_primary_outer_surface_abs_yz_mm": 110.15,
            "canonical_panel_outer_surface_abs_yz_mm": 113.15,
            "b51_sources": [
                str(B51_DATUM_REGISTER.resolve()),
                str(B51_GEOMETRY_SOURCE.resolve()),
            ],
            "b51_longeron_center_abs_yz_mm": 105.65,
            "b51_saddle_lower_face_z_mm": 113.15,
            "longeron_center_offset_mm": 4.0,
            "saddle_to_primary_gap_mm": 3.0,
            "finding": (
                "CURRENT_SADDLE_SHOES_SEAT_ON_REMOVABLE_PANEL_"
                "SURFACE_NOT_DIRECTLY_ON_PRIMARY_LONGERON_OR_FRAME"
            ),
        },
        "reproduced_key_distances": {
            "g07_saddle_to_primary_mm": g07_primary_distance,
            "g08_saddle_to_primary_mm": g08_primary_distance,
            "g07_saddle_to_panels_mm": g07_panel_distance,
            "g08_saddle_to_panels_mm": g08_panel_distance,
            "diagnostic_reproduced": diagnostic_reproduced,
        },
        "h10": {
            "status": "FAIL_GEOMETRY_REDESIGN_REQUIRED",
            "reasons": [
                "The B5.1 datum register is bound to the legacy +/-105.65 mm longeron centers instead of canonical +/-101.65 mm.",
                "Both saddle candidates are 3.0 mm from the canonical primary structure and touch the removable-panel surface.",
                "Obsolete canonical B601 mount/support occurrences must be excluded or explicitly replaced before residual-collision closure.",
                "The inherited 28 rows lack deterministic old-occurrence to new-child mappings and local evidence.",
                "Zero common volume and zero distance do not prove a bolted, bonded, or otherwise qualified attachment.",
            ],
            "ledger_effect": (
                "NO_ROWS_CLOSED; APPEND_ONLY_DIAGNOSTIC_DOES_NOT_"
                "OVERWRITE_B51_INTERFERENCE_DISPOSITION_LEDGER.csv"
            ),
        },
        "claim_limit": (
            "Exact BREP diagnostic only. No material, fastener, preload, "
            "contact-area, tolerance, strength, manufacturing, release, "
            "or flight authority is created."
        ),
    }
    write_json_once(OUTPUT, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "diagnostic_reproduced": diagnostic_reproduced,
                "key_distances": payload["reproduced_key_distances"],
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if diagnostic_reproduced else 2


if __name__ == "__main__":
    raise SystemExit(main())
