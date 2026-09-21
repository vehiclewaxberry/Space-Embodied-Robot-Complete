"""V2_3_NATIVE_SYSTEM_INTEGRATION / 阶段 0：基线冻结 + 隔离复制 + 迁移矩阵。

人工裁决（2026-07-28）：
  CANONICAL_NATIVE_BASELINE = V2_2_NATIVE 顶装（审计现场打开+冷启动复核通过）
  V2_2_NATIVE = READ_ONLY_ACCEPTED_BASELINE（本脚本只读它，绝不写）
  V2_2 = REFERENCE_DONOR_ONLY（禁止整体合并顶装）
  Claude Code = 唯一 SolidWorks 写入者

复制方式：**SolidWorks Pack and Go**（而非文件拷贝）——保证 V2.3 顶装的组件引用
全部重指向 V2.3 内部；纯文件拷贝会让 SolidWorks 按缓存的绝对路径回指 V2.2_NATIVE，
造成"表面是副本、实际改的是冻结基线"的污染。复制后逐组件核验引用根目录。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

CAD = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad")
sys.path.insert(0, str(CAD / "Space_Embodied_Robot_CAD_V2_2/automation"))
from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                            open_document)

SRC = CAD / "Space_Embodied_Robot_CAD_V2_2_NATIVE"
DST = CAD / "Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION"
DONOR = CAD / "Space_Embodied_Robot_CAD_V2_2"
TOP_REL = "Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM"
CANONICAL_SHA = "30c09b50a0d2967ec1f48050caac34d12a43565c44978d54e3785595202def7a"
NOW = datetime.now(timezone.utc).isoformat()


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def freeze(root: Path):
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.name.startswith("~$"):
            continue
        out[p.relative_to(root).as_posix()] = {"sha256": sha256(p),
                                               "bytes": p.stat().st_size}
    return out


MIGRATION = [
    # (donor 模块, 决定, 理由)
    ("00_Master_Skeleton", "REBUILD",
     "V2.3 已有自己的骨架（18 基准面 + C5 负结果参数）；donor 骨架不迁入以免双骨架"),
    ("10_Primary_Structure", "EXCLUDE",
     "V2.3 主结构为框-纵梁-甲板-可拆板骨架化实现且零互穿；迁入 donor 会带回结构冲突"),
    ("20_B601_Interface", "EXCLUDE",
     "V2.3 已有 02_B601_Mount_and_Load_Path（8 件，接触面纪律，零互穿）"),
    ("30_B601_Controlled_Subassembly", "REBUILD",
     "donor 为 q0 bbox 代理；阶段 1 按三表示重建（HIFI/KINEMATIC_PROXY/MASS_SURROGATE）"),
    ("40_End_Effector_Module", "MIGRATE",
     "捕获头壳体/视觉窗——阶段 3 增量迁入，标 REFERENCE_OR_VISUAL_ONLY"),
    ("50_Solar_Array_Left", "MIGRATE_PANEL_ONLY",
     "只迁翼板本体（substrate/边框/电池区）；根部机构用 V2.3 已对齐 Codex 站位的 14 件/侧"),
    ("50_Solar_Array_Right", "MIGRATE_PANEL_ONLY", "同左"),
    ("60_GNC_Sensor_Module", "MIGRATE",
     "GNC 设备体积——阶段 3 迁入，MASS_AUTHORITY=NONE"),
    ("70_Propulsion_Module", "MIGRATE",
     "推进器安装座与喷管视觉模块——阶段 3 迁入"),
    ("80_Communication_Module", "MIGRATE", "通信 reference——阶段 3 迁入"),
    ("90_Thermal_Exterior", "MIGRATE", "热控 reference——阶段 3 迁入"),
    ("Assembly", "EXCLUDE",
     "**禁止整体合并顶装**（人工裁决）；V2.3 以自身顶装为唯一母体"),
]


def main():
    stage = "0"
    log = BuildLog("v23_phase0")
    rec = {"task": "V2_3_NATIVE_SYSTEM_INTEGRATION", "stage": stage,
           "generated_utc": NOW,
           "human_rulings": {
               "CANONICAL_NATIVE_BASELINE": f"{SRC.name}/{TOP_REL}",
               "CANONICAL_TOP_SHA256": CANONICAL_SHA,
               "V2_2_NATIVE_ROLE": "READ_ONLY_ACCEPTED_BASELINE",
               "V2_2_ROLE": "REFERENCE_DONOR_ONLY",
               "V2_0_V2_1_ROLE": "FROZEN_HISTORICAL_BASELINES",
               "SOLIDWORKS_SOLE_WRITER": "CLAUDE_CODE"}}

    # ── 1) 基线绑定核验（按哈希，不按目录名）────────────────────────────
    live = sha256(SRC / TOP_REL)
    rec["baseline_bind"] = {"path": (SRC / TOP_REL).as_posix(),
                             "expected_sha256": CANONICAL_SHA,
                             "live_sha256": live, "match": live == CANONICAL_SHA}
    if live != CANONICAL_SHA:
        raise SystemExit("基线哈希不匹配，停止（fail-closed）")

    # ── 2) 冻结全文件哈希（复制前）───────────────────────────────────────
    before = freeze(SRC)
    rec["baseline_file_count"] = len(before)

    # ── 3) Pack and Go 隔离复制 ─────────────────────────────────────────
    if DST.exists():
        rec["copy"] = {"method": "SKIPPED_TARGET_EXISTS", "target": DST.name}
    else:
        # Pack and Go 在本机绑定下 InvokeTypes(207) 报"非选择性的参数"（已试 1 次）。
        # 改为整树拷贝 + **引用归属核验**：核验步骤是防污染的真正保险——
        # 若 V2.3 顶装的组件解析回 V2_2_NATIVE，本脚本判 LEAKS 并要求整改，
        # 绝不以"看起来复制成功"收口。
        shutil.copytree(SRC, DST,
                        ignore=shutil.ignore_patterns("__pycache__", "~$*"))
        rec["copy"] = {"method": "TREE_COPY_WITH_REFERENCE_SCOPE_VERIFY",
                        "target": DST.as_posix(),
                        "packandgo_note": "GetPackAndGo 本机绑定失败（COM 207），"
                                           "有界尝试 1 次后改道"}

    # ── 4) 源基线零变化证明（复制后重算）─────────────────────────────────
    after = freeze(SRC)
    changed = [k for k in before if k in after
               and before[k]["sha256"] != after[k]["sha256"]]
    rec["source_baseline_unchanged"] = {
        "files_before": len(before), "files_after": len(after),
        "changed": changed, "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "proof": "PASS" if not changed and len(before) == len(after) else "FAIL"}

    # ── 5) V2.3 引用归属核验（必须全部指向 V2.3 内部）────────────────────
    v23_top = DST / TOP_REL
    rec["v23_top_exists"] = v23_top.exists()
    if v23_top.exists():
        sw = connect(log)
        m = open_document(sw, log, v23_top)
        asm = cast(m, "IAssemblyDoc")
        outside, inside = [], 0
        for c in (asm.GetComponents(False) or []):
            cp = get_com_member(cast(c, "IComponent2"), "GetPathName")
            if not cp:
                continue
            if DST.as_posix().lower() in Path(cp).as_posix().lower():
                inside += 1
            else:
                outside.append(cp)
        rec["v23_reference_scope"] = {
            "components_total": inside + len(outside),
            "inside_v23": inside, "outside_v23": outside,
            "verdict": "ISOLATED" if not outside else "LEAKS_TO_SOURCE_BASELINE"}
        sw.CloseAllDocuments(True)

    # ── 6) 输出 ─────────────────────────────────────────────────────────
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "baseline_freeze_manifest.yaml").write_text(
        "# V2.3 基线冻结清单（源=V2_2_NATIVE，READ_ONLY）\n"
        f"generated_utc: {NOW}\n"
        f"source_root: {SRC.name}\n"
        f"canonical_top: {TOP_REL}\n"
        f"canonical_top_sha256: {CANONICAL_SHA}\n"
        f"file_count: {len(before)}\n"
        f"unchanged_proof: {rec['source_baseline_unchanged']['proof']}\n"
        "files:\n" + "".join(
            f"  {k}:\n    sha256: {v['sha256']}\n    bytes: {v['bytes']}\n"
            for k, v in sorted(before.items())), encoding="utf-8")
    (DST / "migration_matrix.yaml").write_text(
        "# V2.2(donor) → V2.3 迁移矩阵（人工裁决：donor 仅 REFERENCE_DONOR_ONLY）\n"
        f"generated_utc: {NOW}\n"
        "policy: 禁止整体合并 donor 顶装；只允许逐子系统迁入并标注权威\n"
        "decisions:\n" + "".join(
            f"  - module: {mod}\n    decision: {dec}\n    reason: \"{why}\"\n"
            for mod, dec, why in MIGRATION), encoding="utf-8")
    (DST / "phase0_record.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: rec[k] for k in
                      ("baseline_bind", "copy", "source_baseline_unchanged",
                       "v23_reference_scope") if k in rec},
                     ensure_ascii=False, indent=1)[:1400])


if __name__ == "__main__":
    main()
