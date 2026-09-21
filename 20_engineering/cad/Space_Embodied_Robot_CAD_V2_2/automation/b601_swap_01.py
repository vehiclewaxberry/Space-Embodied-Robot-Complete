"""B601-SWAP-01: P-C high-fidelity static-geometry integration.

The first executable mode is intentionally read-only:

    python b601_swap_01.py probe

It inspects the ASSET-00 scratch assembly, records its dependency graph,
component hierarchy, transforms, and world-space bounding box, and never saves
the source document.  Build and verification modes are added only after the
probe establishes that the scratch document can be resolved on this machine.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

import b3_lib.sw_core as core
from b3_lib.sw_core import B3FailClosed, BuildLog, cast, connect, get_com_member


V22 = Path(
    r"F:/China Graduate Future Flight Vehicle Innovation Competition/"
    r"20_engineering/cad/Space_Embodied_Robot_CAD_V2_2"
)
SOURCE_STEP = Path(
    r"F:/Robotic arm/High_performance_robotics_arm/vendor/reBot-DevArm/"
    r"hardware/reBot_B601_DM/reBot_B601_DM_v1.1_20260425.step"
)
SOURCE_ASM = Path(
    r"C:/Users/stude/AppData/Local/Temp/claude/"
    r"F--China-Graduate-Future-Flight-Vehicle-Innovation-Competition/"
    r"f82d04fc-7dca-4a0f-ac0b-f39116f6b403/"
    r"scratchpad/b601_import/b601_import.SLDASM"
)
EVIDENCE = V22 / "evidence" / "b601_swap_01"
EXPECTED_STEP_SHA256 = (
    "87a0537d1afd50c04fc441fde11dd4f2ebbb368fe27f6c10fda8567be696d968"
)

core.V2_ROOT = V22
core.LOG_DIR = V22 / "evidence" / "build_logs"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        return list(value)
    except TypeError:
        return [value]


def call_or_value(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return get_com_member(obj, name)
    except Exception:
        return default


def component_record(component: Any) -> dict[str, Any]:
    c = cast(component, "IComponent2")
    name = str(call_or_value(c, "Name2", ""))
    path = str(call_or_value(c, "GetPathName", "") or "")
    parent = call_or_value(c, "GetParent")
    parent_name = (
        str(call_or_value(cast(parent, "IComponent2"), "Name2", ""))
        if parent is not None
        else None
    )
    transform = call_or_value(c, "Transform2")
    transform_data = (
        [float(v) for v in as_list(call_or_value(transform, "ArrayData"))]
        if transform is not None
        else None
    )
    try:
        box = c.GetBox(False, False)
    except Exception:
        box = None
    box_mm = (
        [round(float(v) * 1000.0, 6) for v in as_list(box)]
        if box is not None
        else None
    )
    return {
        "name": name,
        "parent": parent_name,
        "path": path,
        "path_exists": bool(path and Path(path).exists()),
        "is_virtual": bool(call_or_value(c, "IsVirtual", False)),
        "is_suppressed": bool(call_or_value(c, "IsSuppressed", False)),
        "transform": transform_data,
        "bbox_mm": box_mm,
    }


def bbox_union(records: list[dict[str, Any]]) -> list[float] | None:
    boxes = [r["bbox_mm"] for r in records if r.get("bbox_mm") and len(r["bbox_mm"]) == 6]
    if not boxes:
        return None
    return [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        min(b[2] for b in boxes),
        max(b[3] for b in boxes),
        max(b[4] for b in boxes),
        max(b[5] for b in boxes),
    ]


def dependency_records(raw: Any) -> list[dict[str, Any]]:
    values = [str(v) for v in as_list(raw)]
    # SOLIDWORKS returns a flattened repeating sequence.  Preserve the raw
    # sequence and also expose every path-looking item for existence checks;
    # the raw array remains authoritative if the installed SP changes layout.
    out: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        looks_like_path = (
            ":\\" in value
            or ":/" in value
            or value.lower().endswith((".sldprt", ".sldasm", ".step", ".stp"))
        )
        out.append(
            {
                "index": index,
                "value": value,
                "looks_like_path": looks_like_path,
                "exists_if_path": bool(Path(value).exists()) if looks_like_path else None,
            }
        )
    return out


def open_source_read_only(sw: Any, log: BuildLog) -> Any:
    if not SOURCE_ASM.exists():
        log.fail("ASSET-00 scratch assembly missing", path=str(SOURCE_ASM))
    errors_value = 0
    warnings_value = 0
    try:
        result = sw.OpenDoc6(str(SOURCE_ASM), 2, 3, "", 0, 0)
        if isinstance(result, tuple):
            model = result[0]
            if len(result) > 1:
                errors_value = int(result[1])
            if len(result) > 2:
                warnings_value = int(result[2])
        else:
            model = result
    except TypeError:
        errors = core.byref_i4()
        warnings = core.byref_i4()
        model = sw.OpenDoc6(str(SOURCE_ASM), 2, 3, "", errors, warnings)
        errors_value = int(errors.value)
        warnings_value = int(warnings.value)
    if isinstance(model, tuple):
        model = model[0]
    if model is None:
        log.fail(
            "OpenDoc6 read-only failed",
            path=str(SOURCE_ASM),
            errors=errors_value,
            warnings=warnings_value,
        )
    log.event(
        "DOC_OPEN_READ_ONLY",
        path=str(SOURCE_ASM),
        errors=errors_value,
        warnings=warnings_value,
    )
    return cast(model, "IModelDoc2")


def probe() -> dict[str, Any]:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    log = BuildLog("b601_swap_01_probe")
    if not SOURCE_STEP.exists():
        log.fail("registered vendor STEP missing", path=str(SOURCE_STEP))
    step_hash = sha256(SOURCE_STEP)
    if step_hash.lower() != EXPECTED_STEP_SHA256:
        log.fail(
            "vendor STEP hash mismatch",
            expected=EXPECTED_STEP_SHA256,
            actual=step_hash,
        )

    sw = connect(log, visible=False)
    sw.CloseAllDocuments(True)
    raw_dependencies = sw.GetDocumentDependencies2(
        str(SOURCE_ASM), True, True, True
    )
    model = open_source_read_only(sw, log)
    asm = cast(model, "IAssemblyDoc")

    top_records = [
        component_record(c) for c in as_list(asm.GetComponents(True))
    ]
    all_records = [
        component_record(c) for c in as_list(asm.GetComponents(False))
    ]
    result = {
        "probe_id": "B601_SWAP01_SOURCE_PROBE",
        "generated_utc": utc_now(),
        "read_only": True,
        "source_step": {
            "path": str(SOURCE_STEP),
            "bytes": SOURCE_STEP.stat().st_size,
            "sha256": step_hash,
            "registry_match": True,
        },
        "source_scratch_assembly": {
            "path": str(SOURCE_ASM),
            "bytes": SOURCE_ASM.stat().st_size,
            "sha256": sha256(SOURCE_ASM),
        },
        "dependencies": dependency_records(raw_dependencies),
        "component_count_top": len(top_records),
        "component_count_all": len(all_records),
        "top_components": top_records,
        "world_bbox_mm": bbox_union(all_records),
        "all_components": all_records,
    }
    out = EVIDENCE / "source_probe.json"
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sw.CloseAllDocuments(True)
    log.event(
        "SOURCE_PROBE_WRITTEN",
        path=str(out),
        top=len(top_records),
        all=len(all_records),
        bbox_mm=result["world_bbox_mm"],
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "probe"
    if mode != "probe":
        raise B3FailClosed(
            f"unsupported mode {mode!r}; probe must pass before build mode is enabled"
        )
    probe()


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as exc:
        print(f"FAIL_CLOSED: {exc}")
        sys.exit(1)
