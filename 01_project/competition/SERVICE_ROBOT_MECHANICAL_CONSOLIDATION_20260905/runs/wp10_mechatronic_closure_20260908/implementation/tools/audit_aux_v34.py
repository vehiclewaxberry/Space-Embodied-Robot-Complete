"""Actual native pad/net and copper inventory, with immutable parent comparison."""
from pathlib import Path
import json,hashlib,collections,xml.etree.ElementTree as ET
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34';R=A/'results/aux_v34'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    def xml(p):
        x=ET.parse(p).getroot()
        return ({c.get('ref'):c for c in x.findall('./components/comp')},
          {(n.get('ref'),n.get('pin')):net.get('name') for net in x.findall('./nets/net') for n in net.findall('node')})
    comp,nodes=xml(D/'wp10_system.xml');old,on=xml(D.parent/'v32/wp10_system.xml')
    b=k.LoadBoard(str(D/'wp10_aux_protection.kicad_pcb'))
    pads=[];mismatch=[];refs=[]
    for f in b.GetFootprints():
        if f.GetReference().startswith('MH34_'):continue
        ref=f.GetReference();refs.append(ref)
        for p in f.Pads():
            if not p.GetNumber():continue
            q=dict(ref=ref,pin=p.GetNumber(),net=p.GetNetname(),expected=nodes.get((ref,p.GetNumber())),xy_mm=[k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y)])
            pads.append(q)
            if q['net']!=q['expected']:mismatch.append(q)
    delta=[dict(ref=r,pin=p,before=n,after=nodes.get((r,p))) for (r,p),n in on.items() if nodes.get((r,p))!=n]
    value_delta=[dict(ref=r,before=c.findtext('value'),after=comp[r].findtext('value')) for r,c in old.items() if comp[r].findtext('value')!=c.findtext('value')]
    copper=[];sums=collections.defaultdict(float);via_counts=collections.Counter()
    power_nets=['WP10_AUX_FUSED','WP10_AUX_LIMITED','WP10_INPUT_RETURN']
    for t in b.GetTracks():
        if t.GetNetname() not in power_nets:continue
        if isinstance(t,k.PCB_VIA):via_counts[t.GetNetname()]+=1;continue
        length=k.ToMM(t.GetLength());width=k.ToMM(t.GetWidth())
        # Nominal 35um copper, 20C rho. All track resistances summed deliberately includes spurs
        # and both paired-pin necks: conservative series-track estimate; zones/pad areas omitted.
        resistance=1.724e-8*(length/1000)/((width/1000)*35e-6)
        sums[t.GetNetname()]+=resistance
        copper.append(dict(net=t.GetNetname(),length_mm=length,width_mm=width,R20_ohm=resistance))
    out=dict(revision='V34',source_sha256={str(p):digest(p) for p in [D/'wp10_system.xml',D/'wp10_aux_protection.kicad_pcb',D/'wp10_main_input.kicad_pcb']},
      parent_refs=len(old),current_refs=len(comp),parent_pin_records=len(on),current_pin_records=len(nodes),
      missing_parent_refs=sorted(set(old)-set(comp)),added_refs=sorted(set(comp)-set(old)),parent_net_delta=delta,parent_value_delta=value_delta,
      aux_electrical_footprints=len(refs),aux_board_only_mounting_footprints=4,aux_numbered_pads=len(pads),pad_net_mismatch=mismatch,pads=pads,
      track_series_R20_ohm=dict(sums),track_series_total_R20_ohm=sum(sums.values()),power_net_via_counts=dict(via_counts),copper_tracks=copper,
      copper_model='35um nominal copper; sum of all power-net tracks including spurs. Not measured impedance; zones and pad spreading omitted. Via/contact resistances require separate allocation.',
      actual_mated_connector_resistance_upper_bound_ohm=None,qualification=False)
    (R/'NATIVE_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({q:out[q] for q in ['parent_refs','current_refs','parent_pin_records','current_pin_records','parent_net_delta','parent_value_delta','aux_electrical_footprints','aux_numbered_pads','pad_net_mismatch','track_series_R20_ohm','power_net_via_counts']}))
if __name__=='__main__':main()
