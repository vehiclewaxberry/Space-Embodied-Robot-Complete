"""Fix real DRC counterexamples without weakening clearance rules."""
from pathlib import Path
import hashlib,json,shutil
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';L=A/'results/stop_v36/pcb/layout_20260916'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def key(p):return round(k.ToMM(p.x),4),round(k.ToMM(p.y),4)
def main():
    p=D/'wp10_stop_control.kicad_pcb';r=L/'return_repair_b';r.mkdir(exist_ok=True)
    assert not (r/'RETURN_CORRECTION.json').exists()
    expected=json.loads((L/'return_repair_a/RETURN_REPAIR.json').read_text())['board_after_sha256'];assert sha(p)==expected
    shutil.copy2(p,r/'REJECTED_RETURN_A.kicad_pcb')
    b=k.LoadBoard(str(p));moves={(.8,y):(.95,y) for y in [41.875,44.375,46.875]}
    moves.update({(67.3,47):(69.6,47),(67.3,48.8873):(69.6,48.8873)})
    count=0
    for t in b.GetTracks():
        if t.GetNetname()!='WP10_ARM_RETURN':continue
        if isinstance(t,k.PCB_VIA):
            q=key(t.GetPosition())
            if q in moves:t.SetPosition(k.VECTOR2I(*(k.FromMM(v) for v in moves[q])));count+=1
        else:
            for getter,setter in [(t.GetStart,t.SetStart),(t.GetEnd,t.SetEnd)]:
                q=key(getter())
                if q in moves:setter(k.VECTOR2I(*(k.FromMM(v) for v in moves[q])));count+=1
    assert count==12,count
    k.SaveBoard(str(p),b)
    (r/'RETURN_CORRECTION.json').write_text(json.dumps(dict(before_sha256=expected,after_sha256=sha(p),
        reason='Three via-to-edge violations and a5V-to-return short in first manual escape. Preserve rejected file; move only new escape geometry.',
        moved_endpoints=count,moves=[dict(before=x,after=y) for x,y in moves.items()],rules_unchanged=True,whole_design_complete=False),indent=2)+'\n')
    print(json.dumps(dict(moved=count,board_sha256=sha(p))))
if __name__=='__main__':main()
