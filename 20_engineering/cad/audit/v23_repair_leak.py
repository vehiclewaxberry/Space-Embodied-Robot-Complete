"""V2.3 阶段 0 整改：把泄漏回冻结基线的组件重指到 V2.3 内部副本。

背景：整树拷贝后，`Removable_Panels.SLDASM`（顶层组件，但物理位置嵌在
01_Primary_Structure/Removable_Panels/ 下）在 V2.3 顶装中仍按烘死的绝对路径
解析回 V2_2_NATIVE。冷启动复核确认非会话缓存。
整改只写 V2.3（工作版本），冻结基线全程只读并在整改后用冻结哈希自证零变化。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CAD = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad")
sys.path.insert(0, str(CAD / "Space_Embodied_Robot_CAD_V2_2/automation"))
from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                            open_document, rebuild_or_fail, save)

SRC = CAD / "Space_Embodied_Robot_CAD_V2_2_NATIVE"
DST = CAD / "Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION"
TOP_REL = "Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM"
NOW = datetime.now(timezone.utc).isoformat()


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def main():
    log = BuildLog("v23_repair")
    sw = connect(log)
    m = open_document(sw, log, DST / TOP_REL)
    asm = cast(m, "IAssemblyDoc")
    rec = {"id": "V23_PHASE0_LEAK_REPAIR", "generated_utc": NOW, "repairs": []}

    leaks = []
    for c in (asm.GetComponents(False) or []):
        c2 = cast(c, "IComponent2")
        cp = get_com_member(c2, "GetPathName")
        if cp and DST.as_posix().lower() not in Path(cp).as_posix().lower():
            leaks.append((c2, Path(cp)))
    rec["leaks_found"] = [str(p) for _, p in leaks]

    for c2, old in leaks:
        try:
            rel = old.relative_to(SRC)
        except ValueError:
            rec["repairs"].append({"old": str(old), "ok": False,
                                    "error": "不在冻结基线下，无法映射"})
            continue
        new = DST / rel
        if not new.exists():
            rec["repairs"].append({"old": str(old), "new": str(new), "ok": False,
                                    "error": "V2.3 内无对应副本"})
            continue
        m.ClearSelection2(True)
        c2.Select4(False, None, False)
        ok = asm.ReplaceComponents(str(new), "", True, True)
        rec["repairs"].append({"old": old.name, "new": str(new.relative_to(CAD)),
                                "api_ok": bool(ok)})
        log.event("REPLACE_COMPONENT", part=old.name, ok=bool(ok))

    rebuild_or_fail(m, log, "after_replace")
    save(m, log)
    sw.CloseAllDocuments(True)

    # 复验：隔离 + 基线零变化
    sw = connect(log)
    m = open_document(sw, log, DST / TOP_REL)
    asm = cast(m, "IAssemblyDoc")
    outside = []
    total = 0
    for c in (asm.GetComponents(False) or []):
        cp = get_com_member(cast(c, "IComponent2"), "GetPathName")
        if not cp:
            continue
        total += 1
        if DST.as_posix().lower() not in Path(cp).as_posix().lower():
            outside.append(cp)
    rec["post_repair"] = {"components_total": total,
                           "resolved_outside_v23": outside,
                           "verdict": "ISOLATED" if not outside
                                      else "STILL_LEAKING"}
    rec["configurations_after_repair"] = list(m.GetConfigurationNames() or [])
    sw.CloseAllDocuments(True)

    man = (DST / "baseline_freeze_manifest.yaml").read_text(encoding="utf-8")
    frozen, cur = {}, None
    for line in man.splitlines():
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            cur = line.strip().rstrip(":")
        elif line.strip().startswith("sha256:") and cur:
            frozen[cur] = line.split("sha256:")[1].strip()
    bad = [k for k, h in frozen.items()
           if not (SRC / k).exists() or sha256(SRC / k) != h]
    rec["source_baseline_unchanged_after_repair"] = {
        "checked": len(frozen), "violations": bad,
        "proof": "PASS" if not bad else "FAIL"}

    (DST / "phase0_leak_repair.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: rec[k] for k in
                      ("leaks_found", "repairs", "post_repair",
                       "source_baseline_unchanged_after_repair",
                       "configurations_after_repair")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
