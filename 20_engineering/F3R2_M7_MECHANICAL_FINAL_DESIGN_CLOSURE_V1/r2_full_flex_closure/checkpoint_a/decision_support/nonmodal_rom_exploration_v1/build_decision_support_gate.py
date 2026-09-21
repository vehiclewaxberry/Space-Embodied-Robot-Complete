#!/usr/bin/env python3
"""Build the bounded decision-support gate and an acyclic SHA-256 manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[5]
RESULT = HERE / "R2_NONMODAL_ROM_EXPLORATION_RESULTS_V1.json"
INDEPENDENT = HERE / "INDEPENDENT_RECOMPUTE_V1.json"
README = HERE / "README.md"
PRIMARY_SCRIPT = HERE / "recompute_nonmodal_rom_exploration.py"
INDEPENDENT_SCRIPT = HERE / "independent_recompute.py"
THIS_SCRIPT = HERE / "build_decision_support_gate.py"
TEST_SCRIPT = HERE / "tests/test_package.py"
GATE = HERE / "R2_NONMODAL_ROM_EXPLORATION_DECISION_SUPPORT_GATE_V1.json"
MANIFEST = HERE / "NONMODAL_ROM_EXPLORATION_SHA256_MANIFEST_V1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"DECISION_SUPPORT_GATE_FAIL_CLOSED:{message}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def criterion(identifier: str, name: str, passed: bool, evidence: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "evidence": evidence,
    }


def main() -> None:
    for path in (
        RESULT,
        INDEPENDENT,
        README,
        PRIMARY_SCRIPT,
        INDEPENDENT_SCRIPT,
        THIS_SCRIPT,
        TEST_SCRIPT,
    ):
        require(path.is_file(), f"missing package artifact:{rel(path)}")

    result = json.loads(RESULT.read_text(encoding="utf-8"))
    independent = json.loads(INDEPENDENT.read_text(encoding="utf-8"))
    headline = result["headline_findings"]
    governance = result["governance"]

    source_lock = all(
        item["match"] for item in result["source_hashes"].values()
    )
    five = headline["best_tested_5d_weighted_pod"]["global_max_relative_error"]
    nine = headline["hybrid_9d_3b_plus_6t_pod"]["global_max_relative_error"]
    ten = headline["hybrid_10d_3b_plus_7t_pod"]["global_max_relative_error"]
    dense = headline["hybrid_10d_5ms_dense_torsion_peak"][
        "global_dense_relative_peak_error"
    ]
    all_governance_false = all(
        governance[key] is False
        for key in (
            "owner_accepted",
            "owner_acceptance",
            "release_credit",
            "component_gate_pass",
            "round4_generated",
            "e15_inherited",
            "e15_status_changed",
            "next_stage_authorized",
            "flight_qualified",
            "terminal_release",
        )
    )
    limitations = " ".join(result["limitations_and_nonclaims"])
    no_global_claim = (
        "do not prove a global minimum" in limitations
        and "not a theorem" in limitations
    )
    leakage_disclosed = (
        result["validation_status"]["rank_and_method_selected_after_exploration"]
        and result["validation_status"]["blind_validation"] is False
    )

    criteria = [
        criterion("DS01", "all frozen sources hash-lock", source_lock, "all source match flags true"),
        criterion("DS02", "best tested 5D family remains above 1%", five > 0.01, f"{100*five:.9f}%"),
        criterion("DS03", "hybrid 9D negative control remains above 1%", nine > 0.01, f"{100*nine:.9f}%"),
        criterion("DS04", "hybrid 10D internal discrete score is faithfully below 1%", ten <= 0.01, f"{100*ten:.9f}%"),
        criterion("DS05", "5 ms dense torsion audit is faithfully below 1%", dense <= 0.01, f"{100*dense:.9f}%"),
        criterion(
            "DS06",
            "independent key-result recompute",
            independent["all_comparisons_pass"] is True,
            independent["verdict"],
        ),
        criterion("DS07", "training leakage and non-blind status disclosed", leakage_disclosed, "rank/method post-selected; blind_validation=false"),
        criterion("DS08", "no arbitrary-Grassmann global impossibility claim", no_global_claim, "finite tested families only"),
        criterion(
            "DS09",
            "negative controls operate",
            all(
                item["negative_control_pass"]
                for item in result["negative_controls"].values()
            )
            and independent["negative_control"]["negative_control_pass"],
            "rank-regression and synthetic hash mismatch controls pass",
        ),
        criterion("DS10", "all prohibited authorizations remain false", all_governance_false, "Owner/release/e15/next-stage and related flags false"),
    ]
    evidence_integrity_pass = all(item["passed"] for item in criteria)
    require(evidence_integrity_pass, "one or more evidence-integrity criteria failed")

    package_hashes_before_gate = {
        rel(path): {
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in (
            README,
            PRIMARY_SCRIPT,
            INDEPENDENT_SCRIPT,
            THIS_SCRIPT,
            TEST_SCRIPT,
            RESULT,
            INDEPENDENT,
        )
    }
    gate = {
        "schema": "R2_NONMODAL_ROM_EXPLORATION_DECISION_SUPPORT_GATE_V1",
        "evidence_class": "EXPLORATORY_DECISION_SUPPORT_ONLY",
        "decision_support_integrity_status": "PASS_BOUNDED_EVIDENCE_INTEGRITY_ONLY",
        "technical_verdict": (
            "EXPLORATORY_10D_CANDIDATE_IDENTIFIED_WITH_THIN_INTERNAL_MARGIN__"
            "NOT_BLIND_VALIDATION__NO_OWNER_ACCEPTANCE__NO_RELEASE_CREDIT"
        ),
        "criteria": criteria,
        "criteria_passed": sum(item["passed"] for item in criteria),
        "criteria_total": len(criteria),
        "decision_support_evidence_integrity_pass": evidence_integrity_pass,
        "headline_metrics": {
            "best_tested_5d_relative_error": five,
            "hybrid_9d_relative_error": nine,
            "hybrid_10d_relative_error": ten,
            "hybrid_10d_dense_5ms_torsion_relative_error": dense,
            "relative_limit": 0.01,
        },
        "artifact_hashes_without_manifest": package_hashes_before_gate,
        "authorizations": {
            "owner_accepted": False,
            "owner_acceptance": False,
            "release_credit": False,
            "component_gate_pass": False,
            "round4_generated": False,
            "e15_inherited": False,
            "e15_status_changed": False,
            "next_stage_authorized": False,
            "flight_qualified": False,
            "terminal_release": False,
        },
        "unchanged_external_gates": {
            "round3_mutated": False,
            "e22_mutated": False,
            "checkpoint_a_mutated": False,
            "terminal_pack_mutated": False,
        },
        "required_next_evidence_before_any_rom_contract_change": [
            "freeze candidate basis, rank, construction, and hashes before new scoring",
            "blind new base-delta-twist directions",
            "blind LOW/HIGH stiffness corners",
            "blind off-grid contact windows",
            "Owner decision on the existing 3-5 modes-per-wing contract",
            "e15 recertification remains separate and mandatory",
        ],
    }
    write_json(GATE, gate)

    manifest_entries = []
    external_roles = {
        path: "FROZEN_EXTERNAL_SOURCE"
        for path in (
            HERE.parents[2] / "round3_hf_rom_v2/R2_HF_ROM_NUMERICAL_DATA_V2.npz",
            HERE.parents[2] / "round3_hf_rom_v2/R2_FIVE_MODE_ROM_V2.json",
            HERE.parents[1] / "red_team/recompute_rom5_dimension_falsifier.py",
            HERE.parents[1] / "red_team/ROM5_DIMENSION_FALSIFIER_V1.json",
            HERE.parent / "recompute_multicontact_rom_dimension.py",
            HERE.parent / "MULTICONTACT_ROM_DIMENSION_DECISION_SUPPORT_V1.json",
        )
    }
    package_roles = {
        README: "PACKAGE_DOCUMENTATION",
        PRIMARY_SCRIPT: "PRIMARY_RECOMPUTE_SOURCE",
        INDEPENDENT_SCRIPT: "INDEPENDENT_RECOMPUTE_SOURCE",
        THIS_SCRIPT: "GATE_AND_MANIFEST_BUILDER_SOURCE",
        TEST_SCRIPT: "AUTOMATED_AUDIT_SOURCE",
        RESULT: "PRIMARY_EXPLORATORY_RESULT",
        INDEPENDENT: "INDEPENDENT_RECOMPUTE_RESULT",
        GATE: "DECISION_SUPPORT_INTEGRITY_GATE",
    }
    for path, role in sorted(
        {**external_roles, **package_roles}.items(), key=lambda item: rel(item[0])
    ):
        require(path.is_file(), f"manifest input missing:{rel(path)}")
        manifest_entries.append(
            {
                "path": rel(path),
                "role": role,
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    manifest = {
        "schema": "NONMODAL_ROM_EXPLORATION_SHA256_MANIFEST_V1",
        "evidence_class": "EXPLORATORY_DECISION_SUPPORT_ONLY",
        "hash_algorithm": "SHA-256",
        "entries": manifest_entries,
        "entry_count": len(manifest_entries),
        "acyclicity": {
            "manifest_self_included": False,
            "manifest_path": rel(MANIFEST),
            "manifest_hash_referenced_by_gate": False,
            "manifest_hash_referenced_by_results": False,
            "rule": "manifest hashes all controlled inputs/outputs except itself; no hashed artifact depends on the manifest hash",
        },
        "owner_accepted": False,
        "release_credit": False,
        "component_gate_pass": False,
        "e15_inherited": False,
        "next_stage_authorized": False,
    }
    write_json(MANIFEST, manifest)
    print(
        json.dumps(
            {
                "decision_support_integrity_status": gate[
                    "decision_support_integrity_status"
                ],
                "criteria": f"{gate['criteria_passed']}/{gate['criteria_total']}",
                "gate_sha256": digest(GATE),
                "manifest_sha256_external_receipt_only": digest(MANIFEST),
                "manifest_self_included": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

