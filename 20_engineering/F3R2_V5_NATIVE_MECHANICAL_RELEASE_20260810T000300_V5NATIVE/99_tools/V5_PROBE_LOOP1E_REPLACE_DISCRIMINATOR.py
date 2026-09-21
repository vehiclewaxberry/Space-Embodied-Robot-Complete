#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: discriminate LOCAL_ARM_REPLACE_FAIL root cause.

Fail-closed context: receipt
13_validation/V5_LOOP1E_FAIL_20260811T181148.492990Z.json reports
IAssemblyDoc.ReplaceComponents2 == False when repointing component
B51_REF_gripper_detail_LINKLOCAL-1 from the F3R1 lineage tree to the V5-local
staged copy (config 默认).  The gripper SLDPRT is byte-identical across
F3R1/F3R2/July/V5-local (sha 6758B99741FFACAB..., 5,277,750 bytes) and the
staged tree is a verified pairwise-pristine copy of the protected F3R2 donor.

Hypotheses under test (production semantics reproduced in-memory only):
  (a) SW2024 rejects identical-content ReplaceComponents2 in general -> the
      first non-gripper byte-identical external component must also fail.
  (b) the gripper occurrence is not fully resolved (suppressed=0 or
      lightweight=2) in config 默认 of the staged copy -> production replace
      fails, and a resolve-first (SetSuppression2(1)) retry succeeds.
  (c) mate-reattachment failure specific to this heavily referenced part ->
      occurrence is fully resolved yet every ReAttachMates variant fails.

The probe NEVER saves any document, never writes inside the release tree,
never mutates the protected donor (read-only open only), and leaves the
attach-only Session B (requalified, rev 32.5.x) document-empty.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402
import F3R2_V5_SESSION_BINDING as sbin  # noqa: E402

T0 = time.time()
SW_DOC_ASSEMBLY = 2
SW_COMPONENT_SUPPRESSED = 0
SW_COMPONENT_RESOLVED = 1
SW_COMPONENT_LIGHTWEIGHT = 2
SUPPRESSION_LABEL = {0: "SUPPRESSED", 1: "RESOLVED", 2: "LIGHTWEIGHT"}

PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def available_gib() -> float:
    try:
        return round(base.available_gib(), 3)
    except Exception:  # noqa: BLE001
        return -1.0


def close_all(sw: Any) -> int:
    for _pass in range(4):
        documents = base.as_list(base.value(sw, "GetDocuments"))
        if not documents:
            break
        titles: List[str] = []
        for raw in documents:
            try:
                titles.append(str(base.value(raw, "GetTitle")))
            except Exception:  # noqa: BLE001
                continue
        for title in reversed(list(dict.fromkeys(titles))):
            try:
                sw.CloseDoc(title)
            except Exception:  # noqa: BLE001
                pass
    return int(base.value(sw, "GetDocumentCount"))


def open_doc(sw: Any, path: Path, read_only: bool, types: Any, pythoncom: Any) -> Any:
    options = 1 | (2 if read_only else 0)
    raw = sw.OpenDoc6(str(path), SW_DOC_ASSEMBLY, options, "", 0, 0)
    model_raw, outs = base.unpack(raw)
    errors = int(outs[0]) if outs else 0
    warnings = int(outs[1]) if len(outs) > 1 else 0
    if model_raw is None or errors != 0:
        raise RuntimeError(f"OpenDoc6 failed path={path} errors={errors} warnings={warnings}")
    return base.wrap(model_raw, "IModelDoc2", types, pythoncom)


def activate(model: Any, config: str, types: Any, pythoncom: Any) -> bool:
    return bool(m.show_config_ok(model, config, base, types, pythoncom))


def component_rows(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        suppression = int(base.value(component, "GetSuppression2"))
        rows.append({
            "name2": str(base.value(component, "Name2")),
            "path": str(base.value(component, "GetPathName")).replace("\\", "/"),
            "suppression": suppression,
            "suppression_label": SUPPRESSION_LABEL.get(suppression, str(suppression)),
            "fixed": bool(base.value(component, "IsFixed")),
        })
    return sorted(rows, key=lambda row: row["name2"])


def external_components(model: Any, types: Any, pythoncom: Any) -> List[Any]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    externals: List[Any] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        current = Path(str(base.value(component, "GetPathName"))).resolve()
        if m.LOCAL_ARM_ROOT.resolve() not in current.parents:
            externals.append(component)
    return externals


def local_target_for(current: Path) -> Optional[Path]:
    for source_root in (m.B51_DONOR_ROOT.resolve(), m.F3R1_B51_COPY_ROOT.resolve(), m.JULY_B51_DONOR_ROOT.resolve()):
        try:
            relative = current.relative_to(source_root)
            return (m.LOCAL_ARM_ROOT / relative).resolve()
        except ValueError:
            continue
    return None


def production_replace(assembly: Any, component: Any, target: Path, reattach: int = 2, update_callouts: bool = True, replace_all: bool = True) -> bool:
    model_ok = bool(component.Select4(False, None, False))
    if not model_ok:
        return {"select": False}  # type: ignore[return-value]
    ok = bool(assembly.ReplaceComponents2(str(target), "", replace_all, reattach, update_callouts))
    return {"select": True, "replace": ok}  # type: ignore[return-value]


def mate_census(model: Any, leaf: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    feature = base.value(model, "FirstFeature")
    guard = 0
    while feature is not None and guard < 10000:
        guard += 1
        typed = base.wrap(feature, "IFeature", types, pythoncom)
        if str(base.value(typed, "GetTypeName2")) == "MateGroup":
            sub = base.value(typed, "GetFirstSubFeature")
            sub_guard = 0
            while sub is not None and sub_guard < 10000:
                sub_guard += 1
                sf = base.wrap(sub, "IFeature", types, pythoncom)
                row: Dict[str, Any] = {"feature_name": str(base.value(sf, "Name"))}
                try:
                    row["suppressed"] = bool(base.value(sf, "IsSuppressed"))
                    row["error_code"] = int(base.value(sf, "GetErrorCode2"))
                    mate = base.wrap(base.value(sf, "GetSpecificFeature2"), "IMate2", types, pythoncom)
                    endpoints: List[Optional[str]] = []
                    for index in range(int(base.value(mate, "GetMateEntityCount"))):
                        entity = base.wrap(mate.MateEntity(index), "IMateEntity2", types, pythoncom)
                        raw_component = base.value(entity, "ReferenceComponent")
                        endpoints.append(None if raw_component is None else str(base.value(base.wrap(raw_component, "IComponent2", types, pythoncom), "Name2")))
                    row["endpoints"] = endpoints
                except Exception as exc:  # noqa: BLE001
                    row["dump_exception"] = repr(exc)
                rows.append(row)
                sub = base.value(sf, "GetNextSubFeature")
        feature = base.value(typed, "GetNextFeature")
    involving = [row for row in rows if any(isinstance(ep, str) and ep.split("/")[-1] == leaf for ep in (row.get("endpoints") or []))]
    return {"mate_total": len(rows), "mates_involving_leaf": len(involving), "leaf": leaf, "involving": involving}


def suppression_of(component: Any) -> Dict[str, Any]:
    suppression = int(base.value(component, "GetSuppression2"))
    return {"suppression": suppression, "suppression_label": SUPPRESSION_LABEL.get(suppression, str(suppression))}


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_REPLACE_DISCRIMINATOR_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "fail_receipt": "13_validation/V5_LOOP1E_FAIL_20260811T181148.492990Z.json",
        "phases": {},
    }
    sw = types = pythoncom = None
    try:
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        result["memory_available_gib_start"] = available_gib()
        expected_pid = int(sbin.resolve_pid(json.loads(m.LOOP1_RECEIPT.read_text(encoding="utf-8-sig")).get("solidworks", {}).get("pid", -1)))
        if int(session["pid"]) != expected_pid:
            raise RuntimeError(f"exclusive session PID drifted: {session['pid']} != {expected_pid}")
        result["protected_pre"] = {m.sha256(path): str(path) for path in PROTECTED_WATCH if path.is_file()}
        log(f"attach ok pid={session['pid']} rev={session['revision']}")

        # ---- P1: protected donor, read-only, per-config suppression census ----
        donor = open_doc(sw, m.B51_DONOR, True, types, pythoncom)
        donor_rows: Dict[str, Any] = {}
        for config in m.ARM_CONFIGS:
            if not activate(donor, config, types, pythoncom):
                raise RuntimeError(f"donor config activation failed: {config}")
            donor_rows[config] = component_rows(donor, types, pythoncom)
        donor_census = mate_census(donor, m.ARM_LEGACY_GRIPPER_LEAF, types, pythoncom)
        result["phases"]["P1_donor_readonly"] = {"components": donor_rows, "mate_census": donor_census}
        grip_donor = {cfg: [r for r in rows if r["name2"].split("/")[-1] == m.ARM_LEGACY_GRIPPER_LEAF] for cfg, rows in donor_rows.items()}
        result["phases"]["P1_donor_gripper"] = grip_donor
        log(f"P1 donor census done; gripper rows={ {cfg: len(v) for cfg, v in grip_donor.items()} }")
        if close_all(sw) != 0:
            raise RuntimeError("donor close left documents open")

        # ---- P2: staged V5-local copy, production reproduction, NO SAVE ----
        staged_doc = open_doc(sw, m.LOCAL_ARM, False, types, pythoncom)
        assembly = base.wrap(staged_doc, "IAssemblyDoc", types, pythoncom)
        config = m.ARM_CONFIGS[0]
        if not activate(staged_doc, config, types, pythoncom):
            raise RuntimeError(f"staged config activation failed: {config}")
        staged_initial = component_rows(staged_doc, types, pythoncom)
        result["phases"]["P2_staged_initial_components"] = staged_initial
        result["phases"]["P2_staged_initial_mate_census"] = mate_census(staged_doc, m.ARM_LEGACY_GRIPPER_LEAF, types, pythoncom)
        log(f"P2 staged initial externals={sum(1 for r in staged_initial if m.LOCAL_ARM_ROOT.resolve().as_posix() not in Path(r['path']).resolve().as_posix())}")

        attempts: List[Dict[str, Any]] = []
        failing: Optional[Dict[str, Any]] = None
        guard = 0
        while guard < 64:
            guard += 1
            externals = external_components(staged_doc, types, pythoncom)
            if not externals:
                break
            component = externals[0]
            name2 = str(base.value(component, "Name2"))
            current = Path(str(base.value(component, "GetPathName"))).resolve()
            target = local_target_for(current)
            if target is None or not target.is_file():
                failing = {"name2": name2, "current": str(current), "target": None if target is None else str(target), "error": "TARGET_UNRESOLVABLE"}
                break
            staged_doc.ClearSelection2(True)
            outcome = production_replace(assembly, component, target)
            staged_doc.ClearSelection2(True)
            attempts.append({
                "order": guard,
                "name2": name2,
                "leaf": name2.split("/")[-1],
                "current": str(current).replace("\\", "/"),
                "target": str(target).replace("\\", "/"),
                "is_gripper": name2.split("/")[-1] == m.ARM_LEGACY_GRIPPER_LEAF,
                "pre_state": suppression_of(component),
                "outcome": outcome,
            })
            log(f"replace attempt {guard}: {name2} -> {outcome}")
            if not outcome.get("replace"):
                failing = attempts[-1]
                break
        result["phases"]["P2_production_attempts"] = attempts
        result["phases"]["P2_first_failure"] = failing

        diagnostics: Dict[str, Any] = {}
        if failing is not None and failing.get("is_gripper"):
            # Re-acquire a fresh handle on the failing gripper occurrence.
            grip = None
            for raw in base.as_list(assembly.GetComponents(True)):
                candidate = base.wrap(raw, "IComponent2", types, pythoncom)
                if str(base.value(candidate, "Name2")) == failing["name2"]:
                    grip = candidate
                    break
            if grip is None:
                diagnostics["error"] = "FAILING_COMPONENT_HANDLE_LOST"
            else:
                diagnostics["state_before_repair"] = suppression_of(grip)
                diagnostics["fixed"] = bool(base.value(grip, "IsFixed"))
                diagnostics["mate_census"] = mate_census(staged_doc, m.ARM_LEGACY_GRIPPER_LEAF, types, pythoncom)
                # (b) resolve-first retry ------------------------------------
                if int(base.value(grip, "GetSuppression2")) != SW_COMPONENT_RESOLVED:
                    returned = int(grip.SetSuppression2(SW_COMPONENT_RESOLVED))
                    staged_doc.ForceRebuild3(True)
                    diagnostics["resolve_drive"] = {"returned": returned, "readback": suppression_of(grip)}
                    staged_doc.ClearSelection2(True)
                    outcome = production_replace(assembly, grip, Path(failing["target"]))
                    staged_doc.ClearSelection2(True)
                    diagnostics["replace_after_resolve"] = outcome
                    log(f"replace after resolve: {outcome}")
                # (c) reattach-mate matrix on any persistent failure ---------
                if not diagnostics.get("replace_after_resolve", {}).get("replace"):
                    matrix: List[Dict[str, Any]] = []
                    for reattach in (0, 1, 2):
                        for update in (True, False):
                            if reattach == 2 and update is True:
                                continue  # identical to the production attempt
                            staged_doc.ClearSelection2(True)
                            outcome = production_replace(assembly, grip, Path(failing["target"]), reattach=reattach, update_callouts=update)
                            staged_doc.ClearSelection2(True)
                            matrix.append({"reattach": reattach, "update_callouts": update, "outcome": outcome})
                            log(f"reattach matrix r={reattach} u={update}: {outcome}")
                    diagnostics["reattach_matrix"] = matrix
                    staged_doc.ClearSelection2(True)
                    outcome = production_replace(assembly, grip, Path(failing["target"]), replace_all=False)
                    staged_doc.ClearSelection2(True)
                    diagnostics["replace_single_instance"] = outcome
        result["phases"]["P2_failure_diagnostics"] = diagnostics

        # Per-config gripper suppression on the staged copy (both configs).
        per_config: Dict[str, Any] = {}
        for cfg in m.ARM_CONFIGS:
            if activate(staged_doc, cfg, types, pythoncom):
                rows = [r for r in component_rows(staged_doc, types, pythoncom) if r["name2"].split("/")[-1] == m.ARM_LEGACY_GRIPPER_LEAF]
                per_config[cfg] = rows
        result["phases"]["P2_staged_gripper_per_config"] = per_config
        log(f"P2 per-config gripper rows={ {cfg: [(r['suppression_label'], r['path'].split('/')[-1]) for r in rows] for cfg, rows in per_config.items()} }")
        # DISCARD: close without saving; staged tree stays byte-pristine.
        if close_all(sw) != 0:
            raise RuntimeError("staged close left documents open")
        result["phases"]["P3_session_document_count"] = int(base.value(sw, "GetDocumentCount"))

        # ---- verdict synthesis ---------------------------------------------
        non_gripper = [row for row in attempts if not row["is_gripper"]]
        checks = {
            "control_identical_replace_succeeded": bool(non_gripper) and all(row["outcome"].get("replace") for row in non_gripper),
            "gripper_was_first_external": bool(attempts) and attempts[0]["is_gripper"],
            "gripper_failure_reproduced": failing is not None and failing.get("is_gripper") is True,
            "gripper_not_fully_resolved_at_failure": bool(diagnostics) and diagnostics.get("state_before_repair", {}).get("suppression") != SW_COMPONENT_RESOLVED,
            "resolve_first_repair_succeeded": bool(diagnostics.get("replace_after_resolve", {}).get("replace")),
            "any_reattach_variant_succeeded": any(row["outcome"].get("replace") for row in diagnostics.get("reattach_matrix", [])) or bool(diagnostics.get("replace_single_instance", {}).get("replace")),
        }
        result["checks"] = checks
        if checks["control_identical_replace_succeeded"] and checks["gripper_not_fully_resolved_at_failure"] and checks["resolve_first_repair_succeeded"]:
            result["verdict"] = "V5_PROBE_LOOP1E_ROOTCAUSE_B_SUPPRESSED_GRIPPER_RESOLVE_FIRST_FIXABLE"
        elif checks["gripper_failure_reproduced"] and not checks["control_identical_replace_succeeded"]:
            result["verdict"] = "V5_PROBE_LOOP1E_ROOTCAUSE_A_IDENTICAL_CONTENT_REJECTED"
        elif checks["gripper_failure_reproduced"] and not checks["gripper_not_fully_resolved_at_failure"]:
            result["verdict"] = "V5_PROBE_LOOP1E_ROOTCAUSE_C_MATE_REATTACH_OR_COMPONENT_SPECIFIC"
        else:
            result["verdict"] = "V5_PROBE_LOOP1E_MIXED_OR_NOT_REPRODUCED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_DISCRIMINATOR_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                result["cleanup_document_count"] = close_all(sw)
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_exception"] = repr(cleanup_exc)
        try:
            post = {m.sha256(path): str(path) for path in PROTECTED_WATCH if path.is_file()}
            result["protected_post_unchanged"] = post == result.get("protected_pre")
        except Exception as exc:  # noqa: BLE001
            result["protected_post_exception"] = repr(exc)
        result["memory_available_gib_end"] = available_gib()
        result["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if str(result.get("verdict", "")).startswith("V5_PROBE_LOOP1E_ROOTCAUSE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
