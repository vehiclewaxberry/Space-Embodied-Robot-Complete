"""Import the saved routing session transactionally and check unchanged physical nets."""
from pathlib import Path
import hashlib,json,collections,shutil,xml.etree.ElementTree as ET
import pcbnew as k
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';P=A/'results/stop_v36/pcb'
L=P/'layout_20260916';N=P/'thermal_filter_20260916/native_20260916_a'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def state(b):
    footprints={}
    for f in b.GetFootprints():
        pads=sorted((p.GetNumber(),p.GetPosition().x,p.GetPosition().y,p.GetNetname(),p.GetSize().x,p.GetSize().y) for p in f.Pads())
        footprints[f.GetReference()]=dict(position=[f.GetPosition().x,f.GetPosition().y],angle=f.GetOrientationDegrees(),pads=pads,path=f.GetPath().AsString())
    edges=sorted((int(x.GetShape()),x.GetStart().x,x.GetStart().y,x.GetEnd().x,x.GetEnd().y) for x in b.GetDrawings() if x.GetLayer()==k.Edge_Cuts)
    return dict(footprints=footprints,edges=edges,layers=b.GetCopperLayerCount(),thickness=b.GetDesignSettings().GetBoardThickness())

def main():
    out=L/'routing_import_a';out.mkdir(exist_ok=True)
    record=out/'IMPORT_VERIFICATION.json';assert not record.exists(),'Preserve completed checkpoint'
    target=D/'wp10_stop_control.kicad_pcb';pro=target.with_suffix('.kicad_pro');ses=L/'STOP_ROUTED_A.ses'
    assert sha(target)==json.loads((L/'SILKSCREEN_PLACEMENT.json').read_text())['board_after_sha256']
    assert sha(L/'STOP_ROUTING.dsn')==json.loads((L/'ROUTING_ALLOCATION.json').read_text())['dsn_sha256']
    check=json.loads((N/'VERIFICATION.json').read_text())
    assert all(sha(p)==h for field in ('source_bindings','evidence_bindings') for p,h in check[field].items())
    b=k.LoadBoard(str(target));before=state(b);assert len(list(b.GetTracks()))==0
    assert len(before['footprints'])==107
    backups=[(target,out/'BEFORE_IMPORT.kicad_pcb'),(pro,out/'BEFORE_IMPORT.kicad_pro')]
    for src,dst in backups:
        if dst.exists():assert sha(src)==sha(dst)
        else:shutil.copy2(src,dst)
    source_bindings={str(p):sha(p) for p in [target,pro,ses,L/'STOP_ROUTING.dsn',N/'wp10_system.xml',N/'VERIFICATION.json',P/'PHYSICAL_PARTS.json',Path(__file__)]}
    assert k.ImportSpecctraSES(b,str(ses)),'Native SES import failed'
    assert state(b)==before,'SES changed components, pads, nets or board shape'
    candidate=out/'ROUTED_IMPORT_A.kicad_pcb';k.SaveBoard(str(candidate),b)
    cold=k.LoadBoard(str(candidate));assert state(cold)==before,'Saved board structural mismatch'
    parts=json.loads((P/'PHYSICAL_PARTS.json').read_text())
    rt=ET.parse(N/'wp10_system.xml').getroot()
    pn={(n.get('ref'),n.get('pin')):net.get('name') for net in rt.findall('./nets/net') for n in net.findall('node')}
    bound=[]
    for f in cold.GetFootprints():
        if f.GetReference() not in parts:continue
        for p in f.Pads():
            n=p.GetNumber()
            if n and n!='MP':
                assert p.GetNetname()==pn[f.GetReference(),n]
                bound.append([f.GetReference(),n,p.GetNetname()])
    tracks=list(cold.GetTracks());counts=collections.Counter('via' if isinstance(t,k.PCB_VIA) else 'segment' for t in tracks)
    assert counts['segment']>0
    widths=collections.defaultdict(set)
    for t in tracks:
        if not isinstance(t,k.PCB_VIA):widths[t.GetNetname()].add(round(k.ToMM(t.GetWidth()),6))
    assert sha(target)==source_bindings[str(target)]
    shutil.copy2(candidate,target)
    result=dict(status='SES_IMPORTED__PHYSICAL_PAD_NET_PARITY_PASS__POST_ROUTE_DRC_PENDING',board=str(target),board_sha256=sha(target),
        footprints=107,electrical_footprints=103,holes=4,tracks=dict(counts),widths_mm={n:sorted(s) for n,s in widths.items()},
        original_positions_pads_nets_board_shape_unchanged=True,pad_net_bindings=bound,source_bindings=source_bindings,
        manufacturing_release=False,geometry_installed_in873host=False,whole_design_complete=False)
    record.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:result[key] for key in ['status','board_sha256','footprints','tracks']}))
if __name__=='__main__':main()
