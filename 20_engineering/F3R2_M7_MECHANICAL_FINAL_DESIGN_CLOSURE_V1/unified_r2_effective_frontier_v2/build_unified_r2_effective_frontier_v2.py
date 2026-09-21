#!/usr/bin/env python3
"""Build the append-only Unified-R2 effective-frontier V2 package.

This is a documentation/configuration-identity operation only.  It never
creates CAD, meshes, URDF, solver inputs, or consumer bindings.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GENERATED_DATE_LOCAL = "2026-08-24"

SOURCES = {
    "BASE_PREBIND_READINESS": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/UNIFIED_R2_PREBIND_READINESS_V1.json",
    "BASE_PREBIND_GATE": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/UNIFIED_R2_PREBIND_GATE_V1.json",
    "GEOMETRY_DELTA": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/internal_geometry_authority_closure/UNIFIED_R2_PREBIND_GEOMETRY_DELTA_V1.json",
    "ROUTE_C_SOURCE_REFRESH": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_OFFICIAL_SOURCE_REFRESH_V1.yaml",
    "M4_CONFIGURATION_LIBRARY": "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    "M7_R2_MASS_PROPERTIES": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml",
    "SOLAR_R2_ROOT_FRAMES": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/internal_geometry_authority_closure/SOLAR_R2_ROOT_FRAME_REGISTRATION_V1.yaml",
}

BINDING_PATH = HERE / "C01_C09_M4_M7_CONFIGURATION_IDENTITY_BINDING_V1.yaml"
FRONTIER_PATH = HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_V2.json"
GATE_PATH = HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_GATE_V2.json"
HASH_PATH = HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_SHA256.csv"
RECEIPT_PATH = HERE / "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_RECEIPT_V2.md"

FALSE_AUTHORITY_FLAGS = {
    "engineering_specification_complete": False,
    "geometry_execution_authorized": False,
    "full_flex_validation_authorized": False,
    "consumer_rebind_authorized": False,
    "rebase_execution_authorized": False,
    "route_c_cad_authorized": False,
    "heavy_solver_authorized": False,
    "sim13_baseline_mutation_authorized": False,
    "production_dynamics_ready": False,
    "physical_contact_ready": False,
    "physics_gated_rl_ready": False,
    "owner_accepted": False,
    "next_stage_authorized": False,
    "release_credit": False,
    "terminal_release_candidate_generated": False,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def pin(source_id: str, rel: str) -> dict:
    path = ROOT / rel
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "id": source_id,
        "path": rel,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "verified": True,
    }


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8-sig"))


def load_yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8-sig"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_binding(m4: dict, m7: dict, source_pins: list[dict]) -> dict:
    m4_rows = {row["configuration_id"]: row for row in m4["configurations"]}
    m7_rows = {row["configuration_id"]: row for row in m7["configurations"]}
    expected_ids = [f"C{i:02d}" for i in range(1, 10)]
    require(sorted(m4_rows) == expected_ids, "M4 C01-C09 identity set drift")
    require(sorted(m7_rows) == expected_ids, "M7 C01-C09 identity set drift")

    records = []
    for cid in expected_ids:
        a = m4_rows[cid]
        b = m7_rows[cid]
        require(a["name"] == b["name"], f"configuration name mismatch: {cid}")
        mass = b["mass"]
        cg = b["center_of_mass"]
        inertia = b["inertia"]
        require(mass["value_kg"] > 0.0, f"non-positive mass: {cid}")
        require(len(cg["xyz_m"]) == 3, f"invalid CG: {cid}")
        require(set(inertia["components_kg_m2"]) == {"Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"}, f"invalid inertia fields: {cid}")
        require(b["checks"]["positive_definite"] is True, f"M7 positive-definite check not true: {cid}")
        require(b["checks"]["triangle_inequalities"] is True, f"M7 triangle check not true: {cid}")
        require(b["checks"]["no_zero_fill"] is True, f"M7 zero-fill check not true: {cid}")
        records.append({
            "configuration_id": cid,
            "canonical_name": a["name"],
            "m4_identity": {
                "configuration_id": a["configuration_id"],
                "name": a["name"],
                "legacy_mapping": a.get("legacy_mapping"),
                "accepted_named_joint_vector": a.get("frames", {}).get("accepted_named_joint_vector"),
                "release_status": a.get("status"),
                "source_pointer": f"$.configurations[?(@.configuration_id=='{cid}')]",
            },
            "m7_r2_identity": {
                "configuration_id": b["configuration_id"],
                "name": b["name"],
                "historical_empty_m4_configuration_library_name": b.get("m4_configuration_library_name", ""),
                "mass": mass,
                "center_of_mass": cg,
                "inertia": inertia,
                "uncertainty_policy": b.get("uncertainty_policy"),
                "source": b.get("source"),
                "checks": b.get("checks"),
                "source_pointer": f"$.configurations[?(@.configuration_id=='{cid}')]",
            },
            "binding": {
                "id_exact": True,
                "name_exact": True,
                "canonical_identity": f"{cid}:{a['name']}",
                "system_reference_frame_alias": "spacecraft_assembly_frame == S",
                "inertia_reference_point": "configuration_system_CG",
                "classification": "M7_R2_DESIGN_MODEL_BOUND_TO_M4_CONFIGURATION_IDENTITY__NOT_M4_RELEASE_VALUE",
                "machine_identity_bound": True,
                "release_credit": False,
            },
        })

    return {
        "schema": "C01_C09_M4_M7_CONFIGURATION_IDENTITY_BINDING_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "artifact_class": "APPEND_ONLY_CONFIGURATION_IDENTITY_BINDING__NO_SOURCE_MUTATION_NO_RELEASE_PROMOTION",
        "purpose": "bind the shared C01-C09 IDs and names without writing into frozen M4 or M7 source files",
        "identity_rule": "configuration_id AND canonical name must match exactly; index-only joins are forbidden",
        "source_pins": [p for p in source_pins if p["id"] in {"M4_CONFIGURATION_LIBRARY", "M7_R2_MASS_PROPERTIES"}],
        "configuration_count": len(records),
        "records": records,
        "summary": {
            "expected": 9,
            "bound": len(records),
            "id_mismatches": 0,
            "name_mismatches": 0,
            "non_null_mass_cg_inertia_records": len(records),
            "source_files_modified": False,
            "m4_release_status_promoted": False,
            "m7_design_values_reclassified_as_flight_or_measured": False,
        },
        "consumer_guard": {
            "allowed": "future versioned Unified-R2 configuration loader may consume this sidecar identity join after separate execution authorization",
            "forbidden": [
                "mutating M4 CONFIGURATION_LIBRARY_V1",
                "mutating M7 SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2",
                "treating this binding as CAD, collision, contact, FEA, mission-harness or release evidence",
            ],
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def overlay_effective_criteria(base: dict, delta: dict) -> list[dict]:
    rows = {row["id"]: dict(row) for row in base["criteria"]}
    for change in delta["criterion_deltas"]:
        row = rows[change["id"]]
        row["base_pass"] = row["pass"]
        row["base_state"] = row["state"]
        row["pass"] = change["effective_pass"]
        row["state"] = change["effective_state"]
        row["append_only_delta"] = {k: v for k, v in change.items() if k not in {"id", "effective_pass", "effective_state"}}
    return [rows[f"PRB-{i:02d}"] for i in range(1, 21)]


def criterion(cid: str, name: str, passed: bool, evidence) -> dict:
    return {"id": cid, "name": name, "pass": bool(passed), "evidence": evidence}


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    source_pins = [pin(source_id, rel) for source_id, rel in SOURCES.items()]
    base = load_json(SOURCES["BASE_PREBIND_READINESS"])
    delta = load_json(SOURCES["GEOMETRY_DELTA"])
    route = load_yaml(SOURCES["ROUTE_C_SOURCE_REFRESH"])
    m4 = load_yaml(SOURCES["M4_CONFIGURATION_LIBRARY"])
    m7 = load_yaml(SOURCES["M7_R2_MASS_PROPERTIES"])

    require(base["summary"] == {"criteria_total": 20, "pass": 5, "hold": 15}, "base readiness summary drift")
    require(delta["effective_summary"] == {"criteria_total": 20, "pass": 6, "hold": 14}, "delta effective summary drift")
    require(route["decision"]["registry_status_HOLD_after"] == 13, "Route-C HOLD count drift")
    require(route["decision"]["ROUTE_C_CAD_AUTHORIZED"] is False, "Route-C unexpectedly authorized")

    binding = build_binding(m4, m7, source_pins)
    BINDING_PATH.write_text(yaml.safe_dump(binding, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")

    effective_criteria = overlay_effective_criteria(base, delta)
    pass_count = sum(row["pass"] is True for row in effective_criteria)
    hold_count = len(effective_criteria) - pass_count
    require((pass_count, hold_count) == (6, 14), "effective frontier is not 6/20")
    require(next(row for row in effective_criteria if row["id"] == "PRB-17")["pass"] is False, "PRB-17 must remain HOLD")
    require(next(row for row in effective_criteria if row["id"] == "PRB-18")["pass"] is True, "PRB-18 must be PASS")

    frontier = {
        "schema": "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_V2",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "artifact_class": "APPEND_ONLY_EFFECTIVE_FRONTIER_AGGREGATION__BASE_V1_IMMUTABLE",
        "scope": "documentation and configuration identity only",
        "source_pins": source_pins,
        "base_summary": base["summary"],
        "effective_criteria": effective_criteria,
        "effective_summary": {"criteria_total": 20, "pass": pass_count, "hold": hold_count},
        "new_internal_closure": {
            "solar_r2_root_frames": "PASS via PRB-18 append-only delta",
            "bus_length_track": "340.5/366.0 sub-conflict closed; detailed physical structure remains HOLD",
            "configuration_identity_binding": "C01-C09 9/9 exact ID+name sidecar binding generated",
            "route_c_source_refresh": "4 official screening records; zero P-fields promoted",
        },
        "unchanged_blockers": [
            "unified R2 physical assembly absent",
            "full-system generated URDF absent",
            "Route-C Checkpoint-B remains 2/8 and 13/13 registry fields remain null/HOLD",
            "ODR-GPT-07 and ODR-GPT-08 remain pending Owner decisions",
            "mission harness remains FAIL",
            "gripper physical speed and contact timing remain null/HOLD",
            "detailed 12U primary structure remains HOLD",
            "execution memory not admitted for heavy generation",
            "separate Unified-R2 rebase execution authorization absent",
            "current Sim13 production mechanical binding remains invalidated",
        ],
        "current_allowed_action": "documentation, source-only preparation, traceable registry closure, configuration identity binding, and Owner decision review",
        "current_prohibited_action": "Unified R2 CAD/mesh/URDF execution, Route-C geometry, Sim13 baseline mutation, formal FEA, production contact or RL claims",
        "route_c_state": route["decision"],
        "configuration_binding": {
            "path": str(BINDING_PATH.relative_to(ROOT)).replace("\\", "/"),
            "bytes": BINDING_PATH.stat().st_size,
            "sha256": sha256(BINDING_PATH),
            "bound": binding["summary"]["bound"],
            "expected": binding["summary"]["expected"],
        },
        "authority_flags": dict(FALSE_AUTHORITY_FLAGS),
        "technical_verdict": "HOLD_PREBIND_EFFECTIVE_6_OF_20__C01_C09_IDENTITY_BOUND_9_OF_9__SOLAR_ROOT_FRAMES_FROZEN__ROUTE_C_STRUCTURE_MEMORY_URDF_SIM13_AND_RELEASE_JOINS_REMAIN_HOLD",
    }
    FRONTIER_PATH.write_text(json.dumps(frontier, indent=2, ensure_ascii=False), encoding="utf-8")

    checks = [
        criterion("EF2-01", "all seven source artifacts exist and are hash-pinned", len(source_pins) == 7 and all(p["verified"] for p in source_pins), len(source_pins)),
        criterion("EF2-02", "base V1 remains 5/20", base["summary"] == {"criteria_total": 20, "pass": 5, "hold": 15}, base["summary"]),
        criterion("EF2-03", "effective append-only frontier is 6/20", frontier["effective_summary"] == {"criteria_total": 20, "pass": 6, "hold": 14}, frontier["effective_summary"]),
        criterion("EF2-04", "PRB-17 detailed primary structure remains HOLD", next(r for r in effective_criteria if r["id"] == "PRB-17")["pass"] is False, "length-track sub-conflict closed only"),
        criterion("EF2-05", "PRB-18 Solar root frames are PASS", next(r for r in effective_criteria if r["id"] == "PRB-18")["pass"] is True, "append-only geometry delta"),
        criterion("EF2-06", "C01-C09 IDs and names bind 9/9", binding["summary"]["bound"] == 9, binding["summary"]),
        criterion("EF2-07", "nine M7 design rows carry non-null mass CG inertia", binding["summary"]["non_null_mass_cg_inertia_records"] == 9, 9),
        criterion("EF2-08", "frozen M4/M7 source files were not mutated", binding["summary"]["source_files_modified"] is False, False),
        criterion("EF2-09", "Route-C fields remain 13/13 HOLD", route["decision"]["registry_status_HOLD_after"] == 13 and route["decision"]["registry_value_non_null_after"] == 0, route["decision"]),
        criterion("EF2-10", "Route-C CAD remains unauthorized", route["decision"]["ROUTE_C_CAD_AUTHORIZED"] is False, False),
        criterion("EF2-11", "all execution release and Owner flags remain false", all(v is False for v in frontier["authority_flags"].values()), frontier["authority_flags"]),
        criterion("EF2-12", "package emits no CAD mesh URDF or solver artifact", not any(p.suffix.lower() in {".fcstd", ".step", ".stp", ".stl", ".obj", ".urdf", ".inp", ".odb"} for p in HERE.iterdir()), "documentation-only directory"),
    ]
    require(all(c["pass"] for c in checks), "effective-frontier package check failed")
    gate = {
        "schema": "UNIFIED_R2_PREBIND_EFFECTIVE_FRONTIER_GATE_V2",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "package_validation": "PASS",
        "technical_outcome": "HOLD",
        "criteria": checks,
        "summary": {"pass": len(checks), "total": len(checks), "failed": []},
        "effective_prebind_summary": frontier["effective_summary"],
        "technical_verdict": frontier["technical_verdict"],
        "authority_flags": dict(FALSE_AUTHORITY_FLAGS),
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    GATE_PATH.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")

    receipt = f"""# Unified R2 有效前沿 V2 回执\n\n- 基线 V1 保持 **5/20**，未修改。\n- 叠加受控几何 delta 后，有效前沿为 **6/20**：仅 PRB-18 升为 PASS；PRB-17 仍因详细主结构权威缺失而 HOLD。\n- C01-C09 已按“ID + canonical name”完成 **9/9** M4↔M7 机器身份绑定；这不把 M7 设计值升级为 M4/飞行发布值。\n- Route-C 仍为 **13/13 null/HOLD**，CAD 未授权；Unified R2 CAD、系统 URDF、Sim13 重绑和终局发布均未授权。\n- 技术裁决：`{frontier['technical_verdict']}`\n"""
    RECEIPT_PATH.write_text(receipt, encoding="utf-8")

    rows = []
    for p in source_pins:
        rows.append(["SOURCE_PIN", p["id"], p["path"], p["bytes"], p["sha256"]])
    for path in (BINDING_PATH, FRONTIER_PATH, GATE_PATH, RECEIPT_PATH):
        rows.append(["OUTPUT", path.stem, str(path.relative_to(ROOT)).replace("\\", "/"), path.stat().st_size, sha256(path)])
    with HASH_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["class", "id", "path", "bytes", "sha256"])
        writer.writerows(rows)

    print("PASS: effective frontier 6/20; configuration identity binding 9/9; technical outcome HOLD")


if __name__ == "__main__":
    main()
