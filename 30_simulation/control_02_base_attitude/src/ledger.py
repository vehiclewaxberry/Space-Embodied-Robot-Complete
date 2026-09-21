"""Machine-only momentum attribution for CTRL-02."""
from __future__ import annotations

import numpy as np


ATTRIBUTION_LABELS = (
    "INTERNAL_REDISTRIBUTION",
    "MOMENTUM_STORAGE",
    "EXTERNAL_MOMENTUM_REMOVAL",
    "MIXED",
)


def classify_attribution(
    delta_h_external,
    wheel_storage,
    internal_motion: bool,
    tolerance: float,
) -> str:
    """Classify from numeric ledger values, never from a controller name."""
    ext = float(np.linalg.norm(np.asarray(delta_h_external, dtype=float))) > tolerance
    storage = float(np.linalg.norm(np.asarray(wheel_storage, dtype=float))) > tolerance
    if ext and (storage or internal_motion):
        return "MIXED"
    if ext:
        return "EXTERNAL_MOMENTUM_REMOVAL"
    if storage:
        return "MOMENTUM_STORAGE"
    # Closed vocabulary: passive zero-action rows are the zero-measure subset of
    # INTERNAL_REDISTRIBUTION and carry control_action=NONE separately.
    return "INTERNAL_REDISTRIBUTION"


def propellant_from_angular_impulse(
    angular_impulse_Nms: float, lever_m: float, isp_s: float, g0_mps2: float
) -> tuple[float, float]:
    total_impulse_Ns = float(angular_impulse_Nms) / float(lever_m)
    propellant_g = 1000.0 * total_impulse_Ns / (float(isp_s) * float(g0_mps2))
    return total_impulse_Ns, propellant_g
