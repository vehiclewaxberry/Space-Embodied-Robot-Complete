"""Reconcile MCP project metadata and archive explicit revision scope."""
from pathlib import Path
import json,copy
from erc_source_contract import parse,enc,children,val,properties,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';R=A/'results/stop_v36'
t=parse((D/'wp10_stop_detail.kicad_sch').read_text());parent=parse((D/'wp10_system.kicad_sch').read_text())
sheet=next(s for s in children(parent,'sheet') if 'wp10_stop_detail.kicad_sch' in properties(s).values());full='/'+node_uuid(parent)+'/'+node_uuid(sheet)
for s in children(t,'symbol'):
    ref=properties(s)['Reference']
    if ref in ['U112','U119','R180','R181']:
        for x in list(children(s,'instances')):s.remove(x)
        s.append(['instances',['project',json.dumps('wp10_system'),['path',json.dumps(full),['reference',json.dumps(ref)],['unit','1']]]])
for x in children(t,'text'):
    if 'Actual TSR1 supplies and TC4420 driver' in val(x[1]):
        x[1]=json.dumps('V36 STOP candidate: UCC27517 OUT = RAW healthy AND RUN. U119 LV1T04 inverts fast RUN.\nU102 5V bias monitors3.3V. R1014.7k / R18147k; UCC input-current bounds unverified.\n0..50C conditional static design; brownout/rearm/coil release/regen/PCB/hardware remain OPEN.')
# Importing/replacing symbols can leave a divergent embedded copy. Restore local canonical symbol definitions only.
lib=parse((D/'WP10STOP36.kicad_sym').read_text());block=children(t,'lib_symbols')[0]
for s in list(children(block,'symbol')):
    name=val(s[1])
    if name.startswith('WP10STOP36:'):
        canon=copy.deepcopy(next(x for x in children(lib,'symbol') if val(x[1])==name.split(':')[1]));canon[1]=json.dumps(name);block[block.index(s)]=canon
(D/'wp10_stop_detail.kicad_sch').write_text(enc(t)+'\n',encoding='utf-8')
p=D/'sym-lib-table';z=parse(p.read_text())
for lib in children(z,'lib'):
    name=val(children(lib,'name')[0][1])
    if (D/(name+'.kicad_sym')).exists():children(lib,'uri')[0][1]=json.dumps('${KIPRJMOD}/'+name+'.kicad_sym')
p.write_text(enc(z)+'\n',encoding='utf-8')
selected={properties(s)['Reference']:properties(s) for s in children(t,'symbol') if properties(s).get('Selection_Revision')=='V36'}
(R/'SELECTED_PARTS.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
(D/'WORKING_REVISION.json').write_text(json.dumps(dict(revision='V36',formal_active_revision='V35',status='WORKING_STOP_SOURCE_NOT_WHOLE_RELEASE',STOP_PCB_implemented=False,whole_design_complete=False,hardware_tests=0,notes='Copied V35 derivative BOM/CSV/PCB files are inherited until individually regenerated; only native freshly exported XML plus V36 audit can validate changed source.'),indent=2)+'\n')
print('Reconciled four project instances and two embedded symbols; V35 pointer retained')
