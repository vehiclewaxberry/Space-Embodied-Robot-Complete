import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
REL = ROOT/"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
LB = REL/"_work/loop_b"
M7 = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
now = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def ref(rel, cls, status):
    p = ROOT/rel
    return {"path": rel, "bytes": p.stat().st_size, "sha256": sha(p), "classification": cls, "status": status}

def dump_yaml(name, data):
    (REL/name).write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

def copy(src_rel, dst_name):
    shutil.copy(ROOT/src_rel, REL/dst_name)

# 05 accepted URDF ref
dump_yaml("05_ACCEPTED_B601_URDF_REF.yaml", {
 "schema":"ACCEPTED_B601_URDF_REF_V1","generated_utc":now,
 "accepted_urdf":ref("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf","CURRENT_HARDWARE_TRUTH","UNCHANGED"),
 "e_hw_joint_limits_rad":[[-2.8,2.8],[-3.14,0.0],[-3.14,0.0],[-1.87,1.57],[-1.57,1.57],[-3.14,3.14]],
 "modification":"FORBIDDEN","cad_mass_or_geometry_override_of_accepted_urdf":"FORBIDDEN",
 "unified_candidate":ref(M7+"/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf","EMITTED_2026_08_25","SOURCE_ONLY_BUILDER_EMISSION"),
 "generation_receipt":ref(M7+"/unified_r2_digital_prototype_prebind/generated_v2/UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json","EMITTED_2026_08_25","PENDING_OWNER_REVIEW"),
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 06 bridge
dump_yaml("06_PHYSICAL_DYNAMICS_BRIDGE.yaml", {
 "schema":"PHYSICAL_DYNAMICS_BRIDGE_REF_V1","generated_utc":now,
 "bridge":ref(M7+"/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml","CONFIRMED","CHECKPOINT_A_A02_PASS"),
 "bridge_gate":ref(M7+"/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json","CONFIRMED","PASS_9_OF_9"),
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 07 mass properties
dump_yaml("07_SYSTEM_MASS_PROPERTIES.yaml", {
 "schema":"SYSTEM_MASS_PROPERTIES_REF_V1","generated_utc":now,
 "nine_configuration_design_mass":ref(M7+"/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml","DESIGN_MODEL","CANDIDATE_ONLY_NOT_AS_BUILT"),
 "bridged_mass":ref(M7+"/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml","CONFIRMED_BRIDGE","CONSUMED_BY_E22_E23"),
 "authority_v2":ref("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/SYSTEM_MASS_PROPERTIES_AUTHORITY_V2.yaml","CDR_AUTHORITY","CURRENT"),
 "as_built_metrology":"HOLD_EXTERNAL_MEASUREMENT_PENDING",
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 09 M3R ICD
dump_yaml("09_M3R_ICD.yaml", {
 "schema":"M3R_ICD_REF_V1","generated_utc":now,
 "icd_v2":ref("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/MECHANICAL_INTERFACE_CONTROL_DOCUMENT_V2.yaml","CURRENT_ICD","AS_INSTALLED_METROLOGY_HOLD_EXTERNAL"),
 "mass_ruling":ref("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/M3R_MASS_RULING.json","CURRENT_RULING","ACTIVE"),
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 10 gripper interface (+ contact model annex)
dump_yaml("10_GRIPPER_INTERFACE.yaml", {
 "schema":"GRIPPER_INTERFACE_REF_V1","generated_utc":now,
 "actuation_interface":ref(M7+"/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml","CANDIDATE","PHYSICAL_LIMITS_NULL"),
 "geometry_validation":ref("20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json","DIGITAL_GEOMETRY","STROKE_0.0715M"),
 "design_contact_model":ref("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/DESIGN_CONTACT_MODEL_V1.yaml","BOUNDED_PROVISIONAL","PASS_BOUNDED_PROVISIONAL_STRUCTURE"),
 "design_contact_model_gate":ref("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/DESIGN_CONTACT_MODEL_GATE_V1.json","MACHINE_GATE","PASS"),
 "as_built_contact_model":"null MEASUREMENT_PENDING",
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 11 solar r2 mechanism
dump_yaml("11_SOLAR_R2_MECHANISM.yaml", {
 "schema":"SOLAR_R2_MECHANISM_REF_V1","generated_utc":now,
 "candidate_step":ref(M7+"/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step","CURRENT_HARDWARE_CANDIDATE","FROZEN"),
 "mechanism_ledger":ref(M7+"/ecr_solar_array_r2/SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml","CURRENT","ANALYTICAL"),
 "hdrm_latch_design":ref(M7+"/ecr_solar_array_r2/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml","CURRENT","DESIGN"),
 "deployment_torque_ledger":ref(M7+"/ecr_solar_array_r2/SOLAR_R2_DEPLOYMENT_TORQUE_LEDGER_V1.yaml","CURRENT","ANALYTICAL"),
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 13 R2 flex model
dump_yaml("13_R2_FLEX_MODEL.yaml", {
 "schema":"R2_FLEX_MODEL_REF_V1","generated_utc":now,
 "hf_model_v3":ref(M7+"/r2_full_flex_closure/round4_hf_rom_v3/R2_HF_MODEL_V3.yaml","CURRENT_HF","183_DOF_COMPONENT"),
 "seven_mode_rom_v3":ref(M7+"/r2_full_flex_closure/round4_hf_rom_v3/R2_SEVEN_MODE_ROM_V3.json","CURRENT_ROM","7D_B1_B3_T1_T4"),
 "rom_numerical_data_v3":ref(M7+"/r2_full_flex_closure/round4_hf_rom_v3/R2_HF_ROM_NUMERICAL_DATA_V3.npz","CURRENT_ROM_DATA","BINARY"),
 "hf_rom_gate_v3":ref(M7+"/r2_full_flex_closure/round4_hf_rom_v3/R2_FULL_FLEX_HF_ROM_GATE_V3.json","MACHINE_GATE","PASS_WITH_DECLARED_PROVISIONAL_PHYSICS_17_OF_17"),
 "validity_envelope_v3":ref(M7+"/r2_full_flex_closure/round4_hf_rom_v3/R2_FLEXIBILITY_VALIDITY_ENVELOPE_V3.json","CURRENT_ENVELOPE","LOW_NOMINAL_HIGH"),
 "historical_five_mode_v2":ref(M7+"/r2_full_flex_closure/round3_hf_rom_v2/R2_FIVE_MODE_ROM_V2.json","HISTORICAL_IMMUTABLE","SUPERSEDED_FOR_COUPLED"),
 "e23_recertification":"PENDING (30_simulation/e23_r2_full_flex_coupled_recert running)",
 "provisional_physics":"EI/GJ/k_theta/zeta PROVISIONAL_DERIVED bounded intervals; independent latch stiffness null",
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 12 harness mission envelope (current truth)
dump_yaml("12_HARNESS_MISSION_ENVELOPE.yaml", {
 "schema":"HARNESS_MISSION_ENVELOPE_REF_V1","generated_utc":now,
 "rated_envelope":ref(M7+"/ecr_b601_harness_rated_envelope/03_envelope/B601_HARNESS_RATED_ENVELOPE_V1.yaml","NOT_RELEASED","0_SAFE_SAMPLES"),
 "mission_coverage_gate":ref(M7+"/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json","CURRENT_GATE","FAIL_AT_MANDATORY_KEY_STATES"),
 "route_b":"REJECTED (full-range negative result frozen; reopening prohibited)",
 "route_c_odr42_record":ref(M7+"/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_OWNER_DECISION_RECORD_ODR42_V1.json","OWNER_DECISION","APPROVE_BOUNDED_DETAILED_DESIGN"),
 "route_c_full_range":"DEFERRED_HOLD",
 "mission_envelope_status":"OPEN_INTERNAL_DESIGN - physical Route-C mission-first dress-pack design is the remaining internal blocker for TMG-4",
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})

# 14 collision asset manifest
dump_yaml("14_COLLISION_ASSET_MANIFEST.json", {
 "schema":"COLLISION_ASSET_MANIFEST_V1","generated_utc":now,
 "broadphase":ref("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json","BROAD_PHASE_ONLY","CURRENT"),
 "narrow_phase":{"status":"ABSENT","required_for":"SIM13_CONTACT_GRASP_GATE_V2 (NC19)"},
 "keepout_plan":ref("20_engineering/design_inputs/v2_system_mechanical/04_subsystem_layout/V2_serviceability_and_keepout_plan.md
