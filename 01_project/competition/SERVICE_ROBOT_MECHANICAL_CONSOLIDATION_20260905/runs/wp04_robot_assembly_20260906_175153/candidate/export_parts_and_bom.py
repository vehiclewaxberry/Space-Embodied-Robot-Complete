"""R17 final BOM export. --bom-only imports no CAD."""
from pathlib import Path
import argparse,csv,io,json,math,os
from provenance_binding import sha,verify_hashes,receipt_binding,validate_receipt_source,digest
from candidate_context import ENGINEERING
URDF=ENGINEERING/'cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
WP01_KIN=ENGINEERING/'service_robot_wp01_20260905/kinematics.py'
HERE=Path(__file__).resolve().parent
COLS=["id","pn","configuration","product_role","representation_role","qualification_status","parent_assembly","mount_interface","mass_source","mass_owner","mass_kg","mass_basis","source_revision","allocated_dynamics_mass_kg","allocated_dynamics_mass_source","allocated_mass_reference","handoff_sha256","receipt_sha256","geometry_snapshot_sha256"]
def validate_handoff_binding(receipt,handoff,receipt_path,here):
    here=Path(here);validate_receipt_source(receipt,here)
    if receipt["state"]!="service":raise ValueError("BOM_REQUIRES_SERVICE")
    if handoff.get("source_files_unchanged") is not True:raise ValueError("HANDOFF_NOT_STABLE")
    hashes=handoff.get("input_sha256");verify_hashes(hashes);receipt_path=Path(receipt_path).resolve()
    required=[here/'results'/f'{state}_instances.json' for state in ('parking','released','service')]+[URDF,WP01_KIN]+[here/n for n in ('spacecraft_model.py','design_parameters.json','dynamics_handoff.py','r01_design.py','provenance_binding.py','kinematics.py','wing_kinematics.py','root_structure.py','candidate_context.py')]
    if receipt.get('composition'):
        required += [here/name for name in receipt['dependency_sha256']]
        required += [Path(ref['path']) for ref in receipt['composition'].values() if isinstance(ref,dict) and 'path' in ref and 'sha256' in ref]
    for p in required:
        if hashes.get(str(p.resolve()))!=sha(p):raise ValueError("REQUIRED_HANDOFF_INPUT_NOT_BOUND:"+str(p))
    if handoff.get("receipt_bindings",{}).get("service")!=receipt_binding(receipt,receipt_path):raise ValueError("HANDOFF_RECEIPT_IDENTITY_MISMATCH")
    states=[s for s in handoff.get("states",[]) if s.get("state")=="service"]
    if len(states)!=1:raise ValueError("HANDOFF_SERVICE_STATE_MISSING_OR_DUPLICATE")
    s=states[0];values=s["mass_owner_values"];rows=receipt["instances"]
    for hkey,rkey in [('q_deg','q_deg'),('finger_mm','finger_mm'),('T_S_arm_base_mm','T_S_arm_base')]:
        if s.get(hkey)!=receipt.get(rkey):raise ValueError('POSE_CONFIGURATION_MISMATCH:'+hkey)
    expected={r["mass_owner"] for r in rows if r.get("arm_link") or (r.get("mass_kg") is not None and r["mass_kg"]>0)}
    if set(values)!=expected:raise ValueError("MASS_OWNER_COVERAGE_MISMATCH")
    group=s['groups']['ONBOARD_CANDIDATE'];atom_list=group['mass_atoms'];unknown_list=group['unknown_mass_instances']
    atoms={r['mass_owner']:r for r in atom_list}
    if len(atoms)!=len(atom_list) or len({r['id'] for r in atom_list})!=len(atom_list):raise ValueError('DUPLICATE_MASS_ATOM')
    unknown={r['mass_owner']:r for r in unknown_list}
    expected_unknown={r['mass_owner'] for r in rows if r.get('mass_kg') is None and not r.get('arm_link')}
    if len(unknown)!=len(unknown_list) or set(unknown)!=expected_unknown:raise ValueError('UNKNOWN_COVERAGE_MISMATCH')
    if group.get('instance_count')!=len(rows) or group.get('known_mass_missing_properties'):raise ValueError('INCOMPLETE_PROPERTY_SCOPE')
    roles=s.get('mass_owner_values_by_role',{})
    if roles.get('ONBOARD_CANDIDATE')!=values or any(v for k,v in roles.items() if k!='ONBOARD_CANDIDATE'):raise ValueError('MASS_ROLE_MAPPING_MISMATCH')
    for r in rows:
        mapped=atoms.get(r['mass_owner']) or unknown.get(r['mass_owner'])
        if mapped is None and r.get('mass_kg')==0:continue
        if mapped is None or any(mapped.get(k)!=r.get(k) for k in ('id','product_role','representation_role','source_revision','mass_owner')):raise ValueError('ATOM_SOURCE_IDENTITY_MISMATCH')
    if set(atoms)!=expected:raise ValueError("MASS_ATOM_COVERAGE_MISMATCH")
    outputs=[]
    for r in rows:
        owner=r["mass_owner"];m=values.get(owner);atom=atoms.get(owner)
        if m is not None:
            if type(m) not in (int,float) or not math.isfinite(m) or m<=0:raise ValueError("INVALID_ALLOCATED_MASS")
            if atom.get("id")!=r["id"] or atom.get("product_role")!="ONBOARD_CANDIDATE":raise ValueError("ATOM_IDENTITY_MISMATCH")
            if abs(atom["mass_kg"]-m)>1e-12:raise ValueError("ATOM_VALUE_MISMATCH")
            if r.get("arm_link"):
                if atom.get("mass_source")!="SOURCE_DIGITAL":raise ValueError("ARM_MASS_NOT_DIGITAL")
            elif r.get("mass_kg") is None or abs(m-r["mass_kg"])>1e-10:raise ValueError("ROW_MASS_MISMATCH")
        elif r.get("mass_kg") is not None and r["mass_kg"]!=0:raise ValueError("MISSING_KNOWN_MASS")
        outputs.append({**r,"allocated_dynamics_mass_kg":m,"allocated_dynamics_mass_source":"SOURCE_DIGITAL" if r.get("arm_link") else r.get("mass_source"),"allocated_mass_reference":"results/DYNAMICS_HANDOFF.json"})
    total=math.fsum(r["allocated_dynamics_mass_kg"] for r in outputs if r["allocated_dynamics_mass_kg"] is not None)
    if abs(total-s["groups"]["ONBOARD_CANDIDATE"]["known_mass_kg"])>1e-10:raise ValueError("BOM_MASS_TOTAL_MISMATCH")
    return outputs
def csv_bytes(rows,cols):
    f=io.StringIO(newline="");w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(rows);return f.getvalue().encode("utf-8-sig")
def export_bom(here=None):
    here=Path(HERE if here is None else here);rp=here/"results/service_instances.json";hp=here/"results/DYNAMICS_HANDOFF.json"
    before={str(p):sha(p) for p in [rp,hp]};receipt=json.loads(rp.read_text(encoding="utf-8-sig"));handoff=json.loads(hp.read_text(encoding="utf-8-sig"))
    rows=validate_handoff_binding(receipt,handoff,rp,here)
    for r in rows:r.update(handoff_sha256=before[str(hp)],receipt_sha256=before[str(rp)],geometry_snapshot_sha256=digest(receipt["geometry_sha256"]))
    content=csv_bytes(rows,COLS);interfaces=receipt.get("interfaces")
    if not isinstance(interfaces,list) or not interfaces:raise ValueError("MISSING_INTERFACES")
    ibytes=csv_bytes(interfaces,list(interfaces[0]));verify_hashes(before);validate_receipt_source(receipt,here);verify_hashes(handoff["input_sha256"])
    for name,data in [("BOM.csv",content),("INTERFACES.csv",ibytes)]:
        temp=here/(name+".tmp");temp.write_bytes(data);os.replace(temp,here/name)
    result=dict(status="BOM_BOUND_TO_FINAL_GEOMETRY_AND_HANDOFF",row_count=len(rows),handoff_sha256=before[str(hp)],receipt_sha256=before[str(rp)],BOM_sha256=sha(here/"BOM.csv"),geometry_sha256=receipt["geometry_sha256"],physical_mass_complete=False)
    (here/"results/BOM_BINDING.json").write_text(json.dumps(result,indent=2),encoding="utf-8");return result
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--bom-only",action="store_true");a=p.parse_args(argv)
    if not a.bom_only:
        from spacecraft_model import build
        build("service",include_arm=False,write_parts=True)
        raise RuntimeError("PARTS_EXPORTED: finalize geometry, complete receipts and HANDOFF; then --bom-only")
    result=export_bom();print(json.dumps(result));return result
if __name__=="__main__":main()
