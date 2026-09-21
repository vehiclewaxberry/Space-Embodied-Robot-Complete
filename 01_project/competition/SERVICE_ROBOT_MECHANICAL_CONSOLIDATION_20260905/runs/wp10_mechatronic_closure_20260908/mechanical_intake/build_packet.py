"""Build a read-only, source-bound parameter packet from the sealed WP09 delivery."""
from pathlib import Path
import csv, json, hashlib, math, collections, datetime
import numpy as np
from parameter_contract import quantity, convert, transform_mm_to_m, sw16_to_T_m, validate_transform, physical_readiness

HERE = Path(__file__).resolve().parent
C = HERE.parent.parent/'wp09_interfaces_20260907_1525'/'system_completion'
STATES = ['service', 'parking', 'released']
checked = []
hash_cache = {}

def sha(path):
    path = Path(path)
    key = str(path.resolve())
    if key not in hash_cache:
        h = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        hash_cache[key] = h.hexdigest()
    return hash_cache[key]

def check(name, value):
    checked.append((name, bool(value)))
    if not value:
        raise AssertionError(name)

def read(rel):
    return json.loads((C/rel).read_text(encoding='utf-8-sig'))

def save(name, data):
    (HERE/name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')

ledger = read('review/MASS_ASSIGNMENT_873.json')
index = read('results/MASS_ROLLFORWARD_873.json')
plan = read('results/NATIVE_DELTA_INPUTS.json')
hierarchy = read('results/NATIVE_DELTA_HIERARCHY_INPUTS.json')
cold = {st: read(f'results/NATIVE_DELTA_COLD_{st}.json') for st in STATES}
manifest_files = ['review/MASS_ASSIGNMENT_873.json', 'review/MASS_ASSIGNMENT_873.csv',
 'review/MASS_OWNER_SUMMARY_873.csv','results/MASS_ROLLFORWARD_873.json',
 'results/NATIVE_DELTA_INPUTS.json','results/NATIVE_DELTA_HIERARCHY_INPUTS.json',
 'results/NATIVE_DELTA_IMPORTED_PARTS.json','results/NATIVE_DELTA_DELIVERY.json',
 'results/NATIVE_DELTA_FRAME_EQUIVALENCE.json'] + [f'results/NATIVE_DELTA_COLD_{s}.json' for s in STATES]
sources = [{'path': str(C/x), 'sha256': sha(C/x), 'role': 'SEALED_PARENT_RECEIPT_OR_LEDGER'} for x in manifest_files]
check('mass_index_ledger_sha', sha(index['ledger']['path']) == index['ledger']['sha256'])
check('three_cold_bindings', len(index['native_cold_receipts']) == 3 and index['native_cold_all_pass'])
for binding in index['native_cold_receipts']:
    check('cold_index_sha/'+binding['state'], sha(binding['path']) == binding['sha256'])
by_state = {st: {x['id']: x for x in cold[st]['rows']} for st in STATES}
observed = {st: {x['id']: x for x in cold[st]['components']} for st in STATES}
instances = []
max_pose_error = 0.
source_native_files = {}
for st in STATES:
    z = cold[st]
    check(st+'/pass_status', z['status'] == 'PASS_COLD_NATIVE_DELTA_IDENTITIES_TRANSFORMS_LOCAL_DEPENDENCIES')
    check(st+'/count_identity', z['leaf_component_count'] == 873 and len(by_state[st]) == len(observed[st]) == 873)
    check(st+'/source_manifest_bound', z['input_manifest_sha256'] == sha(C/'results/NATIVE_DELTA_INPUTS.json'))
    check(st+'/hierarchy_bound', z['hierarchy_input_sha256'] == sha(C/'results/NATIVE_DELTA_HIERARCHY_INPUTS.json'))
    check(st+'/ten_containers', z['top_level_container_count'] == len(z['parent_containers']) == 10)
    check(st+'/body_scope_not_upgraded', z['actual_all_body_readback_this_cold_open'] is False)
    for parent in z['parent_containers']:
        check(st+'/parent_identity/'+parent['id'], np.allclose(sw16_to_T_m(parent['transform_sw16']), np.eye(4), atol=1e-12, rtol=0))
    check(st+'/same_hardware_ids', set(by_state[st]) == {x['id'] for x in ledger['instances']})
    check(st+'/expected_solid_ledger', sum(x['expected_solids'] for x in z['rows']) == 1254)

for k, old in enumerate(ledger['instances']):
    ident = old['id']
    source_pointer = f'{C}/review/MASS_ASSIGNMENT_873.json#/instances/{k}'
    mat = old['candidate_material_mass_kg']
    ref = old['vendor_reference_mass_kg']
    check(ident+'/one_instance_mass_basis', mat is None or ref is None)
    mass_value = mat if mat is not None else ref
    identity = ('CANDIDATE_GEOMETRY_MATERIAL_MODEL' if mat is not None else
                'MANUFACTURER_AVERAGE_WHOLE_CIC_REFERENCE' if ref is not None else
                'INCLUDED_IN_OWNER_MODULE_NO_LINK_APPORTIONMENT' if 'WHOLE_ARM' in old['accounting_basis'] else
                'NOT_APPLICABLE_RESERVED_SPACE' if not old['physical_mass_applicable'] else 'UNKNOWN')
    if mat is not None:
        check(ident+'/positive_candidate', math.isfinite(mat) and mat > 0)
        check(ident+'/volume_density_mass', math.isclose(mat, old['source_bound_volume_mm3']*old['density_kg_mm3'], rel_tol=1e-12, abs_tol=1e-15))
    data = dict(id=ident, responsibility_owner=old['responsibility_owner'],
        representation_role=old['representation_role'], physical_mass_applicable=old['physical_mass_applicable'],
        accounting_basis=old['accounting_basis'], mass=quantity(mass_value, 'kg', identity, source_pointer),
        center_of_mass_local=quantity(None, 'm', 'UNKNOWN_NOT_BBOX_CENTER', source_pointer),
        inertia_about_COM_local=quantity(None, 'kg*m^2', 'UNKNOWN_NOT_PROXY_BOX_INERTIA', source_pointer),
        source_volume=quantity(old['source_bound_volume_mm3'], 'mm^3', 'SOURCE_CAD_MODEL_OR_PROXY', source_pointer),
        volume_SI=quantity(convert(old['source_bound_volume_mm3'], 'mm^3', 'm^3'), 'm^3', 'EXACT_UNIT_CONVERSION_OF_SOURCE_MODEL', source_pointer),
        material_density_SI=quantity(convert(old['density_kg_mm3'], 'kg/mm^3', 'kg/m^3'), 'kg/m^3', 'CANDIDATE_MATERIAL_MODEL_NOT_AS_BUILT', source_pointer),
        owner_module_mass_must_not_be_added_to_this_mass=True,
        legacy_planning_budget=quantity(old['retained_legacy_planning_budget_kg'], 'kg', 'NONADDITIVE_PLANNING_BUDGET', source_pointer),
        as_built_mass=quantity(None, 'kg', 'MEASUREMENT_PENDING', source_pointer),
        included_in_flight_hardware=None, flight_disposition_status='NOT_DECIDED_FROM_NAME_OR_LEGACY_PRODUCT_ROLE',
        local_frame_definition='Native STEP/SLDPRT frame; not necessarily a body COM or joint frame.',
        dynamic_link_id=None, notes=old.get('note',''), geometry_by_state={})
    for st in STATES:
        row, obs = by_state[st][ident], observed[st][ident]
        step_path = row.get('step_path') or row['source_step']['path']
        step_sha = row.get('source_sha256') or row['source_step']['sha256']
        T_mm = row.get('native_T_local_to_S', row['T_S_local'])
        check(st+'/'+ident+'/plan_native_T_identity', np.allclose(T_mm, row['T_S_local'], rtol=0, atol=1e-10))
        check(st+'/'+ident+'/mass_pose_binding', np.allclose(T_mm, old['planned_T_local_to_S_mm_by_state'][st], rtol=0, atol=1e-10))
        T_m = transform_mm_to_m(T_mm)
        actual = sw16_to_T_m(obs['transform_sw16'])
        err = float(np.max(np.abs(np.asarray(T_m)-np.asarray(actual))))
        max_pose_error = max(max_pose_error, err)
        check(st+'/'+ident+'/cold_observed_pose', err <= 1e-8)
        check(st+'/'+ident+'/fixed_not_joint', obs['fixed'] is True)
        check(st+'/'+ident+'/parent_identity', np.allclose(sw16_to_T_m(obs['parent_transform_sw16']), np.eye(4), rtol=0, atol=1e-12))
        check(st+'/'+ident+'/source_sha_matches_ledger', step_sha == old['source_step_sha256_by_state'][st])
        for path, digest, role in [(step_path, step_sha, 'SOURCE_STEP'), (obs['path'], obs['sha256'], 'NATIVE_LEAF')]:
            check(st+'/'+ident+'/'+role+'_current_sha', sha(path) == digest)
            source_native_files[str(Path(path).resolve())] = {'path': str(Path(path).resolve()), 'sha256': digest, 'role': role}
        bounds = row.get('world_bounds_mm', row.get('bounds_mm'))
        world_bbox = None
        if isinstance(bounds, dict) and 'min_mm' in bounds:
            world_bbox = {'minimum': convert(bounds['min_mm'], 'mm', 'm'),
                         'maximum': convert(bounds['max_mm'], 'mm', 'm'), 'unit': 'm',
                         'identity': 'SOURCE_POSE_BOUNDING_BOX_NOT_COM_OR_COLLISION_CERTIFICATE'}
            check(st+'/'+ident+'/bbox_order', all(a <= b for a, b in zip(world_bbox['minimum'], world_bbox['maximum'])))
        data['geometry_by_state'][st] = dict(source_step={'path': step_path, 'sha256': step_sha},
            native_part={'path': obs['path'], 'sha256': obs['sha256']},
            T_local_to_S_source_mm=T_mm, T_local_to_S_SI_m=T_m,
            observed_T_local_to_S_SI_m=actual, rotation_unit='1', translation_unit='m',
            convention='column vectors; p_S = R_S_local p_local + t_S; right-handed',
            source_translation_unit='mm', source_pose_standard_uncertainty=None,
            source_pose_distribution=None, source_pose_degrees_of_freedom=None,
            actual_cold_readback_receipt=f'{C}/results/NATIVE_DELTA_COLD_{st}.json',
            identity_parent_container=obs['parent_id'], static_fixed_in_this_pose=True,
            expected_solid_count_hash_inherited=row['expected_solids'], all_bodies_reread_in_this_receipt=False,
            world_bbox_SI=world_bbox, source_product_role=row.get('product_role'),
            source_arm_link_label=row.get('arm_link'), source_parent_assembly_label=row.get('parent_assembly'))
    instances.append(data)

owners = []
for k, old in enumerate(ledger['owners']):
    owner = old['owner']
    ids = [x['id'] for x in instances if x['responsibility_owner'] == owner]
    check(owner+'/instance_count', len(ids) == old['instance_count'])
    owners.append(dict(owner=owner, instance_ids=ids, instance_count=len(ids),
        known_material_subset=quantity(old['known_material_subset_kg'], 'kg', 'PARTIAL_CANDIDATE_MODEL_ONLY', f'{C}/review/MASS_ASSIGNMENT_873.json#/owners/{k}'),
        module_reference_mass=quantity(old['module_reference_kg'], 'kg', 'WHOLE_MODULE_REFERENCE_INSTEAD_OF_CHILDREN', f'{C}/review/MASS_ASSIGNMENT_873.json#/owners/{k}'),
        accounting='Alternative owner aggregate; never add to its own child instance masses.',
        numeric_coverage_unresolved=old['numerically_unresolved_instances'],
        full_owner_COM_local=quantity(None, 'm', 'UNKNOWN', None),
        full_owner_inertia_COM_local=quantity(None, 'kg*m^2', 'UNKNOWN', None)))

packet = dict(schema='WP10_MECHANICAL_PARAMETER_INTAKE_V1', generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status='SOURCE_BOUND_STATIC_GEOMETRY_AND_PARTIAL_MASS_INTAKE__PHYSICAL_DYNAMICS_NOT_READY',
    provenance=sources, source_file_registry=list(source_native_files.values()),
    frame_contract={'world_frame': 'S', 'origin': 'Inherited native assembly S; body COM is not assumed at origin.',
        'pose_units': {'rotation': 'dimensionless', 'translation': 'm'},
        'source_translation': 'mm', 'inertia_output': 'kg*m^2',
        'sw_array_contract': 'First 9 are column-major R; 9:12 are metres; last four [1,0,0,0].',
        'manufacturing_tolerance_is_not_measurement_uncertainty': True,
        'unknown_uncertainty_not_zero': True, 'correlations_not_assumed_independent': True},
    state_names=STATES, same_hardware_three_poses=True, instances=instances, owners=owners,
    joint_tree={'status': 'NOT_RECONSTRUCTED_FROM_FIXED_ASSEMBLY', 'joint_count': None,
        'links': None, 'joints': None, 'accepted_URDF_modified': False,
        'required_action': 'Bind accepted B601 DM kinematic tree to current mounts and all articulated/deployable bodies, prove transform/axis/limit identities, then bind link inertias. 10 grouping containers are memory-management folders, not dynamic links.'},
    aggregation={'whole_spacecraft_mass': quantity(None, 'kg', 'UNKNOWN', None),
        'whole_spacecraft_COM_S': quantity(None, 'm', 'UNKNOWN', None),
        'whole_spacecraft_inertia_COM_S': quantity(None, 'kg*m^2', 'UNKNOWN', None),
        'mix_material_reference_budget_sum_prohibited': True,
        'summary_values_inherited_separately': {k: ledger[k] for k in ['candidate_material_subset_kg','B601_whole_vendor_reference_kg','CIC84_whole_vendor_average_weight_reference_kg']}},
    scope={'CAD_loaded': False, 'OCC_COM_called': False, 'new_simulation_run': False,
        'new_scientific_GATE_credit': False, 'physical_hardware_commands_sent': False,
        'mass_values_newly_measured': False, 'source_or_accepted_URDF_mutated': False,
        'research_policy_decision': 'This packet validates syntax/units/source identities only. It does not approve scientific runs or hardware actuation.'})
readiness = physical_readiness(packet)
packet['readiness_summary'] = {k:v for k,v in readiness.items() if k != 'failures'}
check('873_instances_43_owners', len(instances) == 873 and len(owners) == 43)
check('390_direct_numeric_values', sum(x['mass']['estimate'] is not None for x in instances) == 390)
check('no_false_physical_readiness', readiness['physical_dynamics_ready'] is False and readiness['failure_count'] == 873)
save('PARAMETER_PACKET.json', packet)
save('PHYSICAL_INPUT_GAPS.json', readiness)

gap_rows = []
for owner in owners:
    name = owner['owner']
    unresolved = owner['numeric_coverage_unresolved']
    if name == 'LAUNCH_RESERVED_SPACE':
        action = '保留非质量预留空间；明确最终飞行构型是否需要真实发射接口零件。'
    elif name == 'B601_DM_COMPLETE':
        action = '已有整臂 4.5 kg 参考仅计一次；逐 link 质量、COM、惯量需版本匹配厂家数据或辨识；当前运动树须独立绑定，不能平均分摊。'
    elif name == 'SOLAR_CIC_WHOLE_VENDOR_REFERENCE':
        action = '84 个 3.6 g 平均重量参考可继承；完整 CIC/成形互联几何及局部 COM/惯量仍需资料或测量，不能按玻璃包络赋密度。'
    elif name == 'SOLAR_PANEL_BONDLINE':
        action = '已有 84 个正体积胶层；先选定固化后的胶种/密度/适配工艺，再计算设计质量；温度、厚度公差不自动当概率分布。'
    elif name == 'SOLAR_CURRENT_LEAF_LAMINATES':
        action = '冻结 6 片实际铺层、材料、质量与刚度；既有 1.08 kg 为非加和规划预算，不能转成真值或旧模态参数。'
    elif 'FASTENER' in name and unresolved:
        action = '逐连接选定受控料号/材料/长度；从已绑定实体抽取体积/质心/二阶矩后做候选模型，实物抽样核对。'
    elif 'PROPULSION' in name or 'ADCS' in name:
        action = '将当前 MiPS 包络/支架与最终推进总成精确映射；取得供货型式、干/湿质量、COM/惯量、安装与推进剂状态，未绑定 C-POD 不替换为其质量。'
    elif unresolved:
        action = '先冻结实际器件/材料/连接归属，再取厂家质量与完整几何或称量/摆测；旧包络与预算均不得赋实心密度。'
    else:
        action = '质量候选模型已有；可由绑定几何与同一材料模型抽取局部 COM/二阶矩并验证坐标转换，但本次未加载 CAD，完整惯量保持 null。'
    gap_rows.append({'owner': name, 'instance_count': owner['instance_count'], 'numeric_coverage_unresolved': unresolved,
        'full_COM_and_inertia_unresolved_instances': sum(x['physical_mass_applicable'] for x in instances if x['responsibility_owner']==name),
        'action_ZH': action, 'full_physical_ready': False})
with (HERE/'OWNER_CLOSURE_WORKLIST.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w=csv.DictWriter(f, fieldnames=list(gap_rows[0]));w.writeheader();w.writerows(gap_rows)
with (HERE/'INSTANCE_INTAKE.csv').open('w', encoding='utf-8-sig', newline='') as f:
    fields=['id','responsibility_owner','representation_role','physical_mass_applicable','mass_kg','mass_identity','COM_local_m','inertia_COM_local_kg_m2','source_step_service','source_step_sha256_service','native_service','native_sha256_service']
    w=csv.DictWriter(f, fieldnames=fields);w.writeheader()
    for x in instances:
        g=x['geometry_by_state']['service']
        w.writerow(dict(id=x['id'],responsibility_owner=x['responsibility_owner'],representation_role=x['representation_role'],
            physical_mass_applicable=x['physical_mass_applicable'],mass_kg=x['mass']['estimate'],mass_identity=x['mass']['identity'],
            COM_local_m='null',inertia_COM_local_kg_m2='null',source_step_service=g['source_step']['path'],
            source_step_sha256_service=g['source_step']['sha256'],native_service=g['native_part']['path'],native_sha256_service=g['native_part']['sha256']))
save('INTAKE_VERIFICATION.json', dict(status='PASS_SOURCE_IDENTITY_UNIT_AND_POSE_INTAKE__PHYSICAL_INPUTS_INCOMPLETE',
    checks_total=len(checked),checks_passed=sum(v for _,v in checked),failure_ids=[k for k,v in checked if not v],
    unique_geometry_files_SHA_checked=len(source_native_files),unique_metadata_files_SHA_checked=len(sources),
    maximum_source_vs_observed_pose_element_difference=max_pose_error,
    instance_count=873,owner_count=43,states=3,static_poses=2619,numeric_mass_instance_count=390,
    whole_arm_only_covered_instances=10,prior_ledger_numeric_coverage=400,
    physical_or_represented_hardware=872,complete_rigid_body_parameter_count=0,
    whole_spacecraft_mass_kg=None,whole_spacecraft_COM_m=None,whole_spacecraft_inertia_kg_m2=None,
    CAD_or_COM_executed=False,physical_dynamics_ready=False,packet_sha256=sha(HERE/'PARAMETER_PACKET.json'),
    checker_source_sha256=sha(HERE/'parameter_contract.py'),builder_source_sha256=sha(__file__)))
print(json.dumps({'checks':len(checked),'unique_geometry_files':len(source_native_files),'physical_dynamics_ready':False,'packet':str(HERE/'PARAMETER_PACKET.json')}))
