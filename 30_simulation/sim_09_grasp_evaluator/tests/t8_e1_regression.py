"""t8 -- Gate E1 regression: G0 baseline anchors + results-CSV integrity.

Anchors (3 rows): the G0 baseline grid cell (P1, t_c=0, v_app=0.01, pose_6d,
q0=zeros, b601 stack, rigid_6dof) evaluated by the SAME evaluator:

  A1 post_capture_rate_dps   live re-evaluation (flexible disabled) vs frozen value
  A2 H_RW_Nms (=|H_c|)       live re-evaluation vs frozen value
  A3 E_flex_J                results CSV row vs frozen value (full ANCF, nominal
                             f1, Radau rtol 1e-6 -- too slow to re-run here; the
                             CSV row is itself covered by the integrity checks)

Iron rule: if an anchor drifts, FIX THE IMPLEMENTATION -- never edit the
expected values.

CSV integrity: 72 rows, row_complete=1 everywhere, unique scenario hashes that
EXACTLY match the deterministic e1_thin_slice grid, no missing values in the
metric columns of admissible rows, and every admissible row has flex_status
OK/RETRY (FLEX_SOLVER_FAIL must never be counted admissible).
"""
import _helpers  # noqa: F401
import csv
import math
import os

import numpy as np

import e1_thin_slice as e1
import evaluator

CSV_PATH = e1.RESULTS_CSV
G0_CASE_ID = "P1_tc00_v10mm_pose_6d"

# Frozen G0 anchors (E1 sweep @ commit 2f954fd+E1; determinism guaranteed by t7)
EXP_POST_RATE_DPS = 3.0550592621042534   # deg/s  (b601 stack, rigid_6dof)
EXP_H_RW_NMS = 3.6471383214246487        # N*m*s  |H_c| about combined CoM
EXP_E_FLEX_J = 2.4900520357413217e-05    # J      full ANCF nominal, rtol 1e-6
TOL_REL_LIVE = 1e-6        # live re-evaluation (BLAS-build robustness)
TOL_REL_CSV = 1e-9         # CSV round-trip (repr full precision)

ADMISSIBLE_REQUIRED_COLS = [
    "post_capture_rate_dps", "H_RW_Nms", "J_thr_Ns", "m_prop_g", "E_flex_J",
    "base_attitude_change_deg", "base_rate_peak_dps", "Jt_norm_Ns",
    "Lgrasp_norm_Nms", "collision_margin_min_m", "joint_limit_margin_rad",
    "manip_sqrt_det_JJT", "cond_number", "severity_proxy", "M_PCS",
    "mpcs_margin_H", "mpcs_margin_Jthr", "mpcs_margin_Eflex",
    "mpcs_margin_omega", "mpcs_margin_theta",
]


def _rel(measured, expected):
    return abs(measured - expected) / max(abs(expected), 1e-300)


def run():
    assert os.path.exists(CSV_PATH), f"missing E1 results CSV: {CSV_PATH}"
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    # ---- integrity: 72 complete rows, hashes == deterministic grid ----
    assert len(rows) == 72, f"expected 72 rows, found {len(rows)}"
    assert all(r["row_complete"] == "1" for r in rows), "incomplete row present"
    hashes = [r["scenario_hash"] for r in rows]
    assert len(set(hashes)) == 72, "duplicate scenario_hash"
    expected_hashes = {e1.make_candidate(s).scenario_hash
                       for s in e1.build_all_cases()}
    assert set(hashes) == expected_hashes, "CSV hashes != deterministic E1 grid"

    # ---- integrity: admissible rows fully populated, no NaN ----
    n_adm = 0
    for r in rows:
        if r["admissible"] != "1":
            continue
        n_adm += 1
        assert r["flex_status"] in ("OK", "RETRY_OK_rtol1e-5"), \
            f"{r['case_id']}: admissible with flex_status={r['flex_status']}"
        for c in ADMISSIBLE_REQUIRED_COLS:
            assert r[c] not in ("", None), f"{r['case_id']}: empty {c}"
            v = float(r[c])
            assert math.isfinite(v), f"{r['case_id']}: non-finite {c}={r[c]}"
    assert n_adm >= 1, "no admissible case in the whole slice"

    # ---- G0 anchors ----
    g0 = next(r for r in rows if r["case_id"] == G0_CASE_ID)
    spec = next(s for s in e1.build_all_cases() if s["case_id"] == G0_CASE_ID)
    cand = e1.make_candidate(spec)
    assert cand.scenario_hash == g0["scenario_hash"], "G0 hash drifted"

    res = evaluator.evaluate(cand, evaluator.make_config(
        {"flexible": {"enabled": False}}))
    anchor_rows = [
        {"anchor": "post_capture_rate_dps(live)", "expected": EXP_POST_RATE_DPS,
         "measured": res.post_capture_angular_velocity, "tol_rel": TOL_REL_LIVE},
        {"anchor": "H_RW_Nms(live)", "expected": EXP_H_RW_NMS,
         "measured": res.wheel_momentum_required, "tol_rel": TOL_REL_LIVE},
        {"anchor": "E_flex_J(csv)", "expected": EXP_E_FLEX_J,
         "measured": float(g0["E_flex_J"]), "tol_rel": TOL_REL_CSV},
    ]
    worst = 0.0
    for a in anchor_rows:
        a["residual_rel"] = _rel(a["measured"], a["expected"])
        worst = max(worst, a["residual_rel"])
        assert a["residual_rel"] < a["tol_rel"], \
            f"{a['anchor']}: {a['measured']!r} vs {a['expected']!r} " \
            f"(rel {a['residual_rel']:.3e} > {a['tol_rel']:.0e})"
    # live fast-path values must also match the CSV row bit-for-bit-ish
    csv_worst = max(_rel(res.post_capture_angular_velocity,
                         float(g0["post_capture_rate_dps"])),
                    _rel(res.wheel_momentum_required, float(g0["H_RW_Nms"])))
    assert csv_worst < TOL_REL_CSV, f"CSV/live mismatch {csv_worst:.3e}"

    return {"name": "t8_e1_regression", "passed": True, "worst_residual": worst,
            "rows": anchor_rows,
            "note": f"G0 anchors frozen; CSV integrity 72 rows / {n_adm} "
                    "admissible / hashes match deterministic grid"}


if __name__ == "__main__":
    out = run()
    for a in out["rows"]:
        print(f"{a['anchor']:28s} expected={a['expected']} "
              f"measured={a['measured']} rel={a['residual_rel']:.3e}")
    print("PASS | worst", f"{out['worst_residual']:.3e}")
