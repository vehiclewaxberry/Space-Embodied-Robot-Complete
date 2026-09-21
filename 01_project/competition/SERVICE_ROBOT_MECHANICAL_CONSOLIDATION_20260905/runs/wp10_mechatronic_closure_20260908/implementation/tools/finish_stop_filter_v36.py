"""Reconcile nine MCP instances and record explicit filter endpoint contract."""
from pathlib import Path
import json,copy,hashlib
from erc_source_contract import parse,enc,children,properties,val,node_uuid
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';P=A/'results/stop_v36/pcb';R=P/'thermal_filter_20260916'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    plans=json.loads((R/'MCP_PLAN.json').read_text());delta=json.loads((R/'DELTA_PARTS.json').read_text());parent=parse((D/'wp10_system.kicad_sch').read_text());lib=parse((D/'Device.kicad_sym').read_text())
    expected={};changed={}
    for p in plans:
        path=D/p['sheet'];t=parse(path.read_text());refs={z['reference'] for z in p['components']}
        sheet=next(s for s in children(parent,'sheet') if path.name in properties(s).values())
        full='/'+node_uuid(parent)+'/'+node_uuid(sheet)
        for s in children(t,'symbol'):
            ref=properties(s)['Reference']
            if ref in refs:
                for x in list(children(s,'instances')):s.remove(x)
                s.append(['instances',['project',json.dumps('wp10_system'),['path',json.dumps(full),['reference',json.dumps(ref)],['unit','1']]]])
        block=children(t,'lib_symbols')[0]
        for s in list(children(block,'symbol')):
            name=val(s[1])
            if name in ['Device:R','Device:C']:
                canon=copy.deepcopy(next(x for x in children(lib,'symbol') if val(x[1])==name.split(':')[1]));canon[1]=json.dumps(name);block[block.index(s)]=canon
        path.write_text(enc(t)+'\n',encoding='utf-8')
        for ref,pins in p['connections'].items():
            for pin,net in pins.items():
                target=changed if ref.startswith('U') else expected
                target[ref+'.'+pin]=net
    physical=json.loads((P/'PHYSICAL_PARTS.json').read_text());physical.update(delta)
    assert len(physical)==103
    actual={properties(s)['Reference']:properties(s) for p in D.glob('*.kicad_sch') for s in children(parse(p.read_text()),'symbol')}
    assert all(actual[ref].get('Footprint')==p['footprint'] and actual[ref].get('MPN')==p['MPN'] for ref,p in physical.items())
    dump(P/'PHYSICAL_PARTS.json',physical)
    scope=json.loads((P/'BOARD_SCOPE.json').read_text());scope['physical_refs']=sorted(physical);scope['thermal_input_filter_revision']='V36_FILTER_20260916';dump(P/'BOARD_SCOPE.json',scope)
    spec=dict(schema='WP10_STOP_FILTER_ENDPOINT_CONTRACT',prior_native=str(P/'native_checkpoint_20260916/wp10_system.xml'),prior_checkpoint=str(P/'native_checkpoint_20260916/CHECKPOINT_VERIFICATION.json'),
       expected_added_refs=sorted(delta),expected_added_pins=expected,expected_changed_existing_pins=changed,expected_total_refs=249,expected_total_pins=795,expected_board_refs=103,
       topology='raw NTC node retains8.2k pullup,NTC and649k branch. Only INA+ branch gains1k. Each INA+/INB- gets1nF to ARM_RETURN.',
       unchanged_NTC_J106_and_divider_connections_required=True,hardware_qualification=False,whole_design_complete=False)
    dump(R/'FILTER_INTENT.json',spec)
    state=json.loads((D/'WORKING_REVISION.json').read_text());state.update(status='WORKING_STOP_FILTER_SOURCE',electrical_source_refs=249,STOP_board_selected_refs=103,notes='Nine thermal RC parts implemented. Native240ref checkpoint is historical; fresh filter evidence required. STOP PCB not yet created.');dump(D/'WORKING_REVISION.json',state)
    print(json.dumps(dict(added_refs=len(delta),new_pin_contract=len(expected),changed_pins=changed,board_refs=len(physical))))
if __name__=='__main__':main()
