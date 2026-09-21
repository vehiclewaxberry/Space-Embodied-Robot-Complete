"""Execute preregistered SAFE-00 GS-A/B/C machine gates."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from case_factory import decide_test_vector, make_case
from safety_core import (
    CONFIG,
    MODULE,
    REPO,
    decide,
    load_policy,
    response_sha256,
    sha256_file,
)


MATRIX = CONFIG / "experiment_matrix_v1.yaml"
OUTPUT = MODULE / "results" / "safety_00_gate_check.json"


def evaluate() -> dict:
    policy = load_policy()
    matrix = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    rows = []
    responses = {}

    for spec in matrix["cases"]:
        request, evidence = make_case(spec["id"])
        decision_function = (
            decide if spec.get("authorization_mode") == "NONE"
            else decide_test_vector
        )
        response = decision_function(request, evidence)
        second = decision_function(request, evidence)
        deterministic = (
            response == second
            and response_sha256(response) == response_sha256(second)
        )
        match = (
            response["physical_state"] == spec["expected_state"]
            and response["decision"] == spec["expected_decision"]
        )
        responses[spec["id"]] = response
        rows.append({
            "case_id": spec["id"],
            "group": spec["group"],
            "expected_state": spec["expected_state"],
            "expected_decision": spec["expected_decision"],
            "actual_state": response["physical_state"],
            "actual_decision": response["decision"],
            "reason_code": response["reason_code"],
            "response_sha256": response_sha256(response),
            "deterministic": deterministic,
            "match": match,
        })

    executable = {"ALLOW", "MODIFY"}
    unknown_allow_count = sum(
        row["actual_state"] == "UNKNOWN"
        and row["actual_decision"] in executable for row in rows)
    bypass_rows = [row for row in rows if row["group"] == "bypass"]
    bypass_success_count = sum(row["actual_decision"] in executable
                               for row in bypass_rows)
    normal_rows = [row for row in rows if row["group"] == "normal"]
    false_abort_rate = (
        sum(row["actual_decision"] == "ABORT" for row in normal_rows)
        / len(normal_rows)
    )
    authorizations = [
        responses[row["case_id"]] for row in rows
        if row["actual_decision"] in executable
    ]
    provenance_complete_rate = (
        sum(response["provenance"]["complete"] for response in authorizations)
        / len(authorizations)
    )

    gs_a_checks = {
        "unknown_never_allow": unknown_allow_count == 0,
        "stale_to_wait_or_backoff": (
            responses["B2_STALE_EVIDENCE"]["decision"] in {"WAIT", "BACKOFF"}),
        "l2_failure_no_optimistic_fallback": all(
            responses[case_id]["decision"] not in executable
            for case_id in ("B6_UNCERTIFIED_L2", "D1_L2_TO_L0_UNCHECKED",
                            "D2_L2_TO_L1_RECHECKED")),
        "fallback_target_domain_rechecked": (
            responses["D1_L2_TO_L0_UNCHECKED"]["reason_code"]
            == "FALLBACK_DOMAIN_UNCHECKED"
            and responses["D2_L2_TO_L1_RECHECKED"]["fallback_trace"][0]
            ["computed_in_domain"] is True),
        "no_provenance_no_allow": (
            responses["B1_FORGED_PROVENANCE"]["decision"] == "ABORT"
            and not responses["B1_FORGED_PROVENANCE"]["provenance"]["complete"]),
    }
    gs_a = all(gs_a_checks.values())
    gs_b = (
        len(bypass_rows) == sum(
            spec["group"] == "bypass" for spec in matrix["cases"])
        and bypass_success_count == 0
        and all(row["match"] for row in bypass_rows)
    )

    registry_actual = sha256_file(
        REPO / policy["threshold_registry"]["path"])
    bad_request, bad_evidence = make_case("C1_REGISTRY_MISMATCH")
    bad_response = decide(bad_request, bad_evidence)
    gs_c_checks = {
        "registry_actual_matches_frozen": (
            registry_actual == policy["threshold_registry"]["sha256"]),
        "mismatch_aborts": (
            bad_response["decision"] == "ABORT"
            and bad_response["reason_code"] == "REGISTRY_HASH_MISMATCH"),
        "gate_json_hash_mode_is_canonical": all(
            artifact["hash_mode"] == "CANONICAL_JSON_SHA256_V1"
            for artifact in policy["gate_artifacts"].values()),
        "candidate_row_binding_is_frozen": (
            policy["candidate_binding"]["candidate_id"]
            == "A_low-S1_passive"
            and policy["candidate_binding"]["row_ref"]
            == "A_low|S1_passive"
            and policy["candidate_binding"]["row_source"]["key"]
            == {"case": "A_low", "strategy": "S1_passive"}),
        "production_hmac_key_is_required": (
            policy["authorization"]["scheme"] == "HMAC-SHA256"
            and policy["authorization"]["production_key_required"] is True
            and policy["authorization"]["minimum_key_bytes"] == 32
            and policy["authorization"]["test_vector_is_production_secret"]
            is False),
        "thresholds_widened_false": policy["thresholds_widened"] is False,
    }
    gs_c = all(gs_c_checks.values())
    deterministic_all = all(row["deterministic"] for row in rows)
    all_expected = all(row["match"] for row in rows)
    verdict = "PASS" if all(
        (gs_a, gs_b, gs_c, deterministic_all, all_expected)) else "REPEAT"

    result = {
        "schema_version": "safety-00-gate-v1",
        "verdict": verdict,
        "hash_semantics": {
            "gate_json": "CANONICAL_JSON_SHA256_V1",
            "threshold_registry": "RAW_BYTES_SHA256_FROZEN",
        },
        "next_stage_authorized": False,
        "review_status": "PENDING_REVIEW",
        "review_note": (
            "LOOP-6 findings were remediated; independent re-review remains "
            "required before any next-stage authorization."),
        "gates": {
            "GS-A": {"pass": gs_a, "checks": gs_a_checks},
            "GS-B": {
                "pass": gs_b,
                "bypass_case_count": len(bypass_rows),
                "bypass_success_count": bypass_success_count,
            },
            "GS-C": {
                "pass": gs_c,
                "checks": gs_c_checks,
                "registry_expected": policy["threshold_registry"]["sha256"],
                "registry_actual": registry_actual,
            },
        },
        "metrics": {
            "unknown_allow_count": unknown_allow_count,
            "bypass_success_count": bypass_success_count,
            "false_abort_rate": false_abort_rate,
            "authorization_provenance_complete_rate": provenance_complete_rate,
        },
        "determinism": {
            "same_input_response_bitwise_equal": deterministic_all,
            "case_count": len(rows),
        },
        "thresholds_widened": False,
        "cases": rows,
    }
    return result


def run() -> dict:
    result = evaluate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(
        (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"))
    return result


def main() -> int:
    result = run()
    print(json.dumps({
        "verdict": result["verdict"],
        "GS-A": result["gates"]["GS-A"]["pass"],
        "GS-B": result["gates"]["GS-B"]["pass"],
        "GS-C": result["gates"]["GS-C"]["pass"],
        "metrics": result["metrics"],
        "review_status": result["review_status"],
    }, indent=2, ensure_ascii=False))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
