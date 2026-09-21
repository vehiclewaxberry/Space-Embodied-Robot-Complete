"""Read-only plan for bounded MCP source rewiring; no source mutations."""
from pathlib import Path
import json, math
from erc_source_contract import parse,children,val,properties
A=Path(__file__).resolve().parents[1];D=A/'ecad/revisions/v36';R=A/'results/stop_v36'
def pin_xy(t,ref,pn):
    s=next(s for s in children(t,'symbol') if properties(s)['Reference']==ref)
    lid=val(children(s,'lib_id')[0][1]);lib=next(x for b in children(t,'lib_symbols') for x in children(b,'symbol') if val(x[1])==lid)
    p=next(p for u in children(lib,'symbol') for p in children(u,'pin') if val(children(p,'number')[0][1])==str(pn))
    sx,sy,rot=map(float,children(s,'at')[0][1:4]);assert rot==0
    px,py=map(float,children(p,'at')[0][1:3]);return round(sx+px,6),round(sy-py,6)
def xy(n):return tuple(round(float(v),6) for v in children(n,'at')[0][1:3])
changes={'U112':{'1':'STOP_5V','3':'WP10_BRAKE_THERMAL_FAULT_N','4':'RUN_INHIBIT_5V'},'U119':{'1':None,'2':'RUN_DRIVE','4':'RUN_INHIBIT_5V'},'R111':{'1':'RUN_LATCH'},'U102':{'3':'STOP_5V','6':'STOP_5V'},'C111':{'1':'STOP_5V'}}
if __name__=='__main__':
    t=parse((D/'wp10_stop_detail.kicad_sch').read_text());ops=[]
    for ref,pins in changes.items():
        for pn,new in pins.items():
            start=pin_xy(t,ref,pn)
            def points(w):return [tuple(round(float(v),6) for v in q[1:3]) for pts in children(w,'pts') for q in children(pts,'xy')]
            wires=[w for w in children(t,'wire') if len(points(w))==2 and points(w)[0][1]==points(w)[1][1]==start[1] and min(q[0] for q in points(w))<=start[0]<=max(q[0] for q in points(w))]
            assert len(wires)==1,(ref,pn,start,len(wires))
            end=max(points(wires[0]))
            gs=[g for typ in ['label','global_label'] for g in children(t,typ) if xy(g)==end];assert len(gs)==1,(ref,pn,start,gs)
            ops.append(dict(reference=ref,pin=pn,start=start,wire_start=min(points(wires[0])),end=end,old=val(gs[0][1]),new=new,new_type='global_label' if new and new.startswith('WP10_') else 'label'))
    (R/'MCP_REWIRE_INTENT.json').write_text(json.dumps(ops,indent=2)+'\n');print(json.dumps(ops))
