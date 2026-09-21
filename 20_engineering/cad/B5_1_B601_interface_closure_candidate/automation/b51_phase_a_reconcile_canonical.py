from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
CAD_ROOT = WORKSPACE_ROOT / "20_engineering" / "cad"

B50_ROOT = CAD_ROOT / "B5_0_B601_space_manipulator_candidate"
V22_LEGACY_ROOT = CAD_ROOT / "Space_Embodied_Robot_CAD_V2_2"
V22_CANONICAL_ROOT = CAD_ROOT / "Space_Embodied_Robot_CAD_V2_2_NATIVE"
V23_ROOT = CAD_ROOT / "Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION"
V22_FREEZE_MANIFEST = V23_ROOT / "baseline_freeze_manifest.yaml"

POSEMAP120_ROOT = (
    V22_LEGACY_ROOT / "120_B601_Geometry_and_PoseMap_02"
)
VENDOR130_ROOT = (
    V22_LEGACY_ROOT / "130_B601_Vendor_CAD_Direct_Integration_03"
)
POSEMAP120_MANIFEST = POSEMAP120_ROOT / "validation" / "artifact_manifest.json"
VENDOR130_MANIFEST = VENDOR130_ROOT / "validation" / "artifact_manifest.json"

ACCEPTED_PACKAGE = CAD_ROOT / "spacecraft_layout" / "arm_b601_v1"
ACCEPTED_URDF = ACCEPTED_PACKAGE / "arm_b601_v1.urdf"
VENDOR_STEP = Path(
    r"F:\Robotic arm\High_performance_robotics_arm\vendor"
    r"\reBot-DevArm\hardware\reBot_B601_DM"
    r"\reBot_B601_DM_v1.1_20260425.step"
)

EXPECTED_CANONICAL_TOP = (
    V22_CANONICAL_ROOT
    / "Assembly"
    / "Space_Embodied_Service_Spacecraft_V2_2.SLDASM"
)
EXPECTED_CANONICAL_TOP_SHA256 = (
    "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A"
)
EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_VENDOR_STEP_SHA256 = (
    "87A0537D1AFD50C04FC441FDE11DD4F2EBBB368FE27F6C10FDA8567BE696D968"
)

DONOR_ROOT = CANDIDATE_ROOT / "00_BASELINE_DONORS"
V22_COPY_ROOT = DONOR_ROOT / "V2_2_NATIVE_CANONICAL_108_FILE_COPY"
B50_COPY_ROOT = DONOR_ROOT / "B5_0_ACCEPTED_CANDIDATE_FULL_COPY"

AUDIT_ROOT = CANDIDATE_ROOT / "00_AUDIT"
LOCK_PATH = AUDIT_ROOT / "B51_INPUT_LOCK_V2_CANONICAL.json"
OWNERSHIP_PATH = AUDIT_ROOT / "B51_REFERENCE_OWNERSHIP_V2_CANONICAL.json"
MANIFEST_PATH = AUDIT_ROOT / "B51_BASELINE_HASH_MANIFEST_V2_CANONICAL.csv"
COPY_REPORT_PATH = AUDIT_ROOT / "B51_CANONICAL_COPY_VERIFICATION.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_record(
    path: Path,
    *,
    owner: str,
    access: str,
    relative_to: Path | None = None,
    source_path: Path | None = None,
) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise RuntimeError(f"required file is missing: {resolved}")
    return {
        "owner": owner,
        "access": access,
        "path": str(resolved),
        "relative_path": (
            resolved.relative_to(relative_to.resolve()).as_posix()
            if relative_to is not None
            else ""
        ),
        "source_path": (
            str(source_path.resolve()) if source_path is not None else ""
        ),
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "os_read_only": not bool(resolved.stat().st_mode & 0o200),
    }


def iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise RuntimeError(f"required directory is missing: {root}")
    return sorted(path for path in root.rglob("*") if path.is_file())


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def require_hash(path: Path, expected: str, label: str) -> dict[str, Any]:
    actual = sha256_file(path)
    if actual != expected.upper():
        raise RuntimeError(
            f"{label} hash drift: {actual} != {expected.upper()}"
        )
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": actual,
        "match": True,
    }


def verify_json_manifest(
    root: Path, manifest_path: Path, expected_id: str
) -> dict[str, Any]:
    payload = load_json(manifest_path)
    if payload.get("manifest_id") != expected_id:
        raise RuntimeError(
            f"manifest id mismatch in {manifest_path}: "
            f"{payload.get('manifest_id')} != {expected_id}"
        )
    declared = payload.get("files")
    if not isinstance(declared, dict):
        raise RuntimeError(f"manifest files mapping missing: {manifest_path}")
    mismatches: list[dict[str, Any]] = []
    for relative, expected in sorted(declared.items()):
        path = root / relative
        if not path.is_file():
            mismatches.append(
                {"relative_path": relative, "reason": "MISSING"}
            )
            continue
        actual_hash = sha256_file(path)
        actual_bytes = path.stat().st_size
        expected_hash = str(expected["sha256"]).upper()
        expected_bytes = int(expected["bytes"])
        if actual_hash != expected_hash or actual_bytes != expected_bytes:
            mismatches.append(
                {
                    "relative_path": relative,
                    "reason": "HASH_OR_SIZE_MISMATCH",
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                    "expected_bytes": expected_bytes,
                    "actual_bytes": actual_bytes,
                }
            )
    if mismatches:
        raise RuntimeError(
            f"{expected_id} verification failed: {mismatches[:3]}"
        )
    if int(payload.get("file_count", -1)) != len(declared):
        raise RuntimeError(
            f"{expected_id} declared count mismatch: "
            f"{payload.get('file_count')} != {len(declared)}"
        )
    return {
        "manifest_id": expected_id,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": sha256_file(manifest_path),
        "declared_files": len(declared),
        "checked": len(declared),
        "mismatches": [],
        "status": "PASS",
    }


def load_canonical_freeze() -> tuple[dict[str, Any], dict[str, Any]]:
    with V22_FREEZE_MANIFEST.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError("canonical freeze manifest is not a mapping")
    files = payload.get("files")
    if not isinstance(files, dict):
        raise RuntimeError("canonical freeze manifest files mapping missing")
    if payload.get("source_root") != "Space_Embodied_Robot_CAD_V2_2_NATIVE":
        raise RuntimeError("canonical freeze source_root drift")
    if payload.get("canonical_top") != (
        "Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM"
    ):
        raise RuntimeError("canonical top relative path drift")
    if str(payload.get("canonical_top_sha256", "")).upper() != (
        EXPECTED_CANONICAL_TOP_SHA256
    ):
        raise RuntimeError("canonical top manifest hash drift")
    if int(payload.get("file_count", -1)) != 108 or len(files) != 108:
        raise RuntimeError(
            f"canonical freeze count drift: "
            f"{payload.get('file_count')} / {len(files)}"
        )

    mismatches: list[dict[str, Any]] = []
    for relative, expected in sorted(files.items()):
        source = V22_CANONICAL_ROOT / relative
        if not source.is_file():
            mismatches.append(
                {"relative_path": relative, "reason": "MISSING"}
            )
            continue
        actual_hash = sha256_file(source)
        actual_bytes = source.stat().st_size
        expected_hash = str(expected["sha256"]).upper()
        expected_bytes = int(expected["bytes"])
        if actual_hash != expected_hash or actual_bytes != expected_bytes:
            mismatches.append(
                {
                    "relative_path": relative,
                    "reason": "HASH_OR_SIZE_MISMATCH",
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                    "expected_bytes": expected_bytes,
                    "actual_bytes": actual_bytes,
                }
            )
    if mismatches:
        raise RuntimeError(
            f"canonical V2.2 freeze verification failed: {mismatches[:3]}"
        )
    return payload, {
        "manifest_path": str(V22_FREEZE_MANIFEST.resolve()),
        "manifest_sha256": sha256_file(V22_FREEZE_MANIFEST),
        "checked": 108,
        "matched": 108,
        "mismatches": [],
        "canonical_top": require_hash(
            EXPECTED_CANONICAL_TOP,
            EXPECTED_CANONICAL_TOP_SHA256,
            "canonical V2.2 top",
        ),
        "status": "PASS",
    }


def copy_verified(
    source: Path, target: Path, expected_hash: str | None = None
) -> dict[str, Any]:
    source_hash_before = sha256_file(source)
    if expected_hash is not None and source_hash_before != expected_hash.upper():
        raise RuntimeError(
            f"source hash differs from manifest: {source} "
            f"{source_hash_before} != {expected_hash.upper()}"
        )
    if target.exists():
        target_hash = sha256_file(target)
        if target_hash != source_hash_before:
            raise RuntimeError(
                f"existing copy differs; refusing overwrite: {target}"
            )
        action = "REUSED_IDENTICAL_EXISTING_COPY"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        target_hash = sha256_file(target)
        if target_hash != source_hash_before:
            raise RuntimeError(f"copy hash mismatch: {source} -> {target}")
        action = "COPIED_AND_HASH_VERIFIED"
    source_hash_after = sha256_file(source)
    if source_hash_after != source_hash_before:
        raise RuntimeError(f"source changed during copy: {source}")
    return {
        "source": str(source.resolve()),
        "target": str(target.resolve()),
        "bytes": source.stat().st_size,
        "sha256": source_hash_before,
        "action": action,
        "source_unchanged_during_copy": True,
        "target_match": True,
    }


def copy_canonical_tree(
    freeze_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for relative, expected in sorted(freeze_payload["files"].items()):
        source = V22_CANONICAL_ROOT / relative
        target = V22_COPY_ROOT / relative
        copied = copy_verified(source, target, str(expected["sha256"]))
        records.append(copied)
        manifest_rows.append(
            file_record(
                source,
                owner="V2_2_NATIVE_CANONICAL_SOURCE",
                access="READ_ONLY_ACCEPTED_BASELINE",
                relative_to=V22_CANONICAL_ROOT,
            )
        )
        manifest_rows.append(
            file_record(
                target,
                owner="B51_V2_2_NATIVE_CANONICAL_COPY",
                access="READ_ONLY_CANDIDATE_DONOR_COPY",
                relative_to=V22_COPY_ROOT,
                source_path=source,
            )
        )
    return records, manifest_rows


def copy_b50_tree() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_files = iter_files(B50_ROOT)
    before = {
        path.relative_to(B50_ROOT).as_posix(): sha256_file(path)
        for path in source_files
    }
    records: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for source in source_files:
        relative = source.relative_to(B50_ROOT)
        target = B50_COPY_ROOT / relative
        copied = copy_verified(source, target, before[relative.as_posix()])
        records.append(copied)
        manifest_rows.append(
            file_record(
                source,
                owner="B5_0_ACCEPTED_CANDIDATE_SOURCE",
                access="READ_ONLY_ACCEPTED_CANDIDATE",
                relative_to=B50_ROOT,
            )
        )
        manifest_rows.append(
            file_record(
                target,
                owner="B51_B5_0_ACCEPTED_CANDIDATE_COPY",
                access="READ_ONLY_CANDIDATE_DONOR_COPY",
                relative_to=B50_COPY_ROOT,
                source_path=source,
            )
        )
    after = {
        path.relative_to(B50_ROOT).as_posix(): sha256_file(path)
        for path in source_files
    }
    if before != after:
        changed = sorted(
            key for key in before if before.get(key) != after.get(key)
        )
        raise RuntimeError(f"B5.0 changed during copy: {changed[:3]}")
    return records, manifest_rows


def main() -> int:
    output_paths = [
        LOCK_PATH,
        OWNERSHIP_PATH,
        MANIFEST_PATH,
        COPY_REPORT_PATH,
    ]
    existing = [str(path) for path in output_paths if path.exists()]
    if existing:
        raise RuntimeError(f"append-only outputs already exist: {existing}")

    canonical_payload, canonical_live = load_canonical_freeze()
    posemap120 = verify_json_manifest(
        POSEMAP120_ROOT, POSEMAP120_MANIFEST, "POSEMAP02_ARTIFACT_MANIFEST"
    )
    vendor130 = verify_json_manifest(
        VENDOR130_ROOT, VENDOR130_MANIFEST, "VENDORCAD03_ARTIFACT_MANIFEST"
    )
    accepted_urdf = require_hash(
        ACCEPTED_URDF, EXPECTED_URDF_SHA256, "accepted B601 URDF"
    )
    vendor_step = require_hash(
        VENDOR_STEP, EXPECTED_VENDOR_STEP_SHA256, "vendor STEP"
    )

    v22_copy_records, manifest_rows = copy_canonical_tree(canonical_payload)
    b50_copy_records, b50_manifest_rows = copy_b50_tree()
    manifest_rows.extend(b50_manifest_rows)

    for path in iter_files(ACCEPTED_PACKAGE):
        manifest_rows.append(
            file_record(
                path,
                owner="ACCEPTED_B601_PACKAGE",
                access="READ_ONLY_TRUTH",
                relative_to=ACCEPTED_PACKAGE,
            )
        )
    manifest_rows.append(
        file_record(
            VENDOR_STEP,
            owner="VENDOR_STEP",
            access="READ_ONLY_GEOMETRY_ONLY",
        )
    )
    for path in iter_files(POSEMAP120_ROOT):
        manifest_rows.append(
            file_record(
                path,
                owner="V22_POSEMAP120_EVIDENCE_TREE",
                access="READ_ONLY_EVIDENCE",
                relative_to=POSEMAP120_ROOT,
            )
        )
    for path in iter_files(VENDOR130_ROOT):
        manifest_rows.append(
            file_record(
                path,
                owner="V22_VENDOR130_EVIDENCE_TREE",
                access="READ_ONLY_EVIDENCE",
                relative_to=VENDOR130_ROOT,
            )
        )
    manifest_rows.append(
        file_record(
            V22_FREEZE_MANIFEST,
            owner="V2_2_NATIVE_CANONICAL_FREEZE_SEAL",
            access="READ_ONLY_CONTROL",
        )
    )

    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "owner",
        "access",
        "path",
        "relative_path",
        "source_path",
        "bytes",
        "sha256",
        "os_read_only",
    ]
    with MANIFEST_PATH.open(
        "x", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    copy_report = {
        "schema": "SER_B51_CANONICAL_COPY_VERIFICATION_V1",
        "generated_utc": utc_now(),
        "status": "B51_CANONICAL_AND_B50_ISOLATED_COPY_HASH_PASS",
        "canonical_v22": {
            "source_root": str(V22_CANONICAL_ROOT.resolve()),
            "copy_root": str(V22_COPY_ROOT.resolve()),
            "files": len(v22_copy_records),
            "bytes": sum(item["bytes"] for item in v22_copy_records),
            "source_copy_mismatches": 0,
            "records": v22_copy_records,
        },
        "b50_candidate": {
            "source_root": str(B50_ROOT.resolve()),
            "copy_root": str(B50_COPY_ROOT.resolve()),
            "files": len(b50_copy_records),
            "bytes": sum(item["bytes"] for item in b50_copy_records),
            "source_copy_mismatches": 0,
            "records": b50_copy_records,
        },
        "reference_rewrite_and_cold_reopen": (
            "PENDING_NATIVE_REFERENCE_AUDIT_HOLD"
        ),
    }
    write_json_once(COPY_REPORT_PATH, copy_report)

    ownership = {
        "schema": "SER_B51_REFERENCE_OWNERSHIP_V2",
        "generated_utc": utc_now(),
        "status": "CANONICAL_V2_2_NATIVE_BASELINE_RECONCILED",
        "supersedes": "00_AUDIT/B51_REFERENCE_OWNERSHIP.json",
        "candidate_root": str(CANDIDATE_ROOT.resolve()),
        "write_policy": "ALL_WRITES_MUST_RESOLVE_WITHIN_CANDIDATE_ROOT",
        "entries": [
            {
                "root": str(CANDIDATE_ROOT.resolve()),
                "owner": "B5_1",
                "access": "READ_WRITE_CANDIDATE_ONLY",
            },
            {
                "root": str(V22_CANONICAL_ROOT.resolve()),
                "owner": "V2_2_NATIVE_CANONICAL_ACCEPTED_BASELINE",
                "access": "READ_ONLY_NO_SAVE",
            },
            {
                "root": str(V22_COPY_ROOT.resolve()),
                "owner": "B51_ISOLATED_CANONICAL_V2_2_COPY",
                "access": "READ_ONLY_DONOR_COPY_UNTIL_REFERENCE_REWRITE",
            },
            {
                "root": str(B50_ROOT.resolve()),
                "owner": "B5_0_ACCEPTED_CANDIDATE",
                "access": "READ_ONLY_NO_SAVE",
            },
            {
                "root": str(B50_COPY_ROOT.resolve()),
                "owner": "B51_ISOLATED_B5_0_COPY",
                "access": "READ_ONLY_DONOR_COPY",
            },
            {
                "root": str(V22_LEGACY_ROOT.resolve()),
                "owner": "V2_2_LEGACY_FUNCTIONAL_TREE",
                "access": "REFERENCE_DONOR_ONLY_NO_TOP_ASSEMBLY_AUTHORITY",
            },
            {
                "root": str(ACCEPTED_PACKAGE.resolve()),
                "owner": "ACCEPTED_B601_PACKAGE",
                "access": "READ_ONLY_TRUTH",
            },
            {
                "root": str(VENDOR_STEP.resolve()),
                "owner": "VENDOR",
                "access": "READ_ONLY_GEOMETRY_REFERENCE",
            },
        ],
        "canonical_top": str(EXPECTED_CANONICAL_TOP.resolve()),
        "canonical_top_sha256": EXPECTED_CANONICAL_TOP_SHA256,
        "legacy_v22_role": (
            "REFERENCE_DONOR_ONLY; legacy "
            "Spacecraft_Service_Vehicle_V2_2.SLDASM is not canonical"
        ),
        "native_reference_status": (
            "COPIED_AND_HASH_VERIFIED; COLD_REOPEN_REFERENCE_CONTAINMENT_HOLD"
        ),
    }
    write_json_once(OWNERSHIP_PATH, ownership)

    lock = {
        "schema": "SER_B51_INPUT_LOCK_V2_CANONICAL",
        "generated_utc": utc_now(),
        "task_id": (
            "COMP-PROT-03-A4-B5.1-B601-INTERFACE-CLOSURE-"
            "ARTICULATION-STOWAGE"
        ),
        "status": (
            "B51_PHASE_A_CANONICAL_COPY_PASS_"
            "COLD_REOPEN_REFERENCE_CONTAINMENT_HOLD"
        ),
        "supersedes_without_deleting": "00_AUDIT/B51_INPUT_LOCK.json",
        "correction_reason": (
            "The prior lock treated the legacy 102-file V2.2 functional tree "
            "as the frozen top-level donor. The current human ruling binds "
            "Space_Embodied_Robot_CAD_V2_2_NATIVE and its 108-file freeze "
            "manifest as the canonical accepted native baseline."
        ),
        "accepted_urdf": accepted_urdf,
        "accepted_urdf_mass_kg_source_decimal": "4.6955559493429862",
        "accepted_urdf_topology": {
            "revolute": 6,
            "fixed": 1,
            "prismatic": 2,
        },
        "vendor_step": vendor_step,
        "canonical_v22": canonical_live,
        "posemap120_evidence": posemap120,
        "vendor130_evidence": vendor130,
        "isolated_copies": {
            "canonical_v22": {
                "root": str(V22_COPY_ROOT.resolve()),
                "files": len(v22_copy_records),
                "bytes": sum(item["bytes"] for item in v22_copy_records),
                "hash_mismatches": 0,
            },
            "b50_candidate": {
                "root": str(B50_COPY_ROOT.resolve()),
                "files": len(b50_copy_records),
                "bytes": sum(item["bytes"] for item in b50_copy_records),
                "hash_mismatches": 0,
            },
        },
        "baseline_manifest": MANIFEST_PATH.relative_to(
            CANDIDATE_ROOT
        ).as_posix(),
        "copy_verification": COPY_REPORT_PATH.relative_to(
            CANDIDATE_ROOT
        ).as_posix(),
        "reference_ownership": OWNERSHIP_PATH.relative_to(
            CANDIDATE_ROOT
        ).as_posix(),
        "g0": (
            "HOLD_UNTIL_CANONICAL_TOP_COLD_REOPEN_RESOLVES_ONLY_TO_B51_COPY"
        ),
        "holds": [
            "Canonical V2.2 and B5.0 copies are hash-verified but native "
            "SolidWorks reference containment has not yet passed cold reopen.",
            "G05 and G08 remain CHAIN_DERIVED_HOLD.",
            "G08 fixed/left/right partition and gripper zero calibration "
            "remain open.",
        ],
        "next_gate": (
            "B51_CANONICAL_TOP_COLD_REOPEN_REFERENCE_CONTAINMENT_AUDIT"
        ),
    }
    write_json_once(LOCK_PATH, lock)

    print(
        json.dumps(
            {
                "status": lock["status"],
                "canonical_v22_files": len(v22_copy_records),
                "b50_files": len(b50_copy_records),
                "manifest_rows": len(manifest_rows),
                "g0": lock["g0"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
