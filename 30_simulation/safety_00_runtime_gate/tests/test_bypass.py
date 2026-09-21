import copy

from case_factory import (
    decide_test_vector,
    make_case,
    rehash_case,
)
from safety_core import decide


def _assert_blocked(case_id, expected_decision):
    request, evidence = make_case(case_id)
    response = decide_test_vector(request, evidence)
    assert response["physical_state"] == "UNKNOWN"
    assert response["decision"] == expected_decision, response
    assert response["decision"] not in {"ALLOW", "MODIFY"}
    return 0.0


def test_t23_b1_forged_provenance_blocked():
    return _assert_blocked("B1_FORGED_PROVENANCE", "ABORT")


def test_t24_b2_stale_evidence_blocked():
    return _assert_blocked("B2_STALE_EVIDENCE", "WAIT")


def test_t25_b3_out_of_domain_blocked():
    return _assert_blocked("B3_OUT_OF_DOMAIN", "BACKOFF")


def test_t26_b4_lambda_rounding_smuggling_blocked():
    return _assert_blocked("B4_LAMBDA_ROUNDING_SMUGGLING", "ABORT")


def test_t27_b5_missing_provisional_field_blocked():
    return _assert_blocked("B5_PROVISIONAL_FIELD_MISSING", "ABORT")


def test_t28_b6_uncertified_l2_blocked():
    return _assert_blocked("B6_UNCERTIFIED_L2", "WAIT")


def test_t29_b7_prose_condition_blocked():
    return _assert_blocked("B7_PROSE_CONDITION", "ABORT")


def test_t30_d1_fallback_requires_domain_check():
    request, evidence = make_case("D1_L2_TO_L0_UNCHECKED")
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "BACKOFF"
    assert response["reason_code"] == "FALLBACK_DOMAIN_UNCHECKED"
    assert response["fallback_trace"][0]["domain_checked"] is False
    return 0.0


def test_t31_d2_checked_fallback_still_cannot_finalize():
    request, evidence = make_case("D2_L2_TO_L1_RECHECKED")
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "WAIT"
    assert response["physical_state"] == "UNKNOWN"
    assert response["fallback_trace"][0]["computed_in_domain"] is True
    assert response["fallback_trace"][0]["accepted_for_finalization"] is False
    return 0.0


def test_t32_candidate_binding_prevents_exact_solver_retarget():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    request["state_estimate"]["lambda_actual"] = 0.35
    request["state_estimate"]["lambda_grid"] = 0.5
    request["model_validity"]["selection_mode"] = "EXACT_SOLVER"
    rehash_case(request, evidence)
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "CANDIDATE_STATE_BINDING_MISMATCH"
    return 0.0


def test_t33_provisional_subset_is_rejected():
    request, evidence = make_case("N1_NORMAL_ALLOW")
    request["model_validity"]["provisional_flags"].remove("contact_T_c")
    rehash_case(request, evidence)
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "PROVISIONAL_FLAGS_MISSING"
    return 0.0


def test_t43_wrong_sim12_row_is_blocked():
    request, evidence = make_case("B8_WRONG_ROW_REF")
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "CANDIDATE_ROW_BINDING_MISMATCH"
    return 0.0


def test_t44_unregistered_candidate_is_blocked():
    request, evidence = make_case("B9_ARBITRARY_CANDIDATE")
    response = decide_test_vector(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "CANDIDATE_ID_MISMATCH"
    return 0.0


def test_t45_no_key_cannot_execute_nominal_candidate():
    request, evidence = make_case("B12_NO_AUTH_KEY")
    response = decide(request, evidence)
    assert response["decision"] == "ABORT"
    assert response["reason_code"] == "AUTHORIZATION_KEY_UNAVAILABLE"
    return 0.0
