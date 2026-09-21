from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
REPO = CANDIDATE.parents[2]

PARENT_PHASE0 = (
    REPO
    / "20_engineering/cad/"
    "B5_1R1_B601_interface_collision_and_articulation_rework_candidate"
)
PARENT_B51 = REPO / "20_engineering/cad/B5_1_B601_interface_closure_candidate"
CANONICAL_SOURCE = REPO / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2_NATIVE"
VENDOR_SOURCE = Path(
    r"F:\Robotic arm\High_performance_robotics_arm\vendor\reBot-DevArm"
    r"\hardware\reBot_B601_DM\reBot_B601_DM_v1.1_20260425.step"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def check_file(
    *,
    object_id: str,
    source: Path,
    expected_sha256: str,
    expected_bytes: int | None = None,
    copy: Path | None = None,
) -> dict:
    row = {
        "id": object_id,
        "source_path": str(source),
        "expected_sha256": expected_sha256.upper(),
        "expected_bytes": expected_bytes,
        "source_exists": source.is_file(),
    }
    if source.is_file():
        row["source_bytes"] = source.stat().st_size
        row["source_sha256"] = sha256(source)
    else:
        row["source_bytes"] = -1
        row["source_sha256"] = "MISSING"

    row["source_match"] = (
        row["source_sha256"] == row["expected_sha256"]
        and (
            expected_bytes is None
            or row["source_bytes"] == expected_bytes
        )
    )

    if copy is not None:
        row["copy_path"] = str(copy)
        row["copy_exists"] = copy.is_file()
        if copy.is_file():
            row["copy_bytes"] = copy.stat().st_size
            row["copy_sha256"] = sha256(copy)
        else:
            row["copy_bytes"] = -1
            row["copy_sha256"] = "MISSING"
        row["copy_match"] = (
            row["copy_sha256"] == row["expected_sha256"]
            and (
                expected_bytes is None
                or row["copy_bytes"] == expected_bytes
            )
        )
    else:
        row["copy_match"] = True

    row["match"] = row["source_match"] and row["copy_match"]
    return row


def verify_parent_lock() -> dict:
    lock_path = PARENT_PHASE0 / "00_CONTROL/B51R1_PARENT_INPUT_LOCK.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    rows = []
    copy_root = CANDIDATE / "00_BASELINE/PARENT_LOCKED_INPUTS"
    for entry in lock["locked_inputs"]:
        source = REPO / Path(entry["path"])
        copy = copy_root / entry["id"] / source.name
        rows.append(
            check_file(
                object_id=entry["id"],
                source=source,
                expected_sha256=entry["sha256"],
                expected_bytes=int(entry["bytes"]),
                copy=copy,
            )
        )
    return {
        "lock_path": str(lock_path),
        "lock_sha256": sha256(lock_path),
        "declared": len(lock["locked_inputs"]),
        "checked": len(rows),
        "matched": sum(row["match"] for row in rows),
        "mismatches": [row for row in rows if not row["match"]],
        "rows": rows,
    }


def verify_canonical_tree() -> dict:
    manifest_path = (
        REPO
        / "20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/"
        "baseline_freeze_manifest.yaml"
    )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    copy_root = CANDIDATE / "00_BASELINE/V2_2_NATIVE_CANONICAL_108_FILE_COPY"
    rows = []
    for rel, meta in manifest["files"].items():
        rows.append(
            check_file(
                object_id=f"V22::{rel}",
                source=CANONICAL_SOURCE / rel,
                expected_sha256=str(meta["sha256"]),
                expected_bytes=int(meta["bytes"]),
                copy=copy_root / rel,
            )
        )
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "canonical_top": manifest["canonical_top"],
        "canonical_top_sha256": str(manifest["canonical_top_sha256"]).upper(),
        "declared": int(manifest["file_count"]),
        "checked": len(rows),
        "matched": sum(row["match"] for row in rows),
        "mismatches": [row for row in rows if not row["match"]],
        "rows": rows,
    }


def verify_key_authorities() -> list[dict]:
    baseline = CANDIDATE / "00_BASELINE"
    progress = (
        REPO
        / "10_research/mechanical_design_progress_gallery_20260729/"
        "MECHANICAL_DESIGN_PROGRESS_GALLERY_20260729.md"
    )
    return [
        check_file(
            object_id="ACCEPTED_URDF",
            source=REPO / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
            expected_sha256="1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
            expected_bytes=11321,
            copy=baseline / "AUTHORITIES/accepted_urdf/arm_b601_v1.urdf",
        ),
        check_file(
            object_id="VENDOR_STEP_GEOMETRY_ONLY",
            source=VENDOR_SOURCE,
            expected_sha256="87A0537D1AFD50C04FC441FDE11DD4F2EBBB368FE27F6C10FDA8567BE696D968",
            expected_bytes=35114019,
            copy=baseline
            / "AUTHORITIES/vendor_geometry/reBot_B601_DM_v1.1_20260425.step",
        ),
        check_file(
            object_id="B51_PARENT_GATE",
            source=PARENT_B51 / "07_VERIFICATION/B51_GATE.json",
            expected_sha256="DD4286A1826AD6F47AEF81C3685A047786430A6F5BB31D797C206A5A2A91F8D0",
            expected_bytes=8731,
            copy=baseline / "GATES/B51_GATE.json",
        ),
        check_file(
            object_id="B51R1_PHASE0_GATE",
            source=PARENT_PHASE0 / "07_VERIFICATION/B51R1_GATE.json",
            expected_sha256="4E71E5871E3D5CF592EA3FF46C5E3395E5161106BEEBBEAD5908BF6B572ED31C",
            expected_bytes=7333,
            copy=baseline / "GATES/B51R1_PHASE0_GATE.json",
        ),
        check_file(
            object_id="MECHANICAL_PROGRESS_SNAPSHOT",
            source=progress,
            expected_sha256="179C603716B028593D8F3CA0D99A897540C2BA39BD48D66BE3D15BCD5271EBD8",
            expected_bytes=9935,
            copy=baseline
            / "PROGRESS_SNAPSHOT/MECHANICAL_DESIGN_PROGRESS_GALLERY_20260729.md",
        ),
    ]


def verify_authorization() -> dict:
    auth_root = CANDIDATE / "00_BASELINE/AUTHORIZATION_PACKAGE"
    auth_path = auth_root / "B51R1_PHASE1_AUTHORIZATION.yaml"
    auth = yaml.safe_load(auth_path.read_text(encoding="utf-8"))
    package_copy = auth_root / "B51R1_PHASE1_START_PACKAGE.zip"
    # Root duplicate retired on 2026-09-06; the retained package is byte-identical.
    package_source = auth_root / "B51R1_PHASE1_START_PACKAGE.zip"
    # Pin the original B51R1_PHASE1_BASELINE_LOCK.json package hash so that
    # the merged source/copy location cannot pass by comparing a file to itself.
    expected_package_sha256 = "45ADF43622D00BD380BF2002F254801DFC65928886DCC359E893C73D146FF6D6"
    package_source_sha256 = sha256(package_source)
    package_copy_sha256 = sha256(package_copy)
    return {
        "authorization_path": str(auth_path),
        "authorization_sha256": sha256(auth_path),
        "authorization_status": auth["authorization_status"],
        "authorized_by": auth["authorized_by"],
        "authorization_date": str(auth["authorization_date"]),
        "h9_status": auth["truth_lock"]["h9_status"],
        "package_source_sha256": package_source_sha256,
        "package_copy_sha256": package_copy_sha256,
        "package_copy_match": (
            package_source_sha256 == package_copy_sha256 == expected_package_sha256
        ),
        "fail_closed_triggers": auth["fail_closed_triggers"],
    }


def main() -> None:
    parent = verify_parent_lock()
    canonical = verify_canonical_tree()
    authorities = verify_key_authorities()
    authorization = verify_authorization()

    authority_mismatches = [row for row in authorities if not row["match"]]
    pass_hashes = (
        parent["matched"] == parent["declared"]
        and canonical["matched"] == canonical["declared"]
        and not authority_mismatches
        and authorization["package_copy_match"]
    )

    result = {
        "schema": "SER_B51R1_PHASE1_BASELINE_LOCK_V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": "COMP-PROT-03-A4-B5.1R1-PHASE1",
        "authorization_gate": (
            "COMP-PROT-03-A4-B5.1R1-PHASE1-"
            "MASTER-SKELETON-V2-AND-NATIVE-REWORK-AUTHORIZATION"
        ),
        "status": (
            "PASS_HASH_AND_COPY_LOCK_REFERENCE_CONTAINMENT_PENDING"
            if pass_hashes
            else "FAIL_BASELINE_DRIFT_OR_COPY_MISMATCH"
        ),
        "authorization": authorization,
        "parent_21_input_lock": parent,
        "canonical_v22_108_file_lock": canonical,
        "key_authorities": authorities,
        "summary": {
            "parent_inputs": f"{parent['matched']}/{parent['declared']}",
            "canonical_files": f"{canonical['matched']}/{canonical['declared']}",
            "key_authorities": (
                f"{len(authorities) - len(authority_mismatches)}/{len(authorities)}"
            ),
            "hash_or_copy_mismatches": (
                len(parent["mismatches"])
                + len(canonical["mismatches"])
                + len(authority_mismatches)
                + (0 if authorization["package_copy_match"] else 1)
            ),
        },
        "reference_containment": "PENDING_COLD_REOPEN_AUDIT",
        "claim_limits": [
            "SOURCE_HASH_AND_ISOLATED_COPY_LOCK_ONLY",
            "NOT_DURABLE_DATUM_PASS",
            "NOT_NATIVE_CAD_ACCEPTANCE",
            "NOT_H10_OR_T005_CLOSURE",
            "NOT_MANUFACTURING_LAUNCH_OR_FLIGHT_AUTHORITY",
        ],
    }

    output = HERE / "B51R1_PHASE1_BASELINE_LOCK.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "summary": result["summary"],
            },
            ensure_ascii=False,
        )
    )
    if not pass_hashes:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

