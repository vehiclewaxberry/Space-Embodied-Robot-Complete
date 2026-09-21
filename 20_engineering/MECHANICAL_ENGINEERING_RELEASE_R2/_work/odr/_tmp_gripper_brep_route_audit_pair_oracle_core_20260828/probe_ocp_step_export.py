#!/usr/bin/env python3
"""Probe same-process deterministic STEPControl export of validated finger compounds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from OCP.Font import Font_FontMgr
from OCP.TCollection import TCollection_AsciiString, TCollection_HAsciiString

_font_manager = Font_FontMgr.GetInstance_s()
_font_manager.AddFontAlias(TCollection_AsciiString("singleline"), TCollection_AsciiString("Arial"))

from build123d import import_step
from OCP.APIHeaderSection import APIHeaderSection_MakeHeader
from OCP.IFSelect import IFSelect_ReturnStatus
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_StepModelType, STEPControl_Writer


HERE = Path(__file__).resolve().parent
FROZEN_TIMESTAMP = "2026-08-28T00:00:00+00:00"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def export_ocp(shape, path: Path, label: str) -> None:
    writer = STEPControl_Writer()
    Interface_Static.SetIVal_s("write.surfacecurve.mode", 1)
    Interface_Static.SetIVal_s("write.precision.mode", 0)
    transfer_status = writer.Transfer(shape.wrapped, STEPControl_StepModelType.STEPControl_AsIs)
    if transfer_status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"STEP transfer failed: {transfer_status}")
    header = APIHeaderSection_MakeHeader(writer.Model())
    if not header.IsDone():
        header = APIHeaderSection_MakeHeader(0)
        header.Apply(writer.Model())
    header.SetName(TCollection_HAsciiString(label))
    header.SetTimeStamp(TCollection_HAsciiString(FROZEN_TIMESTAMP))
    header.SetOriginatingSystem(TCollection_HAsciiString("OCP_STEPControl_Writer"))
    status = writer.Write(str(path))
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed: {status}")


def main() -> None:
    output_rows = {}
    for side in ("left", "right"):
        source = HERE / "verified_run_a" / f"B601_GRIPPER_{side.upper()}_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE.step"
        shape = import_step(source)
        label = f"B601_GRIPPER_{side.upper()}_FINGER_GRIPPER_LINK_LOCAL_R1_SOURCE"
        paths = []
        for suffix in ("a", "b"):
            folder = HERE / f"ocp_run_{suffix}"
            folder.mkdir(exist_ok=True)
            path = folder / source.name
            if path.exists():
                raise RuntimeError(f"refusing to overwrite temporary probe: {path}")
            export_ocp(shape, path, label)
            paths.append(path)
        output_rows[side] = {
            "source": str(source),
            "exports": [{"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in paths],
            "bitwise_repeatable_same_process": sha256(paths[0]) == sha256(paths[1]),
        }
    output = HERE / "TEMP_OCP_STEPCONTROL_DETERMINISM_PROBE_V1.json"
    if output.exists():
        raise RuntimeError(f"refusing to overwrite temporary receipt: {output}")
    output.write_text(json.dumps(output_rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output_rows, indent=2))


if __name__ == "__main__":
    main()
