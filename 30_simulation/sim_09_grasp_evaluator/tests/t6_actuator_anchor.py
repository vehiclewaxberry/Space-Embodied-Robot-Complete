"""t6 -- actuator budget anchor: the adapter's algebraic outputs, rounded with
the SAME rounding as sim_08 (H:5, tau:6, F:6, J:4, m_p:4 decimals), must equal
DIGIT FOR DIGIT the corresponding rows of the frozen
30_simulation/sim_08_detumble_actuator_budget/results/actuator_budget_sweep.csv.

Rows checked (target_debris_v0 @ 3.0 deg/s; the 36.4998 g row is mandatory):
    (t_d=900,  lever=0.17, cold_gas_60s)   -> propellant 36.4998 g   [mandatory]
    (t_d=900,  lever=0.17, green_mono_220s)-> propellant  9.9545 g
    (t_d=60,   lever=0.05, cold_gas_60s)   -> propellant 124.0992 g
|H_c| itself comes from the sim_09 capture adapter (legacy_v0, nominal
candidate) -- so this test cross-checks capture + actuator algebra + CSV.
"""
import _helpers
import csv
import os
import numpy as np

import adapters
import target_propagation
from evaluator import DEFAULT_CONFIG

CSV_PATH = os.path.join(_helpers.REPO_ROOT, "sim", "sim_08_detumble_actuator_budget",
                        "results", "actuator_budget_sweep.csv")
ROWS = [(900.0, 0.17, "cold_gas_60s"),
        (900.0, 0.17, "green_mono_220s"),
        (60.0, 0.05, "cold_gas_60s")]


def _csv_row(t_d, lever, isp_class):
    with open(CSV_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["target"] == "target_debris_v0"
                    and float(r["tumble_dps"]) == 3.0
                    and float(r["t_detumble_s"]) == t_d
                    and float(r["lever_m"]) == lever
                    and r["isp_class"] == isp_class):
                return r
    raise KeyError((t_d, lever, isp_class))


def run():
    cand = _helpers.nominal_candidate()
    prop = target_propagation.propagate(cand.target_state,
                                        cand.grasp_pose_target[:3, 3],
                                        cand.capture_time)
    placement = adapters.scene_placement(cand, prop,
                                         DEFAULT_CONFIG["scenario"]["capture_point_S"])
    cap = adapters.capture_adapter(cand, prop, placement, chaser_mode="legacy_v0")
    H = cap["H_c_norm_Nms"]

    worst = 0.0
    rows_out = []
    mandatory_seen = False
    for t_d, lever, isp_class in ROWS:
        act = adapters.actuator_adapter(H, t_d, lever, isp_class)
        got = {"H_Nms": round(H, 5),
               "torque_Nm": round(act["torque_Nm"], 6),
               "thruster_force_N": round(act["thruster_force_N"], 6),
               "total_impulse_Ns": round(act["total_impulse_Ns"], 4),
               "propellant_g": round(act["propellant_selected_g"], 4)}
        ref_raw = _csv_row(t_d, lever, isp_class)
        ref = {"H_Nms": float(ref_raw["H_Nms"]),
               "torque_Nm": float(ref_raw["torque_Nm"]),
               "thruster_force_N": float(ref_raw["thruster_force_N"]),
               "total_impulse_Ns": float(ref_raw["total_impulse_Ns"]),
               "propellant_g": float(ref_raw["propellant_g"])}
        for k in got:
            d = abs(got[k] - ref[k])
            worst = max(worst, d)
            assert d == 0.0, (f"row (t_d={t_d}, l={lever}, {isp_class}) field {k}: "
                              f"adapter {got[k]!r} != CSV {ref[k]!r}")
        if ref["propellant_g"] == 36.4998:
            mandatory_seen = True
        rows_out.append({"row": f"t_d={t_d:.0f}s l={lever} {isp_class}",
                         "expected_propellant_g": ref["propellant_g"],
                         "measured_propellant_g": got["propellant_g"],
                         "residual": abs(got["propellant_g"] - ref["propellant_g"])})
    assert mandatory_seen, "mandatory 36.4998 g row not covered"
    return {"name": "t6_actuator_anchor", "passed": True, "worst_residual": worst,
            "rows": rows_out, "H_used_Nms": H,
            "note": "digit-exact vs actuator_budget_sweep.csv (sim_08 rounding applied)"}


if __name__ == "__main__":
    out = run()
    print(f"|H_c| from capture adapter: {out['H_used_Nms']:.10f} N*m*s")
    for r in out["rows"]:
        print(f"{r['row']:34s} propellant expected {r['expected_propellant_g']:9.4f} g  "
              f"measured {r['measured_propellant_g']:9.4f} g  residual {r['residual']:.1e}")
    print("PASS | worst", f"{out['worst_residual']:.3e}")
