"""Canonical source geometry and explicit S-mm transforms for R4."""
from pathlib import Path
import json,hashlib,importlib.util,numpy as np
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace
from OCP.gp import gp_Pnt,gp_Vec

D=Path(__file__).resolve().parents[1];ROOT=D.parents[1]
R1=D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919';R2=D.parent/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919';R3=D.parent/'SERVICE_STAR_B601_INTERFACE_R3_20260920'
spec=importlib.util.spec_from_file_location('sealed_r2_geometry',R2/'tools/build_internal_passage.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
read,write,sha,load,moved=g.read,g.write,g.sha,g.load,g.moved
box,cyl,cut,union,common,distance=g.block,g.cylinder,g.cut,g.union,g.common,g.distance
I=np.eye(4).tolist(); RAW={};WORLD={};SOURCE_CHECKS={}
def compound(parts):
    b=BRep_Builder();c=TopoDS_Compound();b.MakeCompound(c)
    for p in parts:b.Add(c,p)
    return c
def source(r):
    p=r['step_path'];T=np.array(r['T_S_local']);key=(p,tuple(T.flat))
    if key not in WORLD:
        if p not in RAW:
            assert sha(p)==r['source_sha256'];RAW[p]=load(p);SOURCE_CHECKS[p]=r['source_sha256']
        WORLD[key]=moved(RAW[p],T)
    return WORLD[key]
def state_rows():
    m=read(R1/'inputs/NEUTRAL_SOURCE_MAP.json');r2={r['id']:r for r in read(R2/'inputs/NATIVE_ROUTE_PLAN.json')['parts']};r3=read(R3/'inputs/NATIVE_ASSEMBLY_PLAN.json')['part']
    result={}
    for st,s in m['states'].items():
        rr=[dict(r,group=gr['id']) for gr in m['groups'] if gr['id'] in s['groups'] for r in gr['rows']]
        result[st]=[dict(r2.get(r['id'],r3 if r['id']==r3['id'] else r),group=r['group']) for r in rr]
    # Match the final native assembly without ever applying native transforms to historical world STEPs.
    native=read(R3/'inputs/NATIVE_ASSEMBLY_PLAN.json');lookup={r['id']:r for r in result['service']}
    for r in native['expected_leaves']:
        c=lookup[r['id']];assert Path(c['native_path']).resolve()==Path(r['native_path']).resolve()
        assert np.max(np.abs(np.array(c['T_S_local'])-r['T_S_local']))<1e-10
    return result
BOUNDS=read(R2/'inputs/SOURCE_LOCAL_BOUNDS.json')['bounds_by_path']
def world_bounds(r):
    p=r['step_path']
    if p not in BOUNDS:
        if p not in RAW:assert sha(p)==r['source_sha256'];RAW[p]=load(p);SOURCE_CHECKS[p]=r['source_sha256']
        BOUNDS[p]=g.precise_bounds(RAW[p])
    a,z=map(np.array,BOUNDS[p]);T=np.array(r['T_S_local']);v=np.array([[x,y,t] for x in [a[0],z[0]] for y in [a[1],z[1]] for t in [a[2],z[2]]])@T[:3,:3].T+T[:3,3]
    return v.min(0),v.max(0)
def candidates(shape,rows,margin=0):
    a,z=map(np.array,g.precise_bounds(shape))
    for r in rows:
        lo,hi=world_bounds(r)
        if np.all(lo<=z+margin)&np.all(hi>=a-margin):yield r
def emit(ident,shape,role,**kw):
    p=D/'cad'/f'{ident}.step';fact=g.dump(shape,p)
    return dict(id=ident,step_path=str(p),source_sha256=fact['sha256'],native_path=str(D/'native'/f'{ident}.SLDPRT'),T_S_local=I,
        expected_solids=fact['solids'],expected_sheets=0,expected_volume_mm3=fact['volume_mm3'],
        expected_local_bbox_mm={'min_mm':fact['bounds_mm'][0],'max_mm':fact['bounds_mm'][1]},representation_role=role,**kw)
def hex_nut(x,y,z,h,af,bore=3.0):
    poly=BRepBuilderAPI_MakePolygon();rr=af/np.sqrt(3)
    for a in np.linspace(0,2*np.pi,6,endpoint=False):poly.Add(gp_Pnt(x+rr*np.cos(a),y+rr*np.sin(a),z))
    poly.Close();face=BRepBuilderAPI_MakeFace(poly.Wire()).Face();s=BRepPrimAPI_MakePrism(face,gp_Vec(0,0,h)).Shape()
    return cut(s,cyl(bore/2,z-1,z+h+1,x,y))
