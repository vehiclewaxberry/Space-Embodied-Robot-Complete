"""WP12 derived-quantity and source-register computation.

Computes (a) real SHA-256 + byte size for every consumed file with hashlib, and
(b) every derived number quoted in the WP12 ruling artifacts, so that no value is
hand-transcribed. Output: probe/derived.json.
No CAD kernel is launched.
"""
import hashlib, json, math, os, subprocess, ctypes

ROOT = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
HERE = os.path.dirname(os.path.abspath(__file__))

SOURCES = [
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_EXECUTION_PLAN_V1.md",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/PRODUCT_STRUCTURE_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/KEEP_OUT_REGISTER_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/HARNESS_ROUTING_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/receipt.json",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.step",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp3_tolerance_alloc/TOLERANCE_CHAIN_REGISTER_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/HDRM_ENGINEERING_PACK_V1.yaml",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/SOLAR_HINGE_DEPLOYMENT_PACK_V1.yaml",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/06_supports/F3R2_SUPPORT_V2_DEFINITION.json",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_CAMERA_HARNESS_GRIPPER.json",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/B51_B601_ARTICULATED_ENGINEERING_ARM_STOWED_O13V.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Aft_Saddle.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Fwd_Saddle.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Mid_Saddle.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/04_ARM_STOW_SUPPORT.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Release_Clearance_Envelope.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Launch_Lock_Interface_Reference.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Hinge_Pin_Left.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Hinge_Pin_Right.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Hard_Stop_Left.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/Hard_Stop_Right.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_STOWED/WING_L_STOWED.stl",
 "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh/parts_DEPLOYED/WING_L_DEPLOYED.stl",
 "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
 "20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper/base_link.STL",
 "30_simulation/sim_13_physics_gated_embodied_grasping/assets/BOOTSTRAP_TEST_FRAME_TREE.json",
 "30_simulation/sim_13_physics_gated_embodied_grasping/evidence/SIM13_ENVIRONMENT_BOOTSTRAP_GATE.json",
 "30_simulation/sim_13_physics_gated_embodied_grasping/src/mechanical_asset_loader.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/read_saddles.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/arm_probe.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/g08_forensic.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/body_attrib.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/refine.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/step_probe.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/f2_f3.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/f3_section.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/group_check.py",
 "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication/probe/compute_derived.py",
]


def sha(rel):
    h = hashlib.sha256()
    n = 0
    with open(os.path.join(ROOT, rel), "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
    return {"path": rel, "sha256": h.hexdigest().upper(), "bytes": n}


def mem():
    class M(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = M()
    m.dwLength = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return round(m.ullAvailPhys / 2 ** 30, 6), round(m.ullTotalPhys / 2 ** 30, 6)


# ---------------------------------------------------------------- constants pinned from sources
FK = 567.734                # WP2 C05 Q_STOW_ENGINEERING_CANDIDATE retained fact
STEP_ZMAX = 247.908130023   # WP1 build report step_cold_reopen.bounding_box_mm[5]
ARM_MASS = 4.695555949342986
AL = 2700.0
WITNESS = 817.651847974
G07_PAD = 261.5016
G08_PAD = 208.4929
MID_PAD = 212.9189
G07_PRONG = 261.079987
G07_NOTCH = 258.08
G08_NOTCH = 206.42
MID_NOTCH = 211.92
G07_MIN_FOOT = 261.5015563964844
G07_MIN_PRONG_P = 262.0708312988281
G07_MIN_PRONG_M = 289.1963195800781
G08_MIN_FOOT = 204.1654663085938
MID_MIN_FOOT = 214.9189300537109
AXIS_Y = 143.15
PANEL_Y1 = 313.15
PANEL_T2 = 3.0
PANEL_M = 0.3483933
SPAN = 0.200
M_NET = 0.15
BUS_Y = 113.15

d = {}
d["timestamp_local"] = subprocess.check_output(["date", "-Iseconds"], text=True).strip()
av, tot = mem()
d["memory_gate"] = {"available_physical_gib": av, "total_physical_gib": tot, "threshold_gib": 6.0,
                    "memory_gate_passed": False, "measurement_status": "MEASURED"}

d["g08_native_overlap_depth_mm"] = round(G08_NOTCH - G08_MIN_FOOT, 6)
d["mid_true_clearance_to_existing_notch_floor_mm"] = round(MID_MIN_FOOT - MID_NOTCH, 6)
d["mid_v2_pad_face_above_existing_notch_floor_mm"] = round(MID_PAD - MID_NOTCH, 6)
d["g07_clear_above_plus_Y_prong_mm"] = round(G07_MIN_PRONG_P - G07_PRONG, 6)
d["g07_clear_above_minus_Y_prong_mm"] = round(G07_MIN_PRONG_M - G07_PRONG, 6)
d["g07_clear_above_notch_floor_mm"] = round(G07_MIN_FOOT - G07_NOTCH, 6)
d["g07_pad_face_above_assembly_zmax_mm"] = round(G07_PAD - STEP_ZMAX, 9)
d["g08_head_top_vs_existing_notch_floor_mm"] = round(206.4929 - G08_NOTCH, 6)
d["arm_solid_alu_equiv_volume_mm3"] = round(ARM_MASS / AL * 1e9, 3)
d["arm_witness_volume_ratio"] = round((ARM_MASS / AL * 1e9) / WITNESS, 1)
d["fk_ratio_vs_g07"] = round(FK / 0.425611, 1)
d["fk_ratio_vs_g08_declared"] = round(FK / 4.327434, 1)
d["fk_ratio_vs_g08_native"] = round(FK / d["g08_native_overlap_depth_mm"], 1)

# --- solar hinge / panel geometry
d["r_max_proxy_mm"] = math.sqrt((PANEL_Y1 - AXIS_Y) ** 2 + PANEL_T2 ** 2)
d["r_max_root_at_axis_mm"] = math.sqrt(200.0 ** 2 + PANEL_T2 ** 2)
d["proxy_inboard_straddle_mm"] = round(AXIS_Y - BUS_Y, 6)
d["proxy_outboard_reach_mm"] = round(PANEL_Y1 - AXIS_Y, 6)
d["ko03a_full_revolution_y_min_mm"] = round(AXIS_Y - d["r_max_proxy_mm"], 6)
d["ko03a_full_revolution_y_max_mm"] = round(AXIS_Y + d["r_max_proxy_mm"], 6)
d["ko03a_bus_intrusion_mm"] = round(BUS_Y - (AXIS_Y - d["r_max_proxy_mm"]), 6)
d["ko03b_sector_y_min_mm"] = round(AXIS_Y - PANEL_T2, 6)
d["ko03b_sector_y_max_mm"] = round(AXIS_Y + d["r_max_root_at_axis_mm"], 6)
d["ko03b_bus_clearance_mm"] = round((AXIS_Y - PANEL_T2) - BUS_Y, 6)
# axis implied by the native stowed<->deployed box pair
sy0 = 113.150002
dz0 = -3.0
z0 = (sy0 + (dz0 - sy0)) / 2.0
y0 = sy0 - z0
d["native_implied_axis_y_mm"] = y0
d["native_implied_axis_z_mm"] = z0
d["native_implied_axis_offset_from_declared_mm"] = round(math.hypot(y0 - AXIS_Y, z0 - 0.0), 6)
d["native_stowed_max_radius_about_declared_axis_mm"] = round(
    max(math.hypot(y - AXIS_Y, z) for y in (113.150002, 119.150002) for z in (-200.0, 0.0)), 6)
d["native_stowed_vs_neutral_deployed_radius_delta_mm"] = round(
    d["native_stowed_max_radius_about_declared_axis_mm"] - d["r_max_proxy_mm"], 6)
lam = PANEL_M / SPAN
d["I_root_at_axis_kg_m2"] = PANEL_M * SPAN * SPAN / 3.0
d["I_proxy_as_placed_kg_m2"] = lam * (0.170 ** 3 + 0.030 ** 3) / 3.0
d["I_relative_difference_pct"] = round(
    100.0 * (d["I_proxy_as_placed_kg_m2"] - d["I_root_at_axis_kg_m2"]) / d["I_root_at_axis_kg_m2"], 4)
th = math.pi / 2.0
d["t_undamped_root_at_axis_s"] = round(math.sqrt(2 * d["I_root_at_axis_kg_m2"] * th / M_NET), 6)
d["t_undamped_proxy_as_placed_s"] = round(math.sqrt(2 * d["I_proxy_as_placed_kg_m2"] * th / M_NET), 6)
d["stop_energy_J_inertia_independent"] = round(M_NET * th, 6)
d["tip_sensitivity_implied_moment_arm_mm"] = 0.2 / 1e-3

# --- harness station stack
d["harness_declared_connector_face_x_mm"] = 215.0
d["base_link_local_z_extent_mm"] = [0.0, 82.65]
d["base_link_global_x_extent_mm"] = [208.0, 290.65]
d["connector_face_z_local_mm"] = 215.0 - 208.0
d["connector_face_beyond_m3r_stack_max_mm"] = round(215.0 - 210.405, 6)
d["hc2_clamp_x_mm"] = 220.0
d["hc2_z_local_mm"] = 220.0 - 208.0
d["hc1_clamp_x_mm"] = 192.0

d["source_register"] = {s["path"]: s for s in (sha(p) for p in SOURCES)}
json.dump(d, open(os.path.join(HERE, "derived.json"), "w"), indent=1)
for k, v in d.items():
    if k != "source_register":
        print(k, "=", v)
print("source_register entries:", len(d["source_register"]))
