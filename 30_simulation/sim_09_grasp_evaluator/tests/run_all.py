"""sim_09 Gate E0/E1 anchor-regression runner (no pytest; plain asserts).

Runs t1..t7 (Gate E0) + t8 (Gate E1), prints a PASS table, writes
30_simulation/sim_09_grasp_evaluator/results/anchor_report_e0.md.
Exit code 0 iff all tests pass. Iron rule: if an anchor drifts, FIX THE
IMPLEMENTATION -- never edit the expected values.
"""
import _helpers  # noqa: F401  (env pin + paths BEFORE numpy-importing tests)
import os
import time
import traceback

import t1_impulse_anchor
import t2_ik_roundtrip
import t3_momentum
import t4_ancf_anchor
import t5_propagation
import t6_actuator_anchor
import t7_determinism
import t8_e1_regression

TESTS = [t1_impulse_anchor, t2_ik_roundtrip, t3_momentum, t4_ancf_anchor,
         t5_propagation, t6_actuator_anchor, t7_determinism, t8_e1_regression]


def main():
    results = []
    for mod in TESTS:
        t0 = time.time()
        try:
            out = mod.run()
            out["wall_s"] = round(time.time() - t0, 1)
        except (AssertionError, Exception) as e:  # noqa: BLE001 -- report, don't die
            out = {"name": mod.__name__, "passed": False,
                   "worst_residual": float("nan"),
                   "note": f"{type(e).__name__}: {e}",
                   "traceback": traceback.format_exc(),
                   "wall_s": round(time.time() - t0, 1)}
        results.append(out)
        status = "PASS" if out["passed"] else "FAIL"
        print(f"[{status}] {out['name']:22s} worst={out['worst_residual']:.3e} "
              f"wall={out['wall_s']}s")
        if not out["passed"]:
            print(out.get("traceback", out["note"]))

    all_pass = all(r["passed"] for r in results)
    os.makedirs(_helpers.RESULTS_DIR, exist_ok=True)
    report = os.path.join(_helpers.RESULTS_DIR, "anchor_report_e0.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("# sim_09 Gate E0 anchor regression report\n\n")
        f.write(f"generated: {time.strftime('%Y-%m-%d %H:%M:%S')}  |  "
                f"overall: {'ALL PASS' if all_pass else 'FAILURES PRESENT'}\n\n")
        f.write("| test | status | worst residual | wall [s] | note |\n")
        f.write("|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['name']} | {'PASS' if r['passed'] else 'FAIL'} | "
                    f"{r['worst_residual']:.3e} | {r['wall_s']} | "
                    f"{r.get('note', '')} |\n")
        f.write("\n## anchor detail rows\n\n")
        for r in results:
            if "rows" in r:
                f.write(f"### {r['name']}\n\n")
                keys = list(r["rows"][0].keys())
                f.write("| " + " | ".join(keys) + " |\n")
                f.write("|" + "---|" * len(keys) + "\n")
                for row in r["rows"]:
                    f.write("| " + " | ".join(
                        f"{row[k]:.6g}" if isinstance(row[k], float) else str(row[k])
                        for k in keys) + " |\n")
                f.write("\n")
            if "per_mode" in r:
                f.write(f"### {r['name']} (per mode)\n\n")
                f.write("| mode | worst_pos_m | worst_ori_rad | nullity | limit_violations |\n")
                f.write("|---|---|---|---|---|\n")
                for m, d in r["per_mode"].items():
                    f.write(f"| {m} | {d['worst_pos_m']:.3e} | {d['worst_ori_rad']:.3e} | "
                            f"{d['nullity']} | {d['limit_violations']} |\n")
                f.write("\n")
    print(f"\nreport written: {report}")
    print("OVERALL:", "ALL PASS" if all_pass else "FAILURES PRESENT")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
