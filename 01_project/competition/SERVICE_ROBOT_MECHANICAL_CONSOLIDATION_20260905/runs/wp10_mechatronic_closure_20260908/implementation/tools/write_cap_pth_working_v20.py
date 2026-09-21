"""Bind actual V20 source/STEP/native checks and present this local working result."""
from pathlib import Path
import json,datetime,csv,html,math
from c203_surface_generation_contract_v19 import A,read,sha,validate_receipt,SPECS
from prepare_cap_harness_plan_v19 import validate_plan,PLAN
def proof(path):
 v=read(path);assert v['passed'] is True,path
 assert all(sha(p)==h for p,h in v['inputs'].items()),'Stale proof: '+path
 return v
def main():
 paths=['results/CAP_PTH_SOURCE_CHECK_V20.json','results/C203_CAM_CHECK_V20.json','results/SYSTEM_ERC_CHECK_V20.json','results/C203_SURFACE_PROFILE_CHECK_V19.json','results/CAP_HARNESS_PATH_V19.json','results/CAP_TERMINAL_COPPER_AUDIT.json','results/CAP_HARNESS_EXACT_V19.json','power/CAP_HARNESS_ELECTROTHERMAL_V19.json']
 evidence={p:proof(p) for p in paths}
 assert not (A/'ecad/wp10_c203_terminal.kicad_dru').exists()
 plan=read(PLAN);validate_plan(plan);fresh={k:validate_receipt(k) for k in SPECS}
 exact=evidence['results/CAP_HARNESS_EXACT_V19.json']
 assert set(exact['states'])=={'service','parking','released'}
 assert all(s['passed'] and len(s['nominal_contacts'])==9 for s in exact['states'].values())
 old_exact_path='history/20260909_V19_before_CAP_PTH/results/CAP_HARNESS_EXACT_V19.json';old_exact=read(old_exact_path)
 removed={k:old_exact['states'][k]['pcb_geometry']['volume_mm3']-s['pcb_geometry']['volume_mm3'] for k,s in exact['states'].items()}
 expected_removed=2*math.pi*(1.75**2-1**2)*.01
 assert all(abs(v-expected_removed)<1e-6 for v in removed.values()),'STEP delta differs from two enlarged front-mask apertures'
 cad=read('results/CAP_HARNESS_CAD_REVIEW_V19.json');assert sha(cad['target'])==cad['target_sha256'] and all(sha(p)==h for p,h in cad['records'].items())
 valid=read('results/CAP_HARNESS_VALIDATE_V19.json');assert valid['ok'] and valid['failureCount']==0
 shot=read('results/CAP_HARNESS_SNAPSHOT_V19.json');assert shot['ok'] and sha(shot['target'])==shot['target_sha256'] and sha(shot['published_image'])==shot['published_sha256']
 visual=read('results/CAP_HARNESS_VISUAL_REVIEW_V19.json');assert visual['actual_images_viewed'] and visual['target_sha256']==sha(visual['target']) and all(sha(p)==h for p,h in visual['images'].items())
 heat=evidence['power/CAP_HARNESS_ELECTROTHERMAL_V19.json'];active=read('thermal/ACTIVE_HEAT_LOADS_V19.json')
 assert heat['state_count']==384 and heat['heat_rows']==4800 and sha(heat['output_csv'])==heat['output_sha256']
 assert active['source_assembly_sha256']==sha(PLAN) and active['calculation_sha256']==sha(active['calculation']) and active['heat_dataset_sha256']==sha(active['heat_dataset']) and not active['add_to_parent']
 released=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']
 for p in released:assert (A/p).read_bytes()==(A/'history/20260909_V18_before_cap_harness'/p).read_bytes(),'Published V18 unexpectedly changed: '+p
 rows=list(csv.DictReader((A/'SYSTEM_CLOSURE_MATRIX.csv').open(encoding='utf-8-sig')));assert len(rows)==37
 tags=['cap20_normalize_extract_p01','cap20_drc_p01','cap20_cam_active_p01','cap20_erc_p01','cap20_copper_p02','cap20_pcb_gen_p04','cap20_plus_gen_p03','cap20_minus_gen_p02','cap20_exact_p02','cap20_assembly_p01','cap20_review_p01','cap20_shot_p01']
 serial=[]
 for tag in tags:
  path=f'logs/CAP19_SERIAL_{tag}.json';v=read(path)
  assert v['returncode']==0 and v['workspace_mutex_held'] and not v['legacy_native_guards_at_start']
  serial.append(dict(path=path,sha256=sha(path),start=v['started_local'],finish=v['finished_local']))
 for x,y in zip(serial,serial[1:]):assert datetime.datetime.fromisoformat(x['finish'])<=datetime.datetime.fromisoformat(y['start'])
 review=read('results/CAP_PTH_READONLY_REVIEW_V20.json');assert review['passed'] and all(sha(p)==h for p,h in review['reviewed_files'].items())
 paths += [PLAN,old_exact_path,'results/CAP_HARNESS_CAD_REVIEW_V19.json','results/CAP_HARNESS_VALIDATE_V19.json','results/CAP_HARNESS_SNAPSHOT_V19.json','results/CAP_HARNESS_VISUAL_REVIEW_V19.json','results/CAP_PTH_READONLY_REVIEW_V20.json','thermal/ACTIVE_HEAT_LOADS_V19.json','mechanical/cap_harness_assembly.step','mechanical/cap_harness_assembly.step.py','tools/write_cap_pth_working_v20.py',*released]
 state=dict(status='V20_C203_NATIVE_DRC_CLEARED__CAM_AND_NOMINAL_LOCAL_ASSEMBLY_VERIFIED__WHOLE_DESIGN_OPEN',timestamp=datetime.datetime.now().astimezone().isoformat(),goal_turn_classification='progress',system_ERC_errors=0,system_ERC_warnings=0,C203_DRC_violations=0,C203_unconnected_items=0,source_plan=PLAN,source_plan_sha256=sha(PLAN),instances_by_state={k:len(v['rows']) for k,v in plan['states'].items()},unchanged_parent_instances=965,changed_parent_instances=5,added_wire_instances=2,STEP_current=True,STEP_hashes={k:r['output_sha256'] for k,r in fresh.items()},native_serial_sequence=serial,exact_pairs_by_state={k:len(s['exact_pairs']) for k,s in exact['states'].items()},nominal_contacts_per_state=9,original_873_parent_and_99_refs_preserved=True,original_37_statuses_preserved=True,last_sealed_revision='V18',V20_whole_release=False,whole_design_complete=False,manufacturing_release=False,physical_tests_executed=False,open_items=['PTH plating/finished-hole tolerance and solder/flux process qualification','Capacitor harness retention and solder-tool access','CHB input board local surface and contact model','Main-path fault protection, STOP and regen dynamic behavior','Full thermal path/losses, battery and PMM installation/interfaces','Same-revision propulsion ICD and task capability','Whole-assembly tolerance, continuous motion and structural validation'],inputs={p:sha(p) for p in paths})
 state['actual_STEP_mask_volume_removed_mm3_by_state']=removed
 state['expected_two_aperture_volume_removed_mm3']=expected_removed
 (A/'results/CAP_PTH_WORKING_STATUS_V20.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
 md='''# WP10 V20 当前工作件

本轮完成 C203 电容端接板的原生改件、CAM 对照和局部数字装配。整机机电详细设计仍有开放项；最后封装发布保持 V18。

| 对象 | 当前实际结果 |
|---|---|
| 整机原理图 ERC | 12 页重新执行：0 错误、0 警告，原忽略规则保持 |
| C203 原生 PCB DRC | 从 V19 的 6 项降为 0 项；0 未连接，规则未放宽 |
| 四处电气端接 | CAP 两孔 Ø2 PTH、WIRE 两孔 Ø1.8 PTH；另有四个 Ø3.4 安装 NPTH |
| CAP 板面 | 保留背面 Ø3.5 铜环；前面无铜环、Ø3.5 阻焊开窗；孔周裸基材面 X=-6.99 mm，其余座面 X=-7 mm |
| 三态装配清单 | 各 972 行：965 父行保持、PCB 与四颗螺钉按现行表面定位、两根导线 |
| 精确局部检查 | 每态 31 组邻件、9 处名义接触通过；非整星全局／连续动作检查 |
| 电热分账 | 384 状态、4800 行；线长及电阻保持，实际纹波与温升仍待确定 |

[查看页面](WORKING_V20.html) · [局部装配 STEP](mechanical/cap_harness_assembly.step) · [PCB STEP](mechanical/input_cap_pcb.step) · [装配清单](mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json)

[当前机器证据](results/CAP_PTH_WORKING_STATUS_V20.json) · [ERC](results/SYSTEM_ERC_NATIVE_V20.json) · [DRC](results/CAP_TERMINAL_DRC_NATIVE_V20.json) · [CAM 核验](results/C203_CAM_CHECK_V20.json)

![当前原生装配快照](review/CAP_HARNESS_ASSEMBLY_V19.png)

部分活动文件沿用 V19 文件名；当前版本以 V20 状态文件内 SHA256 为准。历史 V19 文件已归档。STEP 可作为 SolidWorks 的导入几何，本轮未生成新的 SLDASM／SLDPRT。

独立审阅发现并修复了 CAM 校验器的终止标记、清单、文件角色和检查回执绑定问题；16 个 CAM、13 个源／绑定反例拒绝通过。首次 PCB 生成因模块导入失败，已修复并实际重生成，未计成功信用。全部最终原生作业串行完成。

尚需完成：焊接和孔桶工艺、线束应变释放与工具空间、CHB 局部板面、主回路故障保护与停止／回生动态、整星热路径、电池／PMM、推进同修订接口及任务能力、整机公差和连续动作验证。0 ERC／DRC 只说明已启用规则下本轮检查通过；不能据此宣布整机完成或制造放行。
'''
 (A/'WORKING_V20.md').write_text(md,encoding='utf-8')
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP10 V20 当前机电工作件</title><style>body{font:17px/1.7 system-ui,"Microsoft YaHei";background:#0e1724;color:#e4edf8;max-width:1080px;margin:40px auto;padding:0 24px}h1{font-size:32px}a{color:#81c4ff}.row{display:flex;gap:16px;flex-wrap:wrap}.card{background:#1b2b40;padding:18px;border-radius:12px;flex:1;min-width:200px}.n{font-size:36px;font-weight:700;color:#9cddbf}img{width:100%;background:white;border-radius:12px}.muted{color:#bac8da}li{margin:8px 0}</style><h1>C203 端接板与线束 · V20</h1><p>电容端接板源文件已修改并完成当前版本的局部数字装配核验。整机机电设计仍有开放项。</p><div class="row"><div class="card"><div class="n">0 / 0</div>整机原理图 ERC 错误／警告<br>12 页实际重查</div><div class="card"><div class="n">6 → 0</div>C203 PCB DRC 违规<br>0 未连接；规则保持</div><div class="card"><div class="n">972</div>三态各 972 行<br>每态 31 组邻件、9 处名义接触</div></div><p><a href="mechanical/cap_harness_assembly.step">下载局部装配 STEP</a> · <a href="mechanical/input_cap_pcb.step">PCB STEP</a> · <a href="mechanical/cap_harness_plus.step">正线 STEP</a> · <a href="mechanical/cap_harness_minus.step">回线 STEP</a></p><img src="review/CAP_HARNESS_ASSEMBLY_V19.png" alt="当前生成的电容端接板及导线局部装配"><p class="muted">当前 CAD 快照，17 个源实例。两根导线均为白色绝缘型号；单视角存在遮挡。孔桶、焊点、公差、预紧和实物接触未资格化。</p><p>CAP 两孔改为 Ø2 PTH，保留背铜环，前面 Ø3.5 阻焊开窗已同步到分层 STEP。四颗板螺钉保持现行座面定位；WIRE 孔、六段走线、网络和规则保持。</p><p><a href="WORKING_V20.md">完整工作说明</a> · <a href="results/CAP_PTH_WORKING_STATUS_V20.json">当前状态与源哈希</a> · <a href="results/SYSTEM_ERC_NATIVE_V20.json">ERC 报告</a> · <a href="results/CAP_TERMINAL_DRC_NATIVE_V20.json">DRC 报告</a> · <a href="results/C203_CAM_CHECK_V20.json">CAM 核验</a></p><p>后续工作：线束固定和工具空间、CHB 局部板面、停止／回生及故障动态、整星散热、电池／PMM与推进接口。最后封装发布仍为 V18；本工作件不表示整机完成或制造放行。</p></html>'''
 (A/'WORKING_V20.html').write_text(page,encoding='utf-8')
 # Old working-page links would otherwise point at changed active STEP files.
 (A/'WORKING_V19.md').write_text('V19 工作件已由 [V20 当前工作件](WORKING_V20.html) 替代。原 V19 说明见 [归档](history/20260909_V19_before_CAP_PTH/WORKING_V19.md)。\n',encoding='utf-8')
 (A/'WORKING_V19.html').write_text('<!doctype html><meta charset="utf-8"><title>V19 已替代</title><p>V19 工作件已由 <a href="WORKING_V20.html">V20 当前工作件</a> 替代。</p>',encoding='utf-8')
 print('V20 source-bound working review created; V18 sealed release and original37 statuses unchanged')
if __name__=='__main__':main()
