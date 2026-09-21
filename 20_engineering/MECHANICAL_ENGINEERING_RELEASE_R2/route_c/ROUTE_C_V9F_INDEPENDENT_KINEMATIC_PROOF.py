"""Independent analytic proof for the single ODR-58 Route-C V9F fallback.

This program intentionally has no CAD/evaluator imports.  It reconstructs the
accepted URDF forward kinematics, the four-stage trombone law, and the external
annular follower from first principles.  It is an independent cross-check, not
a release or qualification gate.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORKSPACE = REPO.parent
BINDING = HERE / "ROUTE_C_V9F_FALLBACK_AUTHORITY_BINDING.json"
URDF = REPO / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
MISSION = (REPO / "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
           / "ecr_b601_harness_rated_envelope/04_mission"
           / "B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml")
OUT = HERE / "ROUTE_C_V9F_INDEPENDENT_KINEMATIC_PROOF.json"

BINDING_SHA256 = "6C49A1604F15FD7E338F6019EBB34E39341683DDC4611B5237B53ECC990F7F7D"
URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
EXPECTED_ARCHITECTURE = ("CHAINLESS_TELESCOPING_TROMBONE_CASSETTE__R55_"
                         "EXTERNAL_ANNULAR_FOLLOWER__LINK4_MOVING_TROLLEY")
EXPECTED_SEGMENT_ID = "SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"
Q4_MIN = -1.87
Q4_MAX = 1.57
Q4_MID = -0.15
XC_MID = -205.0
GAIN = 27.5
XF = -100.0
R_U = math.hypot(23.0, 50.0)
R_ANN = 55.0
BETA_OFFSET = math.radians(20.0)
ANN_GUIDE_SWEEP_DEG = 185.0
STAGE_COUNT = 4
STAGE_LENGTH = 57.0
MIN_STAGE_OVERLAP = 25.0
STOP_MIN = -255.0
STOP_MAX = -155.0
LENGTH_TOL_MM = 1.0e-6
FOLLOWER_TOL_MM = 1.0e-6
TANGENT_TOL_DEG = 1.0e-6


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def fail_closed(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL_CLOSED_AUTHORITY_BINDING: {message}")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(
            f"FAIL_CLOSED_AUTHORITY_BINDING: cannot read JSON {path}: {exc}"
        ) from exc
    fail_closed(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def workspace_path(relative_path: str) -> Path:
    fail_closed(isinstance(relative_path, str) and relative_path,
                "empty or non-string binding path")
    candidate = (WORKSPACE / Path(relative_path)).resolve()
    root = WORKSPACE.resolve()
    fail_closed(candidate == root or root in candidate.parents,
                f"binding path escapes workspace: {relative_path}")
    fail_closed(candidate.is_file(), f"bound file missing: {relative_path}")
    return candidate


def iter_byte_pins(node: object, label: str = "binding"):
    if isinstance(node, dict):
        if set(("path", "sha256")).issubset(node):
            yield label, node
            return
        for key, value in node.items():
            yield from iter_byte_pins(value, f"{label}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_byte_pins(value, f"{label}[{index}]")


def verify_byte_pins(binding: dict) -> tuple[dict[str, Path], list[dict]]:
    resolved: dict[str, Path] = {}
    audit: list[dict] = []
    seen_paths: dict[str, str] = {}
    for label, pin in iter_byte_pins(binding):
        expected = pin.get("sha256")
        fail_closed(isinstance(expected, str) and len(expected) == 64,
                    f"invalid SHA-256 at {label}")
        path = workspace_path(pin.get("path"))
        actual = sha256(path)
        fail_closed(actual == expected.upper(),
                    f"SHA-256 mismatch at {label}: {pin.get('path')}")
        normalized = path.relative_to(WORKSPACE).as_posix()
        if normalized in seen_paths:
            fail_closed(seen_paths[normalized] == expected.upper(),
                        f"conflicting duplicate pins for {normalized}")
        else:
            seen_paths[normalized] = expected.upper()
        resolved[label] = path
        audit.append({
            "binding_key": label,
            "path": normalized,
            "sha256": actual,
            "match": True,
        })
    fail_closed(len(audit) > 0, "binding contains no byte pins")
    return resolved, audit


def exact(actual: object, expected: object, label: str) -> None:
    fail_closed(actual == expected,
                f"{label}: expected {expected!r}, got {actual!r}")


def finite_close(actual: object, expected: object, label: str,
                 tolerance: float = 1.0e-12) -> None:
    try:
        a = float(actual)
        e = float(expected)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"FAIL_CLOSED_AUTHORITY_BINDING: {label} is non-numeric"
        ) from exc
    fail_closed(math.isfinite(a) and math.isfinite(e), f"{label} is non-finite")
    fail_closed(math.isclose(a, e, rel_tol=0.0, abs_tol=tolerance),
                f"{label}: expected {e!r}, got {a!r}")


def literal_assignments(path: Path) -> tuple[str, dict[str, object]]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        raise SystemExit(
            f"FAIL_CLOSED_AUTHORITY_BINDING: cannot parse bound builder: {exc}"
        ) from exc
    values: dict[str, object] = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
    return source, values


def vec(text: str) -> np.ndarray:
    return np.array([float(x) for x in text.split()], dtype=float)


def rot_axis(axis: np.ndarray, angle: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    c, s, C = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    return np.array([
        [x*x*C+c, x*y*C-z*s, x*z*C+y*s],
        [y*x*C+z*s, y*y*C+c, y*z*C-x*s],
        [z*x*C-y*s, z*y*C+x*s, z*z*C+c],
    ])


def rot_rpy(rpy: np.ndarray) -> np.ndarray:
    r, p, y = rpy
    return (rot_axis(np.array([0.0, 0.0, 1.0]), y)
            @ rot_axis(np.array([0.0, 1.0, 0.0]), p)
            @ rot_axis(np.array([1.0, 0.0, 0.0]), r))


def homogeneous(R: np.ndarray | None = None,
                p: np.ndarray | None = None) -> np.ndarray:
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    if p is not None:
        T[:3, 3] = p
    return T


class Arm:
    def __init__(self, urdf: Path):
        root = ET.parse(urdf).getroot()
        joints = {}
        for node in root.findall("joint"):
            if node.attrib.get("type") == "fixed" and node.find("child").attrib["link"] not in {
                    "gripper_link", "gripper_left", "gripper_right"}:
                continue
            origin = node.find("origin")
            xyz = vec(origin.attrib.get("xyz", "0 0 0")) * 1000.0
            rpy = vec(origin.attrib.get("rpy", "0 0 0"))
            axis_node = node.find("axis")
            axis = vec(axis_node.attrib["xyz"]) if axis_node is not None else np.array([0., 0., 1.])
            joints[node.attrib["name"]] = {
                "parent": node.find("parent").attrib["link"],
                "child": node.find("child").attrib["link"],
                "origin": homogeneous(rot_rpy(rpy), xyz),
                "axis": axis,
                "type": node.attrib.get("type"),
            }
        self.joints = [joints[f"joint{i}"] for i in range(1, 7)]

    def fk(self, q: list[float]) -> dict[str, np.ndarray]:
        frames = {"base_link": np.eye(4)}
        for joint, angle in zip(self.joints, q):
            motion = homogeneous(rot_axis(joint["axis"], angle))
            frames[joint["child"]] = frames[joint["parent"]] @ joint["origin"] @ motion
        return frames


def x_center(q4: float) -> float:
    return XC_MID - GAIN * (q4 - Q4_MID)


def beta(q4: float) -> float:
    return BETA_OFFSET + Q4_MAX - q4


def transform_point(T: np.ndarray, p: np.ndarray) -> np.ndarray:
    return (T @ np.r_[p, 1.0])[:3]


def validate_authority_binding() -> tuple[dict, list[dict], dict, dict]:
    fail_closed(sha256(BINDING) == BINDING_SHA256,
                "fallback authority binding record hash mismatch")
    binding = load_json(BINDING)
    exact(binding.get("schema"), "ROUTE_C_V9F_FALLBACK_AUTHORITY_BINDING_V1",
          "binding schema")
    exact(binding.get("authority"),
          "CANDIDATE_ONLY__SINGLE_FALLBACK_BUDGET_CONSUMED__NO_GATE_PASS__NO_RELEASE_CREDIT",
          "binding authority")
    exact(binding.get("manufacturing_use"), "PROHIBITED",
          "binding manufacturing use")
    exact(binding.get("review_status"), "PENDING_OWNER_REVIEW",
          "binding review status")
    exact(binding.get("next_stage_authorized"), False,
          "binding next-stage authority")
    exact(binding.get("release_credit"), False, "binding release credit")

    _, byte_audit = verify_byte_pins(binding)
    authority = binding["owner_authority"]
    exact(authority.get("decision_id"), "ODR-58", "binding decision id")
    exact(authority.get("source_attachment_sha256"),
          "CFE1D03A28AA98BA5CE36EA194ED7F1198526E9138206C2D37D08D387B61BA9F",
          "ODR-58 source attachment")

    odr = load_json(workspace_path(authority["record"]["path"]))
    exact(odr.get("schema"), "OWNER_DECISION_RECORD", "ODR-58 schema")
    exact(odr.get("decision_id"), "ODR-58", "ODR-58 decision id")
    exact(odr.get("decision"), "AUTHORIZE_ONE_BOUNDED_V9_ARCHITECTURE_CLOSURE",
          "ODR-58 decision")
    exact(odr.get("source_attachment_sha256"), authority["source_attachment_sha256"],
          "ODR-58 attachment binding")
    exact(odr.get("iteration_budget"), {
        "primary_architecture_candidates": 1,
        "same_architecture_bounded_geometric_repairs": 1,
        "technically_distinct_fallback_if_primary_topology_invalid": 1,
        "unlimited_loops": False,
    }, "ODR-58 iteration budget")
    exact(odr.get("next_stage_authorized"), False, "ODR-58 next-stage authority")
    exact(odr.get("release_credit"), False, "ODR-58 release credit")

    manifest_pin = binding["v9_frozen_inputs"]["input_manifest"]
    brief_pin = binding["v9_frozen_inputs"]["cad_brief"]
    manifest = load_json(workspace_path(manifest_pin["path"]))
    exact(manifest.get("schema"), "ROUTE_C_V9_INPUT_MANIFEST_V1",
          "V9 input manifest schema")
    exact(manifest["owner_authority"].get("decision_id"), "ODR-58",
          "V9 input manifest owner")
    exact(manifest["owner_authority"].get("record_sha256"),
          authority["record"]["sha256"], "V9 input manifest ODR-58 hash")
    exact(manifest["owner_authority"].get("source_attachment_sha256"),
          authority["source_attachment_sha256"],
          "V9 input manifest source attachment")
    exact(manifest["cad_brief"].get("sha256"), brief_pin["sha256"],
          "V9 CAD brief hash")
    exact(manifest.get("hash_mismatch"), 0, "V9 input manifest hash mismatch count")
    exact(manifest.get("next_stage_authorized"), False,
          "V9 input manifest next-stage authority")
    exact(manifest.get("release_credit"), False,
          "V9 input manifest release credit")

    lineage = binding["primary_negative_lineage"]
    exact(lineage.get("primary_architecture"),
          "SEGMENTED_CONSTRAINED_MOVING_CARRIER__LOW_PROFILE_DUAL_PLANE_SADDLE",
          "primary negative architecture")
    repair = lineage["same_architecture_bounded_repair"]
    rejection = load_json(workspace_path(repair["record"]["path"]))
    exact(rejection.get("schema"), "ROUTE_C_V9_PRIMARY_REJECTION_RECORD_V1",
          "primary early-rejection schema")
    exact(rejection.get("architecture"), lineage["primary_architecture"],
          "primary early-rejection architecture")
    exact(rejection.get("verdict"), "EARLY_REJECTED_BEND_RADIUS",
          "primary early-rejection verdict")
    exact(rejection["repair_authorized"].get("class"),
          "ONE_BOUNDED_GEOMETRIC_REPAIR_OF_SAME_ARCHITECTURE",
          "primary bounded repair class")
    exact(rejection.get("next_stage_authorized"), False,
          "primary early-rejection next-stage authority")
    exact(rejection.get("release_credit"), False,
          "primary early-rejection release credit")
    rejection_prefix = (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/"
        "_work/v9_primary_pre_bounded_repair/"
    )
    rejection_bound_artifacts = {
        pin["path"].removeprefix(rejection_prefix): pin["sha256"]
        for pin in repair.get("archived_artifacts", [])
    }
    exact(rejection_bound_artifacts,
          {item["path"]: item["sha256"]
           for item in rejection.get("archived_artifacts", [])},
          "primary early-rejection archived lineage")

    falsification = lineage["terminal_topology_falsification"]
    falsifier = load_json(workspace_path(falsification["record"]["path"]))
    exact(falsifier.get("schema"), "ROUTE_C_V9_PRIMARY_TOPOLOGY_FALSIFIER_V1",
          "primary topology falsifier schema")
    exact(falsifier.get("candidate"), lineage["primary_architecture"],
          "primary topology falsifier candidate")
    exact(falsifier.get("decision"), falsification["decision"],
          "primary topology falsifier decision")
    exact(falsifier.get("bounded_repair_status"),
          "CONSUMED_BY_EARLY_R54_BEND_RADIUS_REPAIR",
          "primary bounded repair consumption")
    falsifier_checks = falsifier.get("independent_checks", {})
    fail_closed(bool(falsifier_checks)
                and all(check.get("pass") is False
                        for check in falsifier_checks.values()),
                "primary topology falsifier does not retain all negative checks")
    exact(falsifier.get("next_stage_authorized"), False,
          "primary topology falsifier next-stage authority")
    exact(falsifier.get("release_credit"), False,
          "primary topology falsifier release credit")
    topology_prefix = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/"
    topology_bound_artifacts = {
        pin["path"].removeprefix(topology_prefix): pin["sha256"]
        for pin in falsification.get("archived_artifacts", [])
    }
    exact(topology_bound_artifacts, falsifier.get("archived_artifact_hashes"),
          "primary topology-invalid archived lineage")

    budget = binding["iteration_budget_accounting"]
    expected_budget = {
        "primary_architecture_candidates_authorized": 1,
        "primary_architecture_candidates_consumed": 1,
        "same_architecture_bounded_geometric_repairs_authorized": 1,
        "same_architecture_bounded_geometric_repairs_consumed": 1,
        "technically_distinct_fallbacks_authorized": 1,
        "technically_distinct_fallbacks_consumed": 1,
        "technically_distinct_fallbacks_remaining": 0,
        "additional_geometry_iteration_authorized": False,
        "fallback_budget_status": "CONSUMED_BY_V9F_CANDIDATE",
    }
    exact(budget, expected_budget, "V9/V9F iteration budget accounting")

    candidate = binding["v9f_candidate"]
    contract = candidate["key_parameter_contract"]
    exact(candidate.get("architecture"), EXPECTED_ARCHITECTURE,
          "V9F binding architecture")
    exact(candidate.get("segment_id"), EXPECTED_SEGMENT_ID,
          "V9F binding segment id")

    pins = candidate["byte_pins"]
    builder_source, builder_literals = literal_assignments(
        workspace_path(pins["builder"]["path"]))
    fail_closed(EXPECTED_ARCHITECTURE in builder_source,
                "V9F builder does not emit the bound architecture")
    fail_closed(EXPECTED_SEGMENT_ID in builder_source,
                "V9F builder does not emit the bound J4 segment")
    fail_closed("HOLD_UNKNOWN_TORSION" in builder_source,
                "V9F builder does not retain the installed-bundle torsion hold")
    exact(builder_literals.get("INPUT_MANIFEST_SHA256"), manifest_pin["sha256"],
          "V9F builder manifest hash")
    builder_p = builder_literals.get("P")
    fail_closed(isinstance(builder_p, dict), "V9F builder P table is not literal")
    finite_close(builder_p.get("j4_trombone_hard_stop_travel_mm"),
                 contract["physical_travel_mm"], "V9F builder physical travel")
    finite_close(builder_p.get("j4_trombone_center_x_mid_mm"),
                 contract["center_x_mid_mm"], "V9F builder center-x midpoint")
    finite_close(builder_p.get("j4_trombone_gain_mm_per_rad"),
                 contract["center_x_gain_mm_per_rad"], "V9F builder center-x gain")
    finite_close(builder_p.get("j4_q_mid_rad"), contract["q4_center_reference_rad"],
                 "V9F builder q4 center reference")
    finite_close(builder_p.get("j4_telescope_stage_length_mm"),
                 contract["stage_length_mm"], "V9F builder stage length")
    exact(builder_p.get("j4_telescope_stage_count"), contract["stage_count_per_leg"],
          "V9F builder stage count")
    finite_close(builder_p.get("j4_telescope_min_overlap_mm"),
                 contract["minimum_overlap_requirement_mm"],
                 "V9F builder minimum overlap")
    for name, contract_key in (
            ("J4_AXIS_EXTERNAL", "annular_axis_origin_A0_mm"),
            ("J4_AXIS_DIR", "annular_axis_direction_A0"),
            ("J4_ANNULUS_E1", "annular_basis_e1_A0")):
        exact(list(builder_literals.get(name, ())), contract[contract_key],
              f"V9F builder {name}")
    finite_close(builder_literals.get("J4_ANNULUS_R"),
                 contract["annular_follower_radius_mm"],
                 "V9F builder annular radius")
    finite_close(builder_literals.get("J4_ANNULUS_FIXED_ANGLE_DEG"),
                 contract["annulus_fixed_entry_angle_deg"],
                 "V9F builder annular fixed angle")
    finite_close(builder_literals.get("J4_QMAX_RAD"),
                 contract["q4_full_hardware_limits_rad"][1],
                 "V9F builder q4 maximum")
    finite_close(builder_literals.get("J4_QMIN_FULL_RAD"),
                 contract["q4_full_hardware_limits_rad"][0],
                 "V9F builder q4 minimum")
    finite_close(builder_literals.get("J4_ANNULUS_GUIDE_SWEEP_DEG"),
                 contract["physical_annular_guide_sweep_deg"],
                 "V9F builder annular guide sweep")
    exact(builder_literals.get("J4_STAGE_MOTION"), contract["stage_motion_classes"],
          "V9F builder stage motion classes")

    receipt = load_json(workspace_path(pins["build_receipt"]["path"]))
    centerline = load_json(workspace_path(pins["centerline"]["path"]))
    mass_geometry = load_json(workspace_path(pins["parts_mass_geometry"]["path"]))

    exact(receipt.get("schema"), "B601_ROUTE_C_BUILD_RECEIPT_V9F",
          "V9F build receipt schema")
    exact(receipt.get("architecture"), EXPECTED_ARCHITECTURE,
          "V9F build receipt architecture")
    exact(receipt.get("design_candidate_sequence"),
          contract["design_candidate_sequence"], "V9F receipt candidate sequence")
    exact(receipt["input_manifest"].get("sha256"), manifest_pin["sha256"],
          "V9F receipt manifest hash")
    exact(receipt["input_manifest"].get("expected_sha256"), manifest_pin["sha256"],
          "V9F receipt expected manifest hash")
    exact(receipt["input_manifest"].get("match"), True,
          "V9F receipt manifest hash match")
    exact(receipt.get("verdict"),
          "SOURCE_ONLY_DESIGN_CANDIDATE__NO_GATE_PASS__NO_RELEASE_CREDIT",
          "V9F receipt verdict")
    exact(receipt.get("accepted_urdf_unchanged"), True,
          "V9F receipt accepted URDF integrity")
    exact(receipt.get("frozen_assets_modified"), False,
          "V9F receipt frozen-asset status")
    exact(receipt.get("violations"), [], "V9F receipt source-shape violations")
    exact(receipt.get("next_stage_authorized"), False,
          "V9F receipt next-stage authority")
    exact(receipt.get("release_credit"), False, "V9F receipt release credit")
    exact(receipt.get("part_count_exported"),
          contract["receipt_part_count_exported"], "V9F receipt part count")

    exact(centerline.get("schema"), "B601_ROUTE_C_HARNESS_CENTERLINE_V9F",
          "V9F centerline schema")
    exact(centerline.get("architecture"), EXPECTED_ARCHITECTURE,
          "V9F centerline architecture")
    exact(centerline.get("design_candidate_sequence"),
          contract["design_candidate_sequence"], "V9F centerline candidate sequence")
    exact(centerline["owner_authority"].get("decision_id"), "ODR-58",
          "V9F centerline owner")
    exact(centerline["owner_authority"].get("input_manifest_sha256"),
          manifest_pin["sha256"], "V9F centerline manifest hash")
    exact(len(centerline.get("segments", [])), contract["centerline_segment_count"],
          "V9F centerline segment count")
    j4_segments = [segment for segment in centerline["segments"]
                   if segment.get("id") == EXPECTED_SEGMENT_ID]
    exact(len(j4_segments), 1, "V9F J4 segment cardinality")
    exact([section.get("type") for section in j4_segments[0].get("sections", [])],
          contract["j4_section_types"], "V9F J4 section topology")

    j4 = centerline["j4_trombone_annular_follower"]
    exact(j4.get("q4_trombone_law"), contract["q4_trombone_law"],
          "V9F q4 trombone law")
    exact(j4.get("q4_annulus_law"), contract["q4_annulus_law"],
          "V9F q4 annulus law")
    exact(j4.get("q4_full_hardware_limits_rad"),
          contract["q4_full_hardware_limits_rad"], "V9F q4 hardware limits")
    finite_close(j4.get("physical_travel_mm"), contract["physical_travel_mm"],
                 "V9F physical travel")
    finite_close(j4.get("hard_stop_margin_each_end_mm"),
                 contract["hard_stop_margin_each_end_mm"], "V9F hard-stop margin")
    exact(j4.get("hard_stop_center_x_mm"), contract["center_x_hard_stops_mm"],
          "V9F hard-stop interval")
    telescope = j4["four_stage_telescope"]
    exact(telescope.get("stage_count_per_leg"), contract["stage_count_per_leg"],
          "V9F telescope stage count")
    finite_close(telescope.get("stage_length_mm"), contract["stage_length_mm"],
                 "V9F telescope stage length")
    finite_close(telescope.get("minimum_overlap_requirement_mm"),
                 contract["minimum_overlap_requirement_mm"],
                 "V9F minimum overlap requirement")
    finite_close(telescope.get("minimum_overlap_full_range_mm"),
                 contract["minimum_overlap_full_range_mm"],
                 "V9F minimum overlap full range")
    exact([stage.get("motion_class") for stage in telescope.get("stages", [])],
          contract["stage_motion_classes"], "V9F stage motion classes")
    finite_close(j4.get("trombone_u_radius_mm"), contract["trombone_u_radius_mm"],
                 "V9F trombone U radius")
    annulus = j4["annular_follower"]
    finite_close(annulus.get("radius_mm"), contract["annular_follower_radius_mm"],
                 "V9F annular follower radius")
    for index, (actual, expected) in enumerate(zip(
            annulus.get("axis_origin_A0_mm", []),
            contract["annular_axis_origin_A0_mm"])):
        finite_close(actual, expected, f"V9F annular axis origin[{index}]")
    exact(len(annulus.get("axis_origin_A0_mm", [])), 3,
          "V9F annular axis origin cardinality")
    for key, source_key in (("axis_direction_A0", "annular_axis_direction_A0"),
                            ("basis_e1", "annular_basis_e1_A0"),
                            ("basis_e2", "annular_basis_e2_A0")):
        exact(len(annulus.get(key, [])), 3, f"V9F annular {key} cardinality")
        for index, (actual, expected) in enumerate(zip(
                annulus[key], contract[source_key])):
            finite_close(actual, expected, f"V9F annular {key}[{index}]")
    finite_close(annulus.get("physical_guide_sweep_deg"),
                 contract["physical_annular_guide_sweep_deg"],
                 "V9F annular physical guide sweep")
    finite_close(annulus.get("mission_guide_margin_deg"),
                 contract["mission_guide_margin_deg"],
                 "V9F mission guide margin")
    finite_close(annulus.get("full_hardware_guide_margin_deg"),
                 contract["full_hardware_guide_margin_deg"],
                 "V9F full-range guide margin")
    exact(annulus.get("full_hardware_coverage_status"),
          contract["full_hardware_coverage_status"],
          "V9F full-range guide status")
    exact(j4.get("installed_bundle_resistance_torque_status"),
          contract["installed_bundle_resistance_torque_status"],
          "V9F installed-bundle torque hold")
    exact(j4.get("single_bundle_not_branches"), True,
          "V9F single-bundle topology")
    proof_contract = j4["constant_length_proof"]
    finite_close(proof_contract.get("machine_residual_tolerance_required_mm"),
                 contract["constant_length_residual_tolerance_mm"],
                 "V9F constant-length tolerance")
    finite_close(proof_contract.get("derivative_sum_mm_per_rad"), 0.0,
                 "V9F derivative sum")

    finite_close(Q4_MIN, contract["q4_full_hardware_limits_rad"][0],
                 "proof Q4_MIN binding")
    finite_close(Q4_MAX, contract["q4_full_hardware_limits_rad"][1],
                 "proof Q4_MAX binding")
    finite_close(Q4_MID, contract["q4_center_reference_rad"],
                 "proof Q4_MID binding")
    finite_close(XC_MID, contract["center_x_mid_mm"], "proof XC_MID binding")
    finite_close(GAIN, contract["center_x_gain_mm_per_rad"], "proof gain binding")
    finite_close(XF, contract["fixed_leg_station_x_mm"], "proof fixed-leg binding")
    finite_close(math.degrees(BETA_OFFSET), contract["beta_offset_deg"],
                 "proof beta offset binding")
    finite_close(R_U, contract["trombone_u_radius_mm"], "proof U radius binding")
    finite_close(R_ANN, contract["annular_follower_radius_mm"],
                 "proof annulus radius binding")
    finite_close(ANN_GUIDE_SWEEP_DEG,
                 abs(contract["physical_annular_guide_sweep_deg"]),
                 "proof annular guide sweep binding")
    exact(STAGE_COUNT, contract["stage_count_per_leg"], "proof stage count binding")
    finite_close(STAGE_LENGTH, contract["stage_length_mm"],
                 "proof stage length binding")
    finite_close(MIN_STAGE_OVERLAP, contract["minimum_overlap_requirement_mm"],
                 "proof overlap binding")
    finite_close(STOP_MIN, contract["center_x_hard_stops_mm"][0],
                 "proof negative stop binding")
    finite_close(STOP_MAX, contract["center_x_hard_stops_mm"][1],
                 "proof positive stop binding")
    finite_close(LENGTH_TOL_MM, contract["constant_length_residual_tolerance_mm"],
                 "proof length tolerance binding")
    finite_close(FOLLOWER_TOL_MM,
                 contract["follower_position_residual_tolerance_mm"],
                 "proof follower tolerance binding")
    finite_close(TANGENT_TOL_DEG,
                 contract["follower_tangent_residual_tolerance_deg"],
                 "proof tangent tolerance binding")

    with workspace_path(pins["clamp_and_guide_register"]["path"]).open(
            "r", encoding="utf-8", newline="") as stream:
        clamp_rows = list(csv.DictReader(stream))
    fail_closed(bool(clamp_rows), "V9F clamp register is empty")
    clamp_ids = [row.get("clamp_id") for row in clamp_rows]
    exact(len(set(clamp_ids)), len(clamp_ids), "V9F clamp id uniqueness")
    by_id = {row["clamp_id"]: row for row in clamp_rows}
    for clamp_id, host_link in contract["required_clamp_host_pairs"].items():
        fail_closed(clamp_id in by_id, f"required V9F clamp missing: {clamp_id}")
        exact(by_id[clamp_id].get("host_link"), host_link,
              f"V9F clamp host {clamp_id}")

    receipt_parts = receipt.get("parts", [])
    exact(len(receipt_parts), contract["receipt_part_count_exported"],
          "V9F receipt part array count")
    motion_counts = Counter(part.get("motion_class") for part in receipt_parts
                            if part.get("motion_class"))
    exact(dict(motion_counts), contract["required_motion_class_counts"],
          "V9F receipt dynamic motion-class counts")

    exact(mass_geometry.get("schema"), "ROUTE_C_PARTS_MASS_GEOMETRY_V1",
          "V9F mass geometry schema")
    mass_parts = mass_geometry.get("parts", [])
    exact(len(mass_parts), contract["mass_geometry_part_count"],
          "V9F mass geometry part count")
    role_counts = Counter(part.get("geometry_role") for part in mass_parts)
    exact(role_counts.get("PHYSICAL", 0), contract["mass_geometry_physical_count"],
          "V9F mass geometry physical count")
    exact(role_counts.get("BUNDLE_ENVELOPE", 0),
          contract["mass_geometry_bundle_envelope_count"],
          "V9F mass geometry bundle-envelope count")
    exact(set(role_counts), {"PHYSICAL", "BUNDLE_ENVELOPE"},
          "V9F mass geometry roles")
    fail_closed(all(part.get("mass_counted") is (part.get("geometry_role") == "PHYSICAL")
                    for part in mass_parts),
                "V9F mass-counted semantics mismatch")
    fail_closed(all(isinstance(part.get("overlap_disposition"), str)
                    and bool(part["overlap_disposition"].strip())
                    for part in mass_parts),
                "V9F mass geometry has empty overlap disposition")
    fail_closed(all(isinstance(part.get("volume_mm3"), (int, float))
                    and math.isfinite(float(part["volume_mm3"]))
                    and float(part["volume_mm3"]) > 0.0
                    for part in mass_parts),
                "V9F mass geometry has non-positive or non-finite volume")
    exact(Counter(part.get("name") for part in mass_parts),
          Counter(part.get("name") for part in receipt_parts),
          "V9F receipt/mass-geometry part identity")

    proof_inputs = binding["independent_proof_inputs"]
    exact(workspace_path(proof_inputs["accepted_b601_urdf"]["path"]),
          URDF.resolve(), "proof URDF path binding")
    exact(proof_inputs["accepted_b601_urdf"]["sha256"], URDF_SHA256,
          "proof URDF hash binding")
    exact(workspace_path(
        proof_inputs["mandatory_mission_trajectory_contract"]["path"]),
        MISSION.resolve(), "proof mission path binding")

    return binding, byte_audit, receipt, centerline


def main() -> None:
    binding, byte_audit, receipt, centerline = validate_authority_binding()
    if sha256(URDF) != URDF_SHA256:
        raise SystemExit("FAIL_CLOSED_AUTHORITY_BINDING: accepted URDF hash mismatch")

    arm = Arm(URDF)
    qzero = [0.0] * 6
    f0 = arm.fk(qzero)
    T30, T40 = f0["link3"], f0["link4"]

    # Select the point on the accepted joint-4 axis whose A0 y-coordinate is
    # exactly 210 mm.  The tiny z slope is retained from rpy=-1.5708.
    O_joint = T40[:3, 3]
    axis_a0 = T40[:3, :3] @ np.array([0.0, 0.0, 1.0])
    axis_a0 /= np.linalg.norm(axis_a0)
    along = (210.0 - O_joint[1]) / axis_a0[1]
    O_a0 = O_joint + along * axis_a0
    e1_a0 = np.array([1.0, 0.0, 0.0])
    e2_a0 = np.cross(axis_a0, e1_a0)
    e2_a0 /= np.linalg.norm(e2_a0)

    O_l3 = transform_point(np.linalg.inv(T30), O_a0)
    e1_l3 = T30[:3, :3].T @ e1_a0
    e2_l3 = T30[:3, :3].T @ e2_a0

    contract = binding["v9f_candidate"]["key_parameter_contract"]
    annulus_contract = centerline["j4_trombone_annular_follower"]["annular_follower"]
    for index, (actual, expected) in enumerate(zip(
            O_a0, annulus_contract["axis_origin_A0_mm"])):
        finite_close(actual, expected, f"derived annular axis origin[{index}]", 1.0e-9)
    for label, actual_values, expected_values in (
            ("axis", axis_a0, annulus_contract["axis_direction_A0"]),
            ("basis_e1", e1_a0, annulus_contract["basis_e1"]),
            ("basis_e2", e2_a0, annulus_contract["basis_e2"])):
        for index, (actual, expected) in enumerate(zip(actual_values, expected_values)):
            finite_close(actual, expected, f"derived annular {label}[{index}]", 1.0e-12)

    alpha_fixed = math.pi / 2.0
    finite_close(math.degrees(alpha_fixed),
                 contract["annulus_fixed_entry_angle_deg"],
                 "proof annulus fixed-entry angle binding")
    alpha0 = alpha_fixed - beta(0.0)
    moving0_a0 = O_a0 + R_ANN * (math.cos(alpha0)*e1_a0 + math.sin(alpha0)*e2_a0)
    tangent0_a0 = math.sin(alpha0)*e1_a0 - math.cos(alpha0)*e2_a0
    moving0_l4 = transform_point(np.linalg.inv(T40), moving0_a0)
    tangent0_l4 = T40[:3, :3].T @ tangent0_a0

    entry_a0 = O_a0 + R_ANN * e2_a0
    fixed_b_a0 = np.array([XF, entry_a0[1], entry_a0[2]])
    fixed_run = float(entry_a0[0] - fixed_b_a0[0])
    entry_line_tangent = (entry_a0-fixed_b_a0)/np.linalg.norm(entry_a0-fixed_b_a0)
    entry_arc_tangent = e1_a0  # decreasing-angle tangent at alpha=+90 deg
    entry_tangent_error = math.degrees(math.acos(float(np.clip(
        entry_line_tangent @ entry_arc_tangent, -1.0, 1.0))))
    # The downstream seed is defined by moving0 + s*tangent0.  Unlike a
    # different top-of-ring/+X seed, this creates no endpoint reversal.
    downstream_seed = moving0_a0 + 100.0*tangent0_a0
    downstream_tangent = (downstream_seed-moving0_a0)/np.linalg.norm(
        downstream_seed-moving0_a0)
    downstream_tangent_error = math.degrees(math.acos(float(np.clip(
        downstream_tangent @ tangent0_a0, -1.0, 1.0))))

    mission = yaml.safe_load(MISSION.read_text(encoding="utf-8"))
    rows = [(name, [float(x) for x in state["q_rad"]], "MANDATORY_STATE")
            for name, state in mission["states"].items()]
    rows.extend([
        ("FULL_Q4_MIN", [0.0, 0.0, 0.0, Q4_MIN, 0.0, 0.0], "FULL_HARDWARE_BOUNDARY"),
        ("FULL_Q4_MAX", [0.0, 0.0, 0.0, Q4_MAX, 0.0, 0.0], "FULL_HARDWARE_BOUNDARY"),
    ])

    results = []
    total_lengths = []
    max_follower_residual = 0.0
    max_tangent_error = 0.0
    min_overlap = math.inf
    min_stop_margin = math.inf
    for name, q, scope in rows:
        q4 = q[3]
        frames = arm.fk(q)
        T3, T4 = frames["link3"], frames["link4"]
        O = transform_point(T3, O_l3)
        e1 = T3[:3, :3] @ e1_l3
        e2 = T3[:3, :3] @ e2_l3
        alpha = alpha_fixed - beta(q4)
        moving_ring = O + R_ANN * (math.cos(alpha)*e1 + math.sin(alpha)*e2)
        moving_link4 = transform_point(T4, moving0_l4)
        follower_residual = float(np.linalg.norm(moving_ring-moving_link4))

        tangent_ring = math.sin(alpha)*e1 - math.cos(alpha)*e2
        tangent_link4 = T4[:3, :3] @ tangent0_l4
        tangent_cos = float(np.clip(tangent_ring @ tangent_link4 /
                                    (np.linalg.norm(tangent_ring)*np.linalg.norm(tangent_link4)),
                                    -1.0, 1.0))
        tangent_error = math.degrees(math.acos(tangent_cos))

        xc = x_center(q4)
        leg_length = XF - xc
        overlap = (STAGE_COUNT*STAGE_LENGTH-leg_length)/(STAGE_COUNT-1)
        stop_margin = min(xc-STOP_MIN, STOP_MAX-xc)
        trombone_length = 2.0*leg_length + math.pi*R_U
        annulus_length = R_ANN*beta(q4)
        total = trombone_length + fixed_run + annulus_length
        guide_margin = ANN_GUIDE_SWEEP_DEG-math.degrees(beta(q4))

        total_lengths.append(total)
        max_follower_residual = max(max_follower_residual, follower_residual)
        max_tangent_error = max(max_tangent_error, tangent_error)
        min_overlap = min(min_overlap, overlap)
        min_stop_margin = min(min_stop_margin, stop_margin)
        results.append({
            "state": name,
            "scope": scope,
            "q4_rad": q4,
            "xC_mm": xc,
            "leg_length_mm": leg_length,
            "adjacent_stage_overlap_mm": overlap,
            "hard_stop_margin_mm": stop_margin,
            "beta_deg": math.degrees(beta(q4)),
            "annular_guide_margin_deg": guide_margin,
            "trombone_length_mm": trombone_length,
            "fixed_run_length_mm": fixed_run,
            "annulus_length_mm": annulus_length,
            "dynamic_subsystem_total_length_mm": total,
            "follower_position_residual_mm": follower_residual,
            "follower_tangent_error_deg": tangent_error,
        })

    length_spread = max(total_lengths)-min(total_lengths)
    mission_rows = [r for r in results if r["scope"] == "MANDATORY_STATE"]
    full_rows = [r for r in results if r["scope"] == "FULL_HARDWARE_BOUNDARY"]
    checks = {
        "fallback_authority_binding_hash_match": sha256(BINDING) == BINDING_SHA256,
        "all_bound_byte_hashes_match": bool(byte_audit) and all(
            item["match"] is True for item in byte_audit),
        "single_fallback_budget_consumed_and_none_remaining": (
            binding["iteration_budget_accounting"]["technically_distinct_fallbacks_consumed"] == 1
            and binding["iteration_budget_accounting"]["technically_distinct_fallbacks_remaining"] == 0),
        "candidate_only_no_next_stage_or_release_credit": (
            binding["next_stage_authorized"] is False
            and binding["release_credit"] is False
            and receipt["next_stage_authorized"] is False
            and receipt["release_credit"] is False),
        "accepted_urdf_hash_match": True,
        "constant_length_residual_le_1e_6_mm": length_spread <= LENGTH_TOL_MM,
        "follower_position_residual_le_1e_6_mm": max_follower_residual <= FOLLOWER_TOL_MM,
        "follower_tangent_error_le_1e_6_deg": max_tangent_error <= TANGENT_TOL_DEG,
        "fixed_entry_tangent_error_le_1e_6_deg": entry_tangent_error <= TANGENT_TOL_DEG,
        "q0_downstream_tangent_error_le_1e_6_deg": downstream_tangent_error <= TANGENT_TOL_DEG,
        "full_range_telescope_overlap_ge_25_mm": all(
            r["adjacent_stage_overlap_mm"] >= MIN_STAGE_OVERLAP for r in full_rows),
        "full_range_telescope_overlap_lt_stage_length": all(
            r["adjacent_stage_overlap_mm"] < STAGE_LENGTH for r in full_rows),
        "full_range_hard_stop_margin_nonnegative": all(
            r["hard_stop_margin_mm"] >= 0.0 for r in full_rows),
        "mandatory_states_inside_185deg_annular_guide": all(
            r["annular_guide_margin_deg"] >= 0.0 for r in mission_rows),
        "full_range_covered_by_185deg_annular_guide": all(
            r["annular_guide_margin_deg"] >= 0.0 for r in full_rows),
    }
    expected_negative = not checks["full_range_covered_by_185deg_annular_guide"]
    internal_pass = all(v for k, v in checks.items()
                        if k != "full_range_covered_by_185deg_annular_guide")

    doc = {
        "schema": "ROUTE_C_V9F_INDEPENDENT_KINEMATIC_PROOF_V2",
        "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
        "authority": "CANDIDATE_ONLY__INDEPENDENT_ANALYTIC_REPRODUCTION__NO_GATE_PASS__NO_RELEASE_CREDIT",
        "scope": "ODR-58 V9F fallback authority/byte integrity plus independent kinematic identity; not qualification or release",
        "architecture": EXPECTED_ARCHITECTURE,
        "fallback_budget": {
            "authorized": binding["iteration_budget_accounting"][
                "technically_distinct_fallbacks_authorized"],
            "consumed": binding["iteration_budget_accounting"][
                "technically_distinct_fallbacks_consumed"],
            "remaining": binding["iteration_budget_accounting"][
                "technically_distinct_fallbacks_remaining"],
            "status": binding["iteration_budget_accounting"]["fallback_budget_status"],
        },
        "primary_negative_lineage": {
            "architecture": binding["primary_negative_lineage"]["primary_architecture"],
            "early_rejection": binding["primary_negative_lineage"]
                ["same_architecture_bounded_repair"]["verdict"],
            "bounded_repair_disposition": binding["primary_negative_lineage"]
                ["same_architecture_bounded_repair"]["disposition"],
            "terminal_falsification": binding["primary_negative_lineage"]
                ["terminal_topology_falsification"]["decision"],
            "release_credit": False,
        },
        "input_pins": {
            "fallback_authority_binding": {
                "path": BINDING.relative_to(WORKSPACE).as_posix(),
                "sha256": sha256(BINDING),
                "expected": BINDING_SHA256,
            },
            "accepted_urdf": {
                "path": URDF.relative_to(WORKSPACE).as_posix(),
                "sha256": sha256(URDF),
                "expected": binding["independent_proof_inputs"][
                    "accepted_b601_urdf"]["sha256"],
            },
            "mission_contract": {
                "path": MISSION.relative_to(WORKSPACE).as_posix(),
                "sha256": sha256(MISSION),
                "expected": binding["independent_proof_inputs"][
                    "mandatory_mission_trajectory_contract"]["sha256"],
            },
        },
        "bound_byte_audit": byte_audit,
        "derived_axis": {
            "point_A0_mm_at_y_210": O_a0.tolist(),
            "unit_axis_A0": axis_a0.tolist(),
            "e1_A0": e1_a0.tolist(),
            "e2_A0": e2_a0.tolist(),
            "annulus_entry_A0_mm": entry_a0.tolist(),
            "q0_moving_endpoint_A0_mm": moving0_a0.tolist(),
            "q0_moving_endpoint_link4_mm": moving0_l4.tolist(),
            "q0_downstream_seed_A0_mm": downstream_seed.tolist(),
        },
        "laws": {
            "xC_mm": "-205 - 27.5*(q4_rad + 0.15)",
            "beta_rad": "rad(20) + 1.57 - q4_rad",
            "L_trombone_mm": "2*(-100-xC) + pi*sqrt(23^2+50^2)",
            "L_annulus_mm": "55*beta",
            "dL_trombone_dq4_mm_per_rad": 55.0,
            "dL_annulus_dq4_mm_per_rad": -55.0,
        },
        "metrics": {
            "dynamic_subsystem_length_reference_mm": total_lengths[0],
            "dynamic_subsystem_length_spread_mm": length_spread,
            "max_follower_position_residual_mm": max_follower_residual,
            "max_follower_tangent_error_deg": max_tangent_error,
            "fixed_entry_tangent_error_deg": entry_tangent_error,
            "q0_downstream_tangent_error_deg": downstream_tangent_error,
            "minimum_adjacent_stage_overlap_mm": min_overlap,
            "minimum_hard_stop_margin_mm": min_stop_margin,
            "mission_min_annular_guide_margin_deg": min(
                r["annular_guide_margin_deg"] for r in mission_rows),
            "full_range_min_annular_guide_margin_deg": min(
                r["annular_guide_margin_deg"] for r in full_rows),
        },
        "checks": checks,
        "expected_negative_full_range_hold_reproduced": expected_negative,
        "states": results,
        "holds": [
            "FULL_HARDWARE_RANGE_ANNULAR_GUIDE_COVERAGE_DEFERRED_HOLD",
            "FOLLOWER_CONTACT_PRESSURE_FRICTION_WEAR_AND_DRIVE_TORQUE_UNKNOWN",
            "P08_INSTALLED_BUNDLE_RESTORING_MOMENT_UNKNOWN_NOT_ZERO_FILLED",
            "LOCAL_FASTENER_ALLOWABLE_AND_AS_BUILT_QUALIFICATION_UNKNOWN",
        ],
        "verdict": ("PASS_INDEPENDENT_KINEMATIC_IDENTITY__MISSION_GUIDE_RANGE_ONLY__QUALIFICATION_HOLDS"
                    if internal_pass and expected_negative else
                    "FAIL_INDEPENDENT_KINEMATIC_PROOF"),
        "review_status": "PENDING_OWNER_REVIEW",
        "manufacturing_use": "PROHIBITED",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(doc["verdict"])
    print("length spread mm:", length_spread)
    print("follower residual mm:", max_follower_residual)


if __name__ == "__main__":
    main()
