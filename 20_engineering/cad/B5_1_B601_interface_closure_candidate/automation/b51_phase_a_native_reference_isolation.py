"""Cold-audit and isolate the canonical V2.2 native copy used by B5.1.

The accepted V2.2 native tree is never opened for write.  The script launches
three exclusive SolidWorks processes:

1. cold read-only audit of the B5.1 copy;
2. a bounded repair session if, and only if, references resolve back to the
   canonical source at the same relative path;
3. cold read-only verification of the repaired B5.1 copy.

Only the copied top-level assembly may change.  All 108 accepted source files
and all other copied files are hash-checked before and after the operation.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
CAD_ROOT = CANDIDATE_ROOT.parent
SOURCE_ROOT = CAD_ROOT / "Space_Embodied_Robot_CAD_V2_2_NATIVE"
COPY_ROOT = (
    CANDIDATE_ROOT
    / "00_BASELINE_DONORS"
    / "V2_2_NATIVE_CANONICAL_108_FILE_COPY"
)
TOP_RELATIVE = Path("Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM")
COPY_TOP = COPY_ROOT / TOP_RELATIVE
FREEZE_MANIFEST = (
    CAD_ROOT
    / "Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION"
    / "baseline_freeze_manifest.yaml"
)
AUDIT_ROOT = CANDIDATE_ROOT / "00_AUDIT"
PRE_PATH = AUDIT_ROOT / "B51_NATIVE_REFERENCE_PRE_REPAIR.json"
REPAIR_PATH = AUDIT_ROOT / "B51_NATIVE_REFERENCE_REPAIR.json"
FINAL_PATH = AUDIT_ROOT / "B51_NATIVE_REFERENCE_CONTAINMENT.json"

B50_AUTOMATION = (
    CAD_ROOT / "B5_0_B601_space_manipulator_candidate" / "automation"
)
sys.path.insert(0, str(B50_AUTOMATION))
import sw_b50_core as core  # noqa: E402

core.CANDIDATE_ROOT = CANDIDATE_ROOT
core.WRITER_MUTEX_NAME = r"Local\SER_B51_SOLIDWORKS_WRITER"

SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1
SW_OPEN_READ_ONLY = 2
SW_SAVE_SILENT = 1
EXPECTED_CONFIGURATIONS = sorted(
    [
        "DEPLOYED_NOMINAL",
        "DEPLOY_FAILED_BOTH",
        "L_FAIL",
        "R_FAIL",
        "PARTIAL_DEPLOYMENT",
        "MAINTENANCE",
        "STOW_VENDOR_25DEG_PROPOSAL",
        "STOW_NO_CLOCK_COMPARATOR",
        "STOWED",
    ]
)
EXPECTED_LEAK_RELATIVE = Path(
    "01_Primary_Structure/Removable_Panels/Removable_Panels.SLDASM"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def load_freeze() -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load(FREEZE_MANIFEST.read_text(encoding="utf-8"))
    files = payload.get("files")
    if not isinstance(files, dict) or len(files) != 108:
        raise RuntimeError("canonical freeze manifest must contain 108 files")
    return files


def source_snapshot(files: dict[str, dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative, record in sorted(files.items()):
        path = SOURCE_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"canonical source file missing: {path}")
        actual = sha256_file(path)
        expected = str(record["sha256"]).upper()
        if actual != expected:
            raise RuntimeError(
                f"canonical source drift: {relative}: {actual} != {expected}"
            )
        result[relative] = actual
    return result


def copy_snapshot(files: dict[str, dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in sorted(files):
        path = COPY_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"B5.1 copied file missing: {path}")
        result[relative] = sha256_file(path)
    return result


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def unpack_open(
    session: core.SolidWorksSession, *, read_only: bool
) -> tuple[Any, dict[str, Any]]:
    options = SW_OPEN_SILENT | (SW_OPEN_READ_ONLY if read_only else 0)
    try:
        returned = session.sw.OpenDoc6(
            str(COPY_TOP),
            SW_DOC_ASSEMBLY,
            options,
            "",
            0,
            0,
        )
        model, outs = core._unpack_return(returned)
        errors = int(outs[0]) if len(outs) > 0 else None
        warnings = int(outs[1]) if len(outs) > 1 else None
    except TypeError:
        from win32com.client import VARIANT

        errors_ref = VARIANT(
            session.pythoncom.VT_BYREF | session.pythoncom.VT_I4, 0
        )
        warnings_ref = VARIANT(
            session.pythoncom.VT_BYREF | session.pythoncom.VT_I4, 0
        )
        model = session.sw.OpenDoc6(
            str(COPY_TOP),
            SW_DOC_ASSEMBLY,
            options,
            "",
            errors_ref,
            warnings_ref,
        )
        errors = int(errors_ref.value)
        warnings = int(warnings_ref.value)
    if model is None or errors not in (None, 0):
        raise RuntimeError(
            f"OpenDoc6 failed: model={model is not None}, "
            f"errors={errors}, warnings={warnings}"
        )
    return session.cast(model, "IModelDoc2"), {
        "path": str(COPY_TOP.resolve()),
        "read_only": read_only,
        "errors": errors,
        "warnings": warnings,
    }


def component_records(
    session: core.SolidWorksSession, model: Any
) -> tuple[list[dict[str, Any]], list[Any]]:
    assembly = session.cast(model, "IAssemblyDoc")
    components = [
        session.cast(component, "IComponent2")
        for component in list(assembly.GetComponents(False) or [])
    ]
    records: list[dict[str, Any]] = []
    for component in components:
        raw_path = str(core.get_com_member(component, "GetPathName") or "")
        resolved = Path(raw_path).resolve() if raw_path else None
        records.append(
            {
                "name": str(core.get_com_member(component, "Name2")),
                "path": str(resolved) if resolved is not None else "",
                "path_exists": (
                    resolved.is_file() if resolved is not None else False
                ),
                "inside_b51_copy": (
                    is_within(resolved, COPY_ROOT)
                    if resolved is not None
                    else False
                ),
                "inside_canonical_source": (
                    is_within(resolved, SOURCE_ROOT)
                    if resolved is not None
                    else False
                ),
            }
        )
    return records, components


def configuration_names(model: Any) -> list[str]:
    return sorted(str(name) for name in list(model.GetConfigurationNames() or []))


def configuration_audit(
    session: core.SolidWorksSession,
    model: Any,
    configurations: list[str],
) -> list[dict[str, Any]]:
    active = core.get_com_member(model.ConfigurationManager, "ActiveConfiguration")
    original = str(core.get_com_member(active, "Name"))
    results: list[dict[str, Any]] = []
    for name in configurations:
        shown = bool(model.ShowConfiguration2(name))
        if not shown:
            raise RuntimeError(f"cannot activate configuration: {name}")
        active_now = core.get_com_member(
            model.ConfigurationManager, "ActiveConfiguration"
        )
        readback = str(core.get_com_member(active_now, "Name"))
        rebuild_ok = bool(model.ForceRebuild3(True))
        records, _ = component_records(session, model)
        results.append(
            {
                "requested": name,
                "readback": readback,
                "readback_match": readback == name,
                "rebuild_ok": rebuild_ok,
                "components_enumerated_raw": len(records),
                "components_without_path": sum(
                    not bool(item["path"]) for item in records
                ),
                "missing_resolved_paths": [
                    item for item in records if not item["path_exists"]
                ],
                "resolved_outside_b51_copy": [
                    item
                    for item in records
                    if item["path"] and not item["inside_b51_copy"]
                ],
            }
        )
    if not model.ShowConfiguration2(original):
        raise RuntimeError(
            f"cannot restore original configuration after audit: {original}"
        )
    return results


def audit_once(label: str) -> dict[str, Any]:
    with core.SolidWorksSession(CANDIDATE_ROOT, visible=False) as session:
        session_start = session.info()
        model, open_record = unpack_open(session, read_only=True)
        if not model.ForceRebuild3(True):
            raise RuntimeError(f"{label}: top-level rebuild failed")
        records, _ = component_records(session, model)
        configurations = configuration_names(model)
        configuration_checks = configuration_audit(
            session, model, configurations
        )
        unresolved = [item for item in records if not item["path"]]
        missing = [item for item in records if not item["path_exists"]]
        outside = [
            item
            for item in records
            if item["path"] and not item["inside_b51_copy"]
        ]
        result = {
            "label": label,
            "generated_utc": utc_now(),
            "session": session_start,
            "open": open_record,
            "top_sha256": sha256_file(COPY_TOP),
            "components_total": len(records),
            "resolved_inside_b51_copy": sum(
                bool(item["inside_b51_copy"]) for item in records
            ),
            "resolved_outside_b51_copy": outside,
            "unresolved_components": unresolved,
            "missing_resolved_paths": missing,
            "configurations": configurations,
            "configurations_expected": EXPECTED_CONFIGURATIONS,
            "configuration_checks": configuration_checks,
            "component_records": records,
            "verdict": (
                "ISOLATED"
                if (
                    not outside
                    and not unresolved
                    and not missing
                    and configurations == EXPECTED_CONFIGURATIONS
                    and all(
                        item["readback_match"]
                        and item["rebuild_ok"]
                        and not item["components_without_path"]
                        and not item["missing_resolved_paths"]
                        and not item["resolved_outside_b51_copy"]
                        for item in configuration_checks
                    )
                )
                else "REFERENCE_CONTAINMENT_FAIL"
            ),
        }
        session.close_all_documents()
    result["session_after_exit"] = session.info()
    return result


def repair_source_leaks(pre: dict[str, Any]) -> dict[str, Any]:
    leaks = pre["resolved_outside_b51_copy"]
    if not leaks:
        return {
            "generated_utc": utc_now(),
            "action": "NO_REPAIR_REQUIRED",
            "repairs": [],
        }
    if pre["components_total"] != 56:
        raise RuntimeError(
            f"pre-repair component count {pre['components_total']} != 56"
        )
    if pre["unresolved_components"] or pre["missing_resolved_paths"]:
        raise RuntimeError(
            "pre-repair audit contains empty or missing resolved paths"
        )
    expected_source = (SOURCE_ROOT / EXPECTED_LEAK_RELATIVE).resolve()
    if len(leaks) != 1 or Path(leaks[0]["path"]).resolve() != expected_source:
        raise RuntimeError(
            "pre-repair outside-reference set does not match the one "
            f"ratified known leak: {leaks}"
        )
    for leak in leaks:
        path = Path(leak["path"])
        if not is_within(path, SOURCE_ROOT):
            raise RuntimeError(
                f"refusing to repair non-canonical outside reference: {path}"
            )
        relative = path.resolve().relative_to(SOURCE_ROOT.resolve())
        target = COPY_ROOT / relative
        if not target.is_file():
            raise RuntimeError(f"mapped B5.1 copy target missing: {target}")

    with core.SolidWorksSession(CANDIDATE_ROOT, visible=False) as session:
        session_start = session.info()
        model, open_record = unpack_open(session, read_only=False)
        assembly = session.cast(model, "IAssemblyDoc")
        records, components = component_records(session, model)
        live_leaks = [
            record
            for record in records
            if record["path"] and not record["inside_b51_copy"]
        ]
        if len(live_leaks) != 1 or (
            Path(live_leaks[0]["path"]).resolve() != expected_source
        ):
            raise RuntimeError(
                f"repair-session leak set changed: {live_leaks}"
            )
        by_name = {
            record["name"]: component
            for record, component in zip(records, components)
        }
        repairs: list[dict[str, Any]] = []
        for leak in leaks:
            source_path = Path(leak["path"]).resolve()
            relative = source_path.relative_to(SOURCE_ROOT.resolve())
            target = (COPY_ROOT / relative).resolve()
            component = by_name.get(leak["name"])
            if component is None:
                raise RuntimeError(
                    f"leaking component not found in repair session: {leak['name']}"
                )
            model.ClearSelection2(True)
            try:
                selected = bool(component.Select4(False, None, False))
            except TypeError:
                selected = bool(component.Select4(False, None))
            if not selected:
                raise RuntimeError(
                    f"cannot select leaking component: {leak['name']}"
                )
            returned = assembly.ReplaceComponents(
                str(target), "", True, True
            )
            api_ok, outs = core._unpack_return(returned)
            if not bool(api_ok):
                raise RuntimeError(
                    f"ReplaceComponents failed for {leak['name']}: {returned!r}"
                )
            repairs.append(
                {
                    "component": leak["name"],
                    "old": str(source_path),
                    "new": str(target),
                    "selected": selected,
                    "api_ok": bool(api_ok),
                    "api_outputs": [str(value) for value in outs],
                }
            )
        if not model.ForceRebuild3(True):
            raise RuntimeError("repair-session rebuild failed")
        saved = model.Save3(SW_SAVE_SILENT, 0, 0)
        save_ok, save_outs = core._unpack_return(saved)
        errors = int(save_outs[0]) if len(save_outs) > 0 else None
        warnings = int(save_outs[1]) if len(save_outs) > 1 else None
        if not bool(save_ok) or errors not in (None, 0):
            raise RuntimeError(
                f"repair save failed: ok={bool(save_ok)}, "
                f"errors={errors}, warnings={warnings}"
            )
        session.close_all_documents()
        result = {
            "generated_utc": utc_now(),
            "action": "BOUND_CANONICAL_SOURCE_LEAKS_TO_B51_COPY",
            "session": session_start,
            "open": open_record,
            "repairs": repairs,
            "save": {
                "api_ok": bool(save_ok),
                "errors": errors,
                "warnings": warnings,
            },
            "top_sha256_after_save": sha256_file(COPY_TOP),
        }
    result["session_after_exit"] = session.info()
    return result


def launch_retry(operation, label: str) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in range(1, 4):
        try:
            return operation()
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors.append(message)
            transient = (
                "-2146959355" in repr(exc)
                or "服务器运行失败" in str(exc)
            )
            if not transient or attempt == 3:
                raise RuntimeError(
                    f"{label} failed after {attempt} attempt(s): {errors}"
                ) from exc
            if core.sldworks_process_ids():
                raise RuntimeError(
                    f"{label} transient launch failure left a SolidWorks "
                    f"process: {core.sldworks_process_ids()}"
                ) from exc
            time.sleep(20.0 * attempt)
    raise AssertionError("unreachable launch retry")


def main() -> int:
    if FINAL_PATH.exists():
        raise RuntimeError(f"append-only final output already exists: {FINAL_PATH}")
    if REPAIR_PATH.exists() and not PRE_PATH.exists():
        raise RuntimeError("repair receipt exists without pre-repair audit")

    files = load_freeze()
    source_before = source_snapshot(files)
    copy_before = dict(source_before)
    if PRE_PATH.exists():
        pre = load_json(PRE_PATH)
        if pre.get("label") != "B51_COLD_PROCESS_PRE_REPAIR":
            raise RuntimeError("existing pre-repair audit has unexpected label")
        if pre.get("top_sha256") != copy_before[TOP_RELATIVE.as_posix()]:
            raise RuntimeError(
                "existing pre-repair top hash does not match canonical freeze"
            )
    else:
        pre = launch_retry(
            lambda: audit_once("B51_COLD_PROCESS_PRE_REPAIR"),
            "pre-repair cold audit",
        )
        write_json_once(PRE_PATH, pre)

    if REPAIR_PATH.exists():
        repair = load_json(REPAIR_PATH)
        expected_post_hash = repair.get("top_sha256_after_save")
        if not expected_post_hash or sha256_file(COPY_TOP) != expected_post_hash:
            raise RuntimeError(
                "existing repair receipt does not match live copied top hash"
            )
    else:
        if core.sldworks_process_ids():
            raise RuntimeError(
                f"SolidWorks must be absent before repair: "
                f"{core.sldworks_process_ids()}"
            )
        time.sleep(15.0)
        repair = launch_retry(
            lambda: repair_source_leaks(pre),
            "bounded reference repair",
        )
        write_json_once(REPAIR_PATH, repair)

    source_after_repair = source_snapshot(files)
    if core.sldworks_process_ids():
        raise RuntimeError(
            f"SolidWorks must be absent before post audit: "
            f"{core.sldworks_process_ids()}"
        )
    time.sleep(15.0)
    post = launch_retry(
        lambda: audit_once("B51_COLD_PROCESS_POST_REPAIR"),
        "post-repair cold audit",
    )
    source_after_post = source_snapshot(files)
    copy_after = copy_snapshot(files)
    copy_differences_vs_source = sorted(
        relative
        for relative in source_after_post
        if source_after_post[relative] != copy_after[relative]
    )

    source_violations = sorted(
        relative
        for relative in source_before
        if source_before[relative] != source_after_repair[relative]
        or source_before[relative] != source_after_post[relative]
    )
    changed_copy_files = sorted(
        relative
        for relative in copy_before
        if copy_before[relative] != copy_after[relative]
    )
    allowed_copy_change = [TOP_RELATIVE.as_posix()]
    copy_change_scope_pass = changed_copy_files in ([], allowed_copy_change)
    process_ids = [
        pre["session"]["owner_pid"],
        repair.get("session", {}).get("owner_pid"),
        post["session"]["owner_pid"],
    ]
    fresh_process_sessions = (
        all(
            not item["session"]["pre_process_ids"]
            for item in (pre, post)
        )
        and (
            "session" not in repair
            or not repair["session"]["pre_process_ids"]
        )
        and len([pid for pid in process_ids if pid is not None])
        == len(set(pid for pid in process_ids if pid is not None))
        and not pre["session_after_exit"]["post_process_ids"]
        and not post["session_after_exit"]["post_process_ids"]
        and (
            "session_after_exit" not in repair
            or not repair["session_after_exit"]["post_process_ids"]
        )
    )
    source_locks = sorted(str(path) for path in SOURCE_ROOT.rglob("~$*"))
    copy_locks = sorted(str(path) for path in COPY_ROOT.rglob("~$*"))
    passed = (
        pre["components_total"] == 56
        and post["components_total"] == 56
        and post["verdict"] == "ISOLATED"
        and not source_violations
        and copy_change_scope_pass
        and copy_differences_vs_source == allowed_copy_change
        and fresh_process_sessions
        and not source_locks
        and not copy_locks
        and post["top_sha256"] == copy_after[TOP_RELATIVE.as_posix()]
    )
    final = {
        "schema": "SER_B51_NATIVE_REFERENCE_CONTAINMENT_V1",
        "generated_utc": utc_now(),
        "status": (
            "B51_PHASE_A_NATIVE_REFERENCE_CONTAINMENT_PASS"
            if passed
            else "B51_PHASE_A_NATIVE_REFERENCE_CONTAINMENT_HOLD"
        ),
        "canonical_source": {
            "root": str(SOURCE_ROOT.resolve()),
            "checked": len(source_before),
            "hash_violations": source_violations,
            "proof": "PASS" if not source_violations else "FAIL",
        },
        "b51_copy": {
            "root": str(COPY_ROOT.resolve()),
            "top": str(COPY_TOP.resolve()),
            "top_sha256_before": copy_before[TOP_RELATIVE.as_posix()],
            "top_sha256_after": copy_after[TOP_RELATIVE.as_posix()],
            "changed_files": changed_copy_files,
            "allowed_changed_files": allowed_copy_change,
            "differences_vs_canonical_source": copy_differences_vs_source,
            "change_scope_proof": (
                "PASS" if copy_change_scope_pass else "FAIL"
            ),
        },
        "cold_process_proof": {
            "owner_pids": process_ids,
            "fresh_process_sessions": fresh_process_sessions,
        },
        "lock_files_after_close": {
            "canonical_source": source_locks,
            "b51_copy": copy_locks,
        },
        "pre_audit_summary": {
            "components_total": pre["components_total"],
            "resolved_inside_b51_copy": pre[
                "resolved_inside_b51_copy"
            ],
            "outside": pre["resolved_outside_b51_copy"],
            "verdict": pre["verdict"],
        },
        "repair_summary": repair,
        "post_audit": post,
        "g0": (
            "PASS_REFERENCE_CONTAINMENT_ONLY"
            if passed
            else "HOLD_REFERENCE_CONTAINMENT"
        ),
        "claim_limit": (
            "This proves only native reference ownership and accepted-source "
            "hash preservation. It does not authorize B5.1 geometry, "
            "articulation, packaging, manufacturing, or flight release."
        ),
    }
    write_json_once(FINAL_PATH, final)
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
