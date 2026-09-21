"""Stdlib-oriented independent audit of the source-only backend boundary."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = next(parent for parent in (HERE, *HERE.parents) if (parent / "PROJECT_MAP.md").is_file())
OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_INDEPENDENT_AUDIT_V1.json"
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_MANIFEST_V1.json"
NEGATIVE = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_NEGATIVE_CONTROLS_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_VALIDATION_V1.json"
BACKEND_CONTRACT = HERE / "contracts/PHASE_B4G_R2_FULL_RAW_INTEGRITY_BACKEND_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_GOVERNANCE_V1.json"


class AuditError(RuntimeError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _tree(value: Any) -> None:
    if value is None:
        raise AuditError("NULL_JSON_FORBIDDEN")
    if isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AuditError("NONFINITE_JSON")
        return
    if isinstance(value, list):
        for item in value:
            _tree(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise AuditError("NONSTRING_KEY")
            _tree(item)
        return
    raise AuditError(f"NONJSON_TYPE:{type(value).__name__}")


def _load(path: Path) -> Any:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(AuditError(f"NONFINITE_TOKEN:{token}")),
    )
    _tree(value)
    return value


def _canonical(value: Any) -> bytes:
    _tree(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _seal(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["document_sha256"] = hashlib.sha256(_canonical(value)).hexdigest().upper()
    return result


def _seal_valid(value: Any) -> bool:
    if not isinstance(value, dict) or type(value.get("document_sha256")) is not str:
        return False
    payload = {key: item for key, item in value.items() if key != "document_sha256"}
    return hashlib.sha256(_canonical(payload)).hexdigest().upper() == value["document_sha256"]


def _nominal_subprocess() -> dict[str, Any]:
    code = (
        "import json,tempfile;from pathlib import Path;"
        "from r2_full_integrity.fixture_factory import write_technical_fixture;"
        "from r2_full_integrity.integrity import evaluate_full_raw_integrity;"
        f"root=Path({str(HERE)!r});"
        "td=tempfile.TemporaryDirectory(prefix='.technical-fixture-',dir=root);"
        "case,context=write_technical_fixture(Path(td.name)).load();"
        "result=evaluate_full_raw_integrity(case,context);"
        "print(json.dumps({'technical':result['technical_fixture_full_raw_integrity_predicate_pass'],"
        "'passed':result['passed'],'trajectory_count':result['trajectory_count'],"
        "'gate_count':len(result['gate_records']),'actual':result['actual_case_full_raw_integrity_recomputed'],"
        "'next':result['next_stage_authorized']},sort_keys=True));td.cleanup()"
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=HERE, env=environment,
        capture_output=True, text=True, timeout=90, check=False,
    )
    if completed.returncode != 0:
        return {"subprocess_pass": False, "stderr": completed.stderr[-500:]}
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return {"subprocess_pass": False, "stdout": completed.stdout[-500:]}
    payload["subprocess_pass"] = True
    return payload


def audit(*, write_output: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, detail: Any) -> None:
        checks.append({"check_id": check_id, "passed": bool(passed), "detail": detail})

    backend = _load(BACKEND_CONTRACT)
    governance = _load(GOVERNANCE)
    check("A01_CONTRACT_SCHEMA", backend.get("schema") == "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_BACKEND_CONTRACT_V1", backend.get("schema"))
    check("A02_GATE_RULE_COUNT", len(backend.get("gate_rules", {})) == 10, len(backend.get("gate_rules", {})))
    external_results = []
    for record in backend.get("frozen_external_contracts", []):
        path = (PROJECT_ROOT / record["path"]).resolve()
        inside = False
        try:
            path.relative_to(PROJECT_ROOT.resolve())
            inside = True
        except ValueError:
            pass
        external_results.append(bool(inside and path.is_file() and path.stat().st_size == record["bytes"] and _sha(path) == record["sha256"]))
    check("A03_EXTERNAL_CONTRACT_BINDINGS", len(external_results) == 5 and all(external_results), external_results)

    imported: set[str] = set()
    syntax_ok = True
    for path in sorted((HERE / "r2_full_integrity").glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            syntax_ok = False
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    check("A04_SOURCE_AST_VALID", syntax_ok, sorted(imported))
    forbidden_import = any("b4g_solver" in name or "b4_solver" in name or "b3_contact" in name for name in imported)
    check("A05_NO_SOLVER_IMPORT", not forbidden_import, sorted(imported))

    integrity_text = (HERE / "r2_full_integrity/integrity.py").read_text(encoding="utf-8")
    forbidden_oracles = ["gate_predicates", "selector_case_integrity_pass", "clearance.integrity_pass"]
    check("A06_NO_UPSTREAM_BOOLEAN_ORACLE", all(token not in integrity_text for token in forbidden_oracles), forbidden_oracles)
    check("A07_NO_RUNNER_FILE", not any("runner" in path.name.lower() for path in (HERE / "r2_full_integrity").glob("*.py")), "r2_full_integrity/*.py")
    forbidden_suffixes = {".npz", ".csv", ".step", ".stp", ".urdf", ".pyc"}
    forbidden_files = [path.relative_to(HERE).as_posix() for path in HERE.rglob("*") if path.is_file() and path.suffix.lower() in forbidden_suffixes]
    check("A08_NO_PERSISTENT_TRAJECTORY_OR_CAD_ARTIFACT", not forbidden_files, forbidden_files)

    governance_false = [
        "r2_numerical_preflight_executed", "current_system_bound", "formal_nc19_credit",
        "scientific_credit", "owner_authorized", "production_credit",
        "release_authorized", "next_stage_authorized", "cad_or_urdf_generation_authorized",
        "runner_present",
    ]
    check("A09_GOVERNANCE_FAIL_CLOSED", all(governance.get(key) is False for key in governance_false) and governance.get("trajectory_count") == 0, governance_false)
    nominal = _nominal_subprocess()
    check(
        "A10_ISOLATED_TECHNICAL_RECOMPUTATION",
        nominal.get("subprocess_pass") is True and nominal.get("technical") is True
        and nominal.get("gate_count") == 10 and nominal.get("passed") is False
        and nominal.get("trajectory_count") == 0 and nominal.get("actual") is False
        and nominal.get("next") is False,
        nominal,
    )

    receipts_exist = all(path.is_file() for path in (MANIFEST, NEGATIVE, VALIDATION))
    receipt_seals = receipts_exist and all(_seal_valid(_load(path)) for path in (MANIFEST, NEGATIVE, VALIDATION))
    check("A11_UPSTREAM_RECEIPTS_SEALED", receipt_seals, [path.name for path in (MANIFEST, NEGATIVE, VALIDATION)])
    if receipts_exist:
        negative = _load(NEGATIVE)
        validation = _load(VALIDATION)
        evidence_semantics = bool(
            negative.get("result", {}).get("passed") is True
            and negative.get("result", {}).get("control_count") == 14
            and negative.get("result", {}).get("killed_count") == 14
            and validation.get("source_freeze_pass_eligible") is True
            and validation.get("pytest_passed_count") == 18
        )
    else:
        evidence_semantics = False
    check("A12_UPSTREAM_RECEIPT_SEMANTICS", evidence_semantics, receipts_exist)
    passed = all(item["passed"] for item in checks)
    result = _seal({
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_INDEPENDENT_AUDIT_V1",
        "status": "PASS_INDEPENDENT_SOURCE_AUDIT" if passed else "FAIL_INDEPENDENT_SOURCE_AUDIT",
        "independent_source_freeze_pass_eligible": passed,
        "score": {
            "total": len(checks),
            "passed": sum(1 for item in checks if item["passed"]),
            "failed": [item["check_id"] for item in checks if not item["passed"]],
        },
        "checks": checks,
        "trajectory_count": 0,
        "actual_case_full_raw_integrity_recomputed": False,
        "next_stage_authorized": False,
    })
    if write_output:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temporary = OUTPUT.with_name(f".{OUTPUT.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, OUTPUT)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args(argv)
    result = audit(write_output=args.write_receipt)
    print(f"{result['status']} {result['score']['passed']}/{result['score']['total']}")
    return 0 if result["independent_source_freeze_pass_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
