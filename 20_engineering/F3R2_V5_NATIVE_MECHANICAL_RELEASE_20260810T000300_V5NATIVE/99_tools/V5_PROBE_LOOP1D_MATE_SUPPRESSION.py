#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1D live probe: per-configuration mate suppression semantics.

Loop1D failed closed at MATE_CONFIGURATION_SUPPRESSION_FAIL (receipt
13_validation/V5_LOOP1D_FAIL_20260811T054009.564404Z.json): in config LOCKED the
lock mate 锁定7 (HDRM_BASE x HDRM_LATCH_RELEASE_ARMED, occurrence
ARM_HDRM_LATCH_SLIDER-2) reported IFeature.IsSuppressed=False although its
endpoint occurrence was component-suppressed in that configuration.  The Loop1D
contract requires mate suppression to follow the active state-proxy endpoints.

This probe measures, on the live attach-only session (PID 87516, SW2024 SP05):
  P0  build a 3-component assembly (BASE fixed + two latch-slider occurrences)
      with two production lock mates (loop1a.add_component_lock_mate);
  P1  two configurations STATE_A/STATE_B via the production rename/add sequence;
  P2  STATE_A: component-suppress occurrence SLIDER-2 with the production
      SetSuppression2 drive + rebuild -> does the referencing lock mate
      auto-suppress (IFeature.IsSuppressed)?  (fail receipt says: NO)
  P3  STATE_A: explicit IFeature.SetSuppression2(swSuppressFeature=0,
      swThisConfiguration=1) on that mate -> immediate per-config readback;
  P4  STATE_B: production component drive (SLIDER-1 suppressed, SLIDER-2
      resolved) + explicit mate drive (M1 suppress, M2 unsuppress)
      -> per-config independence of mate suppression;
  P5  back to STATE_A -> explicit per-config states persist across live
      configuration switches;
  P6  save to a unique %TEMP% target (write-once, outside the V5 root), close,
      cold read-only reopen, per-config ledger readback -> persistence through
      save/reopen (the Loop1D cold verifier re-runs the mate contract there);
  P7  session left document-empty.

Never writes inside the V5 root, never overwrites/deletes/renames any existing
file, never saves into the release tree, and never mutates the referenced
parts (the production insert helper opens them read-only).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY as loop1a  # noqa: E402
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as m  # noqa: E402

T0 = time.time()
BASE_PART = m.NATIVE_PART_DIR / "ARM_HDRM_LOAD_TRANSFER_BASE.SLDPRT"
SLIDER_PART = m.NATIVE_PART_DIR / "ARM_HDRM_LATCH_SLIDER.SLDPRT"

COMPONENT_SPECS = [
    {"role": "BASE", "path": BASE_PART, "fixed": True, "center_mm": [0.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 5.0]},
    {"role": "LATCH_A", "path": SLIDER_PART, "fixed": False, "center_mm": [8.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
    {"role": "LATCH_B", "path": SLIDER_PART, "fixed": False, "center_mm": [2.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
]

SW_COMPONENT_SUPPRESSED = 0
SW_COMPONENT_RESOLVED = 1
SW_SUPPRESS_FEATURE = 0
SW_UNSUPPRESS_FEATURE = 1
SW_THIS_CONFIGURATION = 1
SW_SPECIFY_CONFIGURATION = 3


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def memory_gib() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().available / 2**30, 3)
    except Exception:  # noqa: BLE001
        return -1.0


def mate_feature_rows(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    """Fresh MateGroup traversal; rows carry the live IFeature handle."""
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
                rows.append({"feature": sf, "feature_name": str(base.value(sf, "Name"))})
                sub = base.value(sf, "GetNextSubFeature")
        feature = base.value(typed, "GetNextFeature")
    return rows


def dump_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in mate_feature_rows(model, types, pythoncom):
        sf = item["feature"]
        row: Dict[str, Any] = {"feature_name": item["feature_name"]}
        try:
            row["suppressed"] = bool(base.value(sf, "IsSuppressed"))
            row["error_code"] = int(base.value(sf, "GetErrorCode"))
            mate = base.wrap(base.value(sf, "GetSpecificFeature2"), "IMate2", types, pythoncom)
            row["mate_type"] = int(base.value(mate, "Type"))
            row["alignment"] = int(base.value(mate, "Alignment"))
            row["flipped"] = bool(base.value(mate, "Flipped"))
            endpoints: List[Optional[str]] = []
            for index in range(int(base.value(mate, "GetMateEntityCount"))):
                entity = base.wrap(mate.MateEntity(index), "IMateEntity2", types, pythoncom)
                raw_component = base.value(entity, "ReferenceComponent")
                if raw_component is None:
                    endpoints.append(None)
                else:
                    endpoints.append(str(base.value(base.wrap(raw_component, "IComponent2", types, pythoncom), "Name2")))
            row["endpoints"] = endpoints
        except Exception as exc:  # noqa: BLE001
            row["dump_exception"] = repr(exc)
        rows.append(row)
    return rows


def dump_component_handles(components: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for role, component in components.items():
        try:
            out[role] = {
                "name2": str(base.value(component, "Name2")),
                "suppression": int(base.value(component, "GetSuppression2")),
                "fixed": bool(base.value(component, "IsFixed")),
            }
        except Exception as exc:  # noqa: BLE001
            out[role] = {"dump_exception": repr(exc)}
    return out


def dump_live_components(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
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


def drive_components(components: Dict[str, Any], active_roles: Set[str]) -> Dict[str, Any]:
    """Production per-config component drive (insert-time handles)."""
    report: Dict[str, Any] = {}
    for role, component in components.items():
        wanted = SW_COMPONENT_RESOLVED if role in active_roles else SW_COMPONENT_SUPPRESSED
        returned = int(component.SetSuppression2(wanted))
        readback = int(base.value(component, "GetSuppression2"))
        report[role] = {"wanted": wanted, "returned": returned, "readback": readback, "ok": readback == wanted}
    return report


def drive_mate(model: Any, endpoint_names: Set[str], suppress: bool, types: Any, pythoncom: Any, config_names: Any = None, option: int = SW_THIS_CONFIGURATION) -> Dict[str, Any]:
    """Explicit per-config mate suppression drive on a fresh feature handle."""
    for item in mate_feature_rows(model, types, pythoncom):
        mate = base.wrap(base.value(item["feature"], "GetSpecificFeature2"), "IMate2", types, pythoncom)
        names: Set[str] = set()
        for index in range(int(base.value(mate, "GetMateEntityCount"))):
            entity = base.wrap(mate.MateEntity(index), "IMateEntity2", types, pythoncom)
            raw_component = base.value(entity, "ReferenceComponent")
            if raw_component is not None:
                names.add(str(base.value(base.wrap(raw_component, "IComponent2", types, pythoncom), "Name2")))
        if names == endpoint_names:
            state = SW_SUPPRESS_FEATURE if suppress else SW_UNSUPPRESS_FEATURE
            returned = item["feature"].SetSuppression2(state, option, config_names)
            readback = bool(base.value(item["feature"], "IsSuppressed"))
            return {
                "feature_name": item["feature_name"],
                "endpoints": sorted(names),
                "state_arg": state,
                "option_arg": option,
                "returned": None if returned is None else repr(returned),
                "readback_suppressed": readback,
                "ok": readback == suppress,
            }
    return {"endpoints": sorted(endpoint_names), "ok": False, "error": "MATE_FEATURE_NOT_FOUND"}


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
        "schema": "V5_PROBE_LOOP1D_MATE_SUPPRESSION_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "phases": {},
        "notes": [],
    }
    sw = types = pythoncom = None
    try:
        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        result["memory_available_gib_start"] = memory_gib()
        log(f"attach: ok pid={session['pid']} rev={session['revision']}")

        # ---- P0: build probe assembly with production insert + lock mates ----
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        components: Dict[str, Any] = {}
        unique_paths: Set[str] = set()
        for spec in COMPONENT_SPECS:
            components[spec["role"]] = m.insert_component(sw, model, assembly, spec, unique_paths, types, pythoncom)
            log(f"insert {spec['role']}: ok name2={base.value(components[spec['role']], 'Name2')}")
        created = []
        for first, second in (("BASE", "LATCH_A"), ("BASE", "LATCH_B")):
            created.append(loop1a.add_component_lock_mate(model, assembly, components[first], components[second], types, pythoncom))
            log(f"lock mate {first}x{second}: ok")
        model.ForceRebuild3(True)
        result["phases"]["P0_build"] = {
            "mates_created": created,
            "components": dump_component_handles(components),
            "ledger": dump_ledger(model, types, pythoncom),
        }

        # ---- P1: production configuration creation sequence ----
        manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
        active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
        active.Name = "STATE_A"
        manager.AddConfiguration2("STATE_B", "probe second state", "", 0, "", "probe", True)
        names = [str(value) for value in base.as_list(base.value(model, "GetConfigurationNames"))]
        if not bool(model.ShowConfiguration2("STATE_A")):
            raise RuntimeError("ShowConfiguration2(STATE_A) failed")
        result["phases"]["P1_configs"] = {"configuration_names": names, "active": "STATE_A"}
        log(f"configs: {names}")

        # ---- P2: STATE_A component suppression only (production drive) ----
        drive_a = drive_components(components, {"BASE", "LATCH_A"})
        model.ForceRebuild3(True)
        drive_a2 = drive_components(components, {"BASE", "LATCH_A"})
        model.ForceRebuild3(True)
        ledger_a_auto = dump_ledger(model, types, pythoncom)
        m2_auto = next((row for row in ledger_a_auto if set(row.get("endpoints") or []) == {"ARM_HDRM_LOAD_TRANSFER_BASE-1", "ARM_HDRM_LATCH_SLIDER-2"}), None)
        result["phases"]["P2_state_a_component_suppress_only"] = {
            "drive_first": drive_a,
            "drive_reapply": drive_a2,
            "live_components": dump_live_components(model, types, pythoncom),
            "ledger": ledger_a_auto,
            "auto_cascade_suppressed_m2": (m2_auto or {}).get("suppressed"),
        }
        log(f"P2: auto-cascade suppressed M2? {(m2_auto or {}).get('suppressed')}")

        # ---- P3: explicit per-config mate suppression in STATE_A ----
        m2_names = {"ARM_HDRM_LOAD_TRANSFER_BASE-1", "ARM_HDRM_LATCH_SLIDER-2"}
        drive_m2_suppress = drive_mate(model, m2_names, True, types, pythoncom)
        model.ForceRebuild3(True)
        ledger_a_explicit = dump_ledger(model, types, pythoncom)
        result["phases"]["P3_state_a_explicit_mate_suppress"] = {
            "drive": drive_m2_suppress,
            "ledger": ledger_a_explicit,
        }
        log(f"P3: explicit M2 suppress readback={drive_m2_suppress.get('readback_suppressed')}")

        # ---- P4: STATE_B production component drive + explicit mate drive ----
        if not bool(model.ShowConfiguration2("STATE_B")):
            raise RuntimeError("ShowConfiguration2(STATE_B) failed")
        drive_b = drive_components(components, {"BASE", "LATCH_B"})
        model.ForceRebuild3(True)
        drive_b2 = drive_components(components, {"BASE", "LATCH_B"})
        model.ForceRebuild3(True)
        m1_names = {"ARM_HDRM_LOAD_TRANSFER_BASE-1", "ARM_HDRM_LATCH_SLIDER-1"}
        drive_m1_suppress = drive_mate(model, m1_names, True, types, pythoncom)
        drive_m2_unsuppress = drive_mate(model, m2_names, False, types, pythoncom)
        model.ForceRebuild3(True)
        ledger_b = dump_ledger(model, types, pythoncom)
        result["phases"]["P4_state_b_explicit_drive"] = {
            "drive_first": drive_b,
            "drive_reapply": drive_b2,
            "drive_m1_suppress": drive_m1_suppress,
            "drive_m2_unsuppress": drive_m2_unsuppress,
            "live_components": dump_live_components(model, types, pythoncom),
            "ledger": ledger_b,
        }
        m2_b = next((row for row in ledger_b if set(row.get("endpoints") or []) == m2_names), {})
        log(f"P4: STATE_B M2 suppressed={m2_b.get('suppressed')} error={m2_b.get('error_code')} (want False/0)")

        # ---- P5: back to STATE_A; explicit per-config states must persist ----
        if not bool(model.ShowConfiguration2("STATE_A")):
            raise RuntimeError("ShowConfiguration2(STATE_A) failed")
        model.ForceRebuild3(True)
        ledger_a_back = dump_ledger(model, types, pythoncom)
        live_a_back = dump_live_components(model, types, pythoncom)
        result["phases"]["P5_back_to_state_a"] = {"live_components": live_a_back, "ledger": ledger_a_back}
        m2_a_back = next((row for row in ledger_a_back if set(row.get("endpoints") or []) == m2_names), {})
        m1_a_back = next((row for row in ledger_a_back if set(row.get("endpoints") or []) == m1_names), {})
        log(f"P5: STATE_A M1 suppressed={m1_a_back.get('suppressed')} M2 suppressed={m2_a_back.get('suppressed')} (want False/True)")

        # ---- P6: save (unique %TEMP% target) + cold read-only reopen ----
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        temp_target = Path(tempfile.gettempdir()) / f"V5_PROBE_LOOP1D_MATE_SUPPRESS_{stamp}.SLDASM"
        save = loop1a.save_assembly(model, temp_target)
        result["phases"]["P6_save"] = {"save": save, "temp_target": str(temp_target)}
        log(f"P6: saved probe assembly -> {temp_target}")
        count_after_close = close_all(sw)
        if count_after_close != 0:
            raise RuntimeError(f"probe assembly close left {count_after_close} documents")
        cold_rows: Dict[str, Any] = {}
        raw_cold, errors, warnings = m.unpack_document(sw.OpenDoc6(str(temp_target), 2, 3, "", 0, 0), "PROBE_COLD_OPEN")
        cold = base.wrap(raw_cold, "IModelDoc2", types, pythoncom)
        cold_title = str(base.value(cold, "GetTitle"))
        try:
            if raw_cold is None or errors != 0 or warnings != 0 or not bool(base.value(cold, "IsOpenedReadOnly")):
                raise RuntimeError(f"cold reopen not clean/read-only errors={errors} warnings={warnings}")
            cold_assembly = base.wrap(cold, "IAssemblyDoc", types, pythoncom)
            cold_assembly.ResolveAllLightWeightComponents(True)
            for config in ("STATE_A", "STATE_B"):
                if not bool(cold.ShowConfiguration2(config)) or not bool(cold.ForceRebuild3(True)):
                    raise RuntimeError(f"cold config activation/rebuild failed: {config}")
                cold_rows[config] = {
                    "live_components": dump_live_components(cold, types, pythoncom),
                    "ledger": dump_ledger(cold, types, pythoncom),
                }
        finally:
            sw.CloseDoc(cold_title)
        result["phases"]["P6_cold_reopen"] = cold_rows
        log("P6: cold reopen per-config ledgers captured")

        # ---- verdict synthesis ----
        def mate_state(rows: List[Dict[str, Any]], endpoints: Set[str]) -> Dict[str, Any]:
            return next((row for row in rows if set(row.get("endpoints") or []) == endpoints), {})

        checks = {
            "P2_auto_cascade_absent_or_present_reported": m2_auto is not None,
            "P3_explicit_suppress_readback": bool(drive_m2_suppress.get("ok")),
            "P4_state_b_m1_suppressed": mate_state(ledger_b, m1_names).get("suppressed") is True,
            "P4_state_b_m2_resolved": mate_state(ledger_b, m2_names).get("suppressed") is False,
            "P4_state_b_m2_error_zero": mate_state(ledger_b, m2_names).get("error_code") == 0,
            "P5_state_a_m1_resolved": mate_state(ledger_a_back, m1_names).get("suppressed") is False,
            "P5_state_a_m2_suppressed": mate_state(ledger_a_back, m2_names).get("suppressed") is True,
            "P6_cold_state_a_m2_suppressed": mate_state(cold_rows["STATE_A"]["ledger"], m2_names).get("suppressed") is True,
            "P6_cold_state_a_m1_resolved": mate_state(cold_rows["STATE_A"]["ledger"], m1_names).get("suppressed") is False,
            "P6_cold_state_b_m1_suppressed": mate_state(cold_rows["STATE_B"]["ledger"], m1_names).get("suppressed") is True,
            "P6_cold_state_b_m2_resolved": mate_state(cold_rows["STATE_B"]["ledger"], m2_names).get("suppressed") is False,
            "P6_cold_state_b_m2_error_zero": mate_state(cold_rows["STATE_B"]["ledger"], m2_names).get("error_code") == 0,
        }
        result["auto_cascade_observed"] = (m2_auto or {}).get("suppressed")
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1D_MATE_SUPPRESSION_PASS" if all(checks.values()) else "V5_PROBE_LOOP1D_MATE_SUPPRESSION_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1D_MATE_SUPPRESSION_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1D_MATE_SUPPRESSION_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
