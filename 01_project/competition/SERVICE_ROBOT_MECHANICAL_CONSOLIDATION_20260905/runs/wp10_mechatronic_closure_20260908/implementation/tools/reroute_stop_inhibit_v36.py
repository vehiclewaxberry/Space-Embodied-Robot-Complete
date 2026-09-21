"""Relieve the driver ground escape by moving its adjacent inhibit branch to B.Cu."""
from pathlib import Path
import hashlib,json,shutil
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';L=A/'results/stop_v36/pcb/layout_20260916'
def mm(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=D/'wp10_stop_control.kicad_pcb';out=L/'return_repair_c';out.mkdir(exist_ok=True)
    assert not (out/'INHIBIT_REROUTE.json').exists()
    expected=json.loads((L/'return_repair_b/RETURN_CORRECTION.json').read_text())['after_sha256'];assert sha(p)==expected
    shutil.copy2(p,out/'REJECTED_RETURN_B.kicad_pcb');b=k.LoadBoard(str(p))
    net=b.GetNetsByName()['/Actual watchdog and contactor driver/RUN_INHIBIT_5V']
    edits={'eed0a95f-54b3-41e0-89f1-e0281fd8ccc5':[(69.487,43.05),(71.75,45.313)],
           '8e2e7e4d-f010-4bc2-a3ce-a1cca5992483':[(71.75,45.313),(71.75,48.15)]}
    count=0
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in edits:
            a,z=edits[t.m_Uuid.AsString()];t.SetStart(mm(*a));t.SetEnd(mm(*z));t.SetLayer(k.B_Cu);count+=1
    assert count==2
    for a,z in [[(69.487,43.511),(69.487,43.05)],[(70.6375,47.95),(71.75,48.15)]]:
        t=k.PCB_TRACK(b);t.SetStart(mm(*a));t.SetEnd(mm(*z));t.SetLayer(k.F_Cu);t.SetWidth(k.FromMM(.25));t.SetNet(net);b.Add(t)
    for x,y in [(69.487,43.05),(71.75,48.15)]:
        v=k.PCB_VIA(b);v.SetPosition(mm(x,y));v.SetWidth(k.FromMM(.6));v.SetDrill(k.FromMM(.3));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net);b.Add(v)
    k.SaveBoard(str(p),b)
    (out/'INHIBIT_REROUTE.json').write_text(json.dumps(dict(before_sha256=expected,after_sha256=sha(p),moved_existing_track_uuids=list(edits),
        added_vias=2,added_segments=2,reason='Physical separation from U112 ground escape; preserve electrical net and all footprints',rules_unchanged=True,whole_design_complete=False),indent=2)+'\n')
    print(json.dumps(dict(board_sha256=sha(p))))
if __name__=='__main__':main()
