from pathlib import Path
import json
A=Path(__file__).resolve().parents[1]
rows=json.loads((A/'mechanical/CURRENT_936_SOURCE_BOUNDS.json').read_text())['states']['service']
for r in rows:
 if r['id'] in ['equipment_battery','adapter_battery','equipment_adcs_propulsion_allocation','adapter_adcs_propulsion_allocation','lower_equipment_deck_B','radiator_spreader'] or r['id'].startswith('P60_HOST_1'):
  print(json.dumps(dict(id=r['id'],bbox=r['bbox_S_mm'])))
for x,y in [(-70,45),(-74,50),(-74,-50),(-55,55),(-55,-55),(-50,0),(-48,60)]:
 q=[x-15.5,y-15.5,-79.95,x+15.5,y+15.5,-24.95]
 hit=[r['id'] for r in rows if not r['is_ground_only'] and all(r['bbox_S_mm'][i]<=q[i+3] and r['bbox_S_mm'][i+3]>=q[i] for i in range(3))]
 print(json.dumps(dict(cap_body_and_vent_center=[x,y],hits=hit)))

