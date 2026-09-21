"""Read-only evidence routing. Never imports/runs simulation or CAD code."""
from pathlib import Path
import csv, hashlib, json, math, xml.etree.ElementTree as ET
from datetime import datetime, timezone
import yaml

OUT = Path(__file__).resolve().parent
ROOT = next(p for p in OUT.parents if (p / 'PROJECT_MAP.md').exists())
C = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion'
P13 = '30_simulation/sim_13_physics_gated_embodied_grasping/'
V4 = P13 + 'v4_synthetic_contact_capture_diagnostic/'
SOURCES = {
 'sim05_readme':'30_simulation/sim_05_free_floating_arm/README_sim_05.md',
 'sim05_csv':'30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv',
 'arm_urdf':'20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf',
 'legacy_mass':'20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv',
 'sim10':'30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json',
 'sim10_config':'20_engineering/config/mission_feasibility/scan_v0.yaml',
 'sim11':'30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json',
 'sim11_config':'20_engineering/config/coupled_scene/coupled_model_v0.yaml',
 'contact_config':'20_engineering/config/coupled_scene/scene_A2_capture.yaml',
 'sim12':'30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json',
 'e23':'30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json',
 'e23_config':'30_simulation/e23_r2_full_flex_coupled_recert/config/e23_config.yaml',
 'e15':'30_simulation/e15_ancf_certification/results/gate_summary.json',
 'r2_release':'20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json',
 'r2_interface':'20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/15_UNIFIED_R2_SYSTEM_INTERFACE.yaml',
 'r2_mass':'20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml',
 'sim13_20':P13+'v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json',
 'sim13_phase_a':V4+'results/SIM13_V4A_PHASE_A_AUDITED_GATE_V3.json',
 'sim13_b4g_superseded':V4+'phase_b4g_post_freeze_synthetic_jaw_retraction_execution/results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json',
 'sim13_r2_source_only':V4+'phase_b4g_r2_post_freeze_numerical_preflight_execution/results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json',
 'safe':'30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json',
 'asm00':'30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json',
}
for name, path in {'current_delivery':'results/DELIVERY_STATUS.json','current_mass':'results/MASS_ROLLFORWARD_873.json','current_native':'results/NATIVE_DELTA_DELIVERY.json','current_dm':'software_native/DM_REFERENCE_CONFIG.json'}.items():
 SOURCES[name] = (C/path).relative_to(ROOT).as_posix()

def load(path):
 p=ROOT/path
 if p.suffix in ('.yaml','.yml'): return yaml.safe_load(p.read_text(encoding='utf-8-sig'))
 if p.suffix=='.json': return json.loads(p.read_text(encoding='utf-8-sig'))
 return p.read_text(encoding='utf-8-sig')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
 d={k:load(p) for k,p in SOURCES.items()}
 sources=[{'id':k,'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for k,p in SOURCES.items()]
 chains=[]
 def bind(owner,label,path,expected):
  p=ROOT/path
  actual=sha(p) if p.is_file() else None
  chains.append({'owner':owner,'binding':label,'path':Path(path).as_posix(),'expected_sha256':expected.lower(),'actual_sha256':actual,'status':'MATCH' if actual==expected.lower() else 'HASH_DRIFT' if actual else 'MISSING'})
 for k,v in d['sim10_config']['frozen_inputs'].items(): bind('sim10',k,v['path'],v['sha256'])
 for p,s in d['sim11']['artifacts_sha256'].items(): bind('sim11',p,'30_simulation/sim_11_coupled_dynamics/results/'+p,s)
 for k,v in d['e23_config']['source_pins'].items(): bind('e23_inputs',k,v['path'],v['sha256'])
 for p,s in d['e23']['evidence_hashes'].items(): bind('e23_evidence',p,p,s)
 v=d['sim13_20']['evidence']; bind('sim13_20','registry',v['path'],v['sha256'])
 for k,v in d['sim13_phase_a']['hash_chain'].items(): bind('sim13_phase_a',k,v['path'],v['sha256'])
 for k in ['mass_evidence']:
  v=d['current_delivery'][k];bind('current_delivery',k,(C/v['path']).relative_to(ROOT).as_posix(),v['sha256'])
 rows=list(csv.DictReader(d['sim05_csv'].splitlines()))
 urdf=ET.fromstring(d['arm_urdf'])
 arm_mass=math.fsum(float(e.attrib['value']) for e in urdf.findall('link/inertial/mass'))
 j2=urdf.find("joint[@name='joint2']/limit")
 sim05={'recorded_peak_deg':max(float(r['base_dev_angle_deg']) for r in rows),'recorded_max_q2_deg':max(float(r['q2_deg']) for r in rows),'urdf_joint2_upper_rad':float(j2.attrib['upper']),'arm_mass_kg_from_urdf':arm_mass,'total_model_mass_kg':25.2+arm_mass,'standalone_gate_json_located':False,'scope':'CSV and URDF read-only audit; README test results are historical, not rerun.'}
 r2c01=next(x for x in d['r2_mass']['configurations'] if x['configuration_id']=='C01')
 mapping=[
  {'model_id':'LEGACY_SIM05','mass_kg':sim05['total_model_mass_kg'],'arm_mass_kg':arm_mass,'geometry':'legacy arm_b601_v1; panels lumped into 24 kg servicer + 1.2 kg adapter','frame':'S/M/E in sim05 README; M at [0.18525,0,0] m, Ry(+90deg)','state':'6R; gripper locked; zero initial momentum benchmark','reuse_scope':'historical mathematical reaction benchmark; q2 out-of-limit cannot be a hardware trajectory','current_873_identity_bound':False,'source_ids':['sim05_csv','arm_urdf','legacy_mass','sim05_readme']},
  {'model_id':'LEGACY_SIM10_12','mass_kg':None,'arm_mass_kg':None,'geometry':'frozen capture stack from sim06/common; 24 kg is mu denominator, NOT a current whole-system mass','frame':'frozen capture impulse/target conventions','state':'9002 points / 16 strategy cells; rigid only; FLEX UNKNOWN','reuse_scope':'existing evidence analysis; reproduction requires original raw hash bindings restored or a separately versioned rebind','current_873_identity_bound':False,'source_ids':['sim10','sim10_config','sim12']},
  {'model_id':'LEGACY_SIM11','mass_kg':d['sim11']['gates']['G3c_all_rigid_vs_sim01']['composite']['mass_kg'],'arm_mass_kg':arm_mass,'geometry':'bus 23.3032134 kg plus 0.3483933 kg panel per side, legacy arm and adapter','frame':'coupled_scene/SSOT S + panel/target frames','state':'3 FFR modes per wing nominal; 20 ms contact PROVISIONAL; damping 0.005 provisional','reuse_scope':'bounded coupling methods and convergence evidence; not measured current panels/contact','current_873_identity_bound':False,'source_ids':['sim11','sim11_config','contact_config','legacy_mass']},
  {'model_id':'UNIFIED_R2_C01_E23','mass_kg':r2c01['mass']['value_kg'],'arm_mass_kg':arm_mass,'geometry':'19-link/18-joint R2 source-only interface; separate R2 seven-mode B1-B3/T1-T4 ROM','frame':'R2 C01 S; inertia about system COM; design uncertainty retained','state':'E23 18/18 bounded provisional; next false; release false','reuse_scope':'R2-only diagnostic evidence; no sim10 threshold inheritance and no 873 CAD transfer','current_873_identity_bound':False,'source_ids':['r2_mass','r2_interface','r2_release','e23','e23_config']},
  {'model_id':'SIM13_SYNTHETIC','mass_kg':None,'arm_mass_kg':None,'geometry':'handwritten synthetic 6R+2P spacecraft and separate 6DOF target','frame':'Phase-A declared inertial/frame/quaternion contract','state':'Phase-A audited no-contact kernel; later B4G tooling freeze is not numerical PASS','reuse_scope':'algorithm theory and existing synthetic evidence only; no R2/current CAD identity','current_873_identity_bound':False,'source_ids':['sim13_phase_a','sim13_b4g_superseded','sim13_r2_source_only']},
  {'model_id':'WP09_873_CAD','mass_kg':d['current_mass']['summary']['full_spacecraft_mass_kg'],'arm_mass_kg':None,'geometry':'873 leaf instances per fixed pose + 10 identity containers; not movable links','frame':'per-instance CAD transforms; research link/joint collision mapping unbound','state':'three static states; whole COM/inertia unknown; DM AS_BUILT limits/ratios unknown','reuse_scope':'source audit and future geometry/model contract; not a validated digital body','current_873_identity_bound':True,'source_ids':['current_native','current_mass','current_dm','current_delivery']}
 ]
 tasks=[
  {'task_id':'Q1_EXISTING_EVIDENCE','question_ids':['Q1'],'intent':'冻结可行域、绑定约束和负结果的只读证据整理','model_id':'LEGACY_SIM10_12','mode':'EVIDENCE_REVIEW','source_ids':['sim10','sim12'],'assumptions':['历史冻结模型与现行样机分开'],'missing_for_numerical_execution':['原始哈希锁的当前一致性处置','另行明确新数值任务范围'],'readiness':'EVIDENCE_AUDIT_READY'},
  {'task_id':'Q1_Q3_RIGID_BASELINE','question_ids':['Q1','Q3'],'intent':'自由漂浮刚体守恒、基座反作用与模型对照合同','model_id':'LEGACY_SIM05','mode':'THEORY_CONTRACT','source_ids':['sim05_csv','arm_urdf','sim05_readme'],'assumptions':['零外力矩/零初始动量研究假设','旧锚点越限仅为数学基准'],'missing_for_numerical_execution':['新可证伪任务与预注册对照','与真实允许构型分开的新输出根'],'readiness':'THEORY_CONTRACT_READY'},
  {'task_id':'Q2_Q3_CONTACT_FLEX','question_ids':['Q2','Q3'],'intent':'有限接触带宽与柔性保真度的模型研究合同','model_id':'UNIFIED_R2_C01_E23','mode':'THEORY_CONTRACT','source_ids':['e23','e23_config','sim11','contact_config'],'assumptions':['R2 EI/GJ/阻尼/接触参数均保留 provisional','固定版本且不转移到 WP09 873'],'missing_for_numerical_execution':['参数边界和对应科学问题','复核原输入哈希及适用域'],'readiness':'THEORY_CONTRACT_READY'},
  {'task_id':'Q3_Q4_GEOMETRY_AVOIDANCE','question_ids':['Q3','Q4'],'intent':'当前 CAD 的碰撞对象/禁入区/构型空间研究合同','model_id':'WP09_873_CAD','mode':'CURRENT_SYSTEM_MODEL','source_ids':['current_native','current_dm','current_mass'],'assumptions':['纯几何模型不默认需要整星准确质量','几何可行与动力学可执行分别评估'],'missing_for_numerical_execution':['873实例到刚性link/6R+夹爪的唯一映射','关节轴/符号/零位/界限及三态运动学一致性','保守collision代理误差及自碰撞/线束/帆板禁入区','连续扫掠而非仅三态检查'],'readiness':'CURRENT_SYSTEM_HOLD'},
  {'task_id':'Q1_Q3_CURRENT_DYNAMICS_CONTROL','question_ids':['Q1','Q2','Q3'],'intent':'以当前样机为对象的动力学与控制预测合同','model_id':'WP09_873_CAD','mode':'CURRENT_SYSTEM_MODEL','source_ids':['current_native','current_mass','current_dm','current_delivery'],'assumptions':['数字惯量须明确为设计估计或实测','固定地面机械臂不能等同自由漂浮在轨系统'],'missing_for_numerical_execution':['各运动link质量/COM/惯量与不确定区间','全机质量/COM/惯量闭合和拓扑','执行器力矩-速度-电压-温度/电流动态及延迟','轮组/推进位置方向、MIB/时延与饱和','接触/柔性适用范围及退化守恒交叉验证'],'readiness':'CURRENT_SYSTEM_HOLD'},
  {'task_id':'Q3_Q4_RL_PREREGISTRATION','question_ids':['Q3','Q4'],'intent':'受物理约束的候选策略学习问题和评价协议','model_id':'SIM13_SYNTHETIC','mode':'THEORY_CONTRACT','source_ids':['sim13_20','sim13_phase_a','sim13_r2_source_only','safe'],'assumptions':['可先定义合成研究，不冒充当前实物数字身体','策略输出与执行权限分离'],'missing_for_numerical_execution':['单一确定性基线与受控环境版本','观察/高层候选动作/奖励/终止与失败定义','训练测试隔离、固定种子/分布、OOD和消融预注册','数值模型适用域与显式训练任务；本轮未获开训授权'],'readiness':'THEORY_CONTRACT_READY'}
 ]
 for t in tasks:
  t.update(documented_research_scope=True,authority='NONE_PLANNING_CONTRACT_ONLY',execution_authorized=False,hardware_validity_established=False,hardware_commands_allowed=False,current_CAD_scientific_PASS_inherited=False)
 findings=[
  '机电整机详细设计未完成；不妨碍只读证据分析和数学/算法合同准备，但尚不足以把当前 CAD 作为经验证的真机数字身体。',
  '9002 是 sim10 原始 Gate 的物理点计数；9000 是规则网格点数，额外含两个锚点。',
  f"sim05 CSV 峰值 {sim05['recorded_peak_deg']} deg 属于旧模型，q2=+60 deg 超过旧 URDF 上限；不得输出为真实关节动作。",
  'R2 31.022864807342987 kg 与 WP09 873 当前未知总质量属于不同构型；不得替换 null 或据此归一化当前 RL 状态/奖励。',
  'Sim13 R2原终裁15/20 与后来20/20负控后端属不同文档范围；20/20不等于生产抓取或学习策略成功。',
  'Phase-A及后续合成模型结果必须使用本身身份；B4G superseded 标记和R2工具源冻结不得当作新完整campaign科学通过。',
  '未知/OOD/provisional 可在清楚声明的纯模型研究中作为研究对象；不能据此肯定当前硬件有效性或动作授权。',
  '机电详细设计与动力学研究有双向依赖：连接/载荷/热/供电定型需要反作用、接触及执行器需求；不应让所有理论与假设模型研究无限期等待整机完成。研究所得设计载荷须声明模型、工况、置信度后交回工程线，不能冒充实测包线。'
 ]
 status={'schema':'WP10_RESEARCH_READINESS_ADVISORY_V1','generated_utc':datetime.now(timezone.utc).isoformat(),'work_modes':['STATE_AUDIT','QUESTION_ROUTING','THEORY_CHAIN_AUDIT','CONTRACT_DRAFT'],'status':'EVIDENCE_AND_THEORY_CONTRACTS_READY__CURRENT_873_DIGITAL_BODY_HOLD','authority_credit':'NONE_ADVISORY_NOT_SCIENTIFIC_GATE','source_manifest':'SOURCE_BINDINGS.json','upstream_binding_audit':'UPSTREAM_HASH_AUDIT.json','all_mechatronic_design_complete':d['current_delivery']['whole_mechatronic_detailed_design_complete'],'current_873_hardware_predictive_model_ready':False,'new_research_execution_authorized':False,'new_training_authorized':False,'hardware_authorized':False,'current_mass_summary':d['current_mass']['summary'],'sim05_readonly_extraction':sim05,'historical_exact_states':{k:{a:v for a,v in d[k].items() if a in ['verdict','technical_verdict','raw_verdict','overall','overall_status','nc_score','maximum_operational_state','next_stage_authorized','release_credit','status','r2_numerical_preflight_executed','full_campaign_executed','scope']} for k in ['sim10','sim11','sim12','e23','e15','r2_release','sim13_20','sim13_phase_a','sim13_r2_source_only','safe','asm00']},'findings':findings,'tasks':tasks,'actions':{'simulation_runs':0,'training_runs':0,'CAD_or_assembly_runs':0,'hardware_actions':0,'external_acquisitions':0,'literature_queue_changes':0,'frozen_source_modifications':0,'validation_scope':'This package only checks source bytes, extracted metadata and planning-contract semantics. No Physics Tool/SAFE implementation.'}}
 write('SOURCE_BINDINGS.json',{'schema':'READ_ONLY_SOURCE_SNAPSHOT_V1','files':sources})
 write('UPSTREAM_HASH_AUDIT.json',{'schema':'SELECTED_HISTORICAL_BINDING_AUDIT_V1','binding_count':len(chains),'matched':sum(x['status']=='MATCH' for x in chains),'nonmatching':sum(x['status']!='MATCH' for x in chains),'scope':'Selected exact raw-byte pins; no whitespace normalization, no historical Gate rewrite, no solver rerun. Hash drift blocks unconditional reproduction claim, not retrospective invalidation of the historical result.','bindings':chains})
 write('MODEL_PARAMETER_CROSSWALK.json',{'schema':'MODEL_COHORT_CROSSWALK_V1','rows':mapping})
 with (OUT/'MODEL_PARAMETER_CROSSWALK.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(mapping[0]));w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v for k,v in x.items()} for x in mapping)
 write('RESEARCH_READINESS.json',status)
 print(json.dumps({'source_count':len(sources),'binding_count':len(chains),'nonmatching_pins':sum(x['status']!='MATCH' for x in chains),'sim05':sim05},ensure_ascii=False))

if __name__=='__main__':main()
