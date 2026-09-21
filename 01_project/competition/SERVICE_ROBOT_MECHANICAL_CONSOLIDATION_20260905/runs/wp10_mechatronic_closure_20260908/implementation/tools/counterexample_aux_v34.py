"""Create a deliberately shorted copy; never change the active board."""
from pathlib import Path
import hashlib,json,shutil
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v34';R=A/'results/aux_v34'
P=D/'wp10_aux_protection.kicad_pcb'
def main():
    before=hashlib.sha256(P.read_bytes()).hexdigest();b=k.LoadBoard(str(P))
    u=next(f for f in b.GetFootprints() if f.GetReference()=='U207')
    ep=next(p for p in u.Pads() if p.GetNumber()=='17');gnd=next(p for p in u.Pads() if p.GetNumber()=='9')
    t=k.PCB_TRACK(b);t.SetStart(ep.GetPosition());t.SetEnd(gnd.GetPosition());t.SetLayer(k.F_Cu);t.SetWidth(k.FromMM(.5));t.SetNet(ep.GetNet());b.Add(t)
    dest=R/'counterexamples';dest.mkdir(exist_ok=True)
    q=dest/'AUX_RTN_GND_SHORT.kicad_pcb';k.SaveBoard(str(q),b)
    shutil.copy2(P.with_suffix('.kicad_pro'),q.with_suffix('.kicad_pro'))
    assert hashlib.sha256(P.read_bytes()).hexdigest()==before
    (dest/'INJECTION.json').write_text(json.dumps(dict(active_board_sha256=before,active_board_unchanged=True,
      negative_board=str(q),injected='0.5mm F.Cu track connecting RTN exposed pad to primary GND pin9',
      expected_native_failure='shorting or copper-clearance violation between distinct nets'),indent=2)+'\n')
    print('Negative copy created; active source unchanged')
if __name__=='__main__':main()
