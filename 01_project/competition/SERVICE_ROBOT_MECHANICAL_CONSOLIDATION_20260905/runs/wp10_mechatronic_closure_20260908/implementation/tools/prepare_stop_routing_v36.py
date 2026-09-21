"""Declare routing width allocations, verify native netclasses and export DSN."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
import pcbnew as k
from build_stop_board_v36 import A,D,P,R,mm
def main():
    target=D/'wp10_stop_control.kicad_pcb';pro=target.with_suffix('.kicad_pro')
    state=json.loads(pro.read_text());default=state['net_settings']['classes'][0]
    specs={'Power24':(.75,1.,.5),'Return':(.4,.8,.4),'LogicSupply':(.35,.7,.35)}
    classes=[default]
    for name,(width,dia,drill) in specs.items():
        item=dict(default);item.update(name=name,track_width=width,via_diameter=dia,via_drill=drill);classes.append(item)
    rt=ET.parse(P/'thermal_filter_20260916/native_20260916_a/wp10_system.xml').getroot()
    pn={(n.get('ref'),n.get('pin')):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node')}
    assignments={pn['J101','3']:'Power24',pn['Q101','2']:'Power24','WP10_ARM_RETURN':'Return',pn['U101','1']:'LogicSupply',pn['U112','1']:'LogicSupply'}
    state['net_settings'].update(classes=classes,netclass_patterns=[dict(netclass=c,pattern=n) for n,c in assignments.items()])
    pro.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    b=k.LoadBoard(str(target))
    seen={str(n):ni.GetNetClassName() for n,ni in b.GetNetsByName().items() if str(n) in assignments}
    # Project-native routing settings must actually resolve, not just exist in JSON.
    print(json.dumps(dict(expected=assignments,native=seen)))
    assert set(seen)==set(assignments) and all(c in seen[n].split(',') for n,c in assignments.items()),('Native class membership mismatch',seen)
    dsn=R/'STOP_ROUTING.dsn';assert k.ExportSpecctraDSN(b,str(dsn))
    from erc_source_contract import parse,children,val
    ds=parse(dsn.read_text());nc=children(children(ds,'network')[0],'class');widths={}
    for cl in nc:
        ws=[float(w[1]) for rule in children(cl,'rule') for w in children(rule,'width')]
        for net in assignments:
            if net in [val(x) for x in cl[2:] if isinstance(x,str)] and ws:widths[net]=ws[0]/1000
    assert widths=={n:specs[c][0] for n,c in assignments.items()},('Native exported DSN widths require investigation',widths)
    (R/'ROUTING_ALLOCATION.json').write_text(json.dumps(dict(netclass_assignments=assignments,native_netclasses=seen,native_effective_width_mm=widths,classes=classes,dsn=str(dsn),dsn_sha256=hashlib.sha256(dsn.read_bytes()).hexdigest(),scope='Trace geometry allocations only; current/temperature and transient release not inferred',whole_design_complete=False),indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
