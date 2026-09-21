"""Bind emitted deltas to portable baseline, preserving original instance IDs."""
from pathlib import Path
import json,hashlib,copy,shutil
C=Path(__file__).resolve().parents[1];D=C/'cad';D.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
portable=read(C/'results/PORTABLE_INPUTS.json');delivery=read(C/'results/PORTABLE_DELIVERY.json')
assert delivery['status'].startswith('PASS_')
solar=read(C/'results/SOLAR_DELTA_STEP_BUILD.json');fast=read(C/'mass/r01_geometry_delta/BUILD_RECEIPT.json')
assert fast['source_frame_leaves']==128
records=[]
for key,q in solar['emitted_parts'].items():
 records.append(dict(id=key,step_path=q['path'],source_sha256=q['sha256'],expected_solids=1,expected_volume_mm3=q['volume_mm3'],expected_local_bbox_mm=[q['local_bounds_mm']['min_mm'],q['local_bounds_mm']['max_mm']],representation_role=q['geometry_role']))
for q in fast['rows']:
 if not q['scope'].startswith('SOURCE_FRAME'):continue
 records.append(dict(id=q['id'],step_path=q['step_path'],source_sha256=q['sha256'],expected_solids=1,expected_volume_mm3=q['volume_mm3'],expected_local_bbox_mm=[q['bounds_mm']['min_mm'],q['bounds_mm']['max_mm']],representation_role=q['representation_role']))
assert len(records)==138 and len({q['id'] for q in records})==138
for i,q in enumerate(records):
 assert sha(q['step_path'])==q['source_sha256'];q['native_path']=str(D/f'D{i:03d}.SLDPRT')
byid={q['id']:q for q in records};states={};copied={}
for state in ('service','parking','released'):
 solarplan=read(C/f'results/SOLAR_{state.upper()}_INSTANCE_PLAN.json');rows=copy.deepcopy(solarplan['rows'])
 prior={q['id']:q for q in portable['states'][state]['rows']}
 for row in rows:
  key=row['id'] if row['id'] in byid else row.get('part_key')
  if key in byid:
   q=byid[key];row.update(native_path=q['native_path'],native_sha256=None,native_delta_part_id=key,
     step_path=q['step_path'],source_sha256=q['source_sha256'],expected_volume_mm3=q['expected_volume_mm3'])
   if row['id'] in {p['id'] for p in fast['rows']}:
    row.update(change='R01_SELECTED_STANDARD_SOURCE_FRAME_REPLACEMENT',representation_role='SIMPLIFIED_PROXY',mass_source='GEOMETRY_STEEL7850_ESTIMATE_NOT_CATALOG_MASS',source_mass_kg=q['expected_volume_mm3']*7.85e-6)
  else:
   q=prior[row['id']];source=C/'mechanical/portable/package'/q['copy_name'];target=D/q['copy_name']
   assert sha(source)==q['source_sha256']
   if not target.exists():shutil.copy2(source,target)
   assert sha(target)==q['source_sha256'];copied[str(target)]=q['source_sha256']
   row.update(native_path=str(target),native_sha256=q['source_sha256'])
  if 'native_T_local_to_S' not in row:
   row['native_T_local_to_S']=prior[row['id']]['native_T_local_to_S']
  row['T_S_local']=row['native_T_local_to_S']
 changed=sorted(set(solarplan['changed_existing_ids'])|{q['id'] for q in fast['rows'] if q['scope'].startswith('SOURCE_FRAME')})
 assert len(changed)==152 and len(rows)==873
 base=C/'mechanical/portable/package'/portable['states'][state]['target_name']
 states[state]=dict(rows=rows,changed_existing_ids=changed,new_instance_ids=solarplan['new_instance_ids'],parent_path=str(base),parent_sha256=sha(base),parent_rows=portable['states'][state]['rows'],target_path=str(D/f'WP09D_{state.upper()}.SLDASM'))
out=dict(status='PREPARED_STEP_BOUND_NATIVE_IMPORT_PENDING',parts=records,states=states,copied_unchanged_parts=copied,
 source_receipts_sha256={str(p):sha(p) for p in [C/'results/PORTABLE_INPUTS.json',C/'results/PORTABLE_DELIVERY.json',C/'results/SOLAR_DELTA_STEP_BUILD.json',C/'mass/r01_geometry_delta/BUILD_RECEIPT.json']},
 component_count=873,expected_solids=1254,new_unique_shapes=138,changed_existing_instances=152,new_layer_instances=168,
 whole_cic_package_geometry_known=False,manufacturing_release=False,continuous_mechanism_verified=False)
(C/'results/NATIVE_DELTA_INPUTS.json').write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ('parts','states','copied_unchanged_parts')}))
