"""Unit contract enforcement (S00).

Internal representation is strict SI: m, kg, s, rad, N, N*m, kg*m^2.
Anything arriving in CAD/display units (mm, g, deg) must pass through the
explicit converters here. Silent pass-through of non-SI data is a contract
violation and the plausibility gates below exist to catch it fail-closed.
"""
from __future__ import annotations

import numpy as np

# --- exact conversion factors -------------------------------------------------
MM_PER_M = 1.0e3
G_PER_KG = 1.0e3
DEG_PER_RAD = 180.0 / np.pi
# inertia: 1 kg*m^2 = 1e3 g * 1e6 mm^2 = 1e9 g*mm^2
GMM2_PER_KGM2 = 1.0e9


def mm_to_m(x):
    return np.asarray(x, dtype=float) / MM_PER_M


def m_to_mm(x):
    return np.asarray(x, dtype=float) * MM_PER_M


def g_to_kg(x):
    return np.asarray(x, dtype=float) / G_PER_KG


def kg_to_g(x):
    return np.asarray(x, dtype=float) * G_PER_KG


def deg_to_rad(x):
    return np.asarray(x, dtype=float) / DEG_PER_RAD


def rad_to_deg(x):
    return np.asarray(x, dtype=float) * DEG_PER_RAD


def inertia_gmm2_to_kgm2(x):
    return np.asarray(x, dtype=float) / GMM2_PER_KGM2


def inertia_kgm2_to_gmm2(x):
    return np.asarray(x, dtype=float) * GMM2_PER_KGM2


class UnitContractViolation(RuntimeError):
    """Raised when ingested data fails the SI plausibility contract."""


# --- fail-closed plausibility gates for the B601-class arm ---------------------
# These bounds are ingestion tripwires for THIS asset class (a <2 m tabletop-class
# arm on a 12U servicer), not physics claims. A kg->g or m->mm mistake shifts
# values by 1e3 (1e6/1e9 for inertia) and lands far outside these windows.
ARM_LINK_OFFSET_MAX_M = 2.0          # any |joint origin| beyond this on a ~0.9 m arm => suspect mm
ARM_LINK_MASS_MAX_KG = 50.0          # any single arm link beyond this => suspect g mis-scale
ARM_LINK_MASS_MIN_KG = 1.0e-4
ARM_LINK_INERTIA_MAX_KGM2 = 10.0     # arm-link inertia beyond this => suspect g*mm^2 mis-scale
ARM_LINK_INERTIA_MIN_KGM2 = 1.0e-12


def assert_si_plausible_arm_model(model: dict) -> None:
    """Fail-closed tripwire: reject an extracted arm model whose magnitudes are
    inconsistent with SI for this asset class. `model` is the dict produced by
    dh_v1.urdf_extract.extract_urdf().
    """
    for j in model["joints"]:
        off = np.linalg.norm(np.asarray(j["origin_xyz"], dtype=float))
        if off > ARM_LINK_OFFSET_MAX_M:
            raise UnitContractViolation(
                f"joint '{j['name']}' origin offset {off:.6g} m exceeds "
                f"{ARM_LINK_OFFSET_MAX_M} m: suspected mm data in SI channel"
            )
    for l in model["links"]:
        if l["inertial"] is None:
            continue
        m = float(l["inertial"]["mass"])
        if not (ARM_LINK_MASS_MIN_KG <= m <= ARM_LINK_MASS_MAX_KG):
            raise UnitContractViolation(
                f"link '{l['name']}' mass {m:.6g} kg outside "
                f"[{ARM_LINK_MASS_MIN_KG}, {ARM_LINK_MASS_MAX_KG}]: suspected unit mis-scale"
            )
        I = np.asarray(l["inertial"]["inertia_com"], dtype=float)
        eig = np.linalg.eigvalsh(I)
        if eig.max() > ARM_LINK_INERTIA_MAX_KGM2 or eig.max() < ARM_LINK_INERTIA_MIN_KGM2:
            raise UnitContractViolation(
                f"link '{l['name']}' principal inertia {eig.max():.6g} kg*m^2 outside "
                f"[{ARM_LINK_INERTIA_MIN_KGM2}, {ARM_LINK_INERTIA_MAX_KGM2}]: suspected unit mis-scale"
            )


def scale_model_units(model: dict, length_scale: float, mass_scale: float) -> dict:
    """Return a deep-scaled copy of an extracted model (used ONLY by negative
    controls to fabricate wrong-unit inputs; never used on the accepted plant).
    length_scale/mass_scale multiply the stored values.
    """
    import copy

    out = copy.deepcopy(model)
    for j in out["joints"]:
        j["origin_xyz"] = [v * length_scale for v in j["origin_xyz"]]
    for l in out["links"]:
        if l["inertial"] is None:
            continue
        l["inertial"]["mass"] = l["inertial"]["mass"] * mass_scale
        l["inertial"]["com"] = [v * length_scale for v in l["inertial"]["com"]]
        I = np.asarray(l["inertial"]["inertia_com"], dtype=float)
        l["inertial"]["inertia_com"] = (I * mass_scale * length_scale**2).tolist()
    out["provenance"] = dict(out.get("provenance", {}))
    out["provenance"]["unit_tamper"] = {
        "length_scale": length_scale,
        "mass_scale": mass_scale,
        "note": "NEGATIVE_CONTROL_ONLY",
    }
    return out
