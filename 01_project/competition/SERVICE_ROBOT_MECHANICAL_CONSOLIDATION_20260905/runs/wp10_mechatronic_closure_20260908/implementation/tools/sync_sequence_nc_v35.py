"""Rename only unrouted, explicitly no-connect pad nets after pin-label cleanup."""
from pathlib import Path
import json
import pcbnew as k
from erc_source_contract import physical_netlist
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v35'
_,pins=physical_netlist(D/'wp10_system.xml')
b=k.LoadBoard(str(D/'wp10_aux_protection.kicad_pcb'))
changed=[]
for f in b.GetFootprints():
    for p in f.Pads():
        key=(f.GetReference(),p.GetNumber())
        if key not in pins: continue
        desired,kind=pins[key]
        old=p.GetNetname()
        if old==desired: continue
        assert key in [('U208','10'),('U209','6')],key
        assert 'no_connect' in kind and old.startswith('unconnected-') and desired.startswith('unconnected-')
        assert not any(t.GetNetname()==old for t in b.GetTracks())
        assert sum(q.GetNetname()==old for g in b.GetFootprints() for q in g.Pads())==1
        net=k.NETINFO_ITEM(b,desired); b.Add(net); p.SetNet(net)
        changed.append(dict(ref=key[0],pin=key[1],previous=old,current=desired))
assert len(changed) in [0,2],changed
if changed:k.SaveBoard(str(D/'wp10_aux_protection.kicad_pcb'),b)
(A/'results/aux_v35/NC_LABEL_SYNC.json').write_text(json.dumps(changed,indent=2)+'\n',encoding='utf-8')
print(json.dumps(changed))
