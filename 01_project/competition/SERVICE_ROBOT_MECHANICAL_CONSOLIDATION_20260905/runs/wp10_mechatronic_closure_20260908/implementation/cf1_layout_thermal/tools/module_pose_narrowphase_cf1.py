"""Exact three-state narrowphase of the existing V30 lug module (coupled_closure/main_input_lugs_v30.step,
56 instances, the same STEP Codex screened in LAYOUT_EXACT_V33.json) at the CF1 mid-height pose.

The CF1 thermal architecture assumes the module sits at T_S_module = [[1,0,0,-24],[0,1,0,30],[0,0,1,61.6]].
That pose was never exactly screened: the V30 accepted pose is REJECTED in coupled_closure/HOST_NARROWPHASE.json
(18 collisions per state) and the three V33 shortlist poses are all acceptable_clearance_candidate=false.
This script answers, for this one pose, whether the module body itself clears the V27 host rows.
Same host_narrowphase.run, same parent, receipt to results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json.
"""
from pathlib import Path
import json, time
from OCP.STEPControl import STEPControl_Reader
from narrowphase_cf1 import Part, sha, hn, A, C, R, SPEC, candidate_lock_drift, is_registered_envelope, REGISTERED_ENVELOPE_ROLES

MODULE = A / 'coupled_closure/main_input_lugs_v30.step'


def main():
    R.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC.read_text(encoding='utf-8')); pose = spec['frame']['T_S_module']
    rd = STEPControl_Reader(); assert rd.ReadFile(str(MODULE)) == 1; rd.TransferRoots()
    module = Part(rd.OneShape(), 'WP10_V30_LUG_MODULE_56_INSTANCES_AT_CF1_POSE')
    parent = json.loads((A / 'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json').read_text(encoding='utf-8-sig'))
    hn.dump = lambda name, obj: None
    t0 = time.time(); out = hn.run([module], pose, parent); elapsed = time.time() - t0
    physical = {}; envelope = {}
    for st, v in out['states'].items():
        for c in v['collisions']:
            tgt = envelope if is_registered_envelope(c['representation_role']) else physical
            tgt.setdefault(c['parent_id'], {})[st] = round(c['common_volume_mm3'], 3)
    v33 = json.loads((A / 'coupled_closure/LAYOUT_EXACT_V33.json').read_text(encoding='utf-8-sig'))
    receipt = dict(
        schema='CF1_MODULE_POSE_NARROWPHASE',
        module_step=str(MODULE.relative_to(A)).replace('\\', '/'), module_step_sha256=sha(MODULE),
        same_module_step_as_LAYOUT_EXACT_V33=sha(MODULE) == v33['module_step_sha256'],
        module_bbox_module_mm=module._bb.min + module._bb.max, module_valid=module.valid,
        T_S_module=pose,
        host_narrowphase_sha256=sha(A / 'coupled_closure/host_narrowphase.py'),
        parent_bounds_sha256=sha(A / 'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json'),
        coupled_adapter_bypassed=True, parent_candidate_lock_drift=candidate_lock_drift(),
        unique_exact_pairs=out['unique_exact_pairs'], unique_host_files=out['unique_host_files'],
        states={st: dict(parent_status=v['status'], checked_pairs=len(v['checked_pairs']), collisions=v['collisions'],
                         checked=[dict(parent_id=c['parent_id'], role=c['representation_role'], distance_mm=c['distance_mm'],
                                       common_volume_mm3=c['common_volume_mm3']) for c in v['checked_pairs']])
                for st, v in out['states'].items()},
        collision_summary=dict(physical_or_oem=physical, registered_envelope=envelope, physical_collision_free=not physical),
        role_classification_rule=dict(registered_not_rejecting=list(REGISTERED_ENVELOPE_ROLES), everything_else_rejects=True),
        status=('MODULE_POSE_CLEAR_OF_HOST_SOLIDS' if not any(v['collisions'] for v in out['states'].values())
                else ('MODULE_POSE_ENVELOPE_INTERSECTIONS_ONLY' if not physical else 'MODULE_POSE_REJECTED_PHYSICAL_INTERFERENCE')),
        context=dict(V30_accepted_pose_status=json.loads((A / 'coupled_closure/HOST_NARROWPHASE.json').read_text(encoding='utf-8-sig'))['status'],
                     V33_shortlist_acceptable=[r['acceptable_clearance_candidate'] for r in v33['results']]),
        elapsed_s=elapsed,
        scope='Whole V30 module compound versus V27 host rows at one pose. Module self-consistency, the 23 unrepresented '
              'reference bodies, harness bends and the CF1 straps are outside this file. Not a fit verification.',
        installed=False, fit_verified=False)
    (R / 'MODULE_POSE_NARROWPHASE_CF1.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=receipt['status'], pairs=out['unique_exact_pairs'],
                          collisions={st: len(v['collisions']) for st, v in out['states'].items()},
                          physical=list(physical), envelope=list(envelope), elapsed_s=round(elapsed, 1))))


if __name__ == '__main__':
    main()
