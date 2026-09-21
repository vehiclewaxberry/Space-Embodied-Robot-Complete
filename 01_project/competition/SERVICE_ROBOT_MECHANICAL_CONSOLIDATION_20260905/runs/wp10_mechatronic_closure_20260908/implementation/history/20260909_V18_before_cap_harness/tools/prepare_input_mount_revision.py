from pathlib import Path
import shutil
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V13_before_cap_mount'
paths=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','tools/build_input_passive_revision.py','tools/integrate_power_loop.py','tools/check_input_passives.py','tools/publish_input_passive_addendum.py','tools/seal_completed_package.py']
paths += ['results/'+p for p in ['DELIVERY_DECISION.json','POWER_LOOP_VERIFICATION.json','POWER_LOOP_ERC.json','INPUT_PASSIVE_READONLY_REVIEW.json','SHARED_BATTERY_PATH_REVIEW.json','SHARED_BATTERY_READONLY_REVIEW.json','OUTPUT_SHA256.csv']]
paths += ['power/'+p for p in ['INPUT_PASSIVE_CALCULATIONS.json','INPUT_PASSIVE_DESIGN.md','SHARED_BATTERY_PATH_DESIGN.md','SHARED_BATTERY_PATH_CALCULATIONS.json','POWER_CHAIN_SELECTION.json']]
for q in paths:
 p=A/q;h=H/q
 if not h.exists():h.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,h)
p=A/'tools/check_input_passives.py';s=p.read_text(encoding='utf-8')
start=s.index("out=A/'ecad/WP10_PASSIVES.pretty'");end=s.index("parts=read('power/POWER_LOOP_PARTS.json')")
body=s[start:end]
source='"""Build dimensional C203 footprint before native schematic verification."""\nfrom pathlib import Path\nfrom input_passive_definition import PASSIVES\nA=Path(__file__).resolve().parents[1]\ndef build_footprint():\n    c=PASSIVES["C203"]\n'+''.join('    '+line+'\n' for line in body.splitlines())+'    return name\n\nif __name__=="__main__":print(build_footprint())\n'
(A/'tools/input_passive_footprint.py').write_text(source,encoding='utf-8')
s=s[:start]+"from input_passive_footprint import build_footprint\nname=build_footprint()\n"+s[end:]
p.write_text(s,encoding='utf-8')
p=A/'tools/integrate_power_loop.py';s=p.read_text(encoding='utf-8')
s=s.replace('from input_passive_definition import PASSIVES','from input_passive_definition import PASSIVES\nfrom input_passive_footprint import build_footprint\nbuild_footprint()')
p.write_text(s,encoding='utf-8')
print('Archived V13 and moved footprint generation ahead of native export.')

