"""Append-only V4 aggregation for the R2 digital-prototype entry package.

V4 binds four already-issued evidence layers: the V3 bounded convergence
aggregate, the source-only CAD postgeneration-validator preflight, the M01
scene/collision prebind, and the append-only current-state reissue.  It does
not generate CAD, instantiate an M01 scene, execute a geometry query, or
supersede any dynamics, control, joint, mechanical, or release Gate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


PACKAGE = Path(__file__).resolve().parent


def workspace_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("WORKSPACE_ROOT_NOT_FOUND")


ROOT = workspace_root()
OUTPUT = PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4.json"
MANIFEST = PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V4.json"
M01_PACKAGE = (
    ROOT
    / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1"
)
CURRENT_STATE_PACKAGE = (
    ROOT
    / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/"
    "current_state_reissue_v2"
)
CANDIDATE_STEP = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step"
CANDIDATE_GLB = PACKAGE / ".R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step.glb"

SOURCE_PINS: dict[str, dict[str, Any]] = {
    "entry_gate_v3": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3.json",
        "bytes": 12446,
        "sha256": "DA4C46C9755E1C60CDCFD717876AE3F5ECB19286002AADD402B5596B073DD4B8",
        "format": "json",
    },
    "entry_manifest_v3": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3.json",
        "bytes": 4578,
        "sha256": "D8C2697C0506CEA7150B87595ADF55F128B9B5CCDA74CEB660CE5C599E4B0CA9",
        "format": "json",
    },
    "cad_postgeneration_validator_preflight": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CAD_POSTGENERATION_VALIDATOR_PREFLIGHT_V1.json",
        "bytes": 5957,
        "sha256": "543719271107A2935161B54311F8CA88A40822D6BC5115BEF68C7D8C0E1018E9",
        "format": "json",
    },
    "m01_prebind_gate": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json",
        "bytes": 7677,
        "sha256": "CDFADB08C3C93F9E380C41B232727E7D08750B2955411DF9E4AF894C550B7FC4",
        "format": "json",
    },
    "m01_prebind_manifest": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_SHA256_V1.csv",
        "bytes": 650,
        "sha256": "2D6F52E299A03666C23158E7966E7A9461A8C83A205D5212E71F43436CD226E1",
        "format": "csv_manifest",
    },
    "current_state_gate_v2": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_state_reissue_v2/R2_CURRENT_STATE_GATE_V2.json",
        "bytes": 5624,
        "sha256": "809D1DED57752F1658FD3A3F9CE3AC25C85B55C823BC2E824E9113B57D2AB8F8",
        "format": "json",
    },
    "current_state_package_manifest_v2": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_state_reissue_v2/R2_CURRENT_STATE_PACKAGE_MANIFEST_V2.json",
        "bytes": 2020,
        "sha256": "797F17EF995FC115AE35715FAAD9FF7602D6332FF141B49D6EA67E00F47BB0CF",
        "format": "json",
    },
}


class AggregateError(RuntimeError):
    """Raised when an aggregate input is malformed or ambiguous."""


def _reject_duplicate_key(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AggregateError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_key
    )
    if not isinstance(value, dict):
        raise AggregateError(f"EXPECTED_JSON_OBJECT:{path}")
    return value


def load_csv_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["path", "bytes", "sha256"]:
            raise AggregateError(f"INVALID_CSV_MANIFEST_HEADER:{path}")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in reader:
            if None in raw or set(raw) != {"path", "bytes", "sha256"}:
                raise AggregateError(f"INVALID_CSV_MANIFEST_ROW:{path}")
            relative = raw["path"]
            if not relative or relative in seen:
                raise AggregateError(f"DUPLICATE_OR_EMPTY_CSV_PATH:{relative}")
            seen.add(relative)
            try:
                size = int(raw["bytes"])
            except (TypeError, ValueError) as exc:
                raise AggregateError(f"INVALID_CSV_BYTES:{relative}") from exc
            digest = raw["sha256"].upper()
            if size < 0 or len(digest) != 64 or any(
                character not in "0123456789ABCDEF" for character in digest
            ):
                raise AggregateError(f"INVALID_CSV_PIN:{relative}")
            rows.append({"path": relative, "bytes": size, "sha256": digest})
    if not rows:
        raise AggregateError(f"EMPTY_CSV_MANIFEST:{path}")
    return {"schema": "CSV_SHA256_MANIFEST", "rows": rows}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_sources() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for source_id, pin in SOURCE_PINS.items():
        path = ROOT / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256(path) if exists else None
        match = bool(
            exists
            and actual_bytes == pin["bytes"]
            and actual_sha == pin["sha256"]
        )
        rows.append(
            {
                "id": source_id,
                "path": pin["path"],
                "format": pin["format"],
                "expected_bytes": pin["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": pin["sha256"],
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
        if match:
            documents[source_id] = (
                load_json(path)
                if pin["format"] == "json"
                else load_csv_manifest(path)
            )
    return documents, {
        "pins": rows,
        "matched": sum(bool(row["match"]) for row in rows),
        "total": len(rows),
        "all_match": all(bool(row["match"]) for row in rows),
    }


def _record_matches(record: Mapping[str, Any], base: Path) -> bool:
    try:
        path = Path(str(record["path"]))
        if not path.is_absolute():
            path = base / path
        return bool(
            path.is_file()
            and path.stat().st_size == record["bytes"]
            and sha256(path) == str(record["sha256"]).upper()
        )
    except (KeyError, OSError, TypeError, ValueError):
        return False


def _records_exact(records: Any, base: Path) -> bool:
    return bool(
        isinstance(records, list)
        and records
        and len({str(row.get("path")) for row in records if isinstance(row, dict)})
        == len(records)
        and all(isinstance(row, dict) and _record_matches(row, base) for row in records)
    )


def _named_check(document: Mapping[str, Any], check_id: str) -> Mapping[str, Any]:
    rows = [row for row in document.get("checks", []) if row.get("id") == check_id]
    return rows[0] if len(rows) == 1 else {}


def observe_runtime(cad_preflight: Mapping[str, Any]) -> dict[str, Any]:
    snapshot_row = _named_check(cad_preflight, "PF05_FOUR_UNIQUE_SNAPSHOT_OUTPUTS")
    raw_outputs = snapshot_row.get("evidence", [])
    snapshot_paths = (
        [Path(str(item)) for item in raw_outputs]
        if isinstance(raw_outputs, list)
        else []
    )
    return {
        "candidate_step": {
            "path": CANDIDATE_STEP.relative_to(ROOT).as_posix(),
            "present": CANDIDATE_STEP.is_file(),
        },
        "hidden_glb": {
            "path": CANDIDATE_GLB.relative_to(ROOT).as_posix(),
            "present": CANDIDATE_GLB.is_file(),
        },
        "candidate_snapshot_outputs": [
            {
                "path": (
                    path.relative_to(ROOT).as_posix()
                    if path.is_absolute() and path.is_relative_to(ROOT)
                    else path.as_posix()
                ),
                "present": path.is_file(),
            }
            for path in snapshot_paths
        ],
    }


def _manifest_record(
    manifest: Mapping[str, Any], collection: str, suffix: str
) -> Mapping[str, Any]:
    rows = [
        row
        for row in manifest.get(collection, [])
        if isinstance(row, dict) and str(row.get("path", "")).endswith(suffix)
    ]
    return rows[0] if len(rows) == 1 else {}


def evaluate(
    documents: Mapping[str, dict[str, Any]],
    binding: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    if not binding.get("all_match"):
        return {
            "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4",
            "technical_verdict": "SOURCE_HASH_DRIFT__FAIL_CLOSED",
            "source_binding": binding,
            "checks": {"V4-01_all_7_source_pins_exact": False},
            "summary": {
                "passed": 0,
                "total": 1,
                "failed": ["V4-01_all_7_source_pins_exact"],
            },
            "next_stage_authorized": False,
            "release_credit": False,
        }

    v3 = documents["entry_gate_v3"]
    v3_manifest = documents["entry_manifest_v3"]
    cad = documents["cad_postgeneration_validator_preflight"]
    m01 = documents["m01_prebind_gate"]
    m01_manifest = documents["m01_prebind_manifest"]
    current = documents["current_state_gate_v2"]
    current_manifest = documents["current_state_package_manifest_v2"]

    v3_gate_record = _manifest_record(
        v3_manifest,
        "local_artifacts",
        "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3.json",
    )
    m01_gate_record = _manifest_record(
        m01_manifest,
        "rows",
        "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json",
    )
    current_gate_record = _manifest_record(
        current_manifest, "package_entries", "R2_CURRENT_STATE_GATE_V2.json"
    )
    current_truth = current.get("current_truth", {})
    current_m01 = current_truth.get("mechanical_m01_route_c", {})
    current_sim13 = current_truth.get("sim13", {})
    current_dynamics = current_truth.get("dynamics", {})
    current_control = current_truth.get("control_and_joint", {})
    current_l06 = current_truth.get("l06_drawing_bom_material_conflict", {})

    snapshot_outputs = runtime.get("candidate_snapshot_outputs", [])
    all_snapshot_outputs_absent = bool(
        isinstance(snapshot_outputs, list)
        and len(snapshot_outputs) == 4
        and all(row.get("present") is False for row in snapshot_outputs)
    )
    all_cad_source_pins_exact = bool(
        isinstance(cad.get("source_pins"), dict)
        and len(cad["source_pins"]) == 9
        and all(
            _record_matches(record, PACKAGE)
            for record in cad["source_pins"].values()
        )
    )

    checks = {
        "V4-01_all_7_source_pins_exact": True,
        "V4-02_V3_additive_convergence_19_of_19_retained": (
            v3.get("schema")
            == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3"
            and v3.get("summary") == {"passed": 19, "total": 19, "failed": []}
            and v3.get("technical_verdict")
            == "PASS_ADDITIVE_DG1_TO_DG5_DESIGN_CANDIDATE_CONVERGENCE__PARENT_DYNAMICS_CAD_M01_ROUTE_C_PHYSICAL_CONTACT_NON_ABORT_CONTROL_AND_RELEASE_HOLD"
        ),
        "V4-03_V3_manifest_declares_four_local_and_eleven_external_records": (
            v3_manifest.get("schema")
            == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3"
            and v3_manifest.get("summary")
            == {"local_count": 4, "external_pin_count": 11, "all_exist": True}
            and v3_manifest.get("parent_gates_mutated") is False
            and v3_manifest.get("next_stage_authorized") is False
            and v3_manifest.get("release_credit") is False
        ),
        "V4-04_V3_manifest_local_records_and_gate_pin_are_exact": (
            _records_exact(v3_manifest.get("local_artifacts"), ROOT)
            and v3_gate_record.get("bytes") == SOURCE_PINS["entry_gate_v3"]["bytes"]
            and v3_gate_record.get("sha256")
            == SOURCE_PINS["entry_gate_v3"]["sha256"]
        ),
        "V4-05_V3_denies_CAD_M01_physical_nonabort_and_release_authority": (
            v3.get("bounded_research_actions_available", {}).get(
                "integrated_candidate_CAD_generation"
            )
            is False
            and v3.get("bounded_research_actions_available", {}).get(
                "geometry_pair_or_edge_query"
            )
            is False
            and v3.get("bounded_research_actions_available", {}).get(
                "M01_path_search"
            )
            is False
            and v3.get("bounded_research_actions_available", {}).get(
                "physical_contact_or_target_attachment"
            )
            is False
            and v3.get("bounded_research_actions_available", {}).get(
                "non_abort_grasp"
            )
            is False
            and v3.get("next_stage_authorized") is False
            and v3.get("release_credit") is False
        ),
        "V4-06_CAD_source_only_postvalidator_preflight_11_of_11": (
            cad.get("schema") == "CAD_POSTGENERATION_VALIDATOR_PREFLIGHT_V1"
            and cad.get("summary") == {"passed": 11, "total": 11, "failed": []}
            and cad.get("verdict")
            == "POSTGENERATION_VALIDATOR_READY__CANDIDATE_ARTIFACT_ABSENT_OR_UNVALIDATED__NO_GEOMETRY_CREDIT"
            and cad.get("authority")
            == "POSTGENERATION_VALIDATION_PREPARATION_ONLY__NO_CAD_GENERATION_OR_GEOMETRY_CREDIT"
        ),
        "V4-07_all_9_CAD_preflight_source_pins_exact": all_cad_source_pins_exact,
        "V4-08_candidate_STEP_and_hidden_GLB_absent_and_geometry_unvalidated": (
            cad.get("candidate_artifact_present") is False
            and cad.get("geometry_validated") is False
            and runtime.get("candidate_step", {}).get("present") is False
            and runtime.get("hidden_glb", {}).get("present") is False
        ),
        "V4-09_candidate_snapshot_not_executed_and_four_outputs_absent": (
            cad.get("snapshot_executed") is False and all_snapshot_outputs_absent
        ),
        "V4-10_CAD_preflight_does_not_claim_memory_or_owner_override": (
            cad.get("memory_gate_applicable") is False
            and cad.get("memory_gate_passed") is False
            and cad.get("owner_override_used") is False
            and cad.get("next_stage_authorized") is False
            and cad.get("release_credit") is False
        ),
        "V4-11_M01_append_only_prebind_18_of_18": (
            m01.get("schema") == "M01_SCENE_AND_COLLISION_PREBIND_GATE_V1"
            and m01.get("checks_passed") == m01.get("checks_total") == 18
            and all(m01.get("checks", {}).values())
            and m01.get("prebind_package_complete") is True
        ),
        "V4-12_M01_has_30_explicit_keys_but_zero_values_and_zero_of_three_scenes": (
            m01.get("scene_accounting", {}).get("explicit_field_keys_present")
            == m01.get("scene_accounting", {}).get("explicit_field_keys_required")
            == 30
            and m01.get("scene_accounting", {}).get(
                "authoritative_field_values_bound"
            )
            == 0
            and m01.get("scene_accounting", {}).get("legacy_required_values_bound")
            == 0
            and m01.get("scene_accounting", {}).get(
                "legacy_required_values_required"
            )
            == 9
            and m01.get("scene_accounting", {}).get("stage_instances_bound") == 0
            and m01.get("scene_accounting", {}).get("stage_instances_required") == 3
            and m01.get("scene_accounting", {}).get("scene_binding_complete")
            is False
        ),
        "V4-13_M01_asset_ledger_accounts_150_active_10_keepout_and_7_missing": (
            m01.get("asset_accounting", {}).get("active_object_rows") == 150
            and m01.get("asset_accounting", {}).get(
                "conditional_virtual_keepout_rows"
            )
            == 10
            and m01.get("asset_accounting", {}).get("known_missing_category_rows")
            == 7
            and m01.get("asset_accounting", {}).get("row_count") == 167
            and m01.get("asset_accounting", {}).get(
                "all_non_null_asset_pins_verified"
            )
            is True
        ),
        "V4-14_M01_only_one_of_150_assets_has_asset_level_operational_authority": (
            m01.get("asset_accounting", {}).get("asset_level_closed_rows") == 1
            and m01.get("asset_accounting", {}).get("operational_authority_rows")
            == 1
            and "149_OF_150_ACTIVE_OBJECTS_LACK_ASSET_LEVEL_OPERATIONAL_AUTHORITY"
            in m01.get("blockers", [])
            and m01.get("system_execution_state", {}).get(
                "complete_system_operational_collision_asset_set_bound"
            )
            is False
        ),
        "V4-15_M01_zero_of_11166_queries_zero_edges_and_search_false": (
            current_m01.get("M01_clearance_policy") == "0_OF_11166"
            and current_m01.get("M01_pair_oracle") == "0_OF_11166"
            and current_m01.get("M01_motion_certificates") == "0_OF_150"
            and current_m01.get("M01_continuous_edge_certificates") == 0
            and current_m01.get("M01_path_search_executed") is False
            and m01.get("system_execution_state", {}).get(
                "system_pair_queries_executed"
            )
            == 0
            and m01.get("system_execution_state", {}).get(
                "system_pair_evaluation_authorized"
            )
            is False
            and m01.get("system_execution_state", {}).get("system_edges_certified")
            == 0
            and m01.get("system_execution_state", {}).get(
                "path_search_authorized"
            )
            is False
            and m01.get("system_execution_state", {}).get("path_search_executed")
            is False
            and "11166_REQUIRED_PAIR_QUERIES_UNEXECUTED_FAIL_CLOSED"
            in m01.get("blockers", [])
        ),
        "V4-16_M01_six_row_manifest_is_self_excluded_and_exact": (
            len(m01_manifest.get("rows", [])) == 6
            and _records_exact(m01_manifest.get("rows"), M01_PACKAGE)
            and all(
                row.get("path") != "M01_SCENE_AND_COLLISION_PREBIND_SHA256_V1.csv"
                for row in m01_manifest.get("rows", [])
            )
            and m01_gate_record.get("bytes") == SOURCE_PINS["m01_prebind_gate"]["bytes"]
            and m01_gate_record.get("sha256")
            == SOURCE_PINS["m01_prebind_gate"]["sha256"]
        ),
        "V4-17_current_state_reissue_integrity_28_of_28": (
            current.get("schema") == "R2_CURRENT_STATE_GATE_V2"
            and current.get("summary") == {"passed": 28, "total": 28, "failed": []}
            and current.get("reissue_integrity_pass") is True
            and current.get("parent_artifacts_modified") is False
        ),
        "V4-18_current_state_six_entry_package_manifest_self_excluded_and_exact": (
            current_manifest.get("schema") == "R2_CURRENT_STATE_PACKAGE_MANIFEST_V2"
            and current_manifest.get("entry_count") == 6
            and current_manifest.get("self_reference_policy")
            == "R2_CURRENT_STATE_PACKAGE_MANIFEST_V2.json EXCLUDES_ITSELF"
            and _records_exact(current_manifest.get("package_entries"), ROOT)
            and current_gate_record.get("bytes")
            == SOURCE_PINS["current_state_gate_v2"]["bytes"]
            and current_gate_record.get("sha256")
            == SOURCE_PINS["current_state_gate_v2"]["sha256"]
            and all(
                not str(row.get("path", "")).endswith(
                    "R2_CURRENT_STATE_PACKAGE_MANIFEST_V2.json"
                )
                for row in current_manifest.get("package_entries", [])
            )
        ),
        "V4-19_baseline_manifest_self_fingerprint_defect_preserved_not_repaired": (
            current_truth.get("baseline_manifest_integrity_defect", {}).get(
                "defect_confirmed"
            )
            is True
            and current_truth.get("baseline_manifest_integrity_defect", {}).get(
                "actual_bytes"
            )
            == 4488
            and current_truth.get("baseline_manifest_integrity_defect", {}).get(
                "actual_sha256"
            )
            == "7E87EE69A582FFEFB3400A67E84A562729585745FE59E8ED1DEC7A12C1EA5BBE"
            and current_truth.get("baseline_manifest_integrity_defect", {}).get(
                "repair_or_parent_mutation_performed"
            )
            is False
        ),
        "V4-20_Route_C_negative_witness_and_formal_HOLD_preserved": (
            current_m01.get("route_c_m01_raw_clearance_mm")
            == -10.729480331980062
            and current_m01.get("route_c_m01_gated_clearance_mm")
            == -17.313396996697108
            and current_m01.get("route_c_m01_fraction") == 0.5
            and current_m01.get("route_c_formal_pass") is False
        ),
        "V4-21_Sim13_20_of_20_is_backend_negative_control_only_and_ABORT_ONLY": (
            current_sim13.get("backend_negative_control_subscope") == "20_OF_20_PASS"
            and current_sim13.get("full_tmg6_reissued") is False
            and current_sim13.get("historical_terminal_snapshot") == "15_OF_20"
            and current_sim13.get("maximum_operational_state") == "ABORT_ONLY"
            and current_sim13.get("sim13_system_binding_gate_passed") is False
        ),
        "V4-22_DG_candidates_do_not_promote_parent_dynamics": (
            current_dynamics.get("DG1_DG2") == "15_OF_15_ADDITIVE_CANDIDATE"
            and current_dynamics.get("DG3")
            == "30_OF_30_ADDITIVE_CANDIDATE_PARENT_FALSE"
            and current_dynamics.get("DG4")
            == "15_OF_15_DESIGN_DIAGNOSTIC_PARENT_AND_PHYSICAL_FALSE"
            and current_dynamics.get("DG5")
            == "16_OF_16_DESIGN_SCREEN_PARENT_FALSE_AS_BUILT_CONTACT_ACTUATOR_NULL"
            and current_dynamics.get("parent_dynamics")
            == "1_OF_6_HOLD_NOT_REISSUED"
            and v3.get("dynamics_candidate_ledger", {}).get(
                "parent_dynamics_engineering_complete"
            )
            is False
        ),
        "V4-23_physical_contact_and_non_ABORT_authority_remain_false": (
            current_sim13.get("current_contact_grasp_authorized") is False
            and current_sim13.get("maximum_operational_state") == "ABORT_ONLY"
            and v3.get("bounded_research_actions_available", {}).get(
                "physical_contact_or_target_attachment"
            )
            is False
            and v3.get("bounded_research_actions_available", {}).get(
                "non_abort_grasp"
            )
            is False
            and "PHYSICAL_AS_BUILT_CONTACT_PATCH_CLOSING_TIME_FORCE_TORQUE_AND_UNCERTAINTY_PENDING"
            in v3.get("exact_remaining_blockers", [])
            and "POST_CAPTURE_ATTACHED_COMBINED_PLANT_AND_NON_ABORT_CONSUMER_AUTHORITY_ABSENT"
            in v3.get("exact_remaining_blockers", [])
        ),
        "V4-24_parent_control_SAFE_RL_VLA_and_joint_system_remain_HOLD": (
            current_control.get("control_technical_predevelopment_complete")
            is False
            and current_control.get("control_engineering_complete") is False
            and current_control.get("joint_gate") == "4_OF_13"
            and current_control.get("joint_system_ready") is False
            and current_control.get("rl_or_vla_execution_authorized") is False
            and current_control.get("historical_safe_gate")
            == "PASS_PENDING_REVIEW_NEXT_STAGE_FALSE"
        ),
        "V4-25_L06_eight_drawings_prohibited_and_6061_vs_7075_conflict_open": (
            current_l06.get("drawing_count") == 8
            and current_l06.get("manufacturing_use") == "PROHIBITED_8_OF_8"
            and current_l06.get("manufacturing_or_procurement_release") is False
            and current_l06.get("d05_material_label") == "AL6061-T6 CANDIDATE"
            and current_l06.get("d06_material_label") == "AL6061-T6 CANDIDATE"
            and current_l06.get("current_m3r_stage_a_b_design_material")
            == "PMAT-AL7075-T651-SHEET-PLATE"
            and current_l06.get("owner_adjudication_required") is True
        ),
        "V4-26_terminal_mechanical_and_release_Gates_remain_HOLD": (
            current_m01.get("terminal_gate_a_pass") is False
            and current.get("mechanical_release_ready") is False
            and current.get("next_stage_authorized") is False
            and current.get("release_credit") is False
        ),
        "V4-27_all_source_authority_flags_fail_closed": (
            all(
                document.get("next_stage_authorized") is False
                and document.get("release_credit") is False
                for document in (
                    v3,
                    v3_manifest,
                    cad,
                    m01,
                    current,
                    current_manifest,
                )
            )
            and m01.get("system_execution_state", {}).get("next_stage_authorized")
            is False
            and m01.get("system_execution_state", {}).get("release_credit")
            is False
        ),
        "V4-28_no_parent_mutation_or_supersession_claim": (
            v3_manifest.get("parent_gates_mutated") is False
            and current.get("parent_artifacts_modified") is False
            and current.get("authority")
            == "APPEND_ONLY_CURRENT_STATE_REISSUE_INTEGRITY_ONLY__NO_ENGINEERING_GATE_SUPERSESSION"
            and m01.get("authority")
            == "APPEND_ONLY_PREBIND_EVIDENCE_ONLY__NO_PARENT_GATE_REISSUE_NO_QUERY_OR_SEARCH_AUTHORITY"
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    all_pass = not failed

    return {
        "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4",
        "technical_verdict": (
            "PASS_ADDITIVE_CAD_EXECUTION_PREPARATION_M01_PREBIND_AND_CURRENT_STATE_REISSUE__CANDIDATE_STEP_M01_QUERY_NON_ABORT_PARENT_GATES_AND_RELEASE_HOLD"
            if all_pass
            else "ADDITIVE_PREPARATION_AND_REISSUE_HOLD__SEE_FAILED_CHECKS"
        ),
        "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
        "source_binding": binding,
        "checks": checks,
        "summary": {
            "passed": sum(bool(value) for value in checks.values()),
            "total": len(checks),
            "failed": failed,
        },
        "additive_evidence_state": {
            "V3_bounded_dynamics_convergence": "19_OF_19",
            "CAD_postgeneration_validator_preflight": "11_OF_11_SOURCE_ONLY",
            "M01_scene_and_collision_prebind": "18_OF_18_APPEND_ONLY",
            "current_state_reissue_integrity": "28_OF_28_APPEND_ONLY",
            "preparation_evidence_consumable": all_pass,
            "parent_gate_credit_inherited": False,
        },
        "CAD_state": {
            "expected_candidate_solids": 399,
            "expected_candidate_groups": 2,
            "candidate_step_present": runtime.get("candidate_step", {}).get("present"),
            "hidden_glb_present": runtime.get("hidden_glb", {}).get("present"),
            "candidate_artifact_generated": False,
            "candidate_geometry_validated": False,
            "candidate_snapshot_executed": False,
            "candidate_snapshot_outputs_present": sum(
                bool(row.get("present")) for row in snapshot_outputs
            ),
            "memory_gate_evaluated_for_generation": False,
            "owner_override_used": False,
            "CAD_generation_authorized_by_V4": False,
        },
        "M01_state": {
            "prebind_checks": "18_OF_18",
            "explicit_decision_keys": "30_OF_30",
            "authoritative_values": "0_OF_30",
            "legacy_required_values": "0_OF_9",
            "stage_instances": "0_OF_3",
            "active_objects_accounted": 150,
            "asset_level_operational_authority": "1_OF_150",
            "clearance_policy": "0_OF_11166",
            "motion_certificates": "0_OF_150",
            "pair_oracle": "0_OF_11166",
            "continuous_edges_certified": 0,
            "pair_query_authorized": False,
            "path_search_authorized": False,
            "path_search_executed": False,
        },
        "system_HOLD_state": {
            "Route_C_formal_pass": False,
            "Route_C_raw_clearance_mm": -10.729480331980062,
            "Route_C_gated_clearance_mm": -17.313396996697108,
            "physical_contact_authority": False,
            "non_abort_authority": False,
            "Sim13_maximum_operational_state": "ABORT_ONLY",
            "parent_dynamics_complete": False,
            "parent_control_complete": False,
            "joint_system_ready": False,
            "terminal_mechanical_gate_a_pass": False,
            "mechanical_release_ready": False,
            "flight_release": False,
        },
        "bounded_actions_available": {
            "consume_V3_candidate_evidence": all_pass,
            "consume_CAD_validation_preparation": all_pass,
            "consume_M01_prebind_ledger": all_pass,
            "consume_current_state_reissue_ledger": all_pass,
            "generate_integrated_candidate_CAD": False,
            "claim_candidate_geometry_validated": False,
            "claim_candidate_snapshot_complete": False,
            "execute_M01_pair_query": False,
            "execute_M01_path_search": False,
            "claim_Route_C_pass": False,
            "claim_physical_contact_or_non_abort": False,
            "execute_RL_or_VLA": False,
            "claim_parent_or_release_pass": False,
        },
        "exact_remaining_blockers": [
            "FRESH_NAMED_CAD_RUN_AUTHORITY_AND_RUNTIME_MEMORY_ADMISSION_OR_EXACT_FRESH_SINGLE_USE_LOW_MEMORY_OWNER_OVERRIDE_REQUIRED",
            "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1_STEP_AND_HIDDEN_GLB_NOT_GENERATED",
            "CAD_POSTGENERATION_INSPECTION_399_SOLIDS_2_GROUPS_BOUNDS_MOUNT_AND_FOUR_VIEW_SNAPSHOT_NOT_EXECUTED",
            "M01_AUTHORITATIVE_SCENE_VALUES_0_OF_30_LEGACY_VALUES_0_OF_9_STAGE_INSTANCES_0_OF_3",
            "149_OF_150_ACTIVE_OBJECTS_LACK_ASSET_LEVEL_OPERATIONAL_AUTHORITY_AND_7_MISSING_CATEGORIES_REMAIN",
            "M01_CLEARANCE_0_OF_11166_MOTION_0_OF_150_ORACLE_0_OF_11166_EDGES_0_AND_SEARCH_FALSE",
            "ROUTE_C_NEGATIVE_CLEARANCE_WITNESS_PRESERVED_AND_FORMAL_PASS_FALSE",
            "PHYSICAL_AS_BUILT_CONTACT_AND_POST_CAPTURE_ATTACHED_COMBINED_PLANT_NOT_CLOSED",
            "NON_ABORT_CONSUMER_AUTHORITY_ABSENT_AND_SIM13_MAXIMUM_STATE_ABORT_ONLY",
            "PARENT_DYNAMICS_CONTROL_JOINT_MECHANICAL_AND_RELEASE_GATES_REMAIN_HOLD",
            "L06_6061_VS_7075_MATERIAL_ADJUDICATION_AND_SIBLING_HASH_DEBT_OPEN",
        ],
        "maximum_claim": "HASH_BOUND_ADDITIVE_SOURCE_ONLY_CAD_VALIDATION_PREPARATION_M01_PREBIND_AND_CURRENT_STATE_REISSUE__NOT_CAD_GENERATED_NOT_GEOMETRY_VALIDATED_NOT_M01_QUERY_NOT_ROUTE_C_NOT_PHYSICAL_CONTACT_NOT_NON_ABORT_NOT_PARENT_GATE_NOT_RELEASE",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_gate() -> dict[str, Any]:
    documents, binding = load_sources()
    if not binding["all_match"]:
        return evaluate(documents, binding, {})
    runtime = observe_runtime(documents["cad_postgeneration_validator_preflight"])
    return evaluate(documents, binding, runtime)


def _artifact_record(path: Path, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "role": role,
    }


def build_manifest() -> dict[str, Any]:
    local: Sequence[tuple[Path, str]] = (
        (Path(__file__).resolve(), "deterministic append-only V4 aggregate evaluator"),
        (
            PACKAGE / "tests" / "test_entry_gate_v4.py",
            "positive, integrity, duplicate-key and tamper-negative tests",
        ),
        (OUTPUT, "generated V4 aggregate Gate"),
    )
    return {
        "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V4",
        "self_reference_policy": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V4.json EXCLUDES_ITSELF",
        "local_artifacts": [_artifact_record(path, role) for path, role in local],
        "external_source_pins": SOURCE_PINS,
        "summary": {
            "local_count": len(local),
            "external_pin_count": len(SOURCE_PINS),
            "all_exist": all(path.is_file() for path, _ in local),
        },
        "parent_gates_mutated": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gate = build_gate()
    payload = canonical_bytes(gate)
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != payload:
            print("FAIL_OUTPUT_MISSING_OR_NOT_BYTE_IDENTICAL")
            return 2
        manifest_payload = canonical_bytes(build_manifest())
        if not MANIFEST.is_file() or MANIFEST.read_bytes() != manifest_payload:
            print("FAIL_MANIFEST_MISSING_OR_NOT_BYTE_IDENTICAL")
            return 2
        print("PASS_BYTE_IDENTICAL")
    else:
        OUTPUT.write_bytes(payload)
        MANIFEST.write_bytes(canonical_bytes(build_manifest()))
        print(gate["technical_verdict"])
        print(f"checks={gate['summary']['passed']}/{gate['summary']['total']}")
        print(f"sha256={sha256(OUTPUT)}")
        print(f"manifest_sha256={sha256(MANIFEST)}")
    return 0 if gate["summary"]["passed"] == gate["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
