"""Read-only validator for the R2 raw-adapter source freeze.

No solver, trajectory, campaign, or runtime raw output is imported or run.
Receipt writing exists only behind the exact ``--write-receipt`` flag.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from r2_raw_adapter.adapter import (
    COMMON_DONOR_PROJECTION_SHA256,
    common_donor_projection,
)
from r2_raw_adapter.array_contract import (
    ARRAY_CONTRACT_DOCUMENT_SHA256,
    EXACT_ARRAYS,
    contract_document,
)
from r2_raw_adapter.freeze_support import (
    all_json_paths,
    build_source_manifest,
    document_seal_valid,
    forbidden_artifacts,
    local_source_inventory,
    project_root_from,
    record_matches,
    seal_document,
    strict_load,
)
from r2_raw_adapter.negative_controls import NEGATIVE_CONTROL_IDS, run_all_negative_controls
from r2_raw_adapter.production_api import FROZEN_SOURCE_SHA256, verify_frozen_sources
from r2_raw_adapter.schedule_binding import MATRIX_SHA256, SCHEDULE_SHA256, schedule_records
from r2_raw_adapter.strict_json import atomic_write_json, canonical_sha256, file_sha256


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = project_root_from(HERE)
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_MANIFEST_V1.json"
NC_EVIDENCE = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_NEGATIVE_CONTROLS_V1.json"
OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_VALIDATION_V1.json"
AUDIT_OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_INDEPENDENT_SOURCE_AUDIT_V1.json"
GATE_OUTPUT = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_OUTPUT = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_TERMINAL_V1.json"
ARRAY_CONTRACT = HERE / "contracts/PHASE_B4G_R2_RAW_ARRAY_CONTRACT_V1.json"
NC_CONTRACT = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_NEGATIVE_CONTROL_CONTRACT_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_GOVERNANCE_V1.json"
FREEZE_CONTRACT = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_CONTRACT_V1.json"
SOURCE_BINDINGS = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_SOURCE_BINDINGS_V1.json"
RUNNER_CONTRACT = HERE / "contracts/PHASE_B4G_R2_AUTHORIZED_RUNNER_VNEXT_PREREGISTRATION_V1.json"


class RawAdapterValidationError(RuntimeError):
    pass


def build_negative_control_evidence(package_root: Path, source_inventory_sha256: str) -> dict[str, Any]:
    result = run_all_negative_controls(package_root)
    return seal_document({
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_NEGATIVE_CONTROLS_V1",
        "status": "PASS_EXACT_86_SOURCE_ONLY_NEGATIVE_CONTROLS_KILLED" if result["all_killed"] else "FAIL_SOURCE_ONLY_NEGATIVE_CONTROLS",
        "source_inventory_sha256": source_inventory_sha256,
        "negative_controls_source_sha256": file_sha256(package_root / "r2_raw_adapter/negative_controls.py"),
        "result_sha256": canonical_sha256(result),
        "result": result,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "next_stage_authorized": False,
    })


def _runner_guard_check() -> dict[str, Any]:
    source = HERE / "r2_raw_adapter/runner_guard.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    expected = {
        "consume_authorization", "authorized_lazy_imports",
        "create_output_root_after_authorization", "run_registered_vnext",
    }
    functions = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    exact: dict[str, bool] = {}
    for name in expected:
        node = functions.get(name)
        body = [] if node is None else list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        exact[name] = bool(
            len(body) == 1 and isinstance(body[0], ast.Raise)
            and isinstance(body[0].exc, ast.Call)
            and isinstance(body[0].exc.func, ast.Name)
            and body[0].exc.func.id == "RunnerAuthorizationError"
            and len(body[0].exc.args) == 1
            and isinstance(body[0].exc.args[0], ast.Name)
            and body[0].exc.args[0].id == "DENIAL"
        )
    contract = strict_load(RUNNER_CONTRACT)
    passed = bool(
        set(functions) >= expected and all(exact.values())
        and contract["direct_owner_source_available"] is False
        and all(contract[key] is False for key in (
            "authorization_consume_success_path_exists", "authorized_import_success_path_exists",
            "output_root_creation_success_path_exists", "physics_or_trajectory_run_success_path_exists",
        ))
    )
    return {"passed": passed, "functions": exact}


def _source_semantics_check() -> dict[str, Any]:
    adapter_path = HERE / "r2_raw_adapter/adapter.py"
    path_binding_path = HERE / "r2_raw_adapter/path_binding.py"
    adapter_text = adapter_path.read_text(encoding="utf-8")
    path_text = path_binding_path.read_text(encoding="utf-8")
    required_adapter = (
        "np.frombuffer(value.tobytes(order=\"C\")", "BytesIO(payload)", "allow_pickle=False",
        "MappingProxyType(arrays)", "_deep_freeze(sidecar)",
        "sidecar_sha256", "array_contract_document_sha256",
    )
    required_path = (
        "st_nlink", "_has_reparse_point", "PATH_ALIAS_OR_CASE_ALIAS_FORBIDDEN",
        "BOUND_FILE_CHANGED_DURING_SINGLE_READ",
    )
    return {
        "passed": all(token in adapter_text for token in required_adapter) and all(token in path_text for token in required_path),
        "adapter_sha256": file_sha256(adapter_path),
        "path_binding_sha256": file_sha256(path_binding_path),
    }


def _partial_boundary_check() -> dict[str, Any]:
    governance = strict_load(GOVERNANCE)
    text = (HERE / "r2_raw_adapter/adapter.py").read_text(encoding="utf-8")
    boundary = governance["g12_boundary"]
    passed = bool(
        boundary["full_raw_integrity_recomputed"] is False
        and boundary["source_only_candidate_predicate_pass"] is False
        and boundary["eligible"] is False
        and boundary["status"] == "HOLD_G12_FULL_RAW_INTEGRITY_BACKEND_NOT_IMPLEMENTED_SOURCE_FREEZE"
        and "post_raw_subset_pass" in text
        and "partial_post_checks_pass" in text
        and "full_post_release_predicate_recomputed\": False" in text
        and "raw_pair_subpredicates_pass" not in text
        and "source_only_candidate_predicate_pass\": False" in text
    )
    return {"passed": passed, "status": boundary["status"], "missing": boundary["missing_exact_backend_scope"]}


def _common_and_numeric_guard_check() -> dict[str, Any]:
    path = HERE / "r2_raw_adapter/adapter.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    donor = functions.get("common_donor_projection")
    donor_uncached = bool(donor is not None and not donor.decorator_list)
    aggregate_source = ast.get_source_segment(path.read_text(encoding="utf-8"), functions["aggregate_g12_raw"]) or ""
    donor_projection = common_donor_projection()
    passed = bool(
        donor_uncached
        and "_numeric_payload_sha256(case.arrays)" in aggregate_source
        and "len(set(numeric_payload_sha256)) != 36" in aggregate_source
        and donor_projection.projection_sha256 == COMMON_DONOR_PROJECTION_SHA256
    )
    return {
        "passed": passed,
        "donor_uncached": donor_uncached,
        "donor_projection_sha256": donor_projection.projection_sha256,
        "g12_numeric_payload_exact_36_unique_guard": "len(set(numeric_payload_sha256)) != 36" in aggregate_source,
    }


def _strict_local_json_check() -> dict[str, Any]:
    failures: list[str] = []
    # Generated validation/audit/Gate/terminal receipts are intentionally
    # downstream of this acyclic receipt and are checked by the published-chain
    # verifier.  Excluding that exact set makes the validator result stable
    # before and after terminal publication.
    paths = all_json_paths(HERE, excluded=(OUTPUT, AUDIT_OUTPUT, GATE_OUTPUT, TERMINAL_OUTPUT))
    for path in paths:
        try:
            strict_load(path)
        except Exception as exc:
            failures.append(f"{path.relative_to(HERE).as_posix()}:{type(exc).__name__}")
    return {"passed": not failures, "checked": len(paths), "failures": failures}


def validate_source_freeze(
    *,
    package_root: Path = HERE,
    manifest_path: Path = MANIFEST,
    negative_control_evidence_path: Path = NC_EVIDENCE,
    output_path: Path = OUTPUT,
    write_output: bool = False,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    checks: list[dict[str, Any]] = []
    contract = strict_load(FREEZE_CONTRACT)

    def add(check_id: str, passed: bool, detail: Any) -> None:
        checks.append({"id": check_id, "pass": passed is True, "detail": detail})

    observed_manifest = strict_load(manifest_path)
    rebuilt_manifest = build_source_manifest(package_root)
    add("R2RAV01_LOCAL_SOURCE_MANIFEST_EXACT", observed_manifest == rebuilt_manifest and document_seal_valid(observed_manifest), {
        "observed_source_count": observed_manifest.get("source_count", -1),
        "rebuilt_source_count": rebuilt_manifest["source_count"],
        "source_inventory_sha256": rebuilt_manifest["source_inventory_sha256"],
    })

    static_array = strict_load(ARRAY_CONTRACT)
    bindings = strict_load(SOURCE_BINDINGS)
    array_pass = bool(
        static_array == contract_document() and len(EXACT_ARRAYS) == 56
        and canonical_sha256(static_array) == ARRAY_CONTRACT_DOCUMENT_SHA256
        and bindings["array_contract_document_sha256"] == ARRAY_CONTRACT_DOCUMENT_SHA256
        and static_array["exact_arrays"]["acquisition_event_count"]["meaning"] == "zero for A0 bookend; one otherwise"
        and all(set(spec) == {"dtype", "shape", "unit", "meaning"} for spec in static_array["exact_arrays"].values())
    )
    add("R2RAV02_ARRAY_CONTRACT_EXACT_56_AND_HASH_BOUND", array_pass, {
        "array_count": len(EXACT_ARRAYS), "array_contract_document_sha256": ARRAY_CONTRACT_DOCUMENT_SHA256,
    })

    rows, order = schedule_records()
    role_counts = {
        role: sum(role in row["roles"] for row in rows)
        for role in ("A0_BOOKEND", "FRESH_ACQ_OBSERVATION", "COMMON_PROPAGATION_DIAGNOSTIC", "FRESH_ALPHA16_PROPAGATION", "G12_FRESH_REFERENCE")
    }
    schedule_pass = bool(
        len(rows) == len(order) == 78 and len(set(order)) == 78
        and canonical_sha256(rows) == MATRIX_SHA256
        and canonical_sha256(order) == SCHEDULE_SHA256
        and bindings["frozen_matrix_sha256"] == MATRIX_SHA256
        and bindings["frozen_schedule_sha256"] == SCHEDULE_SHA256
        and role_counts == {
            "A0_BOOKEND": 12, "FRESH_ACQ_OBSERVATION": 6,
            "COMMON_PROPAGATION_DIAGNOSTIC": 18,
            "FRESH_ALPHA16_PROPAGATION": 18, "G12_FRESH_REFERENCE": 36,
        }
    )
    add("R2RAV03_MATRIX_SCHEDULE_AND_78_ROLE_REGISTRY_HASH_BOUND", schedule_pass, {
        "case_count": len(rows), "role_counts": role_counts,
        "matrix_sha256": canonical_sha256(rows), "schedule_sha256": canonical_sha256(order),
    })

    observed_production = verify_frozen_sources()
    contract_production = {f"{name}.py": digest for name, digest in bindings["production_api_source_hashes"].items()}
    add("R2RAV04_EXTERNAL_PRODUCTION_SOURCE_HASHES_MATCH", observed_production == FROZEN_SOURCE_SHA256 == contract_production, observed_production)

    semantics = _source_semantics_check()
    add("R2RAV05_SIDECAR_NPZ_IMMUTABLE_BOUNDARY_SOURCE_PRESENT", semantics["passed"], semantics)
    partial = _partial_boundary_check()
    add("R2RAV06_RAW_DERIVED_PARTIAL_PREDICATES_AND_HOLD_BOUNDARY", partial["passed"], partial)
    runner = _runner_guard_check()
    add("R2RAV07_RUNNER_VNEXT_FOUR_PATHS_UNCONDITIONALLY_DENIED", runner["passed"], runner)

    nc_contract = strict_load(NC_CONTRACT)
    nc_contract_pass = bool(
        nc_contract["registered_count"] == 86
        and nc_contract["registered_ids"] == list(NEGATIVE_CONTROL_IDS)
        and len(set(NEGATIVE_CONTROL_IDS)) == 86
        and nc_contract["trajectory_count"] == 0
        and nc_contract["r2_numerical_preflight_executed"] is False
    )
    add("R2RAV08_NEGATIVE_CONTROL_CONTRACT_EXACT_86", nc_contract_pass, {"registered_count": len(NEGATIVE_CONTROL_IDS)})

    expected_nc = build_negative_control_evidence(package_root, rebuilt_manifest["source_inventory_sha256"])
    observed_nc = strict_load(negative_control_evidence_path)
    nc_pass = bool(
        observed_nc == expected_nc and document_seal_valid(observed_nc)
        and expected_nc["result"]["registered_count"] == 86
        and expected_nc["result"]["executed_count"] == 86
        and expected_nc["result"]["killed_count"] == 86
        and expected_nc["result"]["all_killed"] is True
    )
    add("R2RAV09_NEGATIVE_CONTROLS_REPLAY_EXACT_AND_ALL_KILLED", nc_pass, {
        "result_sha256": expected_nc["result_sha256"], "all_killed": expected_nc["result"]["all_killed"],
    })

    forbidden = forbidden_artifacts(package_root)
    add("R2RAV10_NO_FORBIDDEN_PERSISTENT_ARTIFACT_OR_CACHE", not forbidden, {"failures": forbidden})
    strict_json_check = _strict_local_json_check()
    add("R2RAV11_ALL_LOCAL_JSON_STRICT_NULL_FREE", strict_json_check["passed"], strict_json_check)

    governance = strict_load(GOVERNANCE)
    required_false_keys = (
        "r2_numerical_preflight_executed", "current_system_bound", "formal_nc19_credit",
        "science_credit", "owner_credit", "production_credit", "release_credit",
        "full_campaign_authorized", "next_stage_authorized", "direct_owner_source_available",
        "persistent_runtime_raw_permitted",
    )
    governance_pass = bool(
        governance["highest_permitted_gate_status"] == contract["highest_permitted_gate_status"]
        and governance["trajectory_count"] == 0
        and all(governance[key] is False for key in required_false_keys)
        and contract["trajectory_count"] == 0
        and contract["r2_numerical_preflight_executed"] is False
        and contract["current_system_bound"] is False
        and contract["formal_nc19_credit"] is False
        and contract["next_stage_authorized"] is False
    )
    add("R2RAV12_GOVERNANCE_FALSE_ZERO_AND_STATUS_EXACT", governance_pass, {
        "highest_permitted_gate_status": governance["highest_permitted_gate_status"], "trajectory_count": governance["trajectory_count"],
    })
    add("R2RAV13_LEGACY_RAW_INCOMPATIBILITY_EXPLICIT", bool(
        static_array["compatibility"] == "FUTURE_R2_EXACT_SCHEMA_LEGACY_B4G_RAW_IS_INCOMPATIBLE"
        and len(static_array["legacy_b4g_missing_required_arrays"]) == 12
        and governance["legacy_raw_compatibility"] == "REJECT_LEGACY_B4G_RAW_EXACT_R2_SCHEMA_REQUIRED"
    ), {"missing_required_array_count": len(static_array["legacy_b4g_missing_required_arrays"])})
    common_numeric = _common_and_numeric_guard_check()
    add("R2RAV14_COMMON_DONOR_UNCACHED_AND_NUMERIC_UNIQUENESS_GUARDS_PRESENT", common_numeric["passed"], common_numeric)

    expected_ids = contract["validator_check_ids"]
    ids_exact = [row["id"] for row in checks] == expected_ids
    failed = [row["id"] for row in checks if row["pass"] is not True]
    if not ids_exact:
        failed.append("VALIDATOR_CHECK_ID_ORDER_DRIFT")
    result = seal_document({
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_VALIDATION_V1",
        "status": contract["validation_pass_status"] if not failed else "FAIL_R2_RAW_EVIDENCE_ADAPTER_SOURCE_VALIDATION",
        "scope": "SOURCE_CONTRACT_HASH_NEGATIVE_CONTROL_REPLAY_ONLY_NO_PHYSICS_NO_TRAJECTORY",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "source_inventory_sha256": rebuilt_manifest["source_inventory_sha256"],
        "negative_control_result_sha256": expected_nc["result_sha256"],
        "source_freeze_pass_eligible": not failed,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "next_stage_authorized": False,
    })
    if write_output:
        atomic_write_json(output_path, result)
    return result


def verify_published_chain() -> dict[str, Any]:
    try:
        gate = strict_load(GATE_OUTPUT)
        terminal = strict_load(TERMINAL_OUTPUT)
        contract = strict_load(FREEZE_CONTRACT)
        evidence = gate.get("evidence", [])
        evidence_ids = {row.get("id") for row in evidence if isinstance(row, dict)}
        expected_ids = {"raw_adapter_source_manifest", "raw_adapter_negative_controls", "raw_adapter_source_validation", "raw_adapter_independent_source_audit"}
        evidence_pass = bool(
            len(evidence) == len(evidence_ids) == 4 and evidence_ids == expected_ids
            and all(record_matches(row, PROJECT_ROOT) for row in evidence)
        )
        records = terminal.get("records", [])
        terminal_pass = bool(
            len(records) == 1 and records[0].get("id") == "raw_adapter_source_freeze_gate"
            and record_matches(records[0], PROJECT_ROOT)
        )
        semantics = bool(
            document_seal_valid(gate) and document_seal_valid(terminal)
            and gate["status"] == terminal["status"] == contract["highest_permitted_gate_status"]
            and gate["trajectory_count"] == terminal["trajectory_count"] == 0
            and gate["r2_numerical_preflight_executed"] is False
            and terminal["r2_numerical_preflight_executed"] is False
            and gate["current_system_bound"] is False and terminal["current_system_bound"] is False
            and gate["formal_nc19_credit"] is False and terminal["formal_nc19_credit"] is False
            and gate["next_stage_authorized"] is False and terminal["next_stage_authorized"] is False
        )
        return {"passed": evidence_pass and terminal_pass and semantics, "evidence_pass": evidence_pass, "terminal_gate_record_pass": terminal_pass, "semantics_pass": semantics}
    except Exception as exc:
        return {"passed": False, "error": f"{type(exc).__name__}:{exc}"}


def _receipt_matches(result: dict[str, Any], path: Path = OUTPUT) -> bool:
    try:
        return strict_load(path) == result
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only R2 raw-adapter source validator", allow_abbrev=False)
    parser.add_argument("--write-receipt", action="store_true", help="explicitly write validator receipt")
    args = parser.parse_args(argv)
    try:
        result = validate_source_freeze(write_output=args.write_receipt)
        receipt_match = args.write_receipt or _receipt_matches(result)
        chain = {"passed": True, "mode": "NOT_REQUIRED_DURING_EXPLICIT_RECEIPT_GENERATION"} if args.write_receipt else verify_published_chain()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_R2_RAW_ADAPTER_VALIDATOR_EXCEPTION", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    passed = bool(result["source_freeze_pass_eligible"] and receipt_match and chain.get("passed") is True)
    status = result["status"] if passed else "FAIL_R2_RAW_ADAPTER_VALIDATOR_RECEIPT_OR_CHAIN_DRIFT"
    print(json.dumps({
        "status": status, "score": result["score"],
        "mode": "WRITE_RECEIPT" if args.write_receipt else "READ_ONLY_RECEIPT_VERIFY",
        "receipt_match": receipt_match, "published_chain": chain,
        "trajectory_count": 0, "r2_numerical_preflight_executed": False,
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
