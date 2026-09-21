#!/usr/bin/env python3
"""Atomically quarantine the invalid pre-R2 solar-array candidate.

This tool is deliberately SolidWorks-independent.  It verifies every source
byte against the audited SHA-256 set, writes a byte-preserving ZIP snapshot,
moves only the enumerated files, verifies the relocated copies, and rolls the
moves back if any step fails.  No file is deleted or overwritten.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
QUARANTINE_ID = "V5_SOLAR_ARRAY_INVALID_CANDIDATE_20260812T162256.8949918Z"
QUARANTINE_ROOT = RUN_ROOT / "13_validation" / "quarantine" / QUARANTINE_ID
RELOCATED_ROOT = QUARANTINE_ROOT / "relocated"
ARCHIVE = QUARANTINE_ROOT / "original_bytes.zip"
RECEIPT = QUARANTINE_ROOT / "V5_SOLAR_ARRAY_INVALID_CANDIDATE_QUARANTINE_RECEIPT.json"

EXPECTED = {
    "01_native_parts/solar_array/SOLAR_DEPLOY_STOP_L_H1.SLDPRT": "CBBE54B8674A039394B426BCDF38EE8E0621BFE688A967BF4407C95C1BBA6EAA",
    "01_native_parts/solar_array/SOLAR_DEPLOY_STOP_L_H2.SLDPRT": "FE0FFC8611C45E071F48FBCF9582207AE7CB52D0DDE0D6873355E5E47B8537DC",
    "01_native_parts/solar_array/SOLAR_DEPLOY_STOP_R_H1.SLDPRT": "8AEB6BF0031AE52E1A02611CCB358F57243A5354BBDE576CEC1C619897AD237B",
    "01_native_parts/solar_array/SOLAR_DEPLOY_STOP_R_H2.SLDPRT": "EB5D22890E66A6BFA7D89914FA53EF7ED170335941107C2EA9BF991EBA608EA4",
    "01_native_parts/solar_array/SOLAR_HARNESS_EXIT_L.SLDPRT": "AD9B92F4B3BE619D392DEA5215CA9C80E3565779F494CF32A0EFEAC1BAF9C662",
    "01_native_parts/solar_array/SOLAR_HARNESS_EXIT_R.SLDPRT": "C937A5D52B22895B451D9601C17624EFC43A608D008BBCF7476CB5E6126F54A8",
    "01_native_parts/solar_array/SOLAR_PANEL_L1.SLDPRT": "12E9FC7AFDBB24B3E1119B0F329F8C9E9A64BB181263E10ECA58C9D7F54E8E76",
    "01_native_parts/solar_array/SOLAR_PANEL_L2.SLDPRT": "E00956F0CF9D5CF8F64B83BB8F6B04DBDCD36D24F3C6B1C1D1F8FCC0D46523E5",
    "01_native_parts/solar_array/SOLAR_PANEL_L3.SLDPRT": "F168F3614AEA21BD8EB419F3A493CCC12DE3748AB0DCCE6D6DF5CB13DF544B0A",
    "01_native_parts/solar_array/SOLAR_PANEL_R1.SLDPRT": "D03948C83FD752A227B5444A4914ADF42A587C9F135D820F63357E3E4669FAE4",
    "01_native_parts/solar_array/SOLAR_PANEL_R2.SLDPRT": "28599E524965587D2E98DC37157D94FCE3620E988F59F59B99A597D2BC4802A3",
    "01_native_parts/solar_array/SOLAR_PANEL_R3.SLDPRT": "97A9AA96F9D418D30D3408D3B28FC6FA8446059C3A54B51C497095195FC06C33",
    "01_native_parts/solar_array/SOLAR_STOW_PAD_L.SLDPRT": "F01F0997225935E03C8321906F811F67FC347DDE27C34685F61BA6A31464E94C",
    "01_native_parts/solar_array/SOLAR_STOW_PAD_R.SLDPRT": "DF4ED1DBAAF88F75D19937D9F75CAB89235A5D078C2783166B73889B247C1C29",
    "02_native_subassemblies/L_SOLAR_ARRAY.SLDASM": "DCC53DC750316A43770A2FDECBDF0614FC432C649E18D03FE8E26943312C50CA",
    "02_native_subassemblies/R_SOLAR_ARRAY.SLDASM": "74C65E00B2DA17527DD56CFDBFD94FC18E318F9B737888B853F9FBC816ECF127",
    "04_configurations/V5_SOLAR_STATE_REGISTER.csv": "EA09A55A8845DF92EFDC7C55A20BB884306BC4401AC201A269302C9900457F05",
    "99_tools/V5_FREEZE_MULTI_PANEL_SOLAR_ARRAY.py": "F0D00D1787405630C0FB7C575CB02564A37A7652C9375CADFD77B35C1332D9AB",
}

INVALIDATING_EVIDENCE = {
    "interface_requirements": "00_authority/SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md",
    "freeze_receipt": "13_validation/V5_SOLAR_ARRAY_INTERFACE_REQUIREMENTS_FREEZE_R2.json",
    "historical_completion_receipt": "13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fact(path: Path) -> dict:
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json_once(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    resolved_root = RUN_ROOT.resolve()
    if not resolved_root.is_dir() or resolved_root.name != "F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE":
        raise RuntimeError(f"unexpected run root: {resolved_root}")
    if QUARANTINE_ROOT.exists():
        raise FileExistsError(f"quarantine target already exists: {QUARANTINE_ROOT}")

    pre = []
    for relative, expected_hash in EXPECTED.items():
        source = (RUN_ROOT / relative).resolve()
        if resolved_root not in source.parents or not source.is_file():
            raise RuntimeError(f"source absent/outside V5 root: {source}")
        actual_hash = sha256(source)
        if actual_hash != expected_hash:
            raise RuntimeError(f"source hash drift: {relative}: {actual_hash} != {expected_hash}")
        destination = (RELOCATED_ROOT / relative).resolve()
        if QUARANTINE_ROOT.resolve() not in destination.parents or destination.exists():
            raise RuntimeError(f"unsafe/existing quarantine destination: {destination}")
        pre.append({"relative_path": relative, **fact(source), "expected_sha256": expected_hash})

    evidence = {}
    for label, relative in INVALIDATING_EVIDENCE.items():
        path = RUN_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"invalidating evidence missing: {path}")
        evidence[label] = fact(path)

    QUARANTINE_ROOT.mkdir(parents=True, exist_ok=False)
    archive_temp = ARCHIVE.with_suffix(".zip.tmp")
    with zipfile.ZipFile(archive_temp, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
        for relative in sorted(EXPECTED):
            bundle.write(RUN_ROOT / relative, arcname=relative)
    with zipfile.ZipFile(archive_temp, "r") as bundle:
        names = sorted(bundle.namelist())
        if names != sorted(EXPECTED):
            raise RuntimeError("ZIP member set drift")
        for relative, expected_hash in EXPECTED.items():
            if hashlib.sha256(bundle.read(relative)).hexdigest().upper() != expected_hash:
                raise RuntimeError(f"ZIP byte verification failed: {relative}")
    os.replace(archive_temp, ARCHIVE)

    moved = []
    try:
        for relative in sorted(EXPECTED):
            source = RUN_ROOT / relative
            destination = RELOCATED_ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            moved.append((source, destination))

        post = []
        for relative, expected_hash in EXPECTED.items():
            source = RUN_ROOT / relative
            destination = RELOCATED_ROOT / relative
            if source.exists() or not destination.is_file() or sha256(destination) != expected_hash:
                raise RuntimeError(f"post-move verification failed: {relative}")
            post.append({
                "relative_path": relative,
                "canonical_source_absent": True,
                **fact(destination),
            })

        payload = {
            "schema": "F3R2_V5_SOLAR_ARRAY_INVALID_CANDIDATE_QUARANTINE_RECEIPT_V1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "quarantine_id": QUARANTINE_ID,
            "reason_codes": [
                "RIGHT_SIDE_DOUBLE_SIGN_MIRROR_FAILURE",
                "SIDE_AGNOSTIC_SINGLE_SIDE_FAILURE_MAPPING",
                "NO_NATIVE_KINEMATIC_MATES",
                "NO_TOP_LEVEL_THREE_PANEL_CLEARANCE_EVIDENCE",
            ],
            "canonical_overwrite_performed": False,
            "deletion_performed": False,
            "recoverable": True,
            "pre_move": pre,
            "archive": fact(ARCHIVE),
            "post_move": post,
            "invalidating_evidence": evidence,
            "historical_receipt_policy": "PRESERVED_IN_PLACE_AS_INVALIDATED_DIAGNOSTIC_DONOR_ONLY",
            "verdict": "V5_INVALID_SOLAR_ARRAY_CANDIDATE_QUARANTINED_PASS",
        }
        write_json_once(RECEIPT, payload)
    except Exception:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, source)
        raise

    print(json.dumps({
        "verdict": "V5_INVALID_SOLAR_ARRAY_CANDIDATE_QUARANTINED_PASS",
        "moved_files": len(EXPECTED),
        "archive": fact(ARCHIVE),
        "receipt": fact(RECEIPT),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
