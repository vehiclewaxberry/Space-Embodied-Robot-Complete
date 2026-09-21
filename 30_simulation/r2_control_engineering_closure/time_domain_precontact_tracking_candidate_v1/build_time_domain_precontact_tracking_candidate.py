"""Build deterministic evidence and machine Gate for the narrow time-domain diagnostic."""

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
SOURCE_PATH = PACKAGE_ROOT / "src" / "time_domain_precontact_tracking.py"
RESULTS = PACKAGE_ROOT / "results"


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("_td_tracking_candidate_builder_core", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("CANDIDATE_CORE_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
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
    evidence_path = RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1.json"
    gate_path = RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_GATE_V1.json"
    negative_path = RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_NEGATIVE_CONTROL_RESULTS_V1.json"
    manifest_only = "--manifest-only" in sys.argv[1:]
    if manifest_only:
        gate = core.load_json_strict(gate_path)
        if not evidence_path.is_file() or not negative_path.is_file():
            raise RuntimeError("MANIFEST_ONLY_REQUIRES_EXISTING_EVIDENCE_GATE_AND_NEGATIVE_RESULTS")
    else:
        evidence, gate, negative = core.build_candidate(PROJECT_ROOT)
        write_json_atomic(evidence_path, evidence)
        write_json_atomic(gate_path, gate)
        write_json_atomic(negative_path, negative)

    inventory_paths = [
        PACKAGE_ROOT / "README.md",
        PACKAGE_ROOT / "build_time_domain_precontact_tracking_candidate.py",
        PACKAGE_ROOT / "contracts" / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_CONTRACT_V1.json",
        PACKAGE_ROOT / "src" / "__init__.py",
        SOURCE_PATH,
        PACKAGE_ROOT / "tests" / "test_time_domain_precontact_tracking.py",
        evidence_path,
        gate_path,
        negative_path,
    ]
    if not all(path.is_file() for path in inventory_paths):
        missing = [str(path) for path in inventory_paths if not path.is_file()]
        raise RuntimeError(f"PACKAGE_INVENTORY_MISSING:{missing}")
    rows = [record(path) for path in inventory_paths]
    manifest = {
        "schema": "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_MANIFEST_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "inventory_count": len(rows),
        "inventory": rows,
        "manifest_and_csv_self_excluded": True,
        "gate_passed": bool(gate["gate_passed"]),
        "next_stage_authorized": False,
        "release_credit": False,
    }
    manifest_path = RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_MANIFEST_V1.json"
    write_json_atomic(manifest_path, manifest)
    csv_path = RESULTS / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_SHA256_V1.csv"
    temporary_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with temporary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("path", "bytes", "sha256"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary_csv.replace(csv_path)
    print(json.dumps({"gate_passed": gate["gate_passed"], "passed": gate["summary"]["passed"], "total": gate["summary"]["total"], "failed": gate["summary"]["failed"]}, ensure_ascii=False))
    return 0 if manifest_only or gate["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
