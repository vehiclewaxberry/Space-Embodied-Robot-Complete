"""Compose DELIVERY_STATUS_CF1.json and SHA256_CF1.csv from the CF1 receipts (no re-solve, no re-check).
Every number is read from a receipt; nothing is typed in here. The adversarial-review summary is merged from
results/REVIEW_CF1.json when present. Plain python."""
from pathlib import Path
import csv, hashlib, json, datetime

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    pcb_v = read(C / 'results/pcb/VALIDATION.json'); cd = read(C / 'results/pcb/CURRENT_DENSITY_CF1.json'); build = read(C / 'results/pcb/NATIVE_BUILD.json')
    th_v = read(C / 'results/thermal/VALIDATION.json'); acc = read(C / 'results/thermal/THERMAL_ACCEPTANCE_CF1.json'); mat = read(C / 'results/thermal/THERMAL_MATRIX_CF1.json')
    np_ = read(C / 'results/mechanical/NARROWPHASE_CF1.json'); mp = read(C / 'results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json')
    probe = read(C / 'results/mechanical/WEB_FACE_PROBE_CF1.json')
    ls = read(C / 'results/mechanical/MODULE_POSE_LOCAL_SEARCH_CF1.json') if (C / 'results/mechanical/MODULE_POSE_LOCAL_SEARCH_CF1.json').exists() else None
    review = read(C / 'results/REVIEW_CF1.json') if (C / 'results/REVIEW_CF1.json').exists() else None
    a5 = acc['result_5mm']; pcb_checks = {c['name']: c for c in pcb_v['checks']}
    sens = acc['unassigned_heat_sensitivity']
    thermal_closed = bool(acc['passes']); closed_with_unassigned = bool(acc['continuous_thermal_closure'])
    status = ('THERMAL_' + ('CLOSED' if thermal_closed else 'OPEN') + '_AT_360W_MODEL_LEVEL'
              + ('' if closed_with_unassigned else '__UNASSIGNED_HEAT_GAP')
              + '__PCB_PAD_ENTRY_NECK_OPEN' + '__MODULE_POSE_REJECTED__WHOLE_DESIGN_OPEN')
    out = dict(
        schema='CF1_DELIVERY_STATUS', revision='CF1', date=datetime.date.today().isoformat(),
        kind='LAYOUT_AND_THERMAL_MODEL_LEVEL_REVISION_ON_V32',
        parent=dict(electrical='ecad/revisions/v32', geometry='V30', source_lock='cf1_layout_thermal/results/PARENT_SOURCE_LOCK.json',
                    parent_board_sha256=build['parent_board_sha256']),
        status=status,
        pcb=dict(validation_passed=pcb_v['passed'], checks=pcb_v['checks_run'], failed_checks=pcb_v['failed'], board_sha256=build['board_sha256'],
                 R20_mohm=cd['cf1']['R20_total_ohm'] * 1e3, parent_R20_mohm=cd['parent']['R20_total_ohm'] * 1e3,
                 loss_20A_100C_W=cd['cf1']['loss_20A_100C_W'], parent_loss_20A_100C_W=cd['parent']['loss_20A_100C_W'],
                 loss_reduction=cd['acceptance']['loss_reduction_vs_V29_recorded'], loss_reduction_bands_only_model=cd['acceptance']['loss_reduction_bands_only_model'],
                 worst_band_density_A_mm2=cd['cf1']['worst_band_current_density_A_mm2'],
                 pad_entry_neck_density_A_mm2=cd['acceptance']['pad_entry_neck_density_A_mm2'], density_limit_A_mm2=cd['acceptance']['forward_density_limit_A_mm2'],
                 drc_violations=0 if pcb_checks['native_DRC_clean_all_rule_severities_enabled']['passed'] else None,
                 schematic_parity=pcb_checks['schematic_parity_refusal_recorded_for_delivered_board']['status'],
                 erc_default_ignored_checks=pcb_checks['system_ERC_no_violations'].get('default_ignored_checks', []),
                 spec_deviations=[
                     dict(clause='DESIGN_SPEC_CF1.md 4.2', asked='10 mm wide F201 land connection', delivered='8 mm bands (plan corridor y 8-16)', accepted_by_owner=False),
                     dict(clause='DESIGN_SPEC_CF1.md 4.3', asked='B.Cu parallel copper with >=12-via arrays at both ends of F201 and of R201/R202',
                          delivered='one B.Cu strip on WP10_PRECHARGED_PLUS with 20 vias', rationale='the B.Cu under the F201/R201/R202 bands is the return pour required by 4.4; both cannot occupy it', accepted_by_owner=False),
                     dict(clause='DESIGN_SPEC_CF1.md 4.4', asked='return + forward B.Cu pours totalling >= 60x40 mm with forward thermal vias', delivered='return pour only, 704 mm2 outline, no forward pour, no thermal vias', accepted_by_owner=False),
                     dict(clause='DESIGN_SPEC_CF1.md negative case', asked='via array mis-connected to another net -> DRC short', delivered='one via moved into the return pour -> DRC shorting_items', rationale='KiCad net propagation makes a persistent wrong-net via inexpressible', accepted_by_owner=False)],
                 fabrication=False, hardware_tests=0),
        thermal=dict(validation_passed=th_v['passed'], checks=th_v['checks_run'], failed_checks=th_v.get('failed', []), acceptance_passes=thermal_closed,
                     acceptance_point=acc['acceptance_point'], worst_env_by_criterion=acc['worst_env_by_criterion'], min_margins_C=acc['min_margins_C'],
                     worst_CHB_case_C=max(c['CHB_case_C'] for c in acc['results_5mm_by_env'].values()),
                     worst_carrier_C=max(c['carrier_C'] for c in acc['results_5mm_by_env'].values()),
                     worst_Q201_Tj_C=max(c['Q201_Tj_C'] for c in acc['results_5mm_by_env'].values()),
                     by_env_5mm={e: dict(CHB_case_C=c['CHB_case_C'], carrier_C=c['carrier_C'], Q201_Tj_C=c['Q201_Tj_C'], passes=c['passes']) for e, c in acc['results_5mm_by_env'].items()},
                     web_model=mat.get('web_model', {}).get('kind'), limits_C=mat['limits_C'],
                     spec_deviations=[dict(clause='DESIGN_SPEC_CF1.md 5', asked='-Y lug patch z 40..90', delivered='z 35..75 (raised clear of the compute/comms proxy top, lowered for the carrier-underside bar)', accepted_by_owner=False),
                                      dict(clause='Global Constraints', asked='pack 20/22/25.2/29.4 V', delivered='20 and 25.2 V (20 V bounds every metric; see axes_note)', accepted_by_owner=False)],
                     mesh_refinement_delta_C=acc['mesh_refinement_delta_C'], matrix_cases=len(mat['cases']),
                     matrix_all_pass=all(c['passes'] for c in mat['cases']),
                     strap_R_K_W=mat['strap_R_K_W'], strap_R_terms_K_W=mat['strap_R_terms_K_W'], path_geometry_sha256=mat['path_geometry_sha256'],
                     unassigned_heat=dict(spec_listed_W=sens['spec_listed_W'], total_unassigned_W=sens['total_unassigned_W'],
                                          points=[(p['extra_face_heat_W'], round(p['CHB_case_C'], 2), round(p['carrier_C'], 2), p['passes']) for p in sens['points']],
                                          spec_listed_with_plus_X_skin=sens['spec_listed_with_plus_X_skin']),
                     continuous_thermal_closure=closed_with_unassigned,
                     fallback={k: (dict(CHB_case_C=v['CHB_case_C'], carrier_C=v['carrier_C'], Q201_Tj_C=v['Q201_Tj_C'], passes=v['passes']) if isinstance(v, dict) and 'CHB_case_C' in v
                                   else (dict(fraction=v.get('fraction'), area_mm2=v.get('area_mm2'), note=v.get('note')) if isinstance(v, dict) and 'fraction' in v else v))
                               for k, v in acc['fallback'].items()},
                     released_state_same_point_CHB_C=acc['released_state_same_point']['CHB_case_C'],
                     cold_250K_60W_heater16W=dict(CHB_C=acc['cold']['with_heater']['CHB_case_C'], carrier_C=acc['cold']['with_heater']['carrier_C']),
                     cold_250K_60W_no_heater=dict(CHB_C=acc['cold']['without_heater']['CHB_case_C'], carrier_C=acc['cold']['without_heater']['carrier_C']),
                     conditional_on=acc['conditional_on'], orbit_validated=False, thermal_vacuum_test=False),
        mechanical=dict(step='cf1_layout_thermal/mechanical/thermal_path_cf1.step', step_sha256=np_['step_sha256'],
                        aluminium_mass_kg=np_['total_aluminium_mass_kg_2700'],
                        web_contact=dict(plus_Y=dict(face_S_y=probe['webs']['shear_web_1']['current_lug_web_face_S_y'], contact_mm2=probe['webs']['shear_web_1']['current_lug_contact_mm2'],
                                                     fraction=probe['webs']['shear_web_1']['current_lug_contact_fraction']),
                                         minus_Y=dict(face_S_y=probe['webs']['shear_web_-1']['current_lug_web_face_S_y'], contact_mm2=probe['webs']['shear_web_-1']['current_lug_contact_mm2'],
                                                      fraction=probe['webs']['shear_web_-1']['current_lug_contact_fraction'])),
                        straps_vs_host=dict(parent_status=np_['status'], physical_only_view=np_['physical_only_view'], physical_collision_free=np_['collision_summary']['physical_collision_free'],
                                            registered_envelope_intersections=np_['collision_summary']['envelope_or_proxy'], envelope_dispositions=np_.get('envelope_dispositions'),
                                            role_rule=np_.get('role_classification_rule'), module_self_check=np_.get('module_self_check')),
                        module_pose=dict(T_S_module=mp['T_S_module'], status=mp['status'],
                                         physical_mm3=mp['collision_summary']['physical_or_oem'],
                                         envelope_mm3=mp['collision_summary'].get('registered_envelope', mp['collision_summary'].get('envelope_or_proxy')),
                                         role_rule=mp.get('role_classification_rule'),
                                         context=mp['context'],
                                         local_search=(dict(poses=ls['poses_checked'], grid_mm=ls['grid_mm'],
                                                            physically_clear_poses=ls['physically_clear_poses'], best=ls['best'])
                                                       if ls else 'NOT_RUN')),
                        native_SolidWorks_created=False, fit_verified=False, installed=False),
        adversarial_review=review if review else 'NOT_RUN',
        open_items=[
            'THERMAL/HOST: both +/-Y walls are a 2 mm inner web + 2 mm gap layer with discrete bridge blocks + 8 mm radiator panel; there is NO bridge under either lug '
            '(nearest +Y bridge = CHB seat 110.6 mm away, nearest -Y bridge = device seat 15 mm away), so the strap heat is trapped in the webs: carrier %.1f C / Tj %.1f C at the nominal 360 W point. '
            'Closure needs a host change (bridge blocks under the lugs) plus +X skin (>= %.0f %% area) or the Q201 11 mOhm alternative, or a different thermal architecture.'
            % (acc['min_margins_C']['carrier_C'] * -1 + mat['limits_C']['carrier'], acc['min_margins_C']['Q201_Tj_C'] * -1 + mat['limits_C']['Q201_Tj'],
               100 * ((acc['fallback'].get('min_plus_X_skin_area_fraction_with_HOST_CHANGE_bridges') or {}).get('fraction') or 0)),
            'PCB: Q201 pad-entry necks carry the full main current at %.1f A/mm2 (limit 35): footprint-bound; needs a wider-pad footprint variant, thicker copper or an accepted local-neck criterion.' % cd['acceptance']['pad_entry_neck_density_A_mm2'],
            'THERMAL: %.1f W of the operating point (THN + STOP + brake) and %.1f W in total are not radiated by this model; see unassigned_heat sensitivity.' % (sens['spec_listed_W'], sens['total_unassigned_W']),
            'MECHANICAL: module pose rejected (physical overlaps with the battery dual clamp); no clear pose within +/-6 mm; no exactly-clear module pose exists in the tree.',
            'MECHANICAL: boss and -Y strap (and the whole module) lie inside the RRC3570 D-max battery envelope.',
            'MECHANICAL: lug fastening into the 2 mm inner web needs through-bolts to the panel or inserts; web hole pattern host-owned.',
            'UPSTREAM: equipment_compute_communications placed at two different poses in two bounds files.',
            'UPSTREAM: coupled_closure/CANDIDATE.json source lock drifted (' + ', '.join(np_['parent_candidate_lock_drift']) + '); parent coupled_adapter no longer imports.'],
        whole_design_complete=False, manufacturing_release=False, flight_release=False, registered_as_active_candidate=False,
        scope='EDA layout increment, lumped thermal screen and five project-nominal aluminium bodies on the V32/V30 parent. '
              'Conditional on a module pose that clears the host; that pose does not exist yet.')
    (C / 'DELIVERY_STATUS_CF1.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = []
    for p in sorted(C.rglob('*')):
        if p.is_file() and '__cadgen__' not in p.parts and 'logs' not in p.parts and '__pycache__' not in p.parts and p.name != 'SHA256_CF1.csv':
            rows.append((str(p.relative_to(A)).replace('\\', '/'), sha(p), p.stat().st_size))
    with (C / 'SHA256_CF1.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['path', 'sha256', 'bytes']); w.writerows(rows)
    print(json.dumps(dict(status=out['status'], files=len(rows), pcb=out['pcb']['validation_passed'], thermal=out['thermal']['validation_passed'],
                          thermal_passes=thermal_closed, continuous=closed_with_unassigned, straps=out['mechanical']['straps_vs_host']['physical_only_view'],
                          module_pose=out['mechanical']['module_pose']['status'], review='present' if review else 'absent')))


if __name__ == '__main__':
    main()
