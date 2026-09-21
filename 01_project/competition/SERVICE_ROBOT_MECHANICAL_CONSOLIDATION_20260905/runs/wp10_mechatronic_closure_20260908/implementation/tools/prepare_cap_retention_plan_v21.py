"""Integrate 971 byte-identical parent rows, one retained clamp, and two lace rows."""
from pathlib import Path
import json,copy,hashlib
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text())
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
def main():
 c=read('power/CAP_HARNESS_RETENTION_V21.json');parent=read(c['parent_plan']);assert sha(c['parent_plan'])==c['parent_plan_sha256']
 mapping={'lower':('C203_LOWER_B','cap21_lower_p02'),'plus':('C203_LACE_PLUS','cap21_plus_p01'),'minus':('C203_LACE_MINUS','cap21_minus_p01')}
 records={};inputs={p:sha(p) for p in [c['parent_plan'],'power/CAP_HARNESS_RETENTION_V21.json','tools/prepare_cap_retention_plan_v21.py']}
 for phase,(name,tag) in mapping.items():
  f=f'results/CAP_RETENTION_GENERATION_{phase.upper()}_V21.json';r=read(f)
  assert r['phase']==phase and all(sha(p)==h for p,h in r['inputs'].items()) and sha(r['output'])==r['output_sha256']
  sf=f'logs/CAP19_SERIAL_{tag}.json';s=read(sf);assert s['returncode']==0 and s['workspace_mutex_held'] and s['finished_local']
  resource=read(f'results/CAP_HARNESS_RESOURCE_{tag}_V19.json');assert resource['attempts'][-1]['status']=='COMPLETED'
  gf='logs/'+resource['attempts'][-1]['name']+'.run.json';g=read(gf)
  assert g['status']=='COMPLETED' and g['returncode']==0 and g['command'][-2:]==['tools/cap_retention_native_v21.py',phase]
  assert g['available_start_mib']>=2048 and g['max_child_tree_rss_mib']==1400
  r.update(receipt=f,guard=gf);records[name]=r
  for p in [f,sf,gf]:inputs[p]=sha(p)
 out=dict(schema='WP10_CAP_RETENTION_SAME_CANDIDATE_PLAN_V21',parent_plan=c['parent_plan'],parent_plan_sha256=sha(c['parent_plan']),component_count=974,states={},inputs=inputs,whole_fit_verified=False,whole_design_complete=False,strain_relief_complete=False)
 for state,st in parent['states'].items():
  rows=copy.deepcopy(st['rows']);lookup={r['id']:r for r in rows};assert len(rows)==len(lookup)==972
  for name,r in records.items():
   if name=='C203_LOWER_B':row=lookup[name]
   else:row=dict(id=name,T_S_step=I,is_ground_only=False,predecessor_ids=[],mass_inertia_requalification='NOT_REQUALIFIED');rows.append(row)
   row.update(step_path=str((A/r['output']).resolve()),source_sha256=r['output_sha256'],native_geometry_current=True,geometry_regeneration_required=False,generation_receipt=r['receipt'],generation_receipt_sha256=sha(r['receipt']),representation_role='SOURCE_DEFINED_RETENTION_CANDIDATE__INSTALLED_GRIP_AND_KNOT_UNQUALIFIED')
  assert all(next(x for x in rows if x['id']==r['id'])==r for r in st['rows'] if r['id']!='C203_LOWER_B')
  out['states'][state]=dict(rows=rows,changed_ids=['C203_LOWER_B'],added_ids=['C203_LACE_PLUS','C203_LACE_MINUS'],unchanged_parent_instances=971)
 (A/'mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json').write_text(json.dumps(out,indent=2))
 print('974 instances/state = 971 unchanged + 1 retained lower clamp + 2 lacing pieces')
if __name__=='__main__':main()

