#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1D live probe: dress rehearsal of the patched production flow.

The Loop1D script was patched after MATE_CONFIGURATION_SUPPRESSION_FAIL
(receipt 13_validation/V5_LOOP1D_FAIL_20260811T054009.564404Z.json) with:
  * per-configuration explicit mate suppression drive (root-cause fix; probe
    V5_PROBE_LOOP1D_MATE_SUPPRESSION P2-P5 + V5_PROBE_LOOP1D_COLD_REOPEN_DIAG);
  * fresh component/feature handles per configuration (stale-handle evidence:
    mate-suppression probe P4, Loop1C1 playbook);
  * read-only ShowConfiguration2 no-op-False tolerated via active-name
    readback (cold-reopen diag probe C1/C3/C5);
  * cold verifier passes live-resolved role components into
    configuration_snapshot (latent missing-argument fix);
  * deterministic occurrence-name contract gate in build_assembly.

This probe runs the PATCHED production functions end-to-end on a minimal
3-component / 2-configuration assembly whose state-proxy shape mirrors the
HDRM contract (one fixed BASE, two occurrences of the same latch part, two
lock mates, per-config active proxy), with a unique %TEMP% save target:

  R0  attach-only session check (PID pinned by attach_empty_session)
  R1  inserts via m.insert_component + occurrence-name contract readback
      (m.expected_name2_map)
  R2  lock mates via loop1a.add_component_lock_mate
  R3  m.configure_document (patched) -> 2 per-config snapshots
  R4  save via loop1a.save_assembly to unique %TEMP% target; close all
  R5  m.verify_assembly_cold (patched) with the live snapshots -> cold
      verdict + signature drift gate exercised
  R6  session left document-empty

Never writes inside the V5 root, never overwrites/deletes/renames any existing
file, and never mutates the referenced parts (inserts open them read-only).
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY as loop1a  # noqa: E402
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as m  # noqa: E402

T0 = time.time()
BASE_PART = m.NATIVE_PART_DIR / "ARM_HDRM_LOAD_TRANSFER_BASE.SLDPRT"
SLIDER_PART = m.NATIVE_PART_DIR / "ARM_HDRM_LATCH_SLIDER.SLDPRT"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
TARGET = Path(tempfile.gettempdir()) / f"V5_PROBE_LOOP1D_DRESS_REHEARSAL_{STAMP}.SLDASM"

PROBE_SPEC: Dict[str, Any] = {
    "target": TARGET,
    "configs": ["STATE_A", "STATE_B"],
    "state_roles": {"STATE_A": "LATCH_A", "STATE_B": "LATCH_B"},
    "components": [
        {"role": "BASE", "path": BASE_PART, "fixed": True, "center_mm": [0.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 5.0]},
        {"role": "LATCH_A", "path": SLIDER_PART, "fixed": False, "center_mm": [8.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
        {"role": "LATCH_B", "path": SLIDER_PART, "fixed": False, "center_mm": [2.0, 0.0, 150.0], "local_center_mm": [0.0, 0.0, 7.0]},
    ],
    "mate_pairs": [("BASE", "LATCH_A"), ("BASE", "LATCH_B")],
    "properties": {},
}


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def memory_gib() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().available / 2**30, 3)
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


def summarize_rows(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append({
            "configuration": row.get("configuration"),
            "active_roles": row.get("active_roles"),
            "mate_ledger": [
                {
                    "feature_name": mate.get("feature_name"),
                    "suppressed": mate.get("suppressed"),
                    "error": mate.get("feature_error_code"),
                    "endpoints": [item.get("name2") for item in mate.get("endpoints", [])],
                }
                for mate in row.get("mate_ledger", [])
            ],
        })
    return out


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1D_DRESS_REHEARSAL_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "phases": {},
    }
    sw = types = pythoncom = None
    try:
        if TARGET.exists():
            raise RuntimeError(f"unique probe target already exists: {TARGET}")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        result["memory_available_gib_start"] = memory_gib()
        log(f"attach: ok pid={session['pid']} rev={session['revision']} docs={session['document_count']}")

        # ---- R1/R2: inserts + occurrence-name contract + lock mates --------
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        components: Dict[str, Any] = {}
        unique_paths: Set[str] = set()
        for item in PROBE_SPEC["components"]:
            components[item["role"]] = m.insert_component(sw, model, assembly, item, unique_paths, types, pythoncom)
            log(f"insert {item['role']}: ok name2={base.value(components[item['role']], 'Name2')}")
        name_contract = m.expected_name2_map(PROBE_SPEC)
        actual_names = {role: str(base.value(component, "Name2")) for role, component in components.items()}
        result["phases"]["R1_inserts"] = {"name_contract": name_contract, "actual_names": actual_names, "name_contract_ok": actual_names == name_contract}
        if actual_names != name_contract:
            raise RuntimeError(f"occurrence-name contract mismatch: {actual_names} != {name_contract}")
        created = []
        for first, second in PROBE_SPEC["mate_pairs"]:
            created.append(loop1a.add_component_lock_mate(model, assembly, components[first], components[second], types, pythoncom))
            log(f"lock mate {first}x{second}: ok")
        result["phases"]["R2_mates"] = {"created": created}

        # ---- R3: patched production configure_document ----------------------
        live_rows = m.configure_document(model, components, PROBE_SPEC, types, pythoncom)
        result["phases"]["R3_configure_document"] = {"snapshots": summarize_rows(live_rows)}
        log("R3: patched configure_document returned per-config snapshots")

        # ---- R4: save to unique %TEMP% target + close all -------------------
        save = loop1a.save_assembly(model, TARGET)
        result["phases"]["R4_save"] = {"save": save}
        log(f"R4: saved -> {TARGET}")
        remaining = close_all(sw)
        if remaining != 0:
            raise RuntimeError(f"close_all left {remaining} documents")
        log("R4: session document-empty")

        # ---- R5: patched production verify_assembly_cold --------------------
        cold = m.verify_assembly_cold(sw, types, pythoncom, "PROBE_DRESS_REHEARSAL", PROBE_SPEC, live_rows)
        result["phases"]["R5_cold_verify"] = {
            "verdict": cold.get("verdict"),
            "cold_brep_bbox_mm": cold.get("cold_brep_bbox_mm"),
            "external_reference_count": cold.get("external_reference_count"),
            "auxiliary_reference_count": cold.get("auxiliary_reference_count"),
            "snapshots": summarize_rows(cold.get("configuration_ledgers", [])),
        }
        log(f"R5: cold verify verdict={cold.get('verdict')}")

        checks = {
            "R1_name_contract_ok": result["phases"]["R1_inserts"]["name_contract_ok"] is True,
            "R3_snapshot_count": len(live_rows) == 2,
            "R5_cold_verdict_pass": cold.get("verdict") == "V5_LOOP1D1_ASSEMBLY_COLD_CONFIG_MATE_REFERENCE_PASS",
            "R5_no_external_references": cold.get("external_reference_count") == 0 and cold.get("auxiliary_reference_count") == 0,
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1D_DRESS_REHEARSAL_PASS" if all(checks.values()) else "V5_PROBE_LOOP1D_DRESS_REHEARSAL_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1D_DRESS_REHEARSAL_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1D_DRESS_REHEARSAL_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
