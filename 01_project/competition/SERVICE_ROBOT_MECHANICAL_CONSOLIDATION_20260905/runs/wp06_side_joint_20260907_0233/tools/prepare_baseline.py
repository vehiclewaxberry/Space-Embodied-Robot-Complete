from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parents[1]
ROOT=R.parents[4]
W5=ROOT/'20_engineering/WP05_SW_20260907'
W4=R.parent/'wp04_robot_assembly_20260906_175153'
manifest=W5/'results/PARTS_SOURCE_MANIFEST_DEDUP.json'
d=json.loads(manifest.read_text(encoding='utf-8'))
parts={p['part_key']:p for p in d['parts']}
instances={p['id']:p for p in d['states']['service']['instances']}
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def item(id):
    i=instances[id]; p=parts[i['part_key']]
    return dict(path=p['path'],sha256=p['sha256'],T_S_local=i['T_S_local'])
ids=[]
for side in [-1,1]:
    ids.extend([f'shear_web_{side}',f'lower_deck_angle_{side}_1'])
    for z in [-94,94]:
        ids.extend([f'{kind}_{side}_150_{z}' for kind in ['shear_clip','shear_web_screw','shear_rail_screw']])
    ids.extend([f'RB_longeron_{side}_{s}' for s in [-1,1]])
ids+=['RB_pillar_2','RB_pillar_3','RB_upper_beam_160','RB_lower_beam_160','RB_lower_spacer_2','RB_lower_spacer_3']
ids += [x for x in instances if 'lower' in x and 'deck' in x and 'angle' not in x and 'screw' not in x and 'washer' not in x and 'nut' not in x]
print('deck IDs',ids[26:])
job=dict(parts={id:item(id) for id in dict.fromkeys(ids)},tests=[],tolerances=dict(linear_mm=1e-5,volume_mm3=1e-5,integration_eps=1e-9),output=str(R/'results/BASELINE_ACTUAL_STEP.json'))
for id in job['parts']:job['tests'].append(dict(id='facts:'+id,kind='facts',part=id))
for side in [-1,1]:
    for z in [-94,94]:
        job['tests'].append(dict(id=f'old_screw_pillar:{side}:{z}',kind='clearance',a=f'shear_web_screw_{side}_150_{z}',b=f'RB_pillar_{2 if side==-1 else 3}',min_mm=.5))
for p in (R/'inputs/catalog').glob('*.step'):
    key='catalog:'+p.stem
    job['parts'][key]=dict(path=str(p),sha256=sha(p),T_S_local=I)
    job['tests'].append(dict(id='facts:'+key,kind='facts',part=key))
(R/'inputs/baseline_job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
files=[manifest,*[W4/'candidate'/x for x in ['r01_design.py','r07_design.py','design_parameters.json','spacecraft_model.py','root_structure.py']],*[Path(x['path']) for x in job['parts'].values()]]
receipt=dict(created_local=datetime.datetime.now().astimezone().isoformat(),role='IMMUTABLE_INPUT_BASELINE_NOT_A_GATE',files=[dict(path=str(p),sha256=sha(p)) for p in dict.fromkeys(files)],four_joint_state_identity={})
for id in [x for x in ids if x.startswith('shear_web_screw')]:
    actual=[next(x for x in state['instances'] if x['id']==id) for state in d['states'].values()]
    receipt['four_joint_state_identity'][id]=len({json.dumps([x['part_key'],x['T_S_local']]) for x in actual})==1
(R/'inputs/SOURCE_BASELINE.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(dict(part_count=len(job['parts']),tests=len(job['tests']),output=job['output'])))
