"""One-shot patch of tools/thermal_cf1.py for the r2 review fixes (kept under logs/scratch as provenance)."""
from pathlib import Path
p = Path(__file__).resolve().parents[2] / 'tools/thermal_cf1.py'
t = p.read_text(encoding='utf-8')
def rep(old, new, count=1):
    global t
    assert t.count(old) >= 1, old[:80]
    t = t.replace(old, new, count)

# 1 link model: spreading + TIM + conduction + TIM + lug through + web through (slice-replace: the old block is one long line)
_marker = "R_TIM = _tim(25 * 40)" + chr(10)
i1 = t.index("def _link_R(lk):"); i2 = t.index(_marker) + len(_marker)
t = t[:i1] + """K_WEB = PATH['material']['web_k_W_mK']
def _link_terms(lk):
    a = lk['conduction_section_mm']; A = a[0] * 1e-3 * a[1] * 1e-3
    As = lk['TIM_sink_mm'][0] * 1e-3 * lk['TIM_sink_mm'][1] * 1e-3
    sp = lk['carrier_spreading']
    return dict(carrier_spreading=sp['length_mm'] * 1e-3 / (K_AL * sp['section_mm'][0] * 1e-3 * sp['section_mm'][1] * 1e-3),
                TIM_source=_tim(lk['TIM_source_mm'][0] * lk['TIM_source_mm'][1]),
                conduction=lk['conduction_length_mm'] * 1e-3 / (K_AL * A),
                TIM_sink=_tim(lk['TIM_sink_mm'][0] * lk['TIM_sink_mm'][1]),
                lug_through=lk['lug_through_mm'] * 1e-3 / (K_AL * As),
                web_through=sum(l['thickness_mm'] * 1e-3 / (K_WEB * l['fill'] * As) for l in PATH['web_section_from_probe']['layers_inward_to_outward_mm']))
def _link_R(lk): return sum(_link_terms(lk).values())
R_STRAP = {k: _link_R(v) for k, v in PATH['links'].items()}
R_STRAP_TERMS = {k: _link_terms(v) for k, v in PATH['links'].items()}
R_TIM = _tim(25 * 40)
R_TIM_PER_INTERFACE = {k + '_' + side: _tim(v[key][0] * v[key][1]) for k, v in PATH['links'].items() for side, key in [('source', 'TIM_source_mm'), ('sink', 'TIM_sink_mm')]}
""" + t[i2:]

# 2 solver: robust resize, finite-positive R, temperature field returned
rep("""    L = block_diag([s.L for s in sheets], format='csr'); L = csr_matrix((L.data, L.indices, L.indptr), shape=(n, n))
    L = csr_matrix(coo_matrix((L.data, (L.nonzero()[0], L.nonzero()[1])), shape=(N, N)))""",
"""    Lc = block_diag([s.L for s in sheets], format='coo')
    L = csr_matrix(coo_matrix((Lc.data, (Lc.row, Lc.col)), shape=(N, N)))
    for r in list(links) + list(node_links):
        assert np.isfinite(r['R_K_W']) and r['R_K_W'] > 0, ('link R must be finite and positive', r)""")
rep("""                net_outward_W=float(radiated.sum()), input_W=float(heat.sum()), balance_error_W=float(radiated.sum() - heat.sum()),
                residual_max_W=float(abs(residual).max()), iterations=it + 1)""",
"""                net_outward_W=float(radiated.sum()), input_W=float(heat.sum()), balance_error_W=float(radiated.sum() - heat.sum()),
                residual_max_W=float(abs(residual).max()), iterations=it + 1,
                field=dict(T_K=T.tolist(), area_m2=area.tolist(), incoming_W_m2=incoming.tolist(), heat_W=heat.tolist(),
                           offsets=[int(o) for o in offsets], node_index=int(n), eps=EPS, sigma=SIGMA,
                           node_link_R_K_W=[r['R_K_W'] for r in node_links], node_link_vectors=[v.tolist() for v in node_vectors]))""")

# 3 replay: both the CANDIDATE scenario (25.2 V) and the acceptance point (20 V); assert Q201 and CHB too
rep('''def replay_check():
    """Replica must reproduce the COUPLED_RESULTS point (360 W, 25.2 V, 0.01 ohm, eta .85, hot x2, V29 copper)."""
    ref = next(p for p in coupled['operating_points'] if abs(p['pack_V'] - 25.2) < 1e-9 and abs(p['shared_R_ohm'] - .01) < 1e-9
               and abs(p['eta_main'] - .85) < 1e-9 and abs(p['main_R_breakdown_ohm']['Q201_25C'] - .042) < 1e-9 and p['active'])
    mine = operating_point(360.0, 25.2, .01, .85, 2.0, COPPER_V29_20C)
    rel = abs(mine['input_power_W'] - ref['input_power_W']) / ref['input_power_W']
    return dict(reference_input_W=ref['input_power_W'], replica_input_W=mine['input_power_W'], relative_error=rel,
                reference_Q201_W=ref['heat_breakdown_W']['Q201'], replica_Q201_W=mine['heat_W']['Q201'], ok=rel < 5e-3)''',
'''def replay_check():
    """Replica must reproduce the COUPLED_RESULTS points at 25.2 V (CANDIDATE scenario) and 20 V (acceptance point):
    360 W, 0.01 ohm, eta .85, hot x2, V29 copper. Input power, Q201 heat and CHB loss are each compared. The known
    omission in the replica is the startup (0.25 W) and input-capacitor leakage (~0.07 W) draws, so the input-power
    tolerance is 1e-3 (about 0.5 W), not tighter."""
    out = dict(points=[], ok=True)
    for pack in (25.2, 20.0):
        ref = next(p for p in coupled['operating_points'] if abs(p['pack_V'] - pack) < 1e-9 and abs(p['shared_R_ohm'] - .01) < 1e-9
                   and abs(p['eta_main'] - .85) < 1e-9 and abs(p['main_R_breakdown_ohm']['Q201_25C'] - .042) < 1e-9 and p['active'])
        mine = operating_point(360.0, pack, .01, .85, 2.0, COPPER_V29_20C)
        rel_in = abs(mine['input_power_W'] - ref['input_power_W']) / ref['input_power_W']
        rel_q = abs(mine['heat_W']['Q201'] - ref['heat_breakdown_W']['Q201']) / ref['heat_breakdown_W']['Q201']
        rel_chb = abs(mine['heat_W']['CHB'] - ref['heat_breakdown_W']['CHB']) / ref['heat_breakdown_W']['CHB']
        ok = rel_in < 1e-3 and rel_q < 5e-3 and rel_chb < 2e-3
        out['points'].append(dict(pack_V=pack, reference_input_W=ref['input_power_W'], replica_input_W=mine['input_power_W'], relative_error=rel_in,
                                  reference_Q201_W=ref['heat_breakdown_W']['Q201'], replica_Q201_W=mine['heat_W']['Q201'], Q201_relative_error=rel_q,
                                  reference_CHB_W=ref['heat_breakdown_W']['CHB'], replica_CHB_W=mine['heat_W']['CHB'], CHB_relative_error=rel_chb, ok=ok))
        out['ok'] = out['ok'] and ok
    out['relative_error'] = max(pt['relative_error'] for pt in out['points'])
    out['known_replica_omissions_W'] = dict(startup=0.25, input_capacitor_leakage=0.07)
    return out''')

# 4 run_case: extra face heat, patch override, cold passes = None, optional field
rep("standby=False, heater_W=0.0, cold_env_K=None):",
    "standby=False, heater_W=0.0, cold_env_K=None, extra_face_heat_W=0.0, patch_override=None, keep_field=False):")
rep("    loads = [dict(sheet=0, center=chb_center, size=[55.9, 59], power_W=mh['CHB_W'] + heater_W)]",
"""    loads = [dict(sheet=0, center=chb_center, size=[55.9, 59], power_W=mh['CHB_W'] + heater_W)]
    if extra_face_heat_W:   # unassigned heat placed uniformly on the three modelled radiators in proportion to their areas
        tot = sum(float(s.area.sum()) for s in sheets[:3])
        loads += [dict(sheet=i, center=[0.0, 0.0], size=list(s.face['face_size_mm']), power_W=extra_face_heat_W * float(s.area.sum()) / tot)
                  for i, s in enumerate(sheets[:3])]""")
rep("    node_links = [dict(sheet=1, R_K_W=sr['plus_Y'], **LUG_PATCH_PLUS_Y), dict(sheet=2, R_K_W=sr['minus_Y'], **LUG_PATCH_MINUS_Y)]",
"""    node_links = [dict(sheet=1, R_K_W=sr['plus_Y'], **LUG_PATCH_PLUS_Y), dict(sheet=2, R_K_W=sr['minus_Y'], **LUG_PATCH_MINUS_Y)]
    if patch_override is not None:
        node_links = patch_override(node_links)""")
rep("    r = solve_with_node(sheets, loads, links, envs, node_links, node_heat)\n",
    "    r = solve_with_node(sheets, loads, links, envs, node_links, node_heat)\n    if not keep_field:\n        r.pop('field', None)\n")
rep("passes=(chb_case <= CHB_LIMIT and carrier <= CARRIER_LIMIT and q201_tj <= Q201_TJ),",
    "passes=(None if cold_env_K is not None else (chb_case <= CHB_LIMIT and carrier <= CARRIER_LIMIT and q201_tj <= Q201_TJ)),")
rep("             unassigned_heat_W=mh['unassigned_W'], strap_R_K_W=sr,",
    "             unassigned_heat_W=mh['unassigned_W'], unassigned_total_W=sum(mh['unassigned_W'].values()), extra_face_heat_W=extra_face_heat_W, strap_R_K_W=sr,")

# 5 main(): rewritten
i = t.index('def main():'); j = t.index("if __name__ == '__main__':")
new_main = r'''def main():
    rep = replay_check()
    assert rep['ok'], rep
    matrix = []
    for load in [60, 120, 240, 360]:
        for eta in [0.85, 0.9]:
            for pack in [20.0, 25.2]:
                for hot in [1.0, 2.0]:
                    for env in ENVS:
                        matrix.append(run_case('service', 10.0, load, pack, 0.01, eta, hot, env))
    hot_cases = [c for c in matrix if c['load_W'] == 360 and c['eta_main'] == 0.85 and c['pack_V'] == 20.0 and c['Q201_hot_multiplier'] == 2.0]
    # acceptance: 360 W, eta 0.85, Q201 x2, pack 20 V (highest current); ALL four environments at 5 mm, worst chosen per criterion
    acc5_by_env = {env: run_case('service', 5.0, 360, 20.0, 0.01, 0.85, 2.0, env, keep_field=True) for env in ENVS}
    worst_env_by_criterion = {k: max(acc5_by_env.values(), key=lambda c: c[k])['env'] for k in ('CHB_case_C', 'carrier_C', 'Q201_Tj_C')}
    min_margins = dict(CHB_case_C=min(c['CHB_margin_C'] for c in acc5_by_env.values()), carrier_C=min(c['carrier_margin_C'] for c in acc5_by_env.values()),
                       Q201_Tj_C=min(c['Q201_Tj_margin_C'] for c in acc5_by_env.values()))
    env_chb = worst_env_by_criterion['CHB_case_C']
    acc10 = next(c for c in hot_cases if c['env'] == env_chb); acc5 = acc5_by_env[env_chb]
    refinement_by_env = {e: abs(acc5_by_env[e]['CHB_case_C'] - next(c for c in hot_cases if c['env'] == e)['CHB_case_C']) for e in ENVS}
    refinement = max(refinement_by_env.values())
    all_pass = all(c['passes'] for c in acc5_by_env.values()) and refinement <= 1.0
    field = acc5['field']
    for c in acc5_by_env.values():
        c.pop('field', None)
    (R / 'ACCEPTANCE_FIELD_CF1.json').write_text(json.dumps(dict(schema='CF1_ACCEPTANCE_FIELD', case=dict(env=env_chb, pitch_mm=5.0, load_W=360, pack_V=20.0, eta=0.85, Q201_hot_multiplier=2.0, state='service'),
                                                            input_W=acc5['input_W'], net_outward_W=acc5['net_outward_W'], node_C=acc5['node_C'],
                                                            node_link_heat_node_to_patch_W=acc5['node_link_heat_node_to_patch_W'], **field), ensure_ascii=False) + '\n', encoding='utf-8')
    # fallbacks when the 5 mm acceptance does not close on every criterion (worst env for the failing criterion)
    fallback = {}
    if not all_pass:
        fail_k = next(k for k in ('carrier_C', 'CHB_case_C', 'Q201_Tj_C') if min_margins[k] < 0) if any(m < 0 for m in min_margins.values()) else 'CHB_case_C'
        fe = worst_env_by_criterion[fail_k]
        fallback['failing_criterion'] = fail_k; fallback['env'] = fe
        fallback['plus_X_skin_added'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.85, 2.0, fe, with_skin=True)
        fallback['Q201_11mohm_alternative'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.85, 2.0, fe, q201_scale=11 / 21)
        fallback['eta_0p90'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.90, 2.0, fe)
        fallback['skin_plus_Q201_alt'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.85, 2.0, fe, with_skin=True, q201_scale=11 / 21)
    # unassigned heat: the model radiates only the module + CHB heat; everything the operating point books as
    # 'unassigned' (harness/contact losses, THN, STOP, brake) is placed on the three faces here as a sensitivity
    spec_listed = acc5['unassigned_heat_W']['THN'] + acc5['unassigned_heat_W']['STOP'] + acc5['unassigned_heat_W']['brake_bias']
    total_unassigned = acc5['unassigned_total_W']
    sens = []
    for extra in [0.0, 5.0, 10.0, spec_listed, total_unassigned]:
        c = run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, env_chb, extra_face_heat_W=extra)
        sens.append(dict(extra_face_heat_W=extra, CHB_case_C=c['CHB_case_C'], carrier_C=c['carrier_C'], Q201_Tj_C=c['Q201_Tj_C'], passes=c['passes']))
    sens_skin = run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, env_chb, extra_face_heat_W=spec_listed, with_skin=True)
    closure_with_spec_listed = next(s for s in sens if abs(s['extra_face_heat_W'] - spec_listed) < 1e-9)['passes']
    # released-state comparison (folded wings) for the same acceptance point: state sensitivity
    released_same = run_case('released', 10.0, 360, 20.0, 0.01, 0.85, 2.0, env_chb)
    # cold: released state, 250 K environment, 60 W standby tier (plan Task 8), heater 20 W electrical x 0.8 = 16 W heat; no hot criterion applies
    cold = run_case('released', 10.0, 60, 25.2, 0.01, 0.85, 1.0, 'DARK_330K_OCCLUDER', cold_env_K=250.0, heater_W=20.0 * 0.8)
    cold_noheater = run_case('released', 10.0, 60, 25.2, 0.01, 0.85, 1.0, 'DARK_330K_OCCLUDER', cold_env_K=250.0, heater_W=0.0)
    # sanity checks (built-in behaviour, kept for regression) and negative controls (must be detected)
    no_strap = run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, env_chb, strap_R=dict(plus_Y=20.0, minus_Y=20.0))
    sanity = dict(strap_degraded_20KW_carrier_exceeds=dict(carrier_C=no_strap['carrier_C'], detected=no_strap['carrier_C'] > CARRIER_LIMIT + 50,
                                                             note='linear identity T_patch + Q*R/2; regression sanity, not a falsification test'),
                  released_state_folded_wings_raises_CHB=dict(service_CHB_C=acc10['CHB_case_C'], released_CHB_C=released_same['CHB_case_C'],
                                                               detected=(released_same['CHB_case_C'] - acc10['CHB_case_C']) > 10.0,
                                                               note='proves the state key selects the released view grid; regression sanity'))
    # negative control 1: the -Y lug patch wired to the wrong face (sheet 1 instead of 2) must move heat between the Y faces
    wrong = run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, env_chb,
                     patch_override=lambda nl: [nl[0], dict(nl[1], sheet=1)])
    d_plus = wrong['panels'][1]['net_outward_W'] - acc10['panels'][1]['net_outward_W']
    d_minus = wrong['panels'][2]['net_outward_W'] - acc10['panels'][2]['net_outward_W']
    # negative control 2: a patch centre outside the face must be refused by Sheet.weights
    try:
        run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, env_chb, patch_override=lambda nl: [nl[0], dict(nl[1], center=[500.0, 55.0])])
        off_face_refused = False
    except AssertionError:
        off_face_refused = True
    # negative control 3: a strap R of zero must be refused before the solve
    try:
        run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, env_chb, strap_R=dict(plus_Y=0.0, minus_Y=R_STRAP['minus_Y']))
        zero_R_refused = False
    except AssertionError:
        zero_R_refused = True
    negative = dict(wrong_patch_face_moves_heat=dict(delta_plus_Y_W=d_plus, delta_minus_Y_W=d_minus, detected=(d_plus > 3.0 and d_minus < -3.0)),
                    off_face_patch_refused=dict(detected=off_face_refused),
                    zero_strap_R_refused=dict(detected=zero_R_refused))
    ce = dict(sanity_checks=sanity, negative_controls=negative,
              energy_balance_all_cases=dict(max_abs_W=max(abs(c['balance_error_W']) for c in matrix + list(acc5_by_env.values())),
                                            note='solver-side number; the independent recomputation and its perturbation control live in verify_thermal_cf1.py'))
    ce['passed'] = all(v['detected'] for v in negative.values()) and all(v['detected'] for v in sanity.values())
    slim = lambda c: {k_: v for k_, v in c.items() if k_ not in ('panels', 'field')} | dict(panels=[{k2: (round(v2, 4) if isinstance(v2, float) else v2) for k2, v2 in p.items()} for p in c['panels']])
    import hashlib
    out = dict(schema='CF1_THERMAL_MATRIX', replay_check=rep, strap_R_K_W=R_STRAP, strap_R_terms_K_W=R_STRAP_TERMS, R_TIM_K_W=R_TIM,
               R_TIM_per_interface_K_W=R_TIM_PER_INTERFACE, R_case_K_W=R_CASE, R_link_K_W=R_LINK,
               lug_patches=dict(minus_Y=LUG_PATCH_MINUS_Y, plus_Y=LUG_PATCH_PLUS_Y),
               path_geometry_file='mechanical/THERMAL_PATH_GEOMETRY_CF1.json',
               path_geometry_sha256=hashlib.sha256((C / 'mechanical/THERMAL_PATH_GEOMETRY_CF1.json').read_bytes()).hexdigest(),
               copper_R20_ohm=dict(V29=COPPER_V29_20C, CF1=COPPER_CF1_20C), limits_C=dict(CHB_case=CHB_LIMIT, carrier=CARRIER_LIMIT, Q201_Tj=Q201_TJ),
               axes=dict(load_W=[60, 120, 240, 360], eta=[0.85, 0.9], pack_V=[20.0, 25.2], Q201_hot_multiplier=[1.0, 2.0], env=list(ENVS)),
               axes_note='Global Constraints list pack 20/22/25.2/29.4 V; 22 and 29.4 V are not run: every metric is monotonically cooler at 25.2 V than at 20 V, so 20 V bounds the set and 22/29.4 V lie between/below 25.2 V.',
               environment='INHERITED_ILLUSTRATIVE_NOT_ORBIT (occluder 330 K, space 3 K, solar 1361 W/m2 on one face, alpha 0.17, eps 0.89)',
               state_for_hot_cases='service (wings deployed)', cases=[slim(c) for c in matrix])
    (R / 'THERMAL_MATRIX_CF1.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    acc = dict(schema='CF1_THERMAL_ACCEPTANCE',
               acceptance_point=dict(load_W=360, eta=0.85, Q201_hot_multiplier=2.0, pack_V=20.0, shared_R_ohm=0.01, env=env_chb, state='service'),
               worst_env_by_criterion=worst_env_by_criterion, min_margins_C=min_margins,
               results_5mm_by_env={e: slim(c) for e, c in acc5_by_env.items()},
               result_10mm=slim(acc10), result_5mm=slim(acc5), mesh_refinement_delta_C=refinement, mesh_refinement_by_env_C=refinement_by_env,
               passes=all_pass, field_file='ACCEPTANCE_FIELD_CF1.json',
               fallback={k_: (slim(v) if isinstance(v, dict) else v) for k_, v in fallback.items()}, released_state_same_point=slim(released_same),
               unassigned_heat_sensitivity=dict(method='extra heat spread uniformly over the three modelled faces in proportion to area, 10 mm mesh, worst-CHB environment',
                                                spec_listed_W=spec_listed, total_unassigned_W=total_unassigned, points=sens,
                                                spec_listed_with_plus_X_skin=dict(CHB_case_C=sens_skin['CHB_case_C'], carrier_C=sens_skin['carrier_C'], Q201_Tj_C=sens_skin['Q201_Tj_C'], passes=sens_skin['passes'])),
               cold=dict(with_heater=slim(cold), without_heater=slim(cold_noheater), heater_electrical_W=20.0, heater_efficiency=0.8, standby_load_W=60,
                         criterion='NONE_DECLARED (passes=null); temperatures reported for the owner'),
               counterexamples=ce,
               continuous_thermal_closure=bool(all_pass and closure_with_spec_listed),
               closure_with_spec_listed_unassigned_heat=bool(closure_with_spec_listed),
               conditional_on=['module pose clears the host (results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json currently REJECTED)',
                               'lug faces bear on the web inner skin over the declared areas (results/mechanical/WEB_FACE_PROBE_CF1.json)',
                               'unassigned heat (see unassigned_heat_sensitivity) is radiated somewhere: this screen places none of it unless stated',
                               '25 psi TIM pressure realised at every interface (clamp design not done)'],
               orbit_validated=False,
               notes=['Module node = carrier; Q201 Tj = carrier + Q201 heat x (0.31 + 1.5) K/W per DESIGN_SPEC; board copper assumed to reach the carrier through the TIM zone.',
                      'Link R = carrier spreading (1-D) + TIM + bar + TIM + lug through + web through (skin/stiffener gap/half plate from WEB_FACE_PROBE_CF1.json).',
                      'Acceptance is evaluated per criterion over all four environments at 5 mm; passes requires every environment and criterion.'])
    (R / 'THERMAL_ACCEPTANCE_CF1.json').write_text(json.dumps(acc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (R / 'COUNTEREXAMPLES.json').write_text(json.dumps(ce, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(replay=rep['relative_error'], strap_R=R_STRAP, worst=worst_env_by_criterion, min_margins=min_margins,
                          acc5=dict(CHB=acc5['CHB_case_C'], carrier=acc5['carrier_C'], Tj=acc5['Q201_Tj_C'], passes=all_pass),
                          refinement=refinement, fallback={k_: (round(v['CHB_case_C'], 2), round(v['carrier_C'], 2)) for k_, v in fallback.items() if isinstance(v, dict)},
                          sens=[(s['extra_face_heat_W'], round(s['CHB_case_C'], 2), round(s['carrier_C'], 2), s['passes']) for s in sens],
                          sens_skin=(round(sens_skin['CHB_case_C'], 2), round(sens_skin['carrier_C'], 2)),
                          cold=dict(CHB=cold['CHB_case_C'], carrier=cold['carrier_C'], noheater_CHB=cold_noheater['CHB_case_C']),
                          counterexamples=ce['passed'], negative=negative), ensure_ascii=False))


'''
t = t[:i] + new_main + t[j:]
p.write_text(t, encoding='utf-8')
print('thermal_cf1.py patched')
