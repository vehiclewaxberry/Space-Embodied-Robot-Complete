"""Read-only recovery probe for the registered B601 STEP.

This does not replace or overwrite the ASSET-00 scratch assembly.  It verifies
whether the exact registered STEP can still be loaded into a fully resolved
in-memory assembly after the scratch assembly's transient spiop dependencies
have disappeared.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import b601_swap_01 as base
from b3_lib.sw_core import B3FailClosed, BuildLog, cast, connect, get_com_member


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_step(sw, log):
    import_data = sw.GetImportFileData(str(base.SOURCE_STEP))
    if import_data is None:
        log.fail("GetImportFileData returned None", path=str(base.SOURCE_STEP))
    started = time.perf_counter()
    errors_value = 0
    try:
        result = sw.LoadFile4(str(base.SOURCE_STEP), "", import_data, 0)
        if isinstance(result, tuple):
            model = result[0]
            if len(result) > 1:
                errors_value = as_int(result[1])
        else:
            model = result
    except TypeError:
        errors = base.core.byref_i4()
        model = sw.LoadFile4(str(base.SOURCE_STEP), "", import_data, errors)
        errors_value = as_int(errors.value)
    elapsed = round(time.perf_counter() - started, 3)
    if model is None:
        log.fail("LoadFile4 failed", errors=errors_value, elapsed_sec=elapsed)
    log.event("STEP_LOADED_IN_MEMORY", errors=errors_value, elapsed_sec=elapsed)
    return cast(model, "IModelDoc2"), errors_value, elapsed


def main():
    base.EVIDENCE.mkdir(parents=True, exist_ok=True)
    log = BuildLog("b601_swap_01_reimport_probe")
    if not base.SOURCE_ASM.exists() or not base.SOURCE_STEP.exists():
        log.fail("registered source input missing")
    step_hash = base.sha256(base.SOURCE_STEP)
    if step_hash.lower() != base.EXPECTED_STEP_SHA256:
        log.fail("vendor STEP hash mismatch", actual=step_hash)
    scratch_hash_before = base.sha256(base.SOURCE_ASM)

    sw = connect(log, visible=False)
    sw.CloseAllDocuments(True)
    model, errors_value, elapsed = load_step(sw, log)
    doc_type = as_int(base.call_or_value(model, "GetType", -1), -1)
    if doc_type != 2:
        log.fail("registered STEP did not load as assembly", doc_type=doc_type)
    asm = cast(model, "IAssemblyDoc")
    try:
        resolve_return = asm.ResolveAllLightWeightComponents(True)
    except Exception as exc:
        resolve_return = f"NOT_CALLED:{type(exc).__name__}:{exc}"
    top_records = [base.component_record(c) for c in base.as_list(asm.GetComponents(True))]
    all_records = [base.component_record(c) for c in base.as_list(asm.GetComponents(False))]
    unresolved = [r for r in all_records if r.get("is_suppressed") or not r.get("bbox_mm")]
    scratch_hash_after = base.sha256(base.SOURCE_ASM)
    result = {
        "probe_id": "B601_SWAP01_REGISTERED_STEP_RECOVERY_PROBE",
        "generated_utc": base.utc_now(),
        "read_only": True,
        "recovery_only_no_source_replacement": True,
        "source_step": {
            "path": str(base.SOURCE_STEP),
            "sha256": step_hash,
            "registry_match": True,
        },
        "source_scratch": {
            "path": str(base.SOURCE_ASM),
            "sha256_before": scratch_hash_before,
            "sha256_after": scratch_hash_after,
            "unchanged": scratch_hash_before == scratch_hash_after,
        },
        "load": {
            "api": "GetImportFileData+LoadFile4",
            "errors": errors_value,
            "elapsed_sec": elapsed,
            "doc_type": doc_type,
            "resolve_return": str(resolve_return),
        },
        "component_count_top": len(top_records),
        "component_count_all": len(all_records),
        "unresolved_or_boxless_count": len(unresolved),
        "world_bbox_mm": base.bbox_union(all_records),
        "top_components": top_records,
        "all_components": all_records,
        "recovery_gate": "PASS" if len(all_records) >= 358 and len(unresolved) == 0 else "HOLD",
    }
    out = base.EVIDENCE / "registered_step_recovery_probe.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sw.CloseAllDocuments(True)
    log.event("RECOVERY_PROBE_WRITTEN", path=str(out), gate=result["recovery_gate"], all=len(all_records))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["recovery_gate"] != "PASS":
        raise B3FailClosed("registered STEP recovery probe did not resolve the complete assembly")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as exc:
        print(f"FAIL_CLOSED: {exc}")
        sys.exit(1)
