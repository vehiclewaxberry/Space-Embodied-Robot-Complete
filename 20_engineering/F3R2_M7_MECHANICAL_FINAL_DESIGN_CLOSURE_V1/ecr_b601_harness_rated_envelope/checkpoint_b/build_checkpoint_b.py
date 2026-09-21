"""Build the fail-closed CHECKPOINT-B Route-C C2 admission package.

CHECKPOINT-B is reached when the admission state has been evaluated from
hash-pinned evidence.  Reaching the checkpoint is not a PASS, CAD authority,
Owner acceptance, next-stage authorization, or release credit.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]

PATHS = {
    "owner_directives": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR_GPT_01_TO_06_TERMINAL_CLOSURE_V1.yaml",
    "mpi_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json",
    "route_b_negative": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V2.json",
    "route_c_registry": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml",
    "route_c_admission": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_C2_ADMISSION_GATE_V1.yaml",
    "rfi_efg_issuance": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/route_c_prep/ROUTE_C_RFI_EFG_ISSUANCE_V1.yaml",
    "product_input_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/ROUTE_C_PRODUCT_INPUT_GATE_V1.json",
    "vendor_rfi_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json",
    "mpi_evidence_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit/ROUTE_C_MPI_EVIDENCE_GATE_V1.json",
    "precad_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/02_pre_cad_parametric_guided_route_search/03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json",
    "mission_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json",
}

ROUTE_C_ROOT = PROJECT_ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c"
CAD_SUFFIXES = {".fcstd", ".step", ".stp", ".stl", ".glb", ".obj", ".iges", ".igs"}


def full(relative: str) -> Path:
    return PROJECT_ROOT / relative


def sha256(path_or_relative: str | Path) -> str:
    path = full(path_or_relative) if isinstance(path_or_relative, str) else path_or_relative
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read_json(key: str) -> dict[str, Any]:
    return json.loads(full(PATHS[key]).read_text(encoding="utf-8"))


def read_yaml(key: str) -> dict[str, Any]:
    return yaml.safe_load(full(PATHS[key]).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"CHECKPOINT_B_FAIL_CLOSED: {message}")


def pin(relative: str, role: str) -> dict[str, Any]:
    path = full(relative)
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "role": role,
    }


def main() -> None:
    for key, relative in PATHS.items():
        require(full(relative).is_file(), f"missing required input {key}: {relative}")

    owner = read_yaml("owner_directives")
    mpi = read_json("mpi_gate")
    route_b = read_json("route_b_negative")
    registry = read_yaml("route_c_registry")
    admission = read_yaml("route_c_admission")
    rfi = read_yaml("rfi_efg_issuance")
    product = read_json("product_input_gate")
    vendor = read_json("vendor_rfi_gate")
    mpi_evidence = read_json("mpi_evidence_gate")
    precad = read_json("precad_gate")
    mission = read_json("mission_gate")

    directives = {item["id"]: item for item in owner["directives"]}
    require(directives["ODR-GPT-03"]["recorded_effect"]["route_c_cad_authorized"] is False,
            "ODR-GPT-03 no longer holds Route-C CAD false")
    require(directives["ODR-GPT-03"]["recorded_effect"]["current_registry_evidence"]
            ["required_fields"] == 13, "ODR-GPT-03 required field count changed")
    require(directives["ODR-GPT-04"]["condition_evaluation"]["result"] == "NOT_SATISFIED",
            "ODR-GPT-04 mission-defer condition unexpectedly changed")
    require(mpi["mpi_gate"] == "PASS" and mpi["criterion_counts"] == {"total": 9, "pass": 9, "fail": 0},
            "MPI bridge is not confirmed by a 9/9 machine Gate")
    require(all(float(mpi["bottom_line_metrics"][name]) == 0.0 for name in
                ("frame_ambiguity", "mass_inconsistency", "inertia_inconsistency",
                 "consumer_ambiguity", "hash_mismatch")), "MPI bottom-line metric is nonzero")

    entries = registry["registry_entries"]
    require(len(entries) == 13 and registry["summary"]["entries_total"] == 13,
            "C2 registry is not exactly 13 entries")
    require(all(item["value"] is None for item in entries), "a C2 value changed from null")
    require(all(item["status"] == "HOLD" for item in entries), "a C2 entry is not HOLD")
    require(registry["summary"]["value_non_null"] == 0 and
            registry["summary"]["status_AVAILABLE"] == 0 and
            registry["summary"]["status_HOLD"] == 13,
            "C2 summary is not 0 non-null / 0 AVAILABLE / 13 HOLD")
    require(registry["summary"]["fabricated_values"] == 0 and
            registry["summary"]["null_coercions"] == 0 and
            registry["summary"]["selections_made"] == 0,
            "registry integrity guard changed")

    tally = admission["current_evaluation"]["tally"]
    require(tally["conditions_total"] == 8 and tally["pass"] == 2 and tally["fail"] == 6,
            "C2 admission is not the verified 2/8 state")
    require(admission["current_evaluation"]["ROUTE_C_CAD_AUTHORIZED"] is False and
            admission["current_evaluation"]["next_stage_authorized"] is False,
            "C2 admission unexpectedly authorizes CAD or next stage")

    rfi_ids = [item["rfi_id"] for item in rfi["rfi_blocks"]]
    require(rfi["status"] == "ISSUED_PER_ODR46" and rfi_ids == ["RFI-E", "RFI-F", "RFI-G"],
            "RFI-E/F/G issuance record changed")
    require(all(item["state"] == "ISSUED__NO_RESPONSE_RECEIVED" for item in rfi["rfi_blocks"]),
            "an RFI response exists but is not yet registered through a new version")
    require(rfi["issuance_record"]["responses_received"] == 0 and
            rfi["issuance_record"]["values_filled_into_c2_01_registry"] == 0 and
            rfi["issuance_record"]["fields_upgraded_null_to_candidate_range"] == 0,
            "RFI response/value count changed")

    require(product["gate"] == "HOLD" and product["criteria_controlled"] == 0 and
            product["criteria_total"] == 8 and product["next_stage_authorized"] is False,
            "minimum product input Gate changed")
    require(vendor["gate"] == "HOLD" and vendor["candidate_routes"]["selected_routes"] == 0 and
            vendor["next_stage_authorized"] is False, "vendor RFI Gate changed")
    require(mpi_evidence["gate"] == "HOLD" and mpi_evidence["criteria_controlled"] == 0 and
            mpi_evidence["criteria_total"] == 8 and mpi_evidence["cad_generation_authorized"] is False,
            "Route-C physical-input MPI evidence Gate changed")
    require(precad["gate"] == "UNKNOWN_FAIL_CLOSED" and precad["candidate_found"] is False and
            precad["cad_entry_authorized"] is False and
            precad["predicate_qualification"]["tests_passed"] == 47 and
            precad["predicate_qualification"]["tests_total"] == 47 and
            precad["predicate_qualification"]["grants_design_authority"] is False,
            "pre-CAD diagnostic state changed")
    require(mission["mission_coverage"] == "FAIL" and
            sum(bool(item["pass"]) for item in mission["key_state_checks"]) == 0 and
            len(mission["key_state_checks"]) == 10,
            "mandatory mission coverage state changed")
    require(route_b["verdict"]["B601_HARNESS_FUNCTIONAL_GATE"] == "FAIL",
            "Route-B exact negative result changed")

    cad_assets = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in ROUTE_C_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in CAD_SUFFIXES
    )
    require(not cad_assets, f"unauthorized Route-C CAD assets found: {cad_assets}")

    rfi_by_field = {
        target["id"]: block["rfi_id"]
        for block in rfi["rfi_blocks"]
        for target in block["targets_fields"]
    }
    matrix_rows: list[dict[str, Any]] = []
    for item in entries:
        source = item.get("candidate_source_or_null")
        matrix_rows.append({
            "id": item["id"],
            "quantity": item["quantity"],
            "unit": item.get("unit"),
            "value": "" if item["value"] is None else item["value"],
            "value_uncertainty": "" if item.get("value_uncertainty") is None else item["value_uncertainty"],
            "status": item["status"],
            "candidate_source_present": str(source is not None).lower(),
            "candidate_source_is_authority": "false",
            "assigned_rfi": rfi_by_field.get(item["id"], "NONE_DIRECT"),
            "acceptable_source_classes": "|".join(item.get("acceptable_source_classes", [])),
            "next_required_evidence": item["required_evidence"],
        })

    matrix_path = HERE / "CHECKPOINT_B_PHYSICAL_INPUT_MATRIX_V1.csv"
    with matrix_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix_rows[0]))
        writer.writeheader()
        writer.writerows(matrix_rows)

    evidence_pins = [
        pin(PATHS["owner_directives"], "CURRENT_DIRECT_OWNER_DIRECTIVES"),
        pin(PATHS["mpi_gate"], "CONFIRMED_MPI_BRIDGE_GATE"),
        pin(PATHS["route_b_negative"], "FROZEN_ROUTE_B_NEGATIVE_RESULT"),
        pin(PATHS["route_c_registry"], "C2_PHYSICAL_REGISTRY"),
        pin(PATHS["route_c_admission"], "C2_ADMISSION_SOURCE_GATE"),
        pin(PATHS["rfi_efg_issuance"], "RFI_EFG_ISSUANCE_RECORD"),
        pin(PATHS["product_input_gate"], "MINIMUM_PRODUCT_INPUT_GATE"),
        pin(PATHS["vendor_rfi_gate"], "VENDOR_RFI_DECISION_GATE"),
        pin(PATHS["mpi_evidence_gate"], "ROUTE_C_MPI_EVIDENCE_GATE"),
        pin(PATHS["precad_gate"], "PRECAD_DIAGNOSTIC_GATE"),
        pin(PATHS["mission_gate"], "MISSION_DEFER_CONDITION_GATE"),
    ]

    integrity_criteria = [
        {"id": "B-I01", "name": "all checkpoint inputs exist and are hash-pinned", "pass": True},
        {"id": "B-I02", "name": "ODR-GPT-03/04 direct authority rebound", "pass": True},
        {"id": "B-I03", "name": "MPI bridge remains 9/9 with five zero bottom-line metrics", "pass": True},
        {"id": "B-I04", "name": "C2 registry independently parsed as 13 null/HOLD entries", "pass": True},
        {"id": "B-I05", "name": "RFI-E/F/G issuance and zero-response state verified", "pass": True},
        {"id": "B-I06", "name": "eight-condition C2 admission evaluated fail-closed", "pass": True},
        {"id": "B-I07", "name": "no Route-C CAD asset exists in controlled Route-C package", "pass": True},
        {"id": "B-I08", "name": "candidate, scan-axis and synthetic evidence remain non-authoritative", "pass": True},
    ]

    gate = {
        "schema": "ROUTE_C_CHECKPOINT_B_GATE_V1",
        "checkpoint": "CHECKPOINT-B__ROUTE_C_C2_ADMISSION_GATE",
        "generated_local": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "generator": "GPT mechanical chief and multi-agent Loop Engineering integrator",
        "checkpoint_reached": True,
        "checkpoint_outcome": "HOLD",
        "technical_verdict": "CHECKPOINT_B_REACHED__ROUTE_C_C2_ADMISSION_HOLD_13_OF_13_PHYSICAL_FIELDS_NULL__CAD_PROHIBITED__NO_RELEASE_CREDIT",
        "scope": "Route-C C2 physical-input admission only; no CAD, product selection, procurement release, mission release, or flight qualification",
        "evaluation_integrity": {
            "criteria": integrity_criteria,
            "summary": {"passed": 8, "total": 8, "failed": []},
        },
        "admission": {
            "rule": "ALL C2-ADM-01..08 must PASS; any FAIL or UNKNOWN keeps ROUTE_C_CAD_AUTHORIZED=false",
            "conditions": admission["current_evaluation"]["per_condition"],
            "summary": tally,
            "pass_ids": tally["pass_ids"],
            "fail_ids": tally["fail_ids"],
            "ROUTE_C_CAD_AUTHORIZED": False,
            "next_stage_authorized": False,
        },
        "physical_registry": {
            "entries_total": 13,
            "value_non_null": 0,
            "status_AVAILABLE": 0,
            "status_HOLD": 13,
            "candidate_sources_present": registry["summary"]["entries_with_candidate_source"],
            "candidate_source_ids": registry["summary"]["entries_with_candidate_source_ids"],
            "candidate_sources_are_authority": False,
            "fields": [{
                "id": item["id"],
                "quantity": item["quantity"],
                "unit": item.get("unit"),
                "value": None,
                "value_uncertainty": None,
                "status": "HOLD",
                "assigned_rfi": rfi_by_field.get(item["id"]),
            } for item in entries],
        },
        "rfi_state": {
            "issuance_status": rfi["status"],
            "rfi_ids": rfi_ids,
            "responses_received": 0,
            "values_filled_into_registry": 0,
            "fields_upgraded_to_candidate_range": 0,
            "rfi_response_alone_closes_mpi": False,
            "registered_field_targets": rfi_by_field,
        },
        "precad_state": {
            "predicate_tests": "47/47 PASS_SYNTHETIC_SEMANTICS_ONLY",
            "predicate_grants_design_authority": False,
            "physical_candidates_evaluated": precad["physical_capacity_frontier"]["physical_candidates_evaluated"],
            "candidate_found": False,
            "physical_capacity_frontier": precad["physical_capacity_frontier"],
            "route_c_cad_assets_found": cad_assets,
        },
        "mission_release_effect": {
            "ODR_GPT_04_defer_condition_met": False,
            "mission_coverage": mission["mission_coverage"],
            "harness_gate": mission["harness_gate"],
            "key_states_safe": 0,
            "key_states_total": 10,
            "trajectory_segments_released": mission["trajectory_segments_with_released_authority"],
            "trajectory_segments_total": 8,
            "full_range_harness_may_be_deferred_now": False,
        },
        "authority_guards": {
            "owner_accepted": False,
            "review_status": "PENDING_OWNER_REVIEW",
            "next_stage_authorized": False,
            "release_credit": False,
            "route_b_reopen_allowed": False,
            "null_to_zero_allowed": False,
            "llm_estimate_as_authority_allowed": False,
            "scan_axis_as_measurement_allowed": False,
            "route_b_seed_inheritance_allowed": False,
            "route_c_cad_authorized": False,
        },
        "allowed_now": [
            "receive and source-control RFI-E/F/G responses",
            "complete electrical, pinout, installed-construction, installation-ICD, and mission-life owner inputs",
            "perform exact-construction bend-torsion, friction/wear, mass-per-length, and installed-OD measurements",
            "update P01-P13 only with units, tolerance/uncertainty, provenance, and authority class",
            "rerun this admission Gate after traceable CM registration",
        ],
        "prohibited_now": [
            "Route-C CAD/STEP/FCStd/STL/GLB generation",
            "catalog candidate to selected product promotion without authority",
            "null to guessed value or zero",
            "LLM engineering estimate as authority",
            "Route-B seed inheritance",
            "production dynamics, physical-contact RL, hardware motion, or release claim",
        ],
        "next_automatic_action": [
            "freeze this Checkpoint-B HOLD evidence",
            "await traceable physical responses and controlled owner-input completion; no heavy solver is authorized",
            "on new registered evidence, rerun C2-ADM-01..08 without weakening any condition",
            "start Route-C CAD only after 8/8 admission PASS and a separately recorded authorization state",
        ],
        "evidence_pins": evidence_pins,
        "terminal_release_candidate_generated": False,
        "owner_accepted": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED; CHECKPOINT_B_SHA256.csv pins this Gate after emission",
    }

    gate_path = HERE / "ROUTE_C_CHECKPOINT_B_GATE_V1.json"
    gate_path.write_text(json.dumps(gate, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    gate_hash = sha256(gate_path)

    field_names = ", ".join(f"{item['id']} {item['quantity']}" for item in entries)
    receipt = f"""# Route-C C2 CHECKPOINT-B 收据

## 总裁决

`CHECKPOINT-B` 已到达，但准入结果为 **HOLD**。

- 机器裁决：`{gate['technical_verdict']}`
- 评价完整性：8/8 PASS
- Route-C C2 准入：2/8 PASS，6/8 FAIL
- C2 物理注册表：0/13 非空，0/13 AVAILABLE，13/13 HOLD
- `ROUTE_C_CAD_AUTHORIZED=false`
- `owner_accepted=false`；`next_stage_authorized=false`；`release_credit=false`
- Gate SHA-256：`{gate_hash}`

## 为什么“检查点完成”仍是 HOLD

检查点完成表示八项准入条件已经按 fail-closed 规则真实求值，不表示准入通过。当前仅 MPI 桥确认两项满足；RFI-E/F/G 虽已发放，但响应为 0，不能替代物理证据，也不能关闭任何 MPI 行。

## 13 个仍为空的物理量

{field_names}。

其中只有 P01、P02、P09 存在目录候选源；它们仍不是项目权威值。目录弯曲半径不等于动态寿命证据，单根/成品电缆外径与线密度不等于安装后 dress-pack 外径与线密度。

## RFI 与仍需项目自有证据的边界

- RFI-E：P12 载体尺寸、P04 载体行程/硬停。
- RFI-F：P10 导向/衬垫材料对的摩擦、磨损与真空工况。
- RFI-G：P13 夹具规则和 P05 夹具接口产品输入；它不能提供项目自有安装坐标。
- P03、P05、P07、P11、P13 等路径/坐标量仍需受控接口与工程推导；P08 组合弯扭顺应性必须靠确切构型试验。

## Mission Release 影响

ODR-GPT-04 的延期条件未满足：任务覆盖仍 FAIL，10 个必需关键状态 0 SAFE，8 条轨迹 0 released。因而 Full-Range Route-C 目前不能降为不阻塞 Gate A 的未来 HOLD。

## CAD 与后续动作

受控 Route-C 目录内未发现 FCStd/STEP/STL/GLB 等 CAD 文件，符合禁令。下一步只允许接收并受控登记 RFI 响应、补齐五类 Owner 输入、执行确切安装构型的弯扭/摩擦磨损/线密度/安装外径测试，并在证据落账后原判据重跑。任何字段为空时不得启动 Route-C CAD。
"""
    receipt_path = HERE / "ROUTE_C_CHECKPOINT_B_RECEIPT_V1.md"
    receipt_path.write_text(receipt, encoding="utf-8")

    output_paths = [Path(__file__).resolve(), gate_path, matrix_path, receipt_path,
                    HERE / "validate_checkpoint_b.py"]
    hash_rows: list[dict[str, Any]] = []
    for path in output_paths:
        require(path.is_file(), f"missing checkpoint output/source: {path}")
        hash_rows.append({
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "role": "CHECKPOINT_OUTPUT_OR_EXECUTABLE",
        })
    hash_rows.extend(evidence_pins)
    hashes_path = HERE / "CHECKPOINT_B_SHA256.csv"
    with hashes_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256", "role"])
        writer.writeheader()
        writer.writerows(hash_rows)

    print(json.dumps({
        "checkpoint_reached": True,
        "checkpoint_outcome": "HOLD",
        "evaluation_integrity": "8/8 PASS",
        "admission": "2/8 PASS",
        "registry": "0/13 non-null; 13/13 HOLD",
        "ROUTE_C_CAD_AUTHORIZED": False,
        "gate_sha256": sha256(gate_path),
        "matrix_sha256": sha256(matrix_path),
        "receipt_sha256": sha256(receipt_path),
        "hash_rows": len(hash_rows),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
