"""Verify unchanged arm row/geometry reuse without importing CAD."""
from pathlib import Path
import json,hashlib
MODE='FRESH_NONARM_PLUS_HASH_LOCKED_UNCHANGED_ARM'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def validate_composition(d,here):
    here=Path(here);c=d.get('composition')
    if d.get('composition_mode')!=MODE or not isinstance(c,dict):raise ValueError('MISSING_COMPOSITION_CONTRACT')
    if d.get('monolithic_complete_step_generated') is not False:raise ValueError('FALSE_MONOLITHIC_STEP_CLAIM')
    for name in ['builder','input_extension','original_receipt','fresh_nonarm_receipt','assembly_index']:
        ref=c.get(name,{})
        if not ref.get('path') or sha(ref['path'])!=ref.get('sha256'):raise ValueError('COMPOSITION_SOURCE_DRIFT:'+name)
    if Path(c['builder']['path']).resolve()!=here/'compose_receipts.py':raise ValueError('WRONG_COMPOSITION_BUILDER')
    old=load(c['original_receipt']['path']);fresh=load(c['fresh_nonarm_receipt']['path']);ext=load(c['input_extension']['path'])
    if d['geometry_sha256'].get(c['original_receipt']['path'])!=c['original_receipt']['sha256']:raise ValueError('ORIGINAL_RECEIPT_NOT_GEOMETRY_BOUND')
    manifest=load(here.parent/'inputs/INPUT_MANIFEST.json')
    if ext['initial_manifest_sha256']!=sha(here.parent/'inputs/INPUT_MANIFEST.json'):raise ValueError('INPUT_EXTENSION_PARENT_DRIFT')
    locked={r['path']:r['sha256'] for r in manifest['source_snapshot']}
    if locked.get(str(Path(c['original_receipt']['path'])))!=c['original_receipt']['sha256']:raise ValueError('OLD_RECEIPT_NOT_ORIGINAL_LOCKED_INPUT')
    old_home=Path(c['original_receipt']['path']).parents[1]
    if sha(old_home/'spacecraft_model.py')!=old['source_sha256']:raise ValueError('OLD_SOURCE_DRIFT')
    for name,h in old['dependency_sha256'].items():
        if sha(old_home/name)!=h:raise ValueError('OLD_DEPENDENCY_DRIFT:'+name)
    for name in ['state','view','q_deg','finger_mm','T_S_arm_base','link_transforms']:
        if d[name]!=old[name] or d[name]!=fresh[name]:raise ValueError('REUSED_ARM_POSE_DRIFT:'+name)
    if d['source_sha256']!=fresh['source_sha256']:raise ValueError('FRESH_SOURCE_MISMATCH')
    for name,h in fresh['dependency_sha256'].items():
        if d['dependency_sha256'].get(name)!=h:raise ValueError('FRESH_DEPENDENCY_MISMATCH:'+name)
    for rows in [old['instances'],d['instances']]:
        arm_rows=[r for r in rows if r.get('arm_link')]
        if len(arm_rows)!=10 or len({r['arm_link'] for r in arm_rows})!=10:raise ValueError('ARM_ROWS_NOT_EXACTLY_TEN_UNIQUE')
    old_arm={r['arm_link']:r for r in old['instances'] if r.get('arm_link')};new_arm={r['arm_link']:r for r in d['instances'] if r.get('arm_link')}
    if len(old_arm)!=10 or len(new_arm)!=10 or set(old_arm)!=set(new_arm):raise ValueError('INCOMPLETE_ARM_IDENTITY')
    sources=c.get('arm_sources',{})
    if set(sources)!=set(old_arm):raise ValueError('INCOMPLETE_ARM_GEOMETRY_MAPPING')
    for name,row in old_arm.items():
        new=dict(new_arm[name]);ref=new.pop('geometry_reuse',None)
        if new!=row or ref!=sources[name]:raise ValueError('REUSED_ARM_ROW_CHANGED:'+name)
        if Path(ref['path']).name!=name+'.step' or sha(ref['path'])!=ref['sha256']:raise ValueError('ARM_BREP_DRIFT:'+name)
        if ext['source_sha256'].get(ref['path'])!=ref['sha256'] or d['geometry_sha256'].get(ref['path'])!=ref['sha256']:raise ValueError('ARM_BREP_NOT_BOUND:'+name)
    for path,h in ext['source_sha256'].items():
        if sha(path)!=h:raise ValueError('INPUT_EXTENSION_DRIFT')
    fresh_rows={r['id']:r for r in fresh['instances']}
    actual={r['id']:r for r in d['instances'] if not r.get('arm_link')}
    if actual!=fresh_rows:raise ValueError('NONARM_ROW_CHANGED')
    step=c['fresh_nonarm_step']
    if sha(step['path'])!=step['sha256'] or d['geometry_sha256'].get(step['path'])!=step['sha256']:raise ValueError('NONARM_FINAL_STEP_NOT_BOUND')
    ids=[r['id'] for r in d['instances']]
    interface_ids=[r['instance'] for r in d['interfaces']]
    if len(ids)!=len(set(ids)) or len(interface_ids)!=len(set(interface_ids)) or set(ids)!=set(interface_ids):raise ValueError('COMPOSITE_INTERFACE_COVERAGE')
    index=load(c['assembly_index']['path'])
    if index['configuration']!=d['configuration'] or index['state']!=d['state'] or index['composition_mode']!=MODE:raise ValueError('WRONG_ASSEMBLY_INDEX')
    nonarm_ids=index.get('nonarm_instance_ids',[])
    if len(nonarm_ids)!=len(set(nonarm_ids)) or set(nonarm_ids)!=set(fresh_rows):raise ValueError('INDEX_NONARM_IDENTITY')
    ar=index['arm_occurrences']
    if len(ar)!=10 or len({r['arm_link'] for r in ar})!=10 or len({r['id'] for r in ar})!=10:raise ValueError('INDEX_ARM_DUPLICATES')
    if index['nonarm_step']!=step or {r['arm_link']:r['geometry'] for r in ar}!=sources:raise ValueError('INDEX_GEOMETRY_MAPPING')
    for row in index['arm_occurrences']:
        if row['T_S_local']!=new_arm[row['arm_link']]['T_S_local'] or row['id']!=new_arm[row['arm_link']]['id']:raise ValueError('INDEX_TRANSFORM_DRIFT')
    lo=[min(r['bounds']['min_mm'][i] for r in d['instances']) for i in range(3)];hi=[max(r['bounds']['max_mm'][i] for r in d['instances']) for i in range(3)]
    if d['bounds']!={'min_mm':lo,'max_mm':hi,'size_mm':[hi[i]-lo[i] for i in range(3)]}:raise ValueError('COMPOSITE_BOUNDS_ERROR')
    return True
