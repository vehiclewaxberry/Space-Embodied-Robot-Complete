"""Move readable references without changing pads, nets or component placements."""
from pathlib import Path
import hashlib,json,math
import pcbnew as k
from build_stop_board_v36 import mm,A,D,P,R
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rect(item):
    z=item.GetBoundingBox();return [k.ToMM(z.GetX()),k.ToMM(z.GetY()),k.ToMM(z.GetRight()),k.ToMM(z.GetBottom())]
def hit(a,b,m=.15):return a[0]<b[2]+m and b[0]<a[2]+m and a[1]<b[3]+m and b[1]<a[3]+m
def main():
    path=D/'wp10_stop_control.kicad_pcb';b=k.LoadBoard(str(path));before=sha(path)
    backup=R/'STOP_BEFORE_SILK.kicad_pcb'
    if backup.exists():assert sha(backup)==before,'Existing board differs from saved pre-silk checkpoint'
    else:backup.write_bytes(path.read_bytes())
    obstacles=[];refs=[];fixed=[]
    fpstate={f.GetReference():[f.GetPosition().x,f.GetPosition().y,f.GetOrientationDegrees()] for f in b.GetFootprints()}
    for f in b.GetFootprints():
        obstacles.extend(rect(p) for p in f.Pads() if p.IsOnLayer(k.F_Mask))
        obstacles.extend(rect(g) for g in f.GraphicalItems() if g.GetLayer()==k.F_SilkS)
        if not f.GetAttributes()&k.FP_BOARD_ONLY:refs.append((f.GetReference(),f.Reference(),[k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y)]))
    for item in b.GetDrawings():
        if isinstance(item,k.PCB_TEXT) and item.GetLayer()==k.F_SilkS:
            refs.append(('BOARD_TEXT',item,[k.ToMM(item.GetPosition().x),k.ToMM(item.GetPosition().y)]))
    placed={};unplaced=[]
    for i,(ref,text,origin) in enumerate(refs):
        text.SetTextSize(mm(.8,.8));text.SetTextThickness(k.FromMM(.12));text.SetTextAngleDegrees(0)
        options=[]
        for dx in range(-18,19):
            for dy in range(-18,19):options.append((abs(dx)+abs(dy),origin[0]+dx*.5,origin[1]+dy*.5))
        if ref=='BOARD_TEXT':
            options=[(abs(x*.5-origin[0])+abs(y*.5-origin[1]),x*.5,y*.5) for x in range(12,169) for y in range(2,139)]
        options.sort();found=None
        for _,x,y in options:
            text.SetPosition(mm(x,y));q=rect(text)
            if q[0]<.4 or q[1]<.4 or q[2]>89.6 or q[3]>69.6:continue
            if any(hit(q,o) for o in obstacles+fixed):continue
            found=[x,y];fixed.append(q);break
        if found is None:unplaced.append(ref)
        else:placed[ref if ref!='BOARD_TEXT' else ref+str(i)]=found
    assert not unplaced,('Need manual reference placement',unplaced)
    assert fpstate=={f.GetReference():[f.GetPosition().x,f.GetPosition().y,f.GetOrientationDegrees()] for f in b.GetFootprints()}
    k.SaveBoard(str(path),b)
    (R/'SILKSCREEN_PLACEMENT.json').write_text(json.dumps(dict(board_before_sha256=before,board_after_sha256=sha(path),reference_count=len(refs),font_height_mm=.8,component_positions_unchanged=True,positions=placed,DRC_recheck_required=True),indent=2)+'\n')
    print(json.dumps(dict(reference_count=len(refs),height_mm=.8,positions_unchanged=True)))
if __name__=='__main__':main()
