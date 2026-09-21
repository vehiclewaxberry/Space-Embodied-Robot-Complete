"""Run the full sim_06 verification suite (no pytest dependency) and write
verification_report_v0.md. Exit code != 0 on any failure — this is Gate A."""
import os, sys, importlib, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MODULES = ["test_linear_momentum", "test_angular_momentum", "test_energy_dissipation",
           "test_frame_invariance", "test_limiting_cases", "test_spatial_inertia_crosscheck",
           "test_point_contact"]

results, failed = [], 0
for name in MODULES:
    mod = importlib.import_module(name)
    for fn_name in sorted(d for d in dir(mod) if d.startswith("test_")):
        fn = getattr(mod, fn_name)
        try:
            worst = fn()
            results.append((name, fn_name, "PASS", worst))
        except AssertionError:
            failed += 1
            results.append((name, fn_name, "FAIL", traceback.format_exc(limit=2)))
        except Exception:
            failed += 1
            results.append((name, fn_name, "ERROR", traceback.format_exc(limit=2)))

report = os.path.join(HERE, "verification_report_v0.md")
with open(report, "w", encoding="utf-8", newline="\n") as f:
    f.write("# sim_06 verification report (Gate A)\n\n")
    f.write("| module | test | status | worst residual |\n|---|---|---|---|\n")
    for m, t, s, w in results:
        wtxt = f"{w:.2e}" if isinstance(w, float) else ("-" if w is None else "see log")
        f.write(f"| {m} | {t} | {s} | {wtxt} |\n")
    f.write(f"\n- total: {len(results)}, failed: {failed}\n")
    f.write("- residuals are normalized (relative); float column = worst case over the sweep.\n")
    f.write("- suites cover: P/H conservation (origin + arbitrary points), plastic dT bounds,\n")
    f.write("  rigid translation/rotation/Galilean-boost invariance, 9 limiting cases with\n")
    f.write("  closed-form expectations, and an independent 6x6 spatial-inertia implementation.\n")

for m, t, s, w in results:
    tag = f"{m}.{t}"
    if s == "PASS":
        print(f"PASS  {tag:60s} worst={w:.2e}" if isinstance(w, float) else f"PASS  {tag}")
    else:
        print(f"{s}  {tag}\n{w}")
print(f"\n{len(results) - failed}/{len(results)} passed -> {report}")
sys.exit(1 if failed else 0)
