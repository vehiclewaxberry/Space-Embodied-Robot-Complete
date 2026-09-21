"""Export physical copper and pad geometry for low-memory independent route review."""
from pathlib import Path
import sys,json,hashlib
import pcbnew as k
A=Path(__file__).resolve().parents[1];target=A/'ecad/revisions/v36/wp10_stop_control.kicad_pcb'
def point(p):return [round(k.ToMM(p.x),7),round(k.ToMM(p.y),7)]
b=k.LoadBoard(str(target));items=[];pads=[]
for t in b.GetTracks():
    via=isinstance(t,k.PCB_VIA)
    items.append(dict(uuid=t.m_Uuid.AsString(),net=t.GetNetname(),type='via' if via else 'segment',
        start=point(t.GetStart()),end=point(t.GetEnd()),layer=b.GetLayerName(t.GetLayer()),
        width_mm=k.ToMM(t.GetWidth(k.F_Cu) if via else t.GetWidth())))
for f in b.GetFootprints():
    for p in f.Pads():
        pads.append(dict(ref=f.GetReference(),pin=p.GetNumber(),net=p.GetNetname(),position=point(p.GetPosition()),
            size=point(p.GetSize()),angle=p.GetOrientationDegrees(),through=p.GetAttribute()==k.PAD_ATTRIB_PTH,
            layers=[b.GetLayerName(x) for x in [k.F_Cu,k.B_Cu] if p.IsOnLayer(x)]))
out=Path(sys.argv[1]);out.write_text(json.dumps(dict(board=str(target),board_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),tracks=items,pads=pads),indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(output=str(out),tracks=len(items),pads=len(pads))))
