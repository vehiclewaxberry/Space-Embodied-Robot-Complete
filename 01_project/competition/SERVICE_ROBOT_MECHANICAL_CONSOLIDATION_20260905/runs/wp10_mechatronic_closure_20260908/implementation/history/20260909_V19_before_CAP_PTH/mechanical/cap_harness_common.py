"""Source-defined stranded-wire envelopes; resistance uses manufacturer R/m."""
from pathlib import Path
import json
from build123d import Edge,Wire,Plane,Circle,sweep,Compound,Color
from cap_harness_path import fillet_path,slice_path,point,tangent
A=Path(__file__).resolve().parents[1]
def pathwire(segs):
 edges=[]
 for s in segs:
  edges.append(Edge.make_line(s['start'],s['end']) if s['kind']=='line' else Edge.make_three_point_arc(s['start'],point(s,.5),s['end']))
 return Wire(edges)
def tube(segs,outer,inner=0):
 plane=Plane(origin=segs[0]['start'],z_dir=tangent(segs[0],0));profile=Circle(outer/2)
 if inner:profile=profile-Circle(inner/2)
 return sweep(plane*profile,path=pathwire(segs))
def make(name):
 c=json.loads((A/'power/CAP_HARNESS_DEFINITION_V19.json').read_text());w=next(x for x in c['wires'] if x['id']=='C203_W_'+name)
 p=fillet_path(w['sharp_vertices_S_mm'],w['bend_radius_mm']);L=sum(s['length'] for s in p)
 core=tube(p,c['wire']['max_bare_D_mm']);core.label=w['id']+'__STRANDED_OUTER_ENVELOPE';core.color=Color(.7,.45,.22)
 insulated=slice_path(p,w['strip_start_mm'],L-w['strip_end_mm'])
 jacket=tube(insulated,c['wire']['max_insulation_D_mm'],c['wire']['max_bare_D_mm']);jacket.label=w['id']+'__ETFE_WHITE_ID_'+name;jacket.color=Color(.84,.85,.84)
 # Actual -9 insulation is white on both conductors; no invented red/black MPN.
 out=Compound(children=[core,jacket]);out.label=w['id']+'__NOMINAL_ROUTE_UNQUALIFIED_RETENTION';return out
