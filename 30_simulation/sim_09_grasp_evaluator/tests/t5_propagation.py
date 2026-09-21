"""t5 -- target propagation invariants:

  P1 |r_g - r_T| constant over t_c            (< 1e-12, rigid-body distance)
  P2 v_g consistent with central difference   (< 1e-8, h = 1e-3 s)
  P3 t_c = one full period returns the initial grasp position (< 1e-9)
  P4 torque_free mode == const_omega for an AXISYMMETRIC body in pure spin
     about the symmetry axis (< 1e-9 on R_T, r_g, v_g)
"""
import _helpers
import numpy as np

import target_propagation as tp

TOL_P1, TOL_P2, TOL_P3, TOL_P4 = 1e-12, 1e-8, 1e-9, 1e-9


def run():
    st = {"omega_dps": 3.0, "tumble_axis": [1.0, 0.15, 0.4],
          "attitude0_quat": [1.0, 0.0, 0.0, 0.0]}
    r_gT = np.array([0.65973, 0.0, 1.02054])
    w = tp.omega_inertial(st)
    r0 = float(np.linalg.norm(r_gT))

    # P1 lever-arm invariance
    worst1 = 0.0
    for t_c in (0.0, 1.7, 12.3, 60.0, 240.0):
        p = tp.propagate(st, r_gT, t_c)
        worst1 = max(worst1, abs(float(np.linalg.norm(p["r_g_I"])) - r0))
    assert worst1 < TOL_P1, f"P1 lever drift {worst1:.3e}"

    # P2 velocity vs central difference
    worst2 = 0.0
    h = 1e-3
    for t_c in (0.0, 5.0, 37.5, 111.0):
        pm = tp.propagate(st, r_gT, t_c - h)
        pp = tp.propagate(st, r_gT, t_c + h)
        v_fd = (pp["r_g_I"] - pm["r_g_I"]) / (2.0 * h)
        p = tp.propagate(st, r_gT, t_c)
        worst2 = max(worst2, float(np.max(np.abs(v_fd - p["v_g_I"]))))
    assert worst2 < TOL_P2, f"P2 velocity mismatch {worst2:.3e}"

    # P3 full-period return
    T_spin = 2.0 * np.pi / float(np.linalg.norm(w))
    p0 = tp.propagate(st, r_gT, 0.0)
    pT = tp.propagate(st, r_gT, T_spin)
    worst3 = float(np.max(np.abs(pT["r_g_I"] - p0["r_g_I"])))
    assert worst3 < TOL_P3, f"P3 period return {worst3:.3e}"

    # P4 torque-free == const-omega for axisymmetric pure spin about +Z
    st_z = {"omega_dps": 3.0, "tumble_axis": [0.0, 0.0, 1.0],
            "attitude0_quat": [1.0, 0.0, 0.0, 0.0]}
    I_axi = np.diag([50.0, 50.0, 20.0])
    worst4 = 0.0
    for t_c in (7.0, 40.0):
        pc = tp.propagate(st_z, r_gT, t_c, mode="const_omega")
        pt = tp.propagate(st_z, r_gT, t_c, mode="torque_free", target_I=I_axi)
        worst4 = max(worst4,
                     float(np.max(np.abs(pc["R_T"] - pt["R_T"]))),
                     float(np.max(np.abs(pc["r_g_I"] - pt["r_g_I"]))),
                     float(np.max(np.abs(pc["v_g_I"] - pt["v_g_I"]))))
    assert worst4 < TOL_P4, f"P4 torque-free vs const-omega {worst4:.3e}"

    worst = max(worst1, worst2, worst3, worst4)
    return {"name": "t5_propagation", "passed": True, "worst_residual": worst,
            "rows": [
                {"check": "P1_lever_invariance", "residual": worst1, "tol": TOL_P1},
                {"check": "P2_central_difference", "residual": worst2, "tol": TOL_P2},
                {"check": "P3_full_period_return", "residual": worst3, "tol": TOL_P3},
                {"check": "P4_torque_free_vs_const", "residual": worst4, "tol": TOL_P4}],
            "note": "const-omega analytic model + validated rigid_body torque-free core"}


if __name__ == "__main__":
    out = run()
    for r in out["rows"]:
        print(f"{r['check']:26s} residual {r['residual']:.3e} (tol {r['tol']:.0e})")
    print("PASS | worst", f"{out['worst_residual']:.3e}")
