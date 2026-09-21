"""Bind regenerated PCB/wires and four corrected screws to the same parent."""
from pathlib import Path
import json,copy
from c203_surface_generation_contract_v19 import A,SPECS,read,sha,validate_receipt
PARENT='mechanical/CHB_INPUT_INSTANCE_PLAN.json'
PROFILE='mechanical/C203_SURFACE_PROFILE_V19.json'
PLAN='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json'
CHANGED=['C203_PCB']+[f'C203_BOARD_SCREW_{i}' for i in range(4)]
ADDED=['C203_W_PLUS','C203_W_MINUS']
I=[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]

def validate_plan(plan,require_generated=True):
 parent=read(PARENT);profile=read(PROFILE)
 assert plan['parent_plan_sha256']==sha(PARENT)
 assert plan['source_surface_profile_sha256']==sha(PROFILE)
 assert plan['component_count']==972 and set(plan['states'])==set(parent['states'])
 assert all(sha(f)==h for f,h in plan['inputs'].items())
 if require_generated:
  assert not plan['surface_profile_pending'] and plan['source_geometry_fresh']
  records={k:validate_receipt(k) for k in SPECS}
 else:assert plan['surface_profile_pending'] and not plan['source_geometry_fresh']
 for state,st in plan['states'].items():
  old={r['id']:r for r in parent['states'][state]['rows']};new={r['id']:r for r in st['rows']}
  assert len(new)==len(st['rows'])==972 and len(old)==970
  assert set(new)-set(old)==set(ADDED) and st['changed_ids']==CHANGED and st['unchanged_parent_instances']==965
  assert all(new[k]==v for k,v in old.items() if k not in CHANGED)
  for i in range(4):
   key=f'C203_BOARD_SCREW_{i}';expected=copy.deepcopy(old[key])
   expected['T_S_step'][0][3]=profile['screw_underhead_x_mm']
   expected['representation_role']='NOMINAL_M3_HEAD_POSITION_DERIVED_FROM_NO_COPPER_BEARING_SURFACE'
   assert new[key]==expected
  for kind,spec in SPECS.items():
   r=new[spec['id']]
   assert r['T_S_step']==(old['C203_PCB']['T_S_step'] if kind=='pcb' else I)
   if require_generated:
    rec=records[kind]
    assert r['source_sha256']==rec['output_sha256'] and Path(r['step_path']).resolve()==(A/rec['output']).resolve()
    assert r['native_geometry_current'] and not r['geometry_regeneration_required']
    assert r['generation_receipt']==rec['receipt_path'] and r['generation_receipt_sha256']==sha(rec['receipt_path'])
   else:
    assert r['geometry_regeneration_required'] and not r.get('native_geometry_current',False)
    assert r['geometry_state']=='OLD_STEP_RETAINED_FOR_HISTORY__NOT_CURRENT_SURFACE_REVISION'
    source=f"mechanical/{spec['stem']}.step.py"
    assert r['expected_generator_source']==source and r['expected_generator_sha256']==sha(source)
 return True

def assemble(parent,profile,records):
 out=dict(schema='WP10_CAP_HARNESS_SOURCE_PLAN_V19',parent_plan=PARENT,parent_plan_sha256=sha(PARENT),component_count=972,states={},whole_fit_verified=False,whole_design_complete=False,
  surface_profile_pending=False,source_geometry_fresh=True,source_surface_profile=PROFILE,source_surface_profile_sha256=sha(PROFILE),
  inputs={f:sha(f) for f in [PARENT,PROFILE,'power/CAP_HARNESS_DEFINITION_V19.json','tools/prepare_cap_harness_plan_v19.py','tools/c203_surface_generation_contract_v19.py']})
 for rec in records.values():
  out['inputs'][rec['receipt_path']]=sha(rec['receipt_path'])
  out['inputs'][rec['guard_receipt']]=sha(rec['guard_receipt'])
 for state,sp in parent['states'].items():
  rows=copy.deepcopy(sp['rows']);assert len(rows)==970
  lookup={r['id']:r for r in rows};assert len(lookup)==970
  for i in range(4):
   r=lookup[f'C203_BOARD_SCREW_{i}'];assert r['T_S_step'][0][3]==-5.4
   assert [r['T_S_step'][j][2] for j in range(3)]==[-1,0,0]
   r['T_S_step'][0][3]=profile['screw_underhead_x_mm']
   r['representation_role']='NOMINAL_M3_HEAD_POSITION_DERIVED_FROM_NO_COPPER_BEARING_SURFACE'
  for kind,rec in records.items():
   name=SPECS[kind]['id']
   if kind=='pcb':r=lookup[name]
   else:
    r=dict(id=name,T_S_step=copy.deepcopy(I),representation_role='STRANDED_WIRE_AND_INSULATION_MAXIMUM_ENVELOPES_NOMINAL_STATIC_ROUTE',is_ground_only=False,mass_inertia_requalification='NOT_REQUALIFIED_IN_THIS_VARIANT',predecessor_ids=[]);rows.append(r)
   r.update(step_path=str((A/rec['output']).resolve()),source_sha256=rec['output_sha256'],native_geometry_current=True,geometry_regeneration_required=False,
    generation_receipt=rec['receipt_path'],generation_receipt_sha256=sha(rec['receipt_path']),geometry_state='SOURCE_BOUND_STEP_GENERATED__EXACT_CONTACT_AND_VISUAL_CHECKS_PENDING')
  out['states'][state]=dict(rows=rows,added_ids=ADDED,changed_ids=CHANGED,unchanged_parent_instances=965)
 return out

def main():
 import sys
 sys.path.insert(0,str(A/'mechanical'))
 from c203_pcb_surface_profile import definition
 profile=definition();records={k:validate_receipt(k) for k in SPECS}
 out=assemble(read(PARENT),profile,records);validate_plan(out)
 temp=A/(PLAN+'.tmp');temp.write_text(json.dumps(out,indent=2),encoding='utf-8');temp.replace(A/PLAN)
 print('972 instances: 965 unchanged, PCB and four screws revised, two wires added; exact fit remains unverified')
if __name__=='__main__':main()
