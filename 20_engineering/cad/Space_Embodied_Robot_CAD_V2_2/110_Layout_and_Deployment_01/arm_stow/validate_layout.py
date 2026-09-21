"""Deterministic geometry and claim-boundary validation for Gate 4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from build123d import import_step

from arm_stow_layout import load_spec, make_entities


ROOT = Path(__file__).resolve().parent
STEP_PATH = ROOT / "arm_stow_layout.step"
RESULT_PATH = ROOT / "validation_results.json"
TOL = 1.0e-6


def _bbox(shape) -> list[float]:
    bb = shape.bounding_box()
    return [bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z]


def _size(bbox: list[float]) -> list[float]:
    return [bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]]


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return min(a1, b1) - max(a0, b0)


def _face_contact(a: list[float], b: list[float]) -> dict[str, Any]:
    overlaps = [
        _overlap(a[0], a[3], b[0], b[3]),
        _overlap(a[1], a[4], b[1], b[4]),
        _overlap(a[2], a[5], b[2], b[5]),
    ]
    touching_axes = []
    for axis, (amin, amax, bmin, bmax) in enumerate(
        ((a[0], a[3], b[0], b[3]), (a[1], a[4], b[1], b[4]), (a[2], a[5], b[2], b[5]))
    ):
        if abs(amax - bmin) <= TOL or abs(bmax - amin) <= TOL:
            touching_axes.append(axis)
    positive_overlap_axes = [index for index, value in enumerate(overlaps) if value > TOL]
    return {
        "touching_axes": touching_axes,
        "axis_overlaps_mm": overlaps,
        "has_face_contact": len(touching_axes) >= 1 and len(positive_overlap_axes) >= 2,
    }


def _step_labels(shape) -> list[str]:
    labels = []

    def walk(node):
        label = getattr(node, "label", None)
        if label:
            labels.append(str(label))
        for child in getattr(node, "children", []) or []:
            walk(child)

    walk(shape)
    return labels


def run() -> dict[str, Any]:
    spec = load_spec()
    entities = make_entities()
    checks = []

    def record(check_id: str, passed: bool, evidence: Any):
        checks.append({"id": check_id, "status": "PASS" if passed else "FAIL", "evidence": evidence})

    record("STEP_EXISTS", STEP_PATH.is_file() and STEP_PATH.stat().st_size > 0, str(STEP_PATH))
    if not STEP_PATH.is_file():
        raise FileNotFoundError(STEP_PATH)

    exported = import_step(STEP_PATH)
    exported_solids = list(exported.solids())
    positive_volumes = [float(s.volume) for s in exported_solids]
    record(
        "STEP_POSITIVE_VOLUME_SOLIDS",
        bool(positive_volumes) and min(positive_volumes) > 0.0,
        {"solid_count": len(positive_volumes), "min_volume_mm3": min(positive_volumes)},
    )

    exported_labels = _step_labels(exported)
    required_labels = [entity["label"] for entity in spec["entities"]]
    missing_labels = [label for label in required_labels if label not in exported_labels]
    record(
        "STEP_REQUIRED_ENTITY_LABELS",
        not missing_labels,
        {"required": len(required_labels), "exported_label_count": len(exported_labels), "missing": missing_labels},
    )

    frozen = spec["frozen_inputs"]
    expected_span = 2.0 * abs(frozen["upper_longeron_centreline_y"][1])
    for beam_id, x_region in (
        ("CROSSBEAM_FORWARD", frozen["forward_support_x_region"]),
        ("CROSSBEAM_AFT", frozen["aft_support_x_region"]),
    ):
        bb = _bbox(entities[beam_id])
        size = _size(bb)
        record(
            f"{beam_id}_SPAN",
            abs(size[1] - expected_span) <= TOL,
            {"measured_y_span_mm": size[1], "required_y_span_mm": expected_span},
        )
        record(
            f"{beam_id}_X_REGION",
            abs(bb[0] - x_region[0]) <= TOL and abs(bb[3] - x_region[1]) <= TOL,
            {"measured_x_bounds_mm": [bb[0], bb[3]], "required_x_region_mm": x_region},
        )

    station_checks = {
        "SADDLE_BRACKET_PORT": frozen["forward_support_x_region"],
        "SADDLE_BRACKET_STARBOARD": frozen["forward_support_x_region"],
        "WRIST_BRACKET_PORT": frozen["aft_support_x_region"],
        "WRIST_BRACKET_STARBOARD": frozen["aft_support_x_region"],
        "MAIN_SOFT_SUPPORT_RESERVATION": frozen["forward_support_x_region"],
        "WRIST_SOFT_SUPPORT_RESERVATION": frozen["aft_support_x_region"],
    }
    station_evidence = {}
    stations_pass = True
    for entity_id, region in station_checks.items():
        bb = _bbox(entities[entity_id])
        passed = bb[0] >= region[0] - TOL and bb[3] <= region[1] + TOL
        stations_pass = stations_pass and passed
        station_evidence[entity_id] = {
            "measured_x_bounds_mm": [bb[0], bb[3]],
            "required_x_region_mm": region,
            "status": "PASS" if passed else "FAIL",
        }
    record(
        "MAIN_SADDLE_AND_WRIST_STATION_SEMANTICS",
        stations_pass,
        station_evidence,
    )

    platform_half_width = frozen["platform_half_width_y"]
    pad_evidence = {}
    pads_pass = True
    for pad_id in (
        "PAD_FORWARD_PORT",
        "PAD_FORWARD_STARBOARD",
        "PAD_AFT_PORT",
        "PAD_AFT_STARBOARD",
    ):
        bb = _bbox(entities[pad_id])
        max_abs_y = max(abs(bb[1]), abs(bb[4]))
        passed = max_abs_y <= platform_half_width + TOL
        pads_pass = pads_pass and passed
        pad_evidence[pad_id] = {
            "measured_max_abs_y_mm": max_abs_y,
            "platform_half_width_mm": platform_half_width,
            "status": "PASS" if passed else "FAIL",
        }
    record("PHYSICAL_PAD_Y_CONTAINMENT", pads_pass, pad_evidence)

    staging_transform = spec["staging_transform_to_cs_s"]
    tz = staging_transform["translation_mm"][2]
    mapped_pad_lower_faces = {
        pad_id: _bbox(entities[pad_id])[2] + tz
        for pad_id in (
            "PAD_FORWARD_PORT",
            "PAD_FORWARD_STARBOARD",
            "PAD_AFT_PORT",
            "PAD_AFT_STARBOARD",
        )
    }
    transform_pass = (
        staging_transform["rotation_matrix_row_major"]
        == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        and all(
            abs(value - frozen["bus_top_exterior_z"]) <= TOL
            for value in mapped_pad_lower_faces.values()
        )
        and staging_transform["status"]
        == "DESIGN_PROPOSAL_SELECTED_FOR_ISOLATED_STAGING"
        and staging_transform["ratification"] == "HOLD"
    )
    record(
        "NUMERIC_TOP_LAYOUT_TO_CS_S_STAGING_TRANSFORM",
        transform_pass,
        {
            "translation_mm": staging_transform["translation_mm"],
            "rotation_matrix_row_major": staging_transform[
                "rotation_matrix_row_major"
            ],
            "mapped_pad_lower_faces_z_mm": mapped_pad_lower_faces,
            "required_bus_top_exterior_z_mm": frozen["bus_top_exterior_z"],
            "status": staging_transform["status"],
            "ratification": staging_transform["ratification"],
        },
    )

    corridor_bbox = _bbox(entities["ARM_KEEP_OUT_FROZEN"])
    corridor_width = corridor_bbox[4] - corridor_bbox[1]
    record(
        "FROZEN_CORRIDOR_WIDTH",
        abs(corridor_width - 80.0) <= TOL and abs(corridor_bbox[1] + 40.0) <= TOL and abs(corridor_bbox[4] - 40.0) <= TOL,
        {"measured_y_bounds_mm": [corridor_bbox[1], corridor_bbox[4]], "measured_width_mm": corridor_width},
    )

    equipment_clearances = {}
    equipment_pass = True
    for entity_id in spec["equipment_reservation_ids"]:
        bb = _bbox(entities[entity_id])
        if bb[1] >= 0.0:
            clearance = bb[1] - 40.0
        elif bb[4] <= 0.0:
            clearance = -40.0 - bb[4]
        else:
            clearance = -40.0
        equipment_clearances[entity_id] = clearance
        equipment_pass = equipment_pass and clearance >= -TOL
    record(
        "NO_EQUIPMENT_INTRUSION_IN_FROZEN_CORRIDOR",
        equipment_pass,
        {"minimum_clearance_from_abs_y40_mm": min(equipment_clearances.values()), "by_entity_mm": equipment_clearances},
    )

    contact_evidence = {}
    contacts_pass = True
    for left_id, right_id in spec["contact_pairs"]:
        left = entities[left_id]
        right = entities[right_id]
        distance = float(left.distance_to(right))
        face = _face_contact(_bbox(left), _bbox(right))
        passed = distance <= TOL and face["has_face_contact"]
        contacts_pass = contacts_pass and passed
        contact_evidence[f"{left_id}__{right_id}"] = {
            "distance_mm": distance,
            **face,
            "status": "PASS" if passed else "FAIL",
        }
    record("PHYSICAL_SUPPORT_CONTACTS_NOT_FLOATING", contacts_pass, contact_evidence)

    authority = spec["authority_exclusions"]
    boundary_pass = (
        authority["mass_authority"] == "EXCLUDED"
        and authority["kinematic_authority"] == "NONE"
        and authority["strength_authority"] == "NONE"
        and authority["stiffness_authority"] == "NONE"
        and authority["flight_qualification"] == "NONE"
        and authority["vendor_shell_support_suitability"] == "NOT_CLAIMED"
    )
    record("CLAIM_BOUNDARY_FAIL_CLOSED", boundary_pass, authority)

    outer = spec["proposal_parameters"]["outer_clearance_half_width_y"]
    record(
        "OUTER_CLEARANCE_EXPLICITLY_PROPOSAL",
        outer["classification"] == "DESIGN_PROPOSAL" and outer["status"] == "TBD_HOLD",
        outer,
    )

    step_bytes = STEP_PATH.read_bytes()
    step_bbox = _bbox(exported)
    result = {
        "schema_version": "1.0",
        "decision_id": spec["decision_id"],
        "artifact": {
            "path": str(STEP_PATH),
            "sha256": hashlib.sha256(step_bytes).hexdigest(),
            "bytes": len(step_bytes),
            "bbox_mm": step_bbox,
            "size_mm": _size(step_bbox),
            "positive_volume_solid_count": len(positive_volumes),
        },
        "checks": checks,
        "summary": {
            "pass": sum(check["status"] == "PASS" for check in checks),
            "fail": sum(check["status"] == "FAIL" for check in checks),
            "verdict": "PASS_WITH_ENGINEERING_HOLDS" if all(check["status"] == "PASS" for check in checks) else "FAIL",
        },
        "claim_status": "LAYOUT_GEOMETRY_ONLY",
        "engineering_status": "DESIGN_PROPOSAL_TBD_HOLD",
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
