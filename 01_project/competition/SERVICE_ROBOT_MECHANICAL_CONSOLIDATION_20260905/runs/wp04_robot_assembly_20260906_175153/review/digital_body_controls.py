"""Independent package review and offline release fault controls, stdlib only."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode=True
RUN=Path(__file__).resolve().parents[1]
C=RUN/"contracts"
OUT=RUN/"review/DIGITAL_BODY_CONTROLS.json"

def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))

def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def review_package(manifest,interfaces,body,release):
    errors=[]
    def require(ok,reason):
        if not ok:
            errors.append(reason)
    require(all(Path(p).is_file() and sha(p)==h for p,h in manifest["input_sha256"].items()),"STALE_INPUT")
    require(all(Path(p).is_file() and sha(p)==h for p,h in manifest["outputs"].items()),"STALE_OUTPUT")
    here=Path(manifest["source_candidate"])
    rows=load(here/"results/service_instances.json")["instances"]
    ids={r["id"] for r in rows}
    mapped=interfaces["instance_interfaces"]
    require(len(mapped)==len(rows)==len({x["from_instance"] for x in mapped}) and {x["from_instance"] for x in mapped}==ids,"INSTANCE_COVERAGE")
    require(body["identity"]["instance_ids"]==sorted(ids),"BODY_IDENTITY")
    require(len({r["mass_owner"] for r in mapped})==len(mapped),"DUPLICATE_OWNER")
    source={r["id"]:r for r in rows}
    require(all(x["mass_owner"]==source[x["from_instance"]]["mass_owner"] and x["representation_role"]==source[x["from_instance"]]["representation_role"] for x in mapped if x["from_instance"] in ids),"IDENTITY_OR_ROLE_MISMATCH")
    require(all(x["to_instance"] is None or x["to_instance"]==source[x["from_instance"]]["mount_interface"] and x["to_instance"] in ids for x in mapped if x["from_instance"] in ids),"INVENTED_MATE")
    require(all(x["physical_connection_verified"] is False for x in mapped),"UNSUPPORTED_PHYSICAL_CONNECTION")
    for state in ("parking","released","service"):
        d=load(here/"results"/(state+"_instances.json"))
        sr={r["id"]:r for r in d["instances"]}
        require(d["view"]=="complete" and set(sr)==ids,"WRONG_STATE_OR_VIEW")
        require(all(x["state_transforms"].get(state)==sr[x["from_instance"]].get("T_S_local") for x in mapped if x["from_instance"] in sr),"TRANSFORM_MISMATCH")
    for doc in (interfaces,body,release):
        require(doc["input_sha256"]==manifest["input_sha256"],"PACKAGE_INPUT_SPLIT")
        require(doc["final_candidate_bound"]==manifest["final_candidate_bound"] and doc["binding_mode"]==manifest["binding_mode"],"PACKAGE_BINDING_SPLIT")
        require(not doc["hardware_verified"] and not doc["scientific_gate"] and not doc["control_gate"] and not doc["historical_gate_changed"],"GATE_PROMOTION")
    if manifest["final_candidate_bound"]:
        require(manifest["binding_mode"]=="FINAL_CURRENT_CANDIDATE" and here.resolve()==(RUN/"candidate").resolve(),"BASELINE_MISLABELLED_FINAL")
    else:
        require(manifest["binding_mode"]=="BASELINE_DEVELOPMENT_REFERENCE","DEVELOPMENT_BINDING_MISLABELLED")
    require(body["legacy_control_contact_SAFE00_PASS_inherited"] is False,"LEGACY_PASS_INHERITANCE")
    require(body["geometry"]["arm_BRep_and_accepted_STL_equivalent"] is False,"BREP_STL_EQUIVALENCE_INVENTED")
    unknown_fields=("physical_velocity_limit","physical_effort_limit","mechanical_hard_stop","controller_soft_limit","stopping_margin")
    for joint in body["joint_limit_contracts"]:
        require(all(joint[f]["value"] is None and joint[f]["status"]=="UNKNOWN" for f in unknown_fields),"PHYSICAL_LIMIT_ZERO_OR_INVENTED")
        require(joint["raw_velocity_physical_unit_authority"] is None,"PHYSICAL_VELOCITY_AUTHORITY_INVENTED")
    urdf=next(Path(p) for p in manifest["input_sha256"] if p.endswith("arm_b601_v1.urdf"))
    raw={j.attrib["name"]:(None if j.find("limit") is None else dict(j.find("limit").attrib)) for j in ET.parse(urdf).getroot().findall("joint")}
    require(len(body["joint_limit_contracts"])==len(raw) and all(j["raw_urdf_limit_attributes"]==raw[j["joint"]] for j in body["joint_limit_contracts"]),"RAW_URDF_CHANGED")
    require(release["hardware_execution_enabled"] is False and release["legacy_SAFE00_dependency"] is False,"HARDWARE_OR_SAFE00_PROMOTION")
    require(all(a["timeout_s"] is None and a["actual_sensor_evidence"] is None for a in release["actions"]),"INVENTED_RELEASE_TIMING")
    require(all(s["sensor_type"] is None and s["threshold"] is None and s["calibration"] is None and s["max_latency_s"] is None for s in release["sensor_confirmation_table"]),"INVENTED_SENSOR")
    require(all(s["associated_instance"] is None or s["associated_instance"] in ids for s in release["sensor_confirmation_table"]),"ABSENT_SENSOR_INSTANCE")
    require(all(body["mass_summary"][s]["full_physical_mass_properties_complete"] is False for s in body["mass_summary"]),"PHYSICAL_MASS_COMPLETENESS_PROMOTION")
    geo=interfaces.get("named_geometric_connections")
    if manifest["final_candidate_bound"]:
        require(isinstance(geo,dict),"MISSING_FINAL_R07_GEOMETRIC_CONTRACT")
    if isinstance(geo,dict):
        raw=load(geo["source"]["path"])
        require(sha(geo["source"]["path"])==geo["source"]["sha256"],"R07_SOURCE_HASH_MISMATCH")
        require(sha(geo["review"]["path"])==geo["review"]["sha256"],"R07_REVIEW_HASH_MISMATCH")
        require(geo["connections"]==raw["connections"],"R07_CONNECTION_FIELDS_CHANGED_OR_OMITTED")
        require(geo["local_instance_ids"]==raw["local_instance_ids"] and set(geo["local_instance_ids"])<=ids,"R07_LOCAL_IDENTITY_MISMATCH")
        require(geo["frame"]=="S" and geo["units"]=="mm","R07_UNITS_OR_FRAME")
        require(geo["nominal_material_grade"] is None and geo["nominal_preload_N"] is None and geo["strength_pass"] is None and geo["physical_assembly_completed"] is False,"R07_PHYSICAL_PROMOTION")
        members={}
        for connection in raw["connections"]:
            owned=set(connection["body_ids"])|set(connection["hardware"].values())
            if connection.get("sleeve_id"):owned.add(connection["sleeve_id"])
            require(owned<=ids,"R07_MISSING_FINAL_MEMBER")
            for id_ in owned:members.setdefault(id_,[]).append(connection["connection_id"])
        for item in mapped:
            expected=members.get(item["from_instance"],[])
            require(item["geometric_connection_ids"]==expected,"R07_INSTANCE_CONNECTION_COVERAGE")
            if expected:
                require(bool(item["mating_features"]) and {f["connection_id"] for f in item["mating_features"]}==set(expected),"R07_MISSING_MATING_FEATURES")
                require(bool(item["assembly_and_tool_path_evidence"]),"R07_MISSING_PATH_EVIDENCE")
    return errors

def main():
    spec=importlib.util.spec_from_file_location("reviewed_release_logic",C/"release_logic.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    paths=[C/"CONTRACT_BINDING_MANIFEST.json",C/"SYSTEM_INTERFACES.json",C/"DIGITAL_BODY_CONSUMER_CONTRACT.json",C/"RELEASE_STATE_CONTRACT.json",C/"release_logic.py",Path(__file__)]
    before={str(p):sha(p) for p in paths}
    documents=[load(p) for p in paths[:4]]
    cases=[]
    def check(name,ok,detail=None):
        cases.append(dict(name=name,passed=bool(ok),detail=detail))
    errors=review_package(*documents)
    check("actual_bound_contract_package",not errors,errors)
    package_controls=[
        ("missing_instance",lambda d:d[1]["instance_interfaces"].pop(),"INSTANCE_COVERAGE"),
        ("duplicate_owner",lambda d:d[1]["instance_interfaces"][1].update(mass_owner=d[1]["instance_interfaces"][0]["mass_owner"]),"DUPLICATE_OWNER"),
        ("role_swap",lambda d:d[1]["instance_interfaces"][0].update(representation_role="VIEW_ONLY"),"IDENTITY_OR_ROLE_MISMATCH"),
        ("invented_mate",lambda d:d[1]["instance_interfaces"][0].update(to_instance="NOT_REAL"),"INVENTED_MATE"),
        ("invented_connection_PASS",lambda d:d[1]["instance_interfaces"][0].update(physical_connection_verified=True),"UNSUPPORTED_PHYSICAL_CONNECTION"),
        ("transform_drift",lambda d:d[1]["instance_interfaces"][0]["state_transforms"].update(service=None),"TRANSFORM_MISMATCH"),
        ("zero_filled_velocity",lambda d:d[2]["joint_limit_contracts"][0]["physical_velocity_limit"].update(value=0),"PHYSICAL_LIMIT_ZERO_OR_INVENTED"),
        ("raw_limit_changed",lambda d:d[2]["joint_limit_contracts"][0]["raw_urdf_limit_attributes"].update(upper="99"),"RAW_URDF_CHANGED"),
        ("legacy_PASS",lambda d:d[2].update(legacy_control_contact_SAFE00_PASS_inherited=True),"LEGACY_PASS_INHERITANCE"),
        ("invented_sensor",lambda d:d[3]["sensor_confirmation_table"][0].update(threshold=0),"INVENTED_SENSOR"),
        ("hardware_enabled",lambda d:d[3].update(hardware_execution_enabled=True),"HARDWARE_OR_SAFE00_PROMOTION"),
        ("physical_mass_complete",lambda d:d[2]["mass_summary"]["service"].update(full_physical_mass_properties_complete=True),"PHYSICAL_MASS_COMPLETENESS_PROMOTION"),
    ]
    for name,mutate,expected in package_controls:
        d=copy.deepcopy(documents);mutate(d);e=review_package(*d)
        check(name,expected in e,e)
    if documents[1].get("named_geometric_connections"):
        connection_controls=[
            ("R07_missing_member",lambda d:d[1]["named_geometric_connections"]["connections"][0]["body_ids"].pop(),"R07_CONNECTION_FIELDS_CHANGED_OR_OMITTED"),
            ("R07_missing_bore",lambda d:d[1]["named_geometric_connections"]["connections"][0]["bore_segments"].pop(),"R07_CONNECTION_FIELDS_CHANGED_OR_OMITTED"),
            ("R07_missing_path",lambda d:d[1]["named_geometric_connections"]["connections"][0]["paths"].pop(),"R07_CONNECTION_FIELDS_CHANGED_OR_OMITTED"),
            ("R07_zero_preload",lambda d:d[1]["named_geometric_connections"].update(nominal_preload_N=0),"R07_PHYSICAL_PROMOTION"),
            ("R07_stale_review",lambda d:d[1]["named_geometric_connections"]["review"].update(sha256="0"*64),"R07_REVIEW_HASH_MISMATCH"),
            ("R07_missing_local_id",lambda d:d[1]["named_geometric_connections"]["local_instance_ids"].pop(),"R07_LOCAL_IDENTITY_MISMATCH"),
            ("R07_wrong_units",lambda d:d[1]["named_geometric_connections"].update(units="m"),"R07_UNITS_OR_FRAME"),
        ]
        for name,mutate,expected in connection_controls:
            d=copy.deepcopy(documents);mutate(d);e=review_package(*d)
            check(name,expected in e,e)
    binding=dict(configuration_id=documents[2]["identity"]["configuration_id"],receipt_sha256="a"*64,contract_sha256="b"*64,snapshot_id="SYNTHETIC_01")
    def signal(value=True):
        return dict(value=value,valid=True,health="OK",timestamp_s=100.)
    def fixture(action):
        rules=mod.STATION_REQUIREMENTS[action]
        stations=[]
        for sid in ("A","B"):
            sig={k:signal(v) for k,v in rules.items()}
            for a,b in mod.OPPOSED:
                if a in sig:
                    sig[b]=signal(not sig[a]["value"])
            stations.append(dict(station_id=sid,signals=sig))
        glob={k:signal() for k in (*mod.GLOBAL_REQUIRED,"residual_load_unloaded","arm_stationary","arm_drive_healthy","arm_service_ready")}
        return dict(schema="WP04_OFFLINE_RELEASE_SNAPSHOT_V1",action=action,binding=copy.deepcopy(binding),
            timestamp_s=100.,source_class="OFFLINE_DESIGN_FIXTURE",global_signals=glob,stations=stations,
            wings=[dict(wing_id=s,signals={"stowed_and_held":signal(action!="SERVICE_ARM_MOTION"),"deployed_and_locked":signal(action=="SERVICE_ARM_MOTION")}) for s in ("-Y","+Y")])
    def run_case(name,action,packet,blocked=True,now=100.1,age=1.,expected=None):
        result=mod.evaluate_release_step(action,packet,binding if expected is None else expected,now,age)
        check(name,(result["logical_status"]=="BLOCKED")==blocked and result["hardware_command_authorized"] is False and result["hardware_command_issued"] is False and result["legacy_SAFE00_credit_inherited"] is False,result)
    for action in mod.STATION_REQUIREMENTS:
        run_case("synthetic_valid_"+action,action,fixture(action),False)
    action="ARM_FIRST_MOTION"
    mutations=[
        ("disconnected",lambda p:p["stations"][0]["signals"]["pin_clear"].update(health="DISCONNECTED")),
        ("half_released",lambda p:p["stations"][1]["signals"]["shoe_clear"].update(value=False)),
        ("unknown",lambda p:p["stations"][1]["signals"]["cap_clear"].update(value=None)),
        ("string_true",lambda p:p["stations"][1]["signals"]["cap_clear"].update(value="True")),
        ("zero_signal",lambda p:p["stations"][1]["signals"]["cap_clear"].update(value=0)),
        ("contradictory",lambda p:p["stations"][0]["signals"]["pin_locked"].update(value=True)),
        ("timeout",lambda p:p.update(timestamp_s=98.)),
        ("future",lambda p:p.update(timestamp_s=101.)),
        ("boolean_time",lambda p:p.update(timestamp_s=True)),
        ("stale_signal",lambda p:p["stations"][0]["signals"]["pin_clear"].update(timestamp_s=0)),
        ("missing_station",lambda p:p["stations"].pop()),
        ("duplicate_station",lambda p:p["stations"][1].update(station_id="A")),
        ("missing_signal",lambda p:p["stations"][0]["signals"].pop("pin_clear")),
        ("invalid_sensor",lambda p:p["stations"][0]["signals"]["pin_clear"].update(valid=False)),
        ("loss_of_power",lambda p:p["global_signals"]["power_healthy"].update(value=False)),
        ("harness_blocked",lambda p:p["global_signals"]["harness_clear"].update(value=False)),
        ("driver_fault",lambda p:p["global_signals"]["arm_drive_healthy"].update(value=False)),
        ("wrong_action",lambda p:p.update(action="OPEN_CAPS")),
        ("wrong_configuration",lambda p:p["binding"].update(configuration_id="OLD")),
        ("wrong_hash",lambda p:p["binding"].update(receipt_sha256="0"*64)),
        ("wrong_snapshot",lambda p:p["binding"].update(snapshot_id="REPLAY")),
        ("unsupported_real_source",lambda p:p.update(source_class="HARDWARE")),
        ("missing_wing",lambda p:p["wings"].pop()),
        ("duplicate_wing",lambda p:p["wings"][1].update(wing_id="-Y")),
        ("wing_not_stowed",lambda p:p["wings"][0]["signals"]["stowed_and_held"].update(value=False)),
        ("mast_unlocked",lambda p:p["stations"][0]["signals"]["mast_park_locked"].update(value=False)),
        ("contradictory_wing",lambda p:p["wings"][0]["signals"]["deployed_and_locked"].update(value=True)),
    ]
    for name,mut in mutations:
        p=fixture(action);mut(p);run_case(name,action,p)
    run_case("no_packet",action,None)
    run_case("array_packet",action,[])
    run_case("unknown_action","OTHER",fixture(action))
    run_case("nonstring_action",[],fixture(action))
    run_case("invalid_age",action,fixture(action),age=None)
    run_case("nan_clock",action,fixture(action),now=float("nan"))
    run_case("missing_context",action,fixture(action),expected={})
    initial=fixture("WITHDRAW_PINS")
    initial["stations"][0]["signals"]["pin_locked"]["value"]=False
    run_case("not_clear_does_not_imply_locked","WITHDRAW_PINS",initial)
    after={str(p):sha(p) for p in paths}
    check("source_files_unchanged",before==after)
    output=dict(schema="WP04_DIGITAL_BODY_SOFTWARE_CONTROLS_V1",binding_mode=documents[0]["binding_mode"],
        final_candidate_bound=documents[0]["final_candidate_bound"],cases=cases,case_count=len(cases),all_passed=all(c["passed"] for c in cases),
        source_sha256_before=before,source_sha256_after=after,
        scope="Actual contract data review plus synthetic offline fault controls; independent of SAFE-00; no CAD/dynamics/hardware execution",
        hardware_executed=False,control_gate=False,physical_sensor_calibrated=False)
    OUT.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(dict(all_passed=output["all_passed"],case_count=len(cases),failed=[c["name"] for c in cases if not c["passed"]],output=str(OUT)),ensure_ascii=False))
    raise SystemExit(0 if output["all_passed"] else 1)

if __name__=="__main__":
    main()
