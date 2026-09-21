"""WP5_MECHANISM_ANALYTIC_CALC_V1

Reproducible analytic calculations behind the three WP5 mechanism packs
(HDRM / solar hinge / gripper). Pure Python, no third-party imports, low
memory. All outputs are DESIGN_TARGET_CANDIDATE / DERIVED values, not test
results and not flight authority.

Run: python WP5_MECHANISM_ANALYTIC_CALC_V1.py
"""
import math

# Pinned contract inputs (M7_EXECUTION_PLAN_V1.md)
M_PANEL = 0.3483933            # kg, solar panel each (contract)
L_SPAN = 0.200                 # m, panel span (contract, flexible_appendage_v1 span_L_m=0.200)
CHORD = 0.227                  # m, panel chord (contract)
M_ARM = 4.695555949342986      # kg, B601 ACCEPTED_URDF (L0, never overridden)
# CDR capture anchors (DERIVED, research-bound; sim_06 capture_impulse_matrix_v0.csv)
J22 = (0.0601233, 0.360622)    # N*s contact impulse range, 22 kg / 0.5 dps
J150 = (0.274973, 0.677633)    # N*s, 150 kg / 3 dps
C22 = (0.00151536, 0.00152744)   # N*m*s grasp couple range
C150 = (0.111944, 0.130197)
LEVER22 = 0.25173              # m grasp lever arm
LEVER150 = 1.21521
POST_RATE22_DPS = 0.231205     # post-capture rate at CAP22_030
POST_RATE150_DPS = 3.06561     # at CAP150_005 (max of family)
# V5 HDRM candidates via CDR AUTHORIZED_MECHANICAL_LOADS_V1 (PROVISIONAL)
HDRM_PRELOAD_CAND_N = 50.0
HDRM_STROKE_CAND_MM = 6.0
# URDF model limits (MODEL LIMIT, not design/qualification load)
GRIPPER_EFFORT_LIMIT_N = 100.0
GRIPPER_VELOCITY_LIMIT_MM_S = 15.0
GRIPPER_STROKE_MM = 71.5
PREGRASP_TRAVEL_MM = 55.0

def solar_hinge():
    I = M_PANEL * L_SPAN**2 / 3.0          # uniform plate about root hinge line
    theta = math.radians(90.0)             # candidate deploy angle
    M_spring, M_fric, M_harn = 0.20, 0.02, 0.03   # N*m candidates
    M_res = M_fric + M_harn
    M_net = M_spring - M_res
    margin = M_spring / M_res
    t = math.sqrt(2 * I * theta / M_net)   # undamped lower bound on time
    w = math.sqrt(2 * M_net * theta / I)   # undamped upper bound on rate
    KE = M_net * theta
    t_tgt = 2.0                            # damped candidate target
    w_term = theta / t_tgt
    c_damp = M_net / w_term
    crush = math.radians(0.5)              # stop crush angle candidate
    M_stop = KE / crush
    F_tip = M_stop / L_SPAN
    return dict(I_root=I, drive_margin=margin, t_undamped=t, omega_end=w,
                KE=KE, tip_speed_undamped=w * L_SPAN, c_damp=c_damp,
                omega_term=w_term, tip_speed_damped=w_term * L_SPAN,
                M_stop_avg=M_stop, F_tip_equiv=F_tip,
                root_shear_1g=M_PANEL * 9.80665,
                root_moment_1g=M_PANEL * 9.80665 * L_SPAN / 2)

def gripper():
    out = {}
    for dt in (0.05, 0.1):
        out[f"F22_dt{dt}"] = (J22[0] / dt, J22[1] / dt)
        out[f"F150_dt{dt}"] = (J150[0] / dt, J150[1] / dt)
        out[f"M22_dt{dt}"] = C22[1] / dt
        out[f"M150_dt{dt}"] = C150[1] / dt
    mu = 0.3                                # candidate contact friction
    F_lat = J150[1] / 0.05                  # worst DERIVED quasi-static lateral
    N_req = F_lat / (2 * mu)
    w150 = math.radians(POST_RATE150_DPS)
    F_cent = 150.0 * w150**2 * LEVER150
    w22 = math.radians(POST_RATE22_DPS)
    F_cent22 = 22.0 * w22**2 * LEVER22
    mu_rail = 0.15                          # candidate rail friction coefficient
    F_rail = mu_rail * N_req
    demand = N_req + F_rail
    out.update(mu_contact_cand=mu, N_req_per_finger=N_req,
               F_centripetal_150=F_cent, N_cent_per_finger=F_cent / (2 * mu),
               F_centripetal_22=F_cent22,
               mu_rail_cand=mu_rail, F_rail_per_finger=F_rail,
               actuator_demand_per_finger=demand,
               drive_margin_vs_urdf_model_limit=GRIPPER_EFFORT_LIMIT_N / demand,
               stroke_time_at_model_velocity_s=GRIPPER_STROKE_MM / GRIPPER_VELOCITY_LIMIT_MM_S,
               pregrasp_time_at_model_velocity_s=PREGRASP_TRAVEL_MM / GRIPPER_VELOCITY_LIMIT_MM_S)
    return out

def hdrm():
    E = 0.5 * HDRM_PRELOAD_CAND_N * HDRM_STROKE_CAND_MM / 1000.0
    rows = {}
    for g in (1.0, 5.0):
        F_dem = M_ARM * g * 9.80665
        rows[f"demand_{g}g"] = dict(F_demand_N=F_dem,
                                    preload_over_demand=HDRM_PRELOAD_CAND_N / F_dem,
                                    per_fastener_direct_M3R_4x=F_dem / 4,
                                    per_fastener_direct_StageAB_8x=F_dem / 8)
    return dict(release_energy_J=E, **rows)

if __name__ == "__main__":
    import json
    print(json.dumps(dict(solar_hinge=solar_hinge(), gripper=gripper(),
                          hdrm=hdrm()), indent=2, default=str))
