"""705-instance responsibility partition and mass-source reconciliation, no CAD/hardware.
Writes only system_completion/mass and results/MASS_ASSIGNMENT.json.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, math, re, sys, datetime
sys.dont_write_bytecode = True
C=Path(__file__).resolve().parents[1]; R=C.parent; N=R/"reuse_closure"
PROJECT=R.parents[4]
M=C/"mass"; M.mkdir(parents=True,exist_ok=True); (C/"results").mkdir(exist_ok=True)

def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(262144),b""):h.update(b)
 return h.hexdigest()

def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")

sources={}
def read(p):
 p=Path(p);sources[str(p)]=sha(p);return json.loads(p.read_text(encoding="utf-8-sig"))

checks=[]
def check(id,condition,details=None):
 checks.append({"id":id,"pass":bool(condition),"details":details})
 if not condition:raise ValueError(id)

old=read(N/"propulsion/CURRENT_V6_MASS_LEDGER.json")
oldrows={x["id"]:x for x in old["instances"]}
files={"service":"NATIVE_SERVICE_RECOVERY_V2.json","parking":"NATIVE_PARKING.json","released":"NATIVE_RELEASED.json"}
receipts={s:read(N/"results"/f) for s,f in files.items()}
states={s:{x["id"]:x for x in d["rows"]} for s,d in receipts.items()}
rows=states["service"]
for s,d in receipts.items():
 check(s+"_terminal_705",d["status"]=="PASS_FIXED_NATIVE_DELTA_WITH_HASH_BOUND_PARENT" and d["component_count"]==705 and len(states[s])==705)
 check(s+"_same_identity",set(states[s])==set(rows))
 check(s+"_metadata_verified",d["all_metadata_verified"] is True)
check("retained700_removed_one_added5",len(set(rows)&set(oldrows))==700 and set(oldrows)-set(rows)=={"front_service_cover"} and len(set(rows)-set(oldrows))==5)

wp04file=R.parent/"wp04_robot_assembly_20260906_175153/candidate/results/service_instances.json"
wp04={x["id"]:x for x in read(wp04file)["instances"]}
wp05file=PROJECT/"20_engineering/WP05_SW_20260907/results/PARTS_SOURCE_MANIFEST.json"
wp05=read(wp05file); parts={x["sha256"]:x for x in wp05["parts"]}
check("WP04_snapshot_matches_WP05_bound_source",sources[str(wp04file)]==wp05["source_sha256_before"][str(wp04file)])
paramfile=PROJECT/"20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json"
param=read(paramfile)
ports=read(R/"functional_closure/results/PORTS_CHECK.json")
ports_native=read(R/"functional_closure/results/NATIVE_PORTS_MATERIAL.json")
read(R.parent/"wp07_system_20260907_0610/inputs/RETENTION_DESIGN_CONTRACT.json")
pv=read(N/"power/POWER_CONTRACT.json")["pv"]
arm=old["summary"]["manufacturer_whole_arm_group"]
arm_source=Path(arm["source"]["path"]);sources[str(arm_source)]=sha(arm_source)
check("B601_manufacturer_pdf_hash",sources[str(arm_source)]==arm["source"]["sha256"])

# Each returned name is a responsibility owner, not a substitute for a measured mass.
def owner_for(x):
 id=x["id"]; a=x.get("parent_assembly"); role=x["representation_role"]
 if a=="B601_ARM":return "B601_DM_COMPLETE"
 if a=="ROOT_STRUCTURE":return "ROOT_FRAME_METAL" if role=="PHYSICAL_GEOMETRY" else "ROOT_FRAME_FASTENER_KIT"
 if a=="PRIMARY_STRUCTURE":return "PRIMARY_STRUCTURE_METAL" if role=="PHYSICAL_GEOMETRY" else "PRIMARY_STRUCTURE_FASTENER_KIT"
 if a=="WP06_SIDE_JOINT_FASTENERS":return "PRIMARY_STRUCTURE_FASTENER_KIT"
 if a=="COVERS" or id=="WP09F_front_service_cover_GSE":return "COVERS_AND_GSE_FRONT_PANEL"
 if a=="EQUIPMENT_BAY":
  if role=="PHYSICAL_GEOMETRY":return "EQUIPMENT_DECKS_AND_ADAPTERS"
  for prefix in ["equipment_","connector_"]:
   if id.startswith(prefix):return "EQUIPMENT_"+id[len(prefix):].upper()
 if a=="R01_FASTENERS":return "R01_EQUIPMENT_FASTENER_KIT"
 if a=="LAUNCH_INTERFACE":return "LAUNCH_RESERVED_SPACE"
 if a=="THERMAL":return "THERMAL_SPREADER" if id=="radiator_spreader" else "THERMAL_INTERFACE_KIT"
 if a=="HARNESS":return "HARNESS_RESTRAINT_HARDWARE" if role=="PHYSICAL_GEOMETRY" else "INTERNAL_AND_ARM_EXTERNAL_HARNESS"
 if a=="EXTERNAL_INTERFACES":
  if id in ["navigation_camera","camera_lens"]:return "NAVIGATION_CAMERA_ASSEMBLY"
  if id=="communications_antenna":return "COMMUNICATIONS_ANTENNA"
  return "EXTERNAL_EQUIPMENT_BRACKETS"
 if a=="ONBOARD_RETENTION":
  if role=="FUNCTIONAL_ENVELOPE":return "RETENTION_ACTUATION_AND_SENSORS_"+id.rsplit("_",1)[1]
  if id.startswith(("hold_contact_pad_","hold_upper_pad_")):return "RETENTION_CONTACT_PADS"
  if id.startswith("WP07_lower_collar_"):return "RETENTION_LOWER_COLLARS"
  if id.startswith("WP07_lower_"):return "RETENTION_LOWER_FASTENER_KIT"
  if id.startswith("WP07_guide_"):return "RETENTION_GUIDE_FASTENER_KIT"
  if id.startswith("hold_fold_mast_"):return "RETENTION_REVISED_MASTS"
  if id.startswith("hold_shoe_guide_"):return "RETENTION_GUIDE_RODS"
  return "RETENTION_ORIGINAL_METAL"
 if a=="SOLAR_WING":
  if id.startswith("wing_release_budget_"):return "SOLAR_RELEASE_KITS"
  if id.startswith("wing_harness_budget_"):return "SOLAR_WIRING_KITS"
  if "_leaf_" in id:return "SOLAR_CURRENT_LEAF_LAMINATES"
  return "SOLAR_CURRENT_FRAMES_AND_HINGES"
 if a=="R07_ROOT_CONNECTIONS":return "R07_ROOT_METAL_CAPS" if role=="PHYSICAL_GEOMETRY" else "R07_ROOT_AND_RETENTION_FASTENER_KIT"
 if id=="MIPS_OEM_MAX_ENVELOPE":return "EQUIPMENT_ADCS_PROPULSION_ALLOCATION"
 if id.startswith("MIPS_"):return "PROPULSION_MOUNTING_KIT"
 if id=="P60_REFERENCE_B":return "P60_MODULE_STACK"
 if id.startswith("P60_"):return "P60_MOUNTING_KIT"
 if id in ["lower_equipment_deck_B","upper_equipment_deck_B"]:return "EQUIPMENT_DECKS_AND_ADAPTERS"
 if id.startswith(("GROMMET_","CLAMP_","POST_","TIEROD_")):return "HARNESS_RESTRAINT_HARDWARE"
 if id in ["PROP_PWR_ROUTE","PROP_DATA_ROUTE"]:return "INTERNAL_AND_ARM_EXTERNAL_HARNESS"
 if id.startswith("WP09F_PWR_"):return "GSE_POWER_GLAND_AND_NUT"
 if id.startswith("WP09F_RS422_"):return "GSE_RS422_GLAND_AND_NUT"
 raise ValueError("No ownership rule: "+id)

def source_hash(x):return x.get("source_sha256") or x.get("source_step",{}).get("sha256")

ledger=[];delta_cover=None;state_mass=defaultdict(float);max_state_volume_delta=0.0
for id,x in rows.items():
 o=oldrows.get(id,{});owner=owner_for(x);role=x["representation_role"]
 model_mass=None;volume=None;rho=None;basis="UNRESOLVED_PHYSICAL_MASS";volref=None;densityref=None
 budget=o.get("candidate_allocated_mass_kg") if o.get("accounting_kind")=="INHERITED_BUDGET" else None
 stvol={}
 if o.get("accounting_kind")=="INHERITED_CAD_ESTIMATE":
  rho=wp04[id]["density_kg_mm3"];densityref=str(wp04file)+"#/instances/id="+id+"/density_kg_mm3"
  for state,idx in states.items():
   sh=source_hash(idx[id]);part=parts[sh];stvol[state]=part["actual_export_facts"]["volume_mm3"]
   check("valid_source_shape_"+state+"_"+id,part["actual_export_facts"]["shape_valid"] is True)
  volume=stvol["service"];model_mass=volume*rho;basis="SOURCE_BOUND_CANDIDATE_MATERIAL";volref=str(wp05file)+"#/parts/sha256="+source_hash(x)
  check("old_mass_recomputed_"+id,abs(model_mass-o["candidate_allocated_mass_kg"])<1e-8)
 elif o.get("accounting_kind")=="NEW_CANDIDATE_MATERIAL_ALLOCATION":
  volume=o["volume_mm3_used"];rho=o["density_kg_mm3_used"];model_mass=volume*rho;basis="EXISTING_EXPLICIT_MATERIAL_ALLOCATION"
  volref=str(N/"propulsion/CURRENT_V6_MASS_LEDGER.json")+"#/instances/id="+id;densityref=str(paramfile)+"#/candidate_aluminum_density_kg_mm3"
  check("explicit_newmetal_not_proxy_"+id,role=="PHYSICAL_GEOMETRY" and rho==param["candidate_aluminum_density_kg_mm3"])
  check("newmetal_identical_state_shapes_"+id,len({source_hash(st[id]) for st in states.values()})==1)
  stvol={s:volume for s in states}
 elif id=="WP09F_front_service_cover_GSE":
  volume=ports["parts"]["front_service_cover_GSE"]["volume_mm3"];rho=wp04["front_service_cover"]["density_kg_mm3"];model_mass=volume*rho
  basis="REPLACEMENT_COVER_EXISTING_AL_MATERIAL_NEW_RECEIPT_VOLUME";volref=str(R/"functional_closure/results/PORTS_CHECK.json")+"#/parts/front_service_cover_GSE";densityref=str(wp04file)+"#/instances/id=front_service_cover/density_kg_mm3"
  pr=next(y for y in ports_native["records"] if y["id"]=="front_service_cover_GSE")
  check("new_cover_native_material_hash_match",pr["ok"] and pr["native_sha256"]==x["native_sha256"])
  check("new_cover_identical_three_states",len({source_hash(st[id]) for st in states.values()})==1)
  stvol={s:volume for s in states};delta_cover={"removed_id":"front_service_cover","removed_candidate_mass_kg":oldrows["front_service_cover"]["candidate_allocated_mass_kg"],"added_id":id,"added_candidate_mass_kg":model_mass,"difference_kg":model_mass-oldrows["front_service_cover"]["candidate_allocated_mass_kg"],"four_gland_and_nut_mass_not_included":True}
 elif owner=="B601_DM_COMPLETE":basis="INCLUDED_IN_ONE_MANUFACTURER_WHOLE_ARM_NOMINAL"
 elif id=="launch_interface_reserved_volume":basis="NONMASS_RESERVED_VOLUME"
 elif budget is not None:basis="PLANNING_BUDGET_ONLY_NOT_MASS_MEASUREMENT"
 elif role=="FUNCTIONAL_ENVELOPE":basis="NO_DENSITY_FOR_ENVELOPE_REPRESENTED_HARDWARE_UNRESOLVED"
 applicable=id!="launch_interface_reserved_volume"
 for state,v in stvol.items():state_mass[state]+=v*rho
 if stvol:max_state_volume_delta=max(max_state_volume_delta,max(stvol.values())-min(stvol.values()))
 if owner=="B601_DM_COMPLETE":note="4.5 kg is counted at the complete-arm owner once; internal motor/driver/fastener solids are not extra mass terms. Family nominal only, shipment revision/tolerance absent."
 elif role=="FUNCTIONAL_ENVELOPE":note="Envelope geometric volume is not material. Except the launch keep-out, represented module/connector/actuator/harness still requires physical mass at its responsibility owner."
 else:note=""
 ledger.append({"id":id,"responsibility_owner":owner,"source_parent_assembly":x.get("parent_assembly"),"representation_role":role,"physical_mass_applicable":applicable,"mass_accounting_basis":basis,"candidate_material_mass_kg":model_mass,"legacy_planning_budget_kg":budget,"whole_module_mass_counted_here":False,"as_built_mass_kg":None,"mass_lower_limit_from_tolerance_kg":None,"volume_mm3":volume,"density_kg_mm3":rho,"volume_source":volref,"density_source":densityref,"state_volume_mm3":stvol,"source_native_sha256_by_state":{s:idx[id]["native_sha256"] for s,idx in states.items()},"source_step_sha256_by_state":{s:source_hash(idx[id]) for s,idx in states.items()},"state_receipt_files":{s:str(N/"results"/f) for s,f in files.items()},"expected_solid_count":x.get("expected_solids"),"COM_S_m":None,"inertia_C_S_kg_m2":None,"note":note})

# Minimum inputs are specific to each engineering responsibility, with no blanket density.
missing={
 "ROOT_FRAME_FASTENER_KIT":"72 installed screws/tie rods/washers/nuts: final SKU, material grade and unit/kit mass; station BOM quantity mapping.",
 "PRIMARY_STRUCTURE_FASTENER_KIT":"44 inherited web/rail fasteners plus16 WP06 side joint items: selected catalogue SKU/material/unit mass; STEP geometry alone does not set density.",
 "R01_EQUIPMENT_FASTENER_KIT":"128 R01 screws/washers/nuts: actual size-length-grade SKU list or one measured complete kit mass with contents list.",
 "R07_ROOT_AND_RETENTION_FASTENER_KIT":"92 R07 rail/hold fasteners and sleeves: final SKU/material or complete kit mass and contents list.",
 "THERMAL_INTERFACE_KIT":"Five interface pads and battery thermal link: installed dimensions/material/density (including bondlines) or finished kit mass.",
 "INTERNAL_AND_ARM_EXTERNAL_HARNESS":"Unique wire/cable BOM, installed cut lengths, linear masses, terminals/shields/sleeves; reconcile overlapping route depictions instead of summing route volumes. External arm loops excluded from B601 whole-arm nominal.",
 "RETENTION_CONTACT_PADS":"Six contact/upper pads: elastomer grade, finished dimensions/density or mass including adhesive.",
 "RETENTION_LOWER_COLLARS":"Four changed collars: explicit candidate material/grade and current part volume receipt or measured finished masses.",
 "RETENTION_REVISED_MASTS":"Two changed masts: current source-bound volumes and explicit retained/changed material; old geometry mass cannot be copied after cuts/additions.",
 "RETENTION_GUIDE_RODS":"Four guide rods: selected material/grade and current shape volume or measured masses; do not apply aluminum by shape name.",
 "RETENTION_LOWER_FASTENER_KIT":"16 catalogue M3 screw/washer/nut solids: procurement material/grade and unit mass or supplier exact complete kit mass.",
 "RETENTION_GUIDE_FASTENER_KIT":"Eight M2 screw/washer proxies: selected SKUs, unit/kit masses; threadless proxies are not certified material.",
 "RETENTION_ACTUATION_AND_SENSORS_0":"Station0 actual puller/release/spring/sensor bill of hardware and assembly mass; distinguish alternate/overlapping actuator proxies before summing.",
 "RETENTION_ACTUATION_AND_SENSORS_1":"Station1 actual puller/release/spring/sensor bill of hardware and assembly mass; distinguish alternate/overlapping actuator proxies before summing.",
 "PROPULSION_MOUNTING_KIT":"16 foot screw/washer/nut SKUs/material/unit masses; bracket and four shims already have source-bound candidate masses.",
 "P60_MOUNTING_KIT":"20 host rods/washers/nuts SKUs/material/unit masses; four posts and tray already have source-bound candidate masses.",
 "HARNESS_RESTRAINT_HARDWARE":"Grommet and clamp polymer grades/finished volumes, rod/fastener kit masses; listed metal posts/clips already counted.",
 "P60_MODULE_STACK":"Bind P60_REFERENCE_B to exact Dock+ACU+PDU configuration; 191g catalogue reference remains excluded until instance/configuration and included shields are fixed.",
 "GSE_POWER_GLAND_AND_NUT":"Exact selected gland+locknut complete-kit manufacturer mass and delivered material; four-mm nut geometry is only a nominal assumption.",
 "GSE_RS422_GLAND_AND_NUT":"Exact selected gland+locknut complete-kit manufacturer mass and delivered material; do not add a nut twice if vendor kit mass includes it.",
 "COMMUNICATIONS_ANTENNA":"Antenna SKU including feed/pigtail mass and explicit harness ownership.",
 "NAVIGATION_CAMERA_ASSEMBLY":"Actual camera+lens SKU and assembled mass; clarify whether legacy0.15kg budget includes lens/connector.",
 "EQUIPMENT_BATTERY":"Actual battery package incl enclosure/connector/thermal scope; BPX0.5kg reference is nested within old1.6kg budget, not an extra device.",
 "EQUIPMENT_ADCS_PROPULSION_ALLOCATION":"Disaggregate3kg planning budget into reaction wheels/ADCS/propulsion actual chosen packages and masses. Old MiPS0.542kg reference is nested, not additional; actual propulsion selection unresolved.",
 "EQUIPMENT_ARM_DRIVE":"Define only external distribution/USB-CAN/terminal electronics and obtain assembled mass. Six DM joint drivers already belong to B601 and must not be added here; old0.8kg is a budget, not measured external hardware.",
 "EQUIPMENT_COMPUTE_COMMUNICATIONS":"Exact OBC/radio/compute board configuration and assembled mass; A3200 reference24g is nested and never a second OBC.",
 "EQUIPMENT_NAVIGATION_ELECTRONICS":"Selected sensor processing/receiver/connector hardware BOM and assembled mass replacing0.3kg budget.",
 "SOLAR_CURRENT_LEAF_LAMINATES":"Six current leaf laminate/CIC/adhesive finished masses or source-bound layup;0.18kg/leaf is only a budget and does not include the unintegrated84-CIC delta.",
 "SOLAR_RELEASE_KITS":"Actual selected two release kits with unit masses replacing0.08kg/wing budgets; do not include frame/hinge masses twice.",
 "SOLAR_WIRING_KITS":"Unique wing harness BOM/cut-length/linear mass/terminations replacing0.05kg/wing budgets; separate body harness boundary."
}
owners={}
for owner in sorted({x["responsibility_owner"] for x in ledger}):
 members=[x for x in ledger if x["responsibility_owner"]==owner]
 known=[x for x in members if x["candidate_material_mass_kg"] is not None]
 unknown=[x["id"] for x in members if x["physical_mass_applicable"] and x["candidate_material_mass_kg"] is None and owner!="B601_DM_COMPLETE"]
 nominal=4.5 if owner=="B601_DM_COMPLETE" else None
 owners[owner]={"owner":owner,"members":[x["id"] for x in members],"instance_count":len(members),"candidate_material_subtotal_kg":sum(x["candidate_material_mass_kg"] for x in known),"catalogue_nominal_whole_module_kg":nominal,"catalogue_nominal_counting_terms":1 if nominal else 0,"legacy_planning_allocation_kg":sum(x["legacy_planning_budget_kg"] for x in members if x["legacy_planning_budget_kg"] is not None),"numeric_estimate_complete_in_owner":not unknown,"as_built_numeric_complete":False,"unresolved_mass_instance_ids":unknown,"minimum_missing_input":missing.get(owner,"Source-bound nominal material model exists; for as-built bound provide material certification/tolerance and manufactured geometry or weighing. Exact B601 DM shipment configuration and measured whole-arm mass required." if owner=="B601_DM_COMPLETE" else "As-built tolerance/material verification only; candidate numerical material subtotal is complete."),"COM_S_m":None,"inertia_C_S_kg_m2":None}
 # This zero is a known-term subtotal; unknown masses are never converted to zero.
 owners[owner]["zero_known_subtotal_is_not_zero_owner_mass"]=not known and nominal is None

check("responsibility_partition_exact_705",len(ledger)==705 and len({x["id"] for x in ledger})==705 and sum(len(x["members"]) for x in owners.values())==705)
check("unique_arm_owner_10_members",owners["B601_DM_COMPLETE"]["instance_count"]==10 and sum(x["expected_solid_count"] for x in ledger if x["responsibility_owner"]=="B601_DM_COMPLETE")==391)
check("arm_internal_nominal_count_once",sum(x["catalogue_nominal_counting_terms"] for x in owners.values())==1)
check("external_fasteners_not_arm_members",all(x["source_parent_assembly"]=="B601_ARM" for x in ledger if x["responsibility_owner"]=="B601_DM_COMPLETE"))
check("no_proxy_density_allocation",all(x["representation_role"]=="PHYSICAL_GEOMETRY" for x in ledger if x["density_kg_mm3"] is not None))
check("unresolved_mass_stays_null",all(x["as_built_mass_kg"] is None and (x["candidate_material_mass_kg"] is None or x["density_kg_mm3"] is not None) for x in ledger))
check("state_material_mass_invariant",max(state_mass.values())-min(state_mass.values())<1e-8)
known_sum=sum(x["candidate_material_mass_kg"] for x in ledger if x["candidate_material_mass_kg"] is not None)
budget_sum=sum(x["legacy_planning_budget_kg"] for x in ledger if x["legacy_planning_budget_kg"] is not None)
check("group_subtotals_no_double_count",abs(sum(x["candidate_material_subtotal_kg"] for x in owners.values())-known_sum)<1e-10)
old_budget=sum(x["candidate_allocated_mass_kg"] for x in old["instances"] if x["accounting_kind"]=="INHERITED_BUDGET")
check("historical_budgets_not_added_to_material_mass",abs(budget_sum-old_budget)<1e-12)
check("cover_delta_reconciliation",abs((known_sum+budget_sum+4.5)-old["summary"]["candidate_allocated_total_including_nominal_arm_kg"]-delta_cover["difference_kg"])<1e-8)

pv_count=pv["Ns"]*pv["Np"]*pv["channels"]
delta={"id":"PV84_UNINTEGRATED_PLANNING_DELTA","part_reference":pv["part_reference"],"count":pv_count,"cell_nominal_reference_kg":pv["cell_mass_reference_kg"],"CIC_only_nominal_reference_kg":pv_count*pv["cell_mass_reference_kg"],"included_in_current_705":False,"current_705_contribution_kg":None,"not_a_complete_new_wing_mass":True,"excluded_layers":["substrate","adhesive","wiring and blocking diodes","hinges and frames","coating/protection"],"current_leaf_budget_must_be_replaced_not_blindly_added":True,"source":str(N/"power/POWER_CONTRACT.json")+"#/pv"}
check("PV84_not_integrated",pv_count==84 and not any("CIC" in x["id"] for x in ledger))
# Conservative round-down only for the declared mathematical geometry/material model.
model_lower=math.floor((known_sum-sum(x["density_kg_mm3"]*1e-5 for x in ledger if x["density_kg_mm3"] is not None))*1e6)/1e6
summary={"schema":"CURRENT_705_MASS_RESPONSIBILITY_ASSIGNMENT_V1","status":"RESPONSIBILITY_COMPLETE_NUMERICAL_MASS_PARTIAL","generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"current_instance_count":705,"state_counts":{s:len(d) for s,d in states.items()},"responsibility_coverage":{"assigned":705,"total":705,"fraction":1.0,"owner_count":len(owners)},"numeric_coverage":{"candidate_geometry_material_instances":sum(x["candidate_material_mass_kg"] is not None for x in ledger),"whole_B601_nominal_included_instances":10,"legacy_budget_only_instances":sum(x["legacy_planning_budget_kg"] is not None for x in ledger),"pure_nonmass_reserved_instances":1,"physical_or_represented_hardware_instances":704,"numeric_material_or_whole_module_nominal_covered_instances":sum(x["candidate_material_mass_kg"] is not None for x in ledger)+10,"coverage_excludes_budgets_and_nominal_tolerance_is_not_as_built":True,"as_built_verified_mass_instances":0,"owner_estimate_complete_count":sum(x["numeric_estimate_complete_in_owner"] for x in owners.values()),"unresolved_mass_owner_count":sum(bool(x["unresolved_mass_instance_ids"]) for x in owners.values())},"current_candidate_material_subtotal_kg":known_sum,"catalogue_B601_whole_arm_nominal_kg":4.5,"material_plus_one_arm_nominal_subtotal_kg":known_sum+4.5,"legacy_planning_allocations_separate_kg":budget_sum,"historical_mixed_sum_after_cover_delta_kg":known_sum+budget_sum+4.5,"historical_mixed_sum_is_not_whole_spacecraft_mass_or_lower_bound":True,"strict_bounds":{"conditional_defined_material_model_lower_bound_kg":model_lower,"conditions":"All178 source-bound physical components retained with recorded nominal geometry and fixed assigned candidate densities; unknown owners contribute nonnegative mass.1e-5mm3 per-part accounting guard and1mg round-down. No supplier nominal/budget is included. Not an as-built guarantee or proof that the geometry is manufacturable.","strict_positive_as_built_lower_bound_kg":None,"universal_mass_nonnegative_bound_kg":0.0,"reason":"No traceable delivered-hardware material/dimensional tolerance or measured lower-limit mass in this evidence set; cannot promote nominal CAD or4.5kg catalogue value to a guaranteed positive as-built bound."},"cover_replacement_delta":delta_cover,"material_density_counts":dict(Counter(str(x["density_kg_mm3"]) for x in ledger if x["density_kg_mm3"] is not None)),"candidate_material_mass_by_state_kg":dict(state_mass),"max_current_state_volume_difference_mm3":max_state_volume_delta,"B601_scope":{"members":owners["B601_DM_COMPLETE"]["members"],"contained_solids_count":391,"391_is_body_count_not_count_of_new_mass_items":True,"included_scope":"One complete nominal B601 DM arm: original links/gripper/internal motors/drivers and original internal hardware, as a family-level whole module; exact shipment revision and included accessories remain unverified.","excluded_scope":["all spacecraft root mounting M5/M6 and R01/R07/WP06/WP07 hardware","satellite retention mechanisms and contact pads","external arm service loops and spacecraft harness","external distribution or USB-CAN board and GSE power supply"],"no_internal_fastener_duplicate_discovered_in_old496":True},"full_current_mass_kg":None,"COM_S_m":None,"inertia_C_S_kg_m2":None,"PV_unintegrated_delta":delta,"source_bindings":sources,"source_files_unchanged":None,"CAD_or_COM_executed":False,"N_modified":False,"historical_scientific_gate_modified":False}
old_unassigned=set(old["summary"]["still_unassigned_instance_ids"])
summary["old496_disposition"]={"count":len(old_unassigned),"B601_internal_members_found":len(old_unassigned&set(owners["B601_DM_COMPLETE"]["members"])),"pure_nonmass_reserved_count":sum(x["id"] in old_unassigned and not x["physical_mass_applicable"] for x in ledger),"by_responsibility_owner":dict(Counter(x["responsibility_owner"] for x in ledger if x["id"] in old_unassigned)),"all496_responsibility_bound":old_unassigned.issubset({x["id"] for x in ledger}),"physical_mass_unresolved_count":sum(x["id"] in old_unassigned and x["physical_mass_applicable"] and x["candidate_material_mass_kg"] is None for x in ledger)}
summary["numeric_coverage"]["material_or_module_nominal_instance_fraction_excluding_pure_space"]=188/704
summary["numeric_coverage"]["owner_pure_nonmass_count"]=1
summary["numeric_coverage"]["owner_estimate_complete_excluding_nonmass_count"]=sum(x["numeric_estimate_complete_in_owner"] for x in owners.values())-1
summary["numeric_coverage"]["unresolved_mass_instance_count_including_budget_only"]=sum(len(x["unresolved_mass_instance_ids"]) for x in owners.values())
summary["duplicate_mass_controls"]=["B601 original internal391 solids only in one4.5kg whole-arm nominal term; no add-on per-body or per-internal-fastener mass.","No cross-state summation: service, parking and released are the same705 identities, not2115 hardware instances.","MiPS0.542kg, BPX0.5kg and A3200 0.024kg references are not added above old aggregate equipment budgets.","Old0.8kg arm_drive allocation is a planning allowance only; its responsibility is external interface electronics, never a second copy of six DM motor drivers.","P60 0.191kg reference not added until exact instance and configuration match.","Route-envelope volumes are not cable material; overlapping path depictions must resolve to one actual harness BOM.","GSE gland-and-nut owner will use complete-kit mass once if supplier mass already includes locknut.","PV84 CIC delta remains separate from current six0.18kg leaf budgets until integrated configuration replaces them."]
check("old496_all_assigned_no_arm_absorption",summary["old496_disposition"]["all496_responsibility_bound"] and summary["old496_disposition"]["B601_internal_members_found"]==0)
try:
 import ctypes
 from ctypes import wintypes
 class PMC(ctypes.Structure):
  _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ["PeakWorkingSetSize","WorkingSetSize","QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage","QuotaPeakNonPagedPoolUsage","QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage"]]
 pmc=PMC();pmc.cb=ctypes.sizeof(pmc)
 fn=ctypes.windll.psapi.GetProcessMemoryInfo;fn.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD];fn.restype=wintypes.BOOL
 ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
 if fn(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(pmc),pmc.cb):summary["peak_working_set_MiB"]=pmc.PeakWorkingSetSize/1048576
except Exception as e:summary["memory_measurement_note"]=str(e)
check("all_read_sources_unchanged",all(sha(p)==h for p,h in sources.items()))
summary["source_files_unchanged"]=True;summary["checks_total"]=len(checks);summary["checks_passed"]=sum(x["pass"] for x in checks);summary["checks"]=checks
save(M/"MASS_ASSIGNMENT_705.json",{"summary":summary,"owners":list(owners.values()),"instances":ledger})
save(M/"PV84_UNINTEGRATED_DELTA.json",delta)
save(C/"results/MASS_ASSIGNMENT.json",summary)
for filename,records,fields in [
 ("MASS_ASSIGNMENT_705.csv",ledger,["id","responsibility_owner","source_parent_assembly","representation_role","physical_mass_applicable","mass_accounting_basis","candidate_material_mass_kg","legacy_planning_budget_kg","as_built_mass_kg","volume_mm3","density_kg_mm3","volume_source","density_source","note"]),
 ("OWNER_SUMMARY.csv",list(owners.values()),["owner","instance_count","candidate_material_subtotal_kg","catalogue_nominal_whole_module_kg","legacy_planning_allocation_kg","numeric_estimate_complete_in_owner","as_built_numeric_complete","minimum_missing_input"]),
 ("OPEN_MASS_INPUTS.csv",[x for x in owners.values() if x["unresolved_mass_instance_ids"]],["owner","instance_count","unresolved_mass_instance_ids","minimum_missing_input"])]:
 with (M/filename).open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fields,extrasaction="ignore");w.writeheader();w.writerows(records)
print(json.dumps({k:summary[k] for k in ["responsibility_coverage","numeric_coverage","current_candidate_material_subtotal_kg","material_plus_one_arm_nominal_subtotal_kg","legacy_planning_allocations_separate_kg","cover_replacement_delta","material_density_counts","checks_total","checks_passed"]},ensure_ascii=False))
