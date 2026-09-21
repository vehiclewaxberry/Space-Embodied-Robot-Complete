"""Apply the geometry-checked inhibit via escape and retain its rejected predecessor."""
from pathlib import Path
import json,hashlib,shutil
import pcbnew as k
A=Path(__file__).resolve().parents[1];L=A/'results/stop_v36/pcb/layout_20260916';p=A/'ecad/revisions/v36/wp10_stop_control.kicad_pcb'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((L/'return_repair_c/ESCAPE_PLAN.json').read_text());assert sha(p)==plan['source_board_sha256']
out=L/'return_repair_d';out.mkdir(exist_ok=True);assert not (out/'ESCAPE_APPLIED.json').exists()
shutil.copy2(p,out/'REJECTED_RETURN_C.kicad_pcb');b=k.LoadBoard(str(p));count=0
old=(69.487,43.05);new=plan['selected'][1]
def match(v):return abs(k.ToMM(v.x)-old[0])<1e-6 and abs(k.ToMM(v.y)-old[1])<1e-6
for t in b.GetTracks():
    if t.GetNetname()!='/Actual watchdog and contactor driver/RUN_INHIBIT_5V':continue
    if isinstance(t,k.PCB_VIA):
        if match(t.GetPosition()):t.SetPosition(k.VECTOR2I(*(k.FromMM(v) for v in new)));count+=1
    else:
        for get,set_ in [(t.GetStart,t.SetStart),(t.GetEnd,t.SetEnd)]:
            if match(get()):set_(k.VECTOR2I(*(k.FromMM(v) for v in new)));count+=1
assert count==3
k.SaveBoard(str(p),b)
(out/'ESCAPE_APPLIED.json').write_text(json.dumps(dict(board_before_sha256=plan['source_board_sha256'],board_after_sha256=sha(p),
    plan_sha256=sha(L/'return_repair_c/ESCAPE_PLAN.json'),moved=count,whole_design_complete=False),indent=2)+'\n')
print(json.dumps(dict(board_sha256=sha(p),moved=count)))
