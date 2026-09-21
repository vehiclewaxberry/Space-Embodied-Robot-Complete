"""Run all sim_11 tests (no pytest). Prints a PASS/FAIL table with the worst
residual returned by each test function; exits 1 on any failure.
科学结论以 results/sim_11_gate_check.json 机器裁决为准：测试 PASS != 科学 Gate PASS。"""
import importlib
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

MODULES = [
    "test_config_ssot",
    "test_panel_modal",
    "test_dynamics_assembly",
    "test_capture_and_degeneration",
    "test_contact_bandwidth",
]


def main():
    results = []
    failed = 0
    for mod_name in MODULES:
        mod = importlib.import_module(mod_name)
        fns = [(n, f) for n, f in vars(mod).items()
               if n.startswith("test_") and callable(f)]
        fns.sort(key=lambda nf: nf[1].__code__.co_firstlineno)
        for name, fn in fns:
            t0 = time.time()
            try:
                worst = fn()
                dt = time.time() - t0
                results.append((mod_name, name, "PASS", worst, dt))
            except Exception:
                dt = time.time() - t0
                failed += 1
                results.append((mod_name, name, "FAIL", None, dt))
                traceback.print_exc()
    print()
    print("=" * 100)
    print("%-30s %-48s %-6s %-12s %s" % ("module", "test", "res", "worst", "t[s]"))
    print("-" * 100)
    for mod_name, name, status, worst, dt in results:
        w = ("%.3e" % worst) if isinstance(worst, (int, float)) else "-"
        print("%-30s %-48s %-6s %-12s %.1f" % (mod_name, name, status, w, dt))
    print("-" * 100)
    npass = sum(1 for r in results if r[2] == "PASS")
    print("TOTAL: %d/%d PASS" % (npass, len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
