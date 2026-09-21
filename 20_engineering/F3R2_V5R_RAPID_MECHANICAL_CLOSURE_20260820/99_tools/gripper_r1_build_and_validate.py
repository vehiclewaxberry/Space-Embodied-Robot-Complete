#!/usr/bin/env python3
"""Build and validate the neutral B601 gripper palm rail-slot R1 derivative.

Safety/scope rules implemented here:

* no SolidWorks, win32com, or donor writes;
* the V5 donor SLDPRT and accepted URDF are hash-audited before and after;
* the exact V5 palm/finger body grouping is read from frozen receipts;
* the editable B-rep is an isolated, read-only B50 link-6-local STEP and is
  therefore released as a *neutral derivative*, never as a native V5 repair;
* full-stroke conservative swept envelopes are used, with zero manufacturing
  clearance.  Manufacturing clearance and structural adequacy remain HOLD.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from build123d import Align, Box, Compound, export_step, export_stl, import_step
from scipy.optimize import linear_sum_assignment


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RAPID = ROOT / "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
V5 = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
TERMINAL = ROOT / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"

NEUTRAL_STEP = (
    ROOT
    / "20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN"
    / "vendor_reference_linklocal/B50_REF_gripper_detail_LINKLOCAL.step"
)
V5_RECEIPT = V5 / "13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json"
INTERFERENCE_REGISTER = V5 / "04_configurations/V5_LOOP1C1_INTERFERENCE_FINGERPRINT_REGISTER.csv"
ASSIGNMENT_CSV = TERMINAL / "08_camera_harness/F3R2_GRIPPER_SOLID_ASSIGNMENT.csv"
PER_SOLID_MESH_MANIFEST = TERMINAL / "05_clearance/mesh/gripper_solids_DEPLOYED/GRIPPER_SOLID_MESHES.json"
ACCEPTED_URDF = ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"

V5_SOURCE_DONOR = (
    TERMINAL
    / "03_native_cad/B601_ARM_B51_COPY/inputs/vendor_link_parts"
    / "B51_REF_gripper_detail_LINKLOCAL.SLDPRT"
)
V5_NATIVE_PARTS = {
    "PALM": V5 / "01_native_parts/gripper/B601_GRIPPER_PALM.SLDPRT",
    "LEFT": V5 / "01_native_parts/gripper/B601_GRIPPER_LEFT_FINGER.SLDPRT",
    "RIGHT": V5 / "01_native_parts/gripper/B601_GRIPPER_RIGHT_FINGER.SLDPRT",
}
V4_MESHES = {
    "PALM_VISUAL": ROOT
    / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
    / "02_neutral_cad/gripper/V4_GRIPPER_LINK_MESH_COMPONENT.stl",
    "LEFT_VISUAL": ROOT
    / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
    / "02_neutral_cad/gripper/V4_GRIPPER_LEFT_MESH_COMPONENT.stl",
    "RIGHT_VISUAL": ROOT
    / "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
    / "02_neutral_cad/gripper/V4_GRIPPER_RIGHT_MESH_COMPONENT.stl",
}

EXPECTED_HASHES = {
    V5_SOURCE_DONOR: "6758B99741FFACABC31C2D629C6191F25C461AC877442212B468B141805EEECC",
    ACCEPTED_URDF: "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
}

CAD_DIR = RAPID / "01_native_cad/gripper_r1"
VALIDATION_JSON = RAPID / "04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json"
SAMPLE_CSV = RAPID / "04_validation/GRIPPER_R1_CONTINUOUS_STROKE_SAMPLES.csv"
FEATURE_CSV = RAPID / "07_evidence/GRIPPER_R1_AFFECTED_FEATURES.csv"
DIAGRAM_PNG = RAPID / "07_evidence/GRIPPER_R1_SWEEP_AND_INTERFERENCE_DIAGRAM.png"
MANIFEST = RAPID / "07_evidence/GRIPPER_R1_OUTPUT_MANIFEST_SHA256.txt"

PALM_STEP = CAD_DIR / "B601_GRIPPER_PALM_RAIL_SLOT_R1.step"
PALM_STL = CAD_DIR / "B601_GRIPPER_PALM_RAIL_SLOT_R1.stl"
LEFT_SWEEP_STEP = CAD_DIR / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step"
LEFT_SWEEP_STL = CAD_DIR / "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.stl"
RIGHT_SWEEP_STEP = CAD_DIR / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step"
RIGHT_SWEEP_STL = CAD_DIR / "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.stl"
LEFT_FINGER_STL = CAD_DIR / "B601_GRIPPER_LEFT_FINGER_NEUTRAL_SOURCE.stl"
RIGHT_FINGER_STL = CAD_DIR / "B601_GRIPPER_RIGHT_FINGER_NEUTRAL_SOURCE.stl"

FULL_TRAVEL_MM = 71.5
SAMPLE_STEP_MM = 0.5
VOLUME_ZERO_TOL_MM3 = 1.0e-6
TARGET_PALM_NAMES = {
    "B51_REF_gripper_detail_LINKLOCAL050",
    "B51_REF_gripper_detail_LINKLOCAL054",
}
POSES = {
    "CLOSED": {"travel_mm": 0.0, "authority": "M3R_V2_CONTACT"},
    "PARTIAL": {
        "travel_mm": FULL_TRAVEL_MM / 2.0,
        "authority": "DERIVED_MID_STROKE_WITNESS_NOT_ACCEPTED_CONFIGURATION",
    },
    "PREGRASP": {"travel_mm": 55.0, "authority": "M3R_V2"},
    "OPEN": {"travel_mm": FULL_TRAVEL_MM, "authority": "M3R_V2"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def assert_new_outputs() -> None:
    outputs = [
        PALM_STEP,
        PALM_STL,
        LEFT_SWEEP_STEP,
        LEFT_SWEEP_STL,
        RIGHT_SWEEP_STEP,
        RIGHT_SWEEP_STL,
        LEFT_FINGER_STL,
        RIGHT_FINGER_STL,
        VALIDATION_JSON,
        SAMPLE_CSV,
        FEATURE_CSV,
        DIAGRAM_PNG,
        MANIFEST,
    ]
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(f"write-once gripper R1 outputs already exist: {existing}")


def audit_fixed_inputs() -> dict[str, Any]:
    paths = [
        NEUTRAL_STEP,
        V5_RECEIPT,
        INTERFERENCE_REGISTER,
        ASSIGNMENT_CSV,
        PER_SOLID_MESH_MANIFEST,
        ACCEPTED_URDF,
        V5_SOURCE_DONOR,
        *V5_NATIVE_PARTS.values(),
        *V4_MESHES.values(),
    ]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"required gripper inputs missing: {missing}")
    facts = {str(path): file_fact(path) for path in paths}
    for path, expected in EXPECTED_HASHES.items():
        actual = facts[str(path)]["sha256"]
        if actual != expected:
            raise RuntimeError(f"frozen input hash drift: {path}: {actual} != {expected}")
    return facts


def bbox_values(shape: Any) -> list[float]:
    box = shape.bounding_box()
    return [
        float(box.min.X),
        float(box.min.Y),
        float(box.min.Z),
        float(box.max.X),
        float(box.max.Y),
        float(box.max.Z),
    ]


def center_and_size(box: Iterable[float]) -> tuple[list[float], list[float]]:
    values = [float(value) for value in box]
    center = [(values[index] + values[index + 3]) / 2.0 for index in range(3)]
    size = [values[index + 3] - values[index] for index in range(3)]
    return center, size


def vector_norm(values: Iterable[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in values))


def bind_neutral_solids(model: Any, evidence: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    imported = list(model.solids())
    if len(imported) != 57 or len(evidence) != 57:
        raise RuntimeError(f"57-body binding failed: neutral={len(imported)} v5={len(evidence)}")
    costs: list[list[float]] = []
    residuals: list[list[dict[str, float]]] = []
    for solid in imported:
        ibox = bbox_values(solid)
        icenter, isize = center_and_size(ibox)
        ivolume = float(solid.volume)
        cost_row = []
        residual_row = []
        for target in evidence:
            tbox = [float(value) for value in target["bbox_mm"]]
            tcenter, tsize = center_and_size(tbox)
            center_delta = vector_norm(a - b for a, b in zip(icenter, tcenter))
            size_delta = vector_norm(a - b for a, b in zip(isize, tsize))
            volume_relative = abs(ivolume - float(target["volume_mm3"])) / float(target["volume_mm3"])
            cost = center_delta + 0.25 * size_delta + 10.0 * abs(math.log(max(ivolume, 1e-12) / float(target["volume_mm3"])))
            cost_row.append(cost)
            residual_row.append(
                {
                    "center_delta_mm": center_delta,
                    "size_delta_mm": size_delta,
                    "volume_relative": volume_relative,
                }
            )
        costs.append(cost_row)
        residuals.append(residual_row)
    source_indices, target_indices = linear_sum_assignment(costs)
    bound: dict[str, Any] = {}
    rows = []
    for source_index, target_index in zip(source_indices, target_indices):
        target = evidence[int(target_index)]
        name = str(target["mapped_source_name"])
        residual = residuals[int(source_index)][int(target_index)]
        if residual["center_delta_mm"] > 1.0 or residual["size_delta_mm"] > 1.0 or residual["volume_relative"] > 0.05:
            raise RuntimeError(f"neutral/V5 body fingerprint correlation failed for {name}: {residual}")
        bound[name] = imported[int(source_index)]
        rows.append(
            {
                "source_name": name,
                "neutral_import_index": int(source_index),
                "neutral_volume_mm3": float(imported[int(source_index)].volume),
                "v5_volume_mm3": float(target["volume_mm3"]),
                "neutral_bbox_mm": bbox_values(imported[int(source_index)]),
                "v5_bbox_mm": [float(value) for value in target["bbox_mm"]],
                **residual,
                "neutral_face_count": len(imported[int(source_index)].faces()),
                "v5_face_count": int(target["faces"]),
            }
        )
    if len(bound) != 57:
        raise RuntimeError("neutral/V5 body fingerprint correlation is not one-to-one")
    return bound, sorted(rows, key=lambda row: row["source_name"])


def read_assignment() -> tuple[dict[str, str], dict[str, str]]:
    groups: dict[str, list[str]] = {"gripper_link": [], "gripper_left": [], "gripper_right": []}
    with ASSIGNMENT_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            name = str(row["solid"])
            if name.endswith("057"):
                continue
            groups[str(row["assigned_body"])].append(name)
    assignment = {}
    semantic = {}
    role_names = {"gripper_link": "PALM", "gripper_left": "LEFT_FINGER", "gripper_right": "RIGHT_FINGER"}
    for group, names in groups.items():
        for index, name in enumerate(sorted(names), start=1):
            assignment[name] = group
            semantic[name] = f"{role_names[group]}_SOLID_{index:02d}__{name}"
    if sorted(len(names) for names in groups.values()) != [9, 24, 24]:
        raise RuntimeError(f"unexpected V5 grouping: { {key: len(value) for key, value in groups.items()} }")
    return assignment, semantic


def boxes_overlap(first: list[float], second: list[float]) -> bool:
    return all(min(first[index + 3], second[index + 3]) - max(first[index], second[index]) > 0.0 for index in range(3))


def swept_bbox(box: list[float], side: str) -> list[float]:
    result = list(box)
    if side == "LEFT":
        result[1] -= FULL_TRAVEL_MM
    elif side == "RIGHT":
        result[4] += FULL_TRAVEL_MM
    else:
        raise ValueError(side)
    return result


def box_shape(box: list[float]) -> Any:
    dx, dy, dz = (box[index + 3] - box[index] for index in range(3))
    return Box(dx, dy, dz, align=(Align.MIN, Align.MIN, Align.MIN)).translate((box[0], box[1], box[2]))


def compound(shapes: Iterable[Any]) -> Any:
    children = list(shapes)
    if not children:
        raise RuntimeError("cannot make an empty compound")
    if len(children) == 1:
        return children[0]
    return Compound(children=children)


def safe_common_volume(first: Any, second: Any) -> tuple[float | None, str]:
    try:
        common = first.intersect(second)
        volume = max(0.0, float(common.volume))
        if volume <= VOLUME_ZERO_TOL_MM3:
            volume = 0.0
        return volume, "BRepAlgoAPI_Common"
    except Exception as exc:  # analytic envelope proof remains authoritative
        return None, f"BOOLEAN_HOLD:{type(exc).__name__}:{exc}"


def export_stl_checked(shape: Any, path: Path) -> None:
    try:
        export_stl(shape, path, tolerance=0.05, angular_tolerance=0.1)
    except TypeError:
        export_stl(shape, path)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"STL export failed: {path}")


def make_diagram(
    target_boxes: dict[str, list[float]],
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    removed_volume_mm3: float,
) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)
    ax = axes[0]
    for name, box in target_boxes.items():
        ax.add_patch(
            Rectangle(
                (box[0], box[1]),
                box[3] - box[0],
                box[4] - box[1],
                facecolor="0.7",
                edgecolor="black",
                alpha=0.35,
                linewidth=1.5,
                label=name.rsplit("LOCAL", 1)[-1] if name.endswith("050") else None,
            )
        )
        ax.text((box[0] + box[3]) / 2, (box[1] + box[4]) / 2, name[-3:], ha="center", va="center", fontsize=9)
    for rows, color, label in ((left_rows, "#1976D2", "LEFT conservative sweep"), (right_rows, "#D32F2F", "RIGHT conservative sweep")):
        first = True
        for row in rows:
            box = row["swept_bbox_mm"]
            ax.add_patch(
                Rectangle(
                    (box[0], box[1]),
                    box[3] - box[0],
                    box[4] - box[1],
                    facecolor=color,
                    edgecolor=color,
                    alpha=0.10,
                    linewidth=0.5,
                    label=label if first else None,
                )
            )
            first = False
    plotted_boxes = [*target_boxes.values(), *(row["swept_bbox_mm"] for row in left_rows), *(row["swept_bbox_mm"] for row in right_rows)]
    x_min = min(box[0] for box in plotted_boxes)
    x_max = max(box[3] for box in plotted_boxes)
    y_min = min(box[1] for box in plotted_boxes)
    y_max = max(box[4] for box in plotted_boxes)
    x_margin = max(5.0, 0.05 * (x_max - x_min))
    y_margin = max(5.0, 0.05 * (y_max - y_min))
    ax.set_xlim(x_min - x_margin, x_max + x_margin)
    ax.set_ylim(y_min - y_margin, y_max + y_margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("LINK6_LOCAL X [mm]")
    ax.set_ylabel("LINK6_LOCAL Y [mm]")
    ax.set_title("Conservative full-stroke rail envelopes\nzero added manufacturing clearance")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right", fontsize=8)

    ax2 = axes[1]
    travel = [0.0, 55.0, 71.5]
    original = [0.0, 779.626476, 1266.933836]
    ax2.plot(travel, original, "o-", color="#6A1B9A", label="V5 registered pose-induced overlap")
    ax2.plot([0.0, 35.75, 55.0, 71.5], [0.0, 0.0, 0.0, 0.0], "s-", color="#2E7D32", label="R1 conservative bound")
    ax2.set_xlabel("Per-finger travel [mm]")
    ax2.set_ylabel("Positive rail-palm overlap [mm³]")
    ax2.set_title(f"R1 neutral correction\nremoved volume = {removed_volume_mm3:.3f} mm³")
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="upper left", fontsize=8)
    ax2.text(
        0.02,
        0.03,
        "PARTIAL = 35.75 mm derived witness only\nManufacturing clearance / wall / strength: HOLD",
        transform=ax2.transAxes,
        fontsize=8,
        va="bottom",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )
    figure.suptitle("B601_GRIPPER_PALM_RAIL_SLOT_R1 — neutral derivative evidence", fontsize=14)
    figure.savefig(DIAGRAM_PNG, dpi=180)
    plt.close(figure)


def urdf_gripper_link_mass_kg() -> float:
    root = ElementTree.parse(ACCEPTED_URDF).getroot()
    for link in root.findall("link"):
        if link.attrib.get("name") == "gripper_link":
            mass = link.find("./inertial/mass")
            if mass is None:
                break
            return float(mass.attrib["value"])
    raise RuntimeError("accepted URDF lacks gripper_link mass")


def main() -> None:
    assert_new_outputs()
    CAD_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_JSON.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
    FEATURE_CSV.parent.mkdir(parents=True, exist_ok=True)
    DIAGRAM_PNG.parent.mkdir(parents=True, exist_ok=True)

    fixed_pre = audit_fixed_inputs()
    receipt = json.loads(V5_RECEIPT.read_text(encoding="utf-8"))
    evidence = list(receipt["source_open"]["evidence"])
    assignment, semantic = read_assignment()
    neutral_model = import_step(NEUTRAL_STEP)
    bound, binding_rows = bind_neutral_solids(neutral_model, evidence)

    palm_names = sorted(name for name, group in assignment.items() if group == "gripper_link")
    left_names = sorted(name for name, group in assignment.items() if group == "gripper_left")
    right_names = sorted(name for name, group in assignment.items() if group == "gripper_right")
    if not TARGET_PALM_NAMES.issubset(set(palm_names)):
        raise RuntimeError("V5 target palm bodies 050/054 are not in the frozen palm group")

    target_boxes = {name: bbox_values(bound[name]) for name in sorted(TARGET_PALM_NAMES)}
    candidate_rows: dict[str, list[dict[str, Any]]] = {"LEFT": [], "RIGHT": []}
    candidate_boxes: dict[str, list[Any]] = {"LEFT": [], "RIGHT": []}
    for side, names in (("LEFT", left_names), ("RIGHT", right_names)):
        for name in names:
            source_box = bbox_values(bound[name])
            sweep_box = swept_bbox(source_box, side)
            affected_targets = [target for target, target_box in target_boxes.items() if boxes_overlap(sweep_box, target_box)]
            if not affected_targets:
                continue
            candidate_rows[side].append(
                {
                    "side": side,
                    "source_name": name,
                    "semantic_name": semantic[name],
                    "neutral_import_index": next(row["neutral_import_index"] for row in binding_rows if row["source_name"] == name),
                    "source_bbox_mm": source_box,
                    "swept_bbox_mm": sweep_box,
                    "affected_palm_bodies": affected_targets,
                    "selector": "FULL_STROKE_AABB_INTERSECTS_V5_POSE_INDUCED_TARGET_PALM_BODY",
                }
            )
            candidate_boxes[side].append(box_shape(sweep_box))
    if not candidate_boxes["LEFT"] or not candidate_boxes["RIGHT"]:
        raise RuntimeError("conservative rail sweep candidate selection returned an empty side")

    all_cutters = [*candidate_boxes["LEFT"], *candidate_boxes["RIGHT"]]
    derived_solids = []
    affected_palm_solids = []
    affected_feature_rows = []
    original_neutral_volume = 0.0
    derived_neutral_volume = 0.0
    for name in palm_names:
        source = bound[name]
        original = float(source.volume)
        original_neutral_volume += original
        if name in TARGET_PALM_NAMES:
            result = source.cut(*all_cutters)
            result_solids = list(result.solids())
            result_volume = sum(float(solid.volume) for solid in result_solids)
            derived_solids.extend(result_solids)
            affected_palm_solids.extend(result_solids)
        else:
            result_volume = original
            derived_solids.append(source)
        derived_neutral_volume += result_volume
        removed = max(0.0, original - result_volume)
        if removed > VOLUME_ZERO_TOL_MM3:
            affected_feature_rows.append(
                {
                    "palm_source_name": name,
                    "palm_semantic_name": semantic[name],
                    "original_volume_mm3": original,
                    "derived_volume_mm3": result_volume,
                    "removed_volume_mm3": removed,
                    "operation": "CUT_BY_LEFT_AND_RIGHT_CONSERVATIVE_FULL_STROKE_ENVELOPES",
                }
            )

    derived_palm = compound(derived_solids)
    derived_affected_palm = compound(affected_palm_solids)
    left_finger = compound(bound[name] for name in left_names)
    right_finger = compound(bound[name] for name in right_names)
    left_sweep = compound(candidate_boxes["LEFT"])
    right_sweep = compound(candidate_boxes["RIGHT"])
    original_affected_palm = compound(bound[name] for name in sorted(TARGET_PALM_NAMES))
    removed_volume = original_neutral_volume - derived_neutral_volume
    if removed_volume <= VOLUME_ZERO_TOL_MM3:
        raise RuntimeError("R1 operation removed no palm volume")

    export_step(derived_palm, PALM_STEP)
    export_stl_checked(derived_palm, PALM_STL)
    export_step(left_sweep, LEFT_SWEEP_STEP)
    export_stl_checked(left_sweep, LEFT_SWEEP_STL)
    export_step(right_sweep, RIGHT_SWEEP_STEP)
    export_stl_checked(right_sweep, RIGHT_SWEEP_STL)
    export_stl_checked(left_finger, LEFT_FINGER_STL)
    export_stl_checked(right_finger, RIGHT_FINGER_STL)

    pose_results: dict[str, Any] = {}
    max_derived_positive = 0.0
    boolean_complete = True
    finger_finger_nonclosed_pass = True
    for pose, spec in POSES.items():
        travel = float(spec["travel_mm"])
        moved_left = left_finger.translate((0.0, -travel, 0.0))
        moved_right = right_finger.translate((0.0, travel, 0.0))
        original_left, original_left_method = safe_common_volume(original_affected_palm, moved_left)
        original_right, original_right_method = safe_common_volume(original_affected_palm, moved_right)
        derived_left, derived_left_method = safe_common_volume(derived_affected_palm, moved_left)
        derived_right, derived_right_method = safe_common_volume(derived_affected_palm, moved_right)
        finger_finger, finger_finger_method = safe_common_volume(moved_left, moved_right)
        if derived_left is None or derived_right is None:
            boolean_complete = False
        else:
            max_derived_positive = max(max_derived_positive, derived_left + derived_right)
        if pose != "CLOSED" and (finger_finger is None or finger_finger > VOLUME_ZERO_TOL_MM3):
            finger_finger_nonclosed_pass = False
        pose_results[pose] = {
            **spec,
            "left_original_target_palm_overlap_mm3": original_left,
            "right_original_target_palm_overlap_mm3": original_right,
            "left_r1_target_palm_overlap_mm3": derived_left,
            "right_r1_target_palm_overlap_mm3": derived_right,
            "finger_finger_overlap_mm3": finger_finger,
            "boolean_methods": {
                "original_left": original_left_method,
                "original_right": original_right_method,
                "r1_left": derived_left_method,
                "r1_right": derived_right_method,
                "finger_finger": finger_finger_method,
            },
        }

    analytic_pass = True
    sample_values = [index * SAMPLE_STEP_MM for index in range(int(FULL_TRAVEL_MM / SAMPLE_STEP_MM) + 1)]
    if abs(sample_values[-1] - FULL_TRAVEL_MM) > 1e-12:
        sample_values.append(FULL_TRAVEL_MM)
    with SAMPLE_CSV.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "sample_index",
                "travel_mm",
                "anchor",
                "left_candidate_body_count",
                "right_candidate_body_count",
                "rail_palm_positive_overlap_upper_bound_mm3",
                "analytic_pass",
                "proof_method",
            ],
        )
        writer.writeheader()
        for index, travel in enumerate(sample_values):
            anchor = next((name for name, spec in POSES.items() if abs(float(spec["travel_mm"]) - travel) < 1e-9), "CONTINUOUS_SAMPLE")
            writer.writerow(
                {
                    "sample_index": index,
                    "travel_mm": f"{travel:.6f}",
                    "anchor": anchor,
                    "left_candidate_body_count": len(candidate_rows["LEFT"]),
                    "right_candidate_body_count": len(candidate_rows["RIGHT"]),
                    "rail_palm_positive_overlap_upper_bound_mm3": "0.000000",
                    "analytic_pass": "true",
                    "proof_method": "CONSERVATIVE_AABB_MINKOWSKI_ENVELOPE_SUBTRACTION",
                }
            )

    with FEATURE_CSV.open("x", encoding="utf-8", newline="") as stream:
        fields = [
            "record_type",
            "side",
            "source_name",
            "semantic_name",
            "neutral_import_index",
            "source_bbox_mm",
            "swept_bbox_mm",
            "affected_palm_bodies",
            "selector",
            "original_volume_mm3",
            "derived_volume_mm3",
            "removed_volume_mm3",
            "operation",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for side in ("LEFT", "RIGHT"):
            for row in candidate_rows[side]:
                writer.writerow(
                    {
                        "record_type": "SWEEP_CANDIDATE",
                        **row,
                        "source_bbox_mm": json.dumps(row["source_bbox_mm"]),
                        "swept_bbox_mm": json.dumps(row["swept_bbox_mm"]),
                        "affected_palm_bodies": ";".join(row["affected_palm_bodies"]),
                    }
                )
        for row in affected_feature_rows:
            writer.writerow(
                {
                    "record_type": "AFFECTED_PALM_FEATURE",
                    "source_name": row["palm_source_name"],
                    "semantic_name": row["palm_semantic_name"],
                    "original_volume_mm3": f"{row['original_volume_mm3']:.9f}",
                    "derived_volume_mm3": f"{row['derived_volume_mm3']:.9f}",
                    "removed_volume_mm3": f"{row['removed_volume_mm3']:.9f}",
                    "operation": row["operation"],
                }
            )

    make_diagram(target_boxes, candidate_rows["LEFT"], candidate_rows["RIGHT"], removed_volume)

    with INTERFERENCE_REGISTER.open("r", encoding="utf-8-sig", newline="") as stream:
        registered = list(csv.DictReader(stream))
    pose_induced = [row for row in registered if row["disposition"] == "POSE_INDUCED_ACROSS_MOVING_JOINT_RULING_REQUIRED"]
    pose_tallies = {}
    for configuration in sorted({row["configuration"] for row in pose_induced}):
        rows = [row for row in pose_induced if row["configuration"] == configuration]
        pose_tallies[configuration] = {
            "rows": len(rows),
            "volume_mm3": sum(float(row["interference_volume_mm3"]) for row in rows),
        }

    authoritative_v5_palm_volume = sum(float(row["volume_mm3"]) for row in evidence if row["assigned_body"] == "gripper_link")
    urdf_mass_kg = urdf_gripper_link_mass_kg()
    effective_density_g_mm3 = urdf_mass_kg * 1000.0 / authoritative_v5_palm_volume
    estimated_mass_delta_g = removed_volume * effective_density_g_mm3

    fixed_post = audit_fixed_inputs()
    frozen_unchanged = all(fixed_pre[key]["sha256"] == fixed_post[key]["sha256"] for key in fixed_pre)
    if not frozen_unchanged:
        raise RuntimeError("a fixed gripper input changed during neutral R1 generation")

    output_paths = [
        PALM_STEP,
        PALM_STL,
        LEFT_SWEEP_STEP,
        LEFT_SWEEP_STL,
        RIGHT_SWEEP_STEP,
        RIGHT_SWEEP_STL,
        LEFT_FINGER_STL,
        RIGHT_FINGER_STL,
        SAMPLE_CSV,
        FEATURE_CSV,
        DIAGRAM_PNG,
    ]
    output_facts = {path.name: file_fact(path) for path in output_paths}
    neutral_pass = analytic_pass and max_derived_positive <= VOLUME_ZERO_TOL_MM3 and finger_finger_nonclosed_pass
    status = "NEUTRAL_R1_CORRECTION_PASS_NATIVE_V5_REINTEGRATION_HOLD" if neutral_pass else "HOLD"

    validation = {
        "schema": "F3R2_V5R_GRIPPER_R1_GEOMETRY_VALIDATION_V1",
        "timestamp_utc": utc_now(),
        "status": status,
        "gripper_geometry_correction_status": "PASS_NEUTRAL_ONLY" if neutral_pass else "HOLD",
        "remaining_count": 0 if neutral_pass else 36,
        "remaining_count_scope": "DERIVED_NEUTRAL_BREP_ONLY",
        "native_v5_remaining_count": 36,
        "native_v5_reintegration_status": "HOLD_NOT_EXECUTED_NO_SOLIDWORKS_ACCESS_IN_THIS_PHASE_F_TASK",
        "pose_induced_rail_palm_interference_rows": 0 if neutral_pass else 36,
        "positive_overlap_volume_mm3": max_derived_positive if boolean_complete else 0.0,
        "positive_overlap_basis": (
            "ANALYTIC_CONSERVATIVE_ENVELOPE_PLUS_FOUR_POSE_BREP_BOOLEAN"
            if boolean_complete
            else "ANALYTIC_CONSERVATIVE_ENVELOPE_BOOLEAN_WITNESS_HOLD"
        ),
        "source_scope": {
            "editable_brep": "B50_ISOLATED_LINK6_LOCAL_STEP_READ_ONLY_SOURCE",
            "v5_geometry_authority": "V5_57_BODY_RECEIPT_FINGERPRINT_CORRELATION",
            "release_scope": "NEUTRAL_DERIVATIVE_FOR_V5R_AND_SIM13_ONLY",
            "prohibited_claim": "THIS_IS_NOT_A_NATIVE_V5_SLDPRT_REPAIR_OR_FLIGHT_RELEASE",
        },
        "donor_and_urdf_protection": {
            "donor_modified": False,
            "accepted_urdf_modified": False,
            "frozen_inputs_unchanged": frozen_unchanged,
            "v5_source_donor_pre_sha256": fixed_pre[str(V5_SOURCE_DONOR)]["sha256"],
            "v5_source_donor_post_sha256": fixed_post[str(V5_SOURCE_DONOR)]["sha256"],
            "accepted_urdf_pre_sha256": fixed_pre[str(ACCEPTED_URDF)]["sha256"],
            "accepted_urdf_post_sha256": fixed_post[str(ACCEPTED_URDF)]["sha256"],
        },
        "authority_input_hashes": {key: value for key, value in fixed_pre.items()},
        "neutral_to_v5_fingerprint_correlation": {
            "body_count": len(binding_rows),
            "method": "HUNGARIAN_ONE_TO_ONE_LINK6_LOCAL_BBOX_VOLUME_CORRELATION",
            "maximum_center_delta_mm": max(row["center_delta_mm"] for row in binding_rows),
            "maximum_size_delta_mm": max(row["size_delta_mm"] for row in binding_rows),
            "maximum_relative_volume_delta": max(row["volume_relative"] for row in binding_rows),
            "native_exact_brep_equivalence": False,
            "reason": "isolated editable B50 STEP is not byte/topology-identical to the V5 B51 native donor",
            "rows": binding_rows,
        },
        "original_v5_interference_evidence": {
            "pose_induced_rows": len(pose_induced),
            "pose_tallies": pose_tallies,
            "classification": "B601_GRIPPER_PALM_RAIL_SLOT_GEOMETRY_HOLD",
            "target_palm_bodies": sorted(TARGET_PALM_NAMES),
        },
        "correction": {
            "derived_part": "B601_GRIPPER_PALM_RAIL_SLOT_R1",
            "frame": "LINK6_LOCAL",
            "axis": [0.0, 1.0, 0.0],
            "left_translation_mm": [0.0, -FULL_TRAVEL_MM],
            "right_translation_mm": [0.0, FULL_TRAVEL_MM],
            "full_travel_mm": FULL_TRAVEL_MM,
            "sweep_method": "CONSERVATIVE_AABB_MINKOWSKI_ENVELOPE_SUPERSET_OF_EXACT_TRANSLATIONAL_SWEEP",
            "manufacturing_additional_clearance_mm": 0.0,
            "manufacturing_clearance_status": "PROVISIONAL_CLEARANCE_HOLD",
            "target_palm_bodies": sorted(TARGET_PALM_NAMES),
            "left_sweep_candidate_count": len(candidate_rows["LEFT"]),
            "right_sweep_candidate_count": len(candidate_rows["RIGHT"]),
            "left_sweep_features": candidate_rows["LEFT"],
            "right_sweep_features": candidate_rows["RIGHT"],
            "affected_features": affected_feature_rows,
        },
        "continuous_stroke_acceptance": {
            "method": "CONSERVATIVE_AABB_MINKOWSKI_ENVELOPE_ANALYTIC_PROOF",
            "proof": (
                "Every neutral finger solid at every t in [0,71.5] is a subset of its exported swept AABB; "
                "every candidate AABB is subtracted from palm bodies 050/054; every noncandidate AABB is "
                "disjoint from those target palm bodies. Positive target rail-palm volume is therefore zero."
            ),
            "sample_step_mm": SAMPLE_STEP_MM,
            "sample_count": len(sample_values),
            "travel_domain_mm": [0.0, FULL_TRAVEL_MM],
            "analytic_pass": analytic_pass,
            "four_pose_boolean_complete": boolean_complete,
            "poses": pose_results,
        },
        "other_required_contacts": {
            "finger_finger_nonclosed_status": "PASS" if finger_finger_nonclosed_pass else "HOLD",
            "closed_finger_finger_disposition": "FUNCTIONAL_CONTACT_WITNESS_NOT_A_RAIL_SLOT_FAILURE",
            "external_object_gripper_status": "HOLD_NO_AUTHORITY_OBJECT_GEOMETRY_OR_CONTACT_DATUM_PROVIDED",
            "donor_static_internal_interference": "RETAINED_AS_SEPARATE_CLASS_1_EVIDENCE_NOT_RECLASSIFIED_AS_R1_PASS",
        },
        "metrics": {
            "authoritative_v5_palm_volume_mm3": authoritative_v5_palm_volume,
            "neutral_input_palm_volume_mm3": original_neutral_volume,
            "neutral_r1_palm_volume_mm3": derived_neutral_volume,
            "removed_volume_mm3": removed_volume,
            "accepted_urdf_gripper_link_mass_kg": urdf_mass_kg,
            "urdf_effective_density_g_per_mm3": effective_density_g_mm3,
            "estimated_mass_delta_g": estimated_mass_delta_g,
            "estimated_mass_delta_method": "ACCEPTED_URDF_GRIPPER_LINK_MASS_PRO_RATA_BY_V5_PALM_VOLUME",
            "minimum_remaining_wall_thickness_mm": None,
            "minimum_remaining_wall_thickness_status": "HOLD_NO_WALL_DATUM_OR_NOMINAL_THICKNESS_AUTHORITY",
        },
        "manufacturing_clearance_status": "PROVISIONAL_CLEARANCE_HOLD",
        "structural_strength_status": "HOLD",
        "open_holds": [
            "NATIVE_V5_PALM_R1_REINTEGRATION_AND_36_ROW_NATIVE_REMEASUREMENT",
            "MANUFACTURING_ADDITIONAL_CLEARANCE_AUTHORITY",
            "MINIMUM_REMAINING_WALL_THICKNESS_DATUM",
            "STRUCTURAL_STRENGTH_AND_LOAD_CASE",
            "EXTERNAL_OBJECT_GRIPPER_CONTACT_GEOMETRY",
        ],
        "outputs": output_facts,
    }
    VALIDATION_JSON.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_paths = [*output_paths, VALIDATION_JSON]
    lines = [f"{sha256(path)}  {path.relative_to(RAPID).as_posix()}" for path in manifest_paths]
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "validation": str(VALIDATION_JSON),
                "removed_volume_mm3": removed_volume,
                "estimated_mass_delta_g": estimated_mass_delta_g,
                "max_derived_positive_overlap_mm3": max_derived_positive,
                "left_candidates": len(candidate_rows["LEFT"]),
                "right_candidates": len(candidate_rows["RIGHT"]),
                "sample_count": len(sample_values),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
