"""Archive current V14 evidence before the V15 input-protection source revision."""
from pathlib import Path
import shutil
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V14_before_fuse_coordination'
paths=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv']
paths += ['tools/'+n for n in ['input_passive_definition.py','input_passive_footprint.py','integrate_power_loop.py','check_input_passives.py','export_input_passive_footprint.py','publish_input_cap_mount.py','seal_completed_package.py']]
paths += ['results/'+n for n in ['DELIVERY_DECISION.json','OUTPUT_SHA256.csv','INPUT_PASSIVE_READONLY_REVIEW.json','INPUT_CAP_MOUNT_READONLY_REVIEW.json','INPUT_CAP_MOUNT_EXACT.json','INPUT_CAP_VISUAL_REVIEW.json','INPUT_PASSIVE_FOOTPRINT_NATIVE.json','POWER_LOOP_VERIFICATION.json','POWER_LOOP_ERC.json','SHARED_BATTERY_READONLY_REVIEW.json','SHARED_BATTERY_PATH_REVIEW.json']]
paths += ['power/'+n for n in ['INPUT_PASSIVE_SELECTION.json','INPUT_PASSIVE_CALCULATIONS.json','SHARED_BATTERY_PATH_CALCULATIONS.json','POWER_CHAIN_SELECTION.json','SELECTED_BOM.csv','INPUT_PASSIVE_DESIGN.md']]
paths += ['ecad/'+n for n in ['wp10_system.xml','C203_MECHANICAL_INTERFACE.json']]
for q in paths:
 p=A/q;h=H/q
 if not h.exists():h.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,h)
print('V14 source and evidence archive prepared')
