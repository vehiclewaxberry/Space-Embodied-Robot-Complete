"""sim_12 Phase1 回归（assert 式）。测试 PASS != 科学 Gate PASS。"""
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "src")))


def t_s12_run_and_gates():
    from strategy_eval import main
    rows, out = main()
    assert out["verdict"] == "SIM12_PHASE1_GATES_PASS", out["verdict"]
    assert len(rows) == 16
    return out["gates"]["GS1_conservation"]["max_eps_H"]


def t_s12_anchor_vs_sim10():
    """B 案 S1 = sim_10 碎片锚点逐位（3.0633°/s / 3.65099 N·m·s）。"""
    from strategy_eval import main
    rows, _ = main()
    r = next(x for x in rows if x["case"] == "B_anchor"
             and x["strategy"] == "S1_passive")
    assert abs(r["post_capture_rate_dps"] - 3.0633304945807067) < 1e-12
    assert abs(r["H_required_Nms"] - 3.650992635553959) < 1e-12
    assert r["feasibility"] == "INFEASIBLE" and r["binding_gate"] == "POST_CAPTURE_RATE"
    return abs(r["post_capture_rate_dps"] - 3.0633304945807067)


def t_s12_s3b_placeholder_absent():
    """S3b 不在 Phase1 策略集（预注册断言未固化前不得进入对比）——参数卡防呆。"""
    import yaml
    c = yaml.safe_load(open(os.path.join(HERE, "..", "..", "..", "config",
                                         "strategy_feasibility",
                                         "strategies_v0.yaml"), encoding="utf-8"))
    assert "S3b" not in " ".join(c["strategies"])
    return 0.0


def main():
    results, failed = [], 0
    for fn in (t_s12_run_and_gates, t_s12_anchor_vs_sim10,
               t_s12_s3b_placeholder_absent):
        t0 = time.time()
        try:
            w = fn()
            results.append((fn.__name__, "PASS", w, time.time() - t0))
        except Exception:
            failed += 1
            results.append((fn.__name__, "FAIL", None, time.time() - t0))
            traceback.print_exc()
    for n, s, w, dt in results:
        print("%-36s %-5s %-12s %.1f" % (n, s, ("%.2e" % w) if isinstance(w, float) else "-", dt))
    print("TOTAL: %d/%d PASS" % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
