from __future__ import annotations

from pathlib import Path
import sys

import pytest


PHASE_B3 = Path(__file__).resolve().parents[1]
if str(PHASE_B3) not in sys.path:
    sys.path.insert(0, str(PHASE_B3))

from b3_contact import (  # noqa: E402
    deterministic_dual_contact_scenario,
    integrate_dual_contact,
    summarize_dual_contact_history,
)


DURATION_S = 0.060
RUN_SPECS = {
    "rk4_coarse": ("rk4", 1.0e-3),
    "rk4_fine": ("rk4", 5.0e-4),
    "rk4_reference": ("rk4", 2.5e-4),
    "midpoint_coarse": ("midpoint", 5.0e-4),
    "midpoint_fine": ("midpoint", 2.5e-4),
    "midpoint_reference": ("midpoint", 1.25e-4),
}


@pytest.fixture(scope="session")
def dual_scenario():
    return deterministic_dual_contact_scenario()


@pytest.fixture(scope="session")
def dual_bundle(dual_scenario):
    model, service, target, config = dual_scenario
    histories = {
        name: integrate_dual_contact(
            model,
            service,
            target,
            config,
            step_s=step_s,
            duration_s=DURATION_S,
            method=method,
        )
        for name, (method, step_s) in RUN_SPECS.items()
    }
    summaries = {
        name: summarize_dual_contact_history(history, config)
        for name, history in histories.items()
    }
    return model, service, target, config, histories, summaries
