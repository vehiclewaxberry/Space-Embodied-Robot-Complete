"""V2.3 阶段 0 收口：引用归属核验（防"表面副本、实际改冻结基线"）。

判据：V2.3 顶装的**每一个**组件解析路径都必须落在 V2.3 根目录内。
任何一个指回 V2_2_NATIVE 即判 LEAKS_TO_SOURCE_BASELINE 并要求整改。
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
                            open_document, rebuild_or_fail)

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
    log = BuildLog("v23_isolation")
    sw = connect(log)
    m = open_document(sw, log, DST / TOP_REL)
    rebuild_or_fail(m, log, "v23_top")
    asm = cast(m, "IAssemblyDoc")
    inside, outside = [], []
    for c in (asm.GetComponents(False) or []):
        cp = get_com_member(cast(c, "IComponent2"), "GetPathName")
        if not cp:
            continue
        pl = Path(cp).as_posix().lower()
        if DST.as_posix().lower() in pl:
            inside.append(Path(cp).name)
        else:
            outside.append(cp)
    cfgs = list(m.GetConfigurationNames() or [])
    rec = {"id": "V23_PHASE0_ISOLATION_VERIFY", "generated_utc": NOW,
           "v23_top": (DST / TOP_REL).as_posix(),
           "v23_top_sha256": sha256(DST / TOP_REL),
           "components_total": len(inside) + len(outside),
           "resolved_inside_v23": len(inside),
           "resolved_outside_v23": outside,
           "configurations": cfgs,
           "verdict": "ISOLATED" if not outside else "LEAKS_TO_SOURCE_BASELINE"}
    sw.CloseAllDocuments(True)

    # 源基线在本次打开后是否仍零变化
    man = (DST / "baseline_freeze_manifest.yaml").read_text(encoding="utf-8")
    frozen = {}
    cur_key = None
    for line in man.splitlines():
        if line.startswith("  ") and line.rstrip().endswith(":") and not line.startswith("    "):
            cur_key = line.strip().rstrip(":")
        elif line.strip().startswith("sha256:") and cur_key:
            frozen[cur_key] = line.split("sha256:")[1].strip()
    changed = []
    for rel, h in frozen.items():
        p = SRC / rel
        if not p.exists():
            changed.append(f"MISSING:{rel}")
        elif sha256(p) != h:
            changed.append(f"CHANGED:{rel}")
    rec["source_baseline_post_open_unchanged"] = {
        "checked": len(frozen), "violations": changed,
        "proof": "PASS" if not changed else "FAIL"}
    rec["source_lock_files_present"] = len(list(SRC.rglob("~$*")))

    (DST / "phase0_isolation_verify.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: rec[k] for k in
                      ("components_total", "resolved_inside_v23",
                       "resolved_outside_v23", "verdict",
                       "source_baseline_post_open_unchanged",
                       "source_lock_files_present")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
