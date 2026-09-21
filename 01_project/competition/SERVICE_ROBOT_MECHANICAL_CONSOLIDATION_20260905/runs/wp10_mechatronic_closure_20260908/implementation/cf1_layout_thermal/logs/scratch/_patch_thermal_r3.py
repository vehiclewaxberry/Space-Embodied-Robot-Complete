"""r3 patch of tools/thermal_cf1.py: in-plane 2 mm web sheets coupled to the panels at the probed bridges, lug patches on the
webs, arch-riser path terms, spec-5 fallbacks (min +X skin area, Q201 11 mOhm) run whenever closure fails, extra receipts."""
from pathlib import Path
p = Path(__file__).resolve().parents[2] / 'tools/thermal_cf1.py'
t = p.read_text(encoding='utf-8')
def rep(old, new, count=1):
    global t
    assert t.count(old) >= 1, old[:90]
    t = t.replace(old, new, count)

# 1 link terms: carrier_path segments + TIM + bar + TIM + lug; web handled by sheets; probe read here
_marker = "R_TIM_PER_INTERFACE = {k + '_' + side: _tim(v[key][0] * v[key][1]) for k, v in PATH['links'].items() for side, key in [('source', 'TIM_source_mm'), ('sink', 'TIM_sink_mm')]}" + chr(10)
i1 = t.index("K_WEB = PATH['material']['web_k_W_mK']"); i2 = t.index(_marker) + len(_marker)
t = t[:i1] + """K_WEB = PATH['material']['web_k_W_mK']
PROBE = read(C / 'results/mechanical/WEB_FACE_PROBE_CF1.json')
WEB = {'plus_Y': PROBE['webs']['shear_web_1'], 'minus_Y': PROBE['webs']['shear_web_-1']}
for _k, _w in WEB.items():
    assert _w['gap_material_under_lug_mm3'] is not None and _w['gap_material_under_lug_mm3'] < 1e-3, ('bridge under the lug: a through term would be needed', _k)
def _link_terms(lk):
    a = lk['conduction_section_mm']; A = a[0] * 1e-3 * a[1] * 1e-3
    As = lk['TIM_sink_mm'][0] * 1e-3 * lk['TIM_sink_mm'][1] * 1e-3
    terms = {}
    for seg in lk['carrier_path']:
        terms['carrier_path:' + seg['name']] = seg['length_mm'] * 1e-3 / (K_AL * seg['section_mm'][0] * 1e-3 * seg['section_mm'][1] * 1e-3)
    terms.update(TIM_source=_tim(lk['TIM_source_mm'][0] * lk['TIM_source_mm'][1]),
                 conduction=lk['conduction_length_mm'] * 1e-3 / (K_AL * A),
                 TIM_sink=_tim(lk['TIM_sink_mm'][0] * lk['TIM_sink_mm'][1]),
                 lug_through=lk['lug_through_mm'] * 1e-3 / (K_AL * As))
    return terms
def _link_R(lk): return sum(_link_terms(lk).values())
R_STRAP = {k: _link_R(v) for k, v in PATH['links'].items()}
R_STRAP_TERMS = {k: _link_terms(v) for k, v in PATH['links'].items()}
R_TIM = _tim(25 * 40)
R_TIM_PER_INTERFACE = {k + '_' + side: _tim(v[key][0] * v[key][1]) for k, v in PATH['links'].items() for side, key in [('source', 'TIM_source_mm'), ('sink', 'TIM_sink_mm')]}
def bridge_links(web_sheet, panel_sheet, side):
    \"\"\"web -> panel couplings at the probed gap-layer bridge blocks: R = gap thickness / (k_web * bridge area).\"\"\"
    w = WEB[side]; out = []
    for b in w['gap_bridges']:
        out.append(dict(a=dict(sheet=web_sheet, center=list(b['patch_center_ab_mm']), size=list(b['patch_size_ab_mm'])),
                        b=dict(sheet=panel_sheet, center=list(b['patch_center_ab_mm']), size=list(b['patch_size_ab_mm'])),
                        R_K_W=w['gap_thickness_mm'] * 1e-3 / (K_WEB * b['area_mm2'] * 1e-6), bridge=b['patch_center_ab_mm']))
    return out
""" + t[i2:]

# 2 sheets: two non-radiating web sheets (indices 3, 4); skin (optional) becomes index 5 with an area fraction
rep("""def build_sheets(state, pitch, with_skin=False):
    rows = faces_for(state)
    sheets = [Sheet(rows[key]['face'], geometry if i == 0 else None, pitch=pitch) for i, key in enumerate(FACE_KEYS)]
    grids = [rows[key]['model_surface_refinement'][-1]['spatial_grid'] for key in FACE_KEYS]
    if with_skin:
        face = dict(rows[SKIN_KEY]['face']); face.setdefault('holes_ab_d_mm', [])
        s = Sheet(face, None, pitch=pitch)
        s.L = csr_matrix(s.L * (2.0 / 8.0))   # uniform 2 mm skin instead of the 8 mm web default
        sheets.append(s); grids.append(rows[SKIN_KEY]['model_surface_refinement'][-1]['spatial_grid'])
    return sheets, grids""",
"""WEB_SHEET = {'plus_Y': 3, 'minus_Y': 4}      # sheet indices of the 2 mm inner webs; panels are 1 (+Y) and 2 (-Y)


def build_sheets(state, pitch, with_skin=False, skin_area_fraction=1.0):
    rows = faces_for(state)
    sheets = [Sheet(rows[key]['face'], geometry if i == 0 else None, pitch=pitch) for i, key in enumerate(FACE_KEYS)]
    grids = [rows[key]['model_surface_refinement'][-1]['spatial_grid'] for key in FACE_KEYS]
    for key, side in (('FIXED_PLUS_Y', 'plus_Y'), ('FIXED_MINUS_Y', 'minus_Y')):     # inner webs: same face frame and holes, 2 mm, adiabatic inner side
        s = Sheet(rows[key]['face'], None, pitch=pitch)
        s.L = csr_matrix(s.L * (WEB[side]['web_thickness_mm'] / 8.0)); s.radiating = False
        sheets.append(s); grids.append(None)
    if with_skin:
        face = dict(rows[SKIN_KEY]['face']); face.setdefault('holes_ab_d_mm', [])
        s = Sheet(face, None, pitch=pitch)
        s.L = csr_matrix(s.L * (2.0 / 8.0))   # uniform 2 mm skin instead of the 8 mm web default
        s.area = s.area * skin_area_fraction   # radiating area fraction (spec 5 bisection); conduction unchanged
        sheets.append(s); grids.append(rows[SKIN_KEY]['model_surface_refinement'][-1]['spatial_grid'])
    return sheets, grids""")

# 3 solver: radiation only on radiating sheets
rep("""    area = np.concatenate([s.area for s in sheets] + [np.zeros(1)]); incoming = []
    for s, e in zip(sheets, envs):
        F = s.view(e['grid']) if e.get('grid') else np.full(s.n, e.get('uniform_F', 0.))
        incoming.append(EPS * SIGMA * ((1 - F) * e.get('space_K', 3.) ** 4 + F * e.get('occluder_K', 330.) ** 4) + ALPHA * e.get('solar_W_m2', 0.))""",
"""    area = np.concatenate([s.area * (1.0 if getattr(s, 'radiating', True) else 0.0) for s in sheets] + [np.zeros(1)]); incoming = []
    for s, e in zip(sheets, envs):
        F = s.view(e['grid']) if e.get('grid') else np.full(s.n, e.get('uniform_F', 0.))
        incoming.append(EPS * SIGMA * ((1 - F) * e.get('space_K', 3.) ** 4 + F * e.get('occluder_K', 330.) ** 4) + ALPHA * e.get('solar_W_m2', 0.))""")
rep("""        panels.append(dict(face=s.face['id'], area_m2=float(s.area.sum()), min_C=float(tt.min() - 273.15), max_C=float(tt.max() - 273.15),""",
"""        panels.append(dict(face=s.face['id'] + ('' if getattr(s, 'radiating', True) else '_INNER_WEB'), area_m2=float(s.area.sum()), radiating=bool(getattr(s, 'radiating', True)),
                           min_C=float(tt.min() - 273.15), max_C=float(tt.max() - 273.15),""")

# 4 run_case: web sheets, bridge links, node links on webs, skin index/fraction, envs for webs
rep("standby=False, heater_W=0.0, cold_env_K=None, extra_face_heat_W=0.0, patch_override=None, keep_field=False):",
    "standby=False, heater_W=0.0, cold_env_K=None, extra_face_heat_W=0.0, patch_override=None, keep_field=False, skin_area_fraction=1.0):")
rep("    sheets, grids = build_sheets(state, pitch, with_skin)", "    sheets, grids = build_sheets(state, pitch, with_skin, skin_area_fraction)")
rep("""    links = [dict(**ep, R_K_W=R_LINK) for ep in old['links_endpoints']]
    sr = strap_R or R_STRAP
    node_links = [dict(sheet=1, R_K_W=sr['plus_Y'], **LUG_PATCH_PLUS_Y), dict(sheet=2, R_K_W=sr['minus_Y'], **LUG_PATCH_MINUS_Y)]""",
"""    links = [dict(**ep, R_K_W=R_LINK) for ep in old['links_endpoints']]
    links += bridge_links(WEB_SHEET['plus_Y'], 1, 'plus_Y') + bridge_links(WEB_SHEET['minus_Y'], 2, 'minus_Y')
    sr = strap_R or R_STRAP
    node_links = [dict(sheet=WEB_SHEET['plus_Y'], R_K_W=sr['plus_Y'], **LUG_PATCH_PLUS_Y), dict(sheet=WEB_SHEET['minus_Y'], R_K_W=sr['minus_Y'], **LUG_PATCH_MINUS_Y)]""")
rep("""    if with_skin:   # skin sheet index 3, coupled to both webs near their +X ends (declared design links)
        for i in (1, 2):
            links.append(dict(a=dict(sheet=3, center=[(-100.0 if i == 1 else 100.0), 0.0], size=[14.0, 100.0]),""",
"""    if with_skin:   # skin sheet index 5, coupled to both panels near their +X ends (declared design links)
        for i in (1, 2):
            links.append(dict(a=dict(sheet=5, center=[(-100.0 if i == 1 else 100.0), 0.0], size=[14.0, 100.0]),""")
rep("""    if cold_env_K is not None:
        envs = [dict(grid=g, occluder_K=cold_env_K, space_K=cold_env_K, solar_W_m2=0.0) for g in grids]
    else:
        sun_sheet, occ = ENVS[env_name]
        envs = envs_for(grids, sun_sheet, occ)""",
"""    if cold_env_K is not None:
        envs = [dict(grid=g, occluder_K=cold_env_K, space_K=cold_env_K, solar_W_m2=0.0) if g is not None else dict(uniform_F=0.0) for g in grids]
    else:
        sun_sheet, occ = ENVS[env_name]
        envs = [e if g is not None else dict(uniform_F=0.0) for e, g in zip(envs_for(grids, sun_sheet, occ), grids)]""")
rep("""    if extra_face_heat_W:   # unassigned heat placed uniformly on the three modelled radiators in proportion to their areas
        tot = sum(float(s.area.sum()) for s in sheets[:3])""",
"""    if extra_face_heat_W:   # unassigned heat placed uniformly on the three modelled radiators (panels) in proportion to their areas
        tot = sum(float(s.area.sum()) for s in sheets[:3])""")
rep("""    r.update(state=state, pitch_mm=pitch, env=env_name if cold_env_K is None else f'COLD_{cold_env_K:.0f}K', load_W=load, pack_V=pack_V, shared_R_ohm=shared_R,""",
"""    r['web_C'] = dict(plus_Y=dict(lug_patch=float(np.dot(np.array(r['field']['T_K']) if 'field' in r else 0, 0)) if False else None),
                      note='web sheet temperatures are in panels[3:5]')
    r['skin_area_fraction'] = skin_area_fraction
    r.update(state=state, pitch_mm=pitch, env=env_name if cold_env_K is None else f'COLD_{cold_env_K:.0f}K', load_W=load, pack_V=pack_V, shared_R_ohm=shared_R,""")

# 5 negative control: wrong face now means the -Y lug on the +Y web sheet
rep("patch_override=lambda nl: [nl[0], dict(nl[1], sheet=1)])", "patch_override=lambda nl: [nl[0], dict(nl[1], sheet=WEB_SHEET['plus_Y'])])")

# 6 fallbacks: run whenever nominal OR spec-listed closure fails; add the spec-5 minimum +X skin area bisection
rep("""    fallback = {}
    if not all_pass:
        fail_k = next(k for k in ('carrier_C', 'CHB_case_C', 'Q201_Tj_C') if min_margins[k] < 0) if any(m < 0 for m in min_margins.values()) else 'CHB_case_C'
        fe = worst_env_by_criterion[fail_k]
        fallback['failing_criterion'] = fail_k; fallback['env'] = fe
        fallback['plus_X_skin_added'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.85, 2.0, fe, with_skin=True)
        fallback['Q201_11mohm_alternative'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.85, 2.0, fe, q201_scale=11 / 21)
        fallback['eta_0p90'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.90, 2.0, fe)
        fallback['skin_plus_Q201_alt'] = run_case('service', 5.0, 360, 20.0, 0.01, 0.85, 2.0, fe, with_skin=True, q201_scale=11 / 21)""",
"""    fallback = {}   # filled after the unassigned-heat sensitivity (spec 5 applies when nominal OR spec-listed closure fails)""")
rep("""    closure_with_spec_listed = next(s for s in sens if abs(s['extra_face_heat_W'] - spec_listed) < 1e-9)['passes']""",
"""    closure_with_spec_listed = next(s for s in sens if abs(s['extra_face_heat_W'] - spec_listed) < 1e-9)['passes']
    if not all_pass or not closure_with_spec_listed:
        extra = 0.0 if not all_pass else spec_listed          # the first failing case
        fail_k = (next((k for k in ('carrier_C', 'CHB_case_C', 'Q201_Tj_C') if min_margins[k] < 0), 'CHB_case_C') if not all_pass
                  else max(('carrier_C', 'CHB_case_C', 'Q201_Tj_C'), key=lambda k: max(s['by_env'][e][k] for s in sens if abs(s['extra_face_heat_W'] - spec_listed) < 1e-9 for e in ENVS) / {'carrier_C': CARRIER_LIMIT, 'CHB_case_C': CHB_LIMIT, 'Q201_Tj_C': Q201_TJ}[k]))
        fallback['basis'] = dict(extra_face_heat_W=extra, criterion=fail_k, envs='all four, 10 mm mesh')
        def fb(**kw):
            per = {e: run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, e, extra_face_heat_W=extra, **kw) for e in ENVS}
            return dict(CHB_case_C=max(c['CHB_case_C'] for c in per.values()), carrier_C=max(c['carrier_C'] for c in per.values()),
                        Q201_Tj_C=max(c['Q201_Tj_C'] for c in per.values()), passes=all(c['passes'] for c in per.values()),
                        by_env={e: dict(CHB_case_C=c['CHB_case_C'], carrier_C=c['carrier_C'], Q201_Tj_C=c['Q201_Tj_C'], passes=c['passes']) for e, c in per.items()})
        fallback['plus_X_skin_full_area'] = fb(with_skin=True)
        fallback['Q201_11mohm_alternative'] = fb(q201_scale=11 / 21)
        fallback['eta_0p90'] = fb(eta=0.90) if False else None
        fallback['skin_plus_Q201_alt'] = fb(with_skin=True, q201_scale=11 / 21)
        if fallback['plus_X_skin_full_area']['passes']:      # spec 5: minimum +X skin radiating-area fraction that closes every criterion in every env
            lo, hi = 0.0, 1.0
            for _ in range(10):
                mid = 0.5 * (lo + hi)
                if fb(with_skin=True, skin_area_fraction=mid)['passes']:
                    hi = mid
                else:
                    lo = mid
            fallback['min_plus_X_skin_area_fraction'] = dict(fraction=hi, area_mm2=hi * 214 * 214, result=fb(with_skin=True, skin_area_fraction=hi))
        else:
            fallback['min_plus_X_skin_area_fraction'] = dict(fraction=None, note='full 214x214 skin does not close; no fraction exists')""")
rep("        fallback['eta_0p90'] = fb(eta=0.90) if False else None\n", "")

# 7 receipts: web sheet model provenance
rep("""               lug_patches=dict(minus_Y=LUG_PATCH_MINUS_Y, plus_Y=LUG_PATCH_PLUS_Y),""",
"""               lug_patches=dict(minus_Y=LUG_PATCH_MINUS_Y, plus_Y=LUG_PATCH_PLUS_Y), lug_patch_sheets=WEB_SHEET,
               web_model=dict(kind='IN_PLANE_WEB_SHEETS_FROM_PROBE', probe_sha256=hashlib.sha256((C / 'results/mechanical/WEB_FACE_PROBE_CF1.json').read_bytes()).hexdigest(),
                              web_thickness_mm={k: WEB[k]['web_thickness_mm'] for k in WEB}, gap_thickness_mm={k: WEB[k]['gap_thickness_mm'] for k in WEB},
                              gap_material_under_lug_mm3={k: WEB[k]['gap_material_under_lug_mm3'] for k in WEB},
                              bridges={k: [dict(center=b['patch_center_ab_mm'], size=b['patch_size_ab_mm'], area_mm2=b['area_mm2'], R_K_W=WEB[k]['gap_thickness_mm'] * 1e-3 / (K_WEB * b['area_mm2'] * 1e-6),
                                                distance_from_lug_mm=b['distance_from_lug_footprint_mm']) for b in WEB[k]['gap_bridges']] for k in WEB},
                              webs_radiate=False),""")
rep("    import hashlib\n    out = dict(schema='CF1_THERMAL_MATRIX'", "    out = dict(schema='CF1_THERMAL_MATRIX'")
rep("def main():\n    rep = replay_check()", "import hashlib\n\n\ndef main():\n    rep = replay_check()")
rep("""                      'Link R = carrier spreading (1-D) + TIM + bar + TIM + lug through + web through (skin/stiffener gap/half plate from WEB_FACE_PROBE_CF1.json).',""",
"""                      'Link R = arch riser path + plate spreading (1-D, -Y only) + TIM + bar + TIM + lug through, ending on the 2 mm inner web sheet; the web reaches the radiating panel only through the probed gap-layer bridges (WEB_FACE_PROBE_CF1.json).',""")
rep("""               conditional_on=['module pose clears the host (results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json currently REJECTED)',
                               'lug faces bear on the web inner skin over the declared areas (results/mechanical/WEB_FACE_PROBE_CF1.json)',""",
"""               conditional_on=['module pose clears the host (results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json currently REJECTED)',
                               'lug faces bear on the 2 mm inner web over the declared areas and the web reaches the panel only through the probed bridges (results/mechanical/WEB_FACE_PROBE_CF1.json)',""")
p.write_text(t, encoding='utf-8')
print('thermal_cf1.py r3 patched')
