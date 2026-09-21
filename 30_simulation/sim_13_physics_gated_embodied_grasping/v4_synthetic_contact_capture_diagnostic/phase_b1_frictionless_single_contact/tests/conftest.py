from __future__ import annotations

import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from b1_contact import deterministic_contact_scenario, integrate_contact


@pytest.fixture(scope="session")
def contact_bundle():
    model, service, target, config = deterministic_contact_scenario()
    duration_s = 0.04
    histories = {
        "rk4_coarse": integrate_contact(model, service, target, config, step_s=1.0e-3, duration_s=duration_s, method="rk4"),
        "rk4_fine": integrate_contact(model, service, target, config, step_s=5.0e-4, duration_s=duration_s, method="rk4"),
        "rk4_reference": integrate_contact(model, service, target, config, step_s=2.5e-4, duration_s=duration_s, method="rk4"),
        "midpoint_coarse": integrate_contact(model, service, target, config, step_s=5.0e-4, duration_s=duration_s, method="midpoint"),
        "midpoint_fine": integrate_contact(model, service, target, config, step_s=2.5e-4, duration_s=duration_s, method="midpoint"),
        "midpoint_reference": integrate_contact(model, service, target, config, step_s=1.25e-4, duration_s=duration_s, method="midpoint"),
    }
    return model, service, target, config, histories
