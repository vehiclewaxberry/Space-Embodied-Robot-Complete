from pathlib import Path
import json
A=Path(__file__).resolve().parents[1]
p=json.loads((A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json').read_text())
print('plan_keys',list(p))
for r in p['states']['service']['rows']:
 if any(x in r['id'].lower() for x in ['chb','bottom','pdu','battery']):
  print(json.dumps(r))
q=json.loads((A/'thermal/FIXED_HEAT_PATH.json').read_text())
print('devices',json.dumps(q['devices']))

