from __future__ import annotations

import gc
import hashlib
import importlib.util
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ROUND_ROOT = PROJECT / r"20_engineering\F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
V5_ROOT = PROJECT / r"20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
BASE_HELPER = PROJECT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = V5_ROOT / r"99_tools\F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "E44BC52CFBDECCC107E361ACB0EDD993EFC46248EB663A994564B77BDA30F906"
SOURCE = V5_ROOT / r"03_top_assembly\SEI_MECH_B601_V5_NATIVE_BASELINE__LOOP1E_STAGING_20260820T140708.895028Z_PID31664.SLDASM"
BASELINE = ROUND_ROOT / r"01_native_cad\SEI_MECH_B601_V5R_LIGHTWEIGHT_OPERATIONAL_BASELINE.SLDASM"
STEP_OUT = ROUND_ROOT / r"01_native_cad\SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.step"
VISUAL_STL = ROUND_ROOT / r"01_native_cad\SEI_MECH_B601_V5R_VISUAL_RAW.stl"
COLLISION_STL = ROUND_ROOT / r"01_native_cad\SEI_MECH_B601_V5R_COLLISION_RAW.stl"
RECEIPT = ROUND_ROOT / r"04_validation\V5R_FALLBACK_A_VALIDATION_RECEIPT.json"
URDF = PROJECT / r"20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf"
OWNER_OVERRIDE = V5_ROOT / r"00_authority\V5_MEMORY_GATE_USER_OVERRIDE.json"

EXPECTED_CONFIGS = [
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
    "SOLAR_DEPLOY_ARM_LOCKED",
    "HDRM_RELEASE",
    "SERVICE",
    "RELEASE_CLEAR_END_STATE",
]

SW_DOC_ASSEMBLY = 2
SW_OPEN_LIGHTWEIGHT_READONLY = 195  # silent|read-only|override-default-lightweight|load-lightweight
SW_SAVE_CURRENT_VERSION = 0
SW_SAVE_SILENT = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fact(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_base() -> Any:
    if sha256(BASE_HELPER) != BASE_HELPER_SHA256 or sha256(BASE_HELPER_COPY) != BASE_HELPER_SHA256:
        raise RuntimeError("BASE_HELPER_HASH_DRIFT")
    for import_root in (PROJECT, V5_ROOT / "99_tools"):
        if str(import_root) not in sys.path:
            sys.path.insert(0, str(import_root))
    spec = importlib.util.spec_from_file_location("v5r_fallback_base", BASE_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("BASE_HELPER_IMPORT_FAIL")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dependencies(sw: Any, path: Path, base: Any) -> list[dict[str, Any]]:
    raw = base.as_list(base.value(sw, "GetDocumentDependencies2", str(path), True, True, False))
    if len(raw) % 2:
        raise RuntimeError(f"DEPENDENCY_ARRAY_ODD_LENGTH:{len(raw)}")
    rows = []
    for index in range(0, len(raw), 2):
        dep_path = Path(str(raw[index + 1])).resolve()
        rows.append(
            {
                "name": str(raw[index]),
                "path": dep_path.as_posix(),
                "exists": dep_path.is_file(),
                "bytes": dep_path.stat().st_size if dep_path.is_file() else None,
            }
        )
    return rows


def show_config(model: Any, name: str, base: Any, types: Any, pythoncom: Any) -> None:
    if bool(model.ShowConfiguration2(name)):
        return
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    if str(base.value(active, "Name")) != name:
        raise RuntimeError(f"CONFIG_ACTIVATION_FAIL:{name}")


def export_model(model: Any, output: Path, base: Any) -> dict[str, Any]:
    raise RuntimeError(
        "DISABLED_AFTER_20260820_SAVEAS_DRIFT:USE_HASH_PINNED_FALLBACK_B_NEUTRAL_ASSETS"
    )
    if output.exists():
        raise RuntimeError(f"WRITE_ONCE_EXPORT_EXISTS:{output}")
    extension = base.value(model, "Extension")
    result = base.value(
        extension,
        "SaveAs",
        str(output),
        SW_SAVE_CURRENT_VERSION,
        SW_SAVE_SILENT,
        None,
        0,
        0,
    )
    saved, outs = base.unpack(result)
    errors = int(outs[0]) if outs else 0
    warnings = int(outs[1]) if len(outs) > 1 else 0
    ok = bool(saved) and errors == 0 and output.is_file() and output.stat().st_size > 0
    return {
        "output": fact(output) if output.is_file() else {"path": output.resolve().as_posix(), "exists": False},
        "api_return": bool(saved),
        "errors": errors,
        "warnings": warnings,
        "pass": ok,
    }


def write_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main() -> int:
    started = utc_now()
    base = None
    sw = None
    model = None
    pythoncom = None
    pre_hashes: dict[str, str] = {}
    payload: dict[str, Any] = {
        "schema": "V5R_FALLBACK_A_VALIDATION_RECEIPT_V1",
        "timestamp_start_utc": started,
        "owner_ruling": "AUTHORIZE_LOW_MEMORY_EXECUTION_WITH_BOUNDED_NATIVE_ATTEMPTS",
        "memory_gate_status": "OWNER_OVERRIDE_LOW_MEMORY",
        "memory_gate_passed": False,
        "owner_override_used": True,
        "execution_authorized": True,
        "native_recovery_attempts_consumed": 2,
        "native_top_assembly_status": "HOLD",
        "formation": "BYTE_IDENTICAL_NO_REPLACE_COPY_OF_LOOP1E_ATTEMPT2_STAGING",
        "full_rebuild_exercised": False,
        "full_rebuild_status": "HOLD_LOW_MEMORY_LIGHTWEIGHT_VALIDATION",
    }
    try:
        required = [SOURCE, BASELINE, BASE_HELPER, BASE_HELPER_COPY, URDF, OWNER_OVERRIDE]
        missing = [path.as_posix() for path in required if not path.is_file() or path.stat().st_size <= 0]
        if missing:
            raise RuntimeError(f"REQUIRED_INPUT_MISSING:{missing}")
        if RECEIPT.exists():
            raise RuntimeError(f"WRITE_ONCE_RECEIPT_EXISTS:{RECEIPT}")
        if any(path.exists() for path in (STEP_OUT, VISUAL_STL, COLLISION_STL)):
            raise RuntimeError("WRITE_ONCE_EXPORT_TARGET_EXISTS")

        pre_hashes = {str(path.resolve()): sha256(path) for path in required}
        if pre_hashes[str(SOURCE.resolve())] != pre_hashes[str(BASELINE.resolve())]:
            raise RuntimeError("FALLBACK_COPY_NOT_BYTE_IDENTICAL")

        base = load_base()
        sw, types, pythoncom, attach = base.attach_empty_session()
        payload["solidworks"] = attach
        payload["memory_available_gib"] = float(base.available_gib())
        payload["inputs"] = {"source_staging": fact(SOURCE), "lightweight_baseline": fact(BASELINE)}

        dep_rows = dependencies(sw, BASELINE, base)
        missing_deps = [row for row in dep_rows if not row["exists"] or not row["bytes"]]
        payload["dependencies"] = {
            "count": len(dep_rows),
            "missing_reference_count": len(missing_deps),
            "external_to_round_root_count": sum(
                not os.path.commonpath([str(ROUND_ROOT.resolve()), row["path"]]).lower()
                == str(ROUND_ROOT.resolve()).lower()
                for row in dep_rows
            ),
            "rows": dep_rows,
        }
        if missing_deps:
            raise RuntimeError(f"MISSING_REFERENCES:{len(missing_deps)}")

        opened = sw.OpenDoc6(str(BASELINE), SW_DOC_ASSEMBLY, SW_OPEN_LIGHTWEIGHT_READONLY, "", 0, 0)
        model_raw, outs = base.unpack(opened)
        errors = int(outs[0]) if outs else 0
        warnings = int(outs[1]) if len(outs) > 1 else 0
        if model_raw is None or errors != 0:
            raise RuntimeError(f"COLD_OPEN_FAIL:errors={errors}:warnings={warnings}")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom)
        if int(base.value(model, "GetType")) != SW_DOC_ASSEMBLY:
            raise RuntimeError("COLD_OPEN_NOT_ASSEMBLY")

        actual_configs = [str(item) for item in base.as_list(base.value(model, "GetConfigurationNames"))]
        if len(actual_configs) != len(EXPECTED_CONFIGS) or set(actual_configs) != set(EXPECTED_CONFIGS):
            raise RuntimeError(f"CONFIGURATION_SET_DRIFT:{actual_configs}")
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        config_rows = []
        for name in EXPECTED_CONFIGS:
            show_config(model, name, base, types, pythoncom)
            box = [float(value) for value in base.as_list(assembly.GetBox(0))]
            if len(box) != 6:
                raise RuntimeError(f"BOUNDING_BOX_FAIL:{name}:{box}")
            components = [
                base.wrap(raw, "IComponent2", types, pythoncom)
                for raw in base.as_list(assembly.GetComponents(True))
            ]
            component_rows = [
                {
                    "name2": str(base.value(component, "Name2")),
                    "path": str(base.value(component, "GetPathName")).replace("\\", "/"),
                    "suppression": int(base.value(component, "GetSuppression2")),
                    "referenced_configuration": str(base.value(component, "ReferencedConfiguration")),
                }
                for component in components
            ]
            if len(component_rows) != 13:
                raise RuntimeError(f"TOP_COMPONENT_COUNT_FAIL:{name}:{len(component_rows)}")
            config_rows.append(
                {
                    "configuration": name,
                    "bounding_box_m": box,
                    "top_component_count": len(component_rows),
                    "components": component_rows,
                    "activation_pass": True,
                }
            )

        show_config(model, "SOLAR_DEPLOYED_NOMINAL", base, types, pythoncom)
        payload["cold_open"] = {
            "errors": errors,
            "warnings": warnings,
            "read_only_requested": True,
            "lightweight_requested": True,
            "configuration_count": len(config_rows),
            "configurations": config_rows,
            "restored_configuration": "SOLAR_DEPLOYED_NOMINAL",
        }

        exports = [
            export_model(model, STEP_OUT, base),
            export_model(model, VISUAL_STL, base),
            export_model(model, COLLISION_STL, base),
        ]
        payload["exports"] = exports
        if not all(row["pass"] for row in exports):
            raise RuntimeError("ONE_OR_MORE_NEUTRAL_EXPORTS_FAILED")

        title = str(base.value(model, "GetTitle"))
        sw.CloseDoc(title)
        model = None
        gc.collect()
        doc_count_after = int(base.value(sw, "GetDocumentCount"))
        payload["document_count_after_close"] = doc_count_after
        if doc_count_after != 0:
            raise RuntimeError(f"DOCUMENT_LEAK_AFTER_CLOSE:{doc_count_after}")

        post_hashes = {str(path.resolve()): sha256(path) for path in required}
        drift = {path: {"pre": pre_hashes[path], "post": post_hashes[path]} for path in pre_hashes if pre_hashes[path] != post_hashes[path]}
        payload["protected_hashes"] = {
            "pre": pre_hashes,
            "post": post_hashes,
            "drift": drift,
            "frozen_asset_hash_mismatch_count": len(drift),
        }
        if drift:
            raise RuntimeError(f"PROTECTED_HASH_DRIFT:{drift}")

        payload.update(
            {
                "timestamp_end_utc": utc_now(),
                "lightweight_operational_baseline_status": "PASS",
                "neutral_operational_baseline_status": "PASS",
                "native_top_assembly_status": "HOLD",
                "missing_reference_count": 0,
                "accepted_configuration_count": len(config_rows),
                "hard_stop_triggered": False,
                "verdict": "V5R_LIGHTWEIGHT_AND_NEUTRAL_OPERATIONAL_BASELINE_PASS_WITH_NATIVE_TOP_HOLD",
            }
        )
        write_once(RECEIPT, payload)
        print(json.dumps({"verdict": payload["verdict"], "receipt": fact(RECEIPT), "exports": exports}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        payload.update(
            {
                "timestamp_end_utc": utc_now(),
                "verdict": "V5R_FALLBACK_A_VALIDATION_OR_EXPORT_FAIL",
                "reason": str(exc),
                "traceback": traceback.format_exc(),
                "hard_stop_triggered": False,
                "next_automatic_action": "V5R_NEUTRAL_FALLBACK_B",
            }
        )
        fail_path = ROUND_ROOT / "04_validation" / ("V5R_FALLBACK_A_FAIL_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + ".json")
        try:
            write_once(fail_path, payload)
        except Exception:
            pass
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        try:
            if model is not None and sw is not None and base is not None:
                sw.CloseDoc(str(base.value(model, "GetTitle")))
        except Exception:
            pass
        model = None
        sw = None
        gc.collect()
        try:
            if pythoncom is not None:
                pythoncom.CoUninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
