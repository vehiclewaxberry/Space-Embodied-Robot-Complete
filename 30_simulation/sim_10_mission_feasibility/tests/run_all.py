"""sim_10 回归测试（assert 式，无 pytest）：t_s10_anchor / t_s10_determinism /
t_s10_monotonic / t_s10_registry_hash / t_s10_conservation。
科学结论以 results/sim_10_gate_check.json 机器裁决为准；测试 PASS != Gate PASS。"""
import hashlib
import os
import sys
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
sys.path.insert(0, SRC)

from feasibility_core import (load_cfg, geometry_classes, exact_point,   # noqa: E402
                              gate_point, actuator_tier_list)


def t_s10_anchor():
    """两锚点与 sim_06 求解器机器恒等（capture_post_state 同款场景）。"""
    from capture_impulse import capture_post_state
    cfg = load_cfg()
    classes = geometry_classes(cfg)
    worst = 0.0
    for cls, tid, m_t in (("G1_slender", "target_debris_v0", 150.0),
                          ("G2_cubesat", "target_satellite_v0", 22.0)):
        ex = exact_point(classes[cls], m_t, 3.0, 1.0, 0.0, 0.01)
        res, _, _ = capture_post_state(tid, 3.0, 0.01)
        d = abs(ex["w_plus_dps"] - float(np.rad2deg(np.linalg.norm(res["w_plus"]))))
        worst = max(worst, d)
    assert worst < 1e-12, worst
    return worst


def t_s10_determinism():
    """quick 网格连跑两次：物理 CSV 逐字节一致。"""
    from scan_grid import run_scan, RES
    cfg = load_cfg()
    p = os.path.join(RES, cfg["output"]["physics_csv"].replace(".csv", "_quick.csv"))
    run_scan(quick=True)
    h1 = hashlib.sha256(open(p, "rb").read()).hexdigest()
    run_scan(quick=True)
    h2 = hashlib.sha256(open(p, "rb").read()).hexdigest()
    assert h1 == h2, (h1, h2)
    return 0.0


def t_s10_monotonic():
    """固定点：|H_c| 与 ω⁺ 随 ω_t 单调增（α=0；v_app 项固定不破坏单调）。"""
    cfg = load_cfg()
    classes = geometry_classes(cfg)
    oms = np.geomspace(0.1, 10.0, 12)
    worst = 0.0
    for cls in classes:
        H = [exact_point(classes[cls], 60.0, om, 1.0, 0.0, 0.01)["H_c_Nms"]
             for om in oms]
        w = [exact_point(classes[cls], 60.0, om, 1.0, 0.0, 0.01)["w_plus_dps"]
             for om in oms]
        dH, dw = np.diff(H), np.diff(w)
        assert np.all(dH > 0), (cls, H)
        assert np.all(dw > 0), (cls, w)
        worst = max(worst, float(-min(dH.min(), dw.min())))
    return worst


def t_s10_registry_hash():
    """冻结输入哈希全匹配 + 阈值一致性断言通过 + thresholds_widened=False。"""
    cfg = load_cfg(verify_hashes=True)      # 哈希漂移会 raise
    assert cfg["_thresholds_widened"] is False
    assert all(v["match"] for v in cfg["_hash_report"].values())
    return 0.0


def t_s10_conservation():
    """抽样网格点 rigidize 守恒残差 <= 1e-12。"""
    cfg = load_cfg()
    classes = geometry_classes(cfg)
    worst = 0.0
    for cls in classes:
        for m_t in (2.0, 60.0, 400.0):
            for om in (0.3, 3.0, 9.0):
                ex = exact_point(classes[cls], m_t, om, 0.5, 1.0, 0.01)
                worst = max(worst, ex["eps_P"], ex["eps_H"])
    assert worst < 1e-12, worst
    return worst


def t_s10_gate_semantics():
    """四门 fail-closed 语义：构造性用例覆盖四区域。"""
    cfg = load_cfg()
    tier = actuator_tier_list(cfg)[0]       # wheels_small|cold_gas|l0.05
    cases = [
        (0.01, 1.0, "WHEELS_ONLY_FEASIBLE"),
        (0.2, 1.0, "THRUSTER_REQUIRED_FEASIBLE"),
        (0.2, 3.0, "INFEASIBLE_RATE"),
        (50.0, 1.0, "INFEASIBLE_RESOURCE"),
    ]
    for H, w, expect in cases:
        g = gate_point(H, w, tier, cfg)
        assert g["region"] == expect, (H, w, g["region"], expect)
    return 0.0


def main():
    tests = [t_s10_anchor, t_s10_determinism, t_s10_monotonic,
             t_s10_registry_hash, t_s10_conservation, t_s10_gate_semantics]
    results, failed = [], 0
    for fn in tests:
        t0 = time.time()
        try:
            worst = fn()
            results.append((fn.__name__, "PASS", worst, time.time() - t0))
        except Exception:
            failed += 1
            results.append((fn.__name__, "FAIL", None, time.time() - t0))
            traceback.print_exc()
    print("=" * 72)
    print("%-32s %-6s %-12s %s" % ("test", "res", "worst", "t[s]"))
    print("-" * 72)
    for name, status, worst, dt in results:
        w = ("%.3e" % worst) if isinstance(worst, (int, float)) else "-"
        print("%-32s %-6s %-12s %.1f" % (name, status, w, dt))
    print("-" * 72)
    print("TOTAL: %d/%d PASS" % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
