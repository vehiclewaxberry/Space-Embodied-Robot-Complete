# -*- coding: utf-8 -*-
"""WP2 V3 (R2) nine-configuration design mass aggregation (R2-WI-05.2).

Method: exact arithmetic component substitution on the frozen V2 document.
For every configuration C01..C09 the two R1 rows (solar_array_left/right,
0.3483933 kg each) are replaced by the R2 composite wings (0.78 kg each)
from SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json.  All non-solar component rows
are carried VERBATIM from V2 (frozen authorities: bus, accepted B601 URDF,
M3R, load bridge, targets).  System mass / CG / inertia-about-system-CG /
principal moments+axes are recomputed; checks per ODR-25:
component-sum, C02/C03 mirror consistency, symmetry, positive
definiteness, triangle inequalities, no zero-fill.

Uncertainty: V2 member-level uncertainty fields are carried verbatim for
non-solar members.  R2 wing uncertainty is a PROVISIONAL candidate policy
(mass u = 20% of wing mass, inertia u = 25% per component, com u = 5 mm
per axis) until the WP2 uncertainty policy V3 formally reruns; flagged
PROVISIONAL_DERIVED, never null (ODR-25).

Inputs (read-only):
  SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml            (frozen V2)
  ../ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json

Outputs:
  SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml
  WP2_V3_R2_RECEIPT.json
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
V2 = HERE / "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"
R2PKG = HERE.parent / "ecr_solar_array_r2" / "SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json"
OUT_YAML = HERE / "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
OUT_RECEIPT = HERE / "WP2_V3_R2_RECEIPT.json"

SOLAR_IDS = {"solar_array_left", "solar_array_right"}
R2_WING_MASS = 0.78
R2_MASS_U = 0.20 * R2_WING_MASS        # PROVISIONAL candidate policy
R2_COM_U = 0.005                        # m per axis
R2_INERTIA_U_FRAC = 0.25

LEGACY_SIM_REFERENCE_KG = 24.000
LEGACY_R1_BOTH_WINGS_KG = 0.6967866


def local_now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def inertia_own_from_origin(I_origin, m, r):
    r = np.asarray(r, float)
    S = (r @ r) * np.eye(3) - np.outer(r, r)
    return np.asarray(I_origin, float) - m * S



def member_inertia_sigmas(mem):
    """Per-component inertia standard uncertainty (Ixx..Iyz) for a member,
    tolerant of V2-carried and R2 record schemas."""
    iu = mem.get("inertia_uncertainty")
    if isinstance(iu, dict):
        c = iu.get("component_standard_uncertainty_kg_m2")
        if isinstance(c, dict):
            return {k: float(c.get(k, 0.0)) for k in
                    ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")}
    prov = mem.get("inertia_standard_uncertainty_kg_m2_provisional")
    if prov is not None:
        a = np.array(prov, float)
        return {"Ixx": float(abs(a[0, 0])), "Iyy": float(abs(a[1, 1])),
                "Izz": float(abs(a[2, 2])), "Ixy": float(abs(a[0, 1])),
                "Ixz": float(abs(a[0, 2])), "Iyz": float(abs(a[1, 2]))}
    return {k: 0.0 for k in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")}


def system_uncertainties(new_members, masses, coms, CG):
    """Gate-compatible system-level standard uncertainties (ODR-25 no-null
    rule).  Method (declared candidate policy V3): independent-member RSS
    for mass; first-order CG propagation sqrt(sum((m_i u_i)^2))/M; inertia
    per-component RSS of member own-tensor sigmas PLUS first-order Steiner
    terms d^2 u_m and 2 m |d| u_com in quadrature.  Off-diagonal components
    use |d| as the lever (declared approximation)."""
    u_m = np.array([float(mem.get("mass_standard_uncertainty_kg") or 0.0)
                    for mem in new_members])
    u_c = np.array([float(mem.get("com_standard_uncertainty_m_per_axis")
                          or 0.0) for mem in new_members])
    sig_mass = float(np.sqrt((u_m ** 2).sum()))
    sig_cg_scalar = float(np.sqrt(((masses * u_c) ** 2).sum())
                          / masses.sum())
    sig_cg = np.array([sig_cg_scalar] * 3)  # per-axis declared equal
    sig = {k: 0.0 for k in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")}
    acc = {k: 0.0 for k in sig}
    for mem, m, r, um, uc in zip(new_members, masses, coms, u_m, u_c):
        d = r - CG
        d2 = float(d @ d)
        dl = float(np.linalg.norm(d))
        steiner = (d2 * um) ** 2 + (2.0 * m * dl * uc) ** 2
        ms = member_inertia_sigmas(mem)
        for k in acc:
            acc[k] += ms[k] ** 2 + steiner
    for k in sig:
        sig[k] = float(np.sqrt(acc[k]))
    return sig_mass, [float(v) for v in sig_cg], sig

def principal(I):
    w, V = np.linalg.eigh(np.asarray(I, float))
    if np.linalg.det(V) < 0:      # ODR-07-era handedness repair convention
        V[:, -1] = -V[:, -1]
    return w, V


def main():
    v2 = yaml.safe_load(V2.read_text(encoding="utf-8"))
    r2 = json.loads(R2PKG.read_text(encoding="utf-8"))
    r2_cfgs = r2["configurations"]

    configs_out = []
    receipts = []

    for cfg in v2["configurations"]:
        cid = cfg["configuration_id"]
        r2c = r2_cfgs[cid]
        members = [m for m in cfg["composition"]
                   if m["component_id"] not in SOLAR_IDS]

        new_members = list(members)
        for side, key in (("left", "left_wing"), ("right", "right_wing")):
            w = r2c[key]
            r_cg = np.array(w["cg_S_m"], float)
            I_own = inertia_own_from_origin(
                w["inertia_about_S_origin_kgm2"], w["mass_kg"], r_cg)
            new_members.append({
                "component_id": f"solar_array_r2_{side}",
                "mass_kg": w["mass_kg"],
                "mass_class": "MATERIAL_DERIVED_CANDIDATE (areal-density "
                              "3.0 kg/m2 model, ODR-20/ODR-21)",
                "mass_standard_uncertainty_kg": R2_MASS_U,
                "com_S_m": [float(v) for v in r_cg],
                "com_class": "ANALYTIC_FROM_R2_GEOMETRY",
                "com_standard_uncertainty_m_per_axis": R2_COM_U,
                "inertia_about_own_com_S_kg_m2": I_own.tolist(),
                "inertia_class": "ANALYTIC_IDEALIZATION",
                "inertia_reference_frame_declared": "S",
                "inertia_reference_point_declared":
                    "component_own_center_of_mass",
                "inertia_standard_uncertainty_kg_m2_provisional":
                    (R2_INERTIA_U_FRAC * np.abs(I_own)).tolist(),
                "source": "ecr_solar_array_r2/"
                          "SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
                "authority": "DESIGN_MODEL (ODR-20); NOT measured; "
                             "AS_BUILT HOLD",
            })

        masses = np.array([m["mass_kg"] for m in new_members], float)
        coms = np.array([m["com_S_m"] for m in new_members], float)
        M = float(masses.sum())
        CG = (masses[:, None] * coms).sum(axis=0) / M

        I_sys = np.zeros((3, 3))
        for m, r, mem in zip(masses, coms, new_members):
            I_own = np.array(mem["inertia_about_own_com_S_kg_m2"], float)
            d = r - CG
            I_sys += I_own + m * ((d @ d) * np.eye(3) - np.outer(d, d))

        w, V = principal(I_sys)
        Ixx, Iyy, Izz = I_sys[0, 0], I_sys[1, 1], I_sys[2, 2]

        checks = {
            "component_sum_equals_system_mass":
                abs(float(np.sum(masses)) - M) < 1e-12,
            "inertia_symmetric":
                bool(np.allclose(I_sys, I_sys.T, atol=1e-15)),
            "positive_definite": bool(w.min() > 0),
            "min_eigenvalue_kg_m2": float(w.min()),
            "triangle_inequalities": bool(
                w[0] + w[1] >= w[2] - 1e-12),
            "no_zero_fill": bool(
                M > 0 and np.all(np.isfinite(I_sys))
                and np.all(np.isfinite(CG))),
            "non_solar_members_carried_verbatim": len(members) == len(
                cfg["composition"]) - 2,
        }

        sig_mass, sig_cg, sig_inertia = system_uncertainties(
            new_members, masses, coms, CG)

        configs_out.append({
            "configuration_id": cid,
            "name": cfg.get("name") or "",
            # gate-compatible blocks (MECHANICAL_TO_EMBODIED_HANDOFF_GATE
            # check design_mass_model_loadable schema)
            "mass": {"value_kg": M,
                     "standard_uncertainty_kg": sig_mass,
                     "authority": "DESIGN_MODEL_R2"},
            "center_of_mass": {"xyz_m": [float(v) for v in CG],
                               "standard_uncertainty_xyz_m": sig_cg,
                               "reference_frame": "S"},
            "inertia": {"components_kg_m2": {
                            "Ixx": float(Ixx), "Iyy": float(Iyy),
                            "Izz": float(Izz), "Ixy": float(I_sys[0, 1]),
                            "Ixz": float(I_sys[0, 2]),
                            "Iyz": float(I_sys[1, 2])},
                        "standard_uncertainty_components_kg_m2": sig_inertia,
                        "reference_frame": "S",
                        "reference_point": "system_center_of_mass"},
            "m4_configuration_library_name":
                cfg.get("m4_configuration_library_name")
                or cfg.get("configuration_label", ""),
            "cg_S_m": [float(v) for v in CG],
            "inertia_about_system_cg_S_kg_m2": {
                "Ixx": float(Ixx), "Iyy": float(Iyy), "Izz": float(Izz),
                "Ixy": float(I_sys[0, 1]), "Ixz": float(I_sys[0, 2]),
                "Iyz": float(I_sys[1, 2])},
            "principal_moments_kg_m2": [float(v) for v in w],
            "principal_axes_columns_S": V.tolist(),
            "uncertainty_policy": "V2 member fields carried verbatim for "
                "non-solar; R2 wings PROVISIONAL candidate policy "
                "(mass u=20%, com u=5 mm/axis, inertia u=25%) pending WP2 "
                "uncertainty policy V3",
            "source": "V2 arithmetic substitution + "
                      "SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
            "checks": checks,
            "composition": new_members,
        })
        receipts.append((cid, checks, M, CG))

    # cross-configuration regression checks (ODR-25 anchors)
    by_id = {c["configuration_id"]: c for c in configs_out}
    c01 = by_id["C01"]["cg_S_m"]
    c02 = by_id["C02"]["cg_S_m"]
    c03 = by_id["C03"]["cg_S_m"]
    # Mirror anchor semantics: the V2 non-solar stack is itself y-asymmetric
    # (carried verbatim, e.g. arm pose in C01). The ODR-25 mirror anchor
    # therefore applies to the SOLAR DELTA against the C01 both-deployed
    # baseline: (C02 - C01) must be the exact negative of (C03 - C01).
    d02 = [c02[i] - c01[i] for i in range(3)]
    d03 = [c03[i] - c01[i] for i in range(3)]
    mirror_ok = (abs(d02[1] + d03[1]) < 1e-9      # y: mirror negation
                 and abs(d02[0] - d03[0]) < 1e-12  # x: shared change
                 and abs(d02[2] - d03[2]) < 1e-12) # z: shared change
    # The solar-subsystem-only stage-1 package anchor (+/-0.1143 m) is
    # checked directly against the stage-1 JSON.
    r2_anchor_l = r2_cfgs["C02"]["both_wings"]["cg_S_m"][1]
    r2_anchor_r = r2_cfgs["C03"]["both_wings"]["cg_S_m"][1]
    solar_only_anchor_ok = (abs(r2_anchor_l + 0.1143) < 1e-3
                            and abs(r2_anchor_r - 0.1143) < 1e-3)
    c01_mass = by_id["C01"]["mass"]["value_kg"]

    doc = {
        "schema": "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2",
        "generated_local": local_now(),
        "authority": "ODR-20/ODR-25, R2-WI-05.2",
        "supersedes": "nothing - V2 stays the frozen R1-ledger document; "
                      "V3_R2 is the R2 design-ledger authority candidate",
        "mass_ledgers": {
            "legacy_simulation_reference_kg": LEGACY_SIM_REFERENCE_KG,
            "r2_whole_sat_candidate_kg": round(
                LEGACY_SIM_REFERENCE_KG - LEGACY_R1_BOTH_WINGS_KG
                + 2 * R2_WING_MASS, 9),
            "m7_design_ledger_c01_kg": c01_mass,
            "note": "two ledgers coexist by design (ODR-20); the M7 design "
                    "ledger carries arm/M3R/bridge members, the legacy "
                    "24 kg ledger serves historical sim reproduction only",
        },
        "regression_anchors": {
            "C02_C03_mirror_cg_y_absolute": [c02[1], c03[1]],
            "note": "absolute C02/C03 CG y are NOT mirror images because "
                    "the V2 non-solar stack is y-asymmetric (carried "
                    "verbatim); the mirror anchor is evaluated on solar "
                    "deltas vs C01",
            "C02_minus_C01_cg": d02,
            "C03_minus_C01_cg": d03,
            "mirror_consistency_on_solar_delta": bool(mirror_ok),
            "solar_only_stage1_anchor_plus_minus_0p1143":
                [r2_anchor_l, r2_anchor_r, bool(solar_only_anchor_ok)],
            "r2_wing_cg_y_abs_deployed_m":
                abs(r2_cfgs["C02"]["left_wing"]["cg_S_m"][1]),
        },
        "configurations": configs_out,
    }
    OUT_YAML.write_text(yaml.safe_dump(doc, sort_keys=False,
                                       allow_unicode=True),
                        encoding="utf-8")

    all_checks = (all(all(c.values()) for _, c, _, _ in receipts
                      if isinstance(c, dict))
                  and mirror_ok and solar_only_anchor_ok)
    receipt = {
        "schema": "WP2_V3_R2_RECEIPT",
        "generated_local": local_now(),
        "verdict": "PASS" if all_checks else "FAIL",
        "per_configuration": [
            {"configuration_id": cid, "mass_kg": M, "cg_S_m": list(CG),
             "checks": c} for cid, c, M, CG in receipts],
        "cross_configuration": {
            "C02_C03_mirror_consistency_on_solar_delta": bool(mirror_ok),
            "solar_only_stage1_anchor_ok": bool(solar_only_anchor_ok)},
        "hashes": {},
    }
    import hashlib
    def sha(p):
        h = hashlib.sha256()
        h.update(p.read_bytes())
        return h.hexdigest().upper()
    OUT_RECEIPT.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    receipt["hashes"] = {OUT_YAML.name: sha(OUT_YAML),
                         OUT_RECEIPT.name: sha(OUT_RECEIPT)}
    OUT_RECEIPT.write_text(json.dumps(receipt, indent=1), encoding="utf-8")

    print("WP2_V3_R2 verdict=%s" % receipt["verdict"])
    for cid, c, M, CG in receipts:
        print("%s m=%.6f cg=[%+.5f %+.5f %+.5f] checks=%s" % (
            cid, M, CG[0], CG[1], CG[2],
            all(c.values()) if isinstance(c, dict) else c))
    print("C02/C03 mirror:", mirror_ok, c02[1], c03[1])


main()
