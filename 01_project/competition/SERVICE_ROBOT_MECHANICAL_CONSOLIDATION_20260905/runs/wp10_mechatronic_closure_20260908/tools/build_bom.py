"""Roll the actual WP10 component identities into the one hierarchy BOM."""
from pathlib import Path
import csv,json,hashlib,collections,xml.etree.ElementTree as ET
D=Path(__file__).resolve().parents[1];C=D.parent/'wp09_interfaces_20260907_1525/system_completion'
E=D/'ecad';S=D/'electrical'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(r):return hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
pfile=C/'ecad/MASTER_BOM.csv';sfile=S/'STOP_BOM.csv';xfile=E/'exports/wp09_system.xml'
parent=rows(pfile);child=rows(sfile);byref={r['reference']:r for r in child};assert len(byref)==len(child)
xml=ET.parse(xfile).getroot();comps=xml.findall('./components/comp')
top=[x for x in comps if x.find('sheetpath').get('names')=='/'];sub=[x for x in comps if x not in top]
assert {x.get('ref') for x in sub}==set(byref)
columns=list(parent[0]);out=[]
for old in parent:
    if old['parent_bom_id']=='SYS/STOPBOARD':continue
    r=dict(old)
    if r['schematic_reference']:
        matches=[x for x in top if x.findtext('value')==r['logical_reference']]
        assert len(matches)==1,r['logical_reference']
        r['schematic_reference']=matches[0].get('ref')
        r['sheet_path']='/'
    if r['logical_reference']=='STOPBOARD':
        r.update(source_pn='WP10 auxiliary-supply stop circuit candidate',
         source_claim=f'{len(child)} actual child symbols; tested static auxiliary supply/driver revision, PCB and dynamic supply qualification remain open',
         source_record_file=str(sfile),source_file_sha256=sha(sfile),source_row_sha256='',
         notes='Current GSE static candidate; no second purchase or double-counted mass. J101.1/.2 are test outputs, external supply forbidden.')
    else:
        r['notes']+=' | Inherited WP09 normalized BOM row SHA '+canon(old)
    out.append(r)
for e in sub:
    p=byref[e.get('ref')];r={k:'' for k in columns};boundary=p['reference'].startswith('J')
    r.update(bom_id='SYS/STOPBOARD/'+p['reference'],parent_bom_id='SYS/STOPBOARD',hierarchy_level='2',
      schematic_reference=p['reference'],sheet_path=e.find('sheetpath').get('names'),logical_reference=p['reference'],
      item_kind='LOGICAL_CONNECTOR_BOUNDARY' if boundary else 'SELECTED_CIRCUIT_COMPONENT',
      source_pn=p['mpn'],manufacturer_part_number='' if boundary else p['mpn'],value=p['value'],design_quantity=p['quantity'],
      standalone_purchase_quantity='0' if boundary else '',procurement_rule='BOUNDARY_NOT_PHYSICAL_MATE' if boundary else 'DESIGN_CANDIDATE_NOT_PURCHASE_RELEASED',
      role='STOPBOARD_PORT' if boundary else 'STOPBOARD_COMPONENT',source_claim=p['source'],source_record_file=str(sfile),
      source_file_sha256=sha(sfile),source_row_sha256=canon(p),source_selection_scope=p['scope'],
      source_footprint=p['footprint'],unverified_package_reference=p['package_reference_unverified'],
      actual_received='UNCONFIRMED',fabrication_release='False',hardware_verified='False',mass_kg='',
      mass_accounting='LOGICAL_BOUNDARY_NO_PHYSICAL_MASS' if boundary else 'UNKNOWN_NOT_INCLUDED_IN_TOTAL',
      notes='Current actual WP10 source. Board dynamics, PCB thermal realization and hardware tests remain open.')
    if p['reference']=='J101':r['notes']+=' Pins1/2 are internal 3.3V/5V TEST outputs; do not connect external supply.'
    out.append(r)
checks=[]
def check(n,v):checks.append({'name':n,'pass':bool(v)});assert v,n
check('actual_reference_bijection',collections.Counter(r['schematic_reference'] for r in out if r['schematic_reference'])==collections.Counter(e.get('ref') for e in comps))
check('unique_BOM_identity',len(out)==len({r['bom_id'] for r in out}))
check('parent_nonchild_responsibilities_preserved',len(out)-len(child)==len(parent)-71)
check('parent_rollup_not_extra_purchase',next(r for r in out if r['logical_reference']=='STOPBOARD')['standalone_purchase_quantity']=='0')
for r in out:
    check('no_false_release_'+r['bom_id'],r['fabrication_release']=='False' and r['hardware_verified']=='False' and r['mass_kg']=='')
    if r['parent_bom_id']=='SYS/STOPBOARD':
        p=byref[r['logical_reference']]
        check('quantity_source_'+r['bom_id'],r['design_quantity']==p['quantity'] and r['source_row_sha256']==canon(p))
        check('source_file_'+r['bom_id'],r['source_file_sha256']==sha(sfile))
        check('mpn_or_logical_port_'+r['bom_id'],r['manufacturer_part_number']==('' if p['reference'].startswith('J') else p['mpn']))
with (E/'MASTER_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(out)
note=f"""# WP10 分层电气 BOM
本表从实际新网表和停止电路BOM生成。{len(comps)}个实际原理图ref唯一映射，其中{len(top)}个顶层设备/边界，{len(child)}个停止电路子项；另保留父版未进网表的8个参考责任项。共{len(out)}行。
STOPBOARD是装配父项，不重复采购或累加子件质量。5个J符号是逻辑边界，未选定实体连接器，不能据引脚编号直接制线。J101.1/.2现为内部电源TEST端，禁止外供；输入仍为J101.3上游保护24V与J101.4回流。
B601套装与分线板/USB-CAN、ODrive及随附电阻的采购去重规则沿父表保留。候选料号不表示收到、下单授权或制造放行；所有未知质量保持空。
新的辅助供源、预负载和TC4420驱动器属于有界GSE静态设计。典型纹波、启动/瞬态、PCB散热和实际母线诊断未闭合，不据BOM完整性签发整机电气完成。
来源母表：{pfile}
当前子页：{sfile}
"""
(E/'MASTER_BOM_NOTES.md').write_text(note,encoding='utf-8')
r={'status':'PASS_ACTUAL_WP10_BOM_IDENTITY__SYSTEM_DESIGN_OPEN','rows':len(out),'actual_schematic_refs':len(comps),'stop_symbols':len(child),
 'selected_component_rows':sum(r['item_kind']=='SELECTED_CIRCUIT_COMPONENT' for r in out),'boundary_symbols':5,'checks_passed':len(checks),
 'sources':[{'path':str(p),'sha256':sha(p)} for p in [pfile,sfile,xfile]],'outputs':[{'path':str(E/n),'sha256':sha(E/n)} for n in ['MASTER_BOM.csv','MASTER_BOM_NOTES.md']],
 'checks':checks,'physical_io':0,'manufacturing_release':False,'whole_system_design_complete':False}
(D/'results/STOP_BOM_INTEGRATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ['checks','sources','outputs']}))

