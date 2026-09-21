from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[2]
SOURCE = PACKAGE_ROOT / "src" / "metric_parent_rebind.py"
RESULTS = PACKAGE_ROOT / "results"


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("_metric_parent_rebind_builder_core", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("REBIND_CORE_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest().upper(),
    }


def main() -> int:
    core = load_core()
    evidence, gate, negative = core.build_rebind(PROJECT_ROOT)
    evidence_path = RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_EVIDENCE_V1.json"
    gate_path = RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_GATE_V1.json"
    negative_path = RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_NEGATIVE_CONTROLS_V1.json"
    write_json(evidence_path, evidence)
    write_json(gate_path, gate)
    write_json(negative_path, negative)
    inventory_paths = [
        PACKAGE_ROOT / "README.md",
        PACKAGE_ROOT / "build_metric_parent_rebind.py",
        PACKAGE_ROOT / "contracts" / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_CONTRACT_V1.json",
        PACKAGE_ROOT / "src" / "__init__.py",
        SOURCE,
        PACKAGE_ROOT / "tests" / "test_metric_parent_rebind.py",
        evidence_path,
        gate_path,
        negative_path,
    ]
    if not all(path.is_file() for path in inventory_paths):
        raise RuntimeError("REBIND_PACKAGE_INVENTORY_INCOMPLETE")
    rows = [record(path) for path in inventory_paths]
    manifest = {
        "schema": "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_MANIFEST_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "inventory_count": len(rows),
        "inventory": rows,
        "manifest_and_csv_self_excluded": True,
        "gate_passed": gate["gate_passed"],
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_MANIFEST_V1.json", manifest)
    csv_path = RESULTS / "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_SHA256_V1.csv"
    temporary = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("path", "bytes", "sha256"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(csv_path)
    print(json.dumps({"gate_passed": gate["gate_passed"], **gate["summary"]}, ensure_ascii=False))
    return 0 if gate["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
