"""Source-bound conservative interface-hole merge; never operates SolidWorks.

Brief: integrate the nine R01/R07 interface hole corrections with the WP10
equipment/thermal branch. All operations use exact OCP BRep booleans in S/mm.
The 873 host is a computational comparison base, not a proven common ancestor.
For the source-reviewed drill-only interfaces use C = X - (B - Y). Keep the
WP10 branch additions and never fill its pre-existing holes using Y-B. This
does not inherit the original R01 closed-hole/edge or strength acceptance.

Ownership: only this script, inputs/INTERFACE_MERGE_PLAN.json,
results/INTERFACE_MERGE.json and nine merged_parts/*.step files are written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

D = Path(__file__).resolve().parents[1]
ROOT = D.parents[1]
RUNS = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs'
W = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
P = D / 'inputs/INTERFACE_MERGE_PLAN.json'
OUT = D / 'results/INTERFACE_MERGE.json'
I = [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def ref(p):
    return {'path': str(p), 'sha256': sha(p)}


def write(p, j):
    p.write_bytes((json.dumps(j, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8'))


def create_plan():
    fmap_path = D / 'inputs/R17_FORWARD_MAP.json'
    imap_path = D / 'inputs/WP10_INCREMENT_MAP.json'
    f, inc = read(fmap_path), read(imap_path)
    bpath = Path(f['base_host']['path'])
    assert sha(bpath) == f['base_host']['sha256']
    base = read(bpath)
    cp = RUNS / 'wp09_interfaces_20260907_1525/results/CANONICAL_NATIVE_INPUTS.json'
    canonical = read(cp)
    cparts = {q['id']: q for q in canonical['unique_parts']}
    cinstances = {q['id']: q for q in canonical['instances']}
    b = {q['id']: q for q in base['states']['service']['rows']}
    x = {q['id']: q for q in inc['states']['service']['rows']}
    y = {q['id']: q for q in f['states']['service']['rows']}
    code = (W / 'spacecraft_model.py').read_text(encoding='utf8')
    assert "for x in xs:angle" not in code  # no implicit execution/import of generator
    assert 'def deck_fastening_parts(P):' in code
    assert "if pn=='WP01-RB-BRIDGE-R2':" in code
    rows = []
    for conflict in f['identity_conflicts']:
        ident, host = conflict['id'], conflict['host_id']
        br, xr, yr = b[host], x[host], y[ident]
        bs = {'path': br['step_path'], 'sha256': br['source_sha256'], 'T_S_step': br['T_S_local']}
        basis = 'Original source is the same local coordinate convention as the native host.'
        if br.get('canonical_id'):
            cc, ci = cparts[br['canonical_id']], cinstances[host]
            assert ci['canonical_id'] == br['canonical_id'] and ci['T_native_to_S'] == br['T_S_local']
            assert ci['source_step'] == br['step_path'] and ci['source_sha256'] == br['source_sha256']
            bs = {'path': cc['path'], 'sha256': cc['sha256'], 'T_S_step': ci['T_native_to_S'],
                  'canonical_binding': ref(cp), 'original_world_source': ref(br['step_path'])}
            basis = 'Host native T belongs to canonical STEP, not the original already-world STEP. C017/C018 canonical evidence binds this pairing.'
        sources = {'B': bs,
                   'X': {'path': xr['step_path'], 'sha256': xr['source_sha256'], 'T_S_step': xr['T_S_step']},
                   'Y': {'path': yr['step_path'], 'sha256': yr['source_sha256'], 'T_S_step': yr['T_S_step']}}
        for source in sources.values():
            assert sha(source['path']) == source['sha256'], source['path']
        for state in ('parking', 'released'):
            brs = {q['id']: q for q in base['states'][state]['rows']}[host]
            xrs = {q['id']: q for q in inc['states'][state]['rows']}[host]
            yrs = {q['id']: q for q in f['states'][state]['rows']}[ident]
            assert brs['step_path'] == br['step_path'] and brs['T_S_local'] == br['T_S_local']
            assert xrs['step_path'] == xr['step_path'] and xrs['T_S_step'] == xr['T_S_step']
            assert yrs['step_path'] == yr['step_path'] and yrs['T_S_step'] == yr['T_S_step']
        if ident == 'WP01-RB-BRIDGE-R2':
            proof = {'source': ref(W / 'spacecraft_model.py'), 'lines': [340, 343],
                     'basis': 'R07-E1 rootadd bridge branch only applies bore() at E1SPEC bolt axes. No carrying boss or flange is added.',
                     'acceptance': ref(RUNS / 'r07_root_longeron_anchoring_20260917/ACCEPTANCE_SUMMARY.json')}
        else:
            proof = {'source': ref(W / 'spacecraft_model.py'), 'lines': [56, 94],
                     'basis': 'R01 deck_fastening_parts reconstructs the existing web/plate/angle and changes drilling patterns. No new carrying boss or flange is intended. Relocated legacy holes would be refilled in the isolated R01 branch; that refill is deliberately NOT applied to the WP10 substrate.',
                     'acceptance': ref(RUNS / 'r01_deck_fastening_20260917/ACCEPTANCE_SUMMARY.json')}
        rows.append({'id': ident, 'host_id': host, 'sources': sources, 'B_coordinate_basis': basis,
                     'expected_B_world_bounds_mm': br.get('bounds_mm', br.get('world_bounds_mm')),
                     'expected_Y_world_bounds_mm': yr['bounds_mm'],
                     'expected_solid_count': 1, 'strategy': 'CUT_ONLY_PRESERVE_X_SUBSTRATE_AND_ADDITIONS',
                     'formula': 'C = X - (B - Y)', 'drill_only_intent_evidence': proof,
                     'states': ['service', 'parking', 'released'], 'output_T_S_step': I,
                     'output': str(D / 'merged_parts' / (re.sub(r'[^A-Za-z0-9_-]', '_', host) + '.step'))})
    assert len(rows) == 9
    plan = {'schema': 'INTERFACE_MERGE_PLAN_V1', 'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'status': 'FROZEN_SOURCE_BOUND_CUT_ONLY_CONSTRUCTION_PLAN', 'input_refs': [ref(fmap_path), ref(imap_path), ref(bpath), ref(cp)],
            'coordinate_frame': 'S_WORLD_MM', 'rows': rows,
            'common_ancestor_proven': False,
            'strategy_reason': '873 predates current mechanical closure but includes WP09 features absent from the R17 branch; never re-add Y-B into WP10.',
            'checks': {'volume_zero_tolerance_mm3': 'max(1e-5, max input volume * 1e-9)',
                       'coordinate_bbox_tolerance_mm': 2e-5, 'minimum_overlap_fraction': 0.7,
                       'linear_boolean_fuzzy_mm': 1e-7},
            'scope': 'Nine interface geometry candidates only. No SolidWorks, whole-fit, load, thermal, electrical or historical acceptance credit.',
            'legacy_hole_note': 'The conservative result retains pre-existing X holes. It does not inherit R01 assertions of old-pattern residual faces = 0 or closed bearing edges.'}
    if P.exists():
        old = read(P)
        assert old['rows'] == plan['rows'] and old['input_refs'] == plan['input_refs'], 'Existing plan differs'
        return old
    write(P, plan)
    return plan


def load_ocp():
    global BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, BRepBuilderAPI_Transform
    global BRepGProp, GProp_GProps, BRepCheck_Analyzer, STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
    global IFSelect_RetDone, gp_Trsf, TopExp_Explorer, TopAbs_SOLID, TopAbs_SHELL, TopoDS, BRep_Tool
    global Bnd_Box, BRepBndLib
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.gp import gp_Trsf
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_SHELL
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib


def volume(shape):
    if shape.IsNull():
        return 0.
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return abs(float(p.Mass()))


def boolean(kind, a, b):
    op = {'common': BRepAlgoAPI_Common, 'cut': BRepAlgoAPI_Cut, 'fuse': BRepAlgoAPI_Fuse}[kind](a, b)
    op.SetRunParallel(False)
    op.SetFuzzyValue(1e-7)
    op.Build()
    assert op.IsDone(), kind + ' failed'
    return op.Shape()


def facts(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    bounds = None if box.IsVoid() else list(box.Get())
    solids, closed = 0, []
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        solids += 1
        solid = TopoDS.Solid_s(ex.Current())
        sx = TopExp_Explorer(solid, TopAbs_SHELL)
        while sx.More():
            closed.append(bool(BRep_Tool.IsClosed_s(TopoDS.Shell_s(sx.Current()))))
            sx.Next()
        ex.Next()
    return {'volume_mm3': volume(shape), 'shape_valid': bool(BRepCheck_Analyzer(shape, True).IsValid()),
            'solid_count': solids, 'shell_closed_flags': closed, 'all_shells_closed': bool(closed) and all(closed),
            'bbox_mm': None if bounds is None else {'min_mm': bounds[:3], 'max_mm': bounds[3:]}}


def load(source):
    assert sha(source['path']) == source['sha256'], 'Input changed'
    rd = STEPControl_Reader()
    assert rd.ReadFile(source['path']) == IFSelect_RetDone
    assert rd.TransferRoots() > 0
    shape = rd.OneShape()
    T = source['T_S_step']
    assert len(T) == 4 and all(len(row) == 4 for row in T) and T[3] == [0., 0., 0., 1.]
    for i in range(3):
        for j in range(3):
            assert abs(sum(T[k][i] * T[k][j] for k in range(3)) - (i == j)) < 1e-9
    t = gp_Trsf()
    t.SetValues(*[T[i][j] for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def bbox_error(actual, expected):
    return max(abs(a - b) for k in ('min_mm', 'max_mm') for a, b in zip(actual[k], expected[k]))


def merge_one(row):
    start = time.monotonic()
    result = {'id': row['id'], 'host_id': row['host_id'], 'strategy': row['strategy'],
              'sources': row['sources'], 'status': 'RUNNING', 'output': None,
              'engineering_acceptance_inherited': False, 'whole_assembly_fit_evaluated': False}
    try:
        b, x, y = [load(row['sources'][key]) for key in ('B', 'X', 'Y')]
        f = {k: facts(s) for k, s in [('B', b), ('X', x), ('Y', y)]}
        result['source_facts'] = f
        assert all(z['shape_valid'] and z['solid_count'] == 1 and z['all_shells_closed'] for z in f.values()), 'Invalid/open/multiple-solid source'
        eB = bbox_error(f['B']['bbox_mm'], row['expected_B_world_bounds_mm'])
        eY = bbox_error(f['Y']['bbox_mm'], row['expected_Y_world_bounds_mm'])
        result['coordinate_bbox_errors_mm'] = {'B': eB, 'Y': eY}
        assert max(eB, eY) <= 2e-5, 'Coordinate source/T mismatch'
        tol = max(1e-5, max(z['volume_mm3'] for z in f.values()) * 1e-9)
        result['zero_volume_tolerance_mm3'] = tol
        overlap = {'BX': volume(boolean('common', b, x)), 'BY': volume(boolean('common', b, y))}
        ratios = {'BX': overlap['BX'] / min(f['B']['volume_mm3'], f['X']['volume_mm3']),
                  'BY': overlap['BY'] / min(f['B']['volume_mm3'], f['Y']['volume_mm3'])}
        result['source_overlap_volume_mm3'] = overlap
        result['source_overlap_fraction'] = ratios
        assert min(ratios.values()) >= 0.7, 'Sources do not share sufficient positioned substrate'
        dx, dy = boolean('cut', b, x), boolean('cut', b, y)
        ax, ay = boolean('cut', x, b), boolean('cut', y, b)
        result['branch_delta_volumes_mm3'] = {'B_minus_X_cut': volume(dx), 'B_minus_Y_cut': volume(dy),
                                             'X_minus_B_add': volume(ax), 'Y_minus_B_ignored_fill_or_old_branch_difference': volume(ay)}
        result['Y_minus_B_policy'] = 'Not accepted as material addition. The source intent is hole correction; WP10 substrate and pre-existing holes take priority. R01 old-hole removal/closed-edge acceptance is not inherited.'
        cross = {'X_cut_intersect_Y_add': volume(boolean('common', dx, ay)),
                 'Y_cut_intersect_X_add': volume(boolean('common', dy, ax))}
        result['direct_cut_add_overlap_mm3'] = cross
        assert max(cross.values()) <= tol, 'Cross-branch addition/deletion conflict'
        candidate = boolean('cut', x, dy)
        cf = facts(candidate)
        result['candidate_facts'] = cf
        assert cf['shape_valid'] and cf['solid_count'] == 1 and cf['all_shells_closed'], 'Merged candidate not one valid closed solid'
        checks = {
            'WP10_deleted_material_not_restored': volume(boolean('common', candidate, dx)),
            'R17_deleted_material_not_restored': volume(boolean('common', candidate, dy)),
            'WP10_added_material_not_lost': volume(boolean('cut', ax, candidate)),
            'candidate_adds_no_material_to_X': volume(boolean('cut', candidate, x)),
            'no_unintended_material_removed_from_X': volume(boolean('cut', boolean('cut', x, candidate), dy)),
            'all_R17_cuts_intersecting_X_removed': volume(boolean('cut', boolean('common', x, dy), boolean('cut', x, candidate))),
        }
        result['preservation_residual_volumes_mm3'] = checks
        assert max(checks.values()) <= tol, 'Boolean intent preservation failed'
        target = Path(row['output'])
        assert target.parent == D / 'merged_parts'
        assert not target.exists(), 'Refuse overwriting previously emitted candidate'
        target.parent.mkdir(exist_ok=True)
        wr = STEPControl_Writer()
        assert wr.Transfer(candidate, STEPControl_AsIs) == IFSelect_RetDone
        assert wr.Write(str(target)) == IFSelect_RetDone
        cold = load({'path': str(target), 'sha256': sha(target), 'T_S_step': I})
        coldfacts = facts(cold)
        residuals = {'saved_minus_candidate': volume(boolean('cut', cold, candidate)),
                     'candidate_minus_saved': volume(boolean('cut', candidate, cold))}
        result['STEP_readback'] = {'facts': coldfacts, 'symmetric_difference_volumes_mm3': residuals}
        assert coldfacts['shape_valid'] and coldfacts['solid_count'] == 1 and coldfacts['all_shells_closed']
        assert max(residuals.values()) <= tol, 'Saved STEP differs from candidate'
        result.update(status='CANDIDATE_GEOMETRY_MERGED_BOOLEAN_INTENT_CHECKED', output={**ref(target), 'T_S_step': I},
                      new_native_material_applied=False, solidworks_started=False,
                      snapshot_status='PENDING_PARENT_INTEGRATED_SNAPSHOT',
                      limitation='Conservative hole-preserving merge can retain legacy open holes/notches; bearing-edge, fastener fit and full assembly checks must be new.')
    except Exception as exc:
        result.update(status='BLOCKED_FAIL_CLOSED', reason=repr(exc))
    result['elapsed_s'] = time.monotonic() - start
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan-only', action='store_true')
    ap.add_argument('--id')
    args = ap.parse_args()
    plan = create_plan()
    if args.plan_only:
        print(json.dumps({'plan': str(P), 'sha256': sha(P), 'rows': len(plan['rows'])}))
        return
    load_ocp()
    results = read(OUT) if OUT.exists() else {'schema': 'INTERFACE_MERGE_RESULT_V1', 'plan': ref(P), 'rows': [],
                                            'whole_design_complete': False, 'manufacturing_release': False,
                                            'historical_PASS_inherited': False, 'CAD_engine': 'OCP_NATIVE_BREP_BOOLEAN',
                                            'solidworks_started': False}
    assert results['plan'] == ref(P)
    done = {q['id'] for q in results['rows']}
    for row in plan['rows']:
        if row['id'] in done or (args.id and row['id'] != args.id):
            continue
        import psutil
        assert psutil.virtual_memory().available / 2**20 >= 512, 'Memory floor'
        r = merge_one(row)
        results['rows'].append(r)
        results['completed_count'] = len(results['rows'])
        results['candidate_count'] = sum(q['status'].startswith('CANDIDATE_') for q in results['rows'])
        results['blocked_count'] = sum(q['status'] == 'BLOCKED_FAIL_CLOSED' for q in results['rows'])
        results['status'] = 'IN_PROGRESS' if len(results['rows']) < 9 else 'COMPLETED_WITH_BLOCKERS' if results['blocked_count'] else 'NINE_INTERFACE_CANDIDATES_BUILT_NO_ASSEMBLY_RELEASE'
        results['generator'] = ref(Path(__file__))
        write(OUT, results)
        print(json.dumps({'id': r['id'], 'status': r['status'], 'reason': r.get('reason'), 'elapsed_s': r['elapsed_s']}, ensure_ascii=False), flush=True)
        gc.collect()


if __name__ == '__main__':
    main()
