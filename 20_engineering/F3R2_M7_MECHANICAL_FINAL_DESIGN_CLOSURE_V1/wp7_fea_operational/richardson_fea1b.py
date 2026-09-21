# -*- coding: utf-8 -*-
"""Richardson (observed-order) extrapolation on the Z series + verification.

Fit v(h) = v_inf - C*h^p to three levels, h proportional to 1/kz.
Fit is made from kz = 3/4/6 and then VERIFIED against the independently
solved kz = 8 and kz = 12 jobs for the governing case.
Written as a reusable module: build_fea1b_evidence.py imports rich_fit().
"""
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
M4 = [(15.494, 42.4393), (-42.5096, 15.3917),
      (-15.4621, -42.612), (42.5416, -15.5644)]


def rich_fit(kzs, vals):
    """Observed-order fit from exactly three (kz, value) points."""
    if len(kzs) != 3 or any(v is None for v in vals):
        return {"status": "NEED_THREE_VALID_POINTS"}
    h = [1.0 / k for k in kzs]
    v1, v2, v3 = vals
    d1, d2 = v2 - v1, v3 - v2
    if d1 == 0.0 or d2 == 0.0:
        return {"status": "ZERO_INCREMENT_NO_FIT",
                "increments": [d1, d2]}
    if d1 * d2 < 0:
        return {"status": "NON_MONOTONE_INCREMENTS_NO_FIT",
                "increments": [d1, d2]}
    target = d1 / d2
    best = None
    p = 0.02
    while p <= 6.0:
        r = (h[0] ** p - h[1] ** p) / (h[1] ** p - h[2] ** p)
        e = abs(r - target)
        if best is None or e < best[1]:
            best = (p, e, r)
        p += 0.002
    p = best[0]
    C = d2 / (h[1] ** p - h[2] ** p)
    vinf = v3 + C * (h[2] ** p)
    rem = 100.0 * (vinf / v3 - 1.0) if v3 else None
    return {"status": "OK", "observed_order_p": p,
            "fit_residual_on_increment_ratio": best[1],
            "increment_ratio_target": target,
            "C": C, "extrapolated_limit": vinf,
            "value_at_finest_fitted_level": v3,
            "estimated_remaining_discretization_error_pct_at_finest_fitted": rem,
            "fitted_levels_kz": list(kzs),
            "method": "v(h)=v_inf - C*h^p with h proportional to 1/kz; p found "
                      "by matching the observed increment ratio"}


def load(d):
    out = {}
    for p in glob.glob(os.path.join(d, "*.json")):
        r = json.load(open(p))
        out[r["job_name"]] = r
    return out


def collar_max(r, lo, hi):
    smap = r.get("stage_a_top_surface_nodal_averaged_mises_by_xy") or {}
    best = None
    for k, v in smap.items():
        x, y = [float(t) for t in k.split("|")]
        dd = min(math.hypot(x - a, y - b) for a, b in M4)
        if lo < dd + 1e-12 and dd <= hi:
            if best is None or v > best[1]:
                best = (k, v)
    return best


def surface_at_xy(r, key):
    return (r.get("stage_a_top_surface_nodal_averaged_mises_by_xy") or {}).get(key)


M6 = [(70.0, 70.0), (70.0, -70.0), (-70.0, 70.0), (-70.0, -70.0)]
M5 = [(62.5 * math.cos(math.radians(22.5 + 45.0 * k)),
       62.5 * math.sin(math.radians(22.5 + 45.0 * k))) for k in range(8)]
ALL_BOLTS = M6 + M5 + M4
STEP_R = (20.0, 50.0, 75.0)


def surface_far_field(r):
    """Max nodal-averaged vM over Stage A top-surface nodes that are clear of
    EVERY rigid bolt patch (>15 mm) and of every staircase radius (>10 mm).
    Fixed physical node set: identical at every kz of the Z series."""
    smap = r.get("stage_a_top_surface_nodal_averaged_mises_by_xy") or {}
    best = None
    n = 0
    for k, v in smap.items():
        x, y = [float(t) for t in k.split("|")]
        if any(math.hypot(x - a, y - b) <= 15.0 for a, b in ALL_BOLTS):
            continue
        rc = math.hypot(x, y)
        if any(abs(rc - rr) <= 10.0 for rr in STEP_R):
            continue
        n += 1
        if best is None or v > best[1]:
            best = (k, v)
    return best, n


QUANT = {
    "ALLIE": lambda r: r["energy_odb"]["ALLIE"],
    "rp_U2_mm": lambda r: r["rp_translation_mm"][1],
    "rp_UR3_rad": lambda r: r["rp_rotation_rad"][2],
    "peak_disp_magnitude_mm": lambda r: r["peak_disp"]["magnitude_mm"],
    "model_volume_weighted_mean_mises_MPa":
        lambda r: r["model_volume_weighted_mean_mises_MPa"],
    "surface_nodal_collar_12_25_max_MPa": lambda r: collar_max(r, 12.0, 25.0)[1],
    "surface_nodal_collar_25_40_max_MPa": lambda r: collar_max(r, 25.0, 40.0)[1],
    "surface_nodal_tracked_node_48_0_MPa":
        lambda r: surface_at_xy(r, "48.0000|0.0000"),
    "surface_nodal_tracked_node_56_8_MPa":
        lambda r: surface_at_xy(r, "56.0000|8.0000"),
    "surface_nodal_patch_peak_MPa": lambda r: collar_max(r, 0.0, 12.0)[1],
    "surface_nodal_far_field_max_MPa": lambda r: surface_far_field(r)[0][1],
    "peak_mises_nodal_averaged_MPa":
        lambda r: r["peak_mises_nodal_averaged"]["value_MPa"],
    "peak_mises_element_averaged_MPa":
        lambda r: r["peak_mises_element_averaged"]["value_MPa"],
    "peak_mises_ip_MPa": lambda r: r["peak_mises_ip"]["value_MPa"],
}

ADMISSIBLE = ["ALLIE", "rp_U2_mm", "rp_UR3_rad", "peak_disp_magnitude_mm",
              "model_volume_weighted_mean_mises_MPa",
              "surface_nodal_collar_12_25_max_MPa",
              "surface_nodal_collar_25_40_max_MPa",
              "surface_nodal_tracked_node_48_0_MPa",
              "surface_nodal_tracked_node_56_8_MPa",
              "surface_nodal_far_field_max_MPa"]
SINGULAR = ["surface_nodal_patch_peak_MPa", "peak_mises_nodal_averaged_MPa",
            "peak_mises_element_averaged_MPa", "peak_mises_ip_MPa"]

LEVELS = [(1, "l3_mm_fine"), (2, "z2_zr_n20k2"), (3, "t3_tt_fine"),
          (4, "z4_zr_n20k4"), (6, "z6_zr_n20k6"), (8, "z8_zr_n20k8"),
          (12, "z12_zr_n20k12")]


def build(case="capture_150kg_qs"):
    B = load(os.path.join(HERE, "jobs_b", "_extract_b"))
    got = {}
    for kz, lv in LEVELS:
        j = "fea1b_%s_%s_c3d8i" % (case, lv)
        if j in B:
            got[kz] = B[j]
    out = {"case": case, "levels_solved_kz": sorted(got),
           "quantities": {}}
    for name, fn in QUANT.items():
        series = {}
        for kz in sorted(got):
            try:
                series[kz] = fn(got[kz])
            except Exception:                                   # noqa: BLE001
                series[kz] = None
        fitk = [3, 4, 6]
        fit = rich_fit(fitk, [series.get(k) for k in fitk])
        ver = {}
        if fit.get("status") == "OK":
            for kz in (8, 12):
                if series.get(kz) is None:
                    ver[kz] = {"status": "LEVEL_NOT_SOLVED_FOR_THIS_CASE"}
                    continue
                pred = fit["extrapolated_limit"] - fit["C"] * (1.0 / kz) ** fit["observed_order_p"]
                ver[kz] = {"predicted": pred, "solved": series[kz],
                           "prediction_error_pct": 100.0 * (series[kz] / pred - 1.0)}
        out["quantities"][name] = {
            "class": ("ADMISSIBLE_CONVERGENCE_QUANTITY" if name in ADMISSIBLE
                      else "SINGULARITY_AFFECTED_NOT_A_DESIGN_STRESS"),
            "values_by_kz": series,
            "successive_change_pct": {
                "%d->%d" % (a, b): (100.0 * (series[b] / series[a] - 1.0)
                                    if series.get(a) and series.get(b) else None)
                for a, b in zip(sorted(got), sorted(got)[1:])},
            "richardson_fit_from_kz_3_4_6": fit,
            "verification_against_independently_solved_levels": ver}
    return out


if __name__ == "__main__":
    r = build()
    print("levels solved:", r["levels_solved_kz"])
    print()
    for cls in ("ADMISSIBLE_CONVERGENCE_QUANTITY",
                "SINGULARITY_AFFECTED_NOT_A_DESIGN_STRESS"):
        print("=== %s ===" % cls)
        for name, d in r["quantities"].items():
            if d["class"] != cls:
                continue
            f = d["richardson_fit_from_kz_3_4_6"]
            if f.get("status") != "OK":
                print(" %-42s %s" % (name, f["status"]))
                continue
            v = d["verification_against_independently_solved_levels"]
            vs = " ".join("kz%d pred=%.6g solved=%.6g err=%+.3f%%" % (
                k, x["predicted"], x["solved"], x["prediction_error_pct"])
                for k, x in sorted(v.items()) if "predicted" in x)
            print(" %-42s p=%.3f  limit=%.6g  rem_err_at_kz6=%+.3f%%" % (
                name, f["observed_order_p"], f["extrapolated_limit"],
                f["estimated_remaining_discretization_error_pct_at_finest_fitted"]))
            print("      %s" % vs)
            print("      values %s" % {k: round(vv, 8) for k, vv in
                                       d["values_by_kz"].items() if vv is not None})
        print()
    with open(os.path.join(HERE, "jobs_b", "_RICHARDSON_150KG.json"), "w") as f:
        json.dump(r, f, indent=1, sort_keys=True)
