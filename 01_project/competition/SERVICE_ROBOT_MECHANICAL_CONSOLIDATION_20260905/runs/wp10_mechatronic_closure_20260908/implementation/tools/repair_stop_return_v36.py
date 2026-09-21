"""Add explicit return bridges to three unrouted pads; preserve first-route evidence."""
from pathlib import Path
import json,hashlib,shutil
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';L=A/'results/stop_v36/pcb/layout_20260916'
def mm(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=D/'wp10_stop_control.kicad_pcb';backup=L/'return_repair_a';backup.mkdir(exist_ok=True)
    expected=json.loads((L/'routing_import_a/IMPORT_VERIFICATION.json').read_text())['board_sha256'];assert sha(p)==expected
    shutil.copy2(p,backup/'BEFORE_RETURN_REPAIR.kicad_pcb')
    b=k.LoadBoard(str(p));net=b.GetNetsByName()['WP10_ARM_RETURN'];changes=[]
    def track(points,layer,width=.4):
        for start,end in zip(points,points[1:]):
            t=k.PCB_TRACK(b);t.SetStart(mm(*start));t.SetEnd(mm(*end));t.SetWidth(k.FromMM(width));t.SetLayer(layer);t.SetNet(net);b.Add(t)
            changes.append(dict(type='track',start=start,end=end,width_mm=width,layer=b.GetLayerName(layer)))
    def via(x,y):
        v=k.PCB_VIA(b);v.SetPosition(mm(x,y));v.SetWidth(k.FromMM(.8));v.SetDrill(k.FromMM(.4));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net);b.Add(v)
        changes.append(dict(type='via',position=[x,y],diameter_mm=.8,drill_mm=.4))
    # All three connector return contacts remain independent pairs in the external harness.
    # On the board their return bridges cross behind the interleaved sensor contacts.
    for y in [41.875,44.375,46.875]:
        track([(1.875,y),(.8,y)],k.F_Cu,.25);via(.8,y)
    track([(.8,41.875),(.8,46.875)],k.B_Cu)
    # Ground pin escapes directly to the already routed local source/capacitor return.
    track([(68.3625,47),(67.3,47)],k.F_Cu,.4);via(67.3,47)
    track([(67.3,47),(67.3,48.8873)],k.B_Cu,.4)
    k.SaveBoard(str(p),b)
    result=dict(board_before_sha256=expected,board_after_sha256=sha(p),added=changes,source_bindings={str(Path(__file__)):sha(Path(__file__))},
        post_repair_DRC_pending=True,whole_design_complete=False)
    (backup/'RETURN_REPAIR.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(added=len(changes),board_sha256=sha(p))))
if __name__=='__main__':main()
