from pathlib import Path
import json,shutil,hashlib
R=Path(__file__).resolve().parents[1]; ROOT=R.parents[4]
d=json.loads((ROOT/'20_engineering/WP05_SW_20260907/results/PARTS_SOURCE_MANIFEST_DEDUP.json').read_text(encoding='utf-8'))
pp={x['part_key']:x for x in d['parts']}
b=json.loads((R/'inputs/baseline_job.json').read_text())
minimum={x for x in b['parts'] if not x.startswith('catalog:')}
changed={f'shear_web_{s}' for s in [-1,1]}|{f'lower_deck_angle_{s}_1' for s in [-1,1]}|{f'shear_clip_{s}_150_{z}' for s in [-1,1] for z in [-94,94]}
old={f'shear_web_screw_{s}_150_{z}' for s in [-1,1] for z in [-94,94]}
def near(x):
    a=x['bounds_mm'];lo,hi=a['min_mm'],a['max_mm']
    return hi[0]>=137 and lo[0]<=155 and any(hi[2]>=zc-5 and lo[2]<=zc+5 for zc in [-93.5,94]) and any(hi[1]>=yl and lo[1]<=yh for yl,yh in [(-157,-50),(50,157)])
rows={};states={}
source=R/'inputs/source';source.mkdir(exist_ok=True)
for state,st in d['states'].items():
    selected=[]
    for x in st['instances']:
        if x['id'] in old or x['id'] in changed:continue
        if x['id'] not in minimum and not near(x):continue
        key=x['id'];p=pp[x['part_key']];dest=source/Path(p['path']).name
        if not dest.exists():shutil.copy2(p['path'],dest)
        assert hashlib.sha256(dest.read_bytes()).hexdigest()==p['sha256']
        it=dict(id=key,path=str(dest),sha256=p['sha256'],T_S_local=x['T_S_local'],bounds_mm=x['bounds_mm'],role=x['representation_role'],parent_assembly=x['parent_assembly'],source_part_key=x['part_key'])
        selected.append(it)
        if state=='service':rows[key]=it
    states[state]=selected
data=dict(scope='All metadata instances scanned in three states; ROI [137,155] X, z axis +/-5, |Y|50..157 plus structural context',total_instances={s:len(x['instances']) for s,x in d['states'].items()},changed_ids=sorted(changed),replaced_ids=sorted(old),states=states)
(R/'inputs/CONTEXT.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print('context counts',{k:len(v) for k,v in states.items()});print([(x['id'],x['parent_assembly']) for x in rows.values()])
