"""Read-only service-state screening of three level-board layout proposals.

Writes reviewer evidence only. Hypothetical obstacle changes are recorded,
never written to CAD or interpreted as completed installation.
"""
from pathlib import Path
import hashlib, itertools, json
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

D=Path(__file__).resolve().parents[2];ROOT=D.parents[1];E=D.parent
R4=E/'SERVICE_STAR_INTERNAL_LAYOUT_R4_20260920';R2=E/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
locks={};raw={};world={}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lock(p):
    p=Path(p);key=str(p.resolve().relative_to(ROOT)).replace('\\','/');h=digest(p)
    if key in locks:assert locks[key]==h
    locks[key]=h;return h
def read(p):lock(p);return json.loads(Path(p).read_text(encoding='utf8'))
def load(p):
    if p not in raw:
        q=STEPControl_Reader();assert q.ReadFile(p)==IFSelect_RetDone;assert q.TransferRoots()>0
        s=q.OneShape();assert BRepCheck_Analyzer(s).IsValid();raw[p]=s
    return raw[p]
def moved(s,t):
    q=gp_Trsf();q.SetValues(*[float(t[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(s,q,True).Shape()
def shape(r):
    p=r['step_path'];t=np.array(r['T_S_local']);key=(p,tuple(t.flat))
    if key not in world:
        assert lock(p)==r['source_sha256'];world[key]=moved(load(p),t)
    return world[key]
def bounds(s):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(s,b,False,False);v=b.Get();return np.array([v[:3],v[3:]])
def volume(s):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);return abs(g.Mass())
def common(a,b):
    q=BRepAlgoAPI_Common(a,b);q.Build();assert q.IsDone();s=q.Shape();assert BRepCheck_Analyzer(s).IsValid();return s
def near(a,b):return bool(np.all(a[0]<=b[1]+1e-7) and np.all(b[0]<=a[1]+1e-7))

native=read(R4/'inputs/NATIVE_ASSEMBLY_PLAN.json');rows=native['expected_leaves']
cached=read(R2/'inputs/SOURCE_LOCAL_BOUNDS.json')['bounds_by_path']
coverage=read(D/'inputs/MAIN_GEOMETRY_COVERAGE.json');core=shape(coverage['board'])
def rbb(r):
    if r['step_path'] in cached:
        lo,hi=cached[r['step_path']];t=np.array(r['T_S_local'])
        pts=np.array(list(itertools.product(*zip(lo,hi))));pts=pts@t[:3,:3].T+t[:3,3]
        return np.array([pts.min(axis=0),pts.max(axis=0)])
    return bounds(shape(r))
rotation90=np.array([[0,-1,0],[1,0,0],[0,0,1]])
cases=[
    dict(id='A_UNDER_P60_RETAIN_ENVELOPE',R=np.eye(3),translation=[-154,76,21],
         changed_host_ids=[],hypothesis='Reroute battery functional bypass and trunk support; maintain full retained obstacles for this diagnostic.'),
    dict(id='B_P60_LOWERED_25_MAIN_ABOVE',R=np.eye(3),translation=[-154,76,68],
         changed_host_ids=['P60_REFERENCE_B','P60_TRAY_B'],hypothesis='P60 module and tray translated -25mm in Z for screening. Posts, rods, mounting and routes require redesign; support correctness is NOT established.'),
    dict(id='C_LEGACY_BATTERY_ALLOCATION_RECONCILIATION',R=rotation90,translation=[-154,-50,-40],
         changed_host_ids=[],hypothesis='Existing legacy battery proxy retained in collision output; it may be superseded only after system/BOM identity decision. No proxy was deleted.'),
]
results=[]
for case in cases:
    t=np.eye(4);t[:3,:3]=case['R'];t[:3,3]=case['translation'];s=moved(core,t);sb=bounds(s)
    hits=[];unknown=[];n=0
    for orig in rows:
        r=orig
        if orig['id'] in case['changed_host_ids']:
            r=dict(orig);rt=np.array(r['T_S_local']);rt[2,3]-=25;r['T_S_local']=rt.tolist()
        if near(sb,rbb(r)):
            n+=1
            try:
                v=volume(common(s,shape(r)))
                if v>1e-5:hits.append(dict(id=r['id'],role=r['representation_role'],overlap_mm3=v))
            except Exception as ex:unknown.append(dict(id=r['id'],error=str(ex)))
    result={k:v for k,v in case.items() if k!='R'}
    result.update(T_S_core=t.tolist(),board_base_center_S_mm=(t@np.array([50,-40,0,1]))[:3].tolist(),
                  mixed_PCBA_bounds_S_mm=sb.tolist(),exact_pairs=n,hits=hits,unknown=unknown,
                  candidate_installed=False,manufacturing_release=False)
    results.append(result);print(case['id'],'pairs',n,'hits',hits,'unknown',unknown,flush=True)
out=dict(schema='R6_HORIZONTAL_OPTIONS_INDEPENDENT_SCREEN_V1',status='SERVICE_STATE_PROPOSAL_SCREEN_NOT_ASSEMBLY_RELEASE',
         full_geometry_scope='35 refs / 40 solids mixed source model; four assumed 6mm heights, body pose, lugs/wires and thermal clamp still unqualified.',
         input_locks=locks,cases=results,retained_source_hashes_unchanged=all(digest(ROOT/p)==h for p,h in locks.items()),
         three_states_revalidated=False,installation_and_insertion_access_validated=False,flight_ready=False)
(D/'results/reviewer/HORIZONTAL_OPTIONS_SCREEN.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('OUTPUT',D/'results/reviewer/HORIZONTAL_OPTIONS_SCREEN.json',flush=True)
