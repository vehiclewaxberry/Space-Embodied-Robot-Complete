from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
B50_ROOT = (
    WORKSPACE_ROOT
    / "20_engineering"
    / "cad"
    / "B5_0_B601_space_manipulator_candidate"
)
V22_ROOT = (
    WORKSPACE_ROOT
    / "20_engineering"
    / "cad"
    / "Space_Embodied_Robot_CAD_V2_2"
)
V22_VENDOR03 = V22_ROOT / "130_B601_Vendor_CAD_Direct_Integration_03"
ACCEPTED_PACKAGE = (
    WORKSPACE_ROOT
    / "20_engineering"
    / "cad"
    / "spacecraft_layout"
    / "arm_b601_v1"
)
ACCEPTED_URDF = ACCEPTED_PACKAGE / "arm_b601_v1.urdf"
VENDOR_STEP = Path(
    r"F:\Robotic arm\High_performance_robotics_arm\vendor"
    r"\reBot-DevArm\hardware\reBot_B601_DM"
    r"\reBot_B601_DM_v1.1_20260425.step"
)
B50_NATIVE_RUN = (
    B50_ROOT / "03_CAD" / "native_runs" / "B50_NATIVE_20260727T2214Z"
)

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_VENDOR_STEP_SHA256 = (
    "87A0537D1AFD50C04FC441FDE11DD4F2EBBB368FE27F6C10FDA8567BE696D968"
)
EXPECTED_V22_TOP_SHA256 = (
    "3B55EDB85B460ECBC23EEC55B99FF83506C33E0F4CECDB0375BABC7B0D50CFB9"
)

CONTROL_RELATIVE_PATHS = [
    "V22_B601_VENDOR_CAD_DIRECT_INTEGRATION_03_REPORT.md",
    "validation/s0_input_lock.json",
    "validation/machine_checks.json",
    "validation/machine_verdict.json",
    "design/adapter_clocking.json",
    "design/b601_stow_joint_vector_v2.json",
    "design/group_link_transforms.json",
    "design/group_link_registration.json",
    "design/stow_contact_registry.json",
    "design/state_policy_vendorcad03.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def record(path: Path, owner: str, access: str) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "owner": owner,
        "access": access,
        "path": str(resolved),
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "os_read_only": not bool(resolved.stat().st_mode & 0o200),
    }


def iter_files(root: Path) -> Iterable[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"{label} is missing: {path}")
    return path


def require_hash(path: Path, expected: str, label: str) -> dict[str, Any]:
    item = record(path, label, "READ_ONLY")
    if item["sha256"] != expected:
        raise RuntimeError(
            f"{label} hash drift: {item['sha256']} != {expected}"
        )
    return item


def write_json_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"overwrite forbidden: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_once(source: Path, target: Path) -> dict[str, Any]:
    require_file(source, "copy source")
    if target.exists():
        raise RuntimeError(f"copy target exists; overwrite forbidden: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    source_hash = sha256_file(source)
    target_hash = sha256_file(target)
    if source_hash != target_hash:
        raise RuntimeError(f"copy hash mismatch: {source} -> {target}")
    return {
        "source": str(source.resolve()),
        "target": target.relative_to(CANDIDATE_ROOT).as_posix(),
        "bytes": target.stat().st_size,
        "sha256": target_hash,
        "copy_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the append-only B5.1 Phase A input lock."
    )
    parser.parse_args()

    if not CANDIDATE_ROOT.is_dir():
        raise RuntimeError(f"candidate root is missing: {CANDIDATE_ROOT}")

    audit_root = CANDIDATE_ROOT / "00_AUDIT"
    lock_path = audit_root / "B51_INPUT_LOCK.json"
    ownership_path = audit_root / "B51_REFERENCE_OWNERSHIP.json"
    manifest_path = audit_root / "B51_BASELINE_HASH_MANIFEST.csv"
    if any(path.exists() for path in (lock_path, ownership_path, manifest_path)):
        raise RuntimeError("Phase A outputs already exist; overwrite forbidden")

    accepted_urdf = require_hash(
        require_file(ACCEPTED_URDF, "accepted URDF"),
        EXPECTED_URDF_SHA256,
        "ACCEPTED_URDF",
    )
    vendor_step = require_hash(
        require_file(VENDOR_STEP, "vendor STEP"),
        EXPECTED_VENDOR_STEP_SHA256,
        "VENDOR_STEP_GEOMETRY_ONLY",
    )
    v22_top_path = (
        V22_ROOT / "Assembly" / "Spacecraft_Service_Vehicle_V2_2.SLDASM"
    )
    v22_top = require_hash(
        require_file(v22_top_path, "V2.2 top assembly"),
        EXPECTED_V22_TOP_SHA256,
        "V2_2_TOP_ASSEMBLY_READ_ONLY_DONOR",
    )

    controls: list[dict[str, Any]] = []
    for relative in CONTROL_RELATIVE_PATHS:
        path = require_file(V22_VENDOR03 / relative, f"control {relative}")
        controls.append(record(path, "V22_VENDOR03_CONTROL", "READ_ONLY"))

    accepted_files = list(iter_files(ACCEPTED_PACKAGE))
    if len(accepted_files) != 12:
        raise RuntimeError(
            f"accepted package file count {len(accepted_files)} != 12"
        )

    native_suffixes = {".sldprt", ".sldasm", ".slddrw"}
    v22_native_files = [
        path
        for path in iter_files(V22_ROOT)
        if path.suffix.lower() in native_suffixes
        and "B5_1_B601_interface_closure_candidate" not in str(path)
    ]
    if len(v22_native_files) != 102:
        raise RuntimeError(
            f"V2.2 native CAD count {len(v22_native_files)} != 102"
        )

    copied_parts: list[dict[str, Any]] = []
    source_parts = sorted(
        (B50_NATIVE_RUN / "10_vendor_reference_parts").glob("*.SLDPRT")
    )
    if len(source_parts) != 8:
        raise RuntimeError(
            f"B5.0 native link-local part count {len(source_parts)} != 8"
        )
    for source in source_parts:
        copied_parts.append(
            copy_once(
                source,
                CANDIDATE_ROOT
                / "03_CAD"
                / "native_inputs"
                / "10_vendor_link_parts"
                / source.name.replace("B50_", "B51_"),
            )
        )
    skeleton_source = require_file(
        B50_NATIVE_RUN / "00_skeleton" / "B50_B601_MASTER_SKELETON.SLDPRT",
        "B5.0 master skeleton",
    )
    copied_parts.append(
        copy_once(
            skeleton_source,
            CANDIDATE_ROOT
            / "03_CAD"
            / "native_inputs"
            / "00_skeleton"
            / "B51_B601_Q0_REFERENCE_SKELETON.SLDPRT",
        )
    )

    manifest_rows: list[dict[str, Any]] = []

    def append_manifest(
        paths: Iterable[Path], owner: str, access: str
    ) -> None:
        for path in paths:
            item = record(path, owner, access)
            manifest_rows.append(item)

    append_manifest(accepted_files, "ACCEPTED_B601_PACKAGE", "READ_ONLY")
    append_manifest([VENDOR_STEP], "VENDOR_STEP", "READ_ONLY_GEOMETRY_ONLY")
    append_manifest(v22_native_files, "V2_2_NATIVE_TREE", "READ_ONLY_DONOR")
    append_manifest(
        [V22_VENDOR03 / relative for relative in CONTROL_RELATIVE_PATHS],
        "V22_VENDOR03_CONTROL",
        "READ_ONLY",
    )
    append_manifest(
        [
            B50_ROOT / "07_VERIFICATION" / "GATE_STATUS.json",
            B50_ROOT / "07_VERIFICATION" / "protected_hash_verification.json",
            B50_NATIVE_RUN
            / "evidence"
            / "native_q0_cold_verify.json",
        ],
        "B5_0_ACCEPTED_EVIDENCE",
        "READ_ONLY",
    )

    audit_root.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "owner",
        "access",
        "path",
        "bytes",
        "sha256",
        "os_read_only",
    ]
    with manifest_path.open("x", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    ownership = {
        "schema": "SER_B51_REFERENCE_OWNERSHIP_V1",
        "generated_utc": utc_now(),
        "candidate_root": str(CANDIDATE_ROOT.resolve()),
        "write_policy": "ALL_WRITES_MUST_RESOLVE_WITHIN_CANDIDATE_ROOT",
        "entries": [
            {
                "root": str(CANDIDATE_ROOT.resolve()),
                "owner": "B5_1",
                "access": "READ_WRITE_CANDIDATE_ONLY",
            },
            {
                "root": str(B50_ROOT.resolve()),
                "owner": "B5_0_ACCEPTED",
                "access": "READ_ONLY_SOURCE_FOR_VERIFIED_COPIES",
            },
            {
                "root": str(V22_ROOT.resolve()),
                "owner": "V2_2_FROZEN_DONOR",
                "access": "READ_ONLY_EXTERNAL_DONOR_NO_SAVE",
            },
            {
                "root": str(ACCEPTED_PACKAGE.resolve()),
                "owner": "ACCEPTED_URDF_PACKAGE",
                "access": "READ_ONLY_TRUTH",
            },
            {
                "root": str(VENDOR_STEP.resolve()),
                "owner": "VENDOR",
                "access": "READ_ONLY_GEOMETRY_REFERENCE",
            },
        ],
        "pack_and_go_status": (
            "NOT_AVAILABLE; V2.2 remains an explicit read-only external donor"
        ),
        "top_level_integration_limit": (
            "No B5.1 claim of a self-contained V2.2 reference tree until "
            "Pack and Go or verified reference rewrite passes cold reopen."
        ),
    }
    write_json_once(ownership_path, ownership)

    lock = {
        "schema": "SER_B51_INPUT_LOCK_V1",
        "generated_utc": utc_now(),
        "task_id": (
            "COMP-PROT-03-A4-B5.1-B601-INTERFACE-CLOSURE-"
            "ARTICULATION-STOWAGE"
        ),
        "status": (
            "B51_PHASE_A_INPUT_LOCK_PASS_WITH_V22_EXTERNAL_READ_ONLY_DONOR"
        ),
        "candidate_root": str(CANDIDATE_ROOT.resolve()),
        "isolation_choice": (
            "SIBLING_ROOT_TO_AVOID_MUTATING_THE_B5_0_ACCEPTED_CANDIDATE"
        ),
        "accepted_urdf": accepted_urdf,
        "accepted_urdf_mass_kg_source_decimal": "4.6955559493429862",
        "vendor_step": vendor_step,
        "v22_top_assembly": v22_top,
        "v22_native_tree": {
            "file_count": len(v22_native_files),
            "bytes": sum(path.stat().st_size for path in v22_native_files),
            "access": "READ_ONLY_EXTERNAL_DONOR",
            "full_tree_final_seal": "NOT_AVAILABLE_HOLD",
        },
        "control_files": controls,
        "accepted_package": {
            "file_count": len(accepted_files),
            "bytes": sum(path.stat().st_size for path in accepted_files),
        },
        "copied_b51_native_inputs": copied_parts,
        "baseline_manifest": manifest_path.relative_to(
            CANDIDATE_ROOT
        ).as_posix(),
        "reference_ownership": ownership_path.relative_to(
            CANDIDATE_ROOT
        ).as_posix(),
        "holds": [
            "V2.2 complete 102-file native tree has no authoritative final seal.",
            "No Pack and Go/reference rewrite has yet produced a self-contained B5.1 V2.2 tree.",
            "G05 and G08 remain CHAIN_DERIVED_HOLD.",
            "G08 fixed/left/right partition and gripper zero calibration are not closed.",
        ],
        "next_gate": (
            "B51_H9_H10_MASTER_SKELETON_AND_NATIVE_ARTICULATION_SMOKE"
        ),
    }
    write_json_once(lock_path, lock)
    print(json.dumps(lock, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
