"""Build a hierarchy-aware BOM from actual exported ECAD identities; no purchasing."""
from pathlib import Path
import csv, hashlib, json, xml.etree.ElementTree as ET
from collections import Counter

C = Path(__file__).resolve().parents[1]
N = C.parent / 'reuse_closure'
FILES = {
    'actual_system_netlist': C/'ecad/exports/wp09_system.xml',
    'stop_source_bom': C/'electrical_delta/STOP_BOM.csv',
    'parent_source_bom': N/'ecad/MASTER_BOM.csv',
    'actual_endpoint_map': C/'ecad/SYSTEM_ENDPOINT_MAP.json',
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
source_hashes = {k: sha(v) for k, v in FILES.items()}
parents = rows(FILES['parent_source_bom'])
stop = rows(FILES['stop_source_bom'])
parent_by_ref = {r['ref']: r for r in parents}
stop_by_ref = {r['reference']: r for r in stop}
assert len(parents) == len(parent_by_ref) == 24
assert len(stop) == len(stop_by_ref) == 71
components = ET.parse(FILES['actual_system_netlist']).getroot().findall('./components/comp')
top = [e for e in components if e.find('sheetpath').get('names') == '/']
child = [e for e in components if e.find('sheetpath').get('names') != '/']
assert len(components) == 94 and len(top) == 23 and len(child) == 71
assert {e.get('ref') for e in child} == set(stop_by_ref)
columns = ['bom_id','parent_bom_id','hierarchy_level','schematic_reference','sheet_path',
           'logical_reference','item_kind','source_pn','manufacturer_part_number',
           'value','design_quantity','standalone_purchase_quantity','procurement_rule',
           'bundle_group','role','source_claim','source_record_file','source_file_sha256',
           'source_row_sha256','source_selection_scope','source_footprint',
           'unverified_package_reference','actual_received','fabrication_release',
           'hardware_verified','mass_kg','mass_accounting','notes']
out = []
def base():
    d = {k: '' for k in columns}
    d.update(actual_received='UNCONFIRMED', fabrication_release='False',
             hardware_verified='False', mass_accounting='UNKNOWN_NOT_INCLUDED_IN_TOTAL')
    return d
def inherit_parent(d, p):
    d.update(source_pn=p['pn'], design_quantity=p['quantity'], role=p['role'],
             source_claim=p['source'], source_record_file='../reuse_closure/ecad/MASTER_BOM.csv',
             source_file_sha256=source_hashes['parent_source_bom'], source_row_sha256=canonical_sha(p),
             source_selection_scope='INHERITED_PARENT_CANDIDATE_TEXT_NOT_NEW_MPN_VERIFICATION',
             procurement_rule='CANDIDATE_REQUIREMENT_ONLY_RELEASE_AND_RECEIPT_UNCONFIRMED')
    if p['ref'] in ('DM','CAN','SEP'):
        d['bundle_group'] = 'B601_DM_DELIVERY_SET'
        d['procurement_rule'] = ('MAIN_KIT_REQUIREMENT_CONFIRM_CONTENTS_BEFORE_ORDER' if p['ref']=='DM'
            else 'MAY_BE_INCLUDED_IN_B601_KIT_VERIFY_DELIVERY_NO_AUTOMATIC_EXTRA_ORDER')
    if p['ref'] in ('U1','RB1'):
        d['bundle_group'] = 'ODRIVE_REGEN_CLAMP_DELIVERY_SET'
        d['procurement_rule'] = ('MODULE_REQUIREMENT_CONFIRM_SUPPLIED_RESISTOR' if p['ref']=='U1'
            else 'PARENT_DESCRIBES_SUPPLIED_RESISTOR_NO_AUTOMATIC_EXTRA_ORDER')

used_parent = set()
for e in top:
    logical = e.findtext('value'); d = base()
    d.update(bom_id='SYS/'+logical, parent_bom_id='SYSTEM', hierarchy_level='1',
             schematic_reference=e.get('ref'), sheet_path='/', logical_reference=logical,
             value=logical, design_quantity='1')
    if logical == 'STOPBOARD':
        d.update(item_kind='DERIVED_ASSEMBLY_PARENT', source_pn='WP09 stop circuit candidate',
                 standalone_purchase_quantity='0', procurement_rule='ROLL_UP_PARENT_DO_NOT_PURCHASE_AGAIN',
                 role='EXTERNAL_GSE_STOP_CONTROL_CIRCUIT_CANDIDATE',
                 source_claim='71 schematic children: 66 selected component instances and 5 logical port boundaries',
                 source_record_file='electrical_delta/STOP_BOM.csv',
                 source_file_sha256=source_hashes['stop_source_bom'],
                 source_selection_scope='ASSEMBLY_CIRCUIT_ONLY_NO_PCB_RELEASE',
                 mass_accounting='PARENT_ROLLUP_ONLY_DO_NOT_ADD_TO_CHILDREN',
                 notes='Supersedes parent STOP_CONTROL responsibility; PCB, connectors, local supplies and enclosure remain unbound.')
    elif logical.startswith('PV_BRANCH_'):
        d.update(item_kind='LOGICAL_ARRAY_BRANCH_BOUNDARY', standalone_purchase_quantity='0',
                 procurement_rule='LOGICAL_BOUNDARY_NOT_A_PURCHASABLE_MODULE',
                 role='ARRAY_INTERFACE_REFERENCE', source_record_file='ecad/exports/wp09_system.xml',
                 source_file_sha256=source_hashes['actual_system_netlist'],
                 source_selection_scope='NETLIST_BOUNDARY_ONLY',
                 mass_accounting='LOGICAL_BOUNDARY_NO_PHYSICAL_MASS',
                 notes='Not an extra array, cell or blocking diode; retain CIC_REF and PV_BLOCKING reference responsibilities.')
    else:
        p = parent_by_ref[logical]; used_parent.add(logical); inherit_parent(d,p)
        d['item_kind'] = 'INHERITED_SYSTEM_ITEM_BOUNDARY'
        if logical == 'FPP':
            d.update(item_kind='OPEN_HARDWARE_RESPONSIBILITY_BOUNDARY',
                     notes='UNBOUND full FPP/RBF/dearm implementation; no selected physical part.')
        elif logical == 'PDU':
            d['notes'] = 'PDU text includes Dock interface/configuration; DOCK is its own row and is not multiplied by this description.'
    out.append(d)

for e in child:
    r = stop_by_ref[e.get('ref')]; d = base(); logical = r['reference']
    is_boundary = logical.startswith('J')
    d.update(bom_id='SYS/STOPBOARD/'+logical, parent_bom_id='SYS/STOPBOARD', hierarchy_level='2',
             schematic_reference=logical, sheet_path=e.find('sheetpath').get('names'),
             logical_reference=logical,
             item_kind='LOGICAL_CONNECTOR_BOUNDARY' if is_boundary else 'SELECTED_CIRCUIT_COMPONENT',
             source_pn=r['mpn'], manufacturer_part_number='' if is_boundary else r['mpn'],
             value=r['value'], design_quantity=r['quantity'],
             standalone_purchase_quantity='0' if is_boundary else '',
             procurement_rule='BOUNDARY_ONLY_CONNECTOR_MATE_NOT_SELECTED' if is_boundary else 'CANDIDATE_COMPONENT_NOT_PURCHASE_RELEASED',
             role='STOPBOARD_PORT' if is_boundary else 'STOPBOARD_COMPONENT',
             source_claim=r['source'], source_record_file='electrical_delta/STOP_BOM.csv',
             source_file_sha256=source_hashes['stop_source_bom'], source_row_sha256=canonical_sha(r),
             source_selection_scope=r['scope'], source_footprint=r['footprint'],
             unverified_package_reference=r['package_reference_unverified'],
             mass_accounting='LOGICAL_BOUNDARY_NO_PHYSICAL_MASS' if is_boundary else 'UNKNOWN_NOT_INCLUDED_IN_TOTAL',
             notes=('J symbol is an electrical boundary, not a selected physical connector; contacts, housing and mate remain open.' if is_boundary
                 else 'MPN and source inherited verbatim from frozen STOP_BOM; package reference is unverified, footprint blank; no PCB/hardware validation.'))
    assert e.findtext('value') == r['mpn']+' / '+r['value'], (logical, e.findtext('value'), r['value'])
    out.append(d)

for p in parents:
    if p['ref'] in used_parent: continue
    d=base(); inherit_parent(d,p)
    d.update(bom_id='REF/'+p['ref'], parent_bom_id='SYSTEM_REFERENCE_RESPONSIBILITIES',
             hierarchy_level='1', logical_reference=p['ref'], value=p['pn'],
             item_kind='PARENT_REFERENCE_OUTSIDE_CURRENT_NETLIST',
             notes='Preserved parent source row; no present 94-component netlist coverage or new design completion credit.')
    if p['ref'] == 'STOP_CONTROL':
        d.update(item_kind='SUPERSEDED_PARENT_RESPONSIBILITY', standalone_purchase_quantity='0',
                 procurement_rule='SUPERSEDED_BY_SYS_STOPBOARD_DO_NOT_ORDER_OR_SUM',
                 mass_accounting='SUPERSEDED_REFERENCE_NO_ADDITIONAL_MASS',
                 notes='Original parent quantity/pn retained for lineage. Current candidate responsibility is SYS/STOPBOARD with 71 children; original row is not an additional controller.')
    elif p['ref'] == 'CIC_REF':
        d['notes'] = '84-cell parent reference retained verbatim; this is not 84 additional cells beyond the separate solar mechanical model. Source refresh/integration belongs to solar work package.'
        d['procurement_rule']='REFERENCE_ARRAY_COUNT_DO_NOT_ADD_TO_SOLAR_MODEL_OR_RELEASE_ORDER'
    elif p['ref'] == 'PV_BLOCKING':
        d['notes']='12-diode requirement only; no frozen MPN or current circuit symbol. Six PV branch boundary symbols do not satisfy this requirement.'
    out.append(d)

checks=[]
def check(name, ok, detail=None):
    checks.append({'check':name,'pass':bool(ok),'detail':detail}); assert ok, (name,detail)
refs=[r['schematic_reference'] for r in out if r['schematic_reference']]
check('one_to_one_actual_94_refs', Counter(refs)==Counter(e.get('ref') for e in components))
check('unique_bom_ids',len(out)==len({r['bom_id'] for r in out}))
check('top_level_23',sum(r['sheet_path']=='/' for r in out)==23)
check('child_71',sum(r['parent_bom_id']=='SYS/STOPBOARD' for r in out)==71)
check('66_selected_child_instances',sum(r['item_kind']=='SELECTED_CIRCUIT_COMPONENT' and r['design_quantity']=='1' and bool(r['manufacturer_part_number']) for r in out)==66)
check('5_nonphysical_J_boundaries',sum(r['item_kind']=='LOGICAL_CONNECTOR_BOUNDARY' and not r['manufacturer_part_number'] and r['standalone_purchase_quantity']=='0' for r in out)==5)
check('STOPBOARD_not_extra_purchase',next(r for r in out if r['bom_id']=='SYS/STOPBOARD')['standalone_purchase_quantity']=='0')
check('all_parent_rows_preserved_or_mapped', {r['source_row_sha256'] for r in out if r['source_record_file']=='../reuse_closure/ecad/MASTER_BOM.csv'}=={canonical_sha(p) for p in parents})
for r in out:
    check('source_file_binding:'+r['bom_id'],r['source_file_sha256'] in source_hashes.values())
    check('no_false_release:'+r['bom_id'],r['fabrication_release']=='False' and r['hardware_verified']=='False' and r['mass_kg']=='')
    if r['item_kind']=='SELECTED_CIRCUIT_COMPONENT':
        src=stop_by_ref[r['logical_reference']]
        check('exact_source_mpn_quantity:'+r['bom_id'],r['manufacturer_part_number']==src['mpn'] and r['design_quantity']==src['quantity'] and r['source_row_sha256']==canonical_sha(src))
    if r['schematic_reference']:
        check('unique_netlist_identity:'+r['bom_id'],refs.count(r['schematic_reference'])==1)
check('inputs_unchanged_during_build', source_hashes=={k:sha(v) for k,v in FILES.items()})

dest=C/'ecad/MASTER_BOM.csv'
with dest.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=columns); w.writeheader(); w.writerows(out)
notes='''# 整机电气分层 BOM（2026-09-08）

本表由实际 KiCad 导出网表、冻结停止子页 BOM 和原版参考 BOM 生成。94 个网表元件各有唯一 `schematic_reference`：23 个顶层边界、71 个停止子页元件。另保留原版未出现在现行网表中的责任行；它们不获得网表覆盖信用。

`SYS/STOPBOARD` 是停止子板父装配责任项，不再作为一块现成控制器重复采购或与子件质量相加。其 71 个子项包括 **66 个带来源 MPN 的候选元件实例和 5 个 J 电气接口边界**。J101–J105 的符号、接口名称与针号均不代表已选定实体连接器；这些行的 MPN 留空，独立采购数为 0。实际连接器、接触件与配对端仍需选择。所有子页 footprint 保持原表为空；`unverified_package_reference` 只是待核验封装候选，不是已验证 PCB 封装。

表中 `design_quantity` 是设计/责任数量；**不能直接求和当作采购数量或实物总数**。`standalone_purchase_quantity` 留空表示尚未确定独立购买数量，并不表示无需购买；0 仅用于明确不独立采购的逻辑边界、装配父项和已替代责任项。此表不包含下单授权，所有制造放行和硬件验证字段均为 False。

原版 ODrive 行写明附带 2 Ω / 50 W 电阻，故 U1/RB1 共享采购组，RB1 不自动增加独立采购。B601 DM 套装与 100045091 分线板、100011896 USB-CAN 板共用套装组；收到的套装内容尚未确认，须按实际交付清点后去重。PDU 行中的 Dock 为接口/配置说明，DOCK 独立责任行不会据此倍增。两条 RS422 线是两个独立候选实例，未合并。

原版 STOP_CONTROL 保留原文与原设计数量作历史追溯，但明确已由 SYS/STOPBOARD 接替，不多出一个控制器。CIC_REF 的 84 片是原版阵列参考计数，与独立太阳阵列机械模型不得累加。PV_BLOCKING 的 12 只仍为未选型责任；6 个 PV_BRANCH 网络边界并没有补完二极管设计。GSE_PCB、线束连接器、PC 等未进入本次 94 元件网表的原版行继续保留。

`source_pn`、`source_claim` 逐项继承原表；顶层原版 PN 是描述性文本，未冒充新核验的完整厂家订货号。停止电路的 66 个 MPN 则逐字绑定冻结子页来源。每行包含来源文件 SHA-256 与来源行规范 JSON SHA-256；整合回执还绑定实际导出网表和端点表。这个整合验证证明身份、数量与来源一致，不证明所有器件已经到货、PCB 可制造、停止全链路已测或整星电气设计完成。

本表不新增质量或采购总价：各元件实际质量未知，停止子板父项与子件不可重复相加。高功率航天电源、停止电路 3.3 V/5.1 V 本地电源、ADC/总线诊断、推进器受控 ICD 及实物试验等仍由对应工作包收束。

复现：使用项目 Python 运行 `tools/build_stop_bom.py`，读取现有源文件，不修改原版或冻结停止电路。结果见 `results/STOP_BOM_INTEGRATION.json`。
'''
notes_path=C/'ecad/MASTER_BOM_NOTES.md';notes_path.write_text(notes,encoding='utf-8')
receipt={
 'status':'PASS_HIERARCHICAL_BOM_IDENTITY_QUANTITY_SOURCE_BINDINGS__DESIGN_OPEN',
 'schema_version':1,'date':'2026-09-08',
 'row_count':len(out),'actual_netlist_components':94,'top_level_netlist_components':23,
 'stop_child_components':71,'selected_stop_component_instances':66,'logical_J_boundaries':5,
 'parent_reference_rows_outside_netlist':sum(not r['schematic_reference'] for r in out),
 'parent_source_rows_preserved':len(parents),'checks_passed':sum(x['pass'] for x in checks),'checks_total':len(checks),
 'source_bindings':{k:{'path':str(v),'sha256':source_hashes[k]} for k,v in FILES.items()},
 'outputs':{'MASTER_BOM.csv':{'path':str(dest),'sha256':sha(dest)},'MASTER_BOM_NOTES.md':{'path':str(notes_path),'sha256':sha(notes_path)}},
 'generator_sha256':sha(Path(__file__)),
 'manufacturing_release':False,'hardware_io_executed':False,'procurement_authorized':False,
 'whole_system_electrical_design_complete':False,'total_mass_kg':None,'total_purchase_quantity':None,
 'checks':checks}
(C/'results/STOP_BOM_INTEGRATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ('checks','source_bindings','outputs')},ensure_ascii=False))
