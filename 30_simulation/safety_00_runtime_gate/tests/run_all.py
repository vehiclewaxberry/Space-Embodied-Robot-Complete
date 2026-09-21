"""Run SAFE-00 deterministic unit and adversarial tests."""
import importlib
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

MODULES = ["test_contract", "test_core", "test_bypass"]


def main():
    results = []
    failed = 0
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        functions = [(name, fn) for name, fn in vars(module).items()
                     if name.startswith("test_") and callable(fn)]
        functions.sort(key=lambda item: item[1].__code__.co_firstlineno)
        for name, fn in functions:
            start = time.perf_counter()
            try:
                metric = fn()
                results.append((module_name, name, "PASS", metric,
                                time.perf_counter() - start))
            except Exception:
                failed += 1
                results.append((module_name, name, "FAIL", None,
                                time.perf_counter() - start))
                traceback.print_exc()
    print("=" * 108)
    print("%-20s %-54s %-6s %-12s %s" %
          ("module", "test", "res", "metric", "t[s]"))
    print("-" * 108)
    for module_name, name, status, metric, elapsed in results:
        text = ("%.3e" % metric) if isinstance(metric, (int, float)) else "-"
        print("%-20s %-54s %-6s %-12s %.3f" %
              (module_name, name, status, text, elapsed))
    print("-" * 108)
    print("TOTAL: %d/%d PASS" % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
