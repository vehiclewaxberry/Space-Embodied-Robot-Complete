"""Prepare WP07 three-state metadata using only stdlib file reads and hashes.

No CAD imports, geometry loading, or COM calls are made. The output is a bound
composition plan; subsequent native edits and actual cold checks remain required.
"""
from pathlib import Path
import ast
import collections
import copy
import datetime as dt
import hashlib
import json
import os

R=Path(__file__).resolve().parents[1]
ROOT=next(p for p in R.parents if (p/'PROJECT_MAP.md').is_file())
W5=ROOT/'20_engineering/WP05_SW_20260907'
W6=R.parent/'wp06_side_joint_20260907_0233'
OUT=R/'results/INTEGRATION_MANIFEST.json'
IDENTITY=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
STATES=('service','parking','released')
CHANGED={f'shear_web_{s}' for s in (-1,1)}|{
    f'shear_clip_{s}_150_{z}' for s in (-1,1) for z in (-94,94)}|{
    f'lower_deck_angle_{s}_1' for s in (-1,1)}
REMOVED={f'shear_web_screw_{s}_150_{z}' for s in (-1,1) for z in (-94,94)}
ADDED={f'WP06_{role}_{s}_{z}' for role in ('screw','washer_outer','washer_inner','nut')
       for s in (-1,1) for z in (-94,94)}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    pins={}
    def pin(path,expected=None):
        path=Path(path).resolve()
        digest=pins.get(str(path)) or sha(path)
        if expected is not None and digest!=expected:
            raise RuntimeError('Input hash mismatch: '+str(path))
        pins[str(path)]=digest
        return dict(path=str(path),sha256=digest)

    old_manifest=W5/'results/PARTS_SOURCE_MANIFEST_DEDUP.json'
    old_imports=W5/'results/NATIVE_IMPORTS.json'
    local_parts=W6/'results/LOCAL_PARTS.json'
    local_native=W6/'results/NATIVE_EXECUTION_V2.json'
    context_path=W6/'inputs/CONTEXT.json'
    parameter_path=R/'candidate/design_parameters.json'
    for path in (old_manifest,old_imports,local_parts,local_native,context_path,parameter_path,Path(__file__)):
        pin(path)
    base=read(old_manifest);imports={p['part_key']:p for p in read(old_imports)['parts']}
    sources={p['part_key']:p for p in base['parts']}
    local=read(local_parts);native=read(local_native);new_imports={p['id']:p for p in native['parts']}
    context=read(context_path);P=read(parameter_path);old_P=read(W6/'candidate/design_parameters.json')
    pin(W6/'candidate/design_parameters.json')
    assert P['wp06']==old_P['wp06'],'Native WP06 parts are bound to different local parameters'
    check_P=copy.deepcopy(P);check_P.pop('parent_configuration_id',None)
    check_P['configuration_id']=old_P['configuration_id']
    assert check_P==old_P,'Unexpected source parameter changes outside the composition identity'
    assert set(context['changed_ids'])==CHANGED and set(context['replaced_ids'])==REMOVED
    assert len(CHANGED)==8 and len(REMOVED)==4 and len(ADDED)==16
    assert CHANGED|ADDED<=set(local['parts']) and CHANGED|ADDED<=set(new_imports)
    pin(local['source_path'],local['source_sha256'])
    assert native['component_count']==53
    code_sources=[pin(W6/'candidate'/n) for n in ('local_assembly.py','side_joint_design.py','r01_design.py','r07_design.py')]
    catalog_sources=[pin(W6/'inputs/catalog'/(name+'.step')) for name in
                     ('iso4762_socket_head_cap_screw_m3x12','din125_flat_washer_m3','iso4032_hex_nut_m3')]
    source_entries={state:pin(R/'candidate'/('servicer_'+state+'.step.py')) for state in STATES}
    for path in [R/'candidate/system_model.py']+[Path(v['path']) for v in source_entries.values()]:
        ast.parse(path.read_text(encoding='utf-8'),filename=str(path));pin(path)

    result=dict(schema='WP07_FULL_SYSTEM_INTEGRATION_V1',status='PREPARED_METADATA_ONLY_NOT_CAD_EXECUTED',
                generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),run_id=R.name,
                units='mm',frame='S',configuration_id=P['configuration_id'],
                base_manifest=pin(old_manifest),base_native_imports=pin(old_imports),
                local_parts_receipt=pin(local_parts),local_native_receipt=pin(local_native),
                parameter_source=pin(parameter_path),system_source=pin(R/'candidate/system_model.py'),
                source_entries=source_entries,changed_ids=sorted(CHANGED),replaced_ids=sorted(CHANGED),removed_ids=sorted(REMOVED),added_ids=sorted(ADDED),
                parametric_delta=dict(count=24,instance_ids=sorted(CHANGED|ADDED),
                                      generator_path=str(W6/'candidate/local_assembly.py'),code_sources=code_sources,
                                      catalog_sources=catalog_sources,parameters=copy.deepcopy(P['wp06']),
                                      input_coordinates='WP06_GLOBAL_S_GEOMETRY_T_IDENTITY',
                                      hardware_geometry='CATALOG_NOMINAL_GEOMETRY_NOT_AS_BUILT'),
                frozen_context_policy='KEEP_EACH_ORIGINAL_UNCHANGED_INSTANCE_ONCE; DO_NOT_APPEND_WP06_CONTEXT',
                retained_arm_status='UNCHANGED_WP05_NATIVE_AND_POSE; EXISTING_GEOMETRY_HOLDS_RETAINED',
                states={},parts={},native_build_executed=False,full_step_export_executed=False,
                physical_assembly_completed=False,manufacturing_release=False,strength_verified=False,
                continuous_motion_verified=False,mate_based_motion_model=False,
                mass_budget_complete=False,mass_note='Changed structural and added hardware masses are null pending current mass-property allocation')

    for state in STATES:
        parent=base['states'][state]
        rows=parent['instances'];lookup={p['id']:p for p in rows}
        assert len(rows)==len(lookup)==585 and CHANGED|REMOVED<=set(lookup)
        cold_path=W5/'results'/('WP05_ROBOT_'+state.upper()+'_COLD.json');cold=read(cold_path);pin(cold_path)
        old_assembly=pin(cold['target'],cold['target_sha256'])
        cold_rows={p['id']:p for p in cold['components']}
        assert set(cold_rows)==set(lookup) and cold['resolved_solid_total']==966
        actual_rows=[]
        for old in rows:
            instance=old['id']
            if instance in REMOVED:
                continue
            row=copy.deepcopy(old)
            if instance in CHANGED:
                row.update(part_key='WP06_'+instance,T_S_local=copy.deepcopy(IDENTITY),
                           bounds_mm=copy.deepcopy(local['parts'][instance]['facts']['bbox_mm']),
                           source_revision='WP06_SIDE_JOINT_PARAMETRIC_DELTA_C02',
                           source_mass_kg=None,mass_source='UNKNOWN_UPDATED_GEOMETRY_ALLOCATION_PENDING',
                           geometry_mode='PARAMETRIC_WP06_LOCAL_DELTA',change='REPLACE_SINGLE_INSTANCE')
                row['previous_native']=pin(imports[old['part_key']]['target'],imports[old['part_key']]['native_save']['sha256'])
                row['previous_part_key']=old['part_key'];row['previous_T_S_local']=copy.deepcopy(old['T_S_local'])
                row['previous_source_metadata']=copy.deepcopy(old)
            else:
                entry=imports[row['part_key']];source=sources[row['part_key']]
                row.update(geometry_mode='FROZEN_WP05_SOURCE_AND_STATE',change='RETAIN_UNCHANGED')
                row['source_step']=pin(source['path'],source['sha256'])
                row['native']=pin(entry['target'],entry['native_save']['sha256'])
                row['expected_solids']=entry['facts']['solid_count']
                row['expected_sheets']=0
                row['native_property_contract']=dict(WP05_ROLE=row['representation_role'])
                assert row['native']['path']==str(Path(cold_rows[instance]['path']).resolve())
                result['parts'].setdefault(row['part_key'],dict(source_step=row['source_step'],native=row['native'],
                    expected_solids=row['expected_solids'],geometry_mode=row['geometry_mode']))
            actual_rows.append(row)
        for instance in sorted(ADDED):
            kind=next(role for role in ('washer_outer','washer_inner','screw','nut') if instance.startswith('WP06_'+role+'_'))
            side,z=instance.rsplit('_',2)[-2:]
            row=dict(id=instance,part_key='WP06_'+instance,T_S_local=copy.deepcopy(IDENTITY),
                     bounds_mm=copy.deepcopy(local['parts'][instance]['facts']['bbox_mm']),
                     representation_role='SIMPLIFIED_PROXY',product_role='ONBOARD_CANDIDATE',
                     parent_assembly='WP06_SIDE_JOINT_FASTENERS',pn=instance,
                     mount_interface=f'WP06_SIDE_JOINT_{side}_{z}',arm_link=None,
                     source_revision='WP06_CATALOG_NOMINAL_HARDWARE_C02',mass_source='UNKNOWN',source_mass_kg=None,
                     qualification_status='NOT_EVALUATED',geometry_mode='PARAMETRIC_WP06_LOCAL_DELTA',change='ADD_HARDWARE',
                     hardware_role=kind)
            actual_rows.append(row)
        for row in actual_rows:
            if row['id'] in CHANGED|ADDED:
                entry=new_imports[row['id']];source=local['parts'][row['id']]
                assert source['sha256']==entry['source_sha256'] and source['T_S_local']==IDENTITY
                row['source_step']=pin(source['path'],source['sha256'])
                row['native']=pin(entry['target'],entry['native_save']['sha256'])
                row['expected_solids']=entry['facts']['solid_count'];row['expected_sheets']=0
                row['actual_source_facts']=copy.deepcopy(source['facts'])
                row['native_property_contract']=dict(WP06_INSTANCE_ID=row['id'],WP06_SOURCE_SHA256=source['sha256'],
                                                     WP06_COORDINATES='WORLD_MM_IDENTITY_ASSEMBLY')
                result['parts'].setdefault(row['part_key'],dict(source_step=row['source_step'],native=row['native'],
                    expected_solids=row['expected_solids'],geometry_mode=row['geometry_mode']))
            row['native_path']=row['native']['path'];row['native_sha256']=row['native']['sha256']
            row['step_path']=row['source_step']['path'];row['source_sha256']=row['source_step']['sha256']
            row['original_id']=None if row['id'] in ADDED else row['id']
            row['world_bounds_mm']=copy.deepcopy(row['bounds_mm'])
        by_id={p['id']:p for p in actual_rows}
        assert len(actual_rows)==len(by_id)==597 and sum(p['expected_solids'] for p in actual_rows)==978
        assert set(by_id)==(set(lookup)-REMOVED)|ADDED
        retained=set(lookup)-CHANGED-REMOVED
        assert len(retained)==573
        for instance in retained:
            for key,value in lookup[instance].items():
                assert by_id[instance][key]==value,('Unexpected frozen metadata edit',state,instance,key)
        context_ids=[p['id'] for p in context['states'][state]]
        assert len(context_ids)==len(set(context_ids)) and set(context_ids)<=retained
        assert len({p['native_path'] for p in actual_rows})==445
        metadata={k:copy.deepcopy(v) for k,v in parent.items() if k!='instances'}
        result['states'][state]=dict(parent_state_metadata=metadata,source_assembly=old_assembly,
            parent_assembly_path=old_assembly['path'],parent_assembly_sha256=old_assembly['sha256'],
            source_cold_receipt=pin(cold_path),component_count=597,expected_solid_total=978,
            retained_instance_count=573,replaced_instance_count=8,deleted_instance_count=4,added_instance_count=16,
            unique_native_dependencies=445,context_ids_retained_once=sorted(context_ids),context_count=len(context_ids),
            role_counts=dict(collections.Counter(p['representation_role'] for p in actual_rows)),
            arm_ids_unchanged=sorted(p['id'] for p in actual_rows if p.get('arm_link')),instances=actual_rows)
    assert len(result['parts'])==460
    result['unique_parts']=460
    result['reused_wp05_unique_native_parts']=436
    result['reused_wp06_unique_native_parts']=24
    result['source_sha256_before']=pins
    after={path:sha(path) for path in pins}
    assert after==pins,'A pinned input changed during metadata preparation'
    result['source_sha256_after']=after;result['inputs_unchanged']=True
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.json.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(temp,OUT)
    print(json.dumps(dict(status=result['status'],states={s:dict(instances=597,solids=978) for s in STATES},
                          unique_parts=460,output=str(OUT)),ensure_ascii=False))


if __name__=='__main__':
    main()
