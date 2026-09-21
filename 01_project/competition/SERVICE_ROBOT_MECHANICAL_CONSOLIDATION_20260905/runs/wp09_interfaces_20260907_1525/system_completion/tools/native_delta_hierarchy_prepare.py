"""Freeze two-level, identity-parent fixed assembly groups without CAD changes."""
from pathlib import Path
import json,hashlib,datetime,psutil,shutil
C=Path(__file__).resolve().parents[1];D=C/'cad';R=C/'results'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not [p for p in psutil.process_iter(['name']) if p.info['name'].lower()=='sldworks.exe']
archive=C/'logs/native_delta_interrupted_v3';archive.mkdir(exist_ok=True)
for rel in ('results/NATIVE_DELTA_INTEGRATE_service.json','cad/W_service.SLDASM','cad/~$W_service.SLDASM'):
 old=(C/rel).resolve();assert old.is_relative_to(C.resolve())
 if old.exists():
  dest=(archive/old.name).resolve();assert dest.is_relative_to(C.resolve()) and not dest.exists()
  digest=sha(old);old.rename(dest);assert sha(dest)==digest
inputs=R/'NATIVE_DELTA_INPUTS.json';snapshot=R/'NATIVE_DELTA_IMPORTED_PARTS.json'
j=json.loads(inputs.read_text());seal=json.loads(snapshot.read_text());parts={p['id']:p for p in seal['parts']}
groups={};states={}
for state,s in j['states'].items():
 rows=sorted(s['rows'],key=lambda x:x['id'])
 for q in rows:
  if q.get('native_delta_part_id'):q['native_sha256']=parts[q['native_delta_part_id']]['native_sha256']
  assert sha(q['native_path'])==q['native_sha256']
 state_groups=[]
 for start in range(0,len(rows),96):
  subset=rows[start:start+96]
  contract=[{k:q[k] for k in ('id','native_path','native_sha256','T_S_local','expected_solids')} for q in subset]
  digest=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  key='G_'+digest[:12]
  if key in groups:assert groups[key]['row_contract_sha256']==digest
  else:groups[key]={'id':key,'path':str(D/(key+'.SLDASM')),'row_contract_sha256':digest,'rows':subset,'leaf_component_count':len(subset)}
  state_groups.append(key)
 states[state]={'groups':state_groups,'top_level_container_count':len(state_groups),'leaf_component_count':len(rows),'target_path':s['target_path']}
out=R/'NATIVE_DELTA_HIERARCHY_INPUTS.json';assert not out.exists()
r={'status':'FIXED_TWO_LEVEL_HIERARCHY_INPUT_FROZEN_NOT_NATIVE_ACCEPTANCE','input_manifest_sha256':sha(inputs),'imported_parts_snapshot_sha256':sha(snapshot),'group_leaf_limit':96,'group_count':len(groups),'groups':list(groups.values()),'states':states,'parent_transform_sw16':[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],'transform_rule':'Each group container is fixed at identity. Leaf original native T is retained; actual parent identity is cold-read and checked, preventing double multiplication.','leaf_count_each':873,'expected_solids_each_hash_bound':1254,'manufacturing_release':False,'continuous_motion_verified':False}
out.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({'path':str(out),'sha256':sha(out),'unique_groups':len(groups),'state_container_counts':{k:v['top_level_container_count'] for k,v in states.items()},'leaf_limit':96}))
