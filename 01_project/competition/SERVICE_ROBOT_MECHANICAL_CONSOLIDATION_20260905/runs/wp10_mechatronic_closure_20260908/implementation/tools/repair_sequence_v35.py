"""Apply the reviewed hold-up correction and canonicalize only new symbols."""
import json,copy,shutil
from pathlib import Path
from erc_source_contract import parse,enc,children,val,properties
from finish_sequence_source_v35 import pin_xy,at,uid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35';R=A/'results/aux_v35'
p=D/'wp10_aux_sequence.kicad_sch';t=parse(p.read_text());parent=parse((D/'wp10_system.kicad_sch').read_text())
from erc_source_contract import node_uuid
sheet=next(s for s in children(parent,'sheet') if 'wp10_aux_sequence.kicad_sch' in properties(s).values());full='/'+node_uuid(parent)+'/'+node_uuid(sheet)
for ref,pn in [('U208',1),('C217',1)]:
    xy=pin_xy(t,ref,pn);gs=[]
    for g in children(t,'global_label'):
        gx,gy=map(float,children(g,'at')[0][1:3])
        if abs(gy-xy[1])<1e-6 and abs(abs(gx-xy[0])-3.81)<1e-5:gs.append(g)
    assert len(gs)==1,(ref,xy,gs);assert val(gs[0][1])=='WP10_AUX_LIMITED';gs[0][1]=json.dumps('WP10_AUX_SEQ_VDD')
parts=json.loads((R/'SELECTED_PARTS.json').read_text())
for ref in ['D209','D210']:
    s=next(s for s in children(t,'symbol') if properties(s)['Reference']==ref)
    for x in list(children(s,'instances')):s.remove(x)
    s.append(['instances',['project',json.dumps('wp10_system'),['path',json.dumps(full),['reference',json.dumps(ref)],['unit','1']]]])
    for q in children(s,'property'):
        if val(q[1])=='Datasheet':q[2]=json.dumps('https://www.st.com/resource/en/datasheet/stps3h100.pdf')
    from finish_sequence_source_v35 import prop
    prop(s,'MPN','STPS3H100U');prop(s,'Manufacturer','STMicroelectronics');prop(s,'Selection_Revision','V35')
    parts[ref]=dict(MPN='STPS3H100U',manufacturer='STMicroelectronics',footprint='WP10_AUX:STPS3H100U_K1A2',source_url='https://www.st.com/resource/en/datasheet/stps3h100.pdf',role='Supply diode OR: K to U208 VDD; A to protected AUX or retained6V bias')
    for pn in [1,2]:
        xy=pin_xy(t,ref,pn);g=next(g for g in children(t,'global_label') if tuple(map(float,children(g,'at')[0][1:3]))==xy)
        end=(xy[0]+(-3.81 if pn==1 else 3.81),xy[1]);angle=180 if pn==1 else 0
        t.append(['wire',['pts',['xy',str(xy[0]),str(xy[1])],['xy',str(end[0]),str(end[1])]],['stroke',['width','0'],['type','default']],['uuid',uid()]])
        at(g,*end,angle);eff=children(g,'effects')[0]
        for j in list(children(eff,'justify')):eff.remove(j)
        eff.append(['justify','right' if pn==1 else 'left']);children(children(eff,'font')[0],'size')[0][1:]=['.8','.8']
        for q in children(g,'property'):at(q,*end,0)
# Canonical copy avoids the MCP's divergent embedded PORT symbol.
library=parse((D/'WP10SEQ.kicad_sym').read_text());block=children(t,'lib_symbols')[0]
for s in list(children(block,'symbol')):
    name=val(s[1])
    if name.startswith('WP10SEQ:'):
        canon=copy.deepcopy(next(x for x in children(library,'symbol') if val(x[1])==name.split(':')[1]));canon[1]=json.dumps(name);block[block.index(s)]=canon
p.write_text(enc(t)+'\n');(R/'SELECTED_PARTS.json').write_text(json.dumps(parts,indent=2)+'\n')
shutil.copy2(D/'wp10_aux_protection.kicad_pcb',R/'REJECTED_FIRST_LAYOUT.kicad_pcb')
shutil.copy2(D.parent/'v34/wp10_aux_protection.kicad_pcb',D/'wp10_aux_protection.kicad_pcb')
print('Added retained-bias diode OR, canonical symbols, archived rejected placement for corrected rebuild')
