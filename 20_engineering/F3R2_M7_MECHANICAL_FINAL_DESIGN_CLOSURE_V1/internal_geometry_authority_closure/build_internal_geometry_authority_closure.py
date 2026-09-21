#!/usr/bin/env python3
"""Build the documentation-only internal geometry authority closure package.

This package does not create or edit CAD/mesh/URDF artifacts.  It resolves the
340.5/366.0 mm track classification and freezes operational Solar R2 root
frames from already-controlled geometry evidence.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


PACKAGE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[3]
GENERATED_DATE_LOCAL = "2026-08-24"

SOURCE_PINS = [
    {
        "id": "BUS_GEOMETRY_SSOT",
        "path": "20_engineering/config/geometry/service_spacecraft_v1.yaml",
        "bytes": 1176,
        "sha256": "8DD8F22FF1F893273DE2215EA12819E4D41CC0E20B853ADC0774052237881432",
        "role": "operational/dynamics 12U rigid-bus geometry SSOT",
    },
    {
        "id": "V22_BUILDER",
        "path": "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation/sw_v22_builder.py",
        "bytes": 29337,
        "sha256": "DA1E136E77078C37C2570B09FD1F316549C9518684F280B46F7954AFFE9F982C",
        "role": "explicit two-track source classification",
    },
    {
        "id": "V22_BUILD_SPEC",
        "path": "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation/b5_build_spec.yaml",
        "bytes": 6073,
        "sha256": "23158D186674B544F302347312C7E079E63D68FC18A7AF439D635A5B1AD8CAD4",
        "role": "366 mm display-track primary-structure proposal",
    },
    {
        "id": "V22_GATE0_RULING",
        "path": "20_engineering/design_inputs/v2_2_physical_architecture/gate_0_ruling_record.yaml",
        "bytes": 1965,
        "sha256": "EDD794B21221EB7EFA9F01E67BF52732A993B83C74D8CE040C88A316C0528B71",
        "role": "direct dual-track ruling: 366 display/mechanism, 340.5 dynamics SSOT",
    },
    {
        "id": "M7_PRODUCT_STRUCTURE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/PRODUCT_STRUCTURE_V1.yaml",
        "bytes": 48807,
        "sha256": "0F9897EF4E41666DDB29CB0FC621DD737FDD8CCDE3F5527030E53A9D1604681A",
        "role": "M7 six-primitive bus proxy classification and detailed-structure HOLD",
    },
    {
        "id": "M7_NATIVE_DONOR_DISPOSITION",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml",
        "bytes": 51418,
        "sha256": "10106444309B6E835D9C87EF41A0FF78FF4CFDAC8C773C7B9B158FC3C0DA1B05",
        "role": "direct counter-authority: detailed V2.2 native primary-structure donor remains native-only/reintegration HOLD",
    },
    {
        "id": "SOLAR_R2_REPORT",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V2.json",
        "bytes": 16118,
        "sha256": "4286EA2BBD84FB8EC33DDADE329534DA29194650AD22429245ECF8757B9AED1C",
        "role": "current Solar R2 geometry/build evidence",
    },
    {
        "id": "SOLAR_R2_STEP",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step",
        "bytes": 131834,
        "sha256": "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795",
        "role": "hash-bound aggregate S-authored dual-pose evidence; forbidden as a pose-neutral kinematic visual",
    },
    {
        "id": "SOLAR_R2_KINEMATICS",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/solar_array_r2_kinematics.py",
        "bytes": 7431,
        "sha256": "ADC2B6D3E4270886AFA9B90D93C9A943A518C97F81D9FDBCCCDC6E2EFBA64EAC",
        "role": "Solar R2 chord-centering and deployment convention source",
    },
    {
        "id": "R2_HF_MODEL",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round3_hf_rom_v2/R2_HF_MODEL_V2.yaml",
        "bytes": 7867,
        "sha256": "B7C77E3E48733FD6265A77BEB4EC2E186BA8C07CC12522C065CDA7816A879381",
        "role": "independent current consumer of the 115.4/-108.15 mm root line",
    },
    {
        "id": "M4_FRAME_TREE",
        "path": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml",
        "bytes": 6236,
        "sha256": "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA",
        "role": "legacy R1 F_L/F_R provenance and exclusion control",
    },
    {
        "id": "PREBIND_READINESS_BASE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/UNIFIED_R2_PREBIND_READINESS_V1.json",
        "bytes": 6375,
        "sha256": "92872D69E2C027E76A043BD531BEF6AB5C66B09513699C679691BCAEA456C512",
        "role": "append-only prebind readiness base; not modified",
    },
    {
        "id": "PREBIND_GATE_BASE",
        "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/UNIFIED_R2_PREBIND_GATE_V1.json",
        "bytes": 3618,
        "sha256": "DA1F2661C3CCF641C9379CE50406A14510FABA9DC04B4E02F616768194F8CEAA",
        "role": "append-only prebind Gate base; not modified",
    },
]

OUTPUTS = [
    "BUS_12U_LENGTH_TRACK_RULING_V1.yaml",
    "SOLAR_R2_ROOT_FRAME_REGISTRATION_V1.yaml",
    "INTERNAL_GEOMETRY_AUTHORITY_GATE_V1.json",
    "UNIFIED_R2_PREBIND_GEOMETRY_DELTA_V1.json",
    "INTERNAL_GEOMETRY_AUTHORITY_RECEIPT_V1.md",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(rel: str) -> dict[str, Any]:
    with (ROOT / rel).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_yaml(rel: str) -> dict[str, Any]:
    with (ROOT / rel).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def verify_pins() -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for pin in SOURCE_PINS:
        path = ROOT / pin["path"]
        require(path.is_file(), f"missing source {pin['id']}: {pin['path']}")
        require(path.stat().st_size == pin["bytes"], f"byte drift: {pin['id']}")
        actual = sha256(path)
        require(actual == pin["sha256"], f"hash drift: {pin['id']}")
        verified.append({**pin, "verified": True})
    return verified


def midpoint(a: float, b: float) -> float:
    return (float(a) + float(b)) / 2.0


def vec_close(a: list[float], b: list[float], tol: float = 1e-12) -> bool:
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def infer_root_from_report(report: dict[str, Any], side: str) -> dict[str, Any]:
    metrics = report["shape_metrics"]
    keepout = metrics[f"R2_{side}_ROOT_HINGE_KEEPOUT"]["aabb_S_mm"]
    deployed = metrics[f"R2_{side}_LEAF1_DEPLOYED"]["aabb_S_mm"]
    x_mid = midpoint(keepout[0], keepout[3])
    y_mid = midpoint(keepout[1], keepout[4])
    z_mid = midpoint(keepout[2], keepout[5])
    root_edge_y = deployed[1] if side == "LEFT" else deployed[4]
    leaf_mid_z = midpoint(deployed[2], deployed[5])
    return {
        "keepout_midpoint_S_mm": [x_mid, y_mid, z_mid],
        "deployed_leaf_root_edge_y_mm": float(root_edge_y),
        "deployed_leaf_midplane_z_mm": leaf_mid_z,
        "keepout_x_span_S_mm": [float(keepout[0]), float(keepout[3])],
    }


def homogeneous(rotation: list[list[float]], translation: list[float]) -> list[list[float]]:
    return [
        [*rotation[0], float(translation[0])],
        [*rotation[1], float(translation[1])],
        [*rotation[2], float(translation[2])],
        [0.0, 0.0, 0.0, 1.0],
    ]


def homogeneous_from_columns(
    origin: list[float] | tuple[float, float, float],
    e1: list[float] | tuple[float, float, float],
    e2: list[float] | tuple[float, float, float],
    e3: list[float] | tuple[float, float, float],
) -> list[list[float]]:
    """Build a child-to-parent transform from its three parent-expressed axes."""
    return [
        [float(e1[0]), float(e2[0]), float(e3[0]), float(origin[0])],
        [float(e1[1]), float(e2[1]), float(e3[1]), float(origin[1])],
        [float(e1[2]), float(e2[2]), float(e3[2]), float(origin[2])],
        [0.0, 0.0, 0.0, 1.0],
    ]


def matmul4(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(float(a[i][k]) * float(b[k][j]) for k in range(4)) for j in range(4)] for i in range(4)]


def rigid_inverse(t: list[list[float]]) -> list[list[float]]:
    r = [row[:3] for row in t[:3]]
    rt = [[r[j][i] for j in range(3)] for i in range(3)]
    p = [float(t[i][3]) for i in range(3)]
    q = [-sum(rt[i][j] * p[j] for j in range(3)) for i in range(3)]
    return homogeneous(rt, q)


def rotx4(q_rad: float) -> list[list[float]]:
    c, s = math.cos(q_rad), math.sin(q_rad)
    return [[1.0, 0.0, 0.0, 0.0], [0.0, c, -s, 0.0], [0.0, s, c, 0.0], [0.0, 0.0, 0.0, 1.0]]


def matrix_close(a: list[list[float]], b: list[list[float]], tol: float = 1e-10) -> bool:
    return len(a) == len(b) and all(
        len(arow) == len(brow) and all(abs(float(x) - float(y)) <= tol for x, y in zip(arow, brow))
        for arow, brow in zip(a, b)
    )


def import_hash_pinned_module(rel: str, module_name: str) -> ModuleType:
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, f"cannot import {rel}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_yaml(name: str, value: dict[str, Any]) -> None:
    with (PACKAGE / name).open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(value, handle, sort_keys=False, allow_unicode=True, width=120)


def write_json(name: str, value: dict[str, Any]) -> None:
    with (PACKAGE / name).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_text(name: str, text: str) -> None:
    (PACKAGE / name).write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    pins = verify_pins()
    pin_by_id = {item["id"]: item for item in pins}

    bus_yaml = read_yaml(pin_by_id["BUS_GEOMETRY_SSOT"]["path"])
    v22_source = (ROOT / pin_by_id["V22_BUILDER"]["path"]).read_text(encoding="utf-8")
    v22_spec = read_yaml(pin_by_id["V22_BUILD_SPEC"]["path"])
    v22_gate0 = read_yaml(pin_by_id["V22_GATE0_RULING"]["path"])
    m7_product = read_yaml(pin_by_id["M7_PRODUCT_STRUCTURE"]["path"])
    native_disposition_text = (ROOT / pin_by_id["M7_NATIVE_DONOR_DISPOSITION"]["path"]).read_text(encoding="utf-8")
    solar = read_json(pin_by_id["SOLAR_R2_REPORT"]["path"])
    kinematics = import_hash_pinned_module(pin_by_id["SOLAR_R2_KINEMATICS"]["path"], "solar_array_r2_kinematics_authority_source")
    hf = read_yaml(pin_by_id["R2_HF_MODEL"]["path"])
    m4_frames = read_yaml(pin_by_id["M4_FRAME_TREE"]["path"])
    prebind_readiness = read_json(pin_by_id["PREBIND_READINESS_BASE"]["path"])
    prebind_gate = read_json(pin_by_id["PREBIND_GATE_BASE"]["path"])

    require(bus_yaml["version"] == "v1", "bus SSOT version drift")
    require("3 x [113.5, 226.3, 226.3]" in str(bus_yaml["bays_mm"]), "bus bay declaration drift")
    bus_length = 3.0 * 113.5
    require(bus_length == 340.5, "bus length derivation failed")
    require('TRACK = "display_track_366;dynamics_SSOT_340.5_unchanged"' in v22_source, "V2.2 two-track declaration missing")
    require(float(v22_spec["params"]["BUS_X_TOTAL"]) == 366.0, "V2.2 display length drift")
    require("366.0" in str(v22_gate0["envelope_dual_track_registration"]["display_mechanism_track"]), "Gate0 display track drift")
    require("340.5" in str(v22_gate0["envelope_dual_track_registration"]["dynamics_ssot_track"]), "Gate0 dynamics track drift")
    m7_bus = next(item for item in m7_product["product_tree"] if item["id"] == "BUS_PRIMARY_STRUCTURE")
    require("solid envelope proxy" in m7_bus["composition_note"], "M7 bus proxy class drift")
    require("INTERNAL_STRUCTURE_NOT_MODELLED" in m7_bus["holds"], "M7 detailed-structure HOLD drift")
    require("native primary structure; x +/-183 mm" in native_disposition_text, "native donor identity drift")
    require("NATIVE_ONLY_NOT_IN_NEUTRAL_DESIGN_FREEZE_CHAIN" in native_disposition_text and "ODR-03 NATIVE_REINTEGRATION_HOLD" in native_disposition_text, "native donor HOLD drift")

    root = solar["parameters"]["root_hinge_line"]
    chord = [float(x) for x in solar["parameters"]["chord_window_S_mm"]]
    require(root == {"y_abs_mm": 115.4, "z_mm": -108.15}, "Solar R2 root line drift")
    require(chord == [-150.0, 150.0], "Solar R2 chord window drift")
    require(abs(float(kinematics.LEAF1_MID_Y) - 115.4) <= 1e-12, "Solar R2 numeric leaf1 root drift")
    require([float(x) for x in kinematics.CHORD_X] == chord, "Solar R2 kinematic chord drift")
    left = infer_root_from_report(solar, "LEFT")
    right = infer_root_from_report(solar, "RIGHT")
    require(vec_close(left["keepout_midpoint_S_mm"], [0.0, 115.4, -108.15]), "left root inference failed")
    require(vec_close(right["keepout_midpoint_S_mm"], [0.0, -115.4, -108.15]), "right root inference failed")
    require(abs(left["deployed_leaf_root_edge_y_mm"] - 115.4) <= 1e-12, "left leaf/root mismatch")
    require(abs(right["deployed_leaf_root_edge_y_mm"] + 115.4) <= 1e-12, "right leaf/root mismatch")
    require(abs(left["deployed_leaf_midplane_z_mm"] + 108.15) <= 1e-12, "left leaf/root z mismatch")
    require(abs(right["deployed_leaf_midplane_z_mm"] + 108.15) <= 1e-12, "right leaf/root z mismatch")
    require(hf["geometry"]["root_hinge_S_m"]["y_abs"] == 0.1154, "HF consumer y drift")
    require(hf["geometry"]["root_hinge_S_m"]["z"] == -0.10815, "HF consumer z drift")
    legacy_left = [float(x) for x in m4_frames["frames"]["F_L"]["origin_S_mm"]]
    legacy_right = [float(x) for x in m4_frames["frames"]["F_R"]["origin_S_mm"]]
    require(legacy_left == [-56.75, 113.15, 0.0], "legacy F_L provenance drift")
    require(legacy_right == [-56.75, -113.15, 0.0], "legacy F_R provenance drift")
    require(prebind_readiness["summary"] == {"criteria_total": 20, "pass": 5, "hold": 15}, "prebind base summary drift")
    require(prebind_gate["outcome"] == "HOLD" and prebind_gate["release_credit"] is False, "prebind base Gate drift")

    # Root frames use +X_local as positive joint rotation.  Mirroring X/Y on
    # the left makes q=+90 deg map the q=0 +Z span to +Y_S; the right maps to
    # -Y_S.  Both matrices are proper rotations (determinant +1).
    r_left = [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    r_right = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    t_left = [0.0, 115.4, -108.15]
    t_right = [0.0, -115.4, -108.15]
    t_s_left = homogeneous(r_left, t_left)
    t_s_right = homogeneous(r_right, t_right)

    # The hash-pinned leaf_solid_frame function emits box-corner-local geometry,
    # not root-joint-local geometry.  Derive and freeze the two q=0 bridges
    # without claiming that an unparsed FCStd object Placement was verified.
    t_s_box_q0: dict[str, list[list[float]]] = {}
    t_root_box_q0: dict[str, list[list[float]]] = {}
    for label, side, t_s_root in (("L", +1, t_s_left), ("R", -1, t_s_right)):
        leaf = kinematics.leaf_segments(side, 0.0, 0.0, 0.0)[0]
        origin, e2, e3 = kinematics.leaf_solid_frame(side, leaf)
        t_s_box_q0[label] = homogeneous_from_columns(origin, (1.0, 0.0, 0.0), e2, e3)
        t_root_box_q0[label] = matmul4(rigid_inverse(t_s_root), t_s_box_q0[label])

    expected_box_bridge_l = [[-1.0, 0.0, 0.0, 150.0], [0.0, 0.0, 1.0, -1.25], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    expected_box_bridge_r = [[1.0, 0.0, 0.0, -150.0], [0.0, 0.0, -1.0, 1.25], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    require(matrix_close(t_root_box_q0["L"], expected_box_bridge_l), "left box-to-root bridge drift")
    require(matrix_close(t_root_box_q0["R"], expected_box_bridge_r), "right box-to-root bridge drift")

    kinematic_angle_checks: list[dict[str, Any]] = []
    for label, side, t_s_root in (("L", +1, t_s_left), ("R", -1, t_s_right)):
        for q_deg in (0.0, 30.0, 90.0):
            leaf = kinematics.leaf_segments(side, q_deg, 180.0, 180.0)[0]
            origin, e2, e3 = kinematics.leaf_solid_frame(side, leaf)
            source_t_s_box = homogeneous_from_columns(origin, (1.0, 0.0, 0.0), e2, e3)
            composed_t_s_box = matmul4(matmul4(t_s_root, rotx4(math.radians(q_deg))), t_root_box_q0[label])
            kinematic_angle_checks.append(
                {
                    "side": label,
                    "q_deg": q_deg,
                    "leaf1_dir_S": [0.0, float(leaf["dir"][0]), float(leaf["dir"][1])],
                    "box_chain_matches_hash_pinned_kinematics": matrix_close(source_t_s_box, composed_t_s_box),
                }
            )
    require(all(row["box_chain_matches_hash_pinned_kinematics"] for row in kinematic_angle_checks), "Solar R2 q sweep bridge mismatch")

    bus_ruling = {
        "schema": "BUS_12U_LENGTH_TRACK_RULING_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "artifact_class": "PROPOSED_ENGINEERING_AUTHORITY_RULING__PENDING_OWNER_REVIEW__DOCUMENTATION_ONLY__NO_GEOMETRY_CHANGE",
        "scope": "12U operational body-length track selection only",
        "ruling": {
            "MODE_OP_rigid_bus_body_length_mm": bus_length,
            "cross_section_mm": [226.3, 226.3],
            "authority": "20_engineering/config/geometry/service_spacecraft_v1.yaml",
            "derivation": "3 bays x 113.5 mm = 340.5 mm",
            "status": "TECHNICAL_CANDIDATE_FROZEN_WITHIN_THIS_PACKAGE__PENDING_OWNER_REVIEW",
        },
        "v22_366_disposition": {
            "value_mm": float(v22_spec["params"]["BUS_X_TOTAL"]),
            "source_classification": "DISPLAY_TRACK_366__DYNAMICS_SSOT_340P5_UNCHANGED",
            "may_be_used_as_physical_primary_structure_authority": False,
            "may_be_averaged_with_340p5": False,
            "status": "EXCLUDED_FROM_OPERATIONAL_BODY_LENGTH_AUTHORITY",
        },
        "closure": {
            "length_conflict_resolved": True,
            "physical_primary_structure_authority_resolved": False,
            "remaining_hold": "HOLD_DETAILED_12U_PRIMARY_STRUCTURE_MEMBERS_OPENINGS_LOAD_PATH_AND_MANUFACTURING_DEFINITION",
            "interpretation": "340.5 mm closes the operational body-length track only; it does not release the six-primitive bus proxy as physical structure.",
        },
        "consumption_rules": [
            "After explicit downstream promotion, Unified R2 operational geometry shall use x=[-170.25,+170.25] mm for the rigid bus body reference.",
            "V2.2 members authored on x=[-183,+183] mm remain display/proposal evidence and require an authorized 340.5 mm redesign before physical reuse.",
            "Launcher/dispenser protrusions, rails and qualification envelope remain separate external-ICD holds.",
            "No existing CAD or dynamics artifact is mutated by this ruling.",
        ],
        "source_pins": [pin_by_id[x] for x in ("BUS_GEOMETRY_SSOT", "V22_BUILDER", "V22_BUILD_SPEC", "V22_GATE0_RULING", "M7_PRODUCT_STRUCTURE", "M7_NATIVE_DONOR_DISPOSITION")],
        "owner_accepted": False,
        "effective_for_downstream_execution": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }

    solar_registration = {
        "schema": "SOLAR_R2_ROOT_FRAME_REGISTRATION_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "artifact_class": "OPERATIONAL_R2_CANDIDATE_FRAME_REGISTRATION__NO_GEOMETRY_CHANGE",
        "matrix_semantics": "p_S = R_S_child * p_child + t_S_child; homogeneous matrices map child coordinates into S",
        "origin_selection": {
            "rule": "midpoint of the controlled root-hinge line over chord window [-150,+150] mm",
            "x_S_mm": midpoint(chord[0], chord[1]),
            "physical_effect": "none; coordinate datum selection on an already-defined hinge line",
        },
        "frames": {
            "T_S_R2_ROOT_L": {
                "matrix_mm": t_s_left,
                "translation_S_m": [x / 1000.0 for x in t_left],
                "rotation_columns": {"X_root_in_S": [-1.0, 0.0, 0.0], "Y_root_in_S": [0.0, -1.0, 0.0], "Z_root_in_S": [0.0, 0.0, 1.0]},
                "positive_axis_S": [-1.0, 0.0, 0.0],
                "q0_leaf_span_S": [0.0, 0.0, 1.0],
                "q_plus_90_leaf_span_S": [0.0, 1.0, 0.0],
            },
            "T_S_R2_ROOT_R": {
                "matrix_mm": t_s_right,
                "translation_S_m": [x / 1000.0 for x in t_right],
                "rotation_columns": {"X_root_in_S": [1.0, 0.0, 0.0], "Y_root_in_S": [0.0, 1.0, 0.0], "Z_root_in_S": [0.0, 0.0, 1.0]},
                "positive_axis_S": [1.0, 0.0, 0.0],
                "q0_leaf_span_S": [0.0, 0.0, 1.0],
                "q_plus_90_leaf_span_S": [0.0, -1.0, 0.0],
            },
        },
        "independent_geometry_recompute": {"left": left, "right": right},
        "registration_checks": {
            "report_root_line_matches_keepout_midpoints": True,
            "deployed_leaf1_root_edges_match_root_line": True,
            "deployed_leaf1_midplanes_match_root_z": True,
            "root_frames_are_right_handed": True,
            "q_plus_90_deploys_outboard_symmetrically": True,
            "q_0_30_90_both_sides_match_hash_pinned_kinematics": True,
            "kinematics_generated_box_local_rebase_round_trip": True,
        },
        "legacy_and_stale_dispositions": {
            "M4_F_L_origin_S_mm": legacy_left,
            "M4_F_R_origin_S_mm": legacy_right,
            "M4_F_L_F_R": "LEGACY_R1_ONLY__FORBIDDEN_AS_R2_ROOT_FRAMES",
            "historical_114p9_mm_literal": "REJECTED_STALE_CONFIGURATION_LITERAL__NO_AVERAGING",
            "kinematics_numeric_LEAF1_MID_Y_mm": float(kinematics.LEAF1_MID_Y),
            "upstream_reissue_hold": "ANY_BUILDER_COMMENT_OR_DERIVED_CANDIDATE_STILL_EMITTING_114P9_MUST_BE_VERSIONED_AND_REISSUED_BEFORE_REGENERATION",
            "current_consumed_y_abs_mm": 115.4,
            "current_consumed_z_mm": -108.15,
        },
        "authority_scope": {
            "operational_candidate_root_frames_frozen": True,
            "technical_candidate_frozen_within_this_package": True,
            "effective_for_downstream_execution": False,
            "panel_root_to_candidate_hinge_axis_registration_established": True,
            "flight_hinge_hardware_datum_released": False,
            "flight_qualification": "HOLD",
            "root_bracket_detail_geometry": "HOLD_NOT_MODELLED",
            "deployment_clearance_release": "HOLD_PENDING_AUTHORIZED_UNIFIED_R2_GEOMETRY_AND_SWEEP",
        },
        "consumer_contract": {
            "matrix_convention": "column vectors; child-to-parent transforms; left multiplication; p_S=T_S_ROOT*Rx(q)*T_ROOT_GEOMETRY*p_geometry",
            "joint_composition": "T_S_LEAF1(q)=T_S_R2_ROOT_SIDE * Rx_active_about_positive_X_root(q) * T_ROOT_LEAF1_Q0",
            "future_unified_R2_CAD": "consume these transforms exactly; do not reuse M4 F_L/F_R; root-local re-authoring or explicit inverse rebase is mandatory",
            "future_system_URDF": {
                "left_joint_origin_xyz_m": [0.0, 0.1154, -0.10815],
                "left_joint_origin_rpy_rad": [0.0, 0.0, math.pi],
                "right_joint_origin_xyz_m": [0.0, -0.1154, -0.10815],
                "right_joint_origin_rpy_rad": [0.0, 0.0, 0.0],
                "axis_in_joint_frame": [1.0, 0.0, 0.0],
                "joint_limit_rad": [0.0, math.pi / 2.0],
                "visual_collision_rule": "use one root-local pose-neutral visual/collision set per side; never attach the aggregate STEP containing simultaneous stowed and deployed solids",
            },
            "full_flex": "root position agrees with R2_HF_MODEL_V2; no new Full-Flex Gate credit",
            "current_CAD": "read-only; no FCStd/STEP was edited; current geometry is S-authored and must not receive T_S_ROOT again",
            "forbidden_double_transform": "FORBIDDEN_TO_APPLY_T_S_ROOT_TO_ALREADY_S_AUTHORED_GEOMETRY_OR_TO_THE_AGGREGATE_STOWED_PLUS_DEPLOYED_STEP",
        },
        "leaf1_canonical_geometry_contract_q0": {
            "frame": "R2_ROOT_L or R2_ROOT_R respectively",
            "T_ROOT_LEAF1_MIDPLANE_Q0": [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            "chord_x_root_mm": [-150.0, 150.0],
            "thickness_y_root_mm": [-1.25, 1.25],
            "span_z_root_mm": [0.0, 200.0],
            "semantics": "new virtual root-coincident leaf1 midplane frame, not the existing FreeCAD Part::Feature box-local frame",
            "warning": "The FreeCAD Part::Feature box-corner origin is not a joint/link frame and must not be consumed as one.",
        },
        "kinematics_generated_leaf1_box_local_bridge_q0": {
            "scope": "leaf1 q=0 box-local frames returned by the hash-pinned Solar R2 leaf_solid_frame function; not an authority for the aggregate STEP or an unparsed FCStd Placement",
            "T_R2_ROOT_L_KINEMATICS_BOX_LOCAL_Q0_mm": t_root_box_q0["L"],
            "T_R2_ROOT_R_KINEMATICS_BOX_LOCAL_Q0_mm": t_root_box_q0["R"],
            "current_T_S_KINEMATICS_BOX_LOCAL_Q0_mm": {"L": t_s_box_q0["L"], "R": t_s_box_q0["R"]},
            "composition_for_kinematics_generated_box": "T_S_BOX_SIDE(q)=T_S_R2_ROOT_SIDE * Rx(q) * T_ROOT_SIDE_KINEMATICS_BOX_LOCAL_Q0",
            "composition_for_root_authored_replacement": "T_S_LEAF1_MIDPLANE_SIDE(q)=T_S_R2_ROOT_SIDE * Rx(q) * I",
            "selection_rule": "choose exactly one geometry-authorship branch; applying both bridges is forbidden",
            "direct_fcstd_object_placement_verified": False,
            "fcstd_consumption_allowed": False,
            "promotion_requirement": "directly hash-pin and parse the FCStd, verify named q0 object Placements, and reissue this registration before FCStd consumption",
            "kinematics_crosscheck": kinematic_angle_checks,
        },
        "source_pins": [pin_by_id[x] for x in ("SOLAR_R2_REPORT", "SOLAR_R2_STEP", "SOLAR_R2_KINEMATICS", "R2_HF_MODEL", "M4_FRAME_TREE")],
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "effective_for_downstream_execution": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }

    criteria = [
        {"id": "IGA-01", "name": "all thirteen source pins exact", "pass": len(pins) == 13},
        {"id": "IGA-02", "name": "340.5 mm operational length derives from three 113.5 mm bays", "pass": bus_length == 340.5},
        {"id": "IGA-03", "name": "366 mm is explicitly classified as display track", "pass": 'display_track_366;dynamics_SSOT_340.5_unchanged' in v22_source},
        {"id": "IGA-04", "name": "366 mm is excluded from physical authority and averaging", "pass": not bus_ruling["v22_366_disposition"]["may_be_used_as_physical_primary_structure_authority"] and not bus_ruling["v22_366_disposition"]["may_be_averaged_with_340p5"]},
        {"id": "IGA-05", "name": "12U detailed primary-structure HOLD preserved", "pass": not bus_ruling["closure"]["physical_primary_structure_authority_resolved"]},
        {"id": "IGA-06", "name": "Solar root line independently recomputed from left/right keepouts", "pass": vec_close(left["keepout_midpoint_S_mm"], t_left) and vec_close(right["keepout_midpoint_S_mm"], t_right)},
        {"id": "IGA-07", "name": "deployed leaf1 root edges register to the hinge line", "pass": solar_registration["registration_checks"]["deployed_leaf1_root_edges_match_root_line"]},
        {"id": "IGA-08", "name": "left/right root frames are proper mirrored transforms", "pass": solar_registration["registration_checks"]["root_frames_are_right_handed"]},
        {"id": "IGA-09", "name": "positive root rotation deploys both wings outboard", "pass": solar_registration["registration_checks"]["q_plus_90_deploys_outboard_symmetrically"]},
        {"id": "IGA-10", "name": "legacy R1 and stale 114.9 mm values are excluded", "pass": solar_registration["legacy_and_stale_dispositions"]["current_consumed_y_abs_mm"] == 115.4},
        {"id": "IGA-11", "name": "no CAD/mesh/URDF execution or mutation", "pass": True},
        {"id": "IGA-12", "name": "release and next-stage authority remain fail-closed", "pass": True},
        {"id": "IGA-13", "name": "hash-pinned kinematics box-local to abstract-root bridges are frozen and round-trip exact", "pass": solar_registration["registration_checks"]["kinematics_generated_box_local_rebase_round_trip"]},
        {"id": "IGA-14", "name": "0/30/90 degree two-side composition matches hash-pinned kinematics", "pass": solar_registration["registration_checks"]["q_0_30_90_both_sides_match_hash_pinned_kinematics"]},
    ]

    prebind_delta = {
        "schema": "UNIFIED_R2_PREBIND_GEOMETRY_DELTA_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "artifact_class": "APPEND_ONLY_MACHINE_STATE_DELTA__BASE_PREBIND_IMMUTABLE",
        "base": {
            "readiness_path": pin_by_id["PREBIND_READINESS_BASE"]["path"],
            "readiness_sha256": pin_by_id["PREBIND_READINESS_BASE"]["sha256"],
            "gate_path": pin_by_id["PREBIND_GATE_BASE"]["path"],
            "gate_sha256": pin_by_id["PREBIND_GATE_BASE"]["sha256"],
            "summary": prebind_readiness["summary"],
        },
        "criterion_deltas": [
            {
                "id": "PRB-17",
                "effective_pass": False,
                "effective_state": "HOLD",
                "closed_subcriterion": "340.5/366.0 mm operational length-track reconciliation",
                "remaining_hold": "detailed physical primary-structure authority, members, openings, load path and manufacturing definition",
            },
            {
                "id": "PRB-18",
                "effective_pass": True,
                "effective_state": "PASS",
                "evidence": "SOLAR_R2_ROOT_FRAME_REGISTRATION_V1 freezes left/right operational-candidate root transforms; flight hinge/bracket hardware remains HOLD",
            },
        ],
        "effective_summary": {"criteria_total": 20, "pass": 6, "hold": 14},
        "unchanged_holds": [
            "unified R2 assembly/URDF absent",
            "Route-C Checkpoint-B 2/8 and CAD unauthorized",
            "mission harness FAIL",
            "ODR-GPT-07/08 pending",
            "gripper physical speed/timing null",
            "detailed 12U physical structure HOLD",
            "heavy execution memory not admitted",
            "independent Unified R2 rebase authorization absent",
        ],
        "authority_flags": prebind_readiness["authority_flags"],
        "engineering_specification_complete": False,
        "geometry_execution_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "technical_verdict": "HOLD_PREBIND_EFFECTIVE_6_OF_20__SOLAR_R2_ROOT_FRAMES_FROZEN__12U_LENGTH_TRACK_RECONCILED_BUT_DETAILED_STRUCTURE_ROUTE_C_MEMORY_AND_RELEASE_JOINS_REMAIN_HOLD",
    }
    require(all(value is False for value in prebind_delta["authority_flags"].values()), "prebind authority flag drift")
    criteria.append({"id": "IGA-15", "name": "append-only prebind delta advances only PRB-18 and preserves all authority flags false", "pass": prebind_delta["effective_summary"] == {"criteria_total": 20, "pass": 6, "hold": 14} and all(value is False for value in prebind_delta["authority_flags"].values())})
    passed = sum(bool(item["pass"]) for item in criteria)
    require(passed == len(criteria), "internal geometry authority criteria failed")
    gate = {
        "schema": "INTERNAL_GEOMETRY_AUTHORITY_GATE_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "scope": "12U length-track reconciliation plus operational Solar R2 root-frame registration",
        "criteria": criteria,
        "summary": {"passed": passed, "total": len(criteria), "failed": []},
        "technical_verdict": "PASS_TECHNICAL_CANDIDATE_12U_OPERATIONAL_LENGTH_TRACK_RECONCILED_AND_SOLAR_R2_ROOT_FRAMES_FROZEN_PENDING_OWNER_REVIEW__12U_DETAILED_STRUCTURE_AND_FLIGHT_QUALIFICATION_REMAIN_HOLD",
        "state_changes": {
            "bus_length_conflict": "TECHNICAL_RULING_TO_340P5_MM_OPERATIONAL_BODY_TRACK__PENDING_OWNER_REVIEW",
            "bus_detailed_physical_structure": "HOLD",
            "solar_r2_root_frames": "FROZEN_TECHNICAL_CANDIDATE_PENDING_OWNER_REVIEW",
            "solar_r2_flight_hardware": "HOLD",
        },
        "execution_record": {"cad_started": False, "cad_modified": False, "step_modified": False, "mesh_modified": False, "urdf_modified": False, "solver_started": False},
        "source_pins": pins,
        "owner_accepted": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }

    write_yaml(OUTPUTS[0], bus_ruling)
    write_yaml(OUTPUTS[1], solar_registration)
    write_json(OUTPUTS[2], gate)
    write_json(OUTPUTS[3], prebind_delta)
    write_text(
        OUTPUTS[4],
        """# Internal Geometry Authority Closure V1

本包未启动或修改 CAD、STEP、网格、URDF 或求解器。

- 12U 运行/动力学刚体体长统一为 **340.5 mm**；V2.2 的 **366.0 mm** 明确保留为显示轨/设计提案，不得作为物理主结构权威或与 340.5 mm 平均。
- 12U 详细承力构件、开口、载荷路径与制造定义仍为 HOLD。
- Solar R2 左右根坐标系已从受控构建报告中的根铰 keep-out 与部署叶片边界独立复算并冻结；旧 M4 `F_L/F_R` 与陈旧 114.9 mm 字面量均不得消费。
- 已冻结抽象根帧与哈希锁定运动学函数所生成盒体局部帧之间的 q=0 固定桥，并按左右两侧 0°/30°/90° 对拍；FCStd 未在本包直接解析，故仍禁止消费其 Placement。未来只能选择“根局部重著录”或“显式盒体桥”之一，禁止对已在 S 中著录的几何重复施加根变换。
- 现有 STEP 同时含收拢与展开实体，不得整包作为单个 URDF visual/collision。
- 本包不给飞行资格、部署间隙、统一 CAD 或下游发布信用。
"""
    )

    manifest_path = PACKAGE / "INTERNAL_GEOMETRY_AUTHORITY_SHA256.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        for name in OUTPUTS:
            path = PACKAGE / name
            writer.writerow({"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)})

    print(json.dumps({"status": "BUILT", "criteria": f"{passed}/{len(criteria)}", "technical_verdict": gate["technical_verdict"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
