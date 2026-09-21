from pathlib import Path
import json,copy,hashlib
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
parent='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json';p=json.loads((A/parent).read_text());d=json.loads((A/'power/CHB_INPUT_DEFINITION.json').read_text())
out=dict(schema='WP10_CHB_INPUT_SOURCE_PLAN_V18',parent_plan=parent,parent_plan_sha256=sha(parent),states={},component_count=970,whole_fit_verified=False,whole_design_complete=False,inputs={'power/CHB_INPUT_DEFINITION.json':sha('power/CHB_INPUT_DEFINITION.json')})
I=[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]
added=[]
def add(k,stem,xyz):
 t=copy.deepcopy(I)
 for i in range(3):t[i][3]=xyz[i]
 path='mechanical/chb_input_'+stem+'.step';added.append(dict(id=k,step_path=str((A/path).resolve()),source_sha256=sha(path),T_S_step=t,representation_role='PROJECT_NOMINAL_TERMINAL_HARDWARE',is_ground_only=False,native_geometry_current=False,mass_inertia_requalification='NOT_REQUALIFIED_IN_THIS_VARIANT',predecessor_ids=[]))
add('CHB_INPUT_PCB','pcb',[0,0,0])
for i,(x,y) in enumerate(d['mount_S_xy_mm']):
 add('CHB_INPUT_SPACER_'+str(i),'spacer',[x,y,d['spacer_z_mm'][0]]);add('CHB_INPUT_SCREW_'+str(i),'screw',[x,y,d['board_bounds_S_mm'][5]])
for state,sp in p['states'].items():
 assert len(sp['rows'])==965
 out['states'][state]=dict(rows=copy.deepcopy(sp['rows'])+added,added_ids=[r['id'] for r in added],changed_ids=[],unchanged_parent_instances=965)
(A/'mechanical/CHB_INPUT_INSTANCE_PLAN.json').write_text(json.dumps(out,indent=2))
print('970-instance source plan: prior965 unchanged, added5')
