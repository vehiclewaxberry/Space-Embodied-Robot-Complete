"""Refreeze path-bound visualization evidence after REORG04.

This utility does not regenerate scientific results.  It updates the two
path-bound CSV manifests to the files at their post-migration locations while
retaining every pre-REORG04 path, size, and SHA-256 value as provenance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "6316f4e32afe00d5cfe7fb6340eb69862a17b1ea"

PROTECTION = ROOT / "40_evidence/artifacts/visualization/tables/gate_artifact_protection_manifest.csv"
FREEZE = ROOT / "40_evidence/artifacts/visualization/viz_gate0_freeze_manifest_20260714.csv"
LEDGER = ROOT / "01_project/governance/reorg04_evidence_refreeze.csv"

OLD_PROTECTION = "tables/visualization/gate_artifact_protection_manifest.csv"
OLD_FREEZE = "artifacts/visualization/viz_gate0_freeze_manifest_20260714.csv"
REASON = "root_namespace_path_refreeze_reorg04"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def baseline_csv(path: str) -> list[dict[str, str]]:
    result = subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:{path}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    text = result.stdout.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def current_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def refreeze_protection() -> list[dict[str, object]]:
    old_rows = baseline_csv(OLD_PROTECTION)
    rows = current_csv(PROTECTION)
    if len(old_rows) != 22 or len(rows) != 22:
        raise RuntimeError(f"protection row count changed: old={len(old_rows)} current={len(rows)}")

    output: list[dict[str, object]] = []
    ledger: list[dict[str, object]] = []
    for index, (old, row) in enumerate(zip(old_rows, rows), start=1):
        snapshot_rel = row["snapshot_path"].replace("\\", "/")
        snapshot = ROOT / snapshot_rel
        if not snapshot.is_file():
            raise FileNotFoundError(snapshot)
        current_hash = sha256(snapshot)
        output.append(
            {
                "source_rel_path": row["source_rel_path"],
                "expected_sha256": current_hash,
                "actual_sha256": current_hash,
                "match_expected": "True",
                "snapshot_path": row["snapshot_path"],
                "snapshot_hash_match": "True",
                "pre_reorg04_source_rel_path": old["source_rel_path"],
                "pre_reorg04_expected_sha256": old["expected_sha256"],
                "pre_reorg04_actual_sha256": old["actual_sha256"],
                "pre_reorg04_match_expected": old["match_expected"],
                "pre_reorg04_snapshot_path": old["snapshot_path"],
                "pre_reorg04_snapshot_hash_match": old["snapshot_hash_match"],
                "refreeze_reason": REASON,
            }
        )
        ledger.append(
            {
                "manifest_type": "e15_snapshot_protection",
                "row_index": index,
                "role": "protected_snapshot",
                "current_path": snapshot_rel,
                "pre_reorg04_path": old["snapshot_path"].replace("\\", "/"),
                "pre_reorg04_size_bytes": "",
                "current_size_bytes": snapshot.stat().st_size,
                "pre_reorg04_sha256": old["expected_sha256"],
                "current_sha256": current_hash,
                "byte_identity": str(current_hash.upper() == old["expected_sha256"].upper()).lower(),
                "refreeze_reason": REASON,
            }
        )

    fields = [
        "source_rel_path",
        "expected_sha256",
        "actual_sha256",
        "match_expected",
        "snapshot_path",
        "snapshot_hash_match",
        "pre_reorg04_source_rel_path",
        "pre_reorg04_expected_sha256",
        "pre_reorg04_actual_sha256",
        "pre_reorg04_match_expected",
        "pre_reorg04_snapshot_path",
        "pre_reorg04_snapshot_hash_match",
        "refreeze_reason",
    ]
    write_csv(PROTECTION, output, fields)
    return ledger


def refreeze_freeze_manifest() -> list[dict[str, object]]:
    old_rows = baseline_csv(OLD_FREEZE)
    rows = current_csv(FREEZE)
    if len(old_rows) != 29 or len(rows) != 29:
        raise RuntimeError(f"freeze row count changed: old={len(old_rows)} current={len(rows)}")

    output: list[dict[str, object]] = []
    ledger: list[dict[str, object]] = []
    for index, (old, row) in enumerate(zip(old_rows, rows), start=1):
        current_rel = row["path"].replace("\\", "/")
        current = ROOT / current_rel
        if not current.is_file():
            raise FileNotFoundError(current)
        current_hash = sha256(current)
        current_size = current.stat().st_size
        output.append(
            {
                "role": row["role"],
                "path": current_rel,
                "size_bytes": current_size,
                "sha256": current_hash,
                "pre_reorg04_path": old["path"],
                "pre_reorg04_size_bytes": old["size_bytes"],
                "pre_reorg04_sha256": old["sha256"],
                "refreeze_reason": REASON,
            }
        )
        ledger.append(
            {
                "manifest_type": "viz_gate0_freeze",
                "row_index": index,
                "role": row["role"],
                "current_path": current_rel,
                "pre_reorg04_path": old["path"],
                "pre_reorg04_size_bytes": old["size_bytes"],
                "current_size_bytes": current_size,
                "pre_reorg04_sha256": old["sha256"],
                "current_sha256": current_hash,
                "byte_identity": str(current_hash.upper() == old["sha256"].upper()).lower(),
                "refreeze_reason": REASON,
            }
        )

    fields = [
        "role",
        "path",
        "size_bytes",
        "sha256",
        "pre_reorg04_path",
        "pre_reorg04_size_bytes",
        "pre_reorg04_sha256",
        "refreeze_reason",
    ]
    write_csv(FREEZE, output, fields)
    return ledger


def validate() -> dict[str, int]:
    protection_rows = current_csv(PROTECTION)
    freeze_rows = current_csv(FREEZE)
    protection_bad = 0
    freeze_bad = 0
    provenance_bad = 0

    for row in protection_rows:
        snapshot = ROOT / row["snapshot_path"].replace("\\", "/")
        current_hash = sha256(snapshot) if snapshot.is_file() else ""
        if (
            not snapshot.is_file()
            or current_hash != row["expected_sha256"].upper()
            or row["actual_sha256"].upper() != row["expected_sha256"].upper()
            or row["match_expected"].lower() != "true"
            or row["snapshot_hash_match"].lower() != "true"
        ):
            protection_bad += 1
        if not row.get("pre_reorg04_expected_sha256") or row.get("refreeze_reason") != REASON:
            provenance_bad += 1

    for row in freeze_rows:
        path = ROOT / row["path"].replace("\\", "/")
        if (
            not path.is_file()
            or sha256(path) != row["sha256"].upper()
            or path.stat().st_size != int(row["size_bytes"])
        ):
            freeze_bad += 1
        if not row.get("pre_reorg04_sha256") or row.get("refreeze_reason") != REASON:
            provenance_bad += 1

    return {
        "protection_rows": len(protection_rows),
        "protection_mismatches": protection_bad,
        "freeze_rows": len(freeze_rows),
        "freeze_mismatches": freeze_bad,
        "provenance_mismatches": provenance_bad,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write refrozen manifests and provenance ledger")
    args = parser.parse_args()

    if args.apply:
        ledger = refreeze_protection()
        ledger.extend(refreeze_freeze_manifest())
        fields = [
            "manifest_type",
            "row_index",
            "role",
            "current_path",
            "pre_reorg04_path",
            "pre_reorg04_size_bytes",
            "current_size_bytes",
            "pre_reorg04_sha256",
            "current_sha256",
            "byte_identity",
            "refreeze_reason",
        ]
        write_csv(LEDGER, ledger, fields)

    result = validate()
    print(result)
    return 0 if all(result[key] == 0 for key in ("protection_mismatches", "freeze_mismatches", "provenance_mismatches")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
