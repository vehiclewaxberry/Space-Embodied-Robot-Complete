"""Source-bound WP04 contracts, stdlib only. --final requires actual WP04 outputs."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
RUN = Path(__file__).resolve().parents[1]
WORKSPACE = next(p for p in RUN.parents if (p / "PROJECT_MAP.md").is_file())
BASELINE = RUN.parent / "wp03_bounded_20260906_161431/candidate"
CONTRACTS = RUN / "contracts"
STATES = ("parking", "released", "service")

def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))

def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def save(name, data):
    path = CONTRACTS / name
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)
    return path

def scalar_unknown(unit, reason):
    return dict(value=None, unit=unit, status="UNKNOWN", source=None, uncertainty=None, reason=reason)

SYSTEMS = [
 ("DB01", "整机表示／坐标", ["B601_ARM"], ["R02", "R08", "R09", "R10", "R11", "R13", "R15"],
  ["每实例几何源/表示用途/shape有效性/T_S_local", "S/A0/安装面/腕/TCP/相机/F/T映射方向", "双指/相邻关节/闭体包含/臂星体/连续路径分账"], ["AS_BUILT_BREP_STL_REGISTRATION", "FULL_ASSEMBLY_COLLISION_COVERAGE"]),
 ("DB02", "机械臂驱动／限位", ["B601_ARM", "EQUIPMENT_BAY"], ["R08", "R12", "R14"],
  ["数字q范围与物理止挡/软限位分列", "供电/连续峰值力矩速度/回生/温升/失电制动", "编码器零位误差/停止距离/控制接口"], ["PHYSICAL_DRIVE_ENVELOPE", "STOPPING_MARGIN", "ENCODER_CALIBRATION"]),
 ("DB03", "双站保持／释放机构", ["ONBOARD_RETENTION"], ["R03", "R04", "R05", "R16"],
  ["导杆双端座/销俘获/真实拉拔连接", "盖轴枢轴防脱/实体止挡/退出锁止", "力行程/预紧/储能/阻尼/卸载后释放"], ["ACTUATOR_SELECTION", "LOADED_RELEASE_CAPACITY", "TERMINAL_LOCK_VERIFICATION"]),
 ("DB04", "释放能源／传感确认", ["ONBOARD_RETENTION", "HARNESS", "EQUIPMENT_BAY"], ["R03", "R05"],
  ["双站销/上下接触/折退终位确认", "传感器靶标/阈值迟滞/有效性/时间戳超时", "EPS针脚/回流保护/使能和故障影响"], ["SENSOR_SELECTION_AND_CALIBRATION", "POWER_DATA_ICD", "FAULT_RESPONSE_VALIDATION"]),
 ("DB05", "双三叶翼机构", ["SOLAR_WING"], ["R02", "R05", "R12", "R14"],
  ["根及叶间关节/防脱/止挡锁闩", "HDRM驱动储能安装及释放", "翼臂共同顺序/服务环/锁止确认"], ["HDRM_SELECTION", "WING_DEPLOYMENT_DRIVE", "WING_HARNESS_ENVELOPE"]),
 ("DB06", "线束与连接器", ["HARNESS", "SOLAR_WING"], ["R03", "R05", "R12"],
  ["逐段端点link frame/夹点/自由长度外径", "动态弯曲扭转/恢复力/寿命/摩擦夹挤", "插头针脚/插拔方向/尾壳应力释放"], ["DYNAMIC_HARNESS_LIMITS", "CONNECTOR_AND_PINOUT_SELECTION", "HARNESS_MASS_SCOPE"]),
 ("DB07", "腕部F/T／工具／抓持", ["B601_ARM", "EXTERNAL_INTERFACES"], ["R02", "R12", "R13"],
  ["腕-F/T-工具-TCP及法兰止口紧固", "夹指接触垫目标双方/有效行程确认", "负载质量惯量/外参线缆/换工具路径"], ["WRIST_STACK_ICD", "PHYSICAL_GRIPPER_LIMITS", "TARGET_CONTACT_INPUTS"]),
 ("DB08", "设备与热安装", ["EQUIPMENT_BAY", "THERMAL", "COVERS"], ["R12", "R14"],
  ["型号孔系连接器/插拔抽出路径", "功耗导热面热阻/绝缘应力释放", "预算总成包含及实件替换"], ["EQUIPMENT_SELECTION", "THERMAL_POWER_INPUTS", "EQUIPMENT_MASS_DISTRIBUTION"]),
 ("DB09", "姿控／推进／感知", ["EQUIPMENT_BAY", "EXTERNAL_INTERFACES"], ["R12"],
  ["轮轴配置/力矩动量及安装", "推进位置方向力臂/喷流禁区", "相机星敏视场/标定/臂翼遮挡"], ["ADCS_ACTUATOR_ALLOCATION", "PROPULSION_ICD", "SENSOR_EXTRINSICS_FOV"]),
 ("DB10", "发射／地面工装", ["LAUNCH_INTERFACE"], ["R06"],
  ["开放停放/发射收拢/AIT分开", "供应接口/整机包络载荷/分离禁区", "工装支点能力/重力卸载拆装"], ["LAUNCHER_SEPARATION_ICD", "LAUNCH_LOADS", "AIT_SUPPORT_CAPACITY"]),
 ("DB11", "维护工具／接头工艺", ["ROOT_STRUCTURE", "PRIMARY_STRUCTURE", "R01_FASTENERS", "COVERS", "EQUIPMENT_BAY"], ["R01", "R07"],
  ["接头对偶定位/紧固方向/长度夹层", "螺纹材料预紧防松公差", "后装设备热垫盖板路径及真实工具"], ["FASTENER_SELECTION_AND_PRELOAD", "MANUFACTURING_TOLERANCE", "ASSEMBLY_PROCESS"]),
]

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args(argv)
    here = RUN / "candidate" if args.final else BASELINE
    inputs = [here / "results" / (s + "_instances.json") for s in STATES]
    inputs += [here / "results/DYNAMICS_HANDOFF.json", here / "BOM.csv", here / "INTERFACES.csv", here / "design_parameters.json"]
    if not all(p.is_file() for p in inputs):
        raise ValueError("FINAL_INPUT_SET_INCOMPLETE" if args.final else "BASELINE_INPUT_SET_INCOMPLETE")
    receipts = {s: load(here / "results" / (s + "_instances.json")) for s in STATES}
    h = load(here / "results/DYNAMICS_HANDOFF.json")
    params = load(here / "design_parameters.json")
    rows = receipts["service"]["instances"]
    ids = {r["id"] for r in rows}
    if len(ids) != len(rows) or len({r["mass_owner"] for r in rows}) != len(rows):
        raise ValueError("DUPLICATE_INSTANCE_OR_OWNER")
    if any(d["state"] != s or d["view"] != "complete" or {r["id"] for r in d["instances"]} != ids for s, d in receipts.items()):
        raise ValueError("STATE_VIEW_IDENTITY_MISMATCH")
    if args.final and any(Path(h["receipt_bindings"][s]["receipt_path"]).resolve() != inputs[i].resolve() or h["receipt_bindings"][s]["receipt_sha256"] != sha(inputs[i]) for i, s in enumerate(STATES)):
        raise ValueError("FINAL_HANDOFF_RECEIPT_BINDING_MISMATCH")
    if args.final and any(not Path(p).is_file() or sha(p)!=v for p,v in h["input_sha256"].items()):
        raise ValueError("FINAL_HANDOFF_INPUT_HASH_MISMATCH")
    historical = [
        WORKSPACE / "20_engineering/service_robot_wp01_20260905/interface_requirements.csv",
        WORKSPACE / "20_engineering/service_robot_wp03_spacecraft_body_r1/ASSEMBLY_SEQUENCE.md",
        WORKSPACE / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/16_EMBODIED_MECHANICAL_CONTRACT.yaml",
        WORKSPACE / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/10_GRIPPER_INTERFACE.yaml",
        WORKSPACE / "10_research/space_embodied_robotics/comp_prot_03_a3_g0_digital_body_method/digital_body_record.schema.json",
    ]
    urdf = WORKSPACE / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
    inputs += historical + [urdf, Path(__file__).resolve(), CONTRACTS / "release_logic.py"]
    geometric = None
    geometric_by_instance = {}
    if args.final:
        cp=here/"results/R07_CONNECTION_CONTRACT.json"
        rp=RUN/"review/R07_REVIEW_FINAL.json"
        if not cp.is_file() or not rp.is_file():
            raise ValueError("R07_FINAL_CONNECTION_OR_REVIEW_MISSING")
        raw=load(cp); review=load(rp)
        if raw.get("run_id")!=RUN.name or raw.get("configuration")!=params["configuration_id"] or raw.get("units")!="mm" or raw.get("frame")!="S":
            raise ValueError("R07_CONNECTION_CONFIGURATION_MISMATCH")
        if raw["source_sha256"]!=sha(here/"r07_design.py"):
            raise ValueError("R07_CONNECTION_SOURCE_MISMATCH")
        checks=review.get("input_sha256_before",{})
        if not checks or checks!=review.get("input_sha256_after") or checks.get(str(cp.resolve()))!=sha(cp):
            raise ValueError("R07_REVIEW_INPUT_BINDING_MISMATCH")
        if any(not Path(p).is_file() or sha(p)!=v for p,v in checks.items()):
            raise ValueError("R07_REVIEW_STALE_INPUT")
        cs=raw["connections"]
        if len({c["connection_id"] for c in cs})!=len(cs) or not set(raw["local_instance_ids"])<=ids:
            raise ValueError("R07_CONNECTION_OR_LOCAL_IDENTITY_MISMATCH")
        for c in cs:
            members=set(c["body_ids"])|set(c["hardware"].values())
            if c.get("sleeve_id"):members.add(c["sleeve_id"])
            if not members<=ids:
                raise ValueError("R07_MEMBER_ABSENT_FROM_FINAL_ASSEMBLY")
            if any(c.get(k) is not None for k in ("physical_thread_engagement_mm","preload_N","strength_pass")):
                raise ValueError("R07_UNSUPPORTED_PHYSICAL_PROMOTION")
            for member in members:
                geometric_by_instance.setdefault(member,[]).append(c)
        inputs += [cp,rp]+[Path(p) for p in checks]
        geometric=dict(source=dict(path=str(cp.resolve()),sha256=sha(cp)),
            review=dict(path=str(rp.resolve()),sha256=sha(rp),status=review["status"]),
            frame=raw["frame"],units=raw["units"],connections=cs,
            local_instance_ids=raw["local_instance_ids"],affected_instance_ids=raw["affected_instance_ids"],
            load_path_edges=raw.get("load_path_edges"),sleeve_installation=raw.get("sleeve_installation"),
            intentional_unqualified_thread_regions=raw.get("intentional_unqualified_thread_regions"),
            remaining=raw["remaining"],physical_assembly_completed=False,manufacturing_release=False,
            scope="REGISTERED_NOMINAL_MATING_GEOMETRY_AND_DECLARED_ASSEMBLY_PHASE_PATHS_ONLY",
            geometry_result_counts={k:dict(count=len(review.get(k,[])),by_status={v:sum(x.get("status")==v for x in review.get(k,[])) for v in sorted({str(x.get("status")) for x in review.get(k,[])})}) for k in ("holes","bearing_faces","paths")},
            nominal_material_grade=None,nominal_preload_N=None,strength_pass=None)
    pins = {str(p.resolve()): sha(p) for p in inputs}
    envelope = dict(run_id=RUN.name, binding_mode="FINAL_CURRENT_CANDIDATE" if args.final else "BASELINE_DEVELOPMENT_REFERENCE",
                    final_candidate_bound=args.final, source_candidate=str(here.resolve()), input_sha256=pins,
                    historical_gate_changed=False, hardware_verified=False, scientific_gate=False, control_gate=False)
    state_rows = {s:{r["id"]:r for r in d["instances"]} for s,d in receipts.items()}
    iface = []
    for idx,r in enumerate(rows):
        mount = r.get("mount_interface")
        target = mount if mount in ids else None
        named=geometric_by_instance.get(r["id"],[])
        features=[dict(connection_id=c["connection_id"],
            body_ids=c["body_ids"],bore_segments=[b for b in c["bore_segments"] if b["instance_id"]==r["id"]],
            bearing_faces=[b for b in c["bearing_faces"] if r["id"] in (b["member_id"],b["hardware_id"])],
            hardware=c["hardware"],axis=c["axis"],origin_mm=c["origin_mm"],frame="S",unit="mm") for c in named]
        iface.append(dict(interface_id="MOUNT::" + r["id"], from_instance=r["id"],
            to_instance=target, unresolved_logical_mount=None if target else mount,
            parent_assembly=r["parent_assembly"], from_frame="INSTANCE::" + r["id"],
            to_frame="INSTANCE::" + target if target else None, frame_reference="S", length_unit="mm",
            state_transforms={s:state_rows[s][r["id"]].get("T_S_local") for s in STATES},
            mating_transform=None, joint_type="NOMINAL_FASTENED_MULTI_MEMBER_CONNECTION" if named else None, allowed_DOF=None,
            mating_features=features or None,geometric_connection_ids=[c["connection_id"] for c in named],
            fit_tolerance=None, fastening_preload=None, electrical_pinout=None, thermal_resistance=None,
            assembly_and_tool_path_evidence=[dict(connection_id=c["connection_id"],assembly_stage=c["assembly_stage"],
                path_ids=[p["path_id"] for p in c["paths"]],review=geometric["review"]) for c in named] or None,
            physical_connection_verified=False,
            geometry_evidence_scope=r.get("evidence_scope"), product_role=r["product_role"],
            representation_role=r["representation_role"], source_revision=r["source_revision"],
            mass_owner=r["mass_owner"], status="REGISTERED_NOMINAL_GEOMETRY_PHYSICAL_CLOSURE_UNKNOWN" if named else "DECLARED_MOUNT_REFERENCE_NOT_MATING_VERIFICATION",
            trace={"receipt":str((here/"results/service_instances.json").resolve()),"json_pointer":"/instances/"+str(idx)}))
    systems = []
    for code,name,groups,issues,required,missing in SYSTEMS:
        systems.append(dict(system_id=code,name_zh=name,issue_ids=issues,
            applicable_instances=[r["id"] for r in rows if code=="DB01" or r["parent_assembly"] in groups],
            required_contract_items_zh=required,unresolved_input_ids=missing,
            design_status="CONTRACT_DEFINED_PHYSICAL_CLOSURE_NOT_INFERRED",
            component_existence_does_not_prove_function=True,hardware_verified=False))
    masses = {}
    for state in h["states"]:
        if state["state"] in STATES:
            g = state["groups"]["ONBOARD_CANDIDATE"]
            masses[state["state"]] = dict(allocated_mass_kg=g["known_mass_kg"],positive_owner_count=len(g["mass_atoms"]),
                unknown_owner_count=len(g["unknown_mass_instances"]),total_instance_count=g["instance_count"],
                full_physical_mass_properties_complete=state["onboard_full_physical_mass_properties_complete"])
    mounts=save("SYSTEM_INTERFACES.json",dict(schema="WP04_SYSTEM_INTERFACES_V1",**envelope,instance_count=len(rows),
        interface_count=len(iface),systems=systems,instance_interfaces=iface,
        named_geometric_connections=geometric,
        note_zh="to_instance仅在原mount标签精确命中实例ID时填写；不代表孔系/承载/接合方式验证。其余逻辑挂载明确未解析。",
        system_requirements_cover_absent_components=True))
    limits=[]
    for joint in ET.parse(urdf).getroot().findall("joint"):
        lim=joint.find("limit")
        limits.append(dict(joint=joint.attrib["name"],type=joint.attrib["type"],
            parent=joint.find("parent").attrib["link"],child=joint.find("child").attrib["link"],
            raw_urdf_limit_attributes=None if lim is None else dict(lim.attrib),raw_source_sha256=sha(urdf),
            numeric_source_limit=next(j["limit"] for j in h["source_joint_tree"] if j["name"]==joint.attrib["name"]),
            kinematic_position_unit="m" if joint.attrib["type"]=="prismatic" else "rad" if joint.attrib["type"]=="revolute" else None,
            raw_velocity_physical_unit_authority=None,physical_velocity_limit=scalar_unknown(None,"数字源字段不是物理速度单位和实测边界"),
            physical_effort_limit=scalar_unknown("N" if joint.attrib["type"]=="prismatic" else "N*m","未绑定连续/峰值驱动及温度工况"),
            mechanical_hard_stop=scalar_unknown(None,"缺实物止挡图/测量"),
            controller_soft_limit=scalar_unknown(None,"缺标定误差和停止距离"),stopping_margin=scalar_unknown(None,"缺驱动延迟/减速能力"),
            encoder_zero_calibration=None,brake_power_loss_state=None,motor_thermal_duty_envelope=None,raw_values_are_not_hardware_limits=True))
    consumers=[
        dict(consumer="DISPLAY",status="CURRENT_DECLARED_INSTANCES_ONLY" if args.final else "BASELINE_REFERENCE_ONLY",required=["instance_identity","geometry_hash","state_transform","view_role"],blocked_by=[]),
        dict(consumer="ARM_FORWARD_KINEMATICS",status="SOURCE_DIGITAL_ONLY",required=["accepted_urdf","q_finger","T_S_arm_base","units"],blocked_by=["AS_BUILT_REGISTRATION"]),
        dict(consumer="ALLOCATED_MASS_COM_INERTIA",status="PARTIAL_CANDIDATE_ONLY",required=["unique_mass_owner","source_and_distribution","state_transform"],blocked_by=["UNKNOWN_MASS_OR_SCOPE","MEASUREMENT_PENDING"]),
        dict(consumer="FULL_ASSEMBLY_COLLISION",status="UNKNOWN",required=["all_required_instance_pairs","representation_validity","containment_and_finger_coverage","same_snapshot"],blocked_by=["COVERAGE_NOT_ESTABLISHED_BY_THIS_CONTRACT"]),
        dict(consumer="FREE_FLOATING_DYNAMICS",status="INPUT_CONTRACT_ONLY",required=["per_link_inertia","free_base_state","joint_velocity_acceleration","external_wrench","flex_contact_scope"],blocked_by=["PHYSICAL_UNKNOWNS","NEW_MODEL_VALIDATION"]),
        dict(consumer="HARDWARE_CONTROL_OR_RELEASE",status="BLOCKED_PHYSICAL_INPUTS",required=["actuator_model","calibrated_state","valid_timing","power_fault_interface"],blocked_by=["PHYSICAL_DRIVE_ENVELOPE","SENSORS_AND_STOPPING_MARGIN"]),
        dict(consumer="CONTACT_GRASP",status="BLOCKED_PHYSICAL_INPUTS",required=["TCP_target_frames","contact_geometry","force_friction_compliance","sensor_calibration"],blocked_by=["WRIST_STACK_ICD","TARGET_CONTACT_INPUTS"]),
        dict(consumer="RL_VLA_POLICY_EXECUTION",status="NOT_IMPLEMENTED_BY_THIS_PACKAGE",required=["action_context_snapshot","dynamics_backend","independent_veto","state_evolution"],blocked_by=["NO_RUNTIME_BACKEND_OR_CONTROL_VALIDATION"]),
    ]
    body=save("DIGITAL_BODY_CONSUMER_CONTRACT.json",dict(schema="WP04_DIGITAL_BODY_CONSUMER_CONTRACT_V1",**envelope,
        identity=dict(configuration_id=params["configuration_id"],states=list(STATES),instance_ids=sorted(ids),arm_links=sorted(r["arm_link"] for r in rows if r.get("arm_link"))),
        frame_policy=dict(S=params.get("frame_S"),T_S_arm_base=receipts["service"]["T_S_arm_base"],
            CAD_length="mm",URDF_length="m",URDF_angle="rad",mass="kg",inertia="kg*m^2",
            T_S_dynamic_base=None,T_WRIST_FT=None,T_FT_TOOL=None,T_TOOL_TCP=None,
            note_zh="S到安装根的固定变换不等于自由漂浮基座初态，frame原点不等于承压面。"),
        geometry=dict(mode=receipts["service"].get("composition_mode"),monolithic_complete_step_generated=receipts["service"].get("monolithic_complete_step_generated"),
            arm_BRep_and_accepted_STL_equivalent=False,complete_view_requires_exact_instance_membership=True,exploded_view_consumer="DISPLAY_ONLY"),
        mass_summary=masses,mass_rule="唯一owner计一次；raw和allocated列不可相加；总成预算替换而非叠加；unknown不得零填；GSE和目标分账",
        joint_limit_contracts=limits,consumer_readiness=consumers,legacy_control_contact_SAFE00_PASS_inherited=False,
        system_interfaces=dict(path=str(mounts.resolve()),sha256=sha(mounts)),
        physical_unknowns={k:None for k in ("unknown_mass_bounds","actuator_dynamics","sensor_latency_calibration","dynamic_harness_limits","wheel_axis_allocation","thruster_positions_directions","physical_TCP_contact","flex_parameters_current_configuration","launcher_ICD")}))
    sys.path.insert(0,str(CONTRACTS))
    from release_logic import STATION_REQUIREMENTS,OPPOSED
    release=save("RELEASE_STATE_CONTRACT.json",dict(schema="WP04_RELEASE_STATE_CONTRACT_V1",**envelope,
        scope="OFFLINE_DESIGN_PRECONDITIONS_ONLY_NO_HARDWARE_DRIVER",hardware_execution_enabled=False,
        legacy_SAFE00_dependency=False,sequence=list(STATION_REQUIREMENTS),
        nominal_geometry=params.get("retention"),station_ids=["A","B"],wing_ids=["-Y","+Y"],
        actions=[dict(action=a,station_requirements=rules,timeout_s=None,force_or_torque_limit=None,
            power_and_energy_requirement=None,actual_sensor_evidence=None,
            hardware_status="UNKNOWN_PHYSICAL_SELECTION_AND_CALIBRATION") for a,rules in STATION_REQUIREMENTS.items()],
        sensor_confirmation_table=[dict(station=s,signal=name,associated_instance=(None if name=="mast_park_locked" else f"hold_confirm_{tag}_{i}" if tag else f"hold_position_sensor_{i}"),
            association_scope="DEDICATED_LOCK_SENSOR_NOT_ESTABLISHED" if name=="mast_park_locked" else "EXISTING_FUNCTIONAL_ENVELOPE_NOT_SELECTED_SENSOR",sensor_type=None,target_geometry=None,
            threshold=None,hysteresis=None,max_latency_s=None,calibration=None,wire_pinout=None,
            diagnostic_states=["VALID_TRUE","VALID_FALSE","UNKNOWN","DISCONNECTED","TIMEOUT","CONTRADICTORY"])
            for i,s in enumerate(("A","B")) for name,tag in (("pin_clear","latch"),("cap_clear","cap"),("shoe_clear","shoe"),("mast_folded",None),("mast_park_locked",None))],
        contradictory_signal_pairs=OPPOSED,
        failure_rule_zh="缺失/无效/断线/UNKNOWN/超时/矛盾/单站或半释放均阻塞依赖动作；逻辑测试满足不产生硬件许可。",
        actual_policy_timing=dict(max_snapshot_age_s=None,action_timeouts_s=None,trusted_clock=None,nonce_store=None),
        evaluator=dict(path=str((CONTRACTS/"release_logic.py").resolve()),sha256=sha(CONTRACTS/"release_logic.py")),
        consumer_contract=dict(path=str(body.resolve()),sha256=sha(body))))
    if pins!={p:sha(p) for p in pins}:
        raise ValueError("INPUT_CHANGED_DURING_CONTRACT_BINDING")
    save("CONTRACT_BINDING_MANIFEST.json",dict(schema="WP04_CONTRACT_BINDING_MANIFEST_V1",**envelope,
        input_unchanged=True,outputs={str(p.resolve()):sha(p) for p in (mounts,body,release)},
        counts=dict(instances=len(rows),interfaces=len(iface),systems=len(systems),joint_contracts=len(limits),
            named_geometric_connections=0 if geometric is None else len(geometric["connections"]))))
    text=f"""# WP04 数字身体与全系统接口合同

当前绑定：**{envelope['binding_mode']}**；来源 {here}。共有{len(rows)}个实例、{len(iface)}条逐实例挂载记录、{len(systems)}类系统合同和{len(limits)}条原始关节合同。

本包覆盖几何、物理属性、任务语义和证据四层。当前用户授权用于机械设计和数字装配；历史裁决保持原范围。合同字段完整不等于物理输入已落实。

- SYSTEM_INTERFACES.json：继承实例角色、质量owner和三态变换；挂载名准确命中实际实例才解析对端，否则保留逻辑接口。最终版并入R07具名多端连接、孔段、承压面、紧固件及指定装配阶段路径，绑定R07_REVIEW_FINAL.json；材料等级/预紧/螺纹/强度保持未知。其余未登记对偶、针脚和热阻仍为null。
- DIGITAL_BODY_CONSUMER_CONTRACT.json：原始关节范围/effort/velocity与物理限位分账。源velocity 50/200、夹指15没有可继承的物理单位权威；不自动转成硬件限幅。质量按唯一owner计一次，未知不得零填。
- RELEASE_STATE_CONTRACT.json：退销→开盖→下鞋退离→折退锁止→臂首动→翼展开→服务动作前置确认。传感器、阈值、时限、功耗及载荷未实选字段未知。
- release_logic.py：只做离线合同检查，不读硬件、不发命令、不替代SAFE-00或Sim13；合成样例满足时hardware_command_authorized仍为false。

整机图必须与收据实例集合、arm_link和三态变换一致。名义BRep、accepted STL、功能包络和爆炸示意有不同用途。全臂可见不等于拓扑、双指、包含、臂星体或连续路径通过。

设备/ADCS/推进、腕部F/T/TCP、线束、翼HDRM和发射接口有具名缺项。旧控制/接触PASS不移入本候选。静态整体惯量只用于锁定相对运动的该姿态；运动模型保留逐link自由度和未知项。

最终生成后依次运行 python -B contracts/bind_contracts.py --final；python -B review/digital_body_controls.py；python -B review/robot_actual_ledger.py。不带--final的合同明确来自R01开发基线，不是WP04最终证据。
"""
    (CONTRACTS/"数字身体与接口说明_ZH.md").write_text(text,encoding="utf-8")
    print(json.dumps(dict(binding=envelope["binding_mode"],instances=len(rows),interfaces=len(iface),outputs=str(CONTRACTS)),ensure_ascii=False))

if __name__=="__main__":
    main()
