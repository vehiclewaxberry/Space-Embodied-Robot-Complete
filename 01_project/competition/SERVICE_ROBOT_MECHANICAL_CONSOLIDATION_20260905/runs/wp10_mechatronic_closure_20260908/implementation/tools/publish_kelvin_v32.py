"""Activate the actual V32 ECAD revision within the existing WP10 candidate."""
from pathlib import Path
from datetime import datetime
import csv,hashlib,json,xml.etree.ElementTree as ET
from verify_kelvin_v32 import A,E,D,R,sha,read,dump

def main():
    v=read(R/'VALIDATION.json'); assert v['passed']
    for p,h in read(R/'PARENT_SOURCE_LOCK.json').items(): assert sha(p)==h
    C=A/'coupled_closure'; parent=C/'CANDIDATE_V30.json'
    root=ET.parse(D/'wp10_system.xml').getroot()
    components=root.findall('./components/comp')
    with (D/'SYSTEM_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['ref','value','footprint','sheet','source_revision']);w.writeheader()
        for c in components:w.writerow(dict(ref=c.get('ref'),value=c.findtext('value'),footprint=c.findtext('footprint'),
                                            sheet=c.find('sheetpath').get('names'),source_revision='V32'))
    with (D/'PIN_NET_TABLE.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['net','ref','pin','pinfunction','pintype']);w.writeheader()
        for n in root.findall('./nets/net'):
            for p in n.findall('node'):w.writerow(dict(net=n.get('name'),ref=p.get('ref'),pin=p.get('pin'),pinfunction=p.get('pinfunction'),pintype=p.get('pintype')))
    copper=read(A/'power/MAIN_INPUT_COPPER_LOSS_V29.json')
    copper.update(schema='WP10_V32_CONDITIONAL_COPPER_LOSS',PCB_sha256=sha(D/'wp10_main_input.kicad_pcb'),
        parent_model='power/MAIN_INPUT_COPPER_LOSS_V29.json',parent_model_sha256=sha(A/'power/MAIN_INPUT_COPPER_LOSS_V29.json'),
        inheritance_basis='Full PCB AST differs only by internal terminal connection attributes and resolved model paths; no copper geometry change.',
        qualified=False,validation='results/kelvin_v32/VALIDATION.json')
    dump(A/'power/MAIN_INPUT_COPPER_LOSS_V32.json',copper)
    delta=dict(original_matrix='SYSTEM_CLOSURE_MATRIX.csv',original_matrix_sha256=sha(A/'SYSTEM_CLOSURE_MATRIX.csv'),
        original_rows=37,original_statuses_modified=False,
        closed_subitem='R201/R202 two split lands per terminal are represented by native component-internal connections',
        related_original_ids=['B03','E01','E06','H03'],whole_row_closure_credit=False,
        evidence=['results/kelvin_v32/VALIDATION.json','results/kelvin_v32/COUNTEREXAMPLES.json'],
        remaining='Power input interface, transient/SOA/mission energy, other PCB design, thermal/installation and whole-host integration remain open.')
    dump(R/'CLOSURE_DELTA.json',delta)
    dump(R/'READONLY_REVIEW.json',dict(reviewer='/root/v31_electrical',review_date='2026-09-11',
        result='PASS_SCOPED_KELVIN_EDA_CONNECTION_REPRESENTATION',
        finding='SWIG model list mutation did not persist; five board and two library model references were initially broken.',
        resolution='Explicit vector index assignment followed by native save/reload and resolved-path hashes; independent AST review confirmed.',
        negative_cases={'removed_R201_attribute_unconnected':2,'removed_VIN_trace_unconnected':1,'removed_VIN_trace_warning':'track_dangling'},
        full_system_PCB_parity=False,hardware_credit=False))
    dump(R/'VISUAL_REVIEW.json',dict(source='MAIN_INPUT_TOP.pdf',image='MAIN_INPUT_TOP.png',
        reviewed_by='root',review_date='2026-09-11',
        finding='Native top copper view inspected: split Kelvin lands remain separate, power lands and terminal grids retained.',
        physical_assembly_or_thermal_credit=False))
    active_files=[p for p in D.rglob('*') if p.is_file() and not p.name.startswith('negative_') and p.suffix not in ['.kicad_prl']]
    candidate=dict(schema='WP10_ACTIVE_DESIGN_DELTA_V32',revision='V32',same_WP10_candidate=True,
        parent_candidate=str(parent),parent_sha256=sha(parent),
        active_sources={'system_schematic':str(D/'wp10_system.kicad_sch'),'system_netlist':str(D/'wp10_system.xml'),
                        'main_input_PCB':str(D/'wp10_main_input.kicad_pcb'),'BOM':str(D/'SYSTEM_BOM.csv'),
                        'pin_net_table':str(D/'PIN_NET_TABLE.csv'),'copper_loss_model':str(A/'power/MAIN_INPUT_COPPER_LOSS_V32.json')},
        source_lock={str(p):sha(p) for p in active_files},
        geometry_parent='V30',native_whole_host_leaf_instances=873,source_instance_plan_count=974,
        new_native_whole_host_integration=False,source_input_baseline='baseline_load_closure_v31/DELIVERY_STATUS_V31.json',
        electrical_refs=len(components),pin_records=v['active_pin_record_count'],
        scoped_acceptance={'system_ERC_errors':0,'system_ERC_warnings':0,'main_input_DRC_violations':0,'main_input_DRC_unconnected':0,
                           'same_ignored_rules_as_parent':True,'native_counterexamples_passed':True},
        full_system_PCB_parity_checked=False,whole_design_complete=False,manufacturing_release=False,hardware_tests=0,
        inherited_nonclosures=['Protected battery interface and replenishment','Actual B601 load and mass/inertia','Stopping energy and heater path',
                              'Complete thermal path and installation','Controlled propulsion ICD and task capability','Whole-spacecraft native integration'])
    candidate['source_lock'][str(A/'power/MAIN_INPUT_COPPER_LOSS_V32.json')]=sha(A/'power/MAIN_INPUT_COPPER_LOSS_V32.json')
    dump(C/'CANDIDATE_V32.json',candidate)
    status=dict(revision='V32',status='KELVIN_EDA_CONNECTION_SUBITEM_CLOSED__WHOLE_DESIGN_OPEN',
        date=datetime.now().astimezone().isoformat(),candidate='coupled_closure/CANDIDATE_V32.json',
        native_CAD_revision='V30 inherited / 873 host unchanged',electrical_refs=211,pin_records=677,
        scoped_checks=v['checks_run'],whole_design_complete=False,hardware_tests=0,original_37_rows_preserved=True)
    dump(C/'DELIVERY_STATUS_V32.json',status)
    md='''# WP10 V32 电气连接修复

本修订已修改实际原理图库、系统页缓存、PCB与封装库，关闭R201/R202的4项Kelvin连接表达问题。它们是各物理金属端子内部连接的分裂焊盘，不是应在PCB上短接的取样槽。没有把电阻两端短路，也没有新增DRC排除。

当前13页系统原理图ERC为0错误/0警告；主输入板在继承规则下DRC为0规则违规/0未连接。当前211个位号、677条针脚记录逐项保持；207/673是加入四个端子前的历史计数。完整系统PCB parity尚未执行，局部板检查不代表所有板均完成。

两项原生反例已执行：撤销R201内部连接属性得到2项未连接；保留属性并删除VIN取样线得到1项未连接和1项悬空走线警告。真实断线仍会被检出。

独立审阅发现模型相对路径未真正回存；现已修复板上5处与库内2处引用，并经原生保存/重载及哈希核对。铜、孔、封装摆放及网络没有变化，原有铜损条件模型重新绑定当前PCB。零规则违规不代表大电流温升、SOA、装配或制造已经验证。

活动ECAD：[系统原理图](../ecad/revisions/v32/wp10_system.kicad_sch) · [主输入板](../ecad/revisions/v32/wp10_main_input.kicad_pcb) · [系统BOM](../ecad/revisions/v32/SYSTEM_BOM.csv) · [针脚网表](../ecad/revisions/v32/PIN_NET_TABLE.csv)。

证据：[18项源与结构检查](../results/kelvin_v32/VALIDATION.json) · [原生反例](../results/kelvin_v32/COUNTEREXAMPLES.json) · [PCB图](../results/kelvin_v32/MAIN_INPUT_TOP.pdf)。

原873装配、99位号父本、V30/V31来源及37行闭环表均保留。当前CAD沿用父版；完整能源、停止回生、散热/安装、推进和原生整机集成仍开放。

依据：[Vishay 30179第2页](https://www.vishay.com/docs/30179/wslp2726.pdf)及[KiCad 10内部连接焊盘机制](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#jumper-pads)。图纸为设计候选，不是制造或上电放行。
'''
    (C/'README_V32.md').write_text(md,encoding='utf-8')
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>WP10 V32 电气修复</title><style>body{font:17px/1.8 system-ui,sans-serif;background:#f0f4f6;color:#203745;margin:0}main{max-width:1000px;margin:auto;padding:36px}section{padding:22px;background:white;border-radius:12px;margin:18px 0}h1{font-size:30px}a{color:#056b8b}img{width:100%}.hold{border-left:5px solid #c88c1a;background:#fff4db;padding:15px}</style><main><h1>WP10 V32：修复主输入板 Kelvin 连接表达</h1><p class="hold">整机仍未完成。此页仅确认本次实际ECAD修订及其验证，不赋予上电、制造或飞行信用。</p><section><strong>4 → 0 项未连接</strong><p>原理图库、13页系统缓存、封装库与PCB同源；211位号 / 677针脚记录保持。ERC 0错误0警告，主输入板在原规则设置下DRC 0违规0未连接。</p><p>原生反例仍能检出撤销内部连接模型和删除真实取样线。没有桥接Kelvin沟槽，没有扩大排除规则。</p></section><section><img src="../results/kelvin_v32/MAIN_INPUT_TOP.png" alt="实际KiCad主输入板顶层铜图"><p>铜、孔位和器件位置保持；五个板模型与两个库模型引用已修复并重载核对。</p></section><section><a href="README_V32.md">修订说明</a> · <a href="../ecad/revisions/v32/wp10_system.kicad_sch">系统原理图</a> · <a href="../ecad/revisions/v32/wp10_main_input.kicad_pcb">主输入PCB</a> · <a href="../ecad/revisions/v32/SYSTEM_BOM.csv">BOM</a> · <a href="../results/kelvin_v32/VALIDATION.json">验证回执</a> · <a href="../results/kelvin_v32/COUNTEREXAMPLES.json">反例</a></section></main></html>'''
    (C/'REVIEW_V32.html').write_text(html,encoding='utf-8')
    pointer=A/'CURRENT_WORKING_CANDIDATE.json'; previous=read(pointer)
    history=A/'history/20260913_V32_activation';history.mkdir(exist_ok=True)
    if not (history/pointer.name).exists():(history/pointer.name).write_bytes(pointer.read_bytes())
    previous.update(revision='V32',entry='coupled_closure/REVIEW_V32.html',candidate='coupled_closure/CANDIDATE_V32.json',
                    geometry_revision='V30',source_activation='coupled_closure/SOURCE_ACTIVATION_V32.json',whole_design_complete=False)
    dump(C/'SOURCE_ACTIVATION_V32.json',dict(revision='V32',candidate_sha256=sha(C/'CANDIDATE_V32.json'),
        sources_activated=candidate['active_sources'],parent_unchanged=True,original_matrix_unchanged=True,
        new_native_CAD_integration=False,whole_design_complete=False))
    dump(pointer,previous)
    nav=A.parents[2]/'CURRENT_candidate.md';old=nav.read_text(encoding='utf-8-sig')
    marker='## WP10 V32 Kelvin电气连接修复（2026-09-13）'
    if marker not in old:
        (history/nav.name).write_bytes(nav.read_bytes())
        nav.write_text(marker+'\n\n[当前修订与实际源](runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/REVIEW_V32.html)：实际ECAD同版关闭4项Kelvin连接表达问题；13页ERC 0错0警，主输入板DRC 0违规0未连接，反例仍能检出真实断线。当前211位号/677针脚。几何沿用V30、原生873宿主未回装；完整机电设计仍开放。下方均为历史记录。\n\n---\n\n'+old,encoding='utf-8')
    print(json.dumps({'revision':'V32','active_ecad':str(D),'closed':'Four Kelvin EDA connection-expression issues','whole_design_complete':False}))

if __name__=='__main__':main()
