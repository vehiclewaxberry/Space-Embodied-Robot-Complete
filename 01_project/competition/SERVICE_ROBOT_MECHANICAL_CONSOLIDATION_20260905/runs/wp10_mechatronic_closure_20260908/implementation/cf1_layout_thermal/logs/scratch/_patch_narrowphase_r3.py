"""r3 patch of the three narrowphase drivers: explicit registered-role allow-list (everything else, including *_PROXY,
rejects), parent ruling kept as the file status with a separate physical-only view, module-self contact receipt."""
from pathlib import Path
T = Path(__file__).resolve().parents[2] / 'tools'

REGISTERED = """REGISTERED_ENVELOPE_ROLES = ('FUNCTIONAL_ENVELOPE', 'FUNCTIONAL_ENVELOPE_OD6_R21_NO_CUT_LENGTH',
                             'MANUFACTURER_MAX_OUTER_ENVELOPE_NOT_OEM_BREP',
                             'STRANDED_WIRE_AND_INSULATION_MAXIMUM_ENVELOPES_NOMINAL_STATIC_ROUTE')


def is_registered_envelope(role):
    \"\"\"Only these roles are 'registered, not rejecting' (plan Task 9). Every other role, including SIMPLIFIED_PROXY and
    GLASS_FOOTPRINT_CIC_LAYER_PROXY (proxies of real hardware), rejects on any common volume, exactly as the parent tool does.\"\"\"
    return role in REGISTERED_ENVELOPE_ROLES
"""

# ---- narrowphase_cf1.py
p = T / 'narrowphase_cf1.py'; t = p.read_text(encoding='utf-8')
t = t.replace("class _BB:", REGISTERED + "\n\nclass _BB:", 1)
old = """    physical = {k: sorted(v) for k, v in by_role.items() if not any(t in k for t in ('ENVELOPE', 'PROXY'))}
    envelope = {k: sorted(v) for k, v in by_role.items() if any(t in k for t in ('ENVELOPE', 'PROXY'))}"""
new = """    physical = {k: sorted(v) for k, v in by_role.items() if not is_registered_envelope(k)}
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
                       no_interpenetration=all(c['common_volume_with_module_mm3'] < 1e-3 for c in self_check))"""
assert old in t; t = t.replace(old, new, 1)
old2 = """        role_classification_rule="a representation_role containing 'ENVELOPE' or 'PROXY' is treated as envelope/proxy (registered, not rejecting); "
                                 "every other role (PHYSICAL_GEOMETRY, OEM_GEOMETRY, BONDLINE_DESIGN_SOLID, SOURCE_BOUND_TIM_PROJECT_CUT, "
                                 "PROJECT_NOMINAL_*, REUSED_NOMINAL_*, PUBLIC_DIMENSION_BOUND_*, ...) is treated as physical and rejects on any common volume","""
new2 = """        role_classification_rule=dict(registered_not_rejecting=list(REGISTERED_ENVELOPE_ROLES),
                                      everything_else_rejects='including SIMPLIFIED_PROXY and GLASS_FOOTPRINT_CIC_LAYER_PROXY (proxies of real hardware) and every physical/OEM/project role, as in the parent tool'),
        module_self_check=module_self,"""
assert old2 in t; t = t.replace(old2, new2, 1)
old3 = """        states={st: dict(status=v['status'], checked_pairs=len(v['checked_pairs']), collisions=v['collisions'],"""
new3 = """        states={st: dict(parent_status=v['status'], checked_pairs=len(v['checked_pairs']), collisions=v['collisions'],"""
assert old3 in t; t = t.replace(old3, new3, 1)
old4 = """        status=('SAVED_GEOMETRY_CLEAR_ONLY' if not any(v['collisions'] for v in out['states'].values())
                else ('SAVED_GEOMETRY_ENVELOPE_INTERSECTIONS_ONLY' if not physical
                      else 'REJECTED_SAVED_GEOMETRY_INTERFERENCE')),"""
new4 = """        status=out['status'],
        status_basis='parent host_narrowphase ruling: any common volume > 1e-3 mm3 with any host row rejects (the battery D-max envelope counts)',
        physical_only_view=('CLEAR' if not physical else 'REJECTED') + '__registered_envelopes_' + ('present' if envelope else 'none'),"""
assert old4 in t; t = t.replace(old4, new4, 1)
p.write_text(t, encoding='utf-8')

# ---- module_pose_narrowphase_cf1.py and module_pose_local_search_cf1.py: same classifier
for name in ('module_pose_narrowphase_cf1.py', 'module_pose_local_search_cf1.py'):
    q = T / name; s = q.read_text(encoding='utf-8')
    s = s.replace("from narrowphase_cf1 import Part, sha, hn, A, C, R, SPEC, candidate_lock_drift",
                  "from narrowphase_cf1 import Part, sha, hn, A, C, R, SPEC, candidate_lock_drift, is_registered_envelope, REGISTERED_ENVELOPE_ROLES", 1)
    s = s.replace("tgt = envelope if any(t in c['representation_role'] for t in ('ENVELOPE', 'PROXY')) else physical",
                  "tgt = envelope if is_registered_envelope(c['representation_role']) else physical")
    s = s.replace("(env if any(t in c['representation_role'] for t in ('ENVELOPE', 'PROXY')) else phys)",
                  "(env if is_registered_envelope(c['representation_role']) else phys)")
    s = s.replace("if not any(t in c['representation_role'] for t in ('ENVELOPE', 'PROXY'))), default=None)",
                  "if not is_registered_envelope(c['representation_role'])), default=None)")
    s = s.replace("        states={st: dict(status=v['status'], checked_pairs=len(v['checked_pairs']), collisions=v['collisions'],",
                  "        states={st: dict(parent_status=v['status'], checked_pairs=len(v['checked_pairs']), collisions=v['collisions'],")
    if name == 'module_pose_narrowphase_cf1.py':
        s = s.replace("        collision_summary=dict(physical_or_oem=physical, envelope_or_proxy=envelope, physical_collision_free=not physical),",
                      "        collision_summary=dict(physical_or_oem=physical, registered_envelope=envelope, physical_collision_free=not physical),\n        role_classification_rule=dict(registered_not_rejecting=list(REGISTERED_ENVELOPE_ROLES), everything_else_rejects=True),")
    q.write_text(s, encoding='utf-8')
print('narrowphase drivers patched')
