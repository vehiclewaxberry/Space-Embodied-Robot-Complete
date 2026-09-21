"""Serial source-STEP tessellation for local thermal obstruction screening."""
from pathlib import Path
import json,hashlib,gc
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local_triangles(path):
    r=STEPControl_Reader();assert int(r.ReadFile(path))==1;r.TransferRoots();s=r.OneShape()
    mesh=BRepMesh_IncrementalMesh(s,.15,False,.25,False);mesh.Perform();assert mesh.IsDone()
    triangles=[];exp=TopExp_Explorer(s,TopAbs_FACE)
    while exp.More():
        face=TopoDS.Face_s(exp.Current());loc=TopLoc_Location();tr=BRep_Tool.Triangulation_s(face,loc)
        if tr is not None:
            pts=np.array([tr.Node(i).Transformed(loc.Transformation()).Coord() for i in range(1,tr.NbNodes()+1)])
            for i in range(1,tr.NbTriangles()+1):triangles.append(pts[np.array(tr.Triangle(i).Get())-1])
        exp.Next()
    assert triangles,path
    return np.array(triangles)
def main():
    bounds=json.loads((A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json').read_text());selected={};cache={};records={}
    assert bounds['source_plan_sha256']==sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json'),'Stale obstacle transforms; rebuild bounds after source changes'
    # Both current side walls plus proposed fixed end/bottom exterior planes.
    # Probe planes select possible obstacles; they are not emitted CAD surfaces.
    probes=[(1,-1,-113.15),(1,1,113.15),(0,1,185.),(0,-1,-189.),(2,-1,-114.),(2,1,114.)]
    for state,rows in bounds['states'].items():
        selected[state]=[r for r in rows if not r['is_ground_only'] and any(max(s*(r['bbox_S_mm'][k]-v),s*(r['bbox_S_mm'][k+3]-v))>1e-5 for k,s,v in probes)]
        for row in selected[state]:
            key=row['source_sha256']
            if key not in cache:
                assert sha(row['step_path'])==key;cache[key]=local_triangles(row['step_path']);gc.collect()
    for state,rows in selected.items():
        tris=[];owners=[]
        for i,row in enumerate(rows):
            T=np.array(row['T_S_step']);local=cache[row['source_sha256']];world=local@T[:3,:3].T+T[:3,3]
            tris.append(world);owners.append(np.full(len(world),i,dtype=np.int32))
        tris=np.concatenate(tris);owners=np.concatenate(owners)
        path=A/'thermal'/f'RADIATOR_OBSTACLES_{state.upper()}.npz';np.savez_compressed(path,triangles=tris,owners=owners)
        records[state]=dict(rows=rows,triangle_count=len(tris),path=path.relative_to(A).as_posix(),sha256=sha(path))
    out=dict(schema='WP10_STEP_OBSTRUCTION_MESH_V1',bounds_input_sha256=sha(A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json'),
       source_plan_sha256=bounds['source_plan_sha256'],mesh_source_sha256=sha(__file__),linear_deflection_mm=.15,angular_deflection_rad=.25,
       unique_STEP_meshes=len(cache),states=records,
       physical_geometry_role='Current STEP representation; proxies/function envelopes separately classified; noas-built or radiometric-temperature claim',
       nominal_tessellation_error_not_rigorous_bound=True)
    (A/'thermal/RADIATOR_MESH_MANIFEST.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(dict(unique_sources=len(cache),triangles={s:r['triangle_count'] for s,r in records.items()})))
if __name__=='__main__':main()
