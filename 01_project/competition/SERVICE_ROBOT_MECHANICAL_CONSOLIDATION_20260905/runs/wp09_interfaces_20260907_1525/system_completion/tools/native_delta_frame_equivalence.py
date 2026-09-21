"""Validate 8 actual native roundtrips; same adaptive OCCT quadrature on old/new."""
from pathlib import Path
import hashlib,json
from build123d import import_step
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
C=Path(__file__).resolve().parents[1];N=C.parent/'reuse_closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def integrate(shape):
 vals=[]
 for eps in (1e-7,1e-9):
  p=GProp_GProps();err=BRepGProp.VolumeProperties_s(shape.wrapped,p,eps,True,False);vals.append(dict(eps=eps,volume_mm3=p.Mass(),estimated_relative_error=err))
 assert abs(vals[1]['volume_mm3']-vals[0]['volume_mm3'])<1e-5
 return vals
j=json.loads((C/'results/NATIVE_DELTA_INPUTS.json').read_text());old=json.loads((N/'results/NATIVE_SERVICE_RECOVERY_V2.json').read_text());old={q['id']:q for q in old['rows']};rows=[]
for q in j['parts'][:8]:
 source=Path(q['step_path']);native=Path(q['native_path']);rt=native.with_suffix('.step');a=import_step(source);b=import_step(rt)
 oa=old[q['id']]['source_step'];op=Path(oa['path']);assert sha(op)==oa['sha256'];o=import_step(op)
 va=integrate(a);vb=integrate(b);vo=integrate(o);relative=abs(va[-1]['volume_mm3']-vb[-1]['volume_mm3'])/va[-1]['volume_mm3']
 forward=a-b;reverse=b-a
 same=len(forward.solids())==len(reverse.solids())==0 and relative<=1e-7 and a.is_valid and b.is_valid and len(a.solids())==len(b.solids())==1
 assert same,q['id']
 rows.append(dict(id=q['id'],source=str(source),source_sha256=sha(source),native=str(native),native_sha256=sha(native),native_roundtrip=str(rt),native_roundtrip_sha256=sha(rt),old_source=str(op),old_source_sha256=sha(op),source_adaptive_integrals=va,native_roundtrip_adaptive_integrals=vb,old_source_adaptive_integrals=vo,relative_volume_error=relative,original_minus_native_solid_count=len(forward.solids()),native_minus_original_solid_count=len(reverse.solids()),pass_geometry_equivalence=bool(same),
  mass_model_density_kg_mm3=2.7e-6,new_adaptive_mass_kg=va[-1]['volume_mm3']*2.7e-6,old_adaptive_mass_kg=vo[-1]['volume_mm3']*2.7e-6,matched_algorithm_delta_mass_kg=(va[-1]['volume_mm3']-vo[-1]['volume_mm3'])*2.7e-6))
r=dict(status='PASS_8_NATIVE_ROUNDTRIPS_SAME_KERNEL_GEOMETRY_EQUIVALENCE',method='OCCT adaptive volume eps1e-7 and1e-9 convergence; source minus native-roundtrip and reverse both empty at kernel tolerance; no assertion of zero error below kernel tolerance',relative_volume_tolerance=1e-7,rows=rows,
 new_mass_kg=sum(q['new_adaptive_mass_kg'] for q in rows),old_mass_kg=sum(q['old_adaptive_mass_kg'] for q in rows),matched_algorithm_delta_mass_kg=sum(q['matched_algorithm_delta_mass_kg'] for q in rows),native_GetMassProperties_scalar_equivalence=False,
 note='SW native volume scalar discrepancy retained in import receipts. Same-kernel native roundtrip establishes geometry consistency; material mass remains calculated candidate, not weighed.')
(C/'results/NATIVE_DELTA_FRAME_EQUIVALENCE.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k!='rows'}))
