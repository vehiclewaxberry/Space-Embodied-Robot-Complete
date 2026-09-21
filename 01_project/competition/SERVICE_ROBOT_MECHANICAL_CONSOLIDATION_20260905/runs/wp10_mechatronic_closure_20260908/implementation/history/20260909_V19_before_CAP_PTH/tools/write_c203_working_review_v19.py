"""Create a working review page only from current native evidence; preserve V18 release."""
from pathlib import Path
import json,hashlib,datetime,html
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def current(p):
 v=read(p);assert v['passed'] and all(sha(f)==h for f,h in v['inputs'].items()),p
 return v
def main():
 exact=current('results/CAP_HARNESS_EXACT_V19.json');native=current('results/C203_WIRE_PTH_NATIVE_CHECK_V19.json')
 assert set(exact['states'])=={'service','parking','released'}
 for st in exact['states'].values():assert st['passed'] and len(st['nominal_contacts'])==9 and all(q['passed'] for q in st['nominal_contacts'])
 cad=read('results/CAP_HARNESS_CAD_REVIEW_V19.json');assert cad['target_sha256']==sha(cad['target']) and all(sha(f)==h for f,h in cad['records'].items())
 valid=read('results/CAP_HARNESS_VALIDATE_V19.json');assert valid['ok'] and valid['failureCount']==0
 shot=read('results/CAP_HARNESS_SNAPSHOT_V19.json');assert shot['ok'] and shot['target_sha256']==sha(shot['target']) and shot['published_sha256']==sha(shot['published_image'])
 visual=read('results/CAP_HARNESS_VISUAL_REVIEW_V19.json');assert visual['actual_images_viewed'] and all(sha(f)==h for f,h in visual['images'].items())
 sequence=['surface_exact_p02','surface_assembly_p02','surface_review_p01','surface_shot_p01'];serial=[]
 for tag in sequence:
  p='logs/CAP19_SERIAL_'+tag+'.json';v=read(p);assert v['returncode']==0 and v['workspace_mutex_held'] and not v['legacy_native_guards_at_start']
  serial.append(dict(path=p,sha256=sha(p),start=v['started_local'],finish=v['finished_local']))
 for x,y in zip(serial,serial[1:]):assert datetime.datetime.fromisoformat(x['finish'])<=datetime.datetime.fromisoformat(y['start'])
 correction=read('results/C203_NATIVE_SERIAL_CORRECTION_V19.json')
 correction.update(status='ORIGINAL_OVERLAP_DISCLOSED__SERIAL_RERUN_COMPLETED',serial_rerun=serial,serial_rerun_completed=True)
 (A/'results/C203_NATIVE_SERIAL_CORRECTION_V19.json').write_text(json.dumps(correction,indent=2),encoding='utf-8')
 state=read('results/CAP_HARNESS_WORKING_STATUS_V19.json');assert state['source_plan_sha256']==sha(state['source_plan'])
 assert native['remaining_DRC_errors']==6 and not state['V19_published']
 md='''# WP10 V19 当前工作件：C203端接板与线束
\n本轮局部名义几何检查已完成；整机设计仍未完成。最后封装发布保持V18，原873组件／99位号父本及37行责任表保留。
\n| 当前对象 | 实际结果 |
|---|---|
| 原生PCB | WIRE两孔改为PTH；DRC从12降为6，余4项孔距与2项阻焊桥，均属于两处CAP孔群 |
| 分层STEP | PCB及两根导线已重生成，绑定同版本源和实际完成回执 |
| 螺钉与剥线 | 4颗M3×8头下平面X=-5.54；剥线4.2/3.6mm；C203端突出1.59mm |
| 当前集成 | 三态各972行：965行不变、5行修改、新增2线 |
| 精确几何 | 三态各31组邻件检查通过；每态9处名义接触通过 |
| 源检查 | 表面38项／14反例；线束22项／10反例；铜连接20项／5反例 |
| 电热计算 | 384状态、4800行替代热账，10反例通过；真实纹波仍未知 |
\n[打开可视化工作件](WORKING_V19.html) · [局部装配STEP](mechanical/cap_harness_assembly.step) · [PCB STEP](mechanical/input_cap_pcb.step)
\n[正线STEP](mechanical/cap_harness_plus.step) · [回线STEP](mechanical/cap_harness_minus.step) · [972行清单](mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json)
\n[精确检查](results/CAP_HARNESS_EXACT_V19.json) · [原生DRC](results/CAP_TERMINAL_DRC_NATIVE_V19.json) · [当前工作状态](results/CAP_HARNESS_WORKING_STATUS_V19.json)
\n![](review/CAP_HARNESS_ASSEMBLY_V19.png)
\n这是17个源实例的局部装配视图。原生检查跳过全局自交扫描；干涉证据限定本轮5改件和2导线、三种静态状态，未重复资格化其余965行。接触为名义几何，真实密封胶、板平整度、孔桶、焊点及预紧未资格化。
\n仍需完成：两处CAP孔的工艺一致性；线束卡箍／应变释放和焊接工具空间；CHB板局部表面；整机热路径、电池／PMM、推进同修订接口及任务能力。尚不能交付制造或据此宣称整星飞行设计完成。
\n首遍exact与assembly有8.813819秒排程重叠，已保留记录并完成串行重跑。后续本任务只经tools/run_cap19_serial.py入口启动原生作业；该入口保留2GiB启动、512MiB下限、自有子树1400MiB上限，不宣称能阻止所有外部直接启动入口。详见[排程修正记录](results/C203_NATIVE_SERIAL_CORRECTION_V19.json)。
'''
 (A/'WORKING_V19.md').write_text(md,encoding='utf-8')
 page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>WP10 V19 工作件</title><style>body{font:17px/1.7 system-ui;background:#0e1724;color:#e4edf8;max-width:1050px;margin:40px auto;padding:0 24px}h1{font-size:32px}a{color:#81c4ff}img{width:100%;background:#fff;border-radius:12px}.row{display:flex;gap:16px;flex-wrap:wrap}.card{background:#1b2b40;padding:18px;border-radius:12px;flex:1;min-width:210px}.muted{color:#bac8da}</style><h1>C203端接板与线束：V19工作件</h1><p>已完成本轮局部名义几何检查。整机设计仍未完成，最后封装发布保持V18。</p><div class="row"><div class="card"><b>原生DRC：12 → 6</b><br>余4项孔距、2项阻焊桥，集中于CAP两孔。</div><div class="card"><b>三态各972行</b><br>修改PCB与4颗螺钉，新增两根导线。</div><div class="card"><b>每态31组邻件检查</b><br>9处名义接触通过；真实装配未执行。</div></div><p><a href="mechanical/cap_harness_assembly.step">下载局部装配STEP</a> · <a href="mechanical/input_cap_pcb.step">PCB STEP</a> · <a href="mechanical/cap_harness_plus.step">正线</a> · <a href="mechanical/cap_harness_minus.step">回线</a></p><img src="review/CAP_HARNESS_ASSEMBLY_V19.png" alt="实际生成的17源实例局部装配"><p class="muted">实际CAD快照。颜色不代表全部器件真实材料；导线均采用白色绝缘型号。分层板、孔、螺钉与路线为名义模型。</p><p>下一步：CAP孔工艺一致性、线束固定和焊接工具空间、CHB板局部表面，以及整星热／能源／推进闭环。</p><p><a href="WORKING_V19.md">工作件说明</a> · <a href="results/CAP_HARNESS_EXACT_V19.json">精确几何证据</a> · <a href="results/CAP_TERMINAL_DRC_NATIVE_V19.json">原生DRC</a> · <a href="results/CAP_HARNESS_WORKING_STATUS_V19.json">机器状态</a></p></html>'''
 (A/'WORKING_V19.html').write_text(page,encoding='utf-8')
 inputs=['WORKING_V19.md','WORKING_V19.html','mechanical/cap_harness_assembly.step','mechanical/cap_harness_assembly.step.py','mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json','results/CAP_HARNESS_EXACT_V19.json','results/CAP_HARNESS_CAD_REVIEW_V19.json','results/CAP_HARNESS_SNAPSHOT_V19.json','results/CAP_HARNESS_VISUAL_REVIEW_V19.json','results/C203_NATIVE_SERIAL_CORRECTION_V19.json','results/C203_WIRE_PTH_NATIVE_CHECK_V19.json','tools/write_c203_working_review_v19.py']
 record=dict(status='CURRENT_WORKING_REVIEW_ONLY__NOT_V19_RELEASE',inputs={p:sha(p) for p in inputs},whole_design_complete=False,manufacturing_release=False,serial_rerun_completed=True)
 (A/'results/C203_WORKING_REVIEW_PACKAGE_V19.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
 print('WORKING_V19.md / WORKING_V19.html written; V18 published files preserved')
if __name__=='__main__':main()
