"""Dependency-light CTRL-01 test runner."""
from __future__ import annotations

from pathlib import Path
import importlib
import json
import sys
import time
import traceback


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
SRC = MODULE / "src"
for path in (str(SRC), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

MODULES = (
    "test_contracts",
    "test_physics_interfaces",
    "test_controller",
    "test_energy_ledger",
    "test_collision_evidence",
    "test_gate_semantics",
)


def main() -> int:
    rows = []
    for module_name in MODULES:
        module = importlib.import_module(module_name)
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            fn = getattr(module, name)
            started = time.perf_counter()
            try:
                value = fn()
                rows.append(
                    (module_name, name, "PASS", float(value or 0.0), time.perf_counter() - started)
                )
            except Exception:
                traceback.print_exc()
                rows.append(
                    (module_name, name, "FAIL", float("nan"), time.perf_counter() - started)
                )
    print("=" * 104)
    print(f"{'module':28s} {'test':52s} {'res':5s} {'worst':>11s} {'t[s]':>8s}")
    print("-" * 104)
    for module, name, status, worst, elapsed in rows:
        print(
            f"{module:28s} {name:52s} {status:5s} "
            f"{worst:11.3e} {elapsed:8.2f}"
        )
    passed = sum(row[2] == "PASS" for row in rows)
    print("-" * 104)
    print(f"TOTAL: {passed}/{len(rows)} PASS")
    result_path = MODULE / "results" / "test_results.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "schema_version": "control-01-tests-v0",
                "tests_passed": passed,
                "tests_total": len(rows),
                "overall": "PASS" if passed == len(rows) else "REPEAT",
                "tests_are_not_gate": True,
                "rows": [
                    {
                        "module": module,
                        "test": name,
                        "status": status,
                        "worst": worst,
                        "elapsed_s": elapsed,
                    }
                    for module, name, status, worst, elapsed in rows
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
