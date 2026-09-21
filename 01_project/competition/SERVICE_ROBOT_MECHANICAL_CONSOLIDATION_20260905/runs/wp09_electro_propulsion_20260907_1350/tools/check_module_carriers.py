"""Independent STEP-only verifier for WP09 local module carriers.

Producer code is never imported. CAD dependencies are loaded only by explicit
main execution under the root's serial resource guard. Assembly schemas and
design contracts are checked before the CAD kernel is initialized.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
R = Path(__file__).resolve().parents[1]
I4 = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pin(snapshots, path, expected=None):
    key = str(Path(path).resolve())
    value = sha(key)
    require(expected is None or value == expected, 'Input SHA mismatch: ' + key)
    require(key not in snapshots or snapshots[key] == value, 'Input changed: ' + key)
    snapshots[key] = value
    return key


def load_helper(path):
    spec = importlib.util.spec_from_file_location('wp09_carrier_independent_geometry', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Audit:
    def __init__(self, output):
        self.output, self.rows, self.inputs = output, [], {}
        self.started = dt.datetime.now(dt.timezone.utc).isoformat()
        self.stage = 'INPUTS'
        self.context = {}

    def check(self, ident, okay, measurement=None, **detail):
        row = dict(id=ident, status='PASS' if okay is True else 'FAIL', detail=detail)
        if measurement is not None:
            row['measurement'] = measurement
        self.rows.append(row)
        return row

    def error(self, ident, exc):
        self.rows.append(dict(id=ident, status='FAIL', exception_type=type(exc).__name__,
                             exception_message=str(exc), traceback=traceback.format_exc()))

    def attempt(self, ident, function):
        try:
            function()
        except Exception as exc:
            self.error(ident, exc)

    def write(self, status='IN_PROGRESS', **extra):
        data = dict(schema='WP09_INDEPENDENT_MODULE_CARRIERS_STEP_CHECK_V1', status=status,
                    started_utc=self.started, checkpoint_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    stage=self.stage, results=self.rows, counts=dict(Counter(x['status'] for x in self.rows)),
                    input_sha256_before=self.inputs, no_producer_imported=True,
                    integrated_into_wp08=False, native_assembly_verified=False, as_built=False,
                    electrical_complete=False, hardware_selected=False, manufacturing_release=False,
                    pressure_system_designed=False, strength_verified=False,
                    **self.context)
        data.update(extra)
        temporary = self.output.with_name(self.output.name + '.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temporary, self.output)


def bbox_difference(a, b):
    return max(abs(a[side][i] - b[side][i]) for side in ('min_mm', 'max_mm') for i in range(3))


def box_from_bounds(g, bounds):
    lo, hi = bounds
    require(len(lo) == len(hi) == 3 and all(hi[i] > lo[i] for i in range(3)), 'Invalid declared box')
    return g.Solid.make_box(*[hi[i] - lo[i] for i in range(3)], g.Plane(origin=lo))


def cylinder(g, point, axis, radius, length):
    require(radius > 0 and length > 0, 'Nonpositive cylinder')
    return g.Solid.make_cylinder(radius, length, g.Plane(origin=point, z_dir=axis))


def ring(g, point, axis, outer_radius, inner_radius, length):
    return cylinder(g, point, axis, outer_radius, length) - cylinder(g, point, axis, inner_radius, length)


def material_difference(g, a, b):
    missing, extra = g.volume(b - a), g.volume(a - b)
    return dict(extra_material_mm3=extra, missing_material_mm3=missing,
                symmetric_difference_mm3=math.fsum((extra, missing)))


def compound(g, shapes):
    # The OCCT compound contains detached, already placed STEP shapes. It is a
    # representation of their material-set union for both directed differences;
    # pair checks separately prohibit unregistered component interpenetration.
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    from build123d import Compound
    result, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result, shape.wrapped)
    return Compound(result)


def check_exact(audit, g, ident, actual, expected):
    af, ef = g.facts(actual), g.facts(expected)
    delta = material_difference(g, actual, expected)
    residual = bbox_difference(af['bbox_mm'], ef['bbox_mm'])
    audit.check('EXACT_CONTRACT_GEOMETRY:' + ident,
                bool(af['shape_valid'] and af['solid_count'] == ef['solid_count'] == 1
                     and residual <= g.linear and delta['symmetric_difference_mm3'] <= g.volume_tol),
                dict(**delta, bbox_max_difference_mm=residual, actual_facts=af, expected_facts=ef),
                scope='Actual exported STEP against an independently constructed contract probe; not OEM full CAD or as-built equivalence.')


def check_bore(audit, g, ident, key, point, axis, diameter, length):
    measured = g.evaluate(dict(kind='axis_bore', part=key, axis_point=point,
                              axis_dir=axis, diameter=diameter, length=length))
    audit.check('AXIS_BORE:' + ident, measured.get('status') == 'PASS', measured,
                scope='Declared centre/axis/diameter material-free probe; exact-shape comparison separately rejects oversized or misplaced bores.')


def reference_parts(g, contract, kind):
    """Validation primitives derived from contract, never from producer objects."""
    p, expected, bores = contract[kind], {}, []
    if kind == 'a3200':
        carrier, board = box_from_bounds(g, p['carrier_box_mm']), box_from_bounds(g, p['board_box_mm'])
        c_lo, c_hi = p['carrier_box_mm']
        b_lo, b_hi = p['board_box_mm']
        for n, (x, y) in enumerate(p['board_holes_xy_mm']):
            board_probe = ((x, y, b_lo[2] - 1), (0, 0, 1), p['board_hole_d_mm'], b_hi[2] - b_lo[2] + 2)
            carrier_probe = ((x, y, c_lo[2] - 1), (0, 0, 1), p['carrier_hole_d_mm'], c_hi[2] - c_lo[2] + 2)
            board = board - cylinder(g, board_probe[0], board_probe[1], board_probe[2] / 2, board_probe[3])
            carrier = carrier - cylinder(g, carrier_probe[0], carrier_probe[1], carrier_probe[2] / 2, carrier_probe[3])
            bores.append((f'BOARD_{n}', 'A3200_BOARD_REFERENCE', *board_probe))
            bores.append((f'CARRIER_BOARD_AXIS_{n}', 'A3200_CARRIER', *carrier_probe))
            z0, z1 = p['spacer_z_mm']
            expected[f'A3200_SPACER_{n}'] = ring(g, (x, y, z0), (0, 0, 1),
                                                p['spacer_outer_d_mm'] / 2, p['spacer_inner_d_mm'] / 2, z1 - z0)
            bores.append((f'SPACER_{n}', f'A3200_SPACER_{n}', (x, y, z0 - 1), (0, 0, 1),
                          p['spacer_inner_d_mm'], z1 - z0 + 2))
            # A sign reversal about local X preserves handedness: R=diag(1,s,s).
            # The source screw has its tip along negative local Z; the nut/washer
            # sources extend positive local Z from their catalogue mating datum.
            for tag, role, z, sign in (
                ('SCREW', 'screw', p['screw_underhead_z_mm'], 1),
                ('TOP_WASHER', 'washer', p['top_washer_z_mm'][0], 1),
                ('BOTTOM_WASHER', 'washer', p['bottom_washer_z_mm'][1], -1),
                ('NUT', 'nut', p['nut_z_mm'][1], -1)):
                source = g.load('CAT:' + role)
                transform = [[1, 0, 0, x], [0, sign, 0, y], [0, 0, sign, z], [0, 0, 0, 1]]
                expected[f'A3200_{tag}_{n}'] = source.moved(g.location(transform))
        for n, (x, y) in enumerate(p['carrier_holes_xy_mm']):
            probe = ((x, y, c_lo[2] - 1), (0, 0, 1), p['carrier_hole_d_mm'], c_hi[2] - c_lo[2] + 2)
            carrier = carrier - cylinder(g, probe[0], probe[1], probe[2] / 2, probe[3])
            bores.append((f'CARRIER_EXTERNAL_{n}', 'A3200_CARRIER', *probe))
        expected.update(A3200_CARRIER=carrier, A3200_BOARD_REFERENCE=board)
    elif kind == 'mips':
        boxes = [box_from_bounds(g, bounds) for bounds in p['carrier_union_boxes_mm']]
        carrier = boxes[0]
        for piece in boxes[1:]:
            carrier = carrier + piece
        for y in p['mounting_y_mm']:
            side = -1 if y < 0 else 1
            for n, z in enumerate(p['mounting_holes_z_mm']):
                point, axis = (p['mounting_holes_x_mm'], y, z), (0, side, 0)
                # Only external material is drilled. The OEM envelope is kept
                # solid because no effective tapped-hole depth is available.
                carrier = carrier - cylinder(g, point, axis, p['side_hole_d_mm'] / 2, 5)
                bores.append((f'CRADLE_SIDE_{side}_{n}', 'MIPS_EXTERNAL_CRADLE', point, axis, p['side_hole_d_mm'], 5))
                ident = f'MIPS_INTERFACE_SHIM_{side}_{n}'
                expected[ident] = ring(g, point, axis, p['shim_outer_d_mm'] / 2,
                                      p['shim_inner_d_mm'] / 2, p['shim_thickness_mm'])
                bores.append((f'SHIM_{side}_{n}', ident, point, axis, p['shim_inner_d_mm'], p['shim_thickness_mm']))
        lo_z = min(bounds[0][2] for bounds in p['carrier_union_boxes_mm'])
        for n, (x, y) in enumerate(p['base_mount_holes_xy_mm']):
            point, axis = (x, y, lo_z - 1), (0, 0, 1)
            carrier = carrier - cylinder(g, point, axis, p['base_mount_hole_d_mm'] / 2, 5)
            bores.append((f'CRADLE_BASE_{n}', 'MIPS_EXTERNAL_CRADLE', point, axis, p['base_mount_hole_d_mm'], 5))
        expected.update(MIPS_EXTERNAL_CRADLE=carrier, MIPS_OEM_MAX_ENVELOPE=box_from_bounds(g, p['equipment_envelope_mm']))
    else:
        raise ValueError('Unknown carrier kind')
    return expected, bores


def run(audit, contract_path, emission_path, kind):
    pins = audit.inputs
    pin(pins, __file__)
    cp = pin(pins, contract_path)
    contract = read(cp)
    require(contract['schema'] == 'WP09_MODULE_CARRIERS_CONTRACT', 'Unexpected contract schema')
    for path, digest in contract['source_inputs'].items():
        pin(pins, path, digest)
    ep = pin(pins, emission_path)
    emission = read(ep)
    require(emission['schema'] == 'WP09_MODULE_LOCAL_EMISSION' and emission['module'] == kind,
            'Unexpected module emission schema or identity')
    require(Path(emission['contract_path']).resolve() == Path(cp) and emission['contract_sha256'] == pins[cp],
            'Emission was built from a different contract')
    require(emission['frame'] == contract[kind]['frame'], 'Emission coordinate frame mismatch')
    pin(pins, emission['producer_path'], emission['producer_sha256'])
    p, parts = contract[kind], {}
    # Exact keys are independently derived, so a missing or extra producer part
    # cannot self-authorize by changing its declared count.
    if kind == 'a3200':
        expected_ids = {'A3200_CARRIER', 'A3200_BOARD_REFERENCE'} | {
            f'A3200_{tag}_{n}' for n in range(len(p['board_holes_xy_mm']))
            for tag in ('SPACER', 'SCREW', 'TOP_WASHER', 'BOTTOM_WASHER', 'NUT')}
        require(len(p['board_holes_xy_mm']) == len(p['carrier_holes_xy_mm']) == 4, 'Four-hole contract required')
        require(abs(p['board_box_mm'][1][2] - p['board_box_mm'][0][2] - p['oem_board_thickness_mm'])
                <= contract['acceptance']['linear_mm'],
                'Board thickness contradicts declared OEM basis')
        require(p['spacer_z_mm'][1] - p['spacer_z_mm'][0] == 3, 'OEM standoff reference must remain 3 mm')
        scope = dict(oem_hole_basis=p['hole_basis'], populated_pcb_component_keepouts_verified=False,
                     actual_fsi_variant_and_alignment_geometry_verified=False, actual_thread_engagement_verified=False,
                     screw_nut_material_exception_enabled=False,
                     nominal_thread_zone_reference=dict(diameter_mm=3, z_interval_mm=p['nut_z_mm'],
                                                        scope='Recorded only; all pair material intersections still required to be zero within numerical tolerance.'))
    else:
        expected_ids = {'MIPS_EXTERNAL_CRADLE', 'MIPS_OEM_MAX_ENVELOPE'} | {
            f'MIPS_INTERFACE_SHIM_{side}_{n}' for side in (-1, 1)
            for n in range(len(p['mounting_holes_z_mm']))}
        require(len(p['mounting_holes_z_mm']) == 2 and len(p['mounting_y_mm']) == 2, 'Four side interfaces required')
        require(p['effective_thread_depth_mm'] is None and p['selected_screw_length_mm'] is None,
                'This checker does not qualify an added thread-depth or fastener-length claim')
        require(p['current_shared_compartment_fit'] is False, 'Unreviewed whole-spacecraft fit upgrade')
        scope = dict(oem_reference_is_solid_max_envelope=True, oem_thread=p['oem_thread'],
                     effective_thread_depth_mm=None, actual_thread_engagement_verified=False,
                     selected_screw_length_mm=None, pressure_components_or_internals_designed=False,
                     current_shared_compartment_fit=False, current_shared_compartment_note=p['current_shared_compartment_note'],
                     front_keepout_basis=p['front_keepout_basis'], plume_or_thrust_vector_verified=False)
    audit.context.update(module=kind, coordinate_frame=p['frame'], contract_path=cp, emission_path=ep,
                         acceptance=dict(contract['acceptance']), scope=scope, unknowns=p['unknowns'])
    require(set(emission['parts']) == expected_ids, 'Exact emitted part membership mismatch')
    require(emission['instances'] == emission['solids'] == p['expected_instances'] == len(expected_ids),
            'Declared instance/solid count mismatch')
    require(emission['integrated_into_wp08'] is False and emission['electrical_complete'] is False,
            'Unsupported emitter integration/electrical claim')
    for ident, row in emission['parts'].items():
        path = pin(pins, row['path'], row['sha256'])
        parts[ident] = dict(path=path, sha256=row['sha256'], T_S_local=I4)
    assembly = emission['assembly_step']
    parts['ASSEMBLY'] = dict(path=pin(pins, assembly['path'], assembly['sha256']),
                             sha256=assembly['sha256'], T_S_local=I4)
    for role, row in contract['catalogue_parts'].items():
        parts['CAT:' + role] = dict(path=pin(pins, row['path'], row['sha256']), sha256=row['sha256'], T_S_local=I4)
    reader_path = pin(pins, contract['geometry_reader'])
    cadgen_root = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src/cadgen')
    require(cadgen_root.is_dir(), 'Missing cadgen helper package')
    for helper in sorted(cadgen_root.rglob('*.py')):
        pin(pins, helper)
    audit.check('HASH_BOUND_EXACT_INPUT_MEMBERSHIP', True, dict(part_ids=sorted(expected_ids), expected_count=len(expected_ids)))
    audit.write()
    reader = load_helper(reader_path)
    g = reader.Geometry(dict(parts=parts, tolerances=contract['acceptance']), pins)
    from build123d import import_step
    g.import_step = import_step
    actual, actual_facts = {}, {}
    audit.stage = 'PART_STEP_READBACK'
    for ident in sorted(expected_ids):
        def read_part(ident=ident):
            shape = g.load(ident)
            fact = g.facts(shape)
            valid = fact['shape_valid'] and fact['solid_count'] == 1 and fact['volume_mm3'] > g.volume_tol
            audit.check('STEP_VALIDITY:' + ident, bool(valid), fact)
            require(valid, 'Invalid or non-single-solid part: ' + ident)
            claimed = emission['parts'][ident]['bbox_mm']
            difference = bbox_difference(fact['bbox_mm'], claimed)
            audit.check('EMISSION_BBOX_READBACK:' + ident, bool(difference <= g.linear),
                        dict(bbox_max_difference_mm=difference, actual_bbox_mm=fact['bbox_mm'], declared_bbox_mm=claimed))
            actual[ident], actual_facts[ident] = shape, fact
        audit.attempt('PART_READ_EXCEPTION:' + ident, read_part)
    require(set(actual) == expected_ids, 'Cannot continue after incomplete or invalid part load')
    expected, bores = reference_parts(g, contract, kind)
    require(set(expected) == expected_ids, 'Independent reference set incomplete')
    audit.stage = 'INDEPENDENT_CONTRACT_GEOMETRY_AND_HOLES'
    for ident in sorted(expected_ids):
        audit.attempt('EXACT_GEOMETRY_EXCEPTION:' + ident,
                      lambda ident=ident: check_exact(audit, g, ident, actual[ident], expected[ident]))
    for hole_id, part_id, point, axis, diameter, length in bores:
        audit.attempt('BORE_EXCEPTION:' + hole_id,
                      lambda hole_id=hole_id, part_id=part_id, point=point, axis=axis, diameter=diameter, length=length:
                      check_bore(audit, g, hole_id, part_id, point, axis, diameter, length))
    audit.write()
    audit.stage = 'ALL_LOCAL_MATERIAL_COMMONS'
    thread_pairs = {frozenset((f'A3200_SCREW_{n}', f'A3200_NUT_{n}')): n for n in range(4)} if kind == 'a3200' else {}
    for a, b in itertools.combinations(sorted(expected_ids), 2):
        def pair(a=a, b=b):
            common = actual[a] & actual[b]
            volume = g.volume(common)
            metadata = {}
            station = thread_pairs.get(frozenset((a, b)))
            if station is not None:
                x, y = p['board_holes_xy_mm'][station]
                region = cylinder(g, (x, y, p['nut_z_mm'][0]), (0, 0, 1), 1.5,
                                  p['nut_z_mm'][1] - p['nut_z_mm'][0])
                outside = 0.0 if volume == 0.0 else g.volume(common - region)
                metadata = dict(corresponding_screw_nut=True, nominal_region_diameter_mm=3,
                                nominal_region_z_mm=p['nut_z_mm'], outside_nominal_region_mm3=outside,
                                allowed_intersection_mm3=0, thread_engagement_credit=False)
            audit.check(f'LOCAL_MATERIAL_COMMON:{a}:{b}', bool(volume <= g.volume_tol),
                        dict(intersection_volume_mm3=volume, **metadata),
                        role_exclusions=False, allowances_enabled=False)
        audit.attempt(f'LOCAL_COMMON_EXCEPTION:{a}:{b}', pair)
    audit.write()
    audit.stage = 'ASSEMBLY_STEP_AND_PART_MATERIAL_UNION'
    loaded_assembly = g.load('ASSEMBLY')
    af = g.facts(loaded_assembly)
    audit.check('ASSEMBLY_STEP_VALIDITY_AND_COUNT', bool(af['shape_valid'] and af['solid_count'] == len(expected_ids)), af)
    part_union = compound(g, [actual[ident] for ident in sorted(expected_ids)])
    difference = material_difference(g, loaded_assembly, part_union)
    audit.check('ASSEMBLY_STEP_EQUALS_EXPORTED_PART_MATERIAL_UNION',
                bool(difference['symmetric_difference_mm3'] <= g.volume_tol), difference,
                method='Both directed actual STEP material differences against OCCT compound of every separately read placed part.',
                part_count=len(expected_ids), source_identity_checks_separate=True)
    # Count and global set equality are complemented by a one-to-one solid
    # matching check, preventing changed export component decomposition credit.
    unmatched = set(range(len(loaded_assembly.solids())))
    solids = list(loaded_assembly.solids())
    solid_facts = [g.facts(s) for s in solids]
    for ident in sorted(expected_ids):
        candidates = [index for index in unmatched if bbox_difference(actual_facts[ident]['bbox_mm'],
                                                                       solid_facts[index]['bbox_mm']) <= g.linear]
        observations, exact = [], []
        for index in candidates:
            delta = material_difference(g, solids[index], actual[ident])
            observations.append(dict(solid_index_zero_based=index, **delta))
            if delta['symmetric_difference_mm3'] <= g.volume_tol:
                exact.append(index)
        okay = len(exact) == 1
        audit.check('ASSEMBLY_SOLID_ONE_TO_ONE:' + ident, okay,
                    dict(candidate_matches=observations, exact_matches=exact))
        if okay:
            unmatched.remove(exact[0])
    audit.check('ASSEMBLY_NO_UNMATCHED_SOLIDS', not unmatched, dict(unmatched_solid_indices=sorted(unmatched)))
    if kind == 'mips':
        audit.stage = 'DECLARED_FRONT_SERVICE_KEEP_OUT'
        keepout = box_from_bounds(g, p['front_design_keepout_mm'])
        for ident in sorted(expected_ids):
            def front(ident=ident):
                measured = g.separation(actual[ident], keepout)
                if ident.startswith('MIPS_INTERFACE_SHIM_'):
                    bb = actual_facts[ident]['bbox_mm']
                    lo, hi = p['front_design_keepout_mm']
                    measured['shim_projection_diagnostic'] = dict(
                        actual_min_x_mm=bb['min_mm'][0],
                        projects_forward_of_equipment_front=bool(bb['min_mm'][0] < hi[0]),
                        y_positive_thickness_overlap_with_keepout=bool(
                            min(bb['max_mm'][1], hi[1]) - max(bb['min_mm'][1], lo[1]) > g.linear),
                        acceptance_credit=False,
                        note='X projection alone is not three-dimensional material intrusion; current shims lie outside the declared keepout Y faces.')
                audit.check('FRONT_DECLARED_KEEPOUT:' + ident,
                            measured['intersection_volume_mm3'] <= g.volume_tol, measured,
                            scope='Only declared 50 mm full-face axial service box. Zero volume may include boundary contact; no plume, nozzle, connector-model or actual spacecraft clearance credit.')
            audit.attempt('FRONT_KEEPOUT_EXCEPTION:' + ident, front)
    audit.stage = 'COVERAGE'
    counts = Counter(row['id'].split(':')[0] for row in audit.rows)
    required = {'STEP_VALIDITY': len(expected_ids), 'EMISSION_BBOX_READBACK': len(expected_ids),
                'EXACT_CONTRACT_GEOMETRY': len(expected_ids), 'AXIS_BORE': len(bores),
                'LOCAL_MATERIAL_COMMON': len(expected_ids) * (len(expected_ids) - 1) // 2,
                'ASSEMBLY_SOLID_ONE_TO_ONE': len(expected_ids)}
    if kind == 'mips':
        required['FRONT_DECLARED_KEEPOUT'] = len(expected_ids)
    audit.check('ALL_REQUIRED_CHECKS_EXECUTED', all(counts[k] == v for k, v in required.items()),
                dict(required=required, actual=dict(counts)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', nargs='?', choices=('a3200', 'mips'))
    parser.add_argument('--module', dest='module_kind', choices=('a3200', 'mips'))
    parser.add_argument('--contract', type=Path, default=R / 'inputs/MODULE_CARRIERS_CONTRACT.json')
    parser.add_argument('--emission', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.kind and args.module_kind and args.kind != args.module_kind:
        parser.error('Positional module and --module disagree')
    args.kind = args.module_kind or args.kind
    if args.kind is None:
        parser.error('Supply a3200 or mips, either positionally or with --module')
    args.emission = args.emission or R / 'results' / args.kind / 'EMISSION.json'
    output = (args.output or R / 'results' / args.kind / 'CHECK.json').resolve()
    require(not output.exists() and not output.with_name(output.name + '.tmp').exists(), 'Existing output protected')
    require(output not in {args.contract.resolve(), args.emission.resolve(), Path(__file__).resolve()}, 'Output overwrites input')
    output.parent.mkdir(parents=True, exist_ok=True)
    audit, completed = Audit(output), False
    audit.write()
    try:
        run(audit, args.contract.resolve(), args.emission.resolve(), args.kind)
        completed = True
    except Exception as exc:
        audit.error('INCOMPLETE_EXECUTION_EXCEPTION', exc)
    after = {}
    for path in audit.inputs:
        try:
            after[path] = sha(path)
        except Exception:
            after[path] = None
    unchanged = audit.inputs == after
    audit.check('ALL_INPUTS_UNCHANGED', unchanged,
                dict(changed=[p for p in audit.inputs if audit.inputs[p] != after[p]]))
    okay = completed and unchanged and bool(audit.rows) and all(r['status'] == 'PASS' for r in audit.rows)
    status = 'PASS_SCOPED_LOCAL_MODULE_CARRIER_STEP_GEOMETRY' if okay else 'FAIL_CLOSED_MODULE_CARRIER_CHECK'
    audit.write(status, completed_all_planned_checks=completed, input_sha256_after=after, inputs_unchanged=unchanged)
    print(json.dumps(dict(status=status, output=str(output), counts=dict(Counter(r['status'] for r in audit.rows))), ensure_ascii=False), flush=True)
    return 0 if okay else 1


if __name__ == '__main__':
    raise SystemExit(main())
