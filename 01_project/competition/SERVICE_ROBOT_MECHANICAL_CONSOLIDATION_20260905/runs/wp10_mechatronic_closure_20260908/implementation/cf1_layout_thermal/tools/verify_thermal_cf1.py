"""Independent checks of the CF1 thermal results (r3): energy balance recomputed from the stored temperature field with a
perturbation control; link resistances recomputed from the geometry file; the web model (thickness, bridges, no bridge
under the lug) checked against the probe receipt, not against the solver's own copy; lug patches on the web sheets;
per-criterion worst environment; acceptance and closure logic; parent-lock identity for all 84 locked sources. No re-solve."""
from pathlib import Path
import hashlib, json, sys
import numpy as np

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent
R = C / 'results/thermal'
sys.path.insert(0, str(A / 'tools'))
from spatial_radiator_network import SIGMA   # parent constant, read-only   # noqa: E402
EPS = 0.89                                    # emissivity used by the parent screen and by thermal_cf1.py (EPS, ALPHA = 0.89, 0.17)


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    m = read(R / 'THERMAL_MATRIX_CF1.json'); acc = read(R / 'THERMAL_ACCEPTANCE_CF1.json'); ce = read(R / 'COUNTEREXAMPLES.json')
    fld = read(R / 'ACCEPTANCE_FIELD_CF1.json')
    lock = read(C / 'results/PARENT_SOURCE_LOCK.json')['sources']
    path = read(C / 'mechanical/THERMAL_PATH_GEOMETRY_CF1.json')
    probe = read(C / 'results/mechanical/WEB_FACE_PROBE_CF1.json')
    checks = []
    def ck(name, passed, **d): checks.append(dict(name=name, passed=bool(passed), **d))
    # 1 source identity: every locked parent source (84), not only the six thermal inputs
    drift = [rel for rel, h in lock.items() if not (A / rel).is_file() or sha(A / rel) != h]
    ck('all_84_locked_parent_sources_unchanged', not drift and len(lock) == 84, locked=len(lock), drift=drift)
    ck('path_geometry_sha_matches_matrix', sha(C / 'mechanical/THERMAL_PATH_GEOMETRY_CF1.json') == m['path_geometry_sha256'])
    ck('probe_sha_matches_matrix_web_model', sha(C / 'results/mechanical/WEB_FACE_PROBE_CF1.json') == m['web_model']['probe_sha256'])
    # 2 replay of the electrical replica against COUPLED_RESULTS at both points, three quantities each
    ck('electrical_replica_matches_COUPLED_RESULTS_both_points', m['replay_check']['ok'] and len(m['replay_check']['points']) == 2,
       points=[(p['pack_V'], p['relative_error'], p['Q201_relative_error'], p['CHB_relative_error']) for p in m['replay_check']['points']])
    # 3 link resistances recomputed from the geometry file (own arithmetic over the same declared inputs)
    tim = lambda a_mm2: path['TIM']['resistance_C_in2_W'] / (a_mm2 / path['TIM']['in2_to_mm2'])
    kk = path['material']['k_W_mK']
    def link_R(lk):
        a = lk['conduction_section_mm']; As = lk['TIM_sink_mm'][0] * 1e-3 * lk['TIM_sink_mm'][1] * 1e-3
        return (sum(s['length_mm'] * 1e-3 / (kk * s['section_mm'][0] * 1e-3 * s['section_mm'][1] * 1e-3) for s in lk['carrier_path'])
                + tim(lk['TIM_source_mm'][0] * lk['TIM_source_mm'][1]) + lk['conduction_length_mm'] * 1e-3 / (kk * a[0] * 1e-3 * a[1] * 1e-3)
                + tim(lk['TIM_sink_mm'][0] * lk['TIM_sink_mm'][1]) + lk['lug_through_mm'] * 1e-3 / (kk * As))
    r_minus = link_R(path['links']['minus_Y']); r_plus = link_R(path['links']['plus_Y'])
    ck('strap_R_recomputed', abs(r_minus - m['strap_R_K_W']['minus_Y']) < 1e-9 and abs(r_plus - m['strap_R_K_W']['plus_Y']) < 1e-9, minus_Y=r_minus, plus_Y=r_plus)
    ck('link_terms_have_no_scalar_web_term', all('web_through' not in m['strap_R_terms_K_W'][k] for k in m['strap_R_terms_K_W'])
       and all(any(t.startswith('carrier_path:arch') for t in m['strap_R_terms_K_W'][k]) for k in m['strap_R_terms_K_W']))
    # 4 web model against the probe receipt (the solver's copy is not trusted)
    pw = {'plus_Y': probe['webs']['shear_web_1'], 'minus_Y': probe['webs']['shear_web_-1']}
    wm = m['web_model']
    ck('web_thickness_from_probe', all(abs(wm['web_thickness_mm'][k] - pw[k]['web_thickness_mm']) < 1e-9 for k in pw) and all(1.9 <= pw[k]['web_thickness_mm'] <= 2.1 for k in pw),
       probe={k: pw[k]['web_thickness_mm'] for k in pw})
    ck('no_bridge_material_under_either_lug', all(pw[k]['gap_material_under_lug_mm3'] is not None and pw[k]['gap_material_under_lug_mm3'] < 1e-3 for k in pw),
       mm3={k: pw[k]['gap_material_under_lug_mm3'] for k in pw})
    def bridges_of(k):
        return sorted((tuple(b['patch_center_ab_mm']), tuple(b['patch_size_ab_mm']), round(b['area_mm2'], 3)) for b in pw[k]['gap_bridges'])
    ck('bridges_in_model_equal_probe', all(sorted((tuple(b['center']), tuple(b['size']), round(b['area_mm2'], 3)) for b in wm['bridges'][k]) == bridges_of(k) for k in pw)
       and all(len(pw[k]['gap_bridges']) >= 1 for k in pw), count={k: len(pw[k]['gap_bridges']) for k in pw})
    kw = path['material']['web_k_W_mK']
    ck('bridge_R_recomputed', all(abs(b['R_K_W'] - pw[k]['gap_thickness_mm'] * 1e-3 / (kw * b['area_mm2'] * 1e-6)) < 1e-9 for k in pw for b in wm['bridges'][k]))
    ck('webs_do_not_radiate', wm['webs_radiate'] is False and all(not p['radiating'] for p in acc['result_5mm']['panels'] if p['face'].endswith('_INNER_WEB'))
       and sum(1 for p in acc['result_5mm']['panels'] if p['face'].endswith('_INNER_WEB')) == 2)
    lp = {k: (v['radiator_patch_center_ab_mm'], v['radiator_patch_size_ab_mm']) for k, v in path['links'].items()}
    ck('lug_patches_match_mechanical_geometry', m['lug_patches'] == {k: dict(center=c, size=s2) for k, (c, s2) in lp.items()}, declared=lp, used=m['lug_patches'])
    ck('lug_patches_sit_on_the_web_sheets', m['lug_patch_sheets'] == {'plus_Y': 3, 'minus_Y': 4})
    # -Y / +Y conduction lengths implied by the boxes
    mb = {p['id']: p['boxes_module_mm'] for p in path['parts']}
    bar = mb['CF1_STRAP_MINUS_Y'][0]; pad = mb['CF1_STRAP_MINUS_Y'][1]; off = path['frame']['S_from_module_mm']
    carrier_y0 = path['frame']['carrier_plate_module_mm'][1] + off[1]; carrier_y1 = bar[1] + bar[4] + off[1]
    centroid = 0.5 * (carrier_y0 + carrier_y1); lug_face = pad[1] + off[1]
    ck('minusY_conduction_length_matches_boxes', abs(abs(centroid - lug_face) - path['links']['minus_Y']['conduction_length_mm']) < 1e-9,
       centroid_S_y=centroid, lug_TIM_face_S_y=lug_face)
    pp = mb['CF1_STRAP_PLUS_Y']; arch_face = path['frame']['carrier_arch_plus_Y_face_module_y'] + off[1]; plus_face = pp[2][1] + pp[2][4] + off[1]
    ck('plusY_conduction_length_matches_boxes', abs((plus_face - arch_face) - path['links']['plus_Y']['conduction_length_mm']) < 1e-9)
    lug_p = mb['CF1_LUG_PLUS_Y'][0]; lug_m = mb['CF1_LUG_MINUS_Y'][0]
    ck('lug_outer_faces_on_probed_web_faces',
       abs((lug_p[1] + lug_p[4] + off[1]) - pw['plus_Y']['inner_face_S_y']) < 1e-6 and abs((lug_m[1] + off[1]) - pw['minus_Y']['inner_face_S_y']) < 1e-6
       and pw['plus_Y']['current_lug_contact_fraction'] >= 0.95 and pw['minus_Y']['current_lug_contact_fraction'] >= 0.95,
       plus_Y=(lug_p[1] + lug_p[4] + off[1], pw['plus_Y']['inner_face_S_y'], pw['plus_Y']['current_lug_contact_fraction']),
       minus_Y=(lug_m[1] + off[1], pw['minus_Y']['inner_face_S_y'], pw['minus_Y']['current_lug_contact_fraction']))
    # 5 energy balance recomputed from the stored field (web sheets carry zero radiating area)
    T = np.array(fld['T_K']); area = np.array(fld['area_m2']); inc = np.array(fld['incoming_W_m2']); heat = np.array(fld['heat_W'])
    radiated = float(np.sum(area * (fld['eps'] * fld['sigma'] * T ** 4 - inc))); inp = float(heat.sum())
    ck('field_constants_match_parent', abs(fld['eps'] - EPS) < 1e-12 and abs(fld['sigma'] - SIGMA) < 1e-20)
    ck('energy_balance_recomputed_from_field_le_1e-6W', abs(radiated - inp) < 1e-6, radiated_W=radiated, input_W=inp)
    n0, n1 = fld['offsets'][0], fld['offsets'][1]
    Tp = T.copy(); Tp[n0:n1] += 1.0
    rad_p = float(np.sum(area * (fld['eps'] * fld['sigma'] * Tp ** 4 - inc)))
    ck('energy_balance_control_1K_perturbation_detected', abs(rad_p - inp) > 1e-3, perturbed_imbalance_W=rad_p - inp)
    web_area = float(np.sum(area[fld['offsets'][3]:fld['offsets'][5]])) if len(fld['offsets']) >= 6 else None
    ck('web_sheets_have_zero_radiating_area_in_field', web_area is not None and web_area == 0.0, web_area_m2=web_area)
    q = [float(np.dot(np.array(v), T) / r) for v, r in zip(fld['node_link_vectors'], fld['node_link_R_K_W'])]
    ck('node_link_heat_recomputed_from_field', all(abs(a - b) < 1e-9 for a, b in zip(q, fld['node_link_heat_node_to_patch_W'])), recomputed_W=q)
    ck('node_heat_equals_strap_heat_flow', abs(sum(q) - heat[fld['node_index']]) < 1e-6, node_heat_W=float(heat[fld['node_index']]))
    worst_bal = max(abs(c['net_outward_W'] - c['input_W']) for c in m['cases'] + list(acc['results_5mm_by_env'].values()))
    ck('solver_totals_balance_all_cases_le_1e-6W', worst_bal < 1e-6, worst_abs_W=worst_bal)
    # 6 CHB case / Tj relations, acceptance and closure logic per environment and criterion
    lim = m['limits_C']; ok_rel = True; ok_pass = True; per_env = {}
    for e, c in acc['results_5mm_by_env'].items():
        chb = c['source_peak_C'][0] + c['CHB_loss_W'] * m['R_case_K_W']; tj = c['carrier_C'] + c['Q201_heat_W'] * (0.31 + 1.5)
        ok_rel &= abs(chb - c['CHB_case_C']) < 1e-9 and abs(tj - c['Q201_Tj_C']) < 1e-9
        p = chb <= lim['CHB_case'] and c['carrier_C'] <= lim['carrier'] and tj <= lim['Q201_Tj']; ok_pass &= (p == c['passes'])
        per_env[e] = dict(CHB=round(chb, 3), carrier=round(c['carrier_C'], 3), Tj=round(tj, 3), passes=p)
    ck('CHB_case_and_Tj_relations_recomputed_all_envs', ok_rel)
    all_pass = all(v['passes'] for v in per_env.values()) and acc['mesh_refinement_delta_C'] <= 1.0
    ck('acceptance_logic_recomputed', ok_pass and acc['passes'] == all_pass, per_env=per_env, mesh_delta_C=acc['mesh_refinement_delta_C'])
    worst = {k: max(acc['results_5mm_by_env'].values(), key=lambda c: c[k])['env'] for k in ('CHB_case_C', 'carrier_C', 'Q201_Tj_C')}
    ck('worst_env_selected_per_criterion', worst == acc['worst_env_by_criterion'], recomputed=worst)
    raw = list(acc['results_5mm_by_env'].values())
    mm = dict(CHB_case_C=min(lim['CHB_case'] - (c['source_peak_C'][0] + c['CHB_loss_W'] * m['R_case_K_W']) for c in raw),
              carrier_C=min(lim['carrier'] - c['carrier_C'] for c in raw), Q201_Tj_C=min(lim['Q201_Tj'] - (c['carrier_C'] + c['Q201_heat_W'] * (0.31 + 1.5)) for c in raw))
    ck('min_margins_recomputed', all(abs(mm[k] - acc['min_margins_C'][k]) < 1e-6 for k in mm), min_margins=mm)
    ck('mesh_refinement_max_over_envs', abs(max(acc['mesh_refinement_by_env_C'].values()) - acc['mesh_refinement_delta_C']) < 1e-12)
    ck('state_is_service_for_hot_cases', all(c['state'] == 'service' for c in m['cases']))
    ck('matrix_axes_include_Q201_x1_and_x2', sorted({c['Q201_hot_multiplier'] for c in m['cases']}) == [1.0, 2.0] and len(m['cases']) == 128)
    s = acc['unassigned_heat_sensitivity']['points']
    mono = all(s[i + 1]['CHB_case_C'] >= s[i]['CHB_case_C'] for i in range(len(s) - 1))
    ck('unassigned_heat_sensitivity_monotone_all_envs', len(s) >= 5 and mono and all(len(p['by_env']) == 4 for p in s)
       and s[-1]['extra_face_heat_W'] >= acc['unassigned_heat_sensitivity']['total_unassigned_W'] - 1e-9)
    spec_pt = next(p for p in s if abs(p['extra_face_heat_W'] - acc['unassigned_heat_sensitivity']['spec_listed_W']) < 1e-9)
    ck('continuous_closure_flag_consistent_with_sensitivity', acc['continuous_thermal_closure'] == (acc['passes'] and spec_pt['passes']),
       spec_listed_W=acc['unassigned_heat_sensitivity']['spec_listed_W'], passes_with_spec_listed=spec_pt['passes'])
    fb = acc['fallback']
    need_fb = not (acc['passes'] and spec_pt['passes'])
    ck('spec5_fallbacks_present_when_closure_fails', (not need_fb) or all(k in fb for k in ('plus_X_skin_full_area', 'Q201_11mohm_alternative', 'skin_plus_Q201_alt', 'min_plus_X_skin_area_fraction',
                                                                                             'HOST_CHANGE_bridge_under_lugs', 'min_plus_X_skin_area_fraction_with_HOST_CHANGE_bridges')),
       needed=need_fb, present=sorted(k for k in fb))
    # every fallback summary must itself be an all-environment evaluation
    ck('fallbacks_evaluated_in_all_four_envs', all(len(v['by_env']) == 4 for k, v in fb.items() if isinstance(v, dict) and 'by_env' in v))
    ck('cold_cases_have_no_hot_pass_flag', acc['cold']['with_heater']['passes'] is None and acc['cold']['without_heater']['passes'] is None
       and abs(acc['cold']['with_heater']['heater_W'] - 16.0) < 1e-9)
    ck('negative_controls_detected', ce['passed'] and all(v['detected'] for v in ce['negative_controls'].values()), controls=list(ce['negative_controls']))
    out = dict(schema='CF1_THERMAL_VALIDATION', passed=all(c['passed'] for c in checks), checks_run=len(checks), failed=[c['name'] for c in checks if not c['passed']], checks=checks,
               scope='Numerical/identity checks of the CF1 thermal screen; not a thermal-vacuum or orbit qualification')
    (R / 'VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=out['passed'], failed=out['failed'], checks=[(c['name'], c['passed']) for c in checks]), ensure_ascii=False))


if __name__ == '__main__':
    main()
