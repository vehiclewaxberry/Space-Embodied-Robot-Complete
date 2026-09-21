"""Revise the same source definition; retain V14 evidence before actual edits."""
from pathlib import Path
import json,shutil
from input_passive_definition import PASSIVES
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V14_before_fuse_coordination'
for q in ['power/SHARED_BATTERY_PATH_DEFINITION.json','tools/check_shared_battery_path.py','tools/shared_battery_path.py','thermal/SHARED_BATTERY_HEAT_LOADS.csv','thermal/INPUT_PASSIVE_HEAT_LOADS.csv']:
 p=A/q;h=H/q
 if not h.exists():h.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,h)
p=A/'power/SHARED_BATTERY_PATH_DEFINITION.json';c=json.loads(p.read_text(encoding='utf-8-sig'))
c['schema']='WP10_SHARED_BATTERY_PATH_DEFINITION_V3'
c['active_geometry_plan']='mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json'
c['cases']['aux_branch_R_ohm']=[PASSIVES['F202']['typical_cold_R_ohm'],.04]
c['cases']['aux_branch_definition']='Total loop allocation includes F202 exactly once. 0.018 ohm is typical cold fuse alone plus ideal zero other path; 0.04 ohm includes 0.022 ohm unmeasured other path. Neither is a guaranteed hot/life resistance or installed circuit value.'
c['cases']['aux_zero_allocation_history']='history/20260909_V14_before_fuse_coordination/power/SHARED_BATTERY_PATH_DEFINITION.json'
c['cases']['aux_fuse_typical_cold_R_ohm']=PASSIVES['F202']['typical_cold_R_ohm']
c['cases']['aux_fuse_selection_source']='power/INPUT_PASSIVE_SELECTION.json:F202'
p.write_text(json.dumps(c,indent=2,ensure_ascii=False),encoding='utf-8')
print('F202 cold resistance bound once; old zero-branch sensitivities archived')
