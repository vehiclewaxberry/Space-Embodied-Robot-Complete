"""Derive all three same-candidate instance tables, preserving untouched rows."""
from pathlib import Path
import copy,csv,hashlib,json
import numpy as np
A=Path(__file__).resolve().parents[1]
P=A.parents[1]/'wp09_interfaces_20260907_1525/system_completion/results/NATIVE_DELTA_INPUTS.json'
I=[[1.,0,0,0],[0,1.,0,0],[0,0,1.,0],[0,0,0,1.]]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bbox(fs):return dict(min_mm=[min(f['bbox'][i] for f in fs) for i in range(3)],max_mm=[max(f['bbox'][i+3] for f in fs) for i in range(3)])
g=read(A/'results/FIXED_HEAT_GEOMETRY.json');assert g['checks_passed']
bottom=read(A/'thermal/BOTTOM_RADIATOR_MOUNT.json')
p=read(P);cfg=read(A/'thermal/FIXED_HEAT_PATH.json')
source_manifest=P.parents[2]/'results/INTEGRATION_MANIFEST_V6.json'
sm=read(source_manifest)
removed=['access_cover_-1','access_cover_1']+[f'cover_mount_{s}_{x}_{z}' for s in [-1,1] for x in [-150,0,150] for z in [-75,75]]
removed+=bottom['removed_instance_ids']
moved=[f'CLAMP_DUAL_{i}_{tag}' for i in [0,1] for tag in ['BN','BW','TN','TW']]+['CLAMP_DUAL_BASE','CLAMP_DUAL_LID','POST_DUAL_0','POST_DUAL_1','TIEROD_DUAL_0','TIEROD_DUAL_1']
replaced={'shear_web_-1':'fixed_heat_wall_neg','shear_web_1':'fixed_heat_wall_pos','upper_equipment_deck_B':'upper_deck_relocated','PROP_PWR_ROUTE':'propulsion_power_route','PROP_DATA_ROUTE':'propulsion_data_route'}
replaced.update(radiator_spreader='bottom_radiator',lower_equipment_deck_B='lower_deck_bottom_mount')
replaced.update({key:'bottom_'+key for key in bottom['baseline_angles']})
new=[]
for d in cfg['devices']:
    key=d['id'];x,z=d['center_xz_mm'];s=d['side'];y=s*(d['carrier_back_abs_y_mm']-d['carrier_size_mm'][2]);tt=d['TIM_mm'][2]
    if key=='U202_CHB':
        if d.get('mount_type')=='BOTTOM_PEDESTAL':
            x,y,z=d['seat_origin_S_mm']
            timT=[[1,0,0,x],[0,1,0,y],[0,0,1,z],[0,0,0,1]]
            rawT=[[1,0,0,x],[0,0,-1,y],[0,1,0,z+tt+1.6],[0,0,0,1]]
        else:
            timT=[[1,0,0,x],[0,0,-1,y],[0,1,0,z],[0,0,0,1]]
            rawT=[[1,0,0,x],[0,-1,0,y-tt-1.6],[0,0,-1,z],[0,0,0,1]]
        oem='sources/CHB500W_STANDARD_OEM.step';tim='mechanical/chb_bottom_tim.step' if d.get('mount_type')=='BOTTOM_PEDESTAL' else 'mechanical/converter_tim.step'
    else:
        timT=[[0,1,0,x],[0,0,1,y],[1,0,0,z],[0,0,0,1]]
        rawT=copy.deepcopy(timT);rawT[1][3]+=tt+.2
        oem='sources/LPS300_OEM.step';tim='mechanical/brake_tim.step'
    ids=g['groups'][key]
    for suffix,source,T,indexes in [('_TIM',tim,timT,ids[:1]),('',oem,rawT,ids[1:])]:
        fs=[g['facts'][i] for i in indexes];bb=bbox(fs)
        new.append(dict(id=key+suffix,step_path=str(A/source),source_sha256=sha(A/source),T_S_local=T,T_S_step=T,native_T_local_to_S=T,
          native_path=None,native_sha256=None,world_bounds_mm=bb,bounds_mm=None,
          expected_solids=len(fs),expected_volume_mm3=sum(f['measure'] for f in fs),representation_role='OEM_GEOMETRY' if suffix=='' else 'SOURCE_BOUND_TIM_PROJECT_CUT',
          source_mass_kg=None,mass_source='NOT_INHERITED_FROM_MATERIAL_VOLUME',ecad_ref=d.get('ecad_ref',key) if suffix=='' else None,
          body_evidence='SOURCE_DELTA_STEP_READBACK_NOT_FULL_NATIVE_ASSEMBLY',change='ADD_WP10_FIXED_HEAT_PATH'))
for i,(x,y) in enumerate(bottom['mount_centers_xy_mm']):
    for tag,z in [('SCREW',bottom['outer_z_mm']),('WASHER',bottom['deck_top_z_mm']),('NUT',bottom['deck_top_z_mm']+bottom['hardware']['washer_thickness_mm'])]:
        source=A/'mechanical'/f'bottom_mount_{tag.lower()}.step';T=copy.deepcopy(I);T[0][3]=x;T[1][3]=y;T[2][3]=z
        new.append(dict(id=f'WP10_BOTTOM_{i}_{tag}',step_path=str(source),source_sha256=sha(source),T_S_step=T,T_S_local=T,native_T_local_to_S=T,
          native_path=None,native_sha256=None,world_bounds_mm=None,bounds_mm=None,expected_solids=1,expected_volume_mm3=None,
          representation_role='PUBLIC_DIMENSION_BOUND_PROJECT_NOMINAL_GEOMETRY',source_mass_kg=None,mass_source='NOT_YET_BOUND',
          ecad_ref=None,body_evidence='SOURCE_DELTA_STEP_READBACK_NOT_FULL_NATIVE_ASSEMBLY',change='ADD_BOTTOM_MOUNT_HARDWARE'))
c=bottom.get('chb_path')
if c and c['enabled']:
    extra=[];x,y=c['center_xy_mm']
    for i,(dx,dy) in enumerate(( (dx,dy) for dx in c['oem_hole_x_offsets_mm'] for dy in c['oem_hole_y_offsets_mm'])):
        extra.append((f'WP10_CHB_{i}_SCREW','bottom_mount_screw',[[1,0,0,x+dx],[0,1,0,y+dy],[0,0,1,bottom['outer_z_mm']],[0,0,0,1]]))
    for sign in [-1,1]:
        x,z=c['wall_contact_center_xz_mm'];y=sign*c['wall_seat_abs_y_mm']
        extra.append((f'WP10_COLD_{sign}_TIM','cold_finger_tim',[[1,0,0,x],[0,0,-sign,y],[0,sign,0,z],[0,0,0,1]]))
        for i,(x,z) in enumerate(c['wall_screw_centers_xz_mm']):
            extra.append((f'WP10_COLD_{sign}_{i}_SCREW','bottom_mount_screw',[[1,0,0,x],[0,0,-sign,sign*113.15],[0,sign,0,z],[0,0,0,1]]))
    for key,stem,T in extra:
        source=A/'mechanical'/f'{stem}.step'
        new.append(dict(id=key,step_path=str(source),source_sha256=sha(source),T_S_step=T,T_S_local=T,native_T_local_to_S=T,native_path=None,native_sha256=None,world_bounds_mm=None,bounds_mm=None,expected_solids=1,expected_volume_mm3=None,representation_role='SOURCE_BOUND_TIM_PROJECT_CUT' if stem=='cold_finger_tim' else 'PUBLIC_DIMENSION_BOUND_PROJECT_NOMINAL_GEOMETRY',source_mass_kg=None,mass_source='NOT_YET_BOUND',ecad_ref=None,body_evidence='SOURCE_DELTA_STEP_READBACK_NOT_FULL_NATIVE_ASSEMBLY',change='ADD_CHB_BOTTOM_COLD_PATH_HARDWARE'))
expected_count=873-len(removed)+len(new)
states={};frame_repairs={}
for state,old in p['states'].items():
    assert len(old['rows'])==873
    rows=copy.deepcopy(old['rows']);oldids={r['id'] for r in rows}
    source_rows={r['id']:r for r in sm['states'][state]['instances']}
    baseline_native={r['id']:r for r in old['parent_rows']}
    frame_repairs[state]=[]
    assert set(removed+moved+list(replaced))<=oldids
    rows=[r for r in rows if r['id'] not in removed]
    for r in rows:
        key=r['id']
        if not r.get('step_path') and r.get('source_step'):
            r['step_path']=r['source_step']['path'];r['source_sha256']=r['source_step']['sha256']
        sr=source_rows.get(key)
        if sr and sr.get('source_sha256')==r.get('source_sha256'):
            # Equal geometry SHA does not mean equal instance placement.
            # Preserve later solar-wing4.5mm pitch changes while undoing only
            # the baseline source/native frame difference (e.g. P60 sourceS).
            br=baseline_native[key]
            assert br['source_sha256']==r['native_sha256'],(state,key,'BASELINE_NATIVE_GEOMETRY_CHANGED')
            current=np.asarray(r['native_T_local_to_S'],float);base=np.asarray(br['native_T_local_to_S'],float)
            delta=current@np.linalg.inv(base)
            r['T_S_step']=(delta@np.asarray(sr['T_S_local'],float)).tolist()
            r['STEP_frame_basis']='V6_STEP_FRAME_PLUS_CURRENT_VS_BASELINE_NATIVE_RIGID_DELTA__BOTH_GEOMETRY_HASHES_MATCH'
            if np.max(np.abs(delta-np.eye(4)))>1e-7:
                frame_repairs[state].append(dict(id=key,old_stale_T_S_step=sr['T_S_local'],current_T_S_step=r['T_S_step'],
                  current_vs_baseline_native_delta=delta.tolist(),STEP_sha256=r['source_sha256'],native_sha256=r['native_sha256']))
        else:
            r['T_S_step']=copy.deepcopy(r['native_T_local_to_S'])
            r['STEP_frame_basis']='LATER_DELTA_EMISSION_SAME_SOURCE_NATIVE_FRAME_OR_WP09F_IDENTITY'
        if key in replaced:
            source=A/'mechanical'/(replaced[key]+'.step');assert source.exists()
            r['parent_native_lineage']=r.get('native');r['native']=None
            r['source_step']=dict(path=str(source),sha256=sha(source))
            r['source_revision']='WP10_FIXED_HEAT_PATH_CANDIDATE_V1'
            r.update(step_path=str(source),source_sha256=sha(source),T_S_local=copy.deepcopy(I),T_S_step=copy.deepcopy(I),native_T_local_to_S=copy.deepcopy(I),
              native_path=None,native_sha256=None,expected_volume_mm3=None,bounds_mm=None,world_bounds_mm=None,
              source_mass_kg=None,mass_source='RECOMPUTE_CHANGED_GEOMETRY',change='REPLACE_WP10_FIXED_HEAT_DEPENDENCY',body_evidence='SOURCE_DELTA_FULL_NATIVE_PENDING')
        elif key in moved:
            r['T_S_step'][0][3]+=6;r['T_S_step'][1][3]-=10
            T=copy.deepcopy(r['native_T_local_to_S']);T[0][3]+=6;T[1][3]-=10
            r.update(T_S_local=T,native_T_local_to_S=T,change='RIGID_RELOCATION_S_X_PLUS6_Y_MINUS10MM',body_evidence='SOURCE_TRANSFORM_FULL_NATIVE_PENDING')
            for bkey in ['bounds_mm','world_bounds_mm']:
                if r.get(bkey):
                    r[bkey]['min_mm'][0]+=6;r[bkey]['max_mm'][0]+=6
                    r[bkey]['min_mm'][1]-=10;r[bkey]['max_mm'][1]-=10
    rows.extend(copy.deepcopy(new));assert len(rows)==expected_count and len({r['id'] for r in rows})==expected_count
    states[state]=dict(rows=rows,parent_873_path=old['target_path'],parent_input_sha256=sha(P),
      removed_ids=removed,moved_ids=moved,changed_shape_ids=list(replaced),new_ids=[r['id'] for r in new],
      target_native_assembly=str(A/'mechanical'/f'WP10_FIXED_HEAT_{state.upper()}.SLDASM'),full_native_exported=False)
out=dict(schema='WP10_FIXED_HEAT_INSTANCE_PLAN_V1',status='ALL_THREE_SOURCE_INSTANCE_TABLES_DERIVED__NATIVE_BUILD_PENDING',
  parent_path=str(P),parent_sha256=sha(P),STEP_source_manifest=str(source_manifest),STEP_source_manifest_sha256=sha(source_manifest),sealed_parent_count=873,candidate_component_count=expected_count,states=states,
  bottom_mount_config_sha256=sha(A/'thermal/BOTTOM_RADIATOR_MOUNT.json'),battery_old_thermal_link_disposition=bottom['battery_disposition'],
  top_level_group_transforms=I,no_double_transform_rule='Source-frame replacement solids and grouping roots use identity',
  new_ref_double_count=False,old_local_carrier_models_role='COMPONENT_STUDIES_NOT_EXTRA_INTEGRATED_INSTANCES',
  local_bay_step=str(A/'mechanical/fixed_heat_bay.step'),local_bay_sha256=sha(A/'mechanical/fixed_heat_bay.step'),
  whole_native_assembly_verified=False,collision_verified=False)
(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
(A/'results/FIXED_HEAT_STEP_FRAME_REPAIR.json').write_text(json.dumps(dict(schema='WP10_STEP_FRAME_RIGID_DELTA_REPAIR_V1',
  cause='Same STEP geometry SHA was incorrectly used to imply same instance pose; later wing spacing had been lost',
  parent_native_baseline_source=str(P),source_sha256=sha(P),repairs_by_state=frame_repairs,
  repaired_source_plan_sha256=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json'),
  geometry_unchanged=True,old_P60_source_vs_native_frame_fix_preserved=True,
  independent_STEP_corner_readback_verified=False,full_assembly_verified=False),ensure_ascii=False,indent=2),encoding='utf-8')
items=[dict(id=k,operation='REMOVE_UNQUALIFIED_BATTERY_THERMAL_LINK' if k=='battery_thermal_link' else 'REMOVE_REPLACED_COVER_SYSTEM',quantity=-1) for k in removed]+[
 dict(id=k,operation='REPLACE_SHAPE_SAME_ID',quantity=0) for k in replaced]+[
 dict(id=k,operation='MOVE_S_X_PLUS6_Y_MINUS10',quantity=0) for k in moved]+[
 dict(id=r['id'],operation='ADD_BOTTOM_MOUNT_HARDWARE' if r['id'].startswith('WP10_BOTTOM_') else 'ADD_ECAD_REF_OR_TIM_ONCE',quantity=1) for r in new]
with (A/'mechanical/FIXED_HEAT_BOM_DELTA.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
print(json.dumps(dict(parent=873,candidate=expected_count,removed=len(removed),moved=len(moved),replaced=len(replaced),added=len(new),native_assembly=False)))
