import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import yaml

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
R = ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b"
M7 = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"

def sha(rel):
    return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest().upper()

def art(rel, cls, status, note=""):
    p = ROOT/rel
    rec = {"path": rel, "bytes": p.stat().st_size, "sha256": sha(rel), "classification": cls, "status": status}
    if note: rec["note"] = note
    return rec

ui = {
 "schema": "UNIFIED_R2_SYSTEM_INTERFACE_V1",
 "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
 "owner_directive": "OWNER DIRECTIVE - TERMINAL MECHANICAL ONE-SHOT CLOSURE (2026-08-25), item 1: one UNIFIED_R2_SYSTEM_INTERFACE binding the current system truth; consumers must not hunt M7/R2/WP11/ODR-01/legacy URDF separately",
 "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
 "fail_closed_invariants": ["UNKNOWN is never PASS", "null is never zero-filled", "a test PASS is not a design Gate PASS", "hash_mismatch aborts consumption"],
 "configuration": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
 "bindings": {
  "accepted_b601_urdf": art("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", "CURRENT_HARDWARE_TRUTH", "UNCHANGED", "E_HW joint limits; modification FORBIDDEN"),
  "system_urdf_candidate": art(M7+"/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf", "EMITTED_THIS_CLOSURE", "SOURCE_ONLY_BUILDER_EMISSION", "19-link Unified-R2 C01 candidate; see urdf_generation_receipt for emission class and documented defect TMC-F01"),
  "urdf_generation_receipt": art(M7+"/unified_r2_digital_prototype_prebind/generated_v2/UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json", "EMITTED_THIS_CLOSURE", "PENDING_OWNER_REVIEW"),
  "system_frame_tree": art(M7+"/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml", "SOURCE_ONLY", "FROZEN"),
  "mpi_physical_to_dynamics_bridge": art(M7+"/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml", "CONFIRMED", "CHECKPOINT_A_A02_PASS"),
  "mpi_bridge_gate": art(M7+"/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json", "CONFIRMED", "PASS_9_OF_9"),
  "solar_r2": art(M7+"/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step", "CURRENT_HARDWARE_CANDIDATE", "FROZEN", "three-leaf/wing R2; modification FORBIDDEN"),
  "solar_r2_modes_hf": art(M7+"/r2_full_flex_closure/round4_hf_rom_v3/R2_SEVEN_MODE_ROM_V3.json", "CURRENT_ROM", "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS_17_OF_17", "7D B1-B3+T1-T4 per-wing ROM; supersedes five-mode V2 for coupled recertification (V2 immutable historical)"),
  "gripper_r1_interface": art(M7+"/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml", "CANDIDATE", "PHYSICAL_LIMITS_NULL"),
  "design_contact_model": art("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/DESIGN_CONTACT_MODEL_V1.yaml", "BOUNDED_PROVISIONAL", "PASS_BOUNDED_PROVISIONAL_STRUCTURE", "T4: every field nominal/lower/upper/authority/source/confidence; AS_BUILT=null MEASUREMENT_PENDING"),
  "m3r_icd": art("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/MECHANICAL_INTERFACE_CONTROL_DOCUMENT_V2.yaml", "CURRENT_ICD", "AS_INSTALLED_METROLOGY_HOLD_EXTERNAL"),
  "nine_configuration_mass_properties": art(M7+"/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml", "DESIGN_MODEL", "CANDIDATE_ONLY_NOT_AS_BUILT"),
  "harness_rated_envelope": art(M7+"/ecr_b601_harness_rated_envelope/03_envelope/B601_HARNESS_RATED_ENVELOPE_V1.yaml", "NOT_RELEASED", "0_SAFE_SAMPLES_MISSION_COVERAGE_FAIL", "TMG-4 open; see route_c_odr42_record"),
  "harness_mission_coverage_gate": art(M7+"/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json", "CURRENT_GATE", "FAIL_AT_MANDATORY_KEY_STATES"),
  "route_c_odr42_record": art(M7+"/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_OWNER_DECISION_RECORD_ODR42_V1.json", "OWNER_DECISION", "APPROVE_BOUNDED_DETAILED_DESIGN", "mission-first bounded design approved; full-range DEFERRED_HOLD"),
  "collision_broadphase": art("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json", "BROAD_PHASE_ONLY", "NARROW_PHASE_ABSENT"),
  "embodied_contract": art(M7+"/wp13_embodied_contract/EMBODIED_MECHANICAL_CONTRACT_R2.yaml", "CURRENT_CONTRACT", "HANDOFF_V2_FAILS_ON_G12_HARNESS"),
  "e22_coupled_gate": art("30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_FULL_FLEX_COUPLED_GATE_V1.json", "HISTORICAL", "HOLD_16_OF_18_G11_G17", "superseded by E23 recertification when E23 gate issues"),
  "e15_gate": art("30_simulation/e15_ancf_certification/results/gate_summary.json", "CURRENT_GATE", "REPEAT_ANCF_CERTIFICATION", "recertification follows E23 pass"),
 },
 "route_c_disposition": {"selection": "EXCLUDED_RESEARCH_CANDIDATE", "basis": "ODR-42 bounded mission-first approval; Route-C is not in the current C01 sim candidate; full-range DEFERRED_HOLD"},
 "failure_state_registry": {
   "artifact_class": "SINGLE_FAILURE_STATE_REGISTRY",
   "states": {
     "UNKNOWN": {"policy": "NEVER_PASS; masks to ABORT_ONLY at runtime"},
     "ABORT_ONLY": {"policy": "maximum current operational state of Sim13 v2 (15/20 NC prebind)"},
     "HOLD": {"policy": "blocks promotion; requires named authority to lift"},
     "MEASUREMENT_PENDING": {"policy": "as-built quantity absent; never substituted by design value in as-built contexts"},
     "DEFERRED_HOLD": {"policy": "owner-decided deferral; reopen only on named trigger"},
   },
 },
 "external_only_holds": ["launcher/deployer ICD", "separation ICD", "flight material allowables", "as-built mass/CG/inertia metrology", "hardware contact calibration (CT01-CT05, gripper closing time, F/T)", "qualification vibration", "TVAC", "flight HDRM reliability", "full-range Route-C harness enhancement (DEFERRED_HOLD)", "SolidWorks native reintegration"],
 "documented_defects": [{"id": "TMC-F01", "summary": "gen_urdf runtime-code marshal fingerprint unstable on available CPython interpreters; URDF emitted via designed source-only builder path with full disclosure; Red Team adjudication required"}],
 "review_status": "PENDING_OWNER_REVIEW",
 "next_stage_authorized": False,
 "release_credit": False,
}
out = R/"UNIFIED_R2_SYSTEM_INTERFACE_V1.yaml"
out.write_text(yaml.safe_dump(ui, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("unified interface written:", out.name, "sha:", hashlib.sha256(out.read_bytes()).hexdigest().upper()[:24])
