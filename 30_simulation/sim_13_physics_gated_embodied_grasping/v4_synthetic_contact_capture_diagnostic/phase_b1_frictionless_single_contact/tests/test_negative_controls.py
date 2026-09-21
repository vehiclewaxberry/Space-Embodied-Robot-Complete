from __future__ import annotations

import pytest

from b1_contact import run_negative_controls


CONTROL_IDS = (
    "NC-B101_SAME_SIGN_ACTION_REACTION",
    "NC-B102_NORMAL_FLIP",
    "NC-B103_GAP_SIGN_SUCTION",
    "NC-B104_MISSING_TARGET_FORCE",
    "NC-B105_MISSING_CONTACT_LOG",
    "NC-B106_NAN_STATE",
    "NC-B107_OVERPENETRATION",
    "NC-B108_RP_UNIT_SCALE",
)


@pytest.mark.parametrize("control_id", CONTROL_IDS)
def test_raw_mutation_exceeds_threshold_and_guard_rejects(contact_bundle, control_id):
    _, _, _, config, histories = contact_bundle
    controls = {item["control_id"]: item for item in run_negative_controls(histories["rk4_reference"], config)}
    result = controls[control_id]
    assert result["raw_error_exceeds_threshold"] is True
    assert result["guard_detected"] is True
    assert result["mutation_rejected"] is True
    assert result["result"] == "PASS_NEGATIVE_CONTROL"
