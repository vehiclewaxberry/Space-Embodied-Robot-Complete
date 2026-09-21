"""B4-1 fail-closed acceptance chain.

The script separates three outcomes:

* PASS: the stated evidence condition is proved.
* HOLD: evidence is absent, incomplete, stale, or outside the implemented audit.
* FAIL: a required contract is contradicted.

Exit codes are 0/2/1 for PASS/HOLD/FAIL respectively.  Generated evidence is
written into a run-scoped temporary directory and only published with atomic
file replacement.  ``latest_run_state.json`` is published last and is the
consumer-side guard against stale or partially published evidence.
"""

import csv
import ctypes
import gc
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import b3_lib.sw_core as core
from b3_lib.sw_core import (B3FailClosed, BuildLog, cast, connect,
                            get_com_member, open_document,
                            read_custom_properties)


V21 = Path(__file__).resolve().parents[1]
V20 = V21.parent / "Space_Embodied_Robot_CAD_V2_0"
ENGINEERING = V21.parent.parent
DESIGN_INPUTS = ENGINEERING / "design_inputs/v2_1_reference_grounded"
OUT_FINAL = V21 / "evidence/acceptance"
INVENTORY_CACHE = OUT_FINAL / ".inventory_cache"
TOP = V21 / "Assembly/Spacecraft_Service_Vehicle_V2_1.SLDASM"
V20_B601 = V20 / "06_B601_Visual_Arm"
V20_B601_TOP = V20_B601 / "SV2_B601_Visual_Arm.SLDASM"
V20_FINAL_SEAL = (
    V20 / "evidence/digital_thread/native_file_hash_manifest_v2_final.csv"
)

core.V2_ROOT = V21
core.LOG_DIR = V21 / "evidence" / "build_logs"

BLACKLIST = [8.5, 6.5, 366.0, 2.5, 6.7, 320.0, 50.8, 0.5]
WHITELIST = {
    340.5, 226.3, 113.15, 170.25, 56.75, 185.25, 160.0, 100.0,
    15.0, 12.0, 200.0, 227.0, 6.0, 105.65, 98.15, 110.15,
    104.15, 158.25, 143.25, 152.25, 62.75, 50.75, 3.0, 8.0,
    86.85, 119.15, 313.15, 238.3,
}
FORBIDDEN_WORDS = [
    "STRENGTH_PASS", "FLIGHT_QUALIFIED", "CDS-compliant",
    "space-proven", "flown", "已飞行验证", "发射合规",
    "qualified for flight", "deployment_verified",
    "global_collision_safe",
]
UNKNOWN_PARAMS = [
    "PANEL_HINGE_AXIS_Z", "PANEL_DEPLOY_ANGLE",
    "SA_ROOT_BRACKET_ENVELOPE", "HINGE_BLOCK_ENVELOPE",
    "HDRM_ENVELOPE", "SERVICE_PANEL_GAP", "HARNESS_CORRIDOR_W",
    "MAINTENANCE_CLEARANCE",
]
ALLOWED_STRUCT_CLASSES = {
    "REFERENCE",
    "LOAD_PATH_INTENT",
    "LOAD_PATH_INTENT_SHEAR_WEB",
    "NON_STRUCTURAL_PANEL",
    "VOLUME_OWNER_REFERENCE",
    "DEPLOYABLE_MODULE",
    "TOP_ASSEMBLY",
}
ALLOWED_EVIDENCE_STATES = {
    "EVIDENCE_BOUND",
    "DESIGN_PROPOSAL",
    "UNKNOWN_BLOCKED",
    "EXCLUDED",
}
SOURCE_CONTRACT_FIELDS = {
    "SOURCE_COMMIT", "SOURCE_HASH", "SOURCE_LICENSE", "ADOPTION_MODE",
}
FEATURE_FIELDS = {
    "FEATURE_ID", "SOURCE", "BORROWED_PRINCIPLE",
    "PROJECT_DIMENSION_OWNER", "ADAPTATION_RULE", "NO_DIRECT_SCALE",
    "EVIDENCE_STATE", "CLAIM_LIMIT",
}
EQUATION_RE = re.compile(
    r'^\s*"([A-Za-z_]\w*)"\s*=\s*'
    r'([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?)\s*$'
)
INVENTORY_SESSION_BATCH_SIZE = 8


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence_record(path):
    path = Path(path)
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "bytes": None,
            "sha256": None,
        }
    return {
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _atomic_write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _wait_for_process_exit(pid, timeout_ms=20000):
    """Wait for one exact Windows process without broad process cleanup."""
    if not pid:
        time.sleep(6)
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
    open_process.restype = ctypes.c_void_p
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    wait_for_single_object.restype = ctypes.c_uint32
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [ctypes.c_void_p]
    close_handle.restype = ctypes.c_bool

    synchronize = 0x00100000
    handle = open_process(synchronize, False, int(pid))
    if not handle:
        return True
    try:
        return wait_for_single_object(handle, int(timeout_ms)) == 0
    finally:
        close_handle(handle)


def _end_solidworks_session(sw, log, reason, required):
    """Close a read-only audit session and verify that its exact PID exits."""
    pid = None
    try:
        pid = int(get_com_member(sw, "GetProcessID"))
    except Exception:
        pass
    try:
        sw.CloseAllDocuments(True)
        try:
            sw.UserControl = False
        except Exception:
            pass
        get_com_member(sw, "ExitApp")
    except Exception as exc:
        log.event(
            "SW_SESSION_EXIT_ERROR",
            reason=reason,
            pid=pid,
            error=f"{type(exc).__name__}:{exc}",
        )
        if required:
            raise B3FailClosed(
                f"SolidWorks batch session exit failed: {reason}"
            ) from exc
        return False

    exited = _wait_for_process_exit(pid)
    log.event(
        "SW_SESSION_EXIT",
        reason=reason,
        pid=pid,
        exited=exited,
    )
    if required and not exited:
        raise B3FailClosed(
            f"SolidWorks batch session did not exit: pid={pid}"
        )
    return exited


def _connect_with_retry(log, attempts=4, retry_delay_seconds=30):
    """Launch/attach with bounded retries after an exited COM server."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return connect(log)
        except Exception as exc:
            last_error = exc
            log.event(
                "SW_CONNECT_RETRY",
                attempt=attempt,
                attempts=attempts,
                delay_seconds=(
                    retry_delay_seconds if attempt < attempts else 0
                ),
                error=f"{type(exc).__name__}:{exc}",
            )
            if attempt < attempts:
                time.sleep(retry_delay_seconds)
    raise B3FailClosed(
        f"SolidWorks connect failed after {attempts} attempts"
    ) from last_error


def _inventory_fingerprint(natives):
    rows = [
        {
            "file": str(path.relative_to(V21)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "mtime_ns": path.stat().st_mtime_ns,
        }
        for path in natives
    ]
    payload = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), rows


def _load_inventory_batch_cache(path, fingerprint, expected_files):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (
        payload.get("inventory_fingerprint") != fingerprint
        or payload.get("files") != expected_files
        or len(payload.get("inventory", [])) != len(expected_files)
    ):
        return None
    return payload


def _within(path, root):
    try:
        Path(path).resolve(strict=False).relative_to(
            Path(root).resolve(strict=False)
        )
        return True
    except ValueError:
        return False


def _record(results, item_id, status, code, **details):
    if status not in {"PASS", "HOLD", "FAIL"}:
        raise ValueError(f"invalid status {status!r} for {item_id}")
    row = {"status": status, "code": code}
    row.update(details)
    results[item_id] = row
    return row


def _exit_code(results):
    statuses = {row["status"] for row in results.values()}
    if "FAIL" in statuses:
        return 1
    if "HOLD" in statuses:
        return 2
    return 0


def _parse_equations(text):
    values = {}
    issues = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("'"):
            continue
        match = EQUATION_RE.fullmatch(raw)
        if not match:
            issues.append({
                "type": "malformed_or_unparsed_assignment",
                "line": line_no,
                "text": raw,
            })
            continue
        name, value = match.groups()
        if name in values:
            issues.append({
                "type": "duplicate_assignment",
                "line": line_no,
                "param": name,
            })
            continue
        try:
            values[name] = Decimal(value)
        except InvalidOperation:
            issues.append({
                "type": "invalid_decimal",
                "line": line_no,
                "param": name,
                "value": value,
            })
    return values, issues


def _source_ids_for_row(source_text, contract_ids):
    source_text = str(source_text or "")
    tokens = re.findall(r"@([A-Z][A-Z0-9_]*)", source_text)
    issues = []
    if source_text.startswith("PROJECT_ORIGINAL"):
        if tokens:
            issues.append("PROJECT_ORIGINAL_must_not_have_external_keys")
        return {"PROJECT_ORIGINAL"}, issues
    if not tokens:
        return set(), ["missing_at_source_foreign_key"]
    unknown = sorted(set(tokens) - set(contract_ids))
    if unknown:
        issues.append(f"unknown_source_ids:{unknown}")
    return set(tokens) & set(contract_ids), issues


def _find_named_values(node, names, path="$"):
    hits = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}"
            if str(key) in names:
                hits.append({"path": child, "value": value})
            hits.extend(_find_named_values(value, names, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            hits.extend(_find_named_values(value, names, f"{path}[{index}]"))
    return hits


def _load_v20_seal():
    issues = []
    rows = {}
    if not V20_FINAL_SEAL.exists():
        return rows, ["v2_0_final_seal_missing"]
    with V20_FINAL_SEAL.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"relative_path", "bytes", "sha256"}
        if not required.issubset(set(reader.fieldnames or [])):
            return rows, ["v2_0_final_seal_schema_invalid"]
        for row in reader:
            rel = str(row.get("relative_path", "")).replace("\\", "/")
            if not rel or rel in rows:
                issues.append(f"v2_0_final_seal_duplicate_or_blank:{rel}")
                continue
            rows[rel] = row
    return rows, issues


def _dependency_audit(sw, natives, run_out, run_id, v20_seal):
    rows = []
    issues = []
    limitations = []
    b601_top_seen = False
    assembly_calls = 0
    dependency_arrays = 0

    native_set = {
        str(path.resolve(strict=False)).casefold(): path for path in natives
    }
    for owner in natives:
        if owner.suffix.upper() != ".SLDASM":
            continue
        assembly_calls += 1
        try:
            raw = sw.GetDocumentDependencies2(
                str(owner), True, True, False
            )
        except Exception as exc:
            limitations.append({
                "owner": str(owner),
                "reason": f"dependency_api_error:{type(exc).__name__}:{exc}",
            })
            continue
        if not isinstance(raw, (tuple, list)):
            limitations.append({
                "owner": str(owner),
                "reason": "dependency_api_return_not_sequence",
            })
            continue
        dependency_arrays += 1
        dependencies = list(raw)[1::2]
        for dependency in dependencies:
            dep_text = str(dependency or "").strip()
            if not dep_text:
                continue
            dep = Path(dep_text)
            if not dep.is_absolute():
                dep = owner.parent / dep
            dep = dep.resolve(strict=False)
            classification = ""
            evidence = ""

            if _within(dep, V21):
                classification = "INTERNAL_V21"
                if not dep.exists():
                    issues.append(f"missing_internal_dependency:{dep}")
                elif (
                    dep.suffix.upper() in {".SLDPRT", ".SLDASM"}
                    and str(dep).casefold() not in native_set
                ):
                    issues.append(f"unscanned_internal_native:{dep}")
            elif _within(dep, V20_B601):
                classification = "ALLOWED_EXTERNAL_V20_B601"
                if dep == V20_B601_TOP.resolve(strict=False):
                    b601_top_seen = True
                if not dep.exists():
                    issues.append(f"missing_v20_b601_dependency:{dep}")
                else:
                    rel_v20 = str(
                        dep.relative_to(V20.resolve(strict=False))
                    ).replace("\\", "/")
                    sealed = v20_seal.get(rel_v20)
                    if not sealed:
                        issues.append(f"v20_b601_not_in_final_seal:{rel_v20}")
                    else:
                        actual_hash = _sha256(dep)
                        actual_bytes = dep.stat().st_size
                        if (
                            actual_hash.casefold()
                            != str(sealed.get("sha256", "")).casefold()
                            or actual_bytes != int(sealed.get("bytes", -1))
                        ):
                            issues.append(
                                f"v20_b601_final_seal_mismatch:{rel_v20}"
                            )
                        evidence = actual_hash
            else:
                classification = "UNEXPECTED_EXTERNAL"
                issues.append(f"unexpected_external_dependency:{owner}:{dep}")

            rows.append({
                "owner": str(owner.relative_to(V21)).replace("\\", "/"),
                "dependency": str(dep),
                "classification": classification,
                "evidence_sha256": evidence,
            })

    if not b601_top_seen:
        limitations.append({
            "owner": str(TOP),
            "reason": "expected_V2_0_B601_top_dependency_not_observed",
        })
    report = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "assembly_calls": assembly_calls,
        "dependency_arrays": dependency_arrays,
        "allowed_external_root": str(V20_B601),
        "required_external_top": str(V20_B601_TOP),
        "b601_top_seen": b601_top_seen,
        "issues": issues,
        "limitations": limitations,
        "rows": rows,
    }
    (run_out / "dependency_graph_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return issues, limitations, report


def _publish_run(run_out, final_out):
    files = sorted(
        path for path in run_out.rglob("*") if path.is_file()
    )
    for source in files:
        relative = source.relative_to(run_out)
        destination = final_out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)


def _static_self_test():
    values, issues = _parse_equations(
        "' comment\n\"A\"=1\n\"B\" = -2.5E+1\n"
    )
    assert not issues
    assert values == {"A": Decimal("1"), "B": Decimal("-25")}
    _, duplicate_issues = _parse_equations("\"A\"=1\n\"A\"=2\n")
    assert any(row["type"] == "duplicate_assignment"
               for row in duplicate_issues)
    ids = {"PROJECT_ORIGINAL", "CDS_REV_14_1"}
    resolved, source_issues = _source_ids_for_row(
        "PROJECT_ORIGINAL（project-owned）", ids
    )
    assert resolved == {"PROJECT_ORIGINAL"} and not source_issues
    resolved, source_issues = _source_ids_for_row(
        "RULE@CDS_REV_14_1", ids
    )
    assert resolved == {"CDS_REV_14_1"} and not source_issues
    _, source_issues = _source_ids_for_row("RULE@UNKNOWN_SOURCE", ids)
    assert source_issues
    assert _exit_code({"x": {"status": "PASS"}}) == 0
    assert _exit_code({"x": {"status": "HOLD"}}) == 2
    assert _exit_code({"x": {"status": "FAIL"}}) == 1
    assert _within(V21 / "x", V21)
    assert not _within(V20, V21)

    # Static checks against the checked-in acceptance contracts.  These do not
    # import, start, or connect to SolidWorks.
    equation_path = V21 / "System_Equations_V2_1.txt"
    current_values, current_equation_issues = _parse_equations(
        equation_path.read_text(encoding="utf-8")
    )
    assert current_values
    assert not current_equation_issues
    assert not (set(current_values) & set(UNKNOWN_PARAMS))

    matrix_path = (
        DESIGN_INPUTS
        / "02_feature_adoption/open_source_feature_adoption_matrix.yaml"
    )
    manifest_path = (
        DESIGN_INPUTS
        / "01_source_admission/source_admission_manifest.yaml"
    )
    current_matrix = yaml.safe_load(
        matrix_path.read_text(encoding="utf-8")
    )
    current_manifest = yaml.safe_load(
        manifest_path.read_text(encoding="utf-8")
    )
    current_contract = current_matrix["source_resolution_contract"]
    current_ids = set(current_contract) - {"rule"}
    assert len(current_ids) == 6
    for source_id in current_ids:
        source_record = current_contract[source_id]
        assert SOURCE_CONTRACT_FIELDS.issubset(source_record)
        assert all(source_record[field] not in (None, "")
                   for field in SOURCE_CONTRACT_FIELDS)
    current_features = current_matrix["features"]
    assert len(current_features) == 37
    seen_feature_ids = set()
    for row in current_features:
        assert FEATURE_FIELDS.issubset(row)
        assert all(row[field] not in (None, "")
                   for field in FEATURE_FIELDS)
        assert row["NO_DIRECT_SCALE"] is True
        feature_id = row["FEATURE_ID"]
        assert feature_id not in seen_feature_ids
        seen_feature_ids.add(feature_id)
        resolved, row_issues = _source_ids_for_row(
            row["SOURCE"], current_ids
        )
        assert resolved and not row_issues
    manifest_ids = {
        row["source_id"] for row in current_manifest["sources"]
    }
    assert manifest_ids == current_ids - {"PROJECT_ORIGINAL"}

    current_rulings = yaml.safe_load(
        (
            DESIGN_INPUTS
            / "05_adversarial_review/human_conflict_rulings.yaml"
        ).read_text(encoding="utf-8")
    )
    assert (
        current_rulings["rulings"]["C1"]["decision"]
        == "规则3机制扩展"
    )
    assert (
        current_rulings["b4_1_authorization"]["HUMAN_APPROVAL"]
        == "GRANTED"
    )

    seal, seal_issues = _load_v20_seal()
    assert not seal_issues
    b601_rel = str(
        V20_B601_TOP.relative_to(V20)
    ).replace("\\", "/")
    assert b601_rel in seal
    assert V20_B601_TOP.exists()
    assert _sha256(V20_B601_TOP).casefold() == str(
        seal[b601_rel]["sha256"]
    ).casefold()
    print("B4_1_ACCEPTANCE_STATIC_SELF_TEST_PASS")
    return 0


def _run_acceptance(run_out, run_id, now):
    log = BuildLog("b4_1_acceptance")
    results = {}

    input_paths = {
        "acceptance_script": Path(__file__).resolve(),
        "system_equations": V21 / "System_Equations_V2_1.txt",
        "b4_1_build_spec": V21 / "automation/b4_1_build_spec.yaml",
        "v2_0_baseline_spec": V20 / "automation/b3_build_spec.yaml",
        "feature_adoption_matrix": (
            DESIGN_INPUTS
            / "02_feature_adoption/open_source_feature_adoption_matrix.yaml"
        ),
        "source_admission_manifest": (
            DESIGN_INPUTS
            / "01_source_admission/source_admission_manifest.yaml"
        ),
        "human_conflict_rulings": (
            DESIGN_INPUTS
            / "05_adversarial_review/human_conflict_rulings.yaml"
        ),
        "drawing_register": (
            DESIGN_INPUTS
            / "04_cad_preparation/v2_1_drawing_register.yaml"
        ),
        "red_team_corrections": (
            DESIGN_INPUTS
            / "05_adversarial_review/red_team_corrections_20260725.yaml"
        ),
        "machine_check": V21 / "evidence/b4_1_verify/machine_check.json",
        "fastener_register": (
            OUT_FINAL / "SV21_fastener_register.csv"
        ),
        "v2_0_final_seal": V20_FINAL_SEAL,
    }
    input_evidence = {
        key: _evidence_record(path) for key, path in input_paths.items()
    }
    missing_required = [
        key for key in (
            "system_equations", "b4_1_build_spec",
            "feature_adoption_matrix", "source_admission_manifest",
            "human_conflict_rulings", "drawing_register",
            "v2_0_final_seal",
        )
        if not input_evidence[key]["exists"]
    ]
    if missing_required:
        _record(
            results, "G0_required_inputs", "FAIL",
            "REQUIRED_INPUTS_MISSING", missing=missing_required,
        )
        raise B3FailClosed(f"required inputs missing: {missing_required}")
    _record(
        results, "G0_required_inputs", "PASS",
        "REQUIRED_INPUTS_PRESENT_AND_HASHED",
        evidence=list(input_evidence),
    )
    (run_out / "input_evidence_hashes.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_utc": now,
            "inputs": input_evidence,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    build_spec = yaml.safe_load(
        input_paths["b4_1_build_spec"].read_text(encoding="utf-8")
    )
    matrix = yaml.safe_load(
        input_paths["feature_adoption_matrix"].read_text(encoding="utf-8")
    )
    source_manifest = yaml.safe_load(
        input_paths["source_admission_manifest"].read_text(encoding="utf-8")
    )
    human_rulings = yaml.safe_load(
        input_paths["human_conflict_rulings"].read_text(encoding="utf-8")
    )
    drawing_register = yaml.safe_load(
        input_paths["drawing_register"].read_text(encoding="utf-8")
    )

    natives = (
        sorted(V21.rglob("*.SLDPRT"))
        + sorted(V21.rglob("*.SLDASM"))
    )
    inventory_fingerprint, inventory_snapshot = _inventory_fingerprint(
        natives
    )
    INVENTORY_CACHE.mkdir(parents=True, exist_ok=True)
    (run_out / "inventory_input_snapshot.json").write_text(
        json.dumps({
            "run_id": run_id,
            "inventory_fingerprint": inventory_fingerprint,
            "batch_size": INVENTORY_SESSION_BATCH_SIZE,
            "files": inventory_snapshot,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    inventory = []
    imported_hits = []
    for start in range(0, len(natives), INVENTORY_SESSION_BATCH_SIZE):
        batch_number = start // INVENTORY_SESSION_BATCH_SIZE + 1
        batch_paths = natives[
            start:start + INVENTORY_SESSION_BATCH_SIZE
        ]
        expected_files = [
            str(path.relative_to(V21)).replace("\\", "/")
            for path in batch_paths
        ]
        cache_path = (
            INVENTORY_CACHE
            / f"{inventory_fingerprint}_batch_{batch_number:02d}.json"
        )
        cached = _load_inventory_batch_cache(
            cache_path, inventory_fingerprint, expected_files
        )
        if cached is not None:
            inventory.extend(cached["inventory"])
            imported_hits.extend(cached.get("imported_hits", []))
            log.event(
                "INVENTORY_BATCH_CACHE_HIT",
                batch=batch_number,
                files=len(expected_files),
                cache=str(cache_path),
            )
            continue

        sw = _connect_with_retry(log)
        sw.CloseAllDocuments(True)
        log.event(
            "INVENTORY_BATCH_START",
            batch=batch_number,
            first_index=start,
            batch_size=len(batch_paths),
        )
        batch_inventory = []
        batch_imported_hits = []
        for path in batch_paths:
            model = open_document(sw, log, path, read_only=True)
            properties = read_custom_properties(model)
            feature_types = []
            feature = cast(
                get_com_member(model, "FirstFeature"), "IFeature"
            )
            while feature is not None:
                feature_type = str(
                    get_com_member(feature, "GetTypeName2")
                )
                feature_types.append(feature_type)
                if "Import" in feature_type:
                    batch_imported_hits.append({
                        "file": str(
                            path.relative_to(V21)
                        ).replace("\\", "/"),
                        "feature_type": feature_type,
                    })
                feature = cast(
                    get_com_member(feature, "GetNextFeature"), "IFeature"
                )
            batch_inventory.append({
                "file": str(path.relative_to(V21)).replace("\\", "/"),
                "props": properties,
                "feature_types": feature_types,
            })
            # pywin32 retains COM wrappers until Python's collector runs.
            feature = None
            model = None
            sw.CloseAllDocuments(True)
            gc.collect()

        _end_solidworks_session(
            sw,
            log,
            reason=f"inventory_batch_{batch_number}",
            required=True,
        )
        sw = None
        gc.collect()
        _atomic_write_json(cache_path, {
            "inventory_fingerprint": inventory_fingerprint,
            "batch": batch_number,
            "files": expected_files,
            "inventory": batch_inventory,
            "imported_hits": batch_imported_hits,
        })
        inventory.extend(batch_inventory)
        imported_hits.extend(batch_imported_hits)
        log.event(
            "INVENTORY_BATCH_CACHED",
            batch=batch_number,
            files=len(batch_inventory),
            cache=str(cache_path),
        )
        time.sleep(15)
    log.event("INVENTORY_DONE", files=len(inventory))
    sw = _connect_with_retry(log)

    native_hash_rows = []
    for path in natives:
        native_hash_rows.append({
            "file": str(path.relative_to(V21)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "mtime_utc": datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).isoformat(),
            "sha256": _sha256(path),
        })
    with (run_out / "native_file_hash_manifest_v2_1.csv").open(
            "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file", "bytes", "mtime_utc", "sha256"],
        )
        writer.writeheader()
        writer.writerows(native_hash_rows)

    # A1: document-level semantic contract.
    semantic_rows = []
    a1_issues = []
    object_ids = {}
    for item in inventory:
        props = item["props"]
        short_class = str(props.get("STRUCT_CLASS", "")).strip()
        long_class = str(props.get("STRUCTURE_CLASS", "")).strip()
        struct_class = short_class or long_class
        object_id = str(props.get("OBJECT_ID", "")).strip()
        evidence_state = str(props.get("EVIDENCE_STATE", "")).strip()
        semantic_rows.append({
            "file": item["file"],
            "struct_class": struct_class,
            "structure_class_mirror": long_class,
            "object_id": object_id,
            "evidence_state": evidence_state,
        })
        if not short_class:
            a1_issues.append(f"missing_STRUCT_CLASS:{item['file']}")
        if long_class and short_class != long_class:
            a1_issues.append(f"class_mismatch:{item['file']}")
        if struct_class not in ALLOWED_STRUCT_CLASSES:
            a1_issues.append(
                f"invalid_struct_class:{item['file']}:{struct_class}"
            )
        if not object_id:
            a1_issues.append(f"missing_OBJECT_ID:{item['file']}")
        else:
            object_ids.setdefault(object_id, []).append(item["file"])
        if evidence_state not in ALLOWED_EVIDENCE_STATES:
            a1_issues.append(
                f"invalid_evidence_state:{item['file']}:{evidence_state}"
            )
    for object_id, files in object_ids.items():
        if len(files) > 1:
            a1_issues.append(
                f"duplicate_object_id:{object_id}:{files}"
            )
    (run_out / "v2_1_structure_semantic_register.yaml").write_text(
        yaml.safe_dump({
            "run_id": run_id,
            "generated_utc": now,
            "allowed_struct_classes": sorted(ALLOWED_STRUCT_CLASSES),
            "allowed_evidence_states": sorted(ALLOWED_EVIDENCE_STATES),
            "entries": semantic_rows,
            "issues": a1_issues,
            "claim_limit": (
                "document-level custom properties only; "
                "configuration-specific properties are not audited"
            ),
        }, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _record(
        results, "A1_semantic_register",
        "PASS" if not a1_issues else "FAIL",
        (
            "DOCUMENT_SEMANTIC_ENUMS_AND_IDS_VALID"
            if not a1_issues else "DOCUMENT_SEMANTIC_CONTRACT_VIOLATION"
        ),
        issues=a1_issues,
    )

    # A2 and A7: exact equation parser and PARAM_* set equality.
    equation_text = input_paths["system_equations"].read_text(
        encoding="utf-8"
    )
    equation_values, equation_issues = _parse_equations(equation_text)
    skeleton_items = [
        item for item in inventory
        if item["file"]
        == "00_Master_Skeleton/Master_Skeleton_V2_1.SLDPRT"
    ]
    a2_issues = list(equation_issues)
    ledger = []
    skeleton_props = {}
    if len(skeleton_items) != 1:
        a2_issues.append({
            "type": "master_skeleton_exact_path_count",
            "count": len(skeleton_items),
        })
    else:
        skeleton_props = skeleton_items[0]["props"]
    actual_param_names = {
        key[6:] for key in skeleton_props if key.startswith("PARAM_")
    }
    expected_param_names = set(equation_values) | set(UNKNOWN_PARAMS)
    for extra in sorted(actual_param_names - expected_param_names):
        a2_issues.append({
            "type": "unexpected_skeleton_param", "param": extra,
        })
    for missing in sorted(expected_param_names - actual_param_names):
        a2_issues.append({
            "type": "missing_skeleton_param", "param": missing,
        })
    equation_hash = input_evidence["system_equations"]["sha256"]
    human_hash = input_evidence["human_conflict_rulings"]["sha256"]
    baseline_hash = input_evidence["v2_0_baseline_spec"]["sha256"]
    for name, value in equation_values.items():
        property_value = skeleton_props.get(f"PARAM_{name}")
        if name in {"LONGERON_OFFSET_Y", "LONGERON_OFFSET_Z"}:
            value_state = "V2_0_DISPLAY_BASELINE_ONLY"
            evidence_ref = str(input_paths["v2_0_baseline_spec"])
            source_hash = baseline_hash
        elif name in {"SIDE_PANEL_SPLIT_X", "STOW_OVERHANG_Z"}:
            value_state = "HUMAN_RULED_DERIVED"
            evidence_ref = str(input_paths["human_conflict_rulings"])
            source_hash = human_hash
        else:
            value_state = "FROZEN_INHERITED_OR_DERIVED"
            evidence_ref = str(input_paths["system_equations"])
            source_hash = equation_hash
        ledger.append({
            "param": name,
            "equations_value": str(value),
            "skeleton_prop": property_value,
            "value_state": value_state,
            "owner": str(input_paths["system_equations"]),
            "evidence_ref": evidence_ref,
            "source_hash": source_hash,
        })
        try:
            if property_value is None:
                raise InvalidOperation
            if Decimal(str(property_value).strip()) != value:
                a2_issues.append({
                    "type": "equation_property_mismatch",
                    "param": name,
                    "equation": str(value),
                    "property": property_value,
                })
        except (InvalidOperation, ValueError):
            a2_issues.append({
                "type": "non_numeric_or_missing_skeleton_property",
                "param": name,
                "property": property_value,
            })
    a7_issues = []
    for name in UNKNOWN_PARAMS:
        property_value = skeleton_props.get(f"PARAM_{name}")
        ledger.append({
            "param": name,
            "equations_value": "NOT_ASSIGNED_NAMED_ONLY",
            "skeleton_prop": property_value,
            "value_state": "UNKNOWN",
            "owner": "H5",
            "evidence_ref": str(input_paths["b4_1_build_spec"]),
            "source_hash": input_evidence["b4_1_build_spec"]["sha256"],
        })
        if name in equation_values:
            a7_issues.append(f"numeric_equation_for_UNKNOWN:{name}")
        if property_value != "UNKNOWN":
            a7_issues.append(
                f"UNKNOWN_property_not_exact:{name}:{property_value}"
            )
    for hit in _find_named_values(build_spec, set(UNKNOWN_PARAMS)):
        if hit["value"] not in (None, "UNKNOWN", "TBD"):
            a7_issues.append(
                f"numeric_or_resolved_build_spec_UNKNOWN:"
                f"{hit['path']}={hit['value']}"
            )
    (run_out / "parameter_provenance_ledger.yaml").write_text(
        yaml.safe_dump({
            "run_id": run_id,
            "generated_utc": now,
            "ledger": ledger,
            "equation_parse_issues": equation_issues,
            "a2_issues": a2_issues,
            "a7_issues": a7_issues,
        }, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _record(
        results, "A2_parameter_ledger",
        "PASS" if not a2_issues else "FAIL",
        (
            "EQUATION_AND_PARAM_SET_EXACT_MATCH"
            if not a2_issues else "PARAMETER_LEDGER_CONTRACT_VIOLATION"
        ),
        issues=a2_issues,
    )
    _record(
        results, "A7_unknown_integrity",
        "PASS" if not a7_issues else "FAIL",
        (
            "UNKNOWN_PARAMS_EXACT_AND_UNASSIGNED"
            if not a7_issues else "UNKNOWN_PARAM_CONTRACT_VIOLATION"
        ),
        issues=a7_issues,
    )

    # A3: the current lint is deliberately non-dispositive.
    blacklist_hits = []
    number_re = re.compile(r"-?\d+\.?\d*")
    for item in inventory:
        blob = json.dumps(item["props"], ensure_ascii=False)
        for token in number_re.findall(blob):
            try:
                value = abs(float(token))
            except ValueError:
                continue
            for forbidden in BLACKLIST:
                if (
                    value not in WHITELIST
                    and abs(value - forbidden)
                    <= max(abs(forbidden) * 0.005, 1e-12)
                ):
                    blacklist_hits.append({
                        "file": item["file"],
                        "value": value,
                        "blacklist_value": forbidden,
                    })
    (run_out / "blacklist_numbers_lint.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_utc": now,
            "blacklist": BLACKLIST,
            "hits": blacklist_hits,
            "status": "HOLD",
            "reason": (
                "custom-property numeric coincidence is neither a complete "
                "geometry scan nor proof of source lineage"
            ),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _record(
        results, "A3_blacklist_lint", "HOLD",
        (
            "BLACKLIST_HITS_REQUIRE_PROVENANCE_REVIEW"
            if blacklist_hits
            else "SCAN_SCOPE_INCOMPLETE_NO_LINEAGE_CONCLUSION"
        ),
        hits=len(blacklist_hits),
    )

    # Dependency graph and A4 zero-lineage checks.
    v20_seal, seal_issues = _load_v20_seal()
    dependency_issues, dependency_limits, dependency_report = (
        _dependency_audit(
            sw, natives, run_out, run_id, v20_seal
        )
    )
    dependency_issues = seal_issues + dependency_issues
    if dependency_issues:
        _record(
            results, "D1_dependency_graph", "FAIL",
            "DEPENDENCY_OR_V2_0_SEAL_CONTRADICTION",
            issues=dependency_issues,
            limitations=dependency_limits,
        )
    elif dependency_limits:
        _record(
            results, "D1_dependency_graph", "HOLD",
            "DEPENDENCY_GRAPH_INCOMPLETE",
            limitations=dependency_limits,
        )
    else:
        _record(
            results, "D1_dependency_graph", "PASS",
            "ONLY_V21_AND_PINNED_V2_0_B601_DEPENDENCIES",
            rows=len(dependency_report["rows"]),
        )
    if imported_hits or dependency_issues:
        a4_status = "FAIL"
        a4_code = "IMPORTED_FEATURE_OR_EXTERNAL_DEPENDENCY_CONTRADICTION"
    else:
        a4_status = "HOLD"
        a4_code = (
            "DEPENDENCY_INCOMPLETE_AND_GEOMETRY_SIGNATURE_NOT_IMPLEMENTED"
            if dependency_limits
            else "GEOMETRY_SIGNATURE_COMPARISON_NOT_IMPLEMENTED"
        )
    _record(
        results, "A4_zero_lineage", a4_status, a4_code,
        imported_features=imported_hits,
        dependency_issues=dependency_issues,
        dependency_limitations=dependency_limits,
    )
    (run_out / "zero_lineage_check.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_utc": now,
            "native_files": len(natives),
            "imported_features": imported_hits,
            "native_hash_manifest": "native_file_hash_manifest_v2_1.csv",
            "dependency_graph": "dependency_graph_check.json",
            "geometry_signature_comparison": "NOT_IMPLEMENTED_HOLD",
            "status": a4_status,
            "code": a4_code,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # A5: atomically resolve every source foreign key and contract record.
    source_contract = matrix.get("source_resolution_contract", {})
    contract_ids = set(source_contract) - {"rule"}
    matrix_issues = []
    contract_issues = []
    for source_id in sorted(contract_ids):
        record = source_contract.get(source_id)
        if not isinstance(record, dict):
            contract_issues.append(
                f"source_contract_not_mapping:{source_id}"
            )
            continue
        missing = sorted(
            field for field in SOURCE_CONTRACT_FIELDS
            if field not in record or record.get(field) in (None, "")
        )
        if missing:
            contract_issues.append(
                f"source_contract_missing_fields:{source_id}:{missing}"
            )
    manifest_source_ids = {
        row.get("source_id")
        for row in source_manifest.get("sources", [])
        if isinstance(row, dict)
    }
    expected_external = contract_ids - {"PROJECT_ORIGINAL"}
    if manifest_source_ids != expected_external:
        contract_issues.append({
            "type": "manifest_contract_source_set_mismatch",
            "manifest": sorted(manifest_source_ids),
            "contract": sorted(expected_external),
        })
    features = matrix.get("features", [])
    if not isinstance(features, list) or not features:
        matrix_issues.append("features_missing_or_empty")
        features = []
    feature_ids = {}
    resolved_rows = []
    for row in features:
        if not isinstance(row, dict):
            matrix_issues.append("feature_row_not_mapping")
            continue
        missing = sorted(
            field for field in FEATURE_FIELDS
            if field not in row or row.get(field) in (None, "")
        )
        feature_id = str(row.get("FEATURE_ID", "")).strip()
        if feature_id:
            feature_ids.setdefault(feature_id, 0)
            feature_ids[feature_id] += 1
        resolved, resolution_issues = _source_ids_for_row(
            row.get("SOURCE"), contract_ids
        )
        if not resolved:
            resolution_issues.append("no_resolved_source_id")
        if row.get("NO_DIRECT_SCALE") is not True:
            resolution_issues.append("NO_DIRECT_SCALE_not_true")
        if missing or resolution_issues:
            matrix_issues.append({
                "feature": feature_id,
                "missing": missing,
                "source_issues": resolution_issues,
            })
        resolved_rows.append({
            "feature": feature_id,
            "source_text": row.get("SOURCE"),
            "resolved_sources": sorted(resolved),
        })
    for feature_id, count in feature_ids.items():
        if count != 1:
            matrix_issues.append(
                f"duplicate_feature_id:{feature_id}:{count}"
            )
    all_a5_issues = contract_issues + matrix_issues
    license_rows = []
    for source_id in sorted(contract_ids):
        record = source_contract.get(source_id)
        if not isinstance(record, dict):
            continue
        license_rows.append({
            "source_id": source_id,
            "source_commit": record.get("SOURCE_COMMIT"),
            "source_hash": record.get("SOURCE_HASH"),
            "source_license": record.get("SOURCE_LICENSE"),
            "adoption_mode": record.get("ADOPTION_MODE"),
        })
    (run_out / "license_attribution_register.yaml").write_text(
        yaml.safe_dump({
            "run_id": run_id,
            "generated_utc": now,
            "matrix_sha256": input_evidence[
                "feature_adoption_matrix"
            ]["sha256"],
            "source_manifest_sha256": input_evidence[
                "source_admission_manifest"
            ]["sha256"],
            "rows": license_rows,
            "issues": all_a5_issues,
            "geometry_lineage_claim": (
                "No file-level source adoption is authorized. "
                "A4 remains HOLD until geometry-signature comparison exists."
            ),
        }, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (run_out / "feature_source_resolution_check.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_utc": now,
            "feature_rows": len(features),
            "source_contract_ids": sorted(contract_ids),
            "resolved_rows": resolved_rows,
            "issues": all_a5_issues,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _record(
        results, "A5_license_and_source_resolution",
        "PASS" if not all_a5_issues else "FAIL",
        (
            "ALL_SOURCE_KEYS_AND_CONTRACT_FIELDS_RESOLVED"
            if not all_a5_issues else "SOURCE_RESOLUTION_CONTRACT_VIOLATION"
        ),
        feature_rows=len(features),
        contract_ids=sorted(contract_ids),
        issues=all_a5_issues,
    )

    # A6: broad text lint is review evidence, not a semantic claim prover.
    claim_hits = []
    scan_extensions = {".txt", ".yaml", ".yml", ".json", ".csv", ".md"}
    scan_roots = [V21, DESIGN_INPUTS]
    scan_files = []
    for root in scan_roots:
        for path in root.rglob("*"):
            if (
                path.is_file()
                and path.suffix.casefold() in scan_extensions
                and not _within(path, run_out)
            ):
                scan_files.append(path)
    for item in inventory:
        blob = json.dumps(item["props"], ensure_ascii=False)
        for word in FORBIDDEN_WORDS:
            if word.casefold() in blob.casefold():
                claim_hits.append({
                    "file": item["file"],
                    "word": word,
                    "scope": "native_custom_properties",
                })
    for path in sorted(set(scan_files)):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for word in FORBIDDEN_WORDS:
            if word.casefold() in text.casefold():
                claim_hits.append({
                    "file": str(path),
                    "word": word,
                    "scope": "delivery_text",
                })
    (run_out / "claim_firewall_lint.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_utc": now,
            "files_scanned": len(set(scan_files)),
            "forbidden_words": FORBIDDEN_WORDS,
            "hits": claim_hits,
            "status": "HOLD",
            "reason": (
                "phrase hits require semantic review because negations and "
                "prohibited-claim registers also contain these terms"
            ),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _record(
        results, "A6_claim_firewall", "HOLD",
        (
            "CLAIM_PHRASES_REQUIRE_SEMANTIC_REVIEW"
            if claim_hits else "NO_PHRASE_HIT_BUT_SEMANTIC_PROOF_ABSENT"
        ),
        hits=len(claim_hits),
        files_scanned=len(set(scan_files)),
    )

    # C1: validate the human ruling and deck classification, but do not claim
    # CAD openings that the builder did not create.
    c1_issues = []
    c1 = human_rulings.get("rulings", {}).get("C1", {})
    if c1.get("decision") != "规则3机制扩展":
        c1_issues.append("C1_human_ruling_missing_or_changed")
    authorization = human_rulings.get("b4_1_authorization", {})
    if authorization.get("HUMAN_APPROVAL") != "GRANTED":
        c1_issues.append("B4_1_human_authorization_not_granted")
    deck_expectations = {
        "02_Equipment_Decks/parts/DECK_REAR_MID.SLDPRT",
        "02_Equipment_Decks/parts/DECK_MID_FRONT.SLDPRT",
    }
    inventory_by_file = {item["file"]: item for item in inventory}
    for deck in sorted(deck_expectations):
        item = inventory_by_file.get(deck)
        if not item:
            c1_issues.append(f"required_deck_missing:{deck}")
        elif (
            item["props"].get("STRUCT_CLASS")
            != "LOAD_PATH_INTENT_SHEAR_WEB"
        ):
            c1_issues.append(f"deck_class_contradiction:{deck}")
    opening_table = {
        "run_id": run_id,
        "generated_utc": now,
        "ruling": "C1 规则3机制扩展",
        "human_ruling_sha256": input_evidence[
            "human_conflict_rulings"
        ]["sha256"],
        "verification_status": (
            "FAIL" if c1_issues else "HOLD_REGISTER_ONLY"
        ),
        "issues": c1_issues,
        "allocations": [
            {
                "member": "DECK_REAR_MID",
                "class": "LOAD_PATH_INTENT_SHEAR_WEB",
                "openings": [{
                    "type": "CABLE_PASSAGE",
                    "station": "named:DECK_PASSAGE_REAR_MID",
                    "diameter": "UNKNOWN",
                    "doubler_intent": True,
                    "owner": "electrical_integration",
                    "cad_feature_state": "NOT_CREATED_HOLD",
                }],
            },
            {
                "member": "DECK_MID_FRONT",
                "class": "LOAD_PATH_INTENT_SHEAR_WEB",
                "openings": [{
                    "type": "CABLE_PASSAGE",
                    "station": "named:DECK_PASSAGE_MID_FRONT",
                    "diameter": "UNKNOWN",
                    "doubler_intent": True,
                    "owner": "electrical_integration",
                    "cad_feature_state": "NOT_CREATED_HOLD",
                }],
            },
            {
                "member": "FRM_* / LNG_*",
                "class": "LOAD_PATH_INTENT",
                "openings": (
                    "FORBIDDEN; service openings belong only to "
                    "NON_STRUCTURAL_PANEL/VISUAL_COVER"
                ),
            },
        ],
        "claim_limit": (
            "The two deck bodies are whole extrusions.  This register does "
            "not prove a named CAD opening, doubler, or physical clearance."
        ),
    }
    (run_out / "opening_allocation_table.yaml").write_text(
        yaml.safe_dump(
            opening_table, allow_unicode=True, sort_keys=False
        ),
        encoding="utf-8",
    )
    _record(
        results, "C1_opening_allocation",
        "FAIL" if c1_issues else "HOLD",
        (
            "C1_RULING_OR_DECK_CONTRADICTION"
            if c1_issues else "REGISTER_ONLY_NO_NAMED_CAD_OPENINGS"
        ),
        issues=c1_issues,
    )

    # A8-A20 evidence contracts.
    machine = {}
    if input_paths["machine_check"].exists():
        machine = json.loads(
            input_paths["machine_check"].read_text(encoding="utf-8")
        )
    keepout_ids = {
        row.get("id")
        for row in build_spec.get("solar_mechanism", {}).get(
            "keepouts", []
        )
        if isinstance(row, dict)
    }
    expected_keepouts = {
        "PANEL_SWEEP_KEEPOUT_L",
        "PANEL_SWEEP_KEEPOUT_R",
        "STOW_OVERHANG_KEEPOUT",
    }
    a8_status = (
        "HOLD" if expected_keepouts.issubset(keepout_ids) else "FAIL"
    )
    a8_code = (
        "REGISTERED_NAMES_ONLY_NO_VERSIONED_CAD_KEEPOUT_ASSETS"
        if a8_status == "HOLD" else "REQUIRED_KEEPOUT_IDS_MISSING"
    )
    _record(
        results, "A8_keepout_asset_family", a8_status, a8_code,
        registered=sorted(keepout_ids),
        expected=sorted(expected_keepouts),
    )

    state_names = set(build_spec.get("state_family", {}))
    machine_states = machine.get("states", {})
    a9_contradictions = []
    a9_limitations = []
    if machine:
        if machine.get("verdict") == "B4_1_MACHINE_CHECK_FAIL":
            a9_contradictions.append("machine_verdict_FAIL")
        if set(machine_states) != state_names:
            a9_contradictions.append({
                "state_set_mismatch": {
                    "machine": sorted(machine_states),
                    "spec": sorted(state_names),
                }
            })
        for state in sorted(state_names & set(machine_states)):
            if machine_states[state].get("match") is not True:
                a9_contradictions.append(f"state_mismatch:{state}")
        if machine.get("failures"):
            a9_contradictions.append({
                "machine_failures": machine.get("failures"),
            })
        reopen = machine.get("reopen", {})
        if (
            reopen.get("total") != len(natives)
            or reopen.get("pass") != len(natives)
        ):
            a9_contradictions.append({
                "reopen_count_mismatch": {
                    "machine": reopen,
                    "current_native_count": len(natives),
                }
            })
        if any(value is not True for value in machine.get("bbox", {}).values()):
            a9_contradictions.append("bbox_check_not_all_true")
        if any(
            value is not True
            for value in machine.get("zero_solid", {}).values()
        ):
            a9_contradictions.append("zero_solid_check_not_all_true")
        try:
            generated = datetime.fromisoformat(
                machine["generated_utc"].replace("Z", "+00:00")
            )
            newest_native = max(
                datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                )
                for path in natives
            )
            if generated < newest_native:
                a9_limitations.append(
                    "machine_check_older_than_current_native_file"
                )
        except (KeyError, TypeError, ValueError):
            a9_limitations.append(
                "machine_check_timestamp_missing_or_invalid"
            )
    else:
        a9_limitations.append("machine_check_missing")
    a9_limitations.extend([
        "machine_check_has_no_native_input_hash_binding",
        "SpeedPak_or_equivalent_performance_configurations_absent",
    ])
    if a9_contradictions:
        a9_status = "FAIL"
        a9_code = "STATE_MACHINE_CHECK_CONTRADICTION"
    else:
        a9_status = "HOLD"
        a9_code = (
            "STATE_AXIS_REVIEWED_BUT_PERFORMANCE_MATRIX_UNPROVED"
        )
    _record(
        results, "A9_state_x_performance_matrix",
        a9_status, a9_code,
        contradictions=a9_contradictions,
        limitations=a9_limitations,
        machine_check_sha256=input_evidence["machine_check"]["sha256"],
    )

    drawing_files = sorted(V21.rglob("*.SLDDRW"))
    fastener_path = input_paths["fastener_register"]
    fastener_rows = []
    fastener_header = []
    if fastener_path.exists():
        with fastener_path.open(
                "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fastener_header = list(reader.fieldnames or [])
            fastener_rows = list(reader)
    fastener_contract = drawing_register.get("fastener_register", {})
    required_fastener_fields = set(
        fastener_contract.get("required_fields", [])
    )
    allowed_access_classes = set(
        fastener_contract.get("allowed_access_classes", [])
    )
    drawing_ids = set(drawing_register.get("drawings", {}))
    a11_contradictions = []
    a11_limitations = []
    if not fastener_rows:
        a11_limitations.append("fastener_register_missing_or_empty")
    else:
        missing_columns = sorted(
            required_fastener_fields - set(fastener_header)
        )
        if missing_columns:
            a11_contradictions.append(
                f"missing_required_columns:{missing_columns}"
            )
        if "TOOL_AXIS" not in fastener_header:
            a11_limitations.append("TOOL_AXIS_column_absent")
        group_ids = {}
        for index, row in enumerate(fastener_rows, 2):
            group_id = str(row.get("FASTENER_GROUP_ID", "")).strip()
            group_ids.setdefault(group_id, 0)
            group_ids[group_id] += 1
            access = str(row.get("ACCESS_CLASS", "")).strip()
            spec = str(row.get("SPEC", "")).strip()
            count = str(row.get("COUNT", "")).strip()
            drawing_ref = str(row.get("DRAWING_REF", "")).strip()
            if not group_id:
                a11_contradictions.append(f"blank_group_id:line{index}")
            if access not in allowed_access_classes:
                a11_contradictions.append(
                    f"invalid_access_class:line{index}:{access}"
                )
            if access == "FORBIDDEN_BLIND":
                a11_contradictions.append(
                    f"forbidden_blind_present:line{index}:{group_id}"
                )
            if drawing_ref not in drawing_ids:
                a11_contradictions.append(
                    f"unresolved_drawing_ref:line{index}:{drawing_ref}"
                )
            if spec in {"", "TBD", "UNKNOWN"}:
                a11_limitations.append(
                    f"unresolved_spec:line{index}:{group_id}"
                )
            if count in {"", "TBD", "UNKNOWN"}:
                a11_limitations.append(
                    f"unresolved_count:line{index}:{group_id}"
                )
            else:
                try:
                    if int(count) <= 0:
                        raise ValueError
                except ValueError:
                    a11_contradictions.append(
                        f"invalid_count:line{index}:{count}"
                    )
            if access == "UNKNOWN_BLOCKED":
                a11_limitations.append(
                    f"unknown_access:line{index}:{group_id}"
                )
        for group_id, count in group_ids.items():
            if not group_id or count != 1:
                a11_contradictions.append(
                    f"duplicate_or_blank_group_id:{group_id}:{count}"
                )
    a11_limitations.append(
        "no_CAD_fastener_instances_or_tool_axis_clearance_evidence"
    )
    if a11_contradictions:
        a11_status = "FAIL"
        a11_code = "FASTENER_REGISTER_SCHEMA_OR_ACCESS_CONTRADICTION"
    else:
        a11_status = "HOLD"
        a11_code = "FASTENER_REGISTER_ONLY_PHYSICAL_ACCESS_UNPROVED"
    _record(
        results, "A11_fastener_access_classes",
        a11_status, a11_code,
        rows=len(fastener_rows),
        contradictions=a11_contradictions,
        limitations=sorted(set(a11_limitations)),
    )

    # A20 proves governance properties only.  Configuration-specific material,
    # density, mass override, and inertia APIs are intentionally not claimed.
    mass_like_properties = []
    mass_governance_issues = []
    for item in inventory:
        props = item["props"]
        if props.get("MASS_OWNER") != "NONE_DISPLAY_ONLY":
            mass_governance_issues.append(
                f"MASS_OWNER_not_display_only:{item['file']}:"
                f"{props.get('MASS_OWNER')}"
            )
        if str(props.get("NO_DYNAMICS_USE", "")).casefold() != "true":
            mass_governance_issues.append(
                f"NO_DYNAMICS_USE_not_true:{item['file']}"
            )
        blocked = str(props.get("BLOCKED_CONSUMERS", ""))
        if "mass_properties" not in blocked:
            mass_governance_issues.append(
                f"mass_properties_not_blocked:{item['file']}"
            )
        for key in props:
            if key.upper() == "MASS_OWNER":
                continue
            if re.search(
                r"(^|_)(MASS|INERTIA|IXX|IYY|IZZ)(_|$)", key, re.I
            ):
                mass_like_properties.append({
                    "file": item["file"], "property": key,
                })
    if mass_like_properties:
        mass_governance_issues.append({
            "mass_like_custom_properties": mass_like_properties,
        })
    if mass_governance_issues:
        a20_status = "FAIL"
        a20_code = "CAD_MASS_GOVERNANCE_CONTRADICTION"
    else:
        a20_status = "HOLD"
        a20_code = (
            "DOCUMENT_GOVERNANCE_PASS_BUT_MATERIAL_AND_OVERRIDE_AUDIT_ABSENT"
        )
    _record(
        results, "A20_mass_inertia_isolation",
        a20_status, a20_code,
        issues=mass_governance_issues,
        limitations=[
            "configuration_specific_custom_properties_not_audited",
            "SolidWorks_material_and_density_not_audited",
            "component_mass_override_not_audited",
            "calculated_mass_and_inertia_are_not_scientific_budget_authority",
        ],
    )

    # Evidence-deficient physical/deliverable checks are explicit HOLDs.
    physical_holds = {
        "A10_wing_replace_with_B601_installed": (
            "NO_FULL_RESOLVED_REPLACEMENT_INTERFERENCE_REPORT",
            "No signed tool-axis keepout or B601-installed replacement check.",
        ),
        "A12_hold_release_ground_rerig": (
            "ZERO_SOLID_RELEASE_REFERENCE_NO_TOOL_CLEARANCE",
            "Release components and service path remain named references.",
        ),
        "A13_volume_extraction_axis_open_face": (
            "EXTRACTION_AXES_AND_OPEN_FACES_NOT_SIGNED",
            "Equipment extraction directions and open faces are absent.",
        ),
        "A14_cable_passage_and_service_loop": (
            "SEMANTIC_ROUTE_ONLY_NO_BEND_OR_CONNECTOR_CLEARANCE",
            "Bend radius, connectors and strain relief remain unknown.",
        ),
        "A15_B601_workspace_and_maintenance_keepout": (
            "Q0_PROXY_IS_NOT_WORKSPACE_OR_TRAJECTORY",
            "Camera frame/FOV and dynamic arm sweep are absent.",
        ),
        "A16_drawing_and_part_traceability": (
            "DRAWING_REGISTER_ONLY_NATIVE_RELEASE_PACKAGE_INCOMPLETE",
            (
                f"native_slddrw_count={len(drawing_files)}; "
                "1:1 pairing, released PDFs and physical fastener evidence "
                "are not proved"
            ),
        ),
        "A17_named_envelope_blockers": (
            "BLOCKER_STRINGS_REGISTERED_BUT_NOT_GEOMETRICALLY_RECOMPUTED",
            "238.3 and deployed tip findings remain open blockers.",
        ),
        "A18_capture_halfspace_accounting": (
            "STATIC_NUMERIC_RULE_ONLY_NO_DEPENDENCY_BOUND_GEOMETRY_PROOF",
            "Static X half-space does not prove B601 clearance or vision.",
        ),
        "A19_stow_chord_orientation": (
            "TRADE_RULE_REGISTERED_BUT_ORIENTATION_NOT_MACHINE_RECOMPUTED",
            "Chord orientation is a registered proposal, not a released gate.",
        ),
    }
    for item_id, (code, reason) in physical_holds.items():
        _record(
            results, item_id, "HOLD", code, reason=reason,
        )

    contract_items = {
        key: value for key, value in results.items()
        if key.startswith("A") and key[1:2].isdigit()
    }
    (run_out / "A8_A20_contract_status.yaml").write_text(
        yaml.safe_dump({
            "run_id": run_id,
            "generated_utc": now,
            "status_vocabulary": {
                "PASS": (
                    "the stated machine/evidence condition is proved within "
                    "its explicit claim limit"
                ),
                "HOLD": (
                    "required physical evidence or deliverable is absent or "
                    "outside the implemented audit"
                ),
                "FAIL": "a required contract is contradicted",
            },
            "items": contract_items,
            "physical_mechanism_gate": "HOLD",
            "red_team_corrections": _evidence_record(
                input_paths["red_team_corrections"]
            ),
        }, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    failed = [
        key for key, value in results.items()
        if value["status"] == "FAIL"
    ]
    held = [
        key for key, value in results.items()
        if value["status"] == "HOLD"
    ]
    passed = [
        key for key, value in results.items()
        if value["status"] == "PASS"
    ]
    exit_code = _exit_code(results)
    if exit_code == 1:
        verdict = "B4_1_ACCEPTANCE_FAIL"
    elif exit_code == 2:
        verdict = "B4_1_ACCEPTANCE_HOLD"
    else:
        verdict = "B4_1_ACCEPTANCE_PASS"
    summary = {
        "run_id": run_id,
        "generated_utc": now,
        "verdict": verdict,
        "exit_code": exit_code,
        "release_ready": exit_code == 0,
        "results": results,
        "failed": failed,
        "held": held,
        "passed": passed,
        "input_evidence_hashes": input_evidence,
        "native_input_manifest": "native_file_hash_manifest_v2_1.csv",
        "claim_limit": (
            "No FEA, dynamics, contact, deployment, workspace, vision, "
            "manufacturing, launch or flight compliance conclusion."
        ),
    }
    (run_out / "acceptance_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifact_rows = []
    for path in sorted(
            item for item in run_out.rglob("*") if item.is_file()):
        artifact_rows.append({
            "file": str(path.relative_to(run_out)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    (run_out / "acceptance_artifact_manifest.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_utc": now,
            "artifacts_before_manifest": artifact_rows,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _end_solidworks_session(
        sw,
        log,
        reason="acceptance_complete",
        required=False,
    )
    return summary


def main():
    OUT_FINAL.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        + f"-pid{os.getpid()}"
    )
    _atomic_write_json(
        OUT_FINAL / "latest_run_state.json",
        {
            "run_id": run_id,
            "status": "RUNNING",
            "started_utc": now,
            "acceptance_script_sha256": _sha256(Path(__file__).resolve()),
        },
    )
    run_out = Path(tempfile.mkdtemp(
        prefix=f".b4_1_acceptance_{run_id}_",
        dir=OUT_FINAL,
    ))
    try:
        summary = _run_acceptance(run_out, run_id, now)
        _publish_run(run_out, OUT_FINAL)
        final_summary = OUT_FINAL / "acceptance_summary.json"
        _atomic_write_json(
            OUT_FINAL / "latest_run_state.json",
            {
                "run_id": run_id,
                "status": summary["verdict"],
                "completed_utc": datetime.now(timezone.utc).isoformat(),
                "exit_code": summary["exit_code"],
                "release_ready": summary["release_ready"],
                "acceptance_summary_sha256": _sha256(final_summary),
            },
        )
        print(json.dumps({
            key: value["status"]
            for key, value in summary["results"].items()
        }, ensure_ascii=False, indent=2))
        print(summary["verdict"])
        return summary["exit_code"]
    except Exception as exc:
        _atomic_write_json(
            OUT_FINAL / "latest_run_state.json",
            {
                "run_id": run_id,
                "status": "B4_1_ACCEPTANCE_EXECUTION_FAIL",
                "failed_utc": datetime.now(timezone.utc).isoformat(),
                "exit_code": 1,
                "release_ready": False,
                "exception_type": type(exc).__name__,
                "exception": str(exc),
            },
        )
        raise
    finally:
        if run_out.exists():
            shutil.rmtree(run_out, ignore_errors=True)


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_static_self_test())
    try:
        sys.exit(main())
    except B3FailClosed as exc:
        print(f"FAIL_CLOSED: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"UNEXPECTED_FAIL_CLOSED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        sys.exit(1)
