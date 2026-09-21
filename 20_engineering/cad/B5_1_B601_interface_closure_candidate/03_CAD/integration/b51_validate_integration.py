"""Selected BREP and proximity checks for the B5.1 render context.

The checks are deliberately scoped.  They do not re-adjudicate the inherited
28-item V14 ledger or substitute for continuous solar/arm motion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from b51_spacecraft_context_common import (
    ARM_STEP,
    BRIDGE_STEP,
    CLAIM_LIMIT,
    GRIP_SADDLE_STEP,
    GROUP_ORDER,
    MAIN_SADDLE_STEP,
    MASS_AUTHORITY,
    REGISTRATION_JSON,
    build_component_map,
    source_contract,
)


HERE = Path(__file__).resolve().parent


def _bbox(shape):
    box = shape.bounding_box()
    return {
        "min": [box.min.X, box.min.Y, box.min.Z],
        "max": [box.max.X, box.max.Y, box.max.Z],
        "size": [box.size.X, box.size.Y, box.size.Z],
    }


def _bbox_diagnostic(left, right):
    lb = _bbox(left)
    rb = _bbox(right)
    gaps = []
    overlap_lengths = []
    for axis in range(3):
        gap = max(
            rb["min"][axis] - lb["max"][axis],
            lb["min"][axis] - rb["max"][axis],
            0.0,
        )
        gaps.append(gap)
        overlap_lengths.append(
            max(
                min(lb["max"][axis], rb["max"][axis])
                - max(lb["min"][axis], rb["min"][axis]),
                0.0,
            )
        )
    return {
        "axis_gaps_mm": gaps,
        "aabb_overlap_lengths_mm": overlap_lengths,
        "aabb_overlap_volume_mm3": (
            overlap_lengths[0] * overlap_lengths[1] * overlap_lengths[2]
        ),
    }


def _common_volume(left, right):
    started = time.perf_counter()
    try:
        common = left & right
        value = sum(solid.volume for solid in common.solids())
        return {
            "status": "COMPUTED",
            "common_volume_mm3": value,
            "elapsed_s": time.perf_counter() - started,
        }
    except Exception as exc:  # vendor BREP may reject some booleans
        return {
            "status": "NOT_COMPUTABLE_VENDOR_BREP_LIMIT",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_s": time.perf_counter() - started,
        }


def _minimum_distance(left, right):
    started = time.perf_counter()
    try:
        value = float(left.distance_to(right))
        return {
            "status": "COMPUTED",
            "minimum_distance_mm": value,
            "elapsed_s": time.perf_counter() - started,
        }
    except Exception as exc:
        return {
            "status": "NOT_COMPUTABLE_VENDOR_BREP_LIMIT",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_s": time.perf_counter() - started,
        }


def _sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _brep_entry(shape):
    solids = list(shape.solids())
    invalid = sum(not solid.is_valid for solid in solids)
    return {
        "compound_is_valid": bool(shape.is_valid),
        "solid_count": len(solids),
        "valid_solid_count": len(solids) - invalid,
        "invalid_solid_count": invalid,
        "bbox_mm": _bbox(shape),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            HERE.parent.parent
            / "07_VERIFICATION"
            / "renders"
            / "B51_INTEGRATION_GEOMETRY_CHECKS.json"
        ),
    )
    args = parser.parse_args()

    components = build_component_map(include_arm=True)
    arm_groups = {
        group_id: group
        for group_id, group in zip(
            GROUP_ORDER, list(components["b601_stow"].children)
        )
    }

    pair_specs = [
        (
            "bridge_vs_primary",
            components["bridge_adapter"],
            components["primary_structure"],
            True,
            "INTERFACE_LOCAL_DIAGNOSTIC",
        ),
        (
            "main_saddle_vs_primary",
            components["main_saddle"],
            components["primary_structure"],
            True,
            "SUPPORT_TO_PRIMARY_LOCAL_DIAGNOSTIC",
        ),
        (
            "grip_saddle_vs_primary",
            components["grip_saddle"],
            components["primary_structure"],
            True,
            "SUPPORT_TO_PRIMARY_LOCAL_DIAGNOSTIC",
        ),
        (
            "bridge_vs_b601_G06_base",
            components["bridge_adapter"],
            arm_groups["G06"],
            True,
            "EXPECTED_INSTALLATION_INTERFACE_REQUIRES_DISPOSITION",
        ),
        (
            "main_saddle_vs_b601_G07",
            components["main_saddle"],
            arm_groups["G07"],
            True,
            "EXPECTED_CONTACT_REGION_QUALIFICATION_HOLD",
        ),
        (
            "grip_saddle_vs_b601_G08",
            components["grip_saddle"],
            arm_groups["G08"],
            True,
            "EXPECTED_CONTACT_REGION_CHAIN_DERIVED_HOLD",
        ),
        (
            "bridge_vs_solar_stow",
            components["bridge_adapter"],
            components["solar_stow"],
            True,
            "STATIC_ENDPOINT_LOCAL_DIAGNOSTIC",
        ),
        (
            "main_saddle_vs_solar_stow",
            components["main_saddle"],
            components["solar_stow"],
            True,
            "STATIC_ENDPOINT_LOCAL_DIAGNOSTIC",
        ),
        (
            "grip_saddle_vs_solar_stow",
            components["grip_saddle"],
            components["solar_stow"],
            True,
            "STATIC_ENDPOINT_LOCAL_DIAGNOSTIC",
        ),
        (
            "whole_b601_stow_vs_primary",
            components["b601_stow"],
            components["primary_structure"],
            False,
            "LARGE_VENDOR_BREP_DISTANCE_ONLY",
        ),
        (
            "whole_b601_stow_vs_solar_stow",
            components["b601_stow"],
            components["solar_stow"],
            False,
            "LARGE_VENDOR_BREP_DISTANCE_ONLY",
        ),
    ]

    checks = {}
    for name, left, right, run_common, scope in pair_specs:
        entry = {
            "scope": scope,
            "bbox_diagnostic": _bbox_diagnostic(left, right),
            "minimum_distance": _minimum_distance(left, right),
        }
        if run_common:
            entry["exact_common"] = _common_volume(left, right)
        else:
            entry["exact_common"] = {
                "status": "NOT_RUN_SCOPE_LIMIT",
                "reason": (
                    "Large imported vendor compound; this bounded visualization "
                    "task does not replace the inherited 28-item H10 ledger."
                ),
            }
        common = entry["exact_common"]
        if common.get("status") == "COMPUTED":
            entry["interpretation"] = (
                "INTERSECTION_PRESENT_DO_NOT_CLOSE_H10"
                if common["common_volume_mm3"] > 1.0e-6
                else "ZERO_COMMON_VOLUME_FOR_THIS_PAIR_ONLY_NOT_GLOBAL_CLEARANCE"
            )
        else:
            entry["interpretation"] = "UNKNOWN_FAIL_CLOSED"
        checks[name] = entry

    output_step = HERE / "B51_SPACECRAFT_B601_STOW_INTEGRATION.step"
    solar_step = HERE / "B51_SOLAR_STATE_REFERENCE.step"
    provenance_paths = [
        ARM_STEP,
        REGISTRATION_JSON,
        BRIDGE_STEP,
        MAIN_SADDLE_STEP,
        GRIP_SADDLE_STEP,
    ]
    if output_step.exists():
        provenance_paths.append(output_step)
    if solar_step.exists():
        provenance_paths.append(solar_step)

    report = {
        "schema": "SER_B51_INTEGRATION_GEOMETRY_CHECKS_V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "ENGINEERING_CANDIDATE_RENDER_CONTEXT_WITH_H9_H10_MOTION_HOLDS"
        ),
        "source_contract": source_contract(),
        "brep": {
            name: _brep_entry(shape)
            for name, shape in components.items()
        },
        "selected_pair_checks": checks,
        "provenance_sha256": {
            str(path): _sha256(path) for path in provenance_paths
        },
        "authority": {
            "mass": MASS_AUTHORITY,
            "claim_limit": CLAIM_LIMIT,
        },
        "explicit_holds": [
            "H9 HUMAN_DECISION_REQUIRED; Mode A/Mode B shells are non-physical witnesses.",
            "H10 NOT CLOSED; inherited 28 items were not reclassified or cleared.",
            "Vendor STOW STEP compound BREP validity is reported as imported; no healing modifies the donor.",
            "Solar views are endpoints only; no continuous clearance curve is produced.",
            "No HDRM release, harness, tolerance, preload, load, modal, manufacturing, or flight conclusion.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

