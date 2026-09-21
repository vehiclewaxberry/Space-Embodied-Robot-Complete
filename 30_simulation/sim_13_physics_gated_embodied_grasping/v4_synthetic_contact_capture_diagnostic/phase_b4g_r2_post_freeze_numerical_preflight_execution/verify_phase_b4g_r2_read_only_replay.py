"""Prove the published read-only command sequence is byte-immutable.

This verifier runs only the standalone validator, standalone independent audit,
and source-only pytest suite.  It snapshots every regular file in this package
before and after those commands.  It never invokes the freezer, a historical
physics module, a numerical case, or a campaign.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
GATE = HERE / "results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json"
EXPECTED_GATE_EVIDENCE = {
    "r2_execution_source_manifest": "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1.json",
    "r2_execution_source_validation": "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1.json",
    "r2_execution_source_independent_audit": "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_V1.json",
    "r2_source_only_negative_controls": "evidence/SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1.json",
}
COMMANDS = (
    ("validator", (sys.executable, "-B", "validate_phase_b4g_r2_execution_source_freeze.py")),
    ("independent_audit", (sys.executable, "-B", "independent_audit_phase_b4g_r2_execution_source_freeze.py")),
    ("pytest", (sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider")),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise RuntimeError(f"NONFINITE_JSON_TOKEN:{token}")


def _load_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"REGULAR_JSON_REQUIRED:{path}")
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )


def _bound_record_matches(row: Any, expected_relative_suffix: str) -> bool:
    if not isinstance(row, dict) or set(row) != {"id", "role", "path", "bytes", "sha256"}:
        return False
    relative = row["path"]
    if type(relative) is not str or "\\" in relative or not relative.endswith(expected_relative_suffix):
        return False
    raw = Path(relative)
    if raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
        return False
    lexical = PROJECT_ROOT / raw
    if lexical.is_symlink():
        return False
    candidate = lexical.resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return False
    return bool(
        candidate.is_file()
        and type(row["bytes"]) is int
        and candidate.stat().st_size == row["bytes"]
        and type(row["sha256"]) is str
        and _sha256(candidate) == row["sha256"]
    )


def verify_published_chain() -> dict[str, Any]:
    try:
        gate = _load_json(GATE)
        terminal = _load_json(TERMINAL)
        evidence = gate.get("evidence", []) if isinstance(gate, dict) else []
        evidence_by_id = {
            row.get("id"): row for row in evidence if isinstance(row, dict) and type(row.get("id")) is str
        }
        evidence_pass = bool(
            len(evidence) == len(evidence_by_id) == 4
            and set(evidence_by_id) == set(EXPECTED_GATE_EVIDENCE)
            and all(
                _bound_record_matches(evidence_by_id[identifier], suffix)
                for identifier, suffix in EXPECTED_GATE_EVIDENCE.items()
            )
        )
        terminal_records = terminal.get("records", []) if isinstance(terminal, dict) else []
        terminal_record_pass = bool(
            len(terminal_records) == 1
            and isinstance(terminal_records[0], dict)
            and terminal_records[0].get("id") == "r2_execution_tooling_source_freeze_gate"
            and _bound_record_matches(
                terminal_records[0],
                "results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json",
            )
        )
        gate_false = gate.get("required_false", {})
        gate_zero = gate.get("required_zero", {})
        terminal_false = terminal.get("required_false", {})
        terminal_zero = terminal.get("required_zero", {})
        semantics_pass = bool(
            gate.get("status") == terminal.get("status") == "PASS_PHASE_B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_ONLY"
            and gate.get("source_inventory_sha256") == terminal.get("source_inventory_sha256")
            and gate.get("source_count") == terminal.get("source_count")
            and gate.get("r2_numerical_preflight_executed") is False
            and terminal.get("r2_numerical_preflight_executed") is False
            and gate.get("trajectory_count") == terminal.get("trajectory_count") == 0
            and gate_false and all(value is False for value in gate_false.values())
            and terminal_false and all(value is False for value in terminal_false.values())
            and gate_zero and all(type(value) is int and value == 0 for value in gate_zero.values())
            and terminal_zero and all(type(value) is int and value == 0 for value in terminal_zero.values())
        )
        return {
            "passed": evidence_pass and terminal_record_pass and semantics_pass,
            "gate_evidence_records_match_bytes_sha256": evidence_pass,
            "terminal_gate_record_matches_bytes_sha256": terminal_record_pass,
            "false_zero_and_status_semantics_pass": semantics_pass,
            "gate_sha256": _sha256(GATE),
            "terminal_sha256": _sha256(TERMINAL),
        }
    except Exception as exc:
        return {"passed": False, "error": f"{type(exc).__name__}:{exc}"}


def package_snapshot(package_root: Path = HERE) -> dict[str, dict[str, Any]]:
    root = package_root.resolve()
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RuntimeError(f"PACKAGE_LINK_FORBIDDEN:{path.relative_to(root).as_posix()}")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            snapshot[relative] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
    return snapshot


def snapshot_delta(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    before_paths = set(before)
    after_paths = set(after)
    return {
        "added": sorted(after_paths - before_paths),
        "removed": sorted(before_paths - after_paths),
        "changed": sorted(path for path in before_paths & after_paths if before[path] != after[path]),
    }


def main() -> int:
    before = package_snapshot()
    chain_before = verify_published_chain()
    command_results: list[dict[str, Any]] = []
    for name, command in COMMANDS:
        completed = subprocess.run(
            command,
            cwd=HERE,
            text=True,
            capture_output=True,
            check=False,
        )
        command_results.append({
            "name": name,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout.strip().splitlines()[-1:] or [],
            "stderr_tail": completed.stderr.strip().splitlines()[-1:] or [],
        })
        if completed.returncode != 0:
            break
    after = package_snapshot()
    chain_after = verify_published_chain()
    delta = snapshot_delta(before, after)
    unchanged = all(not value for value in delta.values())
    commands_pass = len(command_results) == len(COMMANDS) and all(row["returncode"] == 0 for row in command_results)
    passed = bool(commands_pass and unchanged and chain_before.get("passed") is True and chain_after.get("passed") is True)
    if not commands_pass:
        status = "FAIL_READ_ONLY_COMMAND"
    elif not unchanged:
        status = "FAIL_READ_ONLY_REPLAY_MUTATED_PACKAGE"
    elif chain_before.get("passed") is not True or chain_after.get("passed") is not True:
        status = "FAIL_PUBLISHED_HASH_CHAIN"
    else:
        status = "PASS_READ_ONLY_REPLAY_PACKAGE_BYTES_AND_PUBLISHED_HASH_CHAIN_UNCHANGED"
    result = {
        "status": status,
        "package_file_count": len(before),
        "commands": command_results,
        "delta": delta,
        "published_chain_before": chain_before,
        "published_chain_after": chain_after,
        "r2_numerical_preflight_executed": False,
        "trajectory_count": 0,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
