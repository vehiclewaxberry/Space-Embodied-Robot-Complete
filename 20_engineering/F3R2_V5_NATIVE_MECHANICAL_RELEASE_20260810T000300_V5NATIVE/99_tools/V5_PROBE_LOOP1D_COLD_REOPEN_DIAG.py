#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1D live probe: cold read-only configuration activation diagnosis.

The earlier probe (V5_PROBE_LOOP1D_MATE_SUPPRESSION, log
99_tools/probe_logs/V5_PROBE_LOOP1D_MATE_SUPPRESSION_20260811T055940Z.log)
proved on the live session (PID 87516, SW2024 SP05, attach-only):
  * component SetSuppression2 does NOT cascade IFeature.IsSuppressed onto lock
    mates (P2) -> root cause of Loop1D MATE_CONFIGURATION_SUPPRESSION_FAIL;
  * explicit per-config mate suppression via
    IFeature.SetSuppression2(state, swThisConfiguration=1) works and persists
    across live configuration switches (P3/P4/P5);
  * but its P6 cold read-only reopen failed at the first
    ShowConfiguration2/ForceRebuild3 pair, so two facts remain unproven:
      (a) which exact call fails on a cold read-only document, and whether
          ResolveAllLightWeightComponents(True) (called by the Loop1D cold
          verifier) is involved;
      (b) whether explicit per-config mate suppression persists through
          save + cold read-only reopen (the Loop1D cold verifier re-runs the
          mate contract on the cold document).

This probe never builds or saves anything: it cold-opens the still-existing
probe assembly saved by the earlier run
(%TEMP%/V5_PROBE_LOOP1D_MATE_SUPPRESS_20260811T060726.584979Z.SLDASM, saved
with STATE_A active; STATE_A: mate 锁定2 explicitly suppressed; STATE_B: mate
锁定1 explicitly suppressed) read-only and measures each call separately:
  C0  open read-only, list configurations/components/ledger in as-opened state
  C1  ShowConfiguration2(STATE_A) -> bool; ForceRebuild3(True) -> bool
      (exact P6 sequence, but WITHOUT ResolveAllLightWeightComponents first)
  C2  ShowConfiguration2(STATE_B) -> bool; ForceRebuild3(True) -> bool
  C3  back to STATE_A; EditRebuild3() -> bool
  C4  STATE_B with EditRebuild3() -> bool; ledger readback both configs
  C5  close, reopen read-only again, this time WITH
      ResolveAllLightWeightComponents(True) first, then repeat the
      ShowConfiguration2/ForceRebuild3 sequence (isolates the resolver call)
  C6  session left document-empty

Read-only with respect to every existing file: nothing is written inside or
outside the V5 root except this probe's own stdout log.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as m  # noqa: E402

T0 = time.time()
TARGET = Path.home() / "AppData/Local/Temp/V5_PROBE_LOOP1D_MATE_SUPPRESS_20260811T060726.584979Z.SLDASM"


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def memory_gib() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().available / 2**30, 3)
    except Exception:  # noqa: BLE001
        return -1.0


def dump_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
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
                    row["error_code"] = int(base.value(sf, "GetErrorCode"))
                    mate = base.wrap(base.value(sf, "GetSpecificFeature2"), "IMate2", types, pythoncom)
                    endpoints: List[str] = []
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
    return rows


def dump_components(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        rows.append({
            "name2": str(base.value(component, "Name2")),
            "suppression": int(base.value(component, "GetSuppression2")),
            "fixed": bool(base.value(component, "IsFixed")),
        })
    return sorted(rows, key=lambda row: row["name2"])


def active_config_name(model: Any, types: Any, pythoncom: Any) -> str:
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    raw = base.value(manager, "ActiveConfiguration")
    if raw is None:
        return ""
    return str(base.value(base.wrap(raw, "IConfiguration", types, pythoncom), "Name"))


def step_show(model: Any, config: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"config": config}
    try:
        returned = model.ShowConfiguration2(config)
        out["show_returned"] = None if returned is None else bool(returned)
    except Exception as exc:  # noqa: BLE001
        out["show_exception"] = repr(exc)
    out["active_after_show"] = active_config_name(model, types, pythoncom)
    return out


def step_rebuild(model: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        returned = model.ForceRebuild3(True)
        out["force_rebuild3_returned"] = None if returned is None else bool(returned)
    except Exception as exc:  # noqa: BLE001
        out["force_rebuild3_exception"] = repr(exc)
    return out


def step_edit_rebuild(model: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        returned = model.EditRebuild3()
        out["edit_rebuild3_returned"] = None if returned is None else bool(returned)
    except Exception as exc:  # noqa: BLE001
        out["edit_rebuild3_exception"] = repr(exc)
    return out


def cold_open(sw: Any, types: Any, pythoncom: Any) -> Any:
    raw, errors, warnings = m.unpack_document(sw.OpenDoc6(str(TARGET), 2, 3, "", 0, 0), "PROBE_COLD_OPEN")
    if raw is None or errors != 0 or warnings != 0:
        raise RuntimeError(f"cold open failed errors={errors} warnings={warnings}")
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    if not bool(base.value(model, "IsOpenedReadOnly")):
        raise RuntimeError("cold open was not read-only")
    return model


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


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1D_COLD_REOPEN_DIAG_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "target_exists": TARGET.is_file(),
        "phases": {},
    }
    sw = types = pythoncom = None
    try:
        if not TARGET.is_file():
            raise RuntimeError(f"probe target missing: {TARGET}")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        result["memory_available_gib_start"] = memory_gib()
        log(f"attach: ok pid={session['pid']} rev={session['revision']} docs={session['document_count']}")

        # ---- C0..C4: cold reopen WITHOUT ResolveAllLightWeightComponents ----
        model = cold_open(sw, types, pythoncom)
        title = str(base.value(model, "GetTitle"))
        log(f"cold open (no resolver): {title}")
        names = [str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))]
        result["phases"]["C0_as_opened"] = {
            "configuration_names": names,
            "active": active_config_name(model, types, pythoncom),
            "components": dump_components(model, types, pythoncom),
            "ledger": dump_ledger(model, types, pythoncom),
        }
        result["phases"]["C1_state_a_show_force_rebuild"] = {
            **step_show(model, "STATE_A", types, pythoncom),
            **step_rebuild(model),
            "ledger": dump_ledger(model, types, pythoncom),
        }
        log(f"C1: STATE_A show={result['phases']['C1_state_a_show_force_rebuild'].get('show_returned')} force={result['phases']['C1_state_a_show_force_rebuild'].get('force_rebuild3_returned')}")
        result["phases"]["C2_state_b_show_force_rebuild"] = {
            **step_show(model, "STATE_B", types, pythoncom),
            **step_rebuild(model),
            "components": dump_components(model, types, pythoncom),
            "ledger": dump_ledger(model, types, pythoncom),
        }
        log(f"C2: STATE_B show={result['phases']['C2_state_b_show_force_rebuild'].get('show_returned')} force={result['phases']['C2_state_b_show_force_rebuild'].get('force_rebuild3_returned')}")
        result["phases"]["C3_state_a_show_edit_rebuild"] = {
            **step_show(model, "STATE_A", types, pythoncom),
            **step_edit_rebuild(model),
            "ledger": dump_ledger(model, types, pythoncom),
        }
        log(f"C3: STATE_A show={result['phases']['C3_state_a_show_edit_rebuild'].get('show_returned')} edit={result['phases']['C3_state_a_show_edit_rebuild'].get('edit_rebuild3_returned')}")
        result["phases"]["C4_state_b_show_edit_rebuild"] = {
            **step_show(model, "STATE_B", types, pythoncom),
            **step_edit_rebuild(model),
            "ledger": dump_ledger(model, types, pythoncom),
        }
        log(f"C4: STATE_B show={result['phases']['C4_state_b_show_edit_rebuild'].get('show_returned')} edit={result['phases']['C4_state_b_show_edit_rebuild'].get('edit_rebuild3_returned')}")
        sw.CloseDoc(title)
        log("closed first cold document")

        # ---- C5: cold reopen WITH ResolveAllLightWeightComponents(True) -----
        model2 = cold_open(sw, types, pythoncom)
        title2 = str(base.value(model2, "GetTitle"))
        log(f"cold open (with resolver): {title2}")
        resolve_out: Dict[str, Any] = {}
        try:
            resolve_out["resolve_all_returned"] = None
            returned = base.wrap(model2, "IAssemblyDoc", types, pythoncom).ResolveAllLightWeightComponents(True)
            resolve_out["resolve_all_returned"] = None if returned is None else bool(returned)
        except Exception as exc:  # noqa: BLE001
            resolve_out["resolve_all_exception"] = repr(exc)
        result["phases"]["C5_with_resolver"] = {
            "resolve": resolve_out,
            "state_a": {**step_show(model2, "STATE_A", types, pythoncom), **step_rebuild(model2), "ledger": dump_ledger(model2, types, pythoncom)},
            "state_b": {**step_show(model2, "STATE_B", types, pythoncom), **step_rebuild(model2), "components": dump_components(model2, types, pythoncom), "ledger": dump_ledger(model2, types, pythoncom)},
        }
        log(f"C5: resolve={resolve_out.get('resolve_all_returned')} A show={result['phases']['C5_with_resolver']['state_a'].get('show_returned')} force={result['phases']['C5_with_resolver']['state_a'].get('force_rebuild3_returned')} B show={result['phases']['C5_with_resolver']['state_b'].get('show_returned')} force={result['phases']['C5_with_resolver']['state_b'].get('force_rebuild3_returned')}")
        sw.CloseDoc(title2)

        # ---- verdict synthesis ----
        def mate(rows: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
            return next((row for row in rows if row.get("feature_name") == name), {})

        c1 = result["phases"]["C1_state_a_show_force_rebuild"]
        c2 = result["phases"]["C2_state_b_show_force_rebuild"]
        c5 = result["phases"]["C5_with_resolver"]
        checks = {
            "C1_show_state_a_ok": c1.get("show_returned") is True,
            "C1_force_rebuild_ok": c1.get("force_rebuild3_returned") is True,
            "C1_state_a_m2_suppressed_persisted": mate(c1.get("ledger", []), "锁定2").get("suppressed") is True,
            "C1_state_a_m1_resolved_persisted": mate(c1.get("ledger", []), "锁定1").get("suppressed") is False,
            "C2_show_state_b_ok": c2.get("show_returned") is True,
            "C2_force_rebuild_ok": c2.get("force_rebuild3_returned") is True,
            "C2_state_b_m1_suppressed_persisted": mate(c2.get("ledger", []), "锁定1").get("suppressed") is True,
            "C2_state_b_m2_resolved_persisted": mate(c2.get("ledger", []), "锁定2").get("suppressed") is False,
            "C5_show_state_a_ok": c5["state_a"].get("show_returned") is True,
            "C5_force_rebuild_state_a_ok": c5["state_a"].get("force_rebuild3_returned") is True,
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1D_COLD_REOPEN_DIAG_PASS" if all(checks.values()) else "V5_PROBE_LOOP1D_COLD_REOPEN_DIAG_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1D_COLD_REOPEN_DIAG_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                remaining = close_all(sw)
                result["cleanup_document_count"] = remaining
                log(f"cleanup: document_count={remaining}")
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_exception"] = repr(cleanup_exc)
        result["memory_available_gib_end"] = memory_gib()
        result["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1D_COLD_REOPEN_DIAG_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
