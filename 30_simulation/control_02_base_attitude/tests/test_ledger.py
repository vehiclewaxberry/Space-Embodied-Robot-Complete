"""Momentum attribution and propellant formula tests."""
import copy
import json

import numpy as np

from config_loader import MODULE, load_config
from ledger import classify_attribution, propellant_from_angular_impulse
from run_gates import independent_propellant_audit


def test_attribution_vocabulary_from_numeric_ledger():
    tol = 1e-12
    cases = [
        (np.zeros(3), np.zeros(3), True, "INTERNAL_REDISTRIBUTION"),
        (np.zeros(3), [0.01, 0, 0], False, "MOMENTUM_STORAGE"),
        ([0.02, 0, 0], np.zeros(3), False, "EXTERNAL_MOMENTUM_REMOVAL"),
        ([0.02, 0, 0], [0.01, 0, 0], False, "MIXED"),
    ]
    for ext, wheel, internal, expected in cases:
        assert classify_attribution(ext, wheel, internal, tol) == expected
    return 0.0


def test_propellant_formula_reproduces_debris_anchor():
    impulse, prop = propellant_from_angular_impulse(
        3.650992635553959, 0.17, 60.0, 9.80665
    )
    assert abs(impulse - 21.47642726796446) < 1e-12
    assert abs(prop - 36.49976846997439) < 1e-12
    return max(
        abs(impulse - 21.47642726796446),
        abs(prop - 36.49976846997439),
    )


def test_gate_independent_propellant_audit_rejects_tamper():
    cfg = load_config()
    rows = json.loads(
        (MODULE / "results" / "stage_b_summary.json").read_text(encoding="utf-8")
    )
    baseline = independent_propellant_audit(rows, cfg)
    assert baseline["all_match"] is True

    tampered = copy.deepcopy(rows)
    target = next(
        row for row in tampered if row["external_angular_impulse_Nms"] > 0.0
    )
    target["propellant_g"] += 0.001
    rejected = independent_propellant_audit(tampered, cfg)
    assert rejected["all_match"] is False
    assert rejected["max_propellant_abs_difference_g"] >= 0.001 - 1e-12
    return rejected["max_propellant_abs_difference_g"]
