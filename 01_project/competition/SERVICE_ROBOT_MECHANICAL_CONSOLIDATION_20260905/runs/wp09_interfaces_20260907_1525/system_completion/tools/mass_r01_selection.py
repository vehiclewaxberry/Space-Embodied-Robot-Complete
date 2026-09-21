"""R01-only standard-part selection and material delta. Pure Python; no CAD import.

Reads frozen source receipts; writes only new R01_* files under C/mass.
The two geometric mass models are alternatives, never cumulative.
"""
from pathlib import Path
from collections import Counter
import ast, csv, datetime, hashlib, json, math, sys

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parents[1]
R, N = C.parent, C.parent / 'reuse_closure'
M = C / 'mass'
PROJECT = R.parents[4]
W = R.parent / 'wp04_robot_assembly_20260906_175153/candidate'
RHO = 7.85e-6  # kg/mm3; engineering nominal steel density, not batch measurement

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def volume(kind, length=None, socket_af=2.52):
    if kind == 'screw':
        return math.pi * 3**2 / 4 * length + math.pi * 5.5**2 / 4 * 3 - math.sqrt(3) / 2 * socket_af**2 * 1.5
    if kind == 'washer':
        return math.pi / 4 * (6**2 - 3.2**2) * .5
    if kind == 'nut':
        return (math.sqrt(3) / 2 * 5.5**2 - math.pi / 4 * 3**2) * 2.4
    raise ValueError(kind)

def main():
    bindings, checks = {}, []
    def read(p):
        bindings[str(p)] = sha(p)
        return json.loads(Path(p).read_text(encoding='utf-8-sig'))
    def check(key, passed, detail=None):
        checks.append(dict(id=key, pass_=bool(passed), detail=detail))
        if not passed:
            raise ValueError(key)

    basepath = M / 'MASS_ASSIGNMENT_705.json'
    base = read(basepath)
    old = {x['id']: x for x in base['instances'] if x['responsibility_owner'] == 'R01_EQUIPMENT_FASTENER_KIT'}
    check('128_source_owner_instances', len(old) == 128)
    P = read(W / 'design_parameters.json')
    source = W / 'r01_design.py'
    bindings[str(source)] = sha(source)
    # Reuse only inspected, pure source functions, never import build123d or run a source assembly.
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    nodes = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in ('position', 'connections')]
    check('two_pure_source_functions', len(nodes) == 2 and not any(isinstance(x, (ast.Import, ast.ImportFrom)) for n in nodes for x in ast.walk(n)))
    scope = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
    connections = scope['connections'](P)
    check('32_source_connections', len(connections) == 32)
    source_manifest_path = PROJECT / '20_engineering/WP05_SW_20260907/results/PARTS_SOURCE_MANIFEST.json'
    part_manifest = read(source_manifest_path)
    parts = {x['sha256']: x for x in part_manifest['parts']}
    filenames = {'service': 'NATIVE_SERVICE_RECOVERY_V2.json', 'parking': 'NATIVE_PARKING.json', 'released': 'NATIVE_RELEASED.json'}
    states = {}
    for state, name in filenames.items():
        receipt = read(N / 'results' / name)
        states[state] = {x['id']: x for x in receipt['rows'] if x['id'] in old}
        check(state + '_128_bound', len(states[state]) == 128)
    source_list = read(M / 'r01_sources/SOURCE_MANIFEST.json')
    for x in source_list:
        if x.get('status') == 200:
            check('source_hash_' + Path(x['file']).name, sha(x['file']) == x['sha256'])
    references = {
        'screw': {'file': str(M / 'r01_sources/wuerth_ISO4762_29211246.pdf'), 'url': 'https://media.wuerth.com/stmedia/wuerth/documents/documents/std.lang.all/29211246.pdf', 'page': 1, 'revision': 'CL01_3511140108 Rev0.444 2026-07-28'},
        'washer': {'file': str(M / 'r01_sources/wuerth_ISO7092_29208728.pdf'), 'url': 'https://marketplacemedia.witglobal.net/source/marketplace/stmedia/wuerth/documents/documents/std.lang.all/29208728.pdf', 'page': 1, 'revision': 'CL01_35140804111 Rev0.1300 2025-10-10'},
        'nut': {'file': str(M / 'r01_sources/wuerth_ISO4032_29218026.pdf'), 'url': 'https://media.wuerth.com/stmedia/wuerth/documents/documents/LANG_de/29218026.pdf', 'page': 1, 'revision': 'CL01_3512120133 Rev0.305 2026-07-14'},
        'dimensional_crosscheck': {'file': str(M / 'r01_sources/NBK_ISO4762_JISB1176_dimensions.pdf'), 'url': 'https://www.nbk1560.com/images/en-US/product/technical_data/rokkaku_bolt_NBK/rokkaku_bolt_NBK_1.pdf', 'page': 1, 'scope': 'NBK manufacturer excerpt ISO4762:2004/JISB1176:2015; standard geometry crosscheck, not Wuerth batch certificate'},
        'density': {'file': str(M / 'r01_sources/ssab_density.html'), 'url': 'https://www.ssab.com/en/support/product-material-data/steel/20-questions', 'section': '3', 'value_g_cm3': 7.85, 'scope': 'Nominal engineering steel density; not supplier unit mass or exact alloy/batch density'},
        'nut_pairing': {'file': str(M / 'r01_sources/boellhoff_fastening_manual.pdf'), 'url': 'https://media.boellhoff.com/files/pdf1/the-manual-of-fastening-en-8100.pdf', 'page': 14, 'scope': '8.8 screw may pair with nut class8 or higher'},
    }
    for ref in references.values():
        ref['sha256'] = sha(ref['file'])
        bindings[ref['file']] = ref['sha256']
    common = dict(manufacturer='Adolf Wuerth GmbH & Co. KG', material_family='Steel', nominal_density_kg_mm3=RHO, material_selection_status='SELECTED_FOR_ENGINEERING_PROTOTYPE', batch_or_as_built_verified=False, unit_catalogue_mass_kg=None)
    variants = {}
    for L, ean in [(10, '4011231145183'), (12, '4011231145206')]:
        variants['SCREW_M3X' + str(L)] = dict(common, kind='screw', standard='ISO4762 (DIN912 predecessor)', supplier_article='00843  ' + str(L), ean=ean, thread='M3x0.5', thread_tolerance_design='6g', property_class='8.8 per ISO898-1', coating='zinc plated blue passivated A2K', length_mm=L, head_d_mm=5.5, head_h_mm=3., drive_nominal_AF_mm=2.5, model_socket_AF_mm=2.52, model_socket_depth_mm=1.5, scope='No true thread, head fillet, knurl or chamfer modeled; minimum socket AF from standard excerpt selected for tool fit.', source_key='screw')
    variants['WASHER_M3'] = dict(common, kind='washer', standard='ISO7092 small series; DIN433 predecessor', supplier_article='515005013', thread_reference='M3', hardness_class='200HV', coating='zinc plated', od_mm=6., id_mm=3.2, thickness_mm=.5, source_key='washer')
    variants['NUT_M3'] = dict(common, kind='nut', standard='ISO4032 style1', supplier_article='0324903', ean='4053479367057', thread='M3x0.5', thread_tolerance_design='6H', property_class='10 per ISO898-2', coating='zinc plated blue passivated A2K', af_mm=5.5, thickness_mm=2.4, model_threadless_bore_mm=3., source_key='nut')
    counts = Counter()
    rows = []
    for conn in connections:
        for component, identity in conn['hardware'].items():
            kind = 'washer' if component.startswith('washer') else component
            L = conn['underhead_length_mm'] if kind == 'screw' else None
            key = 'SCREW_M3X' + str(L) if kind == 'screw' else kind.upper() + '_M3'
            counts[key] += 1
            native = states['service'][identity]
            hashes = [states[s][identity].get('source_sha256') or states[s][identity]['source_step']['sha256'] for s in states]
            check(identity + '_same_source_3states', len(set(hashes)) == 1)
            part = parts[hashes[0]]
            facts = part['actual_export_facts']
            check(identity + '_valid_source_volume', facts['shape_valid'] is True and facts['solid_count'] == 1 and facts['volume_mm3'] > 0)
            T = native.get('native_T_local_to_S', native['T_S_local'])
            check(identity + '_original_frame_identity', T == [[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]])
            check(identity + '_same_original_T_3states', all(states[s][identity].get('native_T_local_to_S',states[s][identity]['T_S_local']) == T for s in states))
            check(identity + '_previous_mass_null', old[identity]['candidate_material_mass_kg'] is None)
            if kind == 'screw':
                old_analytic = math.pi/4*(3**2*L+5.5**2*3-2.6**2*1.505)
            elif kind == 'washer':
                old_analytic = math.pi/4*(6**2-3.4**2)*.5
            else:
                old_analytic = volume('nut')
            check(identity + '_legacy_analytic_matches_actual_source_receipt', abs(old_analytic-facts['volume_mm3']) < 1e-7)
            v = volume(kind, L)
            rows.append(dict(id=identity, responsibility_owner='R01_EQUIPMENT_FASTENER_KIT', variant=key, component=component, supplier_article=variants[key]['supplier_article'], source_step_sha256=hashes[0], source_volume_receipt=str(source_manifest_path), old_receipt_volume_mm3=facts['volume_mm3'], selected_density_kg_mm3=RHO, existing_geometry_material_delta_kg=facts['volume_mm3']*RHO, corrected_proxy_analytic_volume_mm3=v, corrected_proxy_material_kg=v*RHO, mass_model='SELECTED_STEEL_THREADLESS_GEOMETRY_MODEL', exact_COTS_mass_kg=None, as_built_mass_kg=None, old_native_T_local_to_S=T, axis_S=conn['axis_S'], axis_point_S_mm=conn['axis_point_S_mm'], head_bearing_axis_t_mm=conn['head_bearing_axis_t_mm'], nut_outer_axis_t_mm=conn['nut_outer_axis_t_mm'], underhead_length_mm=conn['underhead_length_mm']))
    check('exact_BOM_counts', dict(counts) == {'SCREW_M3X12':16, 'WASHER_M3':64, 'NUT_M3':32, 'SCREW_M3X10':16}, dict(counts))
    check('no_extra_or_missing_identity', set(x['id'] for x in rows) == set(old))
    for key, v in variants.items():
        v['quantity'] = counts[key]
        v['corrected_proxy_volume_mm3'] = volume(v['kind'], v.get('length_mm'))
        v['corrected_proxy_material_kg'] = v['corrected_proxy_volume_mm3'] * RHO
    fits = []
    for conn in connections:
        deck = conn['kind'] == 'deck_angle'
        L, g = conn['underhead_length_mm'], conn['nominal_grip_mm']
        # Only source nominal stack plus declared standard length crosscheck; member tolerances are not yet released.
        protrusion = L - (g + 2*.5 + 2.4)
        partial_lower = (11.65 if deck else 9.71) - (g + 2*.55 + 2.4)
        # The lower web connection axis is 4mm from the closest vertical angle edge; deck flange half width is5.5mm.
        edge_axis = 5.5 if deck else (4. if conn['deck']=='lower' else 7.)
        f = dict(connection_id=conn['id'], grip_nominal_mm=g, grip_member_tolerance_mm=None, washers_nominal_mm=1., nut_nominal_mm=2.4, screw_length_nominal_mm=L, tip_protrusion_nominal_mm=protrusion, tip_protrusion_min_mm_fixed_nominal_members_only=partial_lower, full_nominal_nut_overlap_mm=2.4, thread_engagement_after_chamfers_mm=None, head_check_d_mm=5.68, nominal_head_d_mm=5.5, conservative_head_to_nearest_member_edge_mm=edge_axis-5.68/2, full_path_clearance_not_evaluated=True, washer_diametral_clearance_on_M3_max_mm=.2, member_hole_diametral_clearance_mm=.4, driver_hex_tool_AF_mm=2.5, driver_circumscribed_d_mm=2.5/math.cos(math.pi/6), socket_model_AF_mm=2.52, tool_to_socket_flat_clearance_per_side_mm=.01, nut_tool_circular_id_mm=6.4, nut_max_nominal_circumscribed_d_mm=5.5/math.cos(math.pi/6), nut_tool_nominal_radial_clearance_mm=(6.4-5.5/math.cos(math.pi/6))/2, nut_tool_outer_d_mm=8., tool_catalogue_selected=False, assembly_sequence=conn['installation_sequence'])
        check(conn['id'] + '_positive_nominal_stack_and_edge', protrusion > 0 and partial_lower > 0 and f['conservative_head_to_nearest_member_edge_mm'] > 0)
        fits.append(f)
    existing = math.fsum(x['existing_geometry_material_delta_kg'] for x in rows)
    corrected = math.fsum(x['corrected_proxy_material_kg'] for x in rows)
    check('source_documents_and_frozen_base_unchanged', all(sha(p)==h for p,h in bindings.items()))
    summary = dict(schema='R01_STANDARD_FASTENER_SELECTION_DELTA_V1', generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='MATERIAL_AND_STANDARD_SELECTION_COMPLETE__128_ANALYTIC_MODEL_MASSES_BOUND__CAD_DELTA_NOT_EXECUTED', owner='R01_EQUIPMENT_FASTENER_KIT', instance_count=128, connection_count=32, variants_count=4, prior_UNSELECTED_count=128, now_selected_count=128, nominal_numeric_material_model_coverage_count=128, exact_supplier_unit_mass_coverage_count=0, as_built_mass_coverage_count=0, existing_128_geometry_with_selected_steel_mass_kg=existing, corrected_128_proxy_material_mass_kg=corrected, corrected_minus_existing_geometry_kg=corrected-existing, base_material_subtotal_kg=base['summary']['current_candidate_material_subtotal_kg'], base_plus_existing_R01_material_subtotal_kg=base['summary']['current_candidate_material_subtotal_kg']+existing, base_plus_corrected_R01_material_subtotal_if_integrated_kg=base['summary']['current_candidate_material_subtotal_kg']+corrected, corrected_geometry_integrated=False, unknown_instance_count_in_previous_ledger=516, unresolved_numerical_model_instances_after_existing_R01_material_binding=388, previous_unresolved_owner_count=30, unresolved_numerical_model_owner_count_after_R01=29, numeric_model_coverage_if_existing_material_delta_applied=(188+128)/704, responsibility_coverage_remains=1., full_spacecraft_mass_kg=None, strict_as_built_lower_bound_kg=None, source_sha256_bindings=bindings, checks_passed=len(checks), checks_total=len(checks), CAD_executed=False, N_modified=False, prior_mass_ledger_modified=False, B601_mass_modified=False, solar_delta_included=False)
    limitations = [
        'Engineering prototype standard/material choice is issued now. It is not conditional on physical delivery. Arrival dimensions/certificates are a later verification activity.',
        'The density is a declared nominal material-model parameter, not an exact alloy/batch value. Plating mass is not separately modeled.',
        'Existing and corrected geometric mass totals are mutually exclusive alternatives. No catalogue mass is added on top. No unknown part elsewhere is assigned zero.',
        'Thread helices, root/underhead fillets, head/nut chamfers and knurling are omitted. Therefore analytical mass is an explicit approximate material model, not supplier actual mass or a guaranteed upper/lower physical bound.',
        'ISO7092 is chosen because OD6/h0.5 matches. ISO7089 M3 OD7 is not an interchangeable unchanged geometry. Washer ID changes3.4 to3.2.',
        'Selected catalogue family says partial thread generically. NBK same-standard short-length table identifies M3x10/x12 as full thread; procurement requires usable thread through the nut, including standard incomplete-thread limits.',
        '5.68mm is a conservative knurled-head envelope from NBK, not a claim that Wuerth5.5mm nominal head is measured5.68. It is excluded from material volume.',
        'Tool envelopes are analytic envelopes only. The old circular2.5mm driver envelope underestimated a2.5AF hex driver. Full tool access, driver-handle envelope and installed neighboring equipment require the staged CAD check.',
        'Flat washers are not an anti-loosening design. Preload/torque, plate bearing and slip, thread effective engagement/chamfers, underhead fillet to washer bore, locking method, joint loads and environmental suitability remain verification tasks, not a strength PASS.',
        'Partial worst-case tip protrusion holds only with nominal member thicknesses; do not present it as a complete tolerance stack. As-built inspection is separate from the formal material selection.',
    ]
    save(M/'R01_FASTENER_SELECTION.json', dict(summary=summary, variants=variants, sources=references, instances=rows, fit_checks=fits, limitations=limitations, checks=checks))
    fields=['id','responsibility_owner','variant','supplier_article','source_step_sha256','old_receipt_volume_mm3','selected_density_kg_mm3','existing_geometry_material_delta_kg','corrected_proxy_analytic_volume_mm3','corrected_proxy_material_kg','mass_model','exact_COTS_mass_kg','as_built_mass_kg']
    with (M/'R01_FASTENER_SELECTION.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    plan=dict(schema='R01_GEOMETRY_DELTA_PLAN_V1', status='PREPARED_NOT_CAD_EXECUTED', brief='Four nominal selected-standard part forms,128 fixed instances. Preserve original part-local frame and native assembly T; correct circular socket to hex2.52AF for nominal2.5AF tool and washer ID3.4to3.2. All lengths mm. No moving joints or pressure hardware.', selection_file=str(M/'R01_FASTENER_SELECTION.json'), selection_sha256=sha(M/'R01_FASTENER_SELECTION.json'), generator=str(C/'tools/mass_r01_geometry_delta.py'), output_dir=str(M/'r01_geometry_delta'), original_part_local_frame='R01 source coordinates are already in spacecraft S; native_T_local_to_S=identity verified for all128 in each pose. New occurrence STEP bodies must bake the same old axis points in this same source frame. Never recenter source STEP without changing the contract.', preserve_instance_ids=True, preserve_all_native_T=True, states=['service','parking','released'], physical_instance_delta_count=0, parts_replaced=128, unique_form_count=4, variants=variants, connections=connections, instances=rows, analytic_fit_checks=fits, output_contract={'canonical_shapes':'4 reference forms only, not directly inserted at original identityT','occurrence_sources':'128 source-frame STEP leaves, generated from4 forms; these preserve original assemblyT','receipt':'C/mass/r01_geometry_delta/BUILD_RECEIPT.json','run':'mass_r01_geometry_delta.py --build-cad; sequential only when root releases CAD worker','snapshot':'Required after valid STEP generation; parent CAD/SW worker performs snapshot and staged assembly validation'}, checks=checks, scope_limits=limitations)
    save(M/'R01_GEOMETRY_DELTA_PLAN.json',plan)
    save(M/'R01_FASTENER_CHECK_RESULTS.json',summary)
    print(json.dumps({k:summary[k] for k in ['status','instance_count','existing_128_geometry_with_selected_steel_mass_kg','corrected_128_proxy_material_mass_kg','corrected_minus_existing_geometry_kg','checks_total']},ensure_ascii=False))

if __name__ == '__main__':
    main()
