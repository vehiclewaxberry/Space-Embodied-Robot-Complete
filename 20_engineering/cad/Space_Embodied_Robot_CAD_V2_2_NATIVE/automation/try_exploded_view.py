"""NATIVE-01：爆炸视图有界尝试（1 次，fail-closed 如实记录）。

风险预判：本机组件变换持久性缺陷已 3 次复现（V2.2 及本轮），
而爆炸视图正是以组件变换存储 —— 同型风险。故只做一次尝试并读回验证。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

V22_AUTO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation")
sys.path.insert(0, str(V22_AUTO))
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                            open_document, rebuild_or_fail)
from build_native import TOP_ASM

ROOT = HERE.parent
NOW = datetime.now(timezone.utc).isoformat()


def main():
    log = BuildLog("native01_explode")
    sw = connect(log, visible=True)
    m = open_document(sw, log, ROOT / "Assembly" / f"{TOP_ASM}.SLDASM")
    m.ShowConfiguration2("STOWED")
    asm = cast(m, "IAssemblyDoc")
    cfg = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration
    rec = {"id": "NATIVE01_EXPLODED_VIEW_ATTEMPT", "generated_utc": NOW,
           "attempts": []}
    before = int(cfg.GetExplodedViewCount())
    rec["exploded_views_before"] = before

    apis = [n for n in ("ToolsExplode", "NewExplodedView", "CreateExplodedView")
            if getattr(asm, n, None) is not None or getattr(m, n, None) is not None]
    rec["available_explode_apis"] = apis
    if not apis:
        rec["attempts"].append({"api": None, "ok": False,
                                 "error": "makepy 早绑定接口中不存在任何爆炸视图创建方法"})
    else:
        try:
            fn = getattr(asm, apis[0], None) or getattr(m, apis[0])
            # 逐组件沿 +Z 拉开（顶层 7 件）；签名按 legacy ToolsExplode 试一次
            comps = asm.GetComponents(True)
            m.ClearSelection2(True)
            for i, c in enumerate(comps):
                cast(c, "IComponent2").Select4(i > 0, None, False)
            ok = fn(len(comps), 0, 0, 0, 0, 0, 0, 0, 0)
            rec["attempts"].append({"api": apis[0], "ok": bool(ok)})
        except Exception as e:
            rec["attempts"].append({"api": apis[0], "ok": False, "error": str(e)})

    rebuild_or_fail(m, log, "explode_attempt")
    after = int(cast(m, "IModelDoc2").ConfigurationManager
                .ActiveConfiguration.GetExplodedViewCount())
    rec["exploded_views_after"] = after
    rec["created"] = after > before
    rec["verdict"] = ("EXPLODED_VIEW_CREATED" if after > before else
                       "EXPLODED_VIEW_NOT_ACHIEVED")
    rec["substitute"] = ("MAINTENANCE 配置（外板抑制=开盖态）+ 工程图 A-A 真剖视 "
                         "共同表达装配层次；两者均为原生产物")
    (ROOT / "evidence/exploded_view_attempt.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    sw.CloseAllDocuments(True)
    print(json.dumps(rec, ensure_ascii=False))


if __name__ == "__main__":
    main()
