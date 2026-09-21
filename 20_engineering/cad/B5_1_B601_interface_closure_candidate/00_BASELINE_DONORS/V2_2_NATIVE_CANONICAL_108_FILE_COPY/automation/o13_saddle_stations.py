"""O13 收口：v3 位形的精确支承站位分析 → 选定鞍座 X 窗口与接触高度。

口径澄清：O11 的 C4「support_windows_10mm_bins」统计的是臂跨越舱面的**全部**分箱，
其 max 塔高是臂底剖面的最高点，不是要建的鞍座。真正的判据是：
**存在**足够多、跨距足够大、塔高 ≤150mm 的站位可供选址。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import o11_clocking_adjudication as O11

NOW = datetime.now(timezone.utc).isoformat()
DECK, CLR, TOWER_MAX = O11.DECK_TOP, 8.0, 150.0
BIN = 20.0


def main():
    v3 = json.loads((ROOT / "design/b601_stow_joint_vector_v3.json")
                    .read_text(encoding="utf-8"))
    q = np.array(v3["q_rad"], float)
    av = O11.arm_vertices(q, v3["clock_deg"])
    M = np.vstack([v for g, v in av.items() if g not in ("G06", "G01")])
    od = M[M[:, 0] < O11.DECK_X]
    b = np.floor(od[:, 0] / BIN).astype(int)
    prof = []
    for k in np.unique(b):
        m = b == k
        if m.sum() < 40:
            continue
        seg = od[m]
        prof.append({"x_lo": float(k * BIN), "x_hi": float(k * BIN + BIN),
                      "z_bottom": round(float(seg[:, 2].min()), 2),
                      "tower_h": round(float(seg[:, 2].min() - DECK), 2),
                      "y_min": round(float(seg[:, 1].min()), 2),
                      "y_max": round(float(seg[:, 1].max()), 2),
                      "n": int(m.sum())})
    # 站位须完整落在舱面内（甲板止于 X=±183），否则鞍座无处生根
    usable = [p for p in prof if CLR <= p["tower_h"] <= TOWER_MAX
              and p["x_lo"] >= -183.0 and p["x_hi"] <= 183.0]
    # 选 3 个鞍座：最靠后、最靠前的可用站位 + 中间塔最矮者
    picked = []
    if len(usable) >= 2:
        us = sorted(usable, key=lambda p: p["x_lo"])
        picked = [us[0], us[-1]]
        mid = [p for p in us if us[0]["x_hi"] + 40 < p["x_lo"] < us[-1]["x_lo"] - 40]
        if mid:
            picked.insert(1, min(mid, key=lambda p: p["tower_h"]))
    out = {"id": "O13_SADDLE_STATIONS", "generated_utc": NOW,
           "vector": v3["q_deg"], "clock_deg": v3["clock_deg"],
           "criteria": {"tower_h_band_mm": [CLR, TOWER_MAX], "bin_mm": BIN,
                         "min_points_per_bin": 40},
           "bottom_profile": prof,
           "n_bins": len(prof), "n_usable": len(usable),
           "usable_span_mm": (round(usable[-1]["x_hi"] - usable[0]["x_lo"], 1)
                               if len(usable) >= 2 else 0.0),
           "tower_h_range_all_bins": [min(p["tower_h"] for p in prof),
                                       max(p["tower_h"] for p in prof)],
           "selected_saddles": [{"tag": t, "x_window": [p["x_lo"], p["x_hi"]],
                                  "contact_z": p["z_bottom"],
                                  "tower_h": p["tower_h"],
                                  "y_range": [p["y_min"], p["y_max"]]}
                                 for t, p in zip(("AFT", "MID", "FWD"), picked)],
           "clarification": "O11 的 C4 tower_over_limit 统计全部跨舱面分箱（含臂最高处），"
                             "非鞍座选址判据；本文件给出的是实际可建站位"}
    (ROOT / "design/o13_saddle_stations.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("bins:", len(prof), "usable:", len(usable),
          "span:", out["usable_span_mm"], "mm")
    print("tower_h all-bins range:", out["tower_h_range_all_bins"])
    for s in out["selected_saddles"]:
        print(f"  {s['tag']}: X{s['x_window']} contact_z={s['contact_z']} "
              f"tower={s['tower_h']} y={s['y_range']}")


if __name__ == "__main__":
    main()
