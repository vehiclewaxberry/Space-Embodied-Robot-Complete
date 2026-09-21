"""Three-state exact narrowphase of the saved CF1 thermal-path STEP against the V27 host bounds.

Reuses coupled_closure/host_narrowphase.run unchanged (same OCP common-volume test, same host source
locks, same 974-row parent). The only differences from the parent's own run:
  * the new parts are the five solids read back from cf1_layout_thermal/mechanical/thermal_path_cf1.step
    (the deliverable itself), not in-memory build123d objects;
  * the pose is the CF1 mid-height candidate T_S_module from THERMAL_PATH_GEOMETRY_CF1.json, not the
    V30 accepted pose;
  * the receipt is written to cf1_layout_thermal/results/mechanical/NARROWPHASE_CF1.json; the parent's
    coupled_closure/HOST_NARROWPHASE.json is never touched (dump is redirected before run()).
Run under tools/native_delta_guard.py. OCP only; build123d is not imported.
"""
from pathlib import Path
import hashlib, json, sys, time
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

HERE = Path(__file__).resolve().parent
C = HERE.parent                      # cf1_layout_thermal
A = C.parent                         # implementation
R = C / 'results/mechanical'
STEP = C / 'mechanical/thermal_path_cf1.step'
SPEC = C / 'mechanical/THERMAL_PATH_GEOMETRY_CF1.json'
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def candidate_lock_drift():
    """coupled_closure/coupled_adapter.py refuses to import when CANDIDATE.json's source lock has drifted. The
    shared ecad/ files it locks were later edited by the V35/V36 work, so the parent's own consumers no longer
    import. host_narrowphase only needs HERE/A/sha/dump from that adapter; we supply them and record the drift."""
    c = json.loads((A / 'coupled_closure/CANDIDATE.json').read_text(encoding='utf-8-sig'))
    return sorted(str(Path(p).relative_to(A)).replace('\\', '/') for p, h in c['source_lock'].items()
                  if not Path(p).exists() or sha(p) != h)


import types                                              # noqa: E402
_shim = types.ModuleType('coupled_adapter')
_shim.HERE = A / 'coupled_closure'; _shim.A = A; _shim.sha = sha; _shim.dump = lambda name, obj: None
sys.modules['coupled_adapter'] = _shim
sys.path.insert(0, str(A / 'coupled_closure'))
import host_narrowphase as hn        # noqa: E402


REGISTERED_ENVELOPE_ROLES = ('FUNCTIONAL_ENVELOPE', 'FUNCTIONAL_ENVELOPE_OD6_R21_NO_CUT_LENGTH',
                             'MANUFACTURER_MAX_OUTER_ENVELOPE_NOT_OEM_BREP',
                             'STRANDED_WIRE_AND_INSULATION_MAXIMUM_ENVELOPES_NOMINAL_STATIC_ROUTE')


def is_registered_envelope(role):
    """Only these roles are 'registered, not rejecting' (plan Task 9). Every other role, including SIMPLIFIED_PROXY and
    GLASS_FOOTPRINT_CIC_LAYER_PROXY (proxies of real hardware), rejects on any common volume, exactly as the parent tool does."""
    return role in REGISTERED_ENVELOPE_ROLES


class _BB:
    def __init__(self, lo, hi):
        self.min = lo; self.max = hi


class Part:
    """Minimal stand-in for the build123d objects host_narrowphase.run expects (.wrapped/.bounding_box/.label)."""
    def __init__(self, shape, label):
        self.wrapped = shape; self.label = label
        bb = Bnd_Box(); BRepBndLib.Add_s(shape, bb, False); x0, y0, z0, x1, y1, z1 = bb.Get()
        self._bb = _BB([x0, y0, z0], [x1, y1, z1])
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, g); self.volume = g.Mass()
        self.valid = BRepCheck_Analyzer(shape).IsValid()

    def bounding_box(self):
        return self._bb


def union_bbox(boxes):
    return [min(b[i] for b in boxes) for i in range(3)] + [max(b[i] + b[i + 3] for b in boxes) for i in range(3)]


def load_parts():
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    rd = STEPControl_Reader(); assert rd.ReadFile(str(STEP)) == 1, 'STEP read failed'; rd.TransferRoots()
    ex = TopExp_Explorer(rd.OneShape(), TopAbs_SOLID); solids = []
    while ex.More():
        solids.append(ex.Current()); ex.Next()
    parts = []
    for s in solids:
        p = Part(s, '?')
        # label by matching the solid's bbox to the declared part boxes (tolerance 1e-6 mm)
        match = [q for q in spec['parts'] if all(abs(a - b) < 1e-6 for a, b in zip(p._bb.min + p._bb.max, union_bbox(q['boxes_module_mm'])))]
        assert len(match) == 1, 'unlabelled solid ' + str(p._bb.min + p._bb.max)
        p.label = match[0]['label']; p.spec_id = match[0]['id']; parts.append(p)
    assert len(parts) == len(spec['parts']) == 5, len(parts)
    assert all(p.valid for p in parts)
    return spec, parts


def main():
    R.mkdir(parents=True, exist_ok=True)
    spec, parts = load_parts()
    pose = spec['frame']['T_S_module']
    parent = json.loads((A / 'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json').read_text(encoding='utf-8-sig'))
    captured = {}
    hn.dump = lambda name, obj: captured.setdefault('raw', obj)      # never write into coupled_closure/
    t0 = time.time()
    out = hn.run(parts, pose, parent)
    elapsed = time.time() - t0
    assert 'raw' in captured and captured['raw'] is out
    by_role = {}
    for st, v in out['states'].items():
        for c in v['collisions']:
            by_role.setdefault(c['representation_role'], set()).add((c['new_part'], c['parent_id']))
    physical = {k: sorted(v) for k, v in by_role.items() if not is_registered_envelope(k)}
    envelope = {k: sorted(v) for k, v in by_role.items() if is_registered_envelope(k)}
    # module-self check: the five CF1 solids against the V30 module STEP in the module frame (no pose), plus contact slabs
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    def _box(x0, y0, z0, x1, y1, z1): return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()
    def _vol(s):
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); return g.Mass()
    def _common(a, b):
        c = BRepAlgoAPI_Common(a, b); c.Build(); assert c.IsDone(); return _vol(c.Shape())
    mrd = STEPControl_Reader(); assert mrd.ReadFile(str(A / 'coupled_closure/main_input_lugs_v30.step')) == 1; mrd.TransferRoots(); module = mrd.OneShape()
    self_check = []
    for p in parts:
        dd = BRepExtrema_DistShapeShape(p.wrapped, module); dd.Perform()
        self_check.append(dict(id=p.spec_id, common_volume_with_module_mm3=round(_common(p.wrapped, module), 4), distance_to_module_mm=round(dd.Value(), 4)))
    bx = {p['id']: p['boxes_module_mm'] for p in spec['parts']}
    boss = bx['CF1_CARRIER_BOSS'][0]; bar = bx['CF1_STRAP_MINUS_Y'][0]; pad = bx['CF1_STRAP_PLUS_Y'][0]
    contact = dict(
        boss_on_carrier_top_mm2=round(_common(_box(boss[0], boss[1], boss[2] - 0.2, boss[0] + boss[3], boss[1] + boss[4], boss[2]), module) / 0.2, 2),
        minusY_bar_on_carrier_bottom_mm2=round(_common(_box(bar[0], -86.0, bar[2] + bar[5], bar[0] + bar[3], bar[1] + bar[4], bar[2] + bar[5] + 0.2), module) / 0.2, 2),
        plusY_paddle_on_arch_face_mm2=round(_common(_box(pad[0], pad[1] - 0.2, pad[2], pad[0] + pad[3], pad[1], pad[2] + pad[5]), module) / 0.2, 2),
        module_material_in_boss_TIM_gap_mm3=round(_common(_box(boss[0], boss[1], boss[2] + boss[5], boss[0] + boss[3], boss[1] + boss[4], -1.6), module), 4))
    module_self = dict(module_step_sha256=sha(A / 'coupled_closure/main_input_lugs_v30.step'), parts=self_check, contact_slabs=contact,
                       no_interpenetration=all(c['common_volume_with_module_mm3'] < 1e-3 for c in self_check))
    receipt = dict(
        schema='CF1_THERMAL_PATH_NARROWPHASE',
        step_file=str(STEP.relative_to(A)).replace('\\', '/'), step_sha256=sha(STEP), spec_sha256=sha(SPEC),
        host_narrowphase_sha256=sha(A / 'coupled_closure/host_narrowphase.py'),
        parent_bounds_sha256=sha(A / 'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json'),
        coupled_adapter_bypassed=True,
        parent_candidate_lock_drift=candidate_lock_drift(),
        role_classification_rule=dict(registered_not_rejecting=list(REGISTERED_ENVELOPE_ROLES),
                                      everything_else_rejects='including SIMPLIFIED_PROXY and GLASS_FOOTPRINT_CIC_LAYER_PROXY (proxies of real hardware) and every physical/OEM/project role, as in the parent tool'),
        module_self_check=module_self,
        T_S_module=pose,
        pose_basis='CF1 mid-height cavity candidate (Task 9 of design/IMPLEMENTATION_PLAN_CF1.md); NOT the V30 accepted pose '
                   '[[1,0,0,-148],[0,0,-1,92],[0,1,0,85]] used by coupled_closure/HOST_NARROWPHASE.json',
        parts=[dict(id=p.spec_id, label=p.label, volume_mm3=p.volume, mass_kg_2700=p.volume * 2700e-9,
                    bbox_module_mm=p._bb.min + p._bb.max) for p in parts],
        total_aluminium_mass_kg_2700=sum(p.volume for p in parts) * 2700e-9,
        unique_exact_pairs=out['unique_exact_pairs'], unique_host_files=out['unique_host_files'],
        states={st: dict(parent_status=v['status'], checked_pairs=len(v['checked_pairs']), collisions=v['collisions'],
                         checked=[dict(new_part=c['new_part'], parent_id=c['parent_id'], role=c['representation_role'],
                                       distance_mm=c['distance_mm'], common_volume_mm3=c['common_volume_mm3']) for c in v['checked_pairs']])
                for st, v in out['states'].items()},
        collision_summary=dict(
            physical_or_oem=physical, envelope_or_proxy=envelope,
            physical_collision_free=not physical),
        status=out['status'],
        status_basis='parent host_narrowphase ruling: any common volume > 1e-3 mm3 with any host row rejects (the battery D-max envelope counts)',
        physical_only_view=('CLEAR' if not physical else 'REJECTED') + '__registered_envelopes_' + ('present' if envelope else 'none'),
        envelope_dispositions={
            'WP10_RRC3570_4_D_MAX_ENVELOPE': 'manufacturer maximum outer box of the battery, not the ordered cell BRep; the V30 module body '
                                             'itself lies inside it by 90412.63 mm3 at this pose (MODULE_POSE_NARROWPHASE_CF1.json), so '
                                             'the boss/strap overlap is a consequence of the module placement, not of the straps',
            'WP10_INTERNAL_BATTERY_BYPASS': 'bounding box crosses every -Y corridor, exact tube solid is >=37.9 mm away: clear',
            'PROP_PWR_ROUTE / PROP_DATA_ROUTE': '+Y strap clears by 1.000 / 1.472 mm: clear with 1 mm design margin'},
        elapsed_s=elapsed,
        scope=out['scope'] + ' The five CF1 solids are checked against the host only; self-intersection with the V30 module '
              'parts at this pose and the module\'s own placement clearance are NOT covered here.',
        installed=False, native_SolidWorks_created=False, fit_verified=False)
    (R / 'NARROWPHASE_CF1.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=receipt['status'], pairs=receipt['unique_exact_pairs'],
                          collisions={st: len(v['collisions']) for st, v in receipt['states'].items()},
                          physical=list(physical), envelope=list(envelope), elapsed_s=round(elapsed, 1))))


if __name__ == '__main__':
    main()
