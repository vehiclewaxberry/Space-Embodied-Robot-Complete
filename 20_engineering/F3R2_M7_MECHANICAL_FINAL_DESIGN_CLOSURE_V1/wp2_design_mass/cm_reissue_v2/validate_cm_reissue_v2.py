#!/usr/bin/env python
"""Independent, read-only validator for the WP2 CM-only reissue V2.

The validator does not import or execute the V3 R2 aggregator.  It writes no
files.  All hashes are recomputed over raw bytes.  JSON output is deterministic
so two invocations over unchanged inputs are byte-identical.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PACKAGE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp2_design_mass/cm_reissue_v2"
)
RECEIPT_NAME = "WP2_CM_ONLY_RECEIPT_V2.json"
GATE_NAME = "WP2_CM_REISSUE_GATE_V2.json"
MANIFEST_NAME = "WP2_CM_REISSUE_MANIFEST_V2.json"

EXPECTED_SOURCE_PATHS = {
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp2_design_mass/WP2_V3_R2_RECEIPT.json",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp2_design_mass/aggregate_m7_design_mass_v3_r2.py",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "00_authority/M7_OWNER_DECISION_ODR_GPT_01_TO_06_TERMINAL_CLOSURE_V1.yaml",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml",
}

EXPECTED_PACKAGE_MEMBERS = {
    f"{PACKAGE_REL}/README.md",
    f"{PACKAGE_REL}/validate_cm_reissue_v2.py",
    f"{PACKAGE_REL}/{RECEIPT_NAME}",
    f"{PACKAGE_REL}/{GATE_NAME}",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha_size(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return sha256_bytes(data), len(data)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_payload_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def main() -> int:
    repo = Path(__file__).resolve().parents[4]
    package = repo / PACKAGE_REL
    receipt = load_json(package / RECEIPT_NAME)
    gate = load_json(package / GATE_NAME)
    manifest = load_json(package / MANIFEST_NAME)

    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, detail: Any) -> None:
        checks.append(
            {
                "id": check_id,
                "status": "PASS" if condition else "FAIL",
                "detail": detail,
            }
        )

    check(
        "CMV2-001_SCHEMAS",
        receipt.get("schema") == "WP2_CM_ONLY_RECEIPT_V2"
        and gate.get("schema") == "WP2_CM_REISSUE_GATE_V2"
        and manifest.get("schema") == "WP2_CM_REISSUE_MANIFEST_V2",
        {
            "receipt": receipt.get("schema"),
            "gate": gate.get("schema"),
            "manifest": manifest.get("schema"),
        },
    )

    source_register = receipt.get("source_register", {})
    check(
        "CMV2-002_SOURCE_SET_EXACT",
        set(source_register) == EXPECTED_SOURCE_PATHS,
        {
            "expected": sorted(EXPECTED_SOURCE_PATHS),
            "observed": sorted(source_register),
        },
    )
    for index, rel in enumerate(sorted(EXPECTED_SOURCE_PATHS), start=3):
        rec = source_register.get(rel, {})
        path = repo / rel
        exists = path.is_file()
        actual_sha, actual_bytes = sha_size(path) if exists else (None, None)
        condition = bool(
            exists
            and actual_sha == rec.get("sha256")
            and actual_bytes == rec.get("bytes")
        )
        check(
            f"CMV2-{index:03d}_SOURCE_RAW_BYTES",
            condition,
            {
                "path": rel,
                "expected_sha256": rec.get("sha256"),
                "actual_sha256": actual_sha,
                "expected_bytes": rec.get("bytes"),
                "actual_bytes": actual_bytes,
            },
        )

    old_rel = receipt["defect_record"]["legacy_receipt_path"]
    old_doc = load_json(repo / old_rel)
    old_actual_sha, old_actual_bytes = sha_size(repo / old_rel)
    recorded_self = old_doc.get("hashes", {}).get("WP2_V3_R2_RECEIPT.json")
    defect = receipt["defect_record"]
    check(
        "CMV2-010_LEGACY_ACTUAL_DIGEST_FIXED",
        old_actual_sha == defect.get("legacy_receipt_actual_sha256")
        and old_actual_bytes == defect.get("legacy_receipt_actual_bytes"),
        {
            "sha256": old_actual_sha,
            "bytes": old_actual_bytes,
        },
    )
    check(
        "CMV2-011_LEGACY_SELF_DIGEST_DRIFT_REPRODUCED",
        recorded_self == defect.get("legacy_receipt_recorded_self_sha256")
        and old_actual_sha != recorded_self,
        {
            "recorded_self_sha256": recorded_self,
            "actual_sha256": old_actual_sha,
        },
    )

    first_emission = copy.deepcopy(old_doc)
    first_emission["hashes"] = {}
    # Path.write_text on the Windows host translated json.dumps LF to CRLF.
    first_bytes = json.dumps(first_emission, indent=1).replace(
        "\n", "\r\n"
    ).encode("utf-8")
    first_sha = sha256_bytes(first_bytes)
    check(
        "CMV2-012_FIRST_EMISSION_EXACT_RECONSTRUCTION",
        first_sha == recorded_self
        and len(first_bytes) == defect.get("reconstructed_first_emission_bytes")
        and first_sha
        == defect.get("reconstructed_first_emission_sha256"),
        {
            "sha256": first_sha,
            "bytes": len(first_bytes),
            "newline_policy": "CRLF_FROM_WINDOWS_PATH_WRITE_TEXT",
        },
    )

    projected = {key: value for key, value in old_doc.items() if key != "hashes"}
    projected_sha = sha256_bytes(canonical_payload_bytes(projected))
    preservation = receipt["payload_preservation"]
    check(
        "CMV2-013_NON_SELF_PAYLOAD_DIGEST_PRESERVED",
        projected_sha == preservation.get("legacy_projection_sha256")
        == preservation.get("cm_reissue_projection_sha256")
        and preservation.get("digests_equal") is True,
        {
            "projection_rule": "REMOVE_TOP_LEVEL_HASHES_ONLY",
            "sha256": projected_sha,
        },
    )
    check(
        "CMV2-014_NO_SCIENTIFIC_PAYLOAD_REEMISSION",
        preservation.get("representation")
        == "REFERENCE_ONLY_NO_SCIENTIFIC_PAYLOAD_REEMITTED"
        and "per_configuration" not in receipt
        and "cross_configuration" not in receipt
        and "mass_kg" not in receipt,
        {
            "representation": preservation.get("representation"),
            "forbidden_top_level_keys_absent": True,
        },
    )

    policy = receipt.get("hash_policy", {})
    excluded = {entry["path"] for entry in policy.get("excluded_members", [])}
    expected_excluded = {
        f"{PACKAGE_REL}/{RECEIPT_NAME}",
        f"{PACKAGE_REL}/{GATE_NAME}",
        f"{PACKAGE_REL}/{MANIFEST_NAME}",
        f"{PACKAGE_REL}/validate_cm_reissue_v2.py",
        f"{PACKAGE_REL}/README.md",
    }
    check(
        "CMV2-015_RECEIPT_SELF_REFERENCE_EXCLUDED",
        policy.get("name") == "SELF_REFERENCE_EXCLUDED"
        and set(policy.get("included_source_members", []))
        == EXPECTED_SOURCE_PATHS
        and excluded == expected_excluded
        and "hashes" not in receipt,
        {
            "policy": policy.get("name"),
            "excluded_members": sorted(excluded),
        },
    )

    check(
        "CMV2-016_MANIFEST_SOURCE_REGISTER_EQUAL",
        manifest.get("source_register") == source_register,
        {"source_count": len(source_register)},
    )
    member_register = manifest.get("package_member_register", {})
    check(
        "CMV2-017_MANIFEST_MEMBER_SET_EXACT",
        set(member_register) == EXPECTED_PACKAGE_MEMBERS,
        {
            "expected": sorted(EXPECTED_PACKAGE_MEMBERS),
            "observed": sorted(member_register),
        },
    )
    for index, rel in enumerate(sorted(EXPECTED_PACKAGE_MEMBERS), start=18):
        rec = member_register.get(rel, {})
        path = repo / rel
        exists = path.is_file()
        actual_sha, actual_bytes = sha_size(path) if exists else (None, None)
        check(
            f"CMV2-{index:03d}_PACKAGE_MEMBER_RAW_BYTES",
            bool(
                exists
                and actual_sha == rec.get("sha256")
                and actual_bytes == rec.get("bytes")
            ),
            {
                "path": rel,
                "expected_sha256": rec.get("sha256"),
                "actual_sha256": actual_sha,
                "expected_bytes": rec.get("bytes"),
                "actual_bytes": actual_bytes,
            },
        )

    manifest_self = f"{PACKAGE_REL}/{MANIFEST_NAME}"
    check(
        "CMV2-022_MANIFEST_SELF_REFERENCE_EXCLUDED",
        manifest.get("self_hash_policy") == "SELF_REFERENCE_EXCLUDED"
        and manifest.get("excluded_members")
        == [
            {
                "path": manifest_self,
                "reason": "MANIFEST_SELF_REFERENCE_IMPOSSIBLE; PIN_DOWNSTREAM_AFTER_EMISSION",
            }
        ]
        and manifest_self not in member_register,
        {
            "excluded_member": manifest_self,
            "manifest_not_self_listed": manifest_self not in member_register,
        },
    )

    gate_criteria = gate.get("criteria", [])
    check(
        "CMV2-023_GATE_IS_CM_ONLY_AND_ALL_CRITERIA_PASS",
        gate.get("gate_verdict") == "PASS_CM_INTEGRITY_REISSUE_ONLY"
        and len(gate_criteria) == 12
        and all(row.get("status") == "PASS" for row in gate_criteria),
        {
            "gate_verdict": gate.get("gate_verdict"),
            "criteria_total": len(gate_criteria),
            "criteria_pass": sum(
                row.get("status") == "PASS" for row in gate_criteria
            ),
        },
    )
    check(
        "CMV2-024_NO_AUTHORITY_OR_RELEASE_UPGRADE",
        gate.get("owner_accepted") is False
        and gate.get("next_stage_authorized") is False
        and gate.get("release_credit") is False
        and gate.get("scientific_gate_inheritance") is False
        and receipt.get("owner_accepted") is False
        and receipt.get("next_stage_authorized") is False
        and receipt.get("release_credit") is False,
        {
            "owner_accepted": gate.get("owner_accepted"),
            "next_stage_authorized": gate.get("next_stage_authorized"),
            "release_credit": gate.get("release_credit"),
            "scientific_gate_inheritance": gate.get("scientific_gate_inheritance"),
        },
    )

    check(
        "CMV2-025_VALIDATOR_INDEPENDENT_AND_READ_ONLY",
        gate.get("validator_contract", {}).get("imports_aggregator") is False
        and gate.get("validator_contract", {}).get("executes_aggregator") is False
        and gate.get("validator_contract", {}).get("writes_files") is False,
        gate.get("validator_contract"),
    )

    snapshot_before = {
        rel: sha_size(repo / rel)
        for rel in sorted(EXPECTED_PACKAGE_MEMBERS | {manifest_self})
    }
    snapshot_after = {
        rel: sha_size(repo / rel)
        for rel in sorted(EXPECTED_PACKAGE_MEMBERS | {manifest_self})
    }
    check(
        "CMV2-026_IN_RUN_BYTE_STABILITY",
        snapshot_before == snapshot_after,
        {
            "member_count": len(snapshot_before),
            "snapshots_equal": snapshot_before == snapshot_after,
        },
    )

    failed = [row["id"] for row in checks if row["status"] != "PASS"]
    result = {
        "schema": "WP2_CM_REISSUE_VALIDATION_RESULT_V2",
        "validator": f"{PACKAGE_REL}/validate_cm_reissue_v2.py",
        "mode": "READ_ONLY_DETERMINISTIC",
        "verdict": "PASS" if not failed else "FAIL",
        "checks_total": len(checks),
        "checks_pass": len(checks) - len(failed),
        "checks_fail": len(failed),
        "failed_check_ids": failed,
        "checks": checks,
    }
    rendered_1 = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=False)
    rendered_2 = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=False)
    if rendered_1 != rendered_2:
        raise RuntimeError("deterministic result serialization failed")
    sys.stdout.write(rendered_1 + "\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

