#!/usr/bin/env python3
"""Phase A: capture independent, read-only pre-run mechanical baselines.

This script hashes protected source trees and files, writes only beneath the
new Phase A evidence directory, and rechecks every captured source after the
JSON evidence has been written.  It does not open or modify any CAD document.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCRIPT = Path(__file__).resolve()
V22 = SCRIPT.parent.parent
WORKSPACE = V22.parents[2]
V20 = V22.parent / "Space_Embodied_Robot_CAD_V2_0"
ASSET00 = V22 / "evidence" / "asset00"
B601_CONTROLLED = V22 / "30_B601_Controlled_Subassembly"
V22_TOP = V22 / "Assembly" / "Spacecraft_Service_Vehicle_V2_2.SLDASM"
V20_BASELINE = V20 / "evidence" / "digital_thread" / "native_file_hash_manifest_v2_final.csv"
ACCEPTED_B601_ROOT = WORKSPACE / "20_engineering" / "cad" / "spacecraft_layout" / "arm_b601_v1"
B601_BASELINE = V20 / "evidence" / "b3_00" / "B3_entry_baseline_manifest.csv"
ASSET_REGISTRY = ASSET00 / "asset_registry.yaml"
VENDOR_HASHES = ASSET00 / "vendor_file_hashes.json"
OUTPUT = V22 / "evidence" / "v22_b601_recovery_mechanical_unblock_01"

SCHEMA_VERSION = "1.0"
PHASE_ID = "V22_B601_RECOVERY_MECHANICAL_UNBLOCK_01_PHASE_A"
MANIFEST_FILES = {
    "asset00": "pre_run_01_asset00_evidence_tree.json",
    "b601_controlled": "pre_run_02_b601_controlled_subassembly.json",
    "v22_top": "pre_run_03_v22_authoritative_top.json",
    "v20_native": "pre_run_04_v20_native_57.json",
    "accepted_b601": "pre_run_05_accepted_b601_12.json",
    "registered_step": "pre_run_06_registered_step.json",
}


class PhaseAError(RuntimeError):
    """Fail-closed error for baseline capture."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> tuple[str, Any]:
    if not path.is_file():
        raise PhaseAError(f"required file missing: {path}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise PhaseAError(f"source changed while hashing: {path}")
    return digest.hexdigest(), after


def workspace_relative(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()
    except ValueError:
        return None


def file_record(
    path: Path,
    relative_path: str,
    *,
    expected_bytes: int | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    path = path.resolve()
    digest, stat = sha256_file(path)
    record: dict[str, Any] = {
        "relative_path": PurePosixPath(relative_path).as_posix(),
        "absolute_path": str(path),
        "workspace_relative_path": workspace_relative(path),
        "bytes": stat.st_size,
        "sha256": digest,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }
    if expected_bytes is not None or expected_sha256 is not None:
        bytes_match = expected_bytes is None or stat.st_size == expected_bytes
        sha_match = expected_sha256 is None or digest == expected_sha256.lower()
        record.update(
            {
                "expected_bytes": expected_bytes,
                "expected_sha256": expected_sha256.lower() if expected_sha256 else None,
                "bytes_match": bytes_match,
                "sha256_match": sha_match,
                "baseline_match": bytes_match and sha_match,
                "status": "MATCH" if bytes_match and sha_match else "MISMATCH",
            }
        )
    else:
        record["status"] = "CAPTURED"
    return record


def tree_summary(records: Iterable[dict[str, Any]], selection_mode: str) -> dict[str, Any]:
    rows = sorted(records, key=lambda item: item["relative_path"].casefold())
    extension_counts: Counter[str] = Counter()
    directories = {"."}
    max_depth = 0
    canonical = hashlib.sha256()
    total_bytes = 0
    for row in rows:
        rel = PurePosixPath(row["relative_path"])
        extension_counts[rel.suffix.lower() or "<none>"] += 1
        parents = rel.parts[:-1]
        max_depth = max(max_depth, len(parents))
        for index in range(1, len(parents) + 1):
            directories.add("/".join(parents[:index]))
        total_bytes += int(row["bytes"])
        canonical.update(
            f"{rel.as_posix()}\0{row['bytes']}\0{row['sha256']}\n".encode("utf-8")
        )
    return {
        "selection_mode": selection_mode,
        "file_count": len(rows),
        "directory_count_including_root": len(directories),
        "max_file_depth": max_depth,
        "total_bytes": total_bytes,
        "extension_counts": dict(sorted(extension_counts.items())),
        "tree_digest_sha256": canonical.hexdigest(),
    }


def common_manifest(manifest_id: str, captured_utc: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "manifest_id": manifest_id,
        "captured_utc": captured_utc,
        "capture_mode": "READ_ONLY_PRE_RUN",
        "hash_algorithm": "SHA-256",
        "source_mutation_authorized": False,
    }


def capture_tree(
    manifest_id: str,
    root: Path,
    captured_utc: str,
    authority: str,
) -> dict[str, Any]:
    if not root.is_dir():
        raise PhaseAError(f"required tree missing: {root}")
    paths = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )
    if not paths:
        raise PhaseAError(f"required tree is empty: {root}")
    records = [file_record(path, path.relative_to(root).as_posix()) for path in paths]
    manifest = common_manifest(manifest_id, captured_utc)
    manifest.update(
        {
            "authority": authority,
            "source_root": str(root.resolve()),
            "tree_summary": tree_summary(records, "RECURSIVE_TREE_ALL_FILES"),
            "files": records,
            "capture_status": "CAPTURED",
        }
    )
    return manifest


def capture_single(
    manifest_id: str,
    path: Path,
    captured_utc: str,
    authority: str,
) -> dict[str, Any]:
    record = file_record(path, path.name)
    manifest = common_manifest(manifest_id, captured_utc)
    manifest.update(
        {
            "authority": authority,
            "source_root": str(path.parent.resolve()),
            "tree_summary": tree_summary([record], "EXACT_SINGLE_FILE"),
            "files": [record],
            "capture_status": "CAPTURED",
        }
    )
    return manifest


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PhaseAError(f"baseline CSV missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def capture_baseline_selection(
    manifest_id: str,
    root: Path,
    baseline_path: Path,
    rows: list[dict[str, str]],
    expected_count: int,
    captured_utc: str,
    authority: str,
) -> dict[str, Any]:
    if len(rows) != expected_count:
        raise PhaseAError(
            f"{manifest_id} baseline count changed: {len(rows)} != {expected_count}"
        )
    relative_paths = [row["relative_path"] for row in rows]
    if len(set(relative_paths)) != len(relative_paths):
        raise PhaseAError(f"{manifest_id} baseline contains duplicate paths")
    records = []
    for row in rows:
        records.append(
            file_record(
                root / row["relative_path"],
                row["relative_path"],
                expected_bytes=int(row["bytes"]),
                expected_sha256=row["sha256"],
            )
        )
    mismatches = [row["relative_path"] for row in records if not row["baseline_match"]]
    baseline_source = file_record(
        baseline_path,
        workspace_relative(baseline_path) or baseline_path.name,
    )
    manifest = common_manifest(manifest_id, captured_utc)
    manifest.update(
        {
            "authority": authority,
            "source_root": str(root.resolve()),
            "baseline_manifest_source": baseline_source,
            "expected_item_count": expected_count,
            "tree_summary": tree_summary(records, "BASELINE_MANIFEST_EXACT_SELECTION"),
            "files": records,
            "mismatch_paths": mismatches,
            "capture_status": "MATCH" if not mismatches else "MISMATCH",
        }
    )
    return manifest


def parse_registered_step() -> tuple[Path, int, str, dict[str, Any]]:
    text = ASSET_REGISTRY.read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^  integrated_step_local:\s*\n"
        r"    path:\s*(?P<path>[^\r\n]+)\r?\n"
        r"    bytes:\s*(?P<bytes>\d+)\r?\n"
        r"    sha256:\s*(?P<sha>[0-9a-fA-F]{64})",
        text,
    )
    if match is None:
        raise PhaseAError("cannot parse integrated_step_local from asset_registry.yaml")
    registry_path = Path(match.group("path").strip().strip('"\''))
    registry_bytes = int(match.group("bytes"))
    registry_sha = match.group("sha").lower()
    vendor = json.loads(VENDOR_HASHES.read_text(encoding="utf-8"))["integrated_step"]
    registry_crosscheck = {
        "asset_registry_bytes": registry_bytes,
        "vendor_hashes_bytes": int(vendor["bytes"]),
        "bytes_match": registry_bytes == int(vendor["bytes"]),
        "asset_registry_sha256": registry_sha,
        "vendor_hashes_sha256": str(vendor["sha256"]).lower(),
        "sha256_match": registry_sha == str(vendor["sha256"]).lower(),
        "asset_registry_name": registry_path.name,
        "vendor_hashes_name": vendor["name"],
        "name_match": registry_path.name == vendor["name"],
    }
    if not all(
        registry_crosscheck[key]
        for key in ("bytes_match", "sha256_match", "name_match")
    ):
        raise PhaseAError(f"registered STEP sources disagree: {registry_crosscheck}")
    return registry_path, registry_bytes, registry_sha, registry_crosscheck


def capture_registered_step(captured_utc: str) -> dict[str, Any]:
    step_path, expected_bytes, expected_sha, crosscheck = parse_registered_step()
    record = file_record(
        step_path,
        step_path.name,
        expected_bytes=expected_bytes,
        expected_sha256=expected_sha,
    )
    registry_sources = [
        file_record(ASSET_REGISTRY, workspace_relative(ASSET_REGISTRY) or ASSET_REGISTRY.name),
        file_record(VENDOR_HASHES, workspace_relative(VENDOR_HASHES) or VENDOR_HASHES.name),
    ]
    manifest = common_manifest("PRE_RUN_REGISTERED_STEP", captured_utc)
    manifest.update(
        {
            "authority": "ASSET00_REGISTERED_VENDOR_STEP_GEOMETRY",
            "source_root": str(step_path.parent.resolve()),
            "registry_sources": registry_sources,
            "registry_crosscheck": crosscheck,
            "tree_summary": tree_summary([record], "EXACT_REGISTERED_STEP"),
            "files": [record],
            "capture_status": "MATCH" if record["baseline_match"] else "MISMATCH",
        }
    )
    return manifest


def json_bytes(payload: dict[str, Any]) -> bytes:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    json.loads(encoded)
    return encoded.encode("utf-8")


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    data = json_bytes(payload)
    with path.open("xb") as stream:
        stream.write(data)


def digest_index_rows(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: item["manifest_id"]):
        digest.update(
            f"{row['manifest_id']}\0{row['source_tree_digest_sha256']}\0"
            f"{row['source_file_count']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def recheck_manifest_sources(manifest: dict[str, Any]) -> dict[str, Any]:
    changed = []
    for row in manifest["files"]:
        path = Path(row["absolute_path"])
        if not path.is_file():
            changed.append({"path": row["relative_path"], "reason": "MISSING"})
            continue
        digest, stat = sha256_file(path)
        if stat.st_size != row["bytes"] or digest != row["sha256"]:
            changed.append(
                {
                    "path": row["relative_path"],
                    "reason": "CONTENT_CHANGED",
                    "captured_bytes": row["bytes"],
                    "current_bytes": stat.st_size,
                    "captured_sha256": row["sha256"],
                    "current_sha256": digest,
                }
            )
    return {
        "manifest_id": manifest["manifest_id"],
        "file_count": len(manifest["files"]),
        "changed_count": len(changed),
        "changed": changed,
        "status": "UNCHANGED" if not changed else "CHANGED",
    }


def main() -> int:
    if OUTPUT.exists():
        raise PhaseAError(f"refusing to overwrite existing evidence directory: {OUTPUT}")

    captured_utc = utc_now()
    v20_rows = read_csv(V20_BASELINE)
    b601_rows = [
        row
        for row in read_csv(B601_BASELINE)
        if row.get("check") == "B601_ASSET"
    ]

    manifests: dict[str, dict[str, Any]] = {
        "asset00": capture_tree(
            "PRE_RUN_ASSET00_EVIDENCE_TREE",
            ASSET00,
            captured_utc,
            "ASSET00_EXISTING_EVIDENCE_TREE",
        ),
        "b601_controlled": capture_tree(
            "PRE_RUN_V22_B601_CONTROLLED_SUBASSEMBLY",
            B601_CONTROLLED,
            captured_utc,
            "V22_CONTROLLED_Q0_PROXY_SUBASSEMBLY",
        ),
        "v22_top": capture_single(
            "PRE_RUN_V22_AUTHORITATIVE_TOP_ASSEMBLY",
            V22_TOP,
            captured_utc,
            "V22_AUTHORITATIVE_TOP_ASSEMBLY",
        ),
        "v20_native": capture_baseline_selection(
            "PRE_RUN_V20_NATIVE_57",
            V20,
            V20_BASELINE,
            v20_rows,
            57,
            captured_utc,
            "V20_SEALED_NATIVE_BASELINE",
        ),
        "accepted_b601": capture_baseline_selection(
            "PRE_RUN_ACCEPTED_B601_12",
            ACCEPTED_B601_ROOT,
            B601_BASELINE,
            b601_rows,
            12,
            captured_utc,
            "ACCEPTED_B601_URDF_MESH_README_BASELINE",
        ),
        "registered_step": capture_registered_step(captured_utc),
    }

    checks = [
        {
            "id": "ASSET00_TREE_CAPTURED",
            "pass": manifests["asset00"]["tree_summary"]["file_count"] > 0,
            "actual": manifests["asset00"]["tree_summary"]["file_count"],
        },
        {
            "id": "B601_CONTROLLED_TREE_CAPTURED",
            "pass": manifests["b601_controlled"]["tree_summary"]["file_count"] > 0,
            "actual": manifests["b601_controlled"]["tree_summary"]["file_count"],
        },
        {
            "id": "V22_TOP_CAPTURED",
            "pass": manifests["v22_top"]["tree_summary"]["file_count"] == 1,
            "actual": manifests["v22_top"]["tree_summary"]["file_count"],
        },
        {
            "id": "V20_NATIVE_57_MATCH",
            "pass": manifests["v20_native"]["capture_status"] == "MATCH",
            "actual": manifests["v20_native"]["tree_summary"]["file_count"],
        },
        {
            "id": "ACCEPTED_B601_12_MATCH",
            "pass": manifests["accepted_b601"]["capture_status"] == "MATCH",
            "actual": manifests["accepted_b601"]["tree_summary"]["file_count"],
        },
        {
            "id": "REGISTERED_STEP_MATCH",
            "pass": manifests["registered_step"]["capture_status"] == "MATCH",
            "actual": manifests["registered_step"]["files"][0]["sha256"],
        },
    ]
    if not all(check["pass"] for check in checks):
        raise PhaseAError(f"pre-write checks failed: {checks}")

    OUTPUT.mkdir(parents=True, exist_ok=False)
    for key, filename in MANIFEST_FILES.items():
        write_new_json(OUTPUT / filename, manifests[key])

    index_rows = []
    for key, filename in MANIFEST_FILES.items():
        output_record = file_record(OUTPUT / filename, filename)
        source_summary = manifests[key]["tree_summary"]
        index_rows.append(
            {
                "manifest_id": manifests[key]["manifest_id"],
                "path": filename,
                "bytes": output_record["bytes"],
                "sha256": output_record["sha256"],
                "capture_status": manifests[key]["capture_status"],
                "source_file_count": source_summary["file_count"],
                "source_total_bytes": source_summary["total_bytes"],
                "source_tree_digest_sha256": source_summary["tree_digest_sha256"],
            }
        )
    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "index_id": "PHASE_A_PRE_RUN_INDEX",
        "captured_utc": captured_utc,
        "written_utc": utc_now(),
        "write_scope": [str(SCRIPT), str(OUTPUT)],
        "protected_sources_read_only": True,
        "manifest_count": len(index_rows),
        "source_set_digest_sha256": digest_index_rows(index_rows),
        "manifests": index_rows,
        "pre_write_checks": checks,
        "machine_verdict": "PHASE_A_PRE_RUN_MANIFESTS_CAPTURED_PASS",
    }
    index_path = OUTPUT / "phase_a_pre_run_index.json"
    write_new_json(index_path, index_payload)

    parsed = {}
    for filename in [*MANIFEST_FILES.values(), index_path.name]:
        with (OUTPUT / filename).open("r", encoding="utf-8") as stream:
            parsed[filename] = json.load(stream)

    source_rechecks = [recheck_manifest_sources(manifest) for manifest in manifests.values()]
    index_rechecks = []
    for row in index_rows:
        digest, stat = sha256_file(OUTPUT / row["path"])
        match = digest == row["sha256"] and stat.st_size == row["bytes"]
        index_rechecks.append(
            {
                "path": row["path"],
                "bytes_match": stat.st_size == row["bytes"],
                "sha256_match": digest == row["sha256"],
                "status": "MATCH" if match else "MISMATCH",
            }
        )

    validation_checks = [
        {
            "id": "ALL_JSON_PARSE",
            "pass": len(parsed) == len(MANIFEST_FILES) + 1,
            "actual": len(parsed),
            "expected": len(MANIFEST_FILES) + 1,
        },
        {
            "id": "ALL_CAPTURED_SOURCES_UNCHANGED_DURING_WRITE",
            "pass": all(item["status"] == "UNCHANGED" for item in source_rechecks),
            "changed_count": sum(item["changed_count"] for item in source_rechecks),
        },
        {
            "id": "ALL_INDEXED_MANIFEST_HASHES_MATCH",
            "pass": all(item["status"] == "MATCH" for item in index_rechecks),
            "mismatch_count": sum(item["status"] != "MATCH" for item in index_rechecks),
        },
        *checks,
    ]
    overall_pass = all(check["pass"] for check in validation_checks)
    validation_payload = {
        "schema_version": SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "validation_id": "PHASE_A_JSON_AND_SOURCE_VALIDATION",
        "validated_utc": utc_now(),
        "json_files_parsed": sorted(parsed),
        "source_rechecks": source_rechecks,
        "indexed_manifest_rechecks": index_rechecks,
        "checks": validation_checks,
        "overall": "PASS" if overall_pass else "FAIL",
        "machine_verdict": (
            "PHASE_A_PRE_RUN_MANIFESTS_VALIDATED_PASS"
            if overall_pass
            else "PHASE_A_PRE_RUN_MANIFESTS_VALIDATION_FAIL"
        ),
    }
    validation_path = OUTPUT / "phase_a_validation.json"
    write_new_json(validation_path, validation_payload)
    with validation_path.open("r", encoding="utf-8") as stream:
        json.load(stream)

    print(
        json.dumps(
            {
                "phase_id": PHASE_ID,
                "output": str(OUTPUT),
                "manifest_count": len(index_rows),
                "source_file_counts": {
                    key: value["tree_summary"]["file_count"]
                    for key, value in manifests.items()
                },
                "overall": validation_payload["overall"],
                "machine_verdict": validation_payload["machine_verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if overall_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PhaseAError as exc:
        print(f"PHASE_A_FAIL_CLOSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
