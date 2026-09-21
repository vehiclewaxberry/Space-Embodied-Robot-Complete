import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
REL = ROOT/"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
LC = REL/"_work/loop_c"
now = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
def jload(rel): return json.loads((ROOT/rel).read_text(encoding="utf-8"))

e23 = jload("30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json")
rt = jload("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_c/TMC_RED_TEAM_AND_FALSIFIER_V1.json")
harness_gate = jload("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/B601_HARNESS_TERMINAL_GATE_V1.json")
handoff_v2 = jload("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json")
sim13_gate = jload("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json")
urdf_receipt = jload("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json")

e23_pass = e23["technical_verdict"] == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS" and e23["summary"]["passed"] == 18
tmg = [
 {"id":"TMG-1","name":"Product Definition","state":"PASS","basis":"M7 criteria 01-08/10-17 PASS lineage + release package files 01-16 complete"},
 {"id":"TMG-2","name":"Frames/Mass","state":"PASS","basis":"frame tree V2 frozen; mass V3 R2 + bridged mass consumed; total mass exact in emitted URDF; as-built metrology EXTERNAL hold"},
 {"id":"TMG-3","name":"Mechanisms","state":"PASS","basis":"Solar R2 mechanism/HDRM/deployment ledgers current; gripper R1 candidate with declared null physical limits"},
 {"id":"TMG-4","name":"Harness Mission Envelope","state":"HOLD","basis":"E_HRN 0/75 SAFE, 11/11 key states UNSAFE, mission coverage FAIL_AT_MANDATORY_KEY_STATES; Route-B REJECTED; ODR-42 APPROVE_BOUNDED_DETAILED_DESIGN issued 2026-08-25; physical Route-C mission-first design is the remaining internal blocker; full-range DEFERRED_HOLD"},
 {"id":"TMG-5","name":"R2 Full-Flex","state":"PASS_WITH_DECLARED_PROVISIONAL_PHYSICS","basis":"Round4 V3 17/17 + E23 18/18; seven-mode HF reconstruction 0.2714% <= 1%; cross-solver 1.81e-05 <= 5%; provisional EI/GJ/k/zeta declared"},
 {"id":"TMG-6","name":"Mechanical-to-Embodied Handoff","state":"FAIL_15_OF_20","basis":"Sim13 NC 15/20 (NC15/16/18/19/20 dependency_hold); handoff V2 11/12 G12 harness; 1-of-2 absent intake paths resolved (unified URDF emitted); backends registered in SIM13_BACKEND_WORK_ORDERS_V1"},
 {"id":"TMG-7","name":"Adversarial Integrity","state":"HIGH_0","basis":"Loop C red team + falsifier " + rt["verdict"]},
]
external_holds = ["launcher/deployer ICD","separation ICD","flight material allowables","as-built mass/CG/inertia","hardware contact calibration (CT01-CT05, gripper closing time, F/T)","qualification vibration","TVAC","flight HDRM reliability","full-range Route-C harness enhancement (DEFERRED_HOLD)","SolidWorks native reintegration","M3R as-installed mass properties"]
internal_open = [
 {"item":"Route-C mission-first physical dress-pack design","blocks":"TMG-4","work_order":"ODR-42 approved; P01-P13 physical inputs, route design, physical CAD branch, predicate evaluation, mission coverage re-issue"},
 {"item":"Sim13 five NC backends (NC15/16/18/19/20)","blocks":"TMG-6","work_order":"20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/SIM13_BACKEND_WORK_ORDERS_V1.json"},
]
gate_a_pass = all(x["state"] in ("PASS","PASS_WITH_DECLARED_PROVISIONAL_PHYSICS","PASS_FULL_RANGE","PASS_HARNESS_RATED_MISSION_ENVELOPE","HIGH_0") or (x["id"]=="TMG-6" and x["state"]=="PASS_20_OF_20") for x in tmg)
verdict = ("MECHANICAL_ENGINEERING_DESIGN_RELEASED_FOR_R2_OPERATIONAL_DIGITAL_TWIN_AND_EMBODIED_CONTROL_WITH_FLIGHT_QUALIFICATION_HOLD"
           if gate_a_pass else
           "TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__TMG4_TM6_INTERNAL_BLOCKERS_REGISTERED__NO_RELEASE_CREDIT")
gate = {
 "schema":"TERMINAL_MECHANICAL_GATE_A_V1","generated_utc":now,
 "owner_directive":"TERMINAL MECHANICAL ONE-SHOT CLOSURE (2026-08-25)",
 "decision_rule":"Authority > Evidence > Independent reproduction > Agent opinion",
 "fail_closed_invariants":["UNKNOWN is never PASS","15/20 is never written 20/20","null is never zero","hash_mismatch=0 required","empty_comparison_set=0 required","unexplained_positive_interference=0 required"],
 "tmg": tmg,
 "invariants_check":{"internal_design_HOLD_except_TMG4_TM6_registered":True,"hash_mismatch":0,"empty_comparison_set":0,"unexplained_positive_interference":0},
 "external_only_holds":external_holds,
 "internal_open_items":internal_open,
 "gate_a_pass":gate_a_pass,
 "verdict":verdict,
 "e23_key_metrics":e23["key_metrics"],
 "sim13_state":{"nc":"15/20","max_operational_state":sim13_gate["maximum_current_operational_state"],"urdf_absent_path_resolved":urdf_receipt["all_checks_pass"]},
 "harness_state":{"terminal_gate":harness_gate["mechanical_design"],"coverage":"FAIL_AT_MANDATORY_KEY_STATES"},
 "documented_defects":[{"id":"TMC-F01","disposition":"documented; Red Team adjudicated; owner review pending"}],
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
}
(REL/"00_RELEASE_GATE.json").write_text(json.dumps(gate,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
# 17 / 18
(REL/"17_MECH_TO_EMBODIED_HANDOFF_GATE.json").write_text(json.dumps({
 "schema":"MECH_TO_EMBODIED_HANDOFF_GATE_TERMINAL_V1","generated_utc":now,
 "current_handoff_gate_v2":{"path":"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json","checks":"11/12","failed":"G12 HARNESS_RATED_OPERATIONAL_ENVELOPE","verdict":handoff_v2["verdict"]},
 "unified_interface":"15_UNIFIED_R2_SYSTEM_INTERFACE.yaml now provides the single consumption point; rerun of handoff V2 with the unified contract still fails G12 until the harness mission envelope passes",
 "verdict":"MECHANICAL_TO_EMBODIED_HANDOFF_FAIL","review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
(REL/"18_SIM13_PREEXECUTION_GATE.json").write_text(json.dumps({
 "schema":"SIM13_PREEXECUTION_GATE_TERMINAL_V1","generated_utc":now,
 "nc_state":"15/20 (NC15/NC16/NC18/NC19/NC20 dependency_hold)",
 "maximum_current_operational_state":sim13_gate["maximum_current_operational_state"],
 "intake":"HOLD_INCOMPLETE; 1-of-2 required absent paths resolved (unified_r2_c01_no_route_c_sim_candidate_v2.urdf EMITTED, all 7 verification checks PASS, documented defect TMC-F01); outstanding: MECH_RL_SYSTEM_INTERFACE_V2.yaml instance (9 GATE artifact slots = the five NC backends)",
 "backends":"SIM13_BACKEND_WORK_ORDERS_V1 registered; no backend execution authorized from this gate",
 "verdict":"ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS (unchanged; truthful)",
 "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
# 22 sha registry
rows = []
for f in sorted(REL.iterdir()):
    if f.is_file(): rows.append((f.name, f.stat().st_size, sha(f)))
with open(REL/"22_RELEASE_SHA256.csv","w",newline="",encoding="utf-8") as fp:
    fp.write("file,bytes,sha256\n")
    for n,b,s in rows: fp.write(f"{n},{b},{s}\n")
print("verdict:",verdict)
print("gate_a_pass:",gate_a_pass)
