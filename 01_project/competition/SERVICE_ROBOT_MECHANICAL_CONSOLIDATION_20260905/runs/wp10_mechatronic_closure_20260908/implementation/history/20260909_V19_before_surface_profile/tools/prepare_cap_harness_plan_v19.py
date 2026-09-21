"""Append actual routed STEP conductors to the same 970-instance source plan."""
from pathlib import Path
import json,hashlib,copy
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
parent='mechanical/CHB_INPUT_INSTANCE_PLAN.json';p=json.loads((A/parent).read_text());added=[]
I=[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]
for name in ['PLUS','MINUS']:
 path='mechanical/cap_harness_'+name.lower()+'.step'
 added.append(dict(id='C203_W_'+name,step_path=str((A/path).resolve()),source_sha256=sha(path),T_S_step=I,representation_role='STRANDED_WIRE_AND_INSULATION_MAXIMUM_ENVELOPES_NOMINAL_STATIC_ROUTE',is_ground_only=False,native_geometry_current=False,mass_inertia_requalification='NOT_REQUALIFIED_IN_THIS_VARIANT',predecessor_ids=[]))
out=dict(schema='WP10_CAP_HARNESS_SOURCE_PLAN_V19',parent_plan=parent,parent_plan_sha256=sha(parent),component_count=972,states={},whole_fit_verified=False,whole_design_complete=False,inputs={'power/CAP_HARNESS_DEFINITION_V19.json':sha('power/CAP_HARNESS_DEFINITION_V19.json')})
for state,sp in p['states'].items():
 assert len(sp['rows'])==970
 out['states'][state]=dict(rows=copy.deepcopy(sp['rows'])+added,added_ids=[r['id'] for r in added],changed_ids=[],unchanged_parent_instances=970)
(A/'mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json').write_text(json.dumps(out,indent=2));print('972 source rows, original970 unchanged')
