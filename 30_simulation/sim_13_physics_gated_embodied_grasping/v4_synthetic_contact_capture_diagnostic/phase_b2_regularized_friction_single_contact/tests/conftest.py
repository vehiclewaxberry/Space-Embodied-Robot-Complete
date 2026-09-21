from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b2_contact import deterministic_friction_scenario, integrate_friction_contact


@pytest.fixture(scope="session")
def friction_bundle():
    model, service, target, config = deterministic_friction_scenario()
    specs = {
        "rk4_coarse": ("rk4", 1.0e-3),
        "rk4_fine": ("rk4", 5.0e-4),
        "rk4_reference": ("rk4", 2.5e-4),
        "midpoint_coarse": ("midpoint", 5.0e-4),
        "midpoint_fine": ("midpoint", 2.5e-4),
        "midpoint_reference": ("midpoint", 1.25e-4),
    }
    histories = {
        name: integrate_friction_contact(
            model, service, target, config,
            step_s=step, duration_s=0.04, method=method,
        )
        for name, (method, step) in specs.items()
    }
    return model, service, target, config, histories
