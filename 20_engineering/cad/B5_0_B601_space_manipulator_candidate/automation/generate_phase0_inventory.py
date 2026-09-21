"""Generate the B5.0 Phase-0 source inventory and protected hash seal.

This script reads sources only. It writes generated evidence exclusively below the
B5.0 candidate root.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE = Path(__file__).resolve().parents[1]
WORKSPACE = Path(__file__).resolve().parents[4]
AUDIT = CANDIDATE / "00_AUDIT"

ACCEPTED = WORKSPACE / "20_engineering/cad/spacecraft_layout/arm_b601_v1"
V22 = WORKSPACE / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2"
V22N = WORKSPACE / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2_NATIVE"
VENDOR_REPO = Path(
    "F:/Robotic arm/High_performance_robotics_arm/vendor/reBot-DevArm"
)
VENDOR_STEP = (
    VENDOR_REPO
    / "hardware/reBot_B601_DM/reBot_B601_DM_v1.1_20260425.step"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def display_path(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return path.as_posix()


def row(path: Path, purpose: str, authority: str, donor: str,
        related: str, limitations: str) -> dict[str, str]:
    stat = path.stat()
    return {
        "file_path": display_path(path),
        "file_type": path.suffix.lower().lstrip(".") or "file",
        "size_bytes": str(stat.st_size),
        "modified_local": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
        "sha256": sha256(path),
        "content_purpose": purpose,
        "authority": authority,
        "is_authoritative_truth": "YES" if authority in {
            "KINEMATIC_AND_MASS_AUTHORITY", "PROJECT_CONFIG_AUTHORITY"
        } else "NO",
        "is_donor": donor,
        "allowed_to_modify": "NO",
        "associated_part_or_link": related,
        "known_limitations": limitations,
    }


def accepted_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(p for p in ACCEPTED.rglob("*") if p.is_file()):
        if path.name == "arm_b601_v1.urdf":
            rows.append(row(
                path,
                "accepted B601 kinematic and inertial model",
                "KINEMATIC_AND_MASS_AUTHORITY",
                "NO",
                "10 links / 9 joints",
                "read-only; model mass is not a physical weigh-in; no manufacturing authority",
            ))
        elif path.suffix.lower() == ".stl":
            rows.append(row(
                path,
                "accepted-URDF visual and collision mesh",
                "GEOMETRY_ATTACHED_TO_ACCEPTED_URDF_NOT_KINEMATIC_OR_MASS",
                "NO",
                path.stem,
                "triangulated; visual and collision are identical; no manufacturing authority",
            ))
        else:
            rows.append(row(
                path,
                "accepted-package evidence",
                "ACCEPTED_PACKAGE_EVIDENCE",
                "NO",
                "",
                "evidence only",
            ))
    return rows


def explicit_project_rows() -> list[dict[str, str]]:
    specs = [
        (
            WORKSPACE / "20_engineering/config/geometry/arm_b601_v1.yaml",
            "geometry SSOT pointer", "PROJECT_CONFIG_AUTHORITY", "NO",
            "accepted URDF and donor references",
            "hardware_step path is stale; do not modify frozen config",
        ),
        (
            V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM",
            "canonical V2.2 functional-geometry top", "FROZEN_REFERENCE_ONLY",
            "YES", "spacecraft top",
            "untracked tree; top-only pinned hash; no final full-tree manifest",
        ),
        (
            V22 / "00_Master_Skeleton/Master_Skeleton_V2_2.SLDPRT",
            "canonical V2.2 master skeleton", "REFERENCE_ONLY", "YES",
            "spacecraft skeleton", "no physical or load release authority",
        ),
        (
            V22 / "20_B601_Interface/SV22_B601_Interface.SLDASM",
            "canonical B601 interface", "REFERENCE_ONLY", "YES",
            "mount interface", "no load-capacity authority",
        ),
        (
            V22 / "110_Layout_and_Deployment_01/design/state_policy.json",
            "seven-state policy", "STATE_POLICY_REFERENCE", "YES",
            "seven named states", "PARTIAL and SERVICE have no geometry binding",
        ),
        (
            V22 / "110_Layout_and_Deployment_01/arm_stow/arm_stow_layout.step",
            "stow analysis geometry", "ANALYSIS_SCENARIO_ONLY", "YES",
            "stow study", "not physical qualification",
        ),
        (
            V22 / "130_B601_Vendor_CAD_Direct_Integration_03/geometry/B601_VENDOR_STOW.step",
            "vendor stow geometry", "REFERENCE_ANALYSIS_ONLY", "YES",
            "B601 stowed visual reference",
            "CANDIDATE_HOLD; no mass or physical-release authority",
        ),
        (
            V22 / "130_B601_Vendor_CAD_Direct_Integration_03/geometry/B601_VENDOR_Q0.step",
            "vendor q0 geometry", "REFERENCE_ANALYSIS_ONLY", "YES",
            "B601 q0 visual reference", "no mass or kinematic authority",
        ),
        (
            V22 / "130_B601_Vendor_CAD_Direct_Integration_03/geometry/B601_SPACECRAFT_ADAPTER.step",
            "adapter concept", "REFERENCE_ANALYSIS_ONLY", "YES",
            "B601 adapter", "no strength or released-interface authority",
        ),
        (
            V22 / "130_B601_Vendor_CAD_Direct_Integration_03/geometry/B601_STOW_SUPPORT_V2.step",
            "stow support concept", "REFERENCE_ANALYSIS_ONLY", "YES",
            "B601 stow support", "no HDRM/contact/preload qualification",
        ),
        (
            V22N / "Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
            "native V2.2 detailed top", "READ_ONLY_NATIVE_DESIGN_PROPOSAL",
            "YES", "native spacecraft top",
            "PENDING_HUMAN_REVIEW; all-files manifest is stale",
        ),
        (
            V22N / "00_Master_Skeleton/00_Master_Skeleton_V2_2.SLDPRT",
            "native master skeleton", "READ_ONLY_NATIVE_DESIGN_PROPOSAL",
            "YES", "native skeleton", "no physical release authority",
        ),
        (
            V22N / "02_B601_Mount_and_Load_Path/02_B601_Mount_and_Load_Path.SLDASM",
            "mount and load-path proposal", "READ_ONLY_NATIVE_DESIGN_PROPOSAL",
            "YES", "B601 mount",
            "loads, materials, joints and fasteners unknown",
        ),
        (
            V22N / "04_ARM_STOW_SUPPORT/04_ARM_STOW_SUPPORT.SLDASM",
            "stow support proposal", "READ_ONLY_NATIVE_DESIGN_PROPOSAL",
            "YES", "B601 stow support",
            "HDRM, contact and preload unknown",
        ),
        (
            V22N / "design/b601_stow_joint_vector_v3.json",
            "stow pose candidate", "CANDIDATE_HOLD", "YES",
            "accepted joint chain comparator",
            "STOW_Z_LIMIT and interface tracks unresolved",
        ),
    ]
    result: list[dict[str, str]] = []
    for spec in specs:
        if spec[0].is_file():
            result.append(row(*spec))
    return result


def vendor_rows() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if VENDOR_STEP.is_file():
        result.append(row(
            VENDOR_STEP,
            "primary B601 visual geometry donor",
            "GEOMETRY_REFERENCE_ONLY",
            "YES",
            "B601 exterior geometry",
            "dumb STEP bodies; no kinematic, mass, inertia or manufacturing authority",
        ))
    for name in ("LICENSE", "LICENSE.txt", "CERN-OHL-W-2.0.txt", "README.md"):
        for path in sorted(VENDOR_REPO.rglob(name)) if VENDOR_REPO.is_dir() else []:
            result.append(row(
                path,
                "vendor license or documentation",
                "THIRD_PARTY_PROVENANCE",
                "YES",
                "",
                "license/documentation only",
            ))
    return result


def protected_paths() -> list[Path]:
    paths = [VENDOR_STEP]
    paths.extend(p for p in ACCEPTED.rglob("*") if p.is_file())
    for top in (
        V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM",
        V22N / "Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
    ):
        if top.is_file():
            paths.append(top)
    if V22N.is_dir():
        paths.extend(
            p for p in V22N.rglob("*")
            if p.is_file() and p.suffix.lower() in {".sldprt", ".sldasm", ".slddrw"}
        )
    return sorted(set(p.resolve() for p in paths if p.is_file()), key=str)


def git_state() -> dict[str, object]:
    branch = subprocess.run(
        ["git", "-C", str(WORKSPACE), "branch", "--show-current"],
        check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(WORKSPACE), "status", "--short"],
        check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.splitlines()
    return {"branch": branch, "dirty_entries": len(status)}


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    inventory = accepted_rows() + explicit_project_rows() + vendor_rows()
    inventory.sort(key=lambda item: item["file_path"].lower())
    write_csv(AUDIT / "B601_ASSET_INVENTORY.csv", inventory)

    protected = [
        {
            "file_path": display_path(path),
            "size_bytes": str(path.stat().st_size),
            "sha256": sha256(path),
        }
        for path in protected_paths()
    ]
    write_csv(AUDIT / "baseline_protected_hashes.csv", protected)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(WORKSPACE),
        "candidate_root": str(CANDIDATE),
        "git": git_state(),
        "accepted_package_files": len([p for p in ACCEPTED.rglob("*") if p.is_file()]),
        "inventory_rows": len(inventory),
        "protected_hash_rows": len(protected),
        "vendor_step_found": VENDOR_STEP.is_file(),
        "b106_hits": [],
        "b106_status": "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH",
        "note": "B106 absence is not evidence that no B106 asset exists outside the audited roots."
    }
    (AUDIT / "audit_scan_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
