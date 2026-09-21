"""Bounded local exact search around the CF1 module pose.

MODULE_POSE_NARROWPHASE_CF1.json rejects the pose [[1,0,0,-24],[0,1,0,30],[0,0,1,61.6]] on four small physical
overlaps (CLAMP_DUAL_BASE 384 mm3, CLAMP_DUAL_LID 19 mm3, POST_DUAL_0/1 9 mm3 each) plus envelope overlaps.
This script asks one narrow question: does a translation of at most a few millimetres clear the physical parts?
Same module STEP, same host_narrowphase.run, same V27 parent, one exact run per candidate translation.
It adopts nothing: the result is a table, and the CF1 straps/thermal patches remain defined for the nominal pose.
"""
from pathlib import Path
import json, time, itertools
from OCP.STEPControl import STEPControl_Reader
from narrowphase_cf1 import Part, sha, hn, A, C, R, SPEC, candidate_lock_drift, is_registered_envelope, REGISTERED_ENVELOPE_ROLES

MODULE = A / 'coupled_closure/main_input_lugs_v30.step'
DX = [0.0]
DY = [0.0, -2.0, -4.0, -6.0]
DZ = [0.0, 2.0, 4.0, 6.0]


def main():
    R.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC.read_text(encoding='utf-8')); base = spec['frame']['T_S_module']
    rd = STEPControl_Reader(); assert rd.ReadFile(str(MODULE)) == 1; rd.TransferRoots()
    module = Part(rd.OneShape(), 'WP10_V30_LUG_MODULE_56_INSTANCES')
    parent = json.loads((A / 'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json').read_text(encoding='utf-8-sig'))
    hn.dump = lambda name, obj: None
    rows = []; t_all = time.time()
    for dx, dy, dz in itertools.product(DX, DY, DZ):
        pose = [list(r) for r in base]; pose[0][3] = base[0][3] + dx; pose[1][3] = base[1][3] + dy; pose[2][3] = base[2][3] + dz
        t0 = time.time(); out = hn.run([module], pose, parent); el = time.time() - t0
        phys = {}; env = {}
        for st, v in out['states'].items():
            for c in v['collisions']:
                (env if is_registered_envelope(c['representation_role']) else phys).setdefault(c['parent_id'], {})[st] = round(c['common_volume_mm3'], 3)
        min_phys_dist = min((c['distance_mm'] for v in out['states'].values() for c in v['checked_pairs']
                             if not is_registered_envelope(c['representation_role'])), default=None)
        rows.append(dict(delta_mm=[dx, dy, dz], T_S_module=pose, physical=phys, envelope=env,
                         physical_volume_mm3=sum(max(v.values()) for v in phys.values()),
                         envelope_volume_mm3=sum(max(v.values()) for v in env.values()),
                         min_distance_to_physical_mm=min_phys_dist, exact_pairs=out['unique_exact_pairs'], elapsed_s=el))
        print(json.dumps(dict(delta=[dx, dy, dz], physical_mm3=rows[-1]['physical_volume_mm3'], envelope_mm3=rows[-1]['envelope_volume_mm3'],
                              phys=list(phys), min_d=min_phys_dist, s=round(el, 1))), flush=True)
    clear = [r for r in rows if not r['physical']]
    best = min(rows, key=lambda r: (r['physical_volume_mm3'], r['envelope_volume_mm3']))
    receipt = dict(schema='CF1_MODULE_POSE_LOCAL_SEARCH', module_step_sha256=sha(MODULE), base_T_S_module=base,
                   grid_mm=dict(dx=DX, dy=DY, dz=DZ), poses_checked=len(rows), rows=rows,
                   physically_clear_poses=[r['delta_mm'] for r in clear],
                   best=dict(delta_mm=best['delta_mm'], physical_volume_mm3=best['physical_volume_mm3'], envelope_volume_mm3=best['envelope_volume_mm3'], physical=best['physical'], envelope=best['envelope']),
                   coupled_adapter_bypassed=True, parent_candidate_lock_drift=candidate_lock_drift(),
                   elapsed_s=time.time() - t_all, adopted=False,
                   scope='Translation-only, finite grid, module body only (no straps, no unrepresented reference bodies). A clear pose here '
                         'would still need the CF1 straps, lug patches and thermal screen re-derived for it. Not a fit verification.')
    (R / 'MODULE_POSE_LOCAL_SEARCH_CF1.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(poses=len(rows), physically_clear=[r['delta_mm'] for r in clear], best=best['delta_mm'], best_phys=best['physical_volume_mm3'], elapsed_s=round(receipt['elapsed_s'], 1))))


if __name__ == '__main__':
    main()
