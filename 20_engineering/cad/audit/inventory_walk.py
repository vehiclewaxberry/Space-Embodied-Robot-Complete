"""MECH-INVENTORY-AUDIT-01 / 步骤 1：只读文件盘点。

严格只读：只 stat / 读字节做哈希 / 读文本判类型。不创建、不修改、不移动
任何被审计对象；唯一写出目标是本 audit/ 目录。
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

CAD = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad")
REPO = CAD.parent.parent
OUT = CAD / "audit"
NOW = datetime.now(timezone.utc).isoformat()

SCAN = {
    "V2_0": CAD / "Space_Embodied_Robot_CAD_V2_0",
    "V2_1": CAD / "Space_Embodied_Robot_CAD_V2_1",
    "V2_2": CAD / "Space_Embodied_Robot_CAD_V2_2",
    "V2_2_NATIVE": CAD / "Space_Embodied_Robot_CAD_V2_2_NATIVE",
    "SPACECRAFT_LAYOUT": CAD / "spacecraft_layout",
    "V0_1": CAD / "Space_Embodied_Robot_CAD_V0_1",
    "V1_0": CAD / "Space_Embodied_Robot_CAD_V1_0",
    "FAILED_BUILDS": CAD / "_failed_builds",
}
SUBAREA = {   # 任务书点名的子域 → 归属根
    "ASSET_00": "Space_Embodied_Robot_CAD_V2_2/evidence/asset00",
    "B601_SWAP_01": "Space_Embodied_Robot_CAD_V2_2/evidence/b601_swap_01",
    "STAGE_100_CODEX": "Space_Embodied_Robot_CAD_V2_2/100_Mechanical_Continuation",
    "STAGE_110_LAYOUT": "Space_Embodied_Robot_CAD_V2_2/110_Layout_and_Deployment_01",
    "STAGE_120_POSEMAP": "Space_Embodied_Robot_CAD_V2_2/120_B601_Geometry_and_PoseMap_02",
    "STAGE_130_VENDORCAD": "Space_Embodied_Robot_CAD_V2_2/130_B601_Vendor_CAD_Direct_Integration_03",
}

NATIVE_EXT = {".SLDPRT", ".SLDASM", ".SLDDRW"}
CLASSES = ["NATIVE_EDITABLE_SOLIDWORKS", "NATIVE_REFERENCE_SOLIDWORKS",
           "IMPORTED_DUMB_SOLID", "STEP_STAGING_ONLY", "URDF_KINEMATIC_PROXY",
           "MESH_VISUAL_PROXY", "ZERO_ENTITY_REFERENCE", "PYTHON_ANALYSIS_ONLY",
           "REPORT_ONLY", "BROKEN_OR_INCOMPLETE"]


def sha256(p: Path, limit=None):
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for c in iter(lambda: f.read(1 << 22), b""):
                h.update(c)
                if limit and f.tell() > limit:
                    break
    except OSError:
        return None
    return h.hexdigest()


def producer_of(path: Path, area: str):
    """生产者归属——以证据为准，不以印象为准。

    实证：
    - V2_0  evidence/b3_00/HUMAN_APPROVAL_RECORD.yaml 记 APPROVAL_CHANNEL=
            "Claude Code 会话人工指令"；构建日志 b3_*.jsonl；automation/b3_lib
    - V2_1  构建日志 b4_1_*.jsonl；automation/b3_lib + b4_1_acceptance.py
    - V2_2  构建日志 asset00_*.jsonl；automation/b3_lib + b5_*.py
    - V2_2_NATIVE 本轮 Claude 建（automation/build_native.py 复用 b3_lib）
    ⇒ 全部原生 SolidWorks 线均由 CLAUDE_CODE 经 b3_lib COM 层产出。
    - 100_Mechanical_Continuation：Codex（STEP-first build123d，cad_viewer 交接）
    - 110_Layout_and_Deployment_01：同为 STEP-first build123d 风格，无 SolidWorks
      接触；归 CODEX_OR_CLAUDE_STEP_TRACK，待人工确认（不臆断）
    """
    s = str(path).replace("\\", "/")
    if "/100_Mechanical_Continuation" in s:
        return "CODEX"
    if "/110_Layout_and_Deployment" in s:
        return "STEP_TRACK_PRODUCER_UNCONFIRMED"
    if area == "SPACECRAFT_LAYOUT":
        return "EXTERNAL"
    if area in ("V0_1", "V1_0"):
        return "EARLY_UNVERIFIED"
    return "CLAUDE_CODE"


def classify(p: Path):
    e = p.suffix.upper()
    if e in NATIVE_EXT:
        return "NATIVE_SOLIDWORKS_PENDING_SW_CHECK"
    if e in (".STEP", ".STP"):
        return "STEP_STAGING_ONLY"
    if e == ".URDF":
        return "URDF_KINEMATIC_PROXY"
    if e in (".STL", ".GLB", ".OBJ", ".PLY", ".3MF"):
        return "MESH_VISUAL_PROXY"
    if e == ".PY":
        return "PYTHON_ANALYSIS_ONLY"
    if e in (".MD", ".CSV", ".JSON", ".YAML", ".YML", ".JSONL", ".TXT", ".DOCX"):
        return "REPORT_ONLY"
    if e in (".PNG", ".JPG", ".BMP", ".PDF", ".SVG"):
        return "REPORT_ONLY"
    return "REPORT_ONLY"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    counts = {}
    for area, root in SCAN.items():
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            parts = set(p.parts)
            if "__pycache__" in parts or ".git" in parts:
                continue
            rel = p.relative_to(CAD).as_posix()
            sub = area
            for k, pref in SUBAREA.items():
                if rel.startswith(pref):
                    sub = k
                    break
            lock = p.name.startswith("~$")
            backup = "backup" in rel.lower() or "_failed_builds" in rel
            cls = classify(p)
            e = p.suffix.upper()
            big = p.stat().st_size
            rows.append({
                "artifact_id": f"{sub}::{p.name}",
                "producer": producer_of(p, area),
                "path": rel,
                "area": sub,
                "file_type": e.lstrip("."),
                "bytes": big,
                "sha256": (sha256(p) if big < 60_000_000 else "SKIPPED_TOO_LARGE"),
                "mtime_utc": datetime.fromtimestamp(
                    p.stat().st_mtime, timezone.utc).isoformat(),
                "class_prelim": cls,
                "is_lock_file": lock,
                "is_backup_or_failed": backup,
                "native_solidworks": e in NATIVE_EXT and not lock,
            })
            key = (sub, cls if not lock else "LOCK_FILE")
            counts[key] = counts.get(key, 0) + 1

    with open(OUT / "artifact_inventory.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    nat = [r for r in rows if r["native_solidworks"]]
    summary = {"audit_id": "MECH_INVENTORY_AUDIT_01_STEP1_WALK",
               "generated_utc": NOW, "readonly": True,
               "total_files": len(rows),
               "native_sw_files": len(nat),
               "lock_files": sum(1 for r in rows if r["is_lock_file"]),
               "by_area": {}, "native_by_area_producer": {}}
    for r in rows:
        a = summary["by_area"].setdefault(r["area"], {"files": 0, "native": 0,
                                                       "producers": {}})
        a["files"] += 1
        a["native"] += 1 if r["native_solidworks"] else 0
        a["producers"][r["producer"]] = a["producers"].get(r["producer"], 0) + 1
    for r in nat:
        k = f"{r['area']}|{r['producer']}"
        summary["native_by_area_producer"][k] = \
            summary["native_by_area_producer"].get(k, 0) + 1
    (OUT / "inventory_walk_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"files={len(rows)} native_sw={len(nat)} locks={summary['lock_files']}")
    for a, d in sorted(summary["by_area"].items()):
        print(f"  {a:22s} files={d['files']:5d} native={d['native']:4d} "
              f"producers={d['producers']}")


if __name__ == "__main__":
    main()
