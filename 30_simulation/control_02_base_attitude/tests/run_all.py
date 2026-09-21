"""Run CTRL-02 tests. Scientific status remains the machine gate verdict."""
import importlib
import json
import os
import sys
import time
import traceback


HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

MODULES = ["test_pipeline", "test_config", "test_ledger", "test_results", "test_transient"]


def main():
    results = []
    failed = 0
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        tests = [
            (name, fn)
            for name, fn in vars(module).items()
            if name.startswith("test_") and callable(fn)
        ]
        tests.sort(key=lambda item: item[1].__code__.co_firstlineno)
        for name, fn in tests:
            t0 = time.time()
            try:
                worst = fn()
                results.append((module_name, name, "PASS", worst, time.time() - t0))
            except Exception:
                failed += 1
                results.append((module_name, name, "FAIL", None, time.time() - t0))
                traceback.print_exc()
    print("=" * 102)
    print("%-20s %-55s %-6s %-12s %s" % ("module", "test", "res", "worst", "t[s]"))
    print("-" * 102)
    for module, name, status, worst, elapsed in results:
        value = ("%.3e" % worst) if isinstance(worst, (int, float)) else "-"
        print(
            "%-20s %-55s %-6s %-12s %.1f"
            % (module, name, status, value, elapsed)
        )
    print("-" * 102)
    print("TOTAL: %d/%d PASS" % (len(results) - failed, len(results)))
    report_path = os.path.normpath(os.path.join(HERE, "..", "results", "test_report.json"))
    gate_path = os.path.normpath(
        os.path.join(HERE, "..", "results", "control_02_gate_check.json")
    )
    gate_verdict = None
    if os.path.exists(gate_path):
        with open(gate_path, encoding="utf-8") as f:
            gate_verdict = json.load(f).get("verdict")
    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(
            {
                "schema_version": "control02-test-report-v1",
                "tests_passed": len(results) - failed,
                "tests_total": len(results),
                "scientific_gate_verdict": gate_verdict,
                "tests": [
                    {
                        "module": module,
                        "name": name,
                        "status": status,
                        "worst": worst,
                        "elapsed_s": elapsed,
                    }
                    for module, name, status, worst, elapsed in results
                ],
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
