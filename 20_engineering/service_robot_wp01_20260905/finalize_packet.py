"""Collect actual output evidence; never promote layout to hardware qualification."""
from pathlib import Path
import csv,hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
STATES=['stowed','initial_deploy','work']
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def report(path):
    text=path.read_text(encoding='utf-8-sig')
    try:return json.loads(text)
    except json.JSONDecodeError:
        for line in reversed(text.splitlines()):
            if line.startswith('{'):
                try:return json.loads(line)
                except json.JSONDecodeError:pass
    return dict(ok=False,reason='NO_FINAL_JSON',log=str(path.relative_to(HERE)))
pins=json.loads((HERE/'SOURCE_INPUTS.json').read_text());source_checks=[]
for row in pins:
    source_checks.append(dict(name=row['name'],source_matches=digest(ROOT/row['source'])==row['sha256'],copy_matches=digest(HERE/row['copy'])==row['sha256']))
entries=[('structure','frame_root_module')]+[(s,'service_robot_'+s) for s in STATES]
artifacts=[];pending=[];findings=[]
for state,stem in entries:
    step=HERE/(stem+'.step');valid=step.exists() and step.stat().st_size>0
    if not valid:pending.append(stem+'.step missing/empty')
    checks={}
    for kind,suffix in [('facts','_facts.log'),('validation','_validate.json'),('snapshot','_snapshot.log')]:
        path=HERE/'results'/(state+suffix)
        checks[kind]=report(path) if path.exists() else dict(ok=False,reason='MISSING')
        if not checks[kind].get('ok'):
            if kind=='validation' and 'failureCount' in checks[kind]:findings.append(dict(state=state,failure_count=checks[kind]['failureCount'],parts=checks[kind].get('parts',[])))
            else:pending.append(state+': '+kind+' incomplete')
    outputs=checks['snapshot'].get('outputs',[])
    images=[dict(path=o['path'],exists=Path(o['path']).is_file()) for o in outputs]
    artifacts.append(dict(state=state,source=stem+'.step.py',step=step.name,bytes=step.stat().st_size if valid else 0,sha256=digest(step) if valid else None,checks={k:dict(ok=v.get('ok'),failureCount=v.get('failureCount')) for k,v in checks.items()},snapshots=images))
trans=report(HERE/'results/TRANSFORM_TRANSFER.json');finger=report(HERE/'results/FINGER_INTERFACE_CHECK.json');interface=report(HERE/'results/INTERFACE_GEOMETRY.json')
receipts={s:report(HERE/'results'/(s+'_build_receipt.json')) for s in STATES}
result=dict(configuration='WP01_ROOF_EXTERNAL_R1',delivery_level='FIRST_PARAMETRIC_LAYOUT_AND_ASSEMBLY_CANDIDATE',delivery_status='PACKET_CHECKS_PENDING' if pending else 'DELIVERED_WITH_RECORDED_SOURCE_TOPOLOGY_FINDINGS',artifacts=artifacts,source_checks=source_checks,original_step_sources_unchanged=all(r['source_matches'] for r in source_checks),transform_transfer=trans['all_pass'],nominal_finger_clearance_mm=finger['minimum_compound_distance_mm'],interface_checks=interface,incomplete_tool_runs=pending,source_topology_findings=findings,hardware_assembly_completed=False,manufacturing_release=False,flight_qualification=False,continuous_motion_collision_validation=False,compact_stow_solved=False,mass_complete=False)
(HERE/'results/DELIVERY_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
rows=[]
for a in artifacts:
    if a['bytes']:rows.append(dict(path=a['step'],bytes=a['bytes'],sha256=a['sha256']))
for p in sorted(HERE.iterdir()):
    if p.suffix in ('.py','.json','.md','.csv') and p.name not in ('OUTPUT_SHA256.csv',):rows.append(dict(path=p.name,bytes=p.stat().st_size,sha256=digest(p)))
with (HERE/'OUTPUT_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(rows)
print(json.dumps(dict(step_files=sum(bool(a['bytes']) for a in artifacts),source_matches=result['original_step_sources_unchanged'],pending=pending),ensure_ascii=False))
