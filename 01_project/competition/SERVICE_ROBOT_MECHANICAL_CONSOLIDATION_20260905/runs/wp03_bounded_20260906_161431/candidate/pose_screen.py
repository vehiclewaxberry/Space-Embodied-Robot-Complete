"""Runtime-bound WP03 candidate surface screen; no full-motion safety claim."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,itertools,json,math,subprocess,sys,time
import numpy as np
from candidate_context import WP01, WP02, RUN_ID
from provenance_binding import sha,verify_hashes,validate_receipt_source
from strict_surface_aggregator import aggregate,digest,require_physical_view
import kinematics as kin
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/"design_parameters.json").read_text(encoding="utf-8"))
STATES=("parking","released","service")
def classify_self_surface(contract,evidence):
    """Actual parent uses this function; negative controls target the same path."""
    return aggregate(contract,evidence)
def load_motion():
    spec=importlib.util.spec_from_file_location("wp03_readonly_triangle_helpers",WP02/"motion_analysis.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def input_snapshot():
    files=[HERE/n for n in ["pose_screen.py","strict_surface_aggregator.py","provenance_binding.py","candidate_context.py","kinematics.py","design_parameters.json","spacecraft_model.py","r01_design.py"]]
    files+=[kin.URDF,WP02/"motion_analysis.py",WP01/'kinematics.py']
    files += [HERE/"results"/f"{s}_instances.json" for s in STATES]
    for link in kin.TREE.findall("link"):files.append(kin.URDF.parent/link.find("visual/geometry/mesh").get("filename"))
    out={str(p.resolve()):sha(p) for p in files}
    for state in STATES:
        r=json.loads((HERE/"results"/f"{state}_instances.json").read_text(encoding="utf-8"))
        validate_receipt_source(r,HERE);require_physical_view(r)
        if r["state"]!=state or r["configuration"]!=P["configuration_id"]:raise ValueError("WRONG_RECEIPT_CONFIGURATION")
        out.update(r["geometry_sha256"])
    verify_hashes(out);return out
def expected_pairs():
    names=[x.get("name") for x in kin.TREE.findall("link")]
    adjacent={frozenset([j.find("parent").get("link"),j.find("child").get("link")]) for j in kin.TREE.findall("joint")}
    return [list(p) for p in itertools.combinations(names,2) if frozenset(p) not in adjacent]
def make_contract(state,hashes):
    receipt=json.loads((HERE/"results"/f"{state}_instances.json").read_text(encoding="utf-8"));cfg=P["states"][state]
    if cfg["q_deg"]!=receipt["q_deg"] or cfg["finger_mm"]!=receipt["finger_mm"]:raise ValueError("PARAMETER_RECEIPT_POSE_MISMATCH")
    config=dict(configuration_id=P["configuration_id"],pose_id=state,state=state,view="complete",q_deg=cfg["q_deg"],finger_mm=cfg["finger_mm"],T_S_arm_base=receipt["T_S_arm_base"])
    return dict(run_id=RUN_ID,configuration=config,input_sha256=hashes,expected_nonadjacent_pairs=expected_pairs(),explicit_unknown_pairs=[["gripper_left","gripper_right"]])
def self_worker(path):
    c=json.loads(Path(path).read_text(encoding="utf-8"));verify_hashes(c["input_sha256"]);config=c["configuration"];pose=config["pose_id"];snap=digest(c["input_sha256"])
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
    motion=load_motion()
    if motion.kin.URDF.resolve()!=kin.URDF.resolve():raise ValueError('INDIRECT_MESH_URDF_MISMATCH')
    raw,_=motion.read_triangles();verify_hashes(c['input_sha256']);frames=kin.fk(config["q_deg"],np.array(config["T_S_arm_base"]),config["finger_mm"])
    world={n:kin.place(t.reshape(-1,3),frames[n]).reshape(-1,3,3) for n,t in raw.items()}
    triangle_bounds={n:(t.min(axis=1),t.max(axis=1)) for n,t in world.items()}
    bounds={n:(lo.min(axis=0),hi.max(axis=0)) for n,(lo,hi) in triangle_bounds.items()}
    identity=vtk.vtkTransform();identity.Identity()
    def poly(tris):
        points=vtk.vtkPoints();points.SetData(numpy_to_vtk(np.ascontiguousarray(tris.reshape(-1,3)),deep=True))
        cells=np.column_stack([np.full(len(tris),3,dtype=np.int64),np.arange(3*len(tris),dtype=np.int64).reshape(-1,3)])
        triangles=vtk.vtkCellArray();triangles.SetCells(len(tris),numpy_to_vtkIdTypeArray(cells.ravel(),deep=True))
        out=vtk.vtkPolyData();out.SetPoints(points);out.SetPolys(triangles);return out
    count=0
    for a,b in c["expected_nonadjacent_pairs"]:
        row=dict(links=[a,b],run_id=c["run_id"],pose_id=pose,snapshot_digest=snap,surface_intersection=None)
        if {a,b}=={"gripper_left","gripper_right"}:
            row.update(method="EXPLICITLY_DEFERRED_FINGER_PAIR",unknown_reason="ACCEPTED_STL_PAIR_REQUIRES_R13_SPECIALIST_VALIDATION")
        else:
            low=np.maximum(bounds[a][0],bounds[b][0]);high=np.minimum(bounds[a][1],bounds[b][1])
            if np.any(low>high):row.update(surface_intersection=False,method="STRICT_LINK_AABB_SEPARATION")
            else:
                crop={}
                for name in [a,b]:
                    lo,hi=triangle_bounds[name];crop[name]=world[name][np.all(hi>=low,axis=1)&np.all(lo<=high,axis=1)]
                row["cropped_triangle_count"]={n:len(t) for n,t in crop.items()}
                if any(not len(t) for t in crop.values()):row.update(surface_intersection=False,method="EMPTY_CONSERVATIVE_TRIANGLE_CROP")
                else:
                    check=vtk.vtkCollisionDetectionFilter();check.SetInputData(0,poly(crop[a]));check.SetInputData(1,poly(crop[b]))
                    check.SetTransform(0,identity);check.SetTransform(1,identity);check.SetBoxTolerance(0);check.SetCellTolerance(0)
                    check.SetNumberOfCellsPerNode(16);check.SetCollisionModeToFirstContact();check.GenerateScalarsOff();check.Update()
                    contacts=int(check.GetNumberOfContacts());row.update(surface_intersection=bool(contacts),method="VTK_FIRST_CONTACT_ORIGINAL_TRIANGLES",contacts=contacts)
        print(json.dumps(dict(event="pair",record=row)),flush=True);count+=1
    verify_hashes(c["input_sha256"])
    completion=dict(completed=True,run_id=c["run_id"],pose_id=pose,snapshot_digest=snap,expected_pair_count=count)
    print(json.dumps(dict(event="complete",completion=completion,input_sha256_after=c["input_sha256"],vtk_version=vtk.vtkVersion.GetVTKVersion())),flush=True)
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--self-worker",type=Path);parser.add_argument("--contract-only",action="store_true");parser.add_argument("--worker-timeout",type=float,default=150);args=parser.parse_args(argv)
    if args.self_worker:return self_worker(args.self_worker)
    hashes=input_snapshot();outputs=[]
    for state in STATES:
        contract=make_contract(state,hashes);cp=HERE/"results"/f"surface_contract_{state}.json";cp.write_text(json.dumps(contract,indent=2),encoding="utf-8")
        if args.contract_only:
            outputs.append(dict(state=state,status="CONTRACT_ONLY_GEOMETRY_NOT_RUN",contract=str(cp)));continue
        timed=False;code=None;error=None
        try:
            p=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--self-worker",str(cp)],capture_output=True,text=True,timeout=args.worker_timeout)
            stdout=p.stdout;stderr=p.stderr;code=p.returncode
            if code!=0:error=stderr[-2000:] or "NONZERO_WORKER_EXIT"
        except subprocess.TimeoutExpired as e:
            timed=True;stdout=e.stdout or "";stderr=e.stderr or "";stdout=stdout.decode("utf-8",errors="replace") if isinstance(stdout,bytes) else stdout;stderr=stderr.decode("utf-8",errors="replace") if isinstance(stderr,bytes) else stderr;error="WORKER_TIMEOUT"
        (HERE/"results"/f"surface_worker_{state}.jsonl").write_text(stdout,encoding="utf-8")
        (HERE/"results"/f"surface_worker_{state}.stderr.log").write_text(stderr,encoding="utf-8")
        rows=[];complete=[];after=None;parse_errors=[]
        for line in stdout.splitlines():
            try:
                e=json.loads(line)
                if not isinstance(e,dict):raise ValueError('EVENT_NOT_OBJECT')
                if e.get("event")=="pair":rows.append(e["record"])
                elif e.get("event")=="complete":complete.append(e["completion"]);after=e.get("input_sha256_after")
                else:parse_errors.append("UNKNOWN_EVENT")
            except (ValueError,KeyError,TypeError):parse_errors.append("MALFORMED_EVENT")
        try:verify_hashes(hashes)
        except ValueError as e:error=str(e)
        if len(complete)!=1:error=error or "MISSING_OR_DUPLICATE_COMPLETION"
        if parse_errors:error=error or ";".join(parse_errors)
        evidence=dict(run_id=RUN_ID,configuration=contract["configuration"],input_sha256_before=hashes,input_sha256_after=after,worker_returncode=code,worker_error=error,timed_out=timed,completion=complete[0] if len(complete)==1 else None,records=rows,geometry_attempted=True,geometry_executed=bool(rows) and not parse_errors)
        result=classify_self_surface(contract,evidence)
        outputs.append(dict(state=state,contract=contract,evidence=evidence,classification=result))
    status="CONTRACTS_READY_GEOMETRY_NOT_RUN" if args.contract_only else "SCOPED_SURFACE_RESULTS_WITH_EXPLICIT_UNKNOWN"
    result=dict(schema="WP03_RUNTIME_BOUND_SURFACE_SCREEN_V2",status=status,poses=outputs,full_wp03_assembly_collision_pass=None,volume_containment_status="UNKNOWN",finger_pair_status="UNKNOWN",continuous_motion_status="NOT_RUN",launch_stow_status="NOT_ESTABLISHED")
    (HERE/"results/POSE_SCREEN.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps(dict(status=status,poses=[dict(state=r["state"],status=r.get("classification",r).get("status")) for r in outputs])))
if __name__=="__main__":main()
