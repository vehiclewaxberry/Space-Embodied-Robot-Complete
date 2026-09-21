import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
import yaml
ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
REL = ROOT/"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
M7 = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
now = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def ref(rel, cls, status):
    p = ROOT/rel
    return {"path": rel, "bytes": p.stat().st_size, "sha256": sha(p), "classification": cls, "status": status}
def dump_yaml(name, data):
    (REL/name).write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
dump_yaml("05_ACCEPTED_B601_URDF_REF.yaml", {
 "schema":"ACCEPTED_B601_URDF_REF_V1","generated_utc":now,
 "accepted_urdf":ref("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf","CURRENT_HARDWARE_TRUTH","UNCHANGED"),
 "e_hw_joint_limits_rad":[[-2.8,2.8],[-3.14,0.0],[-3.14,0.0],[-1.87,1.57],[-1.57,1.57],[-3.14,3.14]],
 "modification":"FORBIDDEN","cad_mass_or_geometry_override_of_accepted_urdf":"FORBIDDEN",
 "unified_candidate":ref(M7+"/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf","EMITTED_2026_08_25","SOURCE_ONLY_BUILDER_EMISSION"),
 "generation_receipt":ref(M7+"/unified_r2_digital_prototype_prebind/generated_v2/UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json","EMITTED_2026_08_25","PENDING_OWNER_REVIEW"),
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})
dump_yaml("06_PHYSICAL_DYNAMICS_BRIDGE.yaml", {
 "schema":"PHYSICAL_DYNAMICS_BRIDGE_REF_V1","generated_utc":now,
 "bridge":ref(M7+"/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml","CONFIRMED","CHECKPOINT_A_A02_PASS"),
 "bridge_gate":ref(M7+"/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json","CONFIRMED","PASS_9_OF_9"),
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})
dump_yaml("07_SYSTEM_MASS_PROPERTIES.yaml", {
 "schema":"SYSTEM_MASS_PROPERTIES_REF_V1","generated_utc":now,
 "nine_configuration_design_mass":ref(M7+"/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml","DESIGN_MODEL","CANDIDATE_ONLY_NOT_AS_BUILT"),
 "bridged_mass":ref(M7+"/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml","CONFIRMED_BRIDGE","CONSUMED_BY_E22_E23"),
 "authority_v2":ref("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/SYSTEM_MASS_PROPERTIES_AUTHORITY_V2.yaml","CDR_AUTHORITY","CURRENT"),
 "as_built_metrology":"HOLD_EXTERNAL_MEASUREMENT_PENDING",
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})
dump_yaml("09_M3R_ICD.yaml", {
 "schema":"M3R_ICD_REF_V1","generated_utc":now,
 "icd_v2":ref("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/MECHANICAL_INTERFACE_CONTROL_DOCUMENT_V2.yaml","CURRENT_ICD","AS_INSTALLED_METROLOGY_HOLD_EXTERNAL"),
 "mass_ruling":ref("20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/M3R_MASS_RULING.json","CURRENT_RULING","ACTIVE"),
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False})
print("s1 done")
