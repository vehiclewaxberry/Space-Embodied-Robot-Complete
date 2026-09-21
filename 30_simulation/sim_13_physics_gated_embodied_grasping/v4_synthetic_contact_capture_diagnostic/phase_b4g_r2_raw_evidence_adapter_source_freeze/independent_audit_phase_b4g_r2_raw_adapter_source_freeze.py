"""Stdlib-only independent audit of the R2 raw-adapter source freeze."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_MANIFEST_V1.json"
NC_EVIDENCE = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_NEGATIVE_CONTROLS_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_VALIDATION_V1.json"
OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_INDEPENDENT_SOURCE_AUDIT_V1.json"
GATE = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_TERMINAL_V1.json"
ARRAY_CONTRACT = HERE / "contracts/PHASE_B4G_R2_RAW_ARRAY_CONTRACT_V1.json"
NC_CONTRACT = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_NEGATIVE_CONTROL_CONTRACT_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_GOVERNANCE_V1.json"
FREEZE_CONTRACT = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_CONTRACT_V1.json"
SOURCE_BINDINGS = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_SOURCE_BINDINGS_V1.json"
RUNNER_CONTRACT = HERE / "contracts/PHASE_B4G_R2_AUTHORIZED_RUNNER_VNEXT_PREREGISTRATION_V1.json"
SOURCE_EXTENSIONS = {".ini", ".json", ".md", ".py"}
OUTPUT_PREFIXES = ("evidence/", "results/")
FORBIDDEN_SUFFIXES = {".csv", ".npz", ".pyc", ".step", ".stp", ".tmp", ".urdf"}
FORBIDDEN_DIRECTORIES = {".pytest_cache", "__pycache__", "raw", "raw_cases"}
TEMP_PREFIXES = (".dbg_", ".r2_raw_nc_", ".r2_raw_test_")
HEX64 = set("0123456789ABCDEF")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise RuntimeError(f"NONFINITE_JSON_TOKEN:{token}")


def _validate_tree(value: Any) -> None:
    if value is None:
        raise RuntimeError("NULL_JSON_FORBIDDEN")
    if isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError("NONFINITE_JSON_NUMBER")
        return
    if isinstance(value, list):
        for item in value:
            _validate_tree(item)
        return
    if isinstance(value, dict):
        if not all(type(key) is str for key in value):
            raise RuntimeError("NONSTRING_JSON_KEY")
        for item in value.values():
            _validate_tree(item)
        return
    raise RuntimeError(f"NON_JSON_TYPE:{type(value).__name__}")


def load(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"REGULAR_JSON_REQUIRED:{path}")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
    _validate_tree(value)
    return value


def canonical_bytes(value: Any) -> bytes:
    _validate_tree(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["document_sha256"] = canonical_hash(value)
    return result


def seal_valid(value: Any) -> bool:
    return bool(
        isinstance(value, dict) and type(value.get("document_sha256")) is str
        and canonical_hash({key: item for key, item in value.items() if key != "document_sha256"}) == value["document_sha256"]
    )


def write_json(path: Path, value: Any) -> None:
    _validate_tree(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(callable(is_junction) and is_junction())


def independent_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    unknown: list[str] = []
    for path in sorted(HERE.rglob("*"), key=lambda item: item.relative_to(HERE).as_posix()):
        relative = path.relative_to(HERE).as_posix()
        if _is_link_or_reparse(path):
            raise RuntimeError(f"LINK_OR_REPARSE:{relative}")
        parts = path.relative_to(HERE).parts
        if any(part in FORBIDDEN_DIRECTORIES or part.startswith(TEMP_PREFIXES) for part in parts):
            raise RuntimeError(f"FORBIDDEN_DIRECTORY:{relative}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise RuntimeError(f"FORBIDDEN_SUFFIX:{relative}")
        if not path.is_file() or relative.startswith(OUTPUT_PREFIXES):
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            unknown.append(relative)
            continue
        if path.stat().st_nlink != 1:
            raise RuntimeError(f"SOURCE_SINGLE_LINK_REQUIRED:{relative}")
        inventory.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_hash(path)})
    if unknown:
        raise RuntimeError(f"UNKNOWN_LOCAL_FILES:{unknown}")
    return inventory


def _manifest_check() -> dict[str, Any]:
    manifest = load(MANIFEST)
    inventory = independent_inventory()
    passed = bool(
        seal_valid(manifest)
        and manifest.get("schema") == "SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_MANIFEST_V1"
        and manifest.get("sources") == inventory
        and manifest.get("source_count") == len(inventory)
        and manifest.get("source_inventory_sha256") == canonical_hash(inventory)
        and manifest.get("trajectory_count") == 0
        and manifest.get("r2_numerical_preflight_executed") is False
    )
    return {"passed": passed, "source_count": len(inventory), "source_inventory_sha256": canonical_hash(inventory)}


def _artifact_guard() -> dict[str, Any]:
    failures: list[str] = []
    for path in HERE.rglob("*"):
        relative = path.relative_to(HERE).as_posix()
        if _is_link_or_reparse(path):
            failures.append(f"LINK:{relative}")
        if any(part in FORBIDDEN_DIRECTORIES or part.startswith(TEMP_PREFIXES) for part in path.relative_to(HERE).parts):
            failures.append(f"DIRECTORY:{relative}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"SUFFIX:{relative}")
    adapter_imports = ast.parse((HERE / "r2_raw_adapter/adapter.py").read_text(encoding="utf-8"))
    imported_names = []
    for node in ast.walk(adapter_imports):
        if isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.append(node.module)
    forbidden_imports = [name for name in imported_names if "solver" in name.lower() or "campaign" in name.lower()]
    return {"passed": not failures and not forbidden_imports, "failures": sorted(set(failures)), "forbidden_imports": forbidden_imports}


def _contract_check() -> dict[str, Any]:
    paths = [ARRAY_CONTRACT, NC_CONTRACT, GOVERNANCE, FREEZE_CONTRACT, SOURCE_BINDINGS, RUNNER_CONTRACT]
    failures: list[str] = []
    hashes: dict[str, str] = {}
    for path in paths:
        try:
            load(path)
            hashes[path.name] = file_hash(path)
        except Exception as exc:
            failures.append(f"{path.name}:{type(exc).__name__}")
    return {"passed": not failures, "contract_hashes": hashes, "failures": failures}


def _external_binding_check() -> dict[str, Any]:
    bindings = load(SOURCE_BINDINGS)
    production_root = PROJECT_ROOT / (
        "30_simulation/sim_13_physics_gated_embodied_grasping/"
        "v4_synthetic_contact_capture_diagnostic/"
        "phase_b4g_r2_post_freeze_numerical_preflight_execution/r2_preflight"
    )
    actual = {name.removesuffix(".py"): file_hash(production_root / name) for name in (
        "strict_json.py", "metrics.py", "rehydrator.py", "schedule.py", "work_energy.py", "evaluator.py",
    )}
    other = {
        "backend_source_terminal_sha256": file_hash(PROJECT_ROOT / (
            "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/"
            "phase_b4g_r2_post_freeze_numerical_preflight_execution/results/"
            "SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json"
        )),
        "common_donor_raw_sha256": file_hash(PROJECT_ROOT / (
            "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/"
            "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/evidence/raw_cases/"
            "052__RK4_REFERENCE__A1__ALPHA_16__TCMD_MS_10.json"
        )),
        "legacy_reference_force_contract_sha256": file_hash(PROJECT_ROOT / (
            "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/"
            "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/contracts/PHASE_B4G_REFERENCE_FORCE_V1.json"
        )),
        "legacy_forced_retraction_source_sha256": file_hash(PROJECT_ROOT / (
            "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/"
            "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/b4g_solver/forced_retraction.py"
        )),
        "legacy_campaign_source_sha256": file_hash(PROJECT_ROOT / (
            "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/"
            "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/b4g_solver/campaign.py"
        )),
    }
    passed = bool(actual == bindings["production_api_source_hashes"] and all(bindings[key] == value for key, value in other.items()))
    return {"passed": passed, "production_source_hashes": actual, "other_hashes": other}


def _array_schema_check() -> dict[str, Any]:
    contract = load(ARRAY_CONTRACT)
    arrays = contract.get("exact_arrays", {})
    dtype_counts = {dtype: sum(spec.get("dtype") == dtype for spec in arrays.values()) for dtype in ("<f8", "<i8", "|b1")}
    passed = bool(
        contract.get("schema") == "SIM13_V4B4G_R2_RAW_ARRAY_CONTRACT_V1"
        and contract.get("exact_array_count") == len(arrays) == 56
        and all(isinstance(spec, dict) and set(spec) == {"dtype", "shape", "unit", "meaning"} for spec in arrays.values())
        and all(spec["dtype"] in {"<f8", "<i8", "|b1"} and isinstance(spec["shape"], list) and type(spec["unit"]) is str and spec["unit"] for spec in arrays.values())
        and arrays["acquisition_event_count"]["meaning"] == "zero for A0 bookend; one otherwise"
        and contract["event_policy"]["no_removal"] == "ZERO_LENGTH_REMOVAL_INDEX_AND_TIME_ARRAYS_NO_SENTINEL_NO_NULL"
        and contract["compatibility"] == "FUTURE_R2_EXACT_SCHEMA_LEGACY_B4G_RAW_IS_INCOMPATIBLE"
    )
    return {"passed": passed, "array_count": len(arrays), "dtype_counts": dtype_counts, "canonical_sha256": canonical_hash(contract)}


def _runner_ast_check() -> dict[str, Any]:
    path = HERE / "r2_raw_adapter/runner_guard.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    expected = {"consume_authorization", "authorized_lazy_imports", "create_output_root_after_authorization", "run_registered_vnext"}
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    exact: dict[str, bool] = {}
    for name in expected:
        node = functions.get(name)
        body = [] if node is None else node.body
        exact[name] = bool(
            len(body) == 1 and isinstance(body[0], ast.Raise)
            and isinstance(body[0].exc, ast.Call)
            and isinstance(body[0].exc.func, ast.Name) and body[0].exc.func.id == "RunnerAuthorizationError"
            and len(body[0].exc.args) == 1 and isinstance(body[0].exc.args[0], ast.Name) and body[0].exc.args[0].id == "DENIAL"
        )
    contract = load(RUNNER_CONTRACT)
    return {"passed": all(exact.values()) and contract["direct_owner_source_available"] is False, "functions": exact}


def _adapter_ast_check() -> dict[str, Any]:
    path = HERE / "r2_raw_adapter/adapter.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    donor = functions.get("common_donor_projection")
    aggregate = ast.get_source_segment(source, functions["aggregate_g12_raw"]) or ""
    passed = bool(
        donor is not None and not donor.decorator_list
        and "np.frombuffer(value.tobytes(order=\"C\")" in source
        and "MappingProxyType(arrays)" in source and "_deep_freeze(sidecar)" in source
        and "_numeric_payload_sha256(case.arrays)" in aggregate
        and "len(set(numeric_payload_sha256)) != 36" in aggregate
        and "post_raw_subset_pass" in source and "partial_post_checks_pass" in source
        and "raw_pair_subpredicates_pass" not in source
    )
    return {"passed": passed, "donor_decorator_count": len(donor.decorator_list) if donor else -1, "adapter_sha256": file_hash(path)}


def _nc_receipt_check() -> dict[str, Any]:
    evidence = load(NC_EVIDENCE)
    contract = load(NC_CONTRACT)
    result = evidence.get("result", {})
    records = result.get("records", [])
    ids = [row.get("id") for row in records if isinstance(row, dict)]
    passed = bool(
        seal_valid(evidence)
        and evidence.get("status") == "PASS_EXACT_86_SOURCE_ONLY_NEGATIVE_CONTROLS_KILLED"
        and contract.get("registered_count") == 86
        and contract.get("registered_ids") == ids
        and result.get("registered_count") == result.get("executed_count") == result.get("killed_count") == 86
        and result.get("all_killed") is True
        and all(row.get("status") == "KILLED_SOURCE_ONLY" for row in records)
        and evidence.get("result_sha256") == canonical_hash(result)
        and evidence.get("trajectory_count") == 0
        and evidence.get("r2_numerical_preflight_executed") is False
    )
    return {"passed": passed, "record_count": len(records), "result_sha256": canonical_hash(result) if isinstance(result, dict) else "INVALID"}


def _validator_receipt_check() -> dict[str, Any]:
    validation = load(VALIDATION)
    manifest = load(MANIFEST)
    passed = bool(
        seal_valid(validation)
        and validation.get("status") == "PASS_R2_RAW_EVIDENCE_ADAPTER_SOURCE_VALIDATION"
        and validation.get("score", {}).get("pass") == validation.get("score", {}).get("total") == 14
        and validation.get("score", {}).get("fail") == 0
        and validation.get("source_freeze_pass_eligible") is True
        and validation.get("source_inventory_sha256") == manifest.get("source_inventory_sha256")
        and validation.get("trajectory_count") == 0
        and validation.get("r2_numerical_preflight_executed") is False
    )
    return {"passed": passed, "status": validation.get("status", "MISSING"), "document_sha256": validation.get("document_sha256", "MISSING")}


def _governance_check() -> dict[str, Any]:
    governance = load(GOVERNANCE)
    freeze = load(FREEZE_CONTRACT)
    false_keys = (
        "r2_numerical_preflight_executed", "current_system_bound", "formal_nc19_credit", "science_credit",
        "owner_credit", "production_credit", "release_credit", "full_campaign_authorized",
        "next_stage_authorized", "direct_owner_source_available", "persistent_runtime_raw_permitted",
    )
    passed = bool(
        governance["highest_permitted_gate_status"] == freeze["highest_permitted_gate_status"] == "PASS_R2_RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_ONLY"
        and governance["trajectory_count"] == freeze["trajectory_count"] == 0
        and all(governance[key] is False for key in false_keys)
        and freeze["r2_numerical_preflight_executed"] is False
        and freeze["current_system_bound"] is False
        and freeze["formal_nc19_credit"] is False
        and freeze["next_stage_authorized"] is False
    )
    return {"passed": passed, "highest_status": freeze["highest_permitted_gate_status"]}


def _legacy_hold_check() -> dict[str, Any]:
    array = load(ARRAY_CONTRACT)
    governance = load(GOVERNANCE)
    passed = bool(
        array["compatibility"] == "FUTURE_R2_EXACT_SCHEMA_LEGACY_B4G_RAW_IS_INCOMPATIBLE"
        and len(array["legacy_b4g_missing_required_arrays"]) == 12
        and governance["g12_boundary"]["full_raw_integrity_recomputed"] is False
        and governance["g12_boundary"]["source_only_candidate_predicate_pass"] is False
        and governance["g12_boundary"]["eligible"] is False
        and governance["claim_boundary"] == "RAW_P1_NARROWED_NOT_ELIMINATED_NO_NUMERICAL_OR_SCIENTIFIC_CREDIT"
    )
    return {"passed": passed, "legacy_missing_array_count": len(array["legacy_b4g_missing_required_arrays"]), "g12_status": governance["g12_boundary"]["status"]}


def _manifest_output_exclusion_check() -> dict[str, Any]:
    manifest = load(MANIFEST)
    paths = [row.get("path", "") for row in manifest.get("sources", [])]
    failures = [path for path in paths if path.startswith(OUTPUT_PREFIXES)]
    return {"passed": manifest.get("self_excluded") is True and manifest.get("acyclic") is True and not failures, "failures": failures}


def audit(*, write_output: bool = False, output_path: Path = OUTPUT) -> dict[str, Any]:
    contract = load(FREEZE_CONTRACT)
    checks: list[dict[str, Any]] = []
    def add(check_id: str, detail: dict[str, Any]) -> None:
        checks.append({"id": check_id, "pass": detail.get("passed") is True, "detail": detail})

    add("R2RAA01_MANIFEST_REHASHED_INDEPENDENTLY", _manifest_check())
    add("R2RAA02_SOURCE_ARTIFACT_AND_LINK_GUARD", _artifact_guard())
    add("R2RAA03_CONTRACT_DOCUMENTS_STRICT_AND_HASHED", _contract_check())
    add("R2RAA04_EXTERNAL_BINDING_FILES_REHASHED", _external_binding_check())
    add("R2RAA05_ARRAY_SCHEMA_56_DTYPE_SHAPE_UNIT_STATIC", _array_schema_check())
    add("R2RAA06_RUNNER_GUARD_AST_EXACT_DENIAL", _runner_ast_check())
    add("R2RAA07_ADAPTER_AST_NO_DONOR_CACHE_AND_BYTES_BACKING", _adapter_ast_check())
    add("R2RAA08_NEGATIVE_CONTROL_RECEIPT_86_ALL_KILLED", _nc_receipt_check())
    add("R2RAA09_VALIDATOR_RECEIPT_CONSISTENT", _validator_receipt_check())
    add("R2RAA10_GOVERNANCE_GATE_CEILING_AND_REQUIRED_FALSE", _governance_check())
    add("R2RAA11_LEGACY_INCOMPATIBILITY_AND_PARTIAL_G12_HOLD", _legacy_hold_check())
    add("R2RAA12_OUTPUT_CHAIN_NOT_IN_SOURCE_MANIFEST", _manifest_output_exclusion_check())
    ids_exact = [row["id"] for row in checks] == contract["audit_check_ids"]
    failed = [row["id"] for row in checks if row["pass"] is not True]
    if not ids_exact:
        failed.append("AUDIT_CHECK_ID_ORDER_DRIFT")
    manifest = load(MANIFEST)
    result = seal({
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_INDEPENDENT_SOURCE_AUDIT_V1",
        "status": contract["audit_pass_status"] if not failed else "FAIL_R2_RAW_EVIDENCE_ADAPTER_INDEPENDENT_SOURCE_AUDIT",
        "scope": "STDLIB_ONLY_INDEPENDENT_SOURCE_AUDIT_NO_VALIDATOR_IMPORT_NO_NUMPY_NO_PHYSICS_NO_TRAJECTORY",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "source_inventory_sha256": manifest["source_inventory_sha256"],
        "independent_source_freeze_pass_eligible": not failed,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "next_stage_authorized": False,
    })
    if write_output:
        write_json(output_path, result)
    return result


def _record_matches(record: Any) -> bool:
    if not isinstance(record, dict) or set(record) != {"id", "role", "path", "bytes", "sha256"}:
        return False
    relative = record["path"]
    if type(relative) is not str or "\\" in relative:
        return False
    raw = Path(relative)
    if raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
        return False
    path = PROJECT_ROOT / raw
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return False
    return bool(
        path.is_file() and not _is_link_or_reparse(path) and path.stat().st_nlink == 1
        and type(record["bytes"]) is int and record["bytes"] == path.stat().st_size
        and type(record["sha256"]) is str and record["sha256"] == file_hash(path)
    )


def verify_chain() -> dict[str, Any]:
    try:
        gate, terminal = load(GATE), load(TERMINAL)
        evidence = gate.get("evidence", [])
        records = terminal.get("records", [])
        passed = bool(
            seal_valid(gate) and seal_valid(terminal)
            and gate.get("status") == terminal.get("status") == "PASS_R2_RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_ONLY"
            and len(evidence) == 4 and all(_record_matches(row) for row in evidence)
            and len(records) == 1 and records[0].get("id") == "raw_adapter_source_freeze_gate" and _record_matches(records[0])
            and gate.get("trajectory_count") == terminal.get("trajectory_count") == 0
            and gate.get("r2_numerical_preflight_executed") is False and terminal.get("r2_numerical_preflight_executed") is False
            and gate.get("next_stage_authorized") is False and terminal.get("next_stage_authorized") is False
        )
        return {"passed": passed}
    except Exception as exc:
        return {"passed": False, "error": f"{type(exc).__name__}:{exc}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only independent raw-adapter source audit", allow_abbrev=False)
    parser.add_argument("--write-receipt", action="store_true", help="explicitly write independent audit receipt")
    args = parser.parse_args(argv)
    try:
        result = audit(write_output=args.write_receipt)
        receipt_match = args.write_receipt or (OUTPUT.is_file() and load(OUTPUT) == result)
        chain = {"passed": True, "mode": "NOT_REQUIRED_DURING_EXPLICIT_RECEIPT_GENERATION"} if args.write_receipt else verify_chain()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_R2_RAW_ADAPTER_AUDIT_EXCEPTION", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    passed = bool(result["independent_source_freeze_pass_eligible"] and receipt_match and chain.get("passed") is True)
    print(json.dumps({
        "status": result["status"] if passed else "FAIL_R2_RAW_ADAPTER_AUDIT_RECEIPT_OR_CHAIN_DRIFT",
        "score": result["score"], "mode": "WRITE_RECEIPT" if args.write_receipt else "READ_ONLY_RECEIPT_VERIFY",
        "receipt_match": receipt_match, "published_chain": chain,
        "trajectory_count": 0, "r2_numerical_preflight_executed": False,
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
