#!/usr/bin/env python3
"""Issue Solar-R2 V3 source/metadata errata without regenerating CAD."""

from __future__ import annotations

import csv
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
SOLAR_DIR = HERE.parent
ROOT = HERE.parents[3]
DATE = "2026-08-24"

REPORT = HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V3.json"
REPORT_MD = HERE / "SOLAR_ARRAY_R2_BUILD_REPORT_V3.md"
GEOM = HERE / "SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3.yaml"
HDRM = HERE / "SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V3.yaml"
ERRATA = HERE / "SOLAR_ARRAY_R2_GENERATION_CHAIN_ERRATA_V3.yaml"
GATE = HERE / "SOLAR_ARRAY_R2_V3_REISSUE_GATE.json"
HASHES = HERE / "SOLAR_ARRAY_R2_V3_REISSUE_SHA256.csv"

SOURCE_REL = {
    "FROZEN_FCSTD": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd",
    "FROZEN_STEP": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step",
    "BUILD_REPORT_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V1.json",
    "BUILD_REPORT_V2": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V2.json",
    "GEOMETRY_YAML_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V1.yaml",
    "HDRM_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml",
    "KINEMATICS_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/solar_array_r2_kinematics.py",
    "BUILDER_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/build_solar_array_r2.py",
    "SWEEP_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/sweep_solar_array_r2_clearance.py",
    "HARNESS_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/build_harness_r2_gates.py",
    "FLEX_SOURCE_V1": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/compute_flexible_appendage_r2.py",
    "ROOT_FRAME_REGISTRATION": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/internal_geometry_authority_closure/SOLAR_R2_ROOT_FRAME_REGISTRATION_V1.yaml",
}

NEW_SOURCE_NAMES = [
    "solar_array_r2_kinematics_v3.py",
    "build_solar_array_r2_v3.py",
    "sweep_solar_array_r2_clearance_v3.py",
    "build_harness_r2_gates_v3.py",
    "compute_flexible_appendage_r2_v3.py",
    "source_execution_guard.py",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def pin(source_id: str, path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "id": source_id,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "verified": True,
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def states_55() -> list[tuple[float, float, float]]:
    states = [(float(v), 0.0, 0.0) for v in range(0, 91, 5)]
    states += [(90.0, float(v), 0.0) for v in range(10, 181, 10)]
    states += [(90.0, 180.0, float(v)) for v in range(10, 181, 10)]
    return states


def numeric_equal(a, b, tol=1.0e-12) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= tol
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(numeric_equal(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(numeric_equal(x, y, tol) for x, y in zip(a, b))
    return a == b


def compare_kinematics() -> dict:
    old = load_module("solar_array_r2_kinematics_frozen_v1", ROOT / SOURCE_REL["KINEMATICS_V1"])
    new = load_module("solar_array_r2_kinematics_source_v3", HERE / "solar_array_r2_kinematics_v3.py")
    mismatches = []
    for state in states_55():
        for side in (+1, -1):
            old_leaves = old.leaf_segments(side, *state)
            new_leaves = new.leaf_segments(side, *state)
            if not numeric_equal(old_leaves, new_leaves):
                mismatches.append({"state": state, "side": side, "field": "leaf_segments"})
                continue
            for index, (a, b) in enumerate(zip(old_leaves, new_leaves), start=1):
                if not numeric_equal(old.leaf_solid_frame(side, a), new.leaf_solid_frame(side, b)):
                    mismatches.append({"state": state, "side": side, "leaf": index, "field": "leaf_solid_frame"})
    metrics_equal = numeric_equal(old.stowed_stack_metrics(), new.stowed_stack_metrics())
    return {
        "states_compared": 55,
        "sides_per_state": 2,
        "leaf_frames_per_side": 3,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "stack_metrics_equal": metrics_equal,
        "old_leaf1_mid_y_mm": old.LEAF1_MID_Y,
        "new_leaf1_mid_y_mm": new.LEAF1_MID_Y,
        "numerically_identical": len(mismatches) == 0 and metrics_equal,
    }


def main() -> None:
    source_pins = [pin(key, ROOT / rel) for key, rel in SOURCE_REL.items()]
    source_pins += [pin(f"V3_SOURCE_{name.upper().replace('.', '_')}", HERE / name) for name in NEW_SOURCE_NAMES]
    v2_path = ROOT / SOURCE_REL["BUILD_REPORT_V2"]
    v2 = json.loads(v2_path.read_text(encoding="utf-8-sig"))
    fcstd = ROOT / SOURCE_REL["FROZEN_FCSTD"]
    step = ROOT / SOURCE_REL["FROZEN_STEP"]
    require(sha256(fcstd) == "9D4D249A5D4EED7BDD8F3C08EC96737884A19523782112B1E72AD9EA0A1B65AB", "frozen FCStd hash drift")
    require(sha256(step) == "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795", "frozen STEP hash drift")
    require(v2["parameters"]["root_hinge_line"]["y_abs_mm"] == 115.4, "V2 physical root line drift")

    v3 = copy.deepcopy(v2)
    v3.update({
        "schema": "SOLAR_ARRAY_R2_BUILD_REPORT_V3",
        "generated_local": "2026-08-24T00:00:00+08:00",
        "generator": "Codex Solar-R2 V3 source/metadata reissue; no CAD regeneration",
        "authority": "append-only errata under frozen Solar R2 V1 geometry and SOLAR_R2_ROOT_FRAME_REGISTRATION_V1",
        "supersedes": "SOLAR_ARRAY_R2_BUILD_REPORT_V2 metadata only; V1 FCStd/STEP remain the frozen geometry",
        "cad_regenerated": False,
        "visible_geometry_changed": False,
        "geometry_payload_changed": False,
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED",
        "report_self_sha256": None,
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "effective_for_downstream_execution": False,
        "next_stage_authorized": False,
        "release_credit": False,
    })
    protrusion = float(v3["stack_metrics"]["protrusion_beyond_side_face_mm"])
    require(abs(protrusion - 9.5) <= 1.0e-12, "computed protrusion is not 9.5 mm")
    v3["protrusion_note"] = (
        f"{protrusion:.1f} mm operational protrusion beyond the 226.3 mm bus side face; "
        "MODE_OP engineering candidate retained. MODE_FLIGHT remains HOLD pending the actual dispenser ICD."
    )
    v3["parameters"]["root_hinge_line"] = {"y_abs_mm": 115.4, "z_mm": -108.15}
    v3["hashes"] = {
        "SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd": sha256(fcstd),
        "SOLAR_ARRAY_R2_CANDIDATE_V1.step": sha256(step),
    }
    v3["outputs"] = {
        "metadata_report": REPORT.name,
        "geometry_registration": GEOM.name,
        "hdrm_registration": HDRM.name,
        "generation_chain_errata": ERRATA.name,
        "cad_outputs": None,
    }
    v3["v3_reissue_proof"] = {
        "shape_metrics_identical_to_v2": v3["shape_metrics"] == v2["shape_metrics"],
        "clearance_pairs_identical_to_v2": v3["clearance_pairs"] == v2["clearance_pairs"],
        "mass_model_identical_to_v2": v3["mass_model_candidate"] == v2["mass_model_candidate"],
        "cad_pins_identical_to_v2": v3["hashes"] == {k: v2["hashes"][k] for k in v3["hashes"]},
        "permitted_changes": ["schema/provenance", "root-line registration text", "9.5 mm protrusion text", "source-chain errata and fail-closed footer"],
    }
    REPORT.write_text(json.dumps(v3, indent=2, ensure_ascii=False), encoding="utf-8")

    geometry = {
        "schema": "SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3",
        "generated_date_local": DATE,
        "artifact_class": "SOURCE_AND_METADATA_REISSUE__FROZEN_V1_CAD_REUSED_BYTE_EXACT",
        "architecture": {
            "wings": 2,
            "leaves_per_wing": 3,
            "leaf_planform_mm": [300.0, 200.0],
            "leaf_thickness_mm": 2.5,
            "hinge_axes": "X_S",
        },
        "geometry_facts": {
            "root_hinge_line": {"y_abs_mm": 115.4, "z_mm": -108.15, "axis": "X_S"},
            "stack_height_mm": v3["stack_metrics"]["stack_height_mm"],
            "protrusion_beyond_side_face_mm": protrusion,
            "deployed_tip_to_tip_mm": v3["stack_metrics"]["deployed_tip_to_tip_mm"],
        },
        "frozen_geometry_binding": {
            "fcstd_path": SOURCE_REL["FROZEN_FCSTD"],
            "fcstd_sha256": sha256(fcstd),
            "step_path": SOURCE_REL["FROZEN_STEP"],
            "step_sha256": sha256(step),
        },
        "cad_regenerated": False,
        "visible_geometry_changed": False,
        "future_geometry_regeneration_source": "build_solar_array_r2_v3.py",
        "future_execution_authorized": False,
        "holds": [
            "MODE_FLIGHT_PROTRUSION_HOLD_PENDING_DISPENSER_ICD",
            "ROOT_BRACKET_AND_HINGE_HARDWARE_DETAIL_HOLD",
            "UNIFIED_R2_CONTINUOUS_CLEARANCE_RELEASE_HOLD",
        ],
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    GEOM.write_text(yaml.safe_dump(geometry, sort_keys=False, allow_unicode=True), encoding="utf-8")

    h1 = yaml.safe_load((ROOT / SOURCE_REL["HDRM_V1"]).read_text(encoding="utf-8-sig"))
    h3 = copy.deepcopy(h1)
    h3["schema"] = "SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V3"
    h3["generated_date_local"] = DATE
    h3["supersedes"] = "V1 registration text only; no hardware selection or geometry promotion"
    architecture = h3.get("architecture", {})
    architecture.setdefault("per_wing", {})["root_hinge"] = "1 per wing (axis parallel X_S, line y=+/-115.4 mm, z=-108.15 mm)"
    h3["architecture"] = architecture
    h3["cad_regenerated"] = False
    h3["visible_geometry_changed"] = False
    h3["review_status"] = "PENDING_OWNER_REVIEW"
    h3["owner_accepted"] = False
    h3["next_stage_authorized"] = False
    h3["release_credit"] = False
    HDRM.write_text(yaml.safe_dump(h3, sort_keys=False, allow_unicode=True), encoding="utf-8")

    errata = {
        "schema": "SOLAR_ARRAY_R2_GENERATION_CHAIN_ERRATA_V3",
        "generated_date_local": DATE,
        "artifact_class": "APPEND_ONLY_ERRATA__FROZEN_PREDECESSORS_IMMUTABLE",
        "current_operational_values": {
            "root_hinge_y_abs_mm": 115.4,
            "root_hinge_z_mm": -108.15,
            "hinge_axis": "X_S",
            "operational_protrusion_mm": 9.5,
        },
        "rejected_historical": [
            {"value": "114.9 mm", "locations": ["V1 geometry YAML", "V1 builder emitted literal", "V1 HDRM registration"], "disposition": "REJECTED_STALE_REGISTRATION__DO_NOT_EDIT_FROZEN_FILES"},
            {"value": "0.1149 m", "locations": ["legacy flexible source and superseded HF contexts"], "disposition": "REJECTED_FOR_NEW_COUPLED_GEOMETRY__HISTORICAL_EVIDENCE_RETAINED"},
            {"value": "9.0 mm", "locations": ["V1/V2 protrusion prose"], "disposition": "REJECTED_STALE_TEXT__STACK_METRICS_AND_FROZEN_GEOMETRY_EQUAL_9.5_MM"},
        ],
        "source_reissue": {
            "files": NEW_SOURCE_NAMES,
            "execution_guard": "SOLAR_R2_V3_EXECUTION_AUTHORIZATION.json absent; every executable source fails closed",
            "generation_performed": False,
            "cad_regenerated": False,
            "visible_geometry_changed": False,
        },
        "frozen_assets_modified": False,
        "effective_for_downstream_execution": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    ERRATA.write_text(yaml.safe_dump(errata, sort_keys=False, allow_unicode=True), encoding="utf-8")

    kin = compare_kinematics()
    checks = [
        {"id": "SR3-01", "name": "frozen FCStd hash unchanged", "pass": sha256(fcstd) == v3["hashes"][fcstd.name], "evidence": sha256(fcstd)},
        {"id": "SR3-02", "name": "frozen STEP hash unchanged", "pass": sha256(step) == v3["hashes"][step.name], "evidence": sha256(step)},
        {"id": "SR3-03", "name": "root arithmetic is 115.4 mm", "pass": abs((113.15 + 1.0 + 2.5 / 2.0) - 115.4) <= 1.0e-12, "evidence": 115.4},
        {"id": "SR3-04", "name": "V3 report geometry and HDRM register 115.4/-108.15/X_S", "pass": geometry["geometry_facts"]["root_hinge_line"] == {"y_abs_mm": 115.4, "z_mm": -108.15, "axis": "X_S"} and "115.4" in h3["architecture"]["per_wing"]["root_hinge"], "evidence": geometry["geometry_facts"]["root_hinge_line"]},
        {"id": "SR3-05", "name": "operational protrusion is 9.5 mm", "pass": protrusion == 9.5 and "9.5 mm" in v3["protrusion_note"], "evidence": protrusion},
        {"id": "SR3-06", "name": "V1 and V3 kinematics are numerically identical at 55 states", "pass": kin["numerically_identical"], "evidence": kin},
        {"id": "SR3-07", "name": "V2 shape clearance and mass payloads are unchanged", "pass": all(v3["v3_reissue_proof"][k] for k in ("shape_metrics_identical_to_v2", "clearance_pairs_identical_to_v2", "mass_model_identical_to_v2", "cad_pins_identical_to_v2")), "evidence": v3["v3_reissue_proof"]},
        {"id": "SR3-08", "name": "no CAD was regenerated", "pass": v3["cad_regenerated"] is False and v3["visible_geometry_changed"] is False, "evidence": {"cad_regenerated": False, "visible_geometry_changed": False}},
        {"id": "SR3-09", "name": "V3 report excludes self hash", "pass": REPORT.name not in v3["hashes"] and v3["self_hash_policy"] == "SELF_REFERENCE_EXCLUDED", "evidence": v3["hashes"]},
        {"id": "SR3-10", "name": "all six dormant V3 sources exist", "pass": all((HERE / name).is_file() for name in NEW_SOURCE_NAMES), "evidence": NEW_SOURCE_NAMES},
        {"id": "SR3-11", "name": "no V3 CAD output exists", "pass": not (HERE / "SOLAR_ARRAY_R2_CANDIDATE_V3.step").exists() and not (HERE / "SOLAR_ARRAY_R2_CANDIDATE_V3.FCStd").exists(), "evidence": "source/metadata only"},
        {"id": "SR3-12", "name": "all execution release and Owner fields remain false", "pass": all(v3[k] is False for k in ("cad_regenerated", "visible_geometry_changed", "effective_for_downstream_execution", "owner_accepted", "next_stage_authorized", "release_credit")), "evidence": "fail-closed"},
    ]
    require(all(row["pass"] for row in checks), "Solar R2 V3 reissue Gate failed")
    gate = {
        "schema": "SOLAR_ARRAY_R2_V3_REISSUE_GATE",
        "generated_date_local": DATE,
        "package_validation": "PASS",
        "technical_outcome": "PASS_SOURCE_AND_METADATA_REISSUE_ONLY__CAD_NOT_REGENERATED",
        "criteria": checks,
        "summary": {"pass": len(checks), "total": len(checks), "failed": []},
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "effective_for_downstream_execution": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    GATE.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")

    REPORT_MD.write_text(
        "# Solar R2 V3 源与元数据重发回执\n\n"
        "- 冻结 V1 FCStd/STEP 未修改、未重生；V3 继续钉住原字节哈希。\n"
        "- 根铰线登记统一为 `y=±115.4 mm, z=-108.15 mm, axis=X_S`。\n"
        "- MODE_OP 突出量文本统一为 `9.5 mm`；MODE_FLIGHT 仍 HOLD。\n"
        "- V1↔V3 运动学已在 55 个状态、左右翼及全部叶片局部框架上数值对拍。\n"
        "- 六个 V3 执行源均为休眠源；缺少单独运行授权和内存准入时 fail-closed。\n"
        "- 本包不授予 Unified R2 CAD、URDF、Sim13、接触、FEA 或发布权限。\n",
        encoding="utf-8",
    )

    rows = []
    for item in source_pins:
        rows.append(["SOURCE_PIN", item["id"], item["path"], item["bytes"], item["sha256"]])
    for path in (REPORT, REPORT_MD, GEOM, HDRM, ERRATA, GATE):
        rows.append(["OUTPUT", path.stem, str(path.relative_to(ROOT)).replace("\\", "/"), path.stat().st_size, sha256(path)])
    with HASHES.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["class", "id", "path", "bytes", "sha256"])
        writer.writerows(rows)
    print("PASS: Solar R2 V3 source/metadata reissue 12/12; CAD not regenerated")


if __name__ == "__main__":
    main()
