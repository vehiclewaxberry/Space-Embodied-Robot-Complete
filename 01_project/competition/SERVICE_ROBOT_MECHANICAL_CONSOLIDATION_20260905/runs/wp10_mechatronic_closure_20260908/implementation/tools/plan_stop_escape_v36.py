"""Conservative local two-layer clearance search; native DRC remains authoritative."""
from pathlib import Path
import json,math
A=Path(__file__).resolve().parents[1];L=A/'results/stop_v36/pcb/layout_20260916'
d=json.loads((L/'return_repair_c/COPPER_C.json').read_text());net='/Actual watchdog and contactor driver/RUN_INHIBIT_5V'
def dist(p,q):return math.hypot(p[0]-q[0],p[1]-q[1])
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def pd(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
    return dist(p,(a[0]+t*dx,a[1]+t*dy))
def sd(a,b,c,e):
    if cross(a,b,c)*cross(a,b,e)<=0 and cross(c,e,a)*cross(c,e,b)<=0 and max(min(a[0],b[0]),min(c[0],e[0]))<=min(max(a[0],b[0]),max(c[0],e[0])) and max(min(a[1],b[1]),min(c[1],e[1]))<=min(max(a[1],b[1]),max(c[1],e[1])):return 0
    return min(pd(a,c,e),pd(b,c,e),pd(c,a,b),pd(e,a,b))
tracks=[t for t in d['tracks'] if t['net']!=net];pads=[p for p in d['pads'] if p['net']!=net]
def safe(a,b,radius,layers):
    for t in tracks:
        if t['type']!='via' and t['layer'] not in layers:continue
        if sd(a,b,t['start'],t['end'])<radius+t['width_mm']/2+.16:return False
    for p in pads:
        if not set(p['layers'])&set(layers):continue
        cx,cy=p['position'];w,h=p['size'];an=math.radians(-p['angle']);ca,sa=math.cos(an),math.sin(an)
        poly=[(cx+x*ca-y*sa,cy+x*sa+y*ca) for x,y in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]]
        def interior(q):return all(cross(poly[i],poly[(i+1)%4],q)>=-1e-10 for i in range(4))
        if interior(a) or interior(b):return False
        if min(sd(a,b,poly[i],poly[(i+1)%4]) for i in range(4))<radius+.16:return False
    return True
origin=(69.487,43.511);goal=(71.75,45.313);solutions=[]
for ix in range(680,706):
    for iy in range(415,445):
        v=(ix/10,iy/10)
        if safe(v,v,.3,['F.Cu','B.Cu']) and safe(origin,v,.125,['F.Cu']) and safe(v,goal,.125,['B.Cu']):solutions.append((dist(origin,v)+dist(v,goal),v))
solutions.sort();assert solutions,'No safe local escape found'
result=dict(source_board_sha256=d['board_sha256'],selected=solutions[0],next_best=solutions[1:5],clearance_screen_mm=.16,via_diameter_mm=.6,
    approximation='Conservative rectangular pad envelopes; existing copper centerlines and widths; native DRC must follow',origin=origin,goal=goal)
(L/'return_repair_c/ESCAPE_PLAN.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
