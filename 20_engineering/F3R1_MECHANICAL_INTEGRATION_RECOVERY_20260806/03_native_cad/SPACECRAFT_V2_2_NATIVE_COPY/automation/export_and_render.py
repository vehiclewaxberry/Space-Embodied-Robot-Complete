"""NATIVE-01 评审出图（辅助证据，非模型交付）。

背景（本轮实测，已入偏差 D-NATIVE-02）：本机 SolidWorks 的 SaveBMP 渲染固定
内部相机——ShowNamedView2（12 种调用形式）、IModelView.RotateAboutCenter、
可见/无头会话切换，图像哈希均逐位不变。故评审视图改由：
原生装配 → 按配置导出 STEP → OCC 网格化 → matplotlib 渲染（含真实剖切）。
原生 .SLDPRT/.SLDASM 仍是唯一交付模型；本脚本产物只作评审辅助。

用法：python export_and_render.py export|render|all
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

ROOT = HERE.parent
STEPS = ROOT / "evidence" / "config_steps"
VIEWS = ROOT / "views"
NOW = datetime.now(timezone.utc).isoformat()
EXPORT_CONFIGS = ["STOWED", "MAINTENANCE", "STOW_NO_CLOCK_COMPARATOR"]


def export():
    from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                                 open_document, rebuild_or_fail)
    from build_native import TOP_ASM
    STEPS.mkdir(parents=True, exist_ok=True)
    log = BuildLog("native01_export")
    sw = connect(log)
    m = open_document(sw, log, ROOT / "Assembly" / f"{TOP_ASM}.SLDASM")
    out = {}
    for cfg in EXPORT_CONFIGS:
        m.ShowConfiguration2(cfg)
        act = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration.Name
        if act != cfg:
            log.fail("配置激活失败", config=cfg)
        m.ForceRebuild3(False)
        p = STEPS / f"native_{cfg}.step"
        ok = m.SaveAs3(str(p), 0, 0)
        out[cfg] = {"step": p.name, "saved": bool(p.exists()),
                    "api_ret": int(ok) if ok is not None else None,
                    "bytes": p.stat().st_size if p.exists() else 0}
        print(cfg, out[cfg])
    (ROOT / "evidence/config_step_export.json").write_text(
        json.dumps({"id": "NATIVE01_CONFIG_STEP_EXPORT", "generated_utc": NOW,
                     "purpose": "评审出图用（辅助证据）；模型交付仍为原生文件",
                     "exports": out}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    sw.CloseAllDocuments(True)


def render():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    sys.path.insert(0, str(ROOT.parent /
                            "Space_Embodied_Robot_CAD_V2_2/130_B601_Vendor_CAD_Direct_Integration_03/src"))
    from s4b_mesh_cache import mesh_group

    VIEWS.mkdir(exist_ok=True)
    cache = {}

    def tris(cfg):
        if cfg not in cache:
            v, t = mesh_group(STEPS / f"native_{cfg}.step")
            cache[cfg] = v.astype(float)[t]
        return cache[cfg]

    def clip(T, axis, keep_sign, at=0.0):
        c = T[:, :, axis].mean(axis=1)
        return T[c * keep_sign <= keep_sign * at] if keep_sign < 0 else T[c >= at]

    def draw(T, out, elev, azim, title, color="#7c93b5"):
        if len(T) == 0:
            print("EMPTY", out)
            return
        if len(T) > 90000:
            T = T[np.linspace(0, len(T) - 1, 90000).astype(int)]
        fig = plt.figure(figsize=(11, 8), dpi=110)
        ax = fig.add_subplot(projection="3d")
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        nn = np.linalg.norm(n, axis=1, keepdims=True)
        n = n / np.where(nn < 1e-12, 1.0, nn)
        lam = 0.35 + 0.65 * np.abs(n @ np.array([0.4, -0.5, 0.77]))
        rgba = np.tile(np.array(matplotlib.colors.to_rgba(color)), (len(T), 1))
        rgba[:, :3] *= lam[:, None]
        ax.add_collection3d(Poly3DCollection(T, facecolors=rgba,
                                              edgecolors=(0, 0, 0, 0.25),
                                              linewidths=0.15))
        lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
        c, r = (lo + hi) / 2, float((hi - lo).max()) / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r)
        ax.set_zlim(c[2] - r, c[2] + r)
        ax.view_init(elev=elev, azim=azim); ax.set_box_aspect((1, 1, 1))
        ax.set_xlabel("X_S"); ax.set_ylabel("Y_S"); ax.set_zlabel("Z_S")
        ax.set_title(title, fontsize=11)
        fig.tight_layout(); fig.savefig(VIEWS / out); plt.close(fig)
        import gc; gc.collect()
        print("view:", out, len(T), "tris")

    S = tris("STOWED")
    draw(S, "v01_iso_stowed.png", 26, -58, "STOWED — native assembly, isometric")
    draw(S, "v02_front_plusX.png", 8, 0, "Front (+X mission face)")
    draw(S, "v03_top.png", 88, -90, "Top")
    draw(S, "v04_right.png", 6, -90, "Right (+Y)")
    draw(clip(S, 1, -1), "v05_section_Y0.png", 22, -58,
         "SECTION Y=0 — primary frames / decks / mount load path", "#5d7fa8")
    draw(clip(S, 2, -1), "v06_section_Z0.png", 22, -58,
         "SECTION Z=0 — three bays, longerons, harness passage", "#5d7fa8")
    draw(clip(S, 0, -1, at=61.0), "v07_section_X61.png", 10, -85,
         "SECTION X<61 — ring frame cross-section (17x17 rails)", "#5d7fa8")
    draw(tris("MAINTENANCE"), "v08_maintenance_panels_off.png", 26, -58,
         "MAINTENANCE — removable panels suppressed (interior access)", "#c08a3e")
    draw(tris("STOW_NO_CLOCK_COMPARATOR"), "v09_comparator_support_off.png",
         26, -58, "STOW_NO_CLOCK_COMPARATOR — stow support suppressed", "#7fa87c")
    draw(clip(clip(S, 1, -1), 2, 1, at=-113.2), "v10_cutaway_quarter.png", 30, -50,
         "Quarter cutaway (Y<0 removed) — assembly hierarchy", "#5d7fa8")


if __name__ == "__main__":
    what = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if what in ("export", "all"):
        export()
    if what in ("render", "all"):
        render()
