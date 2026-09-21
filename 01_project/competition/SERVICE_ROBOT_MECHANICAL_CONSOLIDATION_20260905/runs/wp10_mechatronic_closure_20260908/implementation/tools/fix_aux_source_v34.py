"""Remove the observed stale label left by MCP replace; source-level exact fix."""
from pathlib import Path
import json,copy
from erc_source_contract import parse,enc,children,val,properties,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34'
P=D.parent/'v32'
# Restore unchanged parent structures from source, applying only intended deltas.
p=D/'wp10_power_3.kicad_sch';t=parse((P/p.name).read_text(encoding='utf-8-sig'))
old=[x for x in children(t,'global_label') if val(x[1])=='WP10_AUX_FUSED']
assert len(old)==1
old[0][1]=json.dumps('WP10_AUX_LIMITED');p.write_text(enc(t)+'\n',encoding='utf-8')
p=D/'wp10_power_1.kicad_sch';new=parse(p.read_text(encoding='utf-8-sig'));t=parse((P/p.name).read_text(encoding='utf-8-sig'))
a=next(s for s in children(new,'symbol') if properties(s)['Reference']=='R202')
b=next(s for s in children(t,'symbol') if properties(s)['Reference']=='R202')
for q in list(children(b,'property')):b.remove(q)
b.extend(copy.deepcopy(children(a,'property')))
p.write_text(enc(t)+'\n',encoding='utf-8')
p=D/'wp10_system.kicad_sch';new=parse(p.read_text(encoding='utf-8-sig'));t=parse((P/p.name).read_text(encoding='utf-8-sig'))
s=next(s for s in children(new,'sheet') if 'wp10_aux_protection.kicad_sch' in properties(s).values())
for q in children(s,'property'):
    if val(q[1]) in ['Sheet name','Sheetname']:q[1]=json.dumps('Sheetname')
    if val(q[1]) in ['Sheet file','Sheetfile']:q[1]=json.dumps('Sheetfile')
t.append(s);p.write_text(enc(t)+'\n',encoding='utf-8')
# MCP selected the first .kicad_pro in a multi-board folder; explicitly bind the authoritative hierarchy.
p=D/'wp10_aux_protection.kicad_sch';aux=parse(p.read_text(encoding='utf-8-sig'));full='/'+node_uuid(t)+'/'+node_uuid(s)
for c in children(aux,'symbol'):
    for q in list(children(c,'instances')):c.remove(q)
    c.append(['instances',['project',json.dumps('wp10_system'),['path',json.dumps(full),['reference',json.dumps(properties(c)['Reference'])],['unit','1']]]])
p.write_text(enc(aux)+'\n',encoding='utf-8')
print('Only U202.1 net and R202 properties changed; 14th sheet bound to original root UUID')
