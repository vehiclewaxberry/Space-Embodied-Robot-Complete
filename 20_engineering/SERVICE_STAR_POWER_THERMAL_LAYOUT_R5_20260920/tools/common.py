"""R5 geometry is derived from final R4 canonical geometry, never double-transformed."""
from pathlib import Path
import sys,importlib.util,numpy as np
D=Path(__file__).resolve().parents[1];ROOT=D.parents[1];R4=D.parent/'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920'
spec=importlib.util.spec_from_file_location('r4_geometry_source',R4/'tools/geometry.py');r4=importlib.util.module_from_spec(spec);spec.loader.exec_module(r4)
g=r4.g;read,write,sha,load,moved=r4.read,r4.write,r4.sha,r4.load,r4.moved
box,cyl,cut,union,common,distance=r4.box,r4.cyl,r4.cut,r4.union,r4.common,r4.distance
compound,source,world_bounds,candidates=r4.compound,r4.source,r4.world_bounds,r4.candidates
I=np.eye(4).tolist();IMPL=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
def state_rows():
    m=read(R4/'inputs/MOUNT_LAYOUT.json');p=read(R4/'inputs/PASSAGE_LAYOUT.json');mods={r['id']:r for r in m['replacements']+p['replacements']}
    out={}
    for st,rows in r4.state_rows().items():
        armgroup=next(r['group'] for r in rows if r['id']=='equipment_arm_drive')
        out[st]=[dict(mods.get(r['id'],r),group=r['group']) for r in rows]+[dict(r,group=armgroup) for r in m['additions']]
    native={r['id']:r for r in read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json')['expected_leaves']}
    assert len(out['service'])==len(native)==1130
    for r in out['service']:
        assert Path(r['native_path']).resolve()==Path(native[r['id']]['native_path']).resolve()
        assert np.max(np.abs(np.array(r['T_S_local'])-native[r['id']]['T_S_local']))<1e-10
    return out
def emit(ident,s,role,sub='candidates',**kw):
    p=D/'cad'/sub/(ident+'.step');p.parent.mkdir(exist_ok=True,parents=True);q=g.dump(s,p)
    return dict(id=ident,step_path=str(p),source_sha256=q['sha256'],native_path=str(D/'native'/(ident+'.SLDPRT')),
        T_S_local=I,expected_solids=q['solids'],expected_sheets=0,expected_volume_mm3=q['volume_mm3'],
        expected_local_bbox_mm={'min_mm':q['bounds_mm'][0],'max_mm':q['bounds_mm'][1]},representation_role=role,**kw)
