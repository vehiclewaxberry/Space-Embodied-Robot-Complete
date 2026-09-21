"""Bounded sequential STEP BRep reading; outputs geometric integrals, never CAD."""
from pathlib import Path
import argparse, json, hashlib, gc, math, importlib.metadata, sys, time
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRep import BRep_Tool
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_SHELL
from OCP.TColStd import TColStd_SequenceOfAsciiString
from OCP.gp import gp_Pnt, gp_Trsf, gp_Ax1, gp_Dir
from OCP.TopLoc import TopLoc_Location
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder

M=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--start',type=int,required=True);a.add_argument('--end',type=int,required=True);args=a.parse_args()
jobs=json.loads((M/'SOURCE_JOBS.json').read_text())
packet=json.loads(Path(jobs['source_packet']).read_text());bodies={x['id']:x for x in packet['instances']}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(jobs['source_packet'])==jobs['source_packet_sha256']

def write(path,data):
    tmp=path.with_suffix(path.suffix+'.partial')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(path)

def props(shape,eps=None,reference=None):
    p=GProp_GProps(gp_Pnt(*reference)) if reference is not None else GProp_GProps()
    err=None
    if eps is None:BRepGProp.VolumeProperties_s(shape,p)
    else:
        err=BRepGProp.VolumePropertiesGK_s(shape,p,eps,True,True,True,True,False)
        assert err>=0,'Gauss-Kronrod integration failed'
    c=p.CentreOfMass();mat=p.MatrixOfInertia()
    r={'volume_mm3':p.Mass(),'COM_local_mm':[c.X(),c.Y(),c.Z()],
       'I_COM_local_mm5':[[mat.Value(i,j) for j in range(1,4)] for i in range(1,4)],
       'requested_eps':eps,'returned_volume_relative_error_estimate':err,
       'accumulation_reference_local_mm':reference or [0,0,0],
       'method':'BRepGProp.VolumeProperties(default,no triangulation)' if eps is None else 'BRepGProp.VolumePropertiesGK(adaptive Gauss-Kronrod,OnlyClosed=True,IsUseSpan=True,CGFlag=True,IFlag=True,SkipShared=False)'}
    I=np.asarray(r['I_COM_local_mm5']);eig=np.linalg.eigvalsh(I);tol=max(float(np.max(np.abs(I)))*1e-10,1e-10)
    assert r['volume_mm3']>0 and np.all(np.isfinite(I))
    assert np.max(np.abs(I-I.T))<=tol and eig[0]>=-tol and eig[2]<=eig[0]+eig[1]+tol
    r['principal_geometric_inertias_mm5']=eig.tolist();r['symmetry_PSD_triangle_numerical_tolerance_mm5']=tol
    return p,r

def analytical_fixtures():
    tests=[]
    box=BRepPrimAPI_MakeBox(gp_Pnt(11,22,33),10,20,30).Shape()
    for eps in [None,1e-7,1e-9]:
        _,r=props(box,eps)
        expected=np.diag([6000*(20**2+30**2)/12,6000*(10**2+30**2)/12,6000*(10**2+20**2)/12])
        ok=abs(r['volume_mm3']-6000)<1e-7 and np.max(np.abs(np.asarray(r['COM_local_mm'])-[16,32,48]))<1e-9 and np.max(np.abs(np.asarray(r['I_COM_local_mm5'])-expected))<1e-6
        tests.append({'id':'offset_box_'+str(eps),'pass':bool(ok),'observed':r,'analytic_volume_mm3':6000,'analytic_COM_mm':[16,32,48],'analytic_I_COM_mm5':expected.tolist()})
    cylinder=BRepPrimAPI_MakeCylinder(5,20).Shape();_,r=props(cylinder,1e-9)
    v=math.pi*25*20;expected=np.diag([v*(3*25+400)/12,v*(3*25+400)/12,v*25/2])
    ok=abs(r['volume_mm3']-v)<1e-7 and np.max(np.abs(np.asarray(r['COM_local_mm'])-[0,0,10]))<1e-9 and np.max(np.abs(np.asarray(r['I_COM_local_mm5'])-expected))<1e-6
    tests.append({'id':'curved_cylinder','pass':bool(ok),'observed':r,'analytic_volume_mm3':v,'analytic_I_COM_mm5':expected.tolist()})
    write(M/'results/ANALYTICAL_GEOMETRIC_FIXTURES.json',{'tests':tests,'geometry_saved':False,'mass_density_applied':False})
    assert all(t['pass'] for t in tests)
    return tests

if args.start==0:
    write(M/'results/ANALYTICAL_GEOMETRIC_FIXTURES.json',{'tests':analytical_fixtures(),'geometry_saved':False,'mass_density_applied':False})

batch=[]
for job in jobs['rows'][args.start:args.end]:
    out=M/'results'/('G%03d.json'%job['index'])
    assert not out.exists(),str(out)
    start=time.monotonic();r={'index':job['index'],'source':job['source'],'instances':job['instances'],'status':'RUNNING'}
    try:
        source=job['source']['path'];assert sha(source)==job['source']['sha256']
        reader=STEPControl_Reader();Interface_Static.SetCVal_s('xstep.cascade.unit','MM')
        assert reader.ReadFile(source)==IFSelect_RetDone
        units=[TColStd_SequenceOfAsciiString() for _ in range(3)];reader.FileUnits(*units)
        r['declared_STEP_units']=[[seq.Value(i).ToCString() for i in range(1,seq.Length()+1)] for seq in units]
        reader.SetSystemLengthUnit(1.0)
        transferred=reader.TransferRoots();assert transferred>0
        shape=reader.OneShape();assert not shape.IsNull()
        solid_ex=TopExp_Explorer(shape,TopAbs_SOLID);solids=[]
        while solid_ex.More():solids.append(solid_ex.Current());solid_ex.Next()
        shell_ex=TopExp_Explorer(shape,TopAbs_SHELL);closed=[]
        while shell_ex.More():closed.append(bool(BRep_Tool.IsClosed_s(shell_ex.Current())));shell_ex.Next()
        valid=bool(BRepCheck_Analyzer(shape).IsValid())
        assert valid and len(solids)==job['expected_solids'] and len(closed)>0 and all(closed)
        r['topology']={'valid':valid,'solid_count':len(solids),'shell_count':len(closed),'all_shells_closed':all(closed),'expected_solids':job['expected_solids'],'triangulation_used':False}
        p0,d0=props(shape);c0=d0['COM_local_mm'];p7,d7=props(shape,1e-7,c0);p9,d9=props(shape,1e-9,c0)
        r.update(default=d0,adaptive_eps1e7=d7,adaptive_eps1e9=d9)
        r['convergence']={'volume_relative_change':abs(d9['volume_mm3']-d7['volume_mm3'])/d9['volume_mm3'],
            'COM_max_abs_change_mm':float(np.max(np.abs(np.asarray(d9['COM_local_mm'])-d7['COM_local_mm']))),
            'inertia_max_abs_change_mm5':float(np.max(np.abs(np.asarray(d9['I_COM_local_mm5'])-d7['I_COM_local_mm5']))),
            'strict_volume_COM_inertia_error_bound':None,'status':'OBSERVED_TWO_TOLERANCE_CHANGE_NOT_RIGOROUS_ERROR_BOUND'}
        r['default_vs_adaptive']={'volume_relative_difference':abs(d0['volume_mm3']-d9['volume_mm3'])/d9['volume_mm3'],
            'COM_max_abs_difference_mm':float(np.max(np.abs(np.asarray(d0['COM_local_mm'])-d9['COM_local_mm']))),
            'inertia_max_abs_difference_mm5':float(np.max(np.abs(np.asarray(d0['I_COM_local_mm5'])-d9['I_COM_local_mm5'])))}
        # Reintegrate a real rigidly placed BRep in each of the representative instance's three states.
        representative=bodies[job['instances'][0]];world=[]
        for state,g in representative['geometry_by_state'].items():
            T=np.asarray(g['T_local_to_S_SI_m']);rot=T[:3,:3];tmm=T[:3,3]*1000
            tr=gp_Trsf();tr.SetValues(*[v for i in range(3) for v in [*rot[i],tmm[i]]])
            transformed=shape.Moved(TopLoc_Location(tr));center=rot@np.asarray(d9['COM_local_mm'])+tmm
            pw,dw=props(transformed,1e-9,center.tolist())
            target_I=rot@np.asarray(d9['I_COM_local_mm5'])@rot.T
            irel=float(np.max(np.abs(np.asarray(dw['I_COM_local_mm5'])-target_I)))/max(float(np.max(np.abs(target_I))),1e-20)
            cerr=float(np.max(np.abs(np.asarray(dw['COM_local_mm'])-center)))
            verr=abs(dw['volume_mm3']-d9['volume_mm3'])/d9['volume_mm3']
            axis_checks=[]
            I_origin=target_I+d9['volume_mm3']*(np.dot(center,center)*np.eye(3)-np.outer(center,center))
            for i in range(3):
                direction=np.eye(3)[i]
                actual=pw.MomentOfInertia(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(*direction)))
                axis_checks.append(abs(actual-I_origin[i,i])/max(abs(actual),1e-20))
            assert verr<1e-7 and cerr<1e-5 and irel<1e-6 and max(axis_checks)<1e-7
            world.append({'state':state,'representative_instance':representative['id'],'volume_relative_error':verr,'COM_max_abs_error_mm':cerr,'I_COM_relative_max_error':irel,'axis_origin_MomentOfInertia_relative_errors':axis_checks,'actual_BRep_rigid_placement_reintegrated':True})
            transformed=pw=None
        r['actual_three_pose_BRep_checks']=world
        r.update(status='PASS_SOURCE_BREP_GEOMETRIC_INTEGRALS_AND_POSE_CHECKS',source_unchanged_after=sha(source)==job['source']['sha256'],material_density_applied=False,
            runtime={'python':sys.version,'cadquery_ocp':importlib.metadata.version('cadquery-ocp'),'numpy':np.__version__})
    except Exception as exc:
        r.update(status='SOURCE_READ_OR_GEOMETRY_CHECK_FAILED',exception=repr(exc))
    r['elapsed_s']=time.monotonic()-start;write(out,r);batch.append({'index':job['index'],'status':r['status'],'elapsed_s':r['elapsed_s']})
    shape=reader=solids=units=p0=p7=p9=None;gc.collect()
    print(json.dumps(batch[-1]),flush=True)
write(M/'results'/('BATCH_%03d_%03d.json'%(args.start,args.end)),{'rows':batch,'all_pass':all(x['status'].startswith('PASS_') for x in batch)})
