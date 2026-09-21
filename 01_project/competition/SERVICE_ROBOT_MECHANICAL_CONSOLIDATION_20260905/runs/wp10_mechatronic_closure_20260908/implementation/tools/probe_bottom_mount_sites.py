from pathlib import Path
import json
A=Path(__file__).resolve().parents[1]
p=json.loads((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_text());rows=p['states']['service']['rows']
def overlap(a,b):return all(min(a[i+3],b[i+3])-max(a[i],b[i])>1e-6 for i in range(3))
out=[]
for x,y in [(-168,-65),(-168,65),(-60,-33),(-60,33),(140,-70),(140,70)]:
    hits={}
    for name,box in [('boss',[x-4,y-4,-106.15,x+4,y+4,-101.15]),('washer_nut',[x-3.5,y-3.5,-98.15,x+3.5,y+3.5,-95.25]),('tip',[x-1.5,y-1.5,-95.25,x+1.5,y+1.5,-94.15])]:
        hits[name]=[]
        for r in rows:
            if r['id'] in ['radiator_spreader','lower_equipment_deck_B'] or r['id'].startswith('WP10_BOTTOM_'):continue
            b=r.get('world_bounds_mm') or r.get('bounds_mm')
            if b and overlap(box,b['min_mm']+b['max_mm']):hits[name].append(r['id'])
    out.append(dict(center=[x,y],bbox_candidates=hits))
print(json.dumps(out,indent=2))
