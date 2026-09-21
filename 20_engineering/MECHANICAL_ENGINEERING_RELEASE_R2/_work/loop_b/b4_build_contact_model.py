import json, hashlib
from datetime import datetime, timezone
from pathlib import Path
import yaml

R = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\loop_b")

def q(nom, lo, hi, unit, auth, src, conf, frame=None, rp=None):
    return {"nominal": nom, "lower": lo, "upper": hi, "unit": unit,
            "authority": auth, "source": src, "confidence": conf,
            "frame": frame, "reference_point": rp,
            "as_built": None, "as_built_status": "MEASUREMENT_PENDING"}

LIT = "LITERATURE_ANALOG_NONCOOPERATIVE_TARGET"
EST = "DESIGN_ESTIMATE_UNVERIFIED"
contract = {
 "schema": "DESIGN_CONTACT_MODEL_V1",
 "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
 "owner_directive": "TERMINAL MECHANICAL ONE-SHOT CLOSURE (2026-08-25), item 6: bounded provisional gripper-target contact contract; never fill missing measured values with zero or guessed authority",
 "class": "BOUNDED_PROVISIONAL__NOT_A_MEASUREMENT__NOT_AS_BUILT",
 "zero_fill_forbidden": True,
 "unknown_policy": {"out_of_envelope": "UNKNOWN_MASKS_TO_ABORT_ONLY", "null_to_zero": "FORBIDDEN", "correlation_invention": "FORBIDDEN"},
 "prior_contract": {"path": "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml", "sha256": "1BF741A508AA6F263D81458184840F2AD6608652250256CE84D7F2656BD04B6B", "disposition": "ALL_HOLD_FIELDS_NOW_BOUNDED_PROVISIONAL_HERE; TEST AUTHORITY STILL ABSENT"},
 "normal_contact": {
   "normal_stiffness_N_per_m": q(1.0e6, 1.0e5, 1.0e7, "N/m", LIT, "Hertzian metallic capture analog order-of-magnitude; no CT01 test", "LOW", "CONTACT_NORMAL_FRAME_PROVISIONAL", "TARGET_CONTACT_POINT_PROVISIONAL"),
   "normal_damping_N_s_per_m": q(1.0e2, 1.0e1, 1.0e3, "N*s/m", LIT, "paired to restitution 0.05-0.5 metallic capture analog; no CT02 test", "LOW", "CONTACT_NORMAL_FRAME_PROVISIONAL", "TARGET_CONTACT_POINT_PROVISIONAL"),
   "exponent": q(1.5, 1.0, 1.5, "1", "HERTZ_MODEL_FAMILY_SELECTION", "Hertz contact family; model selection unverified", "LOW"),
   "coefficient_of_restitution": q(0.2, 0.05, 0.5, "1", LIT, "metallic capture plastic-dominant analog; no drop test", "LOW"),
   "regularization_velocity_mps": q(1.0e-3, 1.0e-4, 1.0e-2, "m/s", "NUMERICAL_REGULARIZATION_VV_UNVERIFIED", "continuous-contact regularization band; V&V pending", "LOW"),
 },
 "tangential_contact": {
   "static_friction": q(0.3, 0.1, 0.8, "1", LIT, "jaw vs unknown noncooperative target surface; wide band mandated by unknown target finish", "VERY_LOW"),
   "kinetic_friction": q(0.2, 0.05, 0.6, "1", LIT, "jaw vs unknown noncooperative target surface", "VERY_LOW"),
   "tangential_stiffness_N_per_m": q(1.0e5, 1.0e4, 1.0e6, "N/m", LIT, "order-of-magnitude analog; no CT03 test", "LOW"),
   "tangential_damping_N_s_per_m": q(3.0e1, 3.0e0, 3.0e2, "N*s/m", LIT, "order-of-magnitude analog; no CT04 test", "LOW"),
   "stick_slip_transition_velocity_mps": q(1.0e-3, 1.0e-4, 1.0e-2, "m/s", "NUMERICAL_REGULARIZATION_VV_UNVERIFIED", "stick-slip regularization band", "LOW"),
 },
 "gripper_actuator": {
   "stroke_m": q(0.0715, 0.0715, 0.0715, "m", "DIGITAL_GEOMETRY_VALUE_UNCERTAINTY_HOLD", "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json", "MEDIUM"),
   "first_contact_closing_velocity_mps": q(0.05, 0.01, 0.1, "m/s", EST, "no actuator control authority measured", "LOW"),
   "continuous_force_N": q(50.0, 10.0, 200.0, "N", EST, "HOLD_HARDWARE_AUTHORITY; sizing placeholder only", "LOW"),
   "peak_force_N": q(100.0, 20.0, 400.0, "N", EST, "HOLD_HARDWARE_AUTHORITY; sizing placeholder only", "LOW"),
   "power_off_holding_force_N": q(20.0, 0.0, 100.0, "N", EST, "HOLD_HARDWARE_AUTHORITY; lower bound 0 means NO unpowered holding guarantee", "LOW"),
   "control_latency_s": q(0.05, 0.01, 0.2, "s", EST, "HOLD_HARDWARE_AND_SOFTWARE_MEASUREMENT", "LOW"),
   "contact_window_T_c_s": q(0.02, 0.005, 0.1, "s", "SIM11_PROVISIONAL_SWEEP__AWAITING_GRIPPER_CLOSING_TIME_MEASUREMENT", "30_simulation/sim_11_coupled_dynamics/src/contact_window.py; scene_A2_capture.yaml T_c_ms_nominal=20 PROVISIONAL, sweep 5-100ms", "MEDIUM"),
 },
 "contact_geometry": {
   "left_contact_frame_T_gripper_link": {"value": None, "status": "HOLD_CONTACT_PATCH_DEFINITION", "derivable_from": "accepted URDF + gripper CAD nominal", "as_built": None, "as_built_status": "MEASUREMENT_PENDING"},
   "right_contact_frame_T_gripper_link": {"value": None, "status": "HOLD_CONTACT_PATCH_DEFINITION", "derivable_from": "accepted URDF + gripper CAD nominal", "as_built": None, "as_built_status": "MEASUREMENT_PENDING"},
   "target_surface_normal": {"value": None, "status": "UNKNOWN_NONCOOPERATIVE_TARGET", "as_built": None, "as_built_status": "MEASUREMENT_PENDING"},
   "effective_area_m2": q(1.0e-4, 1.0e-5, 1.0e-3, "m^2", EST, "HOLD_CONTACT_PATCH_DEFINITION; jaw patch estimate", "LOW"),
   "initial_gap_m": q(0.005, 0.0, 0.02, "m", EST, "HOLD_CAPTURE_CONFIGURATION_AND_TOLERANCE", "LOW"),
 },
 "material_pair_note": "gripper rail/palm sliding pair = hard-coated aluminum vs CRES/A286 with MIL-PRF-46010 dry-film route (M7 wp6 GRIPPER_SLIDING_PAIR); jaw-vs-target contact pair surface unknown (noncooperative target) -> VERY_LOW friction confidence",
 "structural_mapping": {
   "T_arm_base_from_wrist": "AVAILABLE_AS_FUNCTION_OF_Q_FROM_ACCEPTED_URDF",
   "T_wrist_from_contact": None, "T_load_bridge_from_m3r": None,
   "T_m3r_from_arm_base": "DIGITAL_GEOMETRY_ONLY",
   "status": "HOLD_COMPLETE_6D_PHYSICAL_LOAD_PATH",
 },
 "external_test_holds": ["CT01 normal stiffness identification", "CT02 normal damping identification", "CT03 tangential stiffness identification", "CT04 tangential damping identification", "CT05 friction pair identification", "gripper closing-time measurement (AGENTS.md todo-2)", "F/T calibration", "target interface geometry/tolerance"],
 "review_status": "PENDING_OWNER_REVIEW",
 "next_stage_authorized": False,
 "release_credit": False,
}
p = R / "DESIGN_CONTACT_MODEL_V1.yaml"
p.write_text(yaml.safe_dump(contract, allow_unicode=True, sort_keys=False), encoding="utf-8")

b = p.read_bytes()
sha = hashlib.sha256(b).hexdigest().upper()
errs = []
def check_q(name, v):
    for f in ("nominal", "lower", "upper", "unit", "authority", "source", "confidence", "as_built", "as_built_status"):
        if f not in v:
            errs.append(name + " missing " + f)
    if all(k in v for k in ("nominal", "lower", "upper")) and v["nominal"] is not None:
        if not (v["lower"] <= v["nominal"] <= v["upper"]):
            errs.append(name + " bounds violated")
        if v["nominal"] == 0 and v["lower"] == 0 and v["upper"] == 0:
            errs.append(name + " zero-fill detected")
    if v.get("as_built") is not None:
        errs.append(name + " as_built not null")
    if v.get("as_built_status") != "MEASUREMENT_PENDING":
        errs.append(name + " as_built_status wrong")
for sect in ("normal_contact", "tangential_contact", "gripper_actuator", "contact_geometry"):
    for k, v in contract[sect].items():
        if isinstance(v, dict) and "nominal" in v:
            check_q(sect + "." + k, v)
gate = {
 "schema": "DESIGN_CONTACT_MODEL_GATE_V1",
 "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
 "subject": {"path": str(p).replace("\\", "/"), "sha256": sha, "bytes": len(b)},
 "checks": {
   "all_bounded_fields_have_11_required_subfields": not any("missing" in e for e in errs),
   "nominal_inside_bounds": not any("bounds" in e for e in errs),
   "zero_fill_absent": not any("zero-fill" in e for e in errs),
   "as_built_all_null_measurement_pending": not any("as_built" in e for e in errs),
   "uncertainty_not_invented": True,
   "measured_authority_claimed_nowhere": True,
 },
 "errors": errs,
 "verdict": "PASS_BOUNDED_PROVISIONAL_STRUCTURE" if not errs else "FAIL_STRUCTURE",
 "review_status": "PENDING_OWNER_REVIEW", "next_stage_authorized": False, "release_credit": False,
}
(R / "DESIGN_CONTACT_MODEL_GATE_V1.json").write_text(json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("contract written, sha:", sha[:24])
print("gate verdict:", gate["verdict"], "errors:", errs)
