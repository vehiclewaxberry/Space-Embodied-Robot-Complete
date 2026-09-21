"""Repair MCP project/cache/library metadata; preserve all schematic connectivity."""
from pathlib import Path
import copy,json,hashlib
from erc_source_contract import parse,enc,children,val,properties,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';R=A/'results/stop_v36/pcb'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parent=parse((D/'wp10_system.kicad_sch').read_text())
    p=D/'wp10_stop_detail.kicad_sch';t=parse(p.read_text())
    sheet=next(s for s in children(parent,'sheet') if p.name in properties(s).values())
    full='/'+node_uuid(parent)+'/'+node_uuid(sheet)
    j=next(s for s in children(t,'symbol') if properties(s)['Reference']=='J106')
    for x in list(children(j,'instances')):j.remove(x)
    j.append(['instances',['project',json.dumps('wp10_system'),['path',json.dumps(full),['reference',json.dumps('J106')],['unit','1']]]])
    lib=parse((D/'WP10STOP36.kicad_sym').read_text());block=children(t,'lib_symbols')[0]
    for s in list(children(block,'symbol')):
        name=val(s[1])
        if name.startswith('WP10STOP36:'):
            canon=copy.deepcopy(next(x for x in children(lib,'symbol') if val(x[1])==name.split(':')[1]))
            canon[1]=json.dumps(name);block[block.index(s)]=canon
    p.write_text(enc(t)+'\n',encoding='utf-8')
    p=D/'fp-lib-table';t=parse(p.read_text());known={val(children(x,'name')[0][1]) for x in children(t,'lib')}
    parts=json.loads((R/'PHYSICAL_PARTS.json').read_text())
    for name in sorted({p['footprint'].split(':')[0] for p in parts.values()}-known):
        t.append(['lib',['name',json.dumps(name)],['type',json.dumps('KiCad')],['uri',json.dumps('${KIPRJMOD}/'+name+'.pretty')],['options',json.dumps('')],['descr',json.dumps('V36 STOP candidate; local footprint sources bound separately')]])
    p.write_text(enc(t)+'\n',encoding='utf-8')
    actual={properties(s)['Reference']:properties(s) for p in D.glob('*.kicad_sch') for s in children(parse(p.read_text()),'symbol')}
    mismatches=[ref for ref,p in parts.items() if actual[ref].get('Footprint')!=p['footprint'] or actual[ref].get('MPN')!=p['MPN']]
    missing=[ref for ref,p in parts.items() if not (D/(p['footprint'].split(':')[0]+'.pretty')/(p['footprint'].split(':')[1]+'.kicad_mod')).is_file()]
    assert not mismatches and not missing,(mismatches,missing)
    state=dict(revision='V36',formal_active_revision='V35',status='WORKING_STOP_PHYSICAL_MAPPING_CHECKPOINT',electrical_source_refs=len([r for r in actual if not r.startswith('#')]),STOP_board_selected_refs=len(parts),STOP_PCB_implemented=False,whole_design_complete=False,hardware_tests=0,
        notes='J106 metadata and15thermal footprints repaired;2custom footprints created. Old root XML/ERC/BOM remain historical. Fresh checkpoint evidence is under results/stop_v36/pcb/native_checkpoint_20260916; planned9filter parts NOT implemented.')
    (D/'WORKING_REVISION.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    (R/'METADATA_REPAIR.json').write_text(json.dumps(dict(**state,J106_instance_path=full,footprint_mapping_mismatches=mismatches,missing_footprint_files=missing,source_bindings={str(p):sha(p) for p in list(D.glob('*.kicad_sch'))+[D/'fp-lib-table',D/'WP10STOP36.kicad_sym']}),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(state))
if __name__=='__main__':main()
