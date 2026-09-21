"""Normalize MCP-produced hierarchy instance paths, then freeze its source nodes.

MCP selected an unrelated .kicad_pro basename and omitted the root UUID in
symbol instance paths. Only the newly added declaration sheet is repaired.
No physical symbol, wire, footprint, or pin definition is generated here.
"""
from erc_source_contract import *
import shutil

root_path=A/'ecad/wp10_system.kicad_sch'; page_path=A/'ecad'/PAGE
root=parse(root_path.read_text()); page=parse(page_path.read_text())
new_sheets=[s for s in children(root,'sheet') if properties(s).get('Sheet file',properties(s).get('Sheetfile'))==PAGE]
assert len(new_sheets)==1
sheet=new_sheets[0];rid=node_uuid(root);sid=node_uuid(sheet)
for old in children(sheet,'instances'):sheet.remove(old)
sheet.append(['instances',['project',json.dumps('wp10_system'),['path',json.dumps('/'+rid),['page','"12"']]]])
for block in children(root,'sheet_instances'):
    for path in list(children(block,'path')):
        if val(path[1])!='/' and sid in val(path[1]):block.remove(path)
for symbol in children(page,'symbol'):
    ref=properties(symbol)['Reference'];assert ref.startswith('#FLG')
    for key in ['in_bom','on_board','in_pos_files']:
        for n in children(symbol,key):n[1]='no'
    for old in children(symbol,'instances'):symbol.remove(old)
    symbol.append(['instances',['project','"wp10_system"',['path',json.dumps('/'+rid+'/'+sid),['reference',json.dumps(ref)],['unit','1']]]])
for n in children(page,'sheet_instances'):page.remove(n)
root_path.write_text(enc(root),encoding='utf-8');page_path.write_text(enc(page),encoding='utf-8')
src=A/'power/erc_sources';src.mkdir(exist_ok=True)
shutil.copy2(page_path,src/PAGE)
dump(src/'root_sheet.json',sheet)
flags,_,_=source_inventory(root_path)
assert len(flags)==7
_,pins=physical_netlist(H/'ecad/wp10_system.xml')
ep=read(A/'ecad/SYSTEM_ENDPOINT_MAP.json')
k1a=ep['K1.A2(+)'];k1b=ep['K1.A1(-)']
node_groups=[['U101.4','U202.6','U203.5'],['J200.1','F201.1','F201.2','U201.2'],
 ['J200.2','U201.5','U202.2','U203.4'],['J200.1','F202.1','F202.2','U202.1'],
 ['F201.2','R201.1','R201.2','R202.1','R202.2','Q201.2','Q201.3','U203.1'],
 ['U203.9','Q202.3','Q202.2','Q203.2','U204.10','U204.12'],
 ['U203.9','Q202.3','Q202.2','Q203.2','Q203.3',k1a['ref']+'.'+k1a['pin'],k1b['ref']+'.'+k1b['pin'],'U301.10']]
conditions=[
 'Intentional common isolated secondary reference. Positive outputs remain separate; no primary-secondary bridge.',
 'External protected source present at project J200 and F201 intact. Battery OEM cavity and Sys Detect remain unbound.',
 'External primary return boundary at project J200. This is not proof of an OEM-approved battery connection.',
 'Protected source and F202 intact. Independent of Q201; not independent of the battery or AUX fuse.',
 'F201/R201/R202/Q201 conductive with valid supply and appropriate latched/precharge state. ERC does not evaluate startup.',
 'CHB may feed through Q202 S-to-D body diode/channel. ARM regeneration may feed through closed K1 and Q203 S-to-D diode. Diode drops and dynamics unverified.',
 'Forward path requires CHB, Q202/Q203 and closed K1. Motor regeneration can energize the load-side bus with K1 open; its energy and timing remain unverified.'
]
declarations=[]
for i,f in enumerate(sorted(flags,key=lambda f:f['reference'])):
    assert len(f['nets'])==1
    d={k:f[k] for k in ['reference','uuid','library','sheet','position','instances']}
    d.update(net=f['nets'][0],condition=conditions[i],required_nodes={p:pins[tuple(p.rsplit('.',1))][0] for p in node_groups[i]})
    declarations.append(d)
contract=dict(schema='WP10_CONDITIONAL_ERC_SOURCE_DECLARATIONS_V16',root_uuid=rid,sheet_uuid=sid,declarations=declarations,
 source_bindings={p.relative_to(A).as_posix():sha(p) for p in [src/PAGE,src/'root_sheet.json',A/'ecad/power.kicad_sym']},
 provenance='Symbols, labels, text and hierarchical sheet created through KiCad MCP. Project/path/BOM metadata normalized locally because MCP chose a different project basename and incomplete instance paths.',
 sources=['https://docs.kicad.org/10.0/en/eeschema/eeschema.html#power-pins-and-power-flags','https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf'],
 permission_basis=['WP09R work order line108 permits evidence-supported normal EDA declarations','WP10 work order line166 permits reasonable EDA marks without concealing absent power/control'],
 baseline_entities=201,baseline_pin_network_type_nodes=657,hardware_qualified=False,battery_OEM_interface_bound=False,
 operating_state_simulation=False,whole_design_complete=False)
dump(A/'power/ERC_SOURCE_DECLARATIONS.json',contract)
print(json.dumps(dict(declarations=len(declarations),root_uuid=rid,sheet_uuid=sid,physical_entities_edited=0)))
