from pathlib import Path
import json,hashlib,runpy
A=Path(__file__).resolve().parents[1];core=runpy.run_path(str(A/'tools/check_fixed_heat_geometry.py'))
P=A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json';plan=json.loads(P.read_text());p=json.loads((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_text())
chosen=['radiator_spreader','lower_equipment_deck_B',*p['baseline_angles'],'U202_CHB','U202_CHB_TIM','shear_web_-1','shear_web_1']
rows=[dict(r) for r in plan['states']['service']['rows'] if r['id'] in chosen or r['id'].startswith(('WP10_BOTTOM_','WP10_CHB_','WP10_COLD_'))];assert len(rows)==38
parts=[];unique={};folder=A/'mechanical/native';folder.mkdir(exist_ok=True)
for r in rows:
    path=Path(r['step_path']);digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==r['source_sha256']
    if digest not in unique:
        shape=core['read'](path);f=core['prop'](shape);assert len(core['parts'](shape))==1;key=f'C{len(parts):02d}'
        q=dict(id=key,step_path=str(path),source_sha256=digest,native_path=str(folder/(key+'.SLDPRT')),expected_solids=1,expected_volume_mm3=f['measure'],expected_local_bbox_mm=dict(min_mm=f['bbox'][:3],max_mm=f['bbox'][3:]),representation_role=r.get('representation_role','PROJECT_MODIFIED_SOURCE_GEOMETRY'))
        unique[digest]=q;parts.append(q)
    q=unique[digest];r.update(native_path=q['native_path'],native_part_id=q['id'],T_S_local=r['T_S_step'],expected_solids=1)
assert len(parts)==14 and max(len(r['native_path']) for r in rows)<250
out=dict(schema='WP10_COLD_PATH_NATIVE_INPUTS_V1',source_plan_sha256=hashlib.sha256(P.read_bytes()).hexdigest(),parts=parts,rows=rows,assembly_path=str(folder/'WP10_THERMAL_CORE.SLDASM'),coordinate_frame='STRUCTURAL_S_SOURCE_IDENTITY_AND_EXPLICIT_OEM_AND_HARDWARE_T_S_STEP',fixed_pose_only=True,whole894_native_integrated=False)
(A/'mechanical/NATIVE_COLD_INPUTS.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(parts=len(parts),instances=len(rows))))
