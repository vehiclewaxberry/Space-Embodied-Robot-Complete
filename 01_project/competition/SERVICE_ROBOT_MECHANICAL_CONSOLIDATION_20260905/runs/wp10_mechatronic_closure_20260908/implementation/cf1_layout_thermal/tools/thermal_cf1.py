"""CF1 thermal matrix: service-state radiator faces + main-input module node with two straps to the +/-Y webs.

Reuses tools/spatial_radiator_network.py (Sheet, SIGMA; k=130 W/mK aluminium sheets, eps 0.89, alpha 0.17).
Adds ONE lumped node (module carrier, no radiation) coupled by conductances 1/R to two web patches, and an
optional +X skin sheet (design fallback only). Electrical operating points are recomputed here with a
transparent algebraic model and checked against COUPLED_RESULTS.json (V29 copper) before use.
Anaconda python (numpy/scipy)."""
from pathlib import Path
import importlib.util, json, math, sys, copy
import numpy as np
from scipy.sparse import coo_matrix, diags, block_diag, csr_matrix
from scipy.sparse.linalg import spsolve

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent
R = C / 'results/thermal'
R.mkdir(parents=True, exist_ok=True)


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


net = module('wp10_spatial_sheet', A / 'tools/spatial_radiator_network.py')
Sheet, SIGMA = net.Sheet, net.SIGMA
EPS, ALPHA = 0.89, 0.17

# ------------------------------------------------------------------ inputs
view = read(A / 'thermal/RADIATOR_MESH_VIEW_SCREEN.json')
geometry = read(A / 'thermal/BOTTOM_RADIATOR_MOUNT.json')
old = read(A / 'thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json')
cand = read(A / 'coupled_closure/CANDIDATE_V30.json')
coupled = read(A / 'coupled_closure/COUPLED_RESULTS.json')
copper = read(C / 'results/pcb/CURRENT_DENSITY_CF1.json')
pressure = next(x for x in old['pressure_sensitivity'] if x['psi'] == 25)
R_CASE = pressure['case_interface_R_K_W']          # CHB case -> bottom plate (TIM at 25 psi)
R_LINK = pressure['per_link_R_K_W']                # CHB cold fingers to +/-Y webs
CHB_LIMIT = cand['thermal']['CHB_case_limit_C']
Q201_RJC = cand['thermal']['Q201_Rjc_K_W']; Q201_TJ = cand['thermal']['Q201_junction_limit_C']
Q201_CASE_TO_CARRIER = 1.5                          # DESIGN_SPEC requirement (TIM 0.54 typ + clamp margin)
CARRIER_LIMIT = 95.0
FACE_KEYS = ['FIXED_MINUS_Z_BOTTOM_PLATE', 'FIXED_PLUS_Y', 'FIXED_MINUS_Y']   # sheet 0,1,2 (same order as thermal_closure.py)
SKIN_KEY = 'PROPOSED_PLUS_X_FIXED_SKIN'
E = cand['electrical']
R_MAIN_FIXED = dict(Q201_25C=E['main_R_components_ohm']['Q201_25C'], shunts=E['main_R_components_ohm']['shunts'],
                    fuse=E['main_R_components_ohm']['fuse_typical_20C'], other=E['main_R_components_ohm']['other_wiring_contacts_allocation'])
COPPER_V29_20C = E['main_R_components_ohm']['copper_20C']
COPPER_CF1_20C = copper['cf1']['R20_total_ohm']
AUX_W, STARTUP_W, STOP_W, THN_W, BRAKE_W = E['aux_output_W'], E['startup_input_W'], 16.8, 4.2, 1.0

# Conduction path to the +/-Y shear webs. Geometry, material and TIM are NOT restated here: they are read from
# mechanical/THERMAL_PATH_GEOMETRY_CF1.json, the same file thermal_path_cf1.step.py turns into solids, so the
# resistances used by this screen and the as-drawn parts cannot drift apart silently.
PATH = read(C / 'mechanical/THERMAL_PATH_GEOMETRY_CF1.json')
K_AL = PATH['material']['k_W_mK']
def _tim(area_mm2): return PATH['TIM']['resistance_C_in2_W'] / (area_mm2 / PATH['TIM']['in2_to_mm2'])
K_WEB = PATH['material']['web_k_W_mK']
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
    """web -> panel couplings at the probed gap-layer bridge blocks: R = gap thickness / (k_web * bridge area)."""
    w = WEB[side]; out = []
    for b in w['gap_bridges']:
        out.append(dict(a=dict(sheet=web_sheet, center=list(b['patch_center_ab_mm']), size=list(b['patch_size_ab_mm'])),
                        b=dict(sheet=panel_sheet, center=list(b['patch_center_ab_mm']), size=list(b['patch_size_ab_mm'])),
                        R_K_W=w['gap_thickness_mm'] * 1e-3 / (K_WEB * b['area_mm2'] * 1e-6), bridge=b['patch_center_ab_mm']))
    return out
LUG_PATCH_MINUS_Y = dict(center=PATH['links']['minus_Y']['radiator_patch_center_ab_mm'], size=PATH['links']['minus_Y']['radiator_patch_size_ab_mm'])
LUG_PATCH_PLUS_Y = dict(center=PATH['links']['plus_Y']['radiator_patch_center_ab_mm'], size=PATH['links']['plus_Y']['radiator_patch_size_ab_mm'])


def operating_point(load_W, pack_V, shared_R, eta, hot_mult, copper_R20, copper_C=100.0):
    """Algebraic steady point of the shared battery path (main + aux branches), transparent replica.
    Returns heat breakdown [W]. Copper at copper_C via alpha 0.00393; Q201 R = 25C value x hot_mult."""
    P_main_out = load_W + BRAKE_W
    R_copper = copper_R20 * (1 + 0.00393 * (copper_C - 20))
    R_main = R_MAIN_FIXED['Q201_25C'] * hot_mult + R_MAIN_FIXED['shunts'] + R_MAIN_FIXED['fuse'] + R_copper + R_MAIN_FIXED['other']
    P_aux_in = AUX_W / E['eta_aux']; R_aux = E['aux_R_ohm']
    I_m = P_main_out / eta / pack_V; I_a = P_aux_in / pack_V; I_c = 0.003 + 0.003
    for _ in range(200):
        I_t = I_m + I_a + I_c
        V_j = pack_V - I_t * shared_R
        V_main_in = V_j - I_m * R_main
        V_aux_in = V_j - I_a * R_aux
        I_m_new = (P_main_out / eta) / V_main_in
        I_a_new = P_aux_in / V_aux_in
        if abs(I_m_new - I_m) < 1e-12 and abs(I_a_new - I_a) < 1e-12:
            break
        I_m, I_a = I_m_new, I_a_new
    I_t = I_m + I_a + I_c
    heat = dict(Q201=I_m ** 2 * R_MAIN_FIXED['Q201_25C'] * hot_mult, shunts=I_m ** 2 * R_MAIN_FIXED['shunts'],
                fuse=I_m ** 2 * R_MAIN_FIXED['fuse'], copper=I_m ** 2 * R_copper, other_main=I_m ** 2 * R_MAIN_FIXED['other'],
                shared_contact=I_t ** 2 * shared_R, aux_branch=I_a ** 2 * R_aux, CHB=P_main_out * (1 / eta - 1),
                THN=AUX_W * (1 / E['eta_aux'] - 1), input_startup=STARTUP_W, input_controller=I_c * V_j / 2,
                STOP_output_allocation=STOP_W, brake_bias_output_allocation=BRAKE_W)
    return dict(pack_V=pack_V, shared_R_ohm=shared_R, eta_main=eta, hot_multiplier=hot_mult, load_W=load_W,
                battery_A=I_t, main_A=I_m, main_input_V=V_main_in, input_power_W=pack_V * I_t, heat_W=heat)


def replay_check():
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
    return out


def module_heat(op):
    h = op['heat_W']
    return dict(module_W=h['Q201'] + h['shunts'] + h['fuse'] + h['copper'] + h['input_startup'] + h['input_controller'],
                Q201_W=h['Q201'], unassigned_W=dict(other_wiring_contacts=h['other_main'], shared_contact=h['shared_contact'],
                                                     aux_branch=h['aux_branch'], THN=h['THN'], STOP=h['STOP_output_allocation'],
                                                     brake_bias=h['brake_bias_output_allocation']), CHB_W=h['CHB'])


def faces_for(state):
    rows = {r['face']['id']: r for r in view['results'] if r['state'] == state}
    return rows


WEB_SHEET = {'plus_Y': 3, 'minus_Y': 4}      # sheet indices of the 2 mm inner webs; panels are 1 (+Y) and 2 (-Y)


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
    return sheets, grids


def solve_with_node(sheets, loads, links, envs, node_links, node_heat_W):
    """spatial_radiator_network.solve() plus one non-radiating lumped node (index n)."""
    offsets = np.cumsum([0] + [s.n for s in sheets]); n = offsets[-1]; N = n + 1
    Lc = block_diag([s.L for s in sheets], format='coo')
    L = csr_matrix(coo_matrix((Lc.data, (Lc.row, Lc.col)), shape=(N, N)))
    for r in list(links) + list(node_links):
        assert np.isfinite(r['R_K_W']) and r['R_K_W'] > 0, ('link R must be finite and positive', r)
    heat = np.zeros(N); load_weights = []; link_vectors = []
    for r in loads:
        i = r['sheet']; v = np.zeros(N); v[offsets[i]:offsets[i + 1]] = sheets[i].weights(r['center'], r['size']); heat += r['power_W'] * v; load_weights.append(v)
    rr, cc, vv = [], [], []
    for r in links:
        v = np.zeros(N)
        for tag, sign in [('a', 1), ('b', -1)]:
            ep = r[tag]; i = ep['sheet']; v[offsets[i]:offsets[i + 1]] += sign * sheets[i].weights(ep['center'], ep['size'])
        ids = np.flatnonzero(v); outer = np.outer(v[ids], v[ids]) / r['R_K_W']
        rr.extend(np.repeat(ids, len(ids))); cc.extend(np.tile(ids, len(ids))); vv.extend(outer.ravel()); link_vectors.append(v)
    node_vectors = []
    for r in node_links:                              # node <-> patch on sheet r['sheet'] with resistance R
        v = np.zeros(N); i = r['sheet']; v[offsets[i]:offsets[i + 1]] = -sheets[i].weights(r['center'], r['size']); v[n] = 1.0
        ids = np.flatnonzero(v); outer = np.outer(v[ids], v[ids]) / r['R_K_W']
        rr.extend(np.repeat(ids, len(ids))); cc.extend(np.tile(ids, len(ids))); vv.extend(outer.ravel()); node_vectors.append(v)
    if rr:
        L = L + coo_matrix((vv, (rr, cc)), shape=(N, N)).tocsr()
    heat[n] += node_heat_W
    area = np.concatenate([s.area * (1.0 if getattr(s, 'radiating', True) else 0.0) for s in sheets] + [np.zeros(1)]); incoming = []
    for s, e in zip(sheets, envs):
        F = s.view(e['grid']) if e.get('grid') else np.full(s.n, e.get('uniform_F', 0.))
        incoming.append(EPS * SIGMA * ((1 - F) * e.get('space_K', 3.) ** 4 + F * e.get('occluder_K', 330.) ** 4) + ALPHA * e.get('solar_W_m2', 0.))
    incoming = np.concatenate(incoming + [np.zeros(1)]); T = np.full(N, 355.)
    for it in range(80):
        residual = L @ T + area * (EPS * SIGMA * T ** 4 - incoming) - heat
        if abs(residual).max() < 1e-11 and abs(float(np.sum(area * (EPS * SIGMA * T ** 4 - incoming)) - heat.sum())) < 5e-9:
            break
        delta = spsolve((L + diags(area * 4 * EPS * SIGMA * T ** 3)).tocsc(), -residual); T += delta * min(1, 30 / max(abs(delta).max(), 1e-30))
    assert abs(residual).max() < 1e-8, 'thermal solve did not converge'
    radiated = area * (EPS * SIGMA * T ** 4 - incoming); panels = []
    for i, s in enumerate(sheets):
        sl = slice(offsets[i], offsets[i + 1]); tt = T[sl]
        panels.append(dict(face=s.face['id'] + ('' if getattr(s, 'radiating', True) else '_INNER_WEB'), area_m2=float(s.area.sum()), radiating=bool(getattr(s, 'radiating', True)),
                           min_C=float(tt.min() - 273.15), max_C=float(tt.max() - 273.15),
                           mean_C=float(np.dot(tt, s.area) / s.area.sum() - 273.15), net_outward_W=float(radiated[sl].sum()), mesh=list(s.X.shape)))
    return dict(panels=panels, source_mean_C=[float(np.dot(T, v) - 273.15) for v in load_weights],
                source_peak_C=[float(T[v > 1e-12].max() - 273.15) for v in load_weights],
                link_heat_a_to_b_W=[float(np.dot(T, v) / r['R_K_W']) for v, r in zip(link_vectors, links)],
                node_C=float(T[n] - 273.15), node_link_heat_node_to_patch_W=[float(np.dot(T, v) / r['R_K_W']) for v, r in zip(node_vectors, node_links)],
                net_outward_W=float(radiated.sum()), input_W=float(heat.sum()), balance_error_W=float(radiated.sum() - heat.sum()),
                residual_max_W=float(abs(residual).max()), iterations=it + 1,
                field=dict(T_K=T.tolist(), area_m2=area.tolist(), incoming_W_m2=incoming.tolist(), heat_W=heat.tolist(),
                           offsets=[int(o) for o in offsets], node_index=int(n), eps=EPS, sigma=SIGMA,
                           node_link_R_K_W=[r['R_K_W'] for r in node_links], node_link_vectors=[v.tolist() for v in node_vectors]))


ENVS = {'HOT_A_SUN_PLUS_Y': (1, 330.0), 'HOT_B_SUN_MINUS_Z': (0, 330.0), 'HOT_C_SUN_MINUS_Y': (2, 330.0), 'DARK_330K_OCCLUDER': (None, 330.0)}


def envs_for(grids, sun_sheet, occluder_K, space_K=3.0, solar=1361.0):
    return [dict(grid=g, occluder_K=occluder_K, space_K=space_K, solar_W_m2=(solar if i == sun_sheet else 0.0)) for i, g in enumerate(grids)]


def run_case(state, pitch, load, pack_V, shared_R, eta, hot, env_name, copper_R20=COPPER_CF1_20C, q201_scale=1.0,
             strap_R=None, with_skin=False, skin_link_R=0.5, standby=False, heater_W=0.0, cold_env_K=None, extra_face_heat_W=0.0, patch_override=None, keep_field=False, skin_area_fraction=1.0,
             host_bridge_under_lugs=False):
    op = operating_point(load, pack_V, shared_R, eta, hot, copper_R20)
    mh = module_heat(op)
    q201 = mh['Q201_W'] * q201_scale
    node_heat = mh['module_W'] - mh['Q201_W'] + q201
    sheets, grids = build_sheets(state, pitch, with_skin, skin_area_fraction)
    chb_center = geometry['chb_path']['center_xy_mm']
    loads = [dict(sheet=0, center=chb_center, size=[55.9, 59], power_W=mh['CHB_W'] + heater_W)]
    if extra_face_heat_W:   # unassigned heat placed uniformly on the three modelled radiators (panels) in proportion to their areas
        tot = sum(float(s.area.sum()) for s in sheets[:3])
        loads += [dict(sheet=i, center=[0.0, 0.0], size=list(s.face['face_size_mm']), power_W=extra_face_heat_W * float(s.area.sum()) / tot)
                  for i, s in enumerate(sheets[:3])]
    links = [dict(**ep, R_K_W=R_LINK) for ep in old['links_endpoints']]
    links += bridge_links(WEB_SHEET['plus_Y'], 1, 'plus_Y') + bridge_links(WEB_SHEET['minus_Y'], 2, 'minus_Y')
    if host_bridge_under_lugs:   # HYPOTHETICAL host change: a gap-layer bridge block under each lug footprint (like the device bosses); not in the saved host
        for side, panel in (('plus_Y', 1), ('minus_Y', 2)):
            patch = LUG_PATCH_PLUS_Y if side == 'plus_Y' else LUG_PATCH_MINUS_Y
            links.append(dict(a=dict(sheet=WEB_SHEET[side], center=list(patch['center']), size=list(patch['size'])),
                              b=dict(sheet=panel, center=list(patch['center']), size=list(patch['size'])),
                              R_K_W=WEB[side]['gap_thickness_mm'] * 1e-3 / (K_WEB * patch['size'][0] * patch['size'][1] * 1e-6), bridge='HYPOTHETICAL_UNDER_LUG'))
    sr = strap_R or R_STRAP
    node_links = [dict(sheet=WEB_SHEET['plus_Y'], R_K_W=sr['plus_Y'], **LUG_PATCH_PLUS_Y), dict(sheet=WEB_SHEET['minus_Y'], R_K_W=sr['minus_Y'], **LUG_PATCH_MINUS_Y)]
    if patch_override is not None:
        node_links = patch_override(node_links)
    if with_skin:   # skin sheet index 5, coupled to both panels near their +X ends (declared design links)
        for i in (1, 2):
            links.append(dict(a=dict(sheet=5, center=[(-100.0 if i == 1 else 100.0), 0.0], size=[14.0, 100.0]),
                              b=dict(sheet=i, center=[165.0, 0.0], size=[14.0, 100.0]), R_K_W=skin_link_R))
    if cold_env_K is not None:
        envs = [dict(grid=g, occluder_K=cold_env_K, space_K=cold_env_K, solar_W_m2=0.0) if g is not None else dict(uniform_F=0.0) for g in grids]
    else:
        sun_sheet, occ = ENVS[env_name]
        envs = [e if g is not None else dict(uniform_F=0.0) for e, g in zip(envs_for(grids, sun_sheet, occ), grids)]
    r = solve_with_node(sheets, loads, links, envs, node_links, node_heat)
    if not keep_field:
        r.pop('field', None)
    chb_case = r['source_peak_C'][0] + mh['CHB_W'] * R_CASE
    carrier = r['node_C']
    q201_tj = carrier + q201 * (Q201_RJC + Q201_CASE_TO_CARRIER)
    r['web_note'] = 'inner-web sheet temperatures are panels[3] (+Y) and panels[4] (-Y); they do not radiate'
    r['skin_area_fraction'] = skin_area_fraction
    r.update(state=state, pitch_mm=pitch, env=env_name if cold_env_K is None else f'COLD_{cold_env_K:.0f}K', load_W=load, pack_V=pack_V, shared_R_ohm=shared_R,
             eta_main=eta, Q201_hot_multiplier=hot, Q201_R_scale=q201_scale, CHB_loss_W=mh['CHB_W'], module_heat_W=node_heat, Q201_heat_W=q201,
             unassigned_heat_W=mh['unassigned_W'], unassigned_total_W=sum(mh['unassigned_W'].values()), extra_face_heat_W=extra_face_heat_W, strap_R_K_W=sr, with_skin=with_skin, heater_W=heater_W,
             CHB_case_C=chb_case, CHB_margin_C=CHB_LIMIT - chb_case, carrier_C=carrier, carrier_margin_C=CARRIER_LIMIT - carrier,
             Q201_Tj_C=q201_tj, Q201_Tj_margin_C=Q201_TJ - q201_tj,
             passes=(None if cold_env_K is not None else (chb_case <= CHB_LIMIT and carrier <= CARRIER_LIMIT and q201_tj <= Q201_TJ)), battery_A=op['battery_A'], input_power_W=op['input_power_W'])
    return r


import hashlib


def main():
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
    fallback = {}   # filled after the unassigned-heat sensitivity (spec 5 applies when nominal OR spec-listed closure fails)
    # unassigned heat: the model radiates only the module + CHB heat; everything the operating point books as
    # 'unassigned' (harness/contact losses, THN, STOP, brake) is placed on the three faces here as a sensitivity
    spec_listed = acc5['unassigned_heat_W']['THN'] + acc5['unassigned_heat_W']['STOP'] + acc5['unassigned_heat_W']['brake_bias']
    total_unassigned = acc5['unassigned_total_W']
    sens = []
    for extra in [0.0, 5.0, 10.0, spec_listed, total_unassigned]:
        per = {e: run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, e, extra_face_heat_W=extra) for e in ENVS}
        sens.append(dict(extra_face_heat_W=extra,
                         CHB_case_C=max(c['CHB_case_C'] for c in per.values()), carrier_C=max(c['carrier_C'] for c in per.values()),
                         Q201_Tj_C=max(c['Q201_Tj_C'] for c in per.values()), passes=all(c['passes'] for c in per.values()),
                         by_env={e: dict(CHB_case_C=c['CHB_case_C'], carrier_C=c['carrier_C'], Q201_Tj_C=c['Q201_Tj_C'], passes=c['passes']) for e, c in per.items()}))
    per_skin = {e: run_case('service', 10.0, 360, 20.0, 0.01, 0.85, 2.0, e, extra_face_heat_W=spec_listed, with_skin=True) for e in ENVS}
    sens_skin = dict(CHB_case_C=max(c['CHB_case_C'] for c in per_skin.values()), carrier_C=max(c['carrier_C'] for c in per_skin.values()),
                     Q201_Tj_C=max(c['Q201_Tj_C'] for c in per_skin.values()), passes=all(c['passes'] for c in per_skin.values()),
                     by_env={e: dict(CHB_case_C=c['CHB_case_C'], carrier_C=c['carrier_C'], Q201_Tj_C=c['Q201_Tj_C'], passes=c['passes']) for e, c in per_skin.items()})
    closure_with_spec_listed = next(s for s in sens if abs(s['extra_face_heat_W'] - spec_listed) < 1e-9)['passes']
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
        fallback['skin_plus_Q201_alt'] = fb(with_skin=True, q201_scale=11 / 21)
        # HYPOTHETICAL host change (not in the saved host): a gap-layer bridge block under each lug, like the device bosses
        fallback['HOST_CHANGE_bridge_under_lugs'] = fb(host_bridge_under_lugs=True)
        fallback['HOST_CHANGE_bridge_under_lugs_plus_skin'] = fb(host_bridge_under_lugs=True, with_skin=True)
        fallback['HOST_CHANGE_bridge_under_lugs_plus_Q201_alt'] = fb(host_bridge_under_lugs=True, q201_scale=11 / 21)
        fallback['HOST_CHANGE_bridge_under_lugs_plus_skin_plus_Q201_alt'] = fb(host_bridge_under_lugs=True, with_skin=True, q201_scale=11 / 21)
        # spec 5: minimum +X skin radiating-area fraction that closes every criterion in every env (with the saved host, then with the bridge change)
        for tag, extra_kw in (('min_plus_X_skin_area_fraction', {}), ('min_plus_X_skin_area_fraction_with_HOST_CHANGE_bridges', dict(host_bridge_under_lugs=True))):
            if fb(with_skin=True, **extra_kw)['passes']:
                lo, hi = 0.0, 1.0
                for _ in range(10):
                    mid = 0.5 * (lo + hi)
                    if fb(with_skin=True, skin_area_fraction=mid, **extra_kw)['passes']:
                        hi = mid
                    else:
                        lo = mid
                fallback[tag] = dict(fraction=hi, area_mm2=hi * 214 * 214, result=fb(with_skin=True, skin_area_fraction=hi, **extra_kw))
            else:
                fallback[tag] = dict(fraction=None, note='full 214x214 skin does not close in this configuration; no fraction exists')
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
                     patch_override=lambda nl: [nl[0], dict(nl[1], sheet=WEB_SHEET['plus_Y'])])
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
    out = dict(schema='CF1_THERMAL_MATRIX', replay_check=rep, strap_R_K_W=R_STRAP, strap_R_terms_K_W=R_STRAP_TERMS, R_TIM_K_W=R_TIM,
               R_TIM_per_interface_K_W=R_TIM_PER_INTERFACE, R_case_K_W=R_CASE, R_link_K_W=R_LINK,
               lug_patches=dict(minus_Y=LUG_PATCH_MINUS_Y, plus_Y=LUG_PATCH_PLUS_Y), lug_patch_sheets=WEB_SHEET,
               web_model=dict(kind='IN_PLANE_WEB_SHEETS_FROM_PROBE', probe_sha256=hashlib.sha256((C / 'results/mechanical/WEB_FACE_PROBE_CF1.json').read_bytes()).hexdigest(),
                              web_thickness_mm={k: WEB[k]['web_thickness_mm'] for k in WEB}, gap_thickness_mm={k: WEB[k]['gap_thickness_mm'] for k in WEB},
                              gap_material_under_lug_mm3={k: WEB[k]['gap_material_under_lug_mm3'] for k in WEB},
                              bridges={k: [dict(center=b['patch_center_ab_mm'], size=b['patch_size_ab_mm'], area_mm2=b['area_mm2'], R_K_W=WEB[k]['gap_thickness_mm'] * 1e-3 / (K_WEB * b['area_mm2'] * 1e-6),
                                                distance_from_lug_mm=b['distance_from_lug_footprint_mm']) for b in WEB[k]['gap_bridges']] for k in WEB},
                              webs_radiate=False),
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
               fallback=fallback, released_state_same_point=slim(released_same),
               unassigned_heat_sensitivity=dict(method='extra heat spread uniformly over the three modelled faces in proportion to area, 10 mm mesh, evaluated in all four environments; listed temperatures are per-criterion maxima over environments and passes requires every environment',
                                                spec_listed_W=spec_listed, total_unassigned_W=total_unassigned, points=sens,
                                                spec_listed_with_plus_X_skin=sens_skin),
               cold=dict(with_heater=slim(cold), without_heater=slim(cold_noheater), heater_electrical_W=20.0, heater_efficiency=0.8, standby_load_W=60,
                         criterion='NONE_DECLARED (passes=null); temperatures reported for the owner'),
               counterexamples=ce,
               continuous_thermal_closure=bool(all_pass and closure_with_spec_listed),
               closure_with_spec_listed_unassigned_heat=bool(closure_with_spec_listed),
               conditional_on=['module pose clears the host (results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json currently REJECTED)',
                               'lug faces bear on the 2 mm inner web over the declared areas and the web reaches the panel only through the probed bridges (results/mechanical/WEB_FACE_PROBE_CF1.json)',
                               'unassigned heat (see unassigned_heat_sensitivity) is radiated somewhere: this screen places none of it unless stated',
                               '25 psi TIM pressure realised at every interface (clamp design not done)'],
               orbit_validated=False,
               notes=['Module node = carrier; Q201 Tj = carrier + Q201 heat x (0.31 + 1.5) K/W per DESIGN_SPEC; board copper assumed to reach the carrier through the TIM zone.',
                      'Link R = arch riser path + plate spreading (1-D, -Y only) + TIM + bar + TIM + lug through, ending on the 2 mm inner web sheet; the web reaches the radiating panel only through the probed gap-layer bridges (WEB_FACE_PROBE_CF1.json).',
                      'Acceptance is evaluated per criterion over all four environments at 5 mm; passes requires every environment and criterion.'])
    (R / 'THERMAL_ACCEPTANCE_CF1.json').write_text(json.dumps(acc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (R / 'COUNTEREXAMPLES.json').write_text(json.dumps(ce, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(replay=rep['relative_error'], strap_R=R_STRAP, worst=worst_env_by_criterion, min_margins=min_margins,
                          acc5=dict(CHB=acc5['CHB_case_C'], carrier=acc5['carrier_C'], Tj=acc5['Q201_Tj_C'], passes=all_pass),
                          refinement=refinement, fallback={k_: (round(v['CHB_case_C'], 2), round(v['carrier_C'], 2), v['passes']) for k_, v in fallback.items() if isinstance(v, dict) and 'CHB_case_C' in v},
                          min_skin_fraction=(fallback.get('min_plus_X_skin_area_fraction') or {}).get('fraction'),
                          sens=[(s['extra_face_heat_W'], round(s['CHB_case_C'], 2), round(s['carrier_C'], 2), s['passes']) for s in sens],
                          sens_skin=(round(sens_skin['CHB_case_C'], 2), round(sens_skin['carrier_C'], 2), sens_skin['passes']),
                          cold=dict(CHB=cold['CHB_case_C'], carrier=cold['carrier_C'], noheater_CHB=cold_noheater['CHB_case_C']),
                          counterexamples=ce['passed'], negative=negative), ensure_ascii=False))


if __name__ == '__main__':
    main()
