"""Run all sim_05 tests (no pytest). Prints a PASS/FAIL table with the worst
residual returned by each test function; exits 1 on any failure."""
import importlib
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

MODULES = [
    "test_urdf_structure",
    "test_inertia_positive_definite",
    "test_joint_axis_consistency",
    "test_fk_against_step_frames",
    "test_mass_rollup",
    "test_dynamics",
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
    print("=" * 88)
    print("%-32s %-42s %-6s %-12s %s" % ("module", "test", "res", "worst", "t[s]"))
    print("-" * 88)
    for mod_name, name, status, worst, dt in results:
        w = ("%.3e" % worst) if isinstance(worst, (int, float)) else "-"
        print("%-32s %-42s %-6s %-12s %.1f" % (mod_name, name, status, w, dt))
    print("-" * 88)
    npass = sum(1 for r in results if r[2] == "PASS")
    print("TOTAL: %d/%d PASS" % (npass, len(results)))
    td = importlib.import_module("test_dynamics")
    fn3 = getattr(td, "test_3_geometric_phase_closed_cycle")
    if hasattr(fn3, "phase_deg"):
        print("geometric phase after closed joint cycle: %.4f deg  (euler xyz final: %s)"
              % (fn3.phase_deg, ["%.4f" % v for v in fn3.euler_final]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
