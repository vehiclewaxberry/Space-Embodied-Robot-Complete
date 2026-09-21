"""Independent STEP-only check of the WP08 +Y rear rib local candidate.

Run explicitly, under the root's serial CAD resource guard. The producer is
hashed but never imported. All geometry comes from exported, hash-bound STEP.
Default output is a new results/rear_rib/CHECK.json; existing output is protected.
This checker gives no native-integration, thread, strength or flight credit.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import gc
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
IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
REPLACED = ('rear_launch_bulkhead', 'rear_vertical_rib_86')
CONTEXT = 'CONTEXT_RB_end_frame_-1'
STATES = ('service', 'parking', 'released')


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def pin(snapshots, path, expected=None):
    path = str(Path(path).resolve())
    digest = sha(path)
    if expected is not None:
        require(digest == expected, 'SHA256 mismatch: ' + path)
    require(path not in snapshots or snapshots[path] == digest, 'Input changed: ' + path)
    snapshots[path] = digest
    return path


def box(value):
    require(isinstance(value, dict), 'Missing AABB')
    lo, hi = value['min_mm'], value['max_mm']
    require(len(lo) == len(hi) == 3, 'AABB must have three coordinates')
    require(all(math.isfinite(float(v)) for v in lo + hi), 'Nonfinite AABB')
    require(all(lo[i] <= hi[i] for i in range(3)), 'Inverted AABB')
    return {'min_mm': list(lo), 'max_mm': list(hi)}


def box_gap(a, b):
    # Lower bound on Euclidean separation; zero means BRep evaluation required.
    axis = [max(a['min_mm'][i] - b['max_mm'][i], b['min_mm'][i] - a['max_mm'][i], 0.0)
            for i in range(3)]
    return math.sqrt(sum(x*x for x in axis))


class Audit:
    def __init__(self, output):
        self.output, self.rows, self.snapshots = output, [], {}
        self.started = dt.datetime.now(dt.timezone.utc).isoformat()
        self.stage = 'INITIAL_INPUT_VALIDATION'
        self.extra = {}

    def write(self, status='IN_PROGRESS', **extra):
        data = dict(schema='WP08_REAR_RIB_INDEPENDENT_STEP_CHECK_V1', status=status,
                    started_utc=self.started, checkpoint_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    stage=self.stage, counts=dict(Counter(r['status'] for r in self.rows)), results=self.rows,
                    input_sha256_before=self.snapshots, no_producer_generator_loaded=True,
                    integrated_into_wp08_three_state=False, physical_assembly_completed=False,
                    continuous_motion_verified=False, strength_verified=False, thread_qualified=False,
                    preload_verified=False, manufacturing_release=False, **self.extra)
        data.update(extra)
        temporary = self.output.with_name(self.output.name + '.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temporary, self.output)

    def check(self, ident, condition, measurement=None, **detail):
        # Nested payload cannot replace the controlling id/status, even if a
        # measurement function returns fields named id or status.
        row = dict(id=ident, status='PASS' if condition is True else 'FAIL', detail=detail)
        if measurement is not None:
            row['measurement'] = measurement
        self.rows.append(row)
        return row

    def error(self, ident, exc):
        self.rows.append(dict(id=ident, status='FAIL', exception_type=type(exc).__name__,
                              exception_message=str(exc), traceback=traceback.format_exc()))

    def perform(self, ident, callback):
        try:
            callback()
        except Exception as exc:
            self.error(ident, exc)


def material_outside(g, material, allowance):
    volume = g.volume(material)
    # Never subtract an empty Common: some OCCT versions treat its topology as
    # invalid even though the completed solid-material measurement is zero.
    if volume == 0.0:
        return volume, 0.0
    return volume, g.volume(material - allowance)


def run(audit, emission_path, contract_path):
    s = audit.snapshots
    pin(s, __file__)
    pin(s, contract_path)
    c = read(contract_path)
    audit.extra.update(contract_path=str(contract_path), thresholds=dict(c['acceptance']),
                       unknowns=c['unknowns'],
                       scope='Independent local STEP geometry only; three-state neighbourhood checks are against pinned WP08 source instances, not a new native assembly.',
                       tool_scope={'actual_tool_model': None, 'outer_diameter_mm': 8,
                                   'swept_length_mm': 40, 'hex_fit_verified': False,
                                   'initial_assembly': 'Straight approach to both fastener ends against final placed geometry only; not an ordered insertion simulation.',
                                   'maintenance': 'Same declared straight access envelopes; no operational access procedure or actual driver/socket is qualified.',
                                   'final_engagement_exceptions': 'Rear corresponding screw only; front corresponding screw and nut only. No other role or part exclusion.'})
    for path, digest in c['source_inputs'].items():
        pin(s, path, digest)
    pin(s, emission_path)
    emission = read(emission_path)
    require(emission['contract_sha256'] == s[str(contract_path.resolve())], 'Emission contract mismatch')
    require(Path(emission['contract_path']).resolve() == contract_path.resolve(), 'Emission contract path mismatch')
    pin(s, emission['producer_path'], emission['producer_sha256'])
    pin(s, emission['assembly_step']['path'], emission['assembly_step']['sha256'])
    manifest_path = pin(s, c['manifest_path'], c['manifest_sha256'])
    manifest = read(manifest_path)
    require(set(manifest['states']) == set(STATES), 'Exactly three manifest poses required')
    p, tol = c['parameters'], c['acceptance']
    require(p['axis_y_mm'] == 90 and p['axis_z_mm'] == [-50, 50], 'Unreviewed bore axes')
    require(p['clearance_hole_d_mm'] == 3.4 and p['tool_outer_d_mm'] == 8, 'Unreviewed bore/tool diameter')
    require(p['nut_bottom_x_mm'] == -182.5 and p['nominal_nut_outer_x_mm'] == -180.1,
            'Unreviewed permitted thread region')
    require([p['driver_sweep_min_x_mm'], p['driver_tip_x_mm'], p['socket_tip_x_mm'], p['socket_sweep_max_x_mm']]
            == [-236.5, -196.5, -182.5, -142.5], 'Unreviewed tool sweep')
    ltol, vtol = tol['linear_mm'], tol['volume_mm3']
    hardware = [f'WP08_REAR_YPLUS_{z}_{role}' for z in (-50, 50)
                for role in ('screw', 'washer_head', 'washer_inner', 'nut')]
    expected = set(REPLACED) | {CONTEXT} | set(hardware)
    require(set(emission['parts']) == expected, 'Emission must contain exactly 2 replacements, 8 hardware and 1 context')
    require((emission['replacement_count'], emission['addition_count'], emission['context_count']) == (2, 8, 1),
            'Emission count contract mismatch')
    parts = {}
    for ident, row in emission['parts'].items():
        pin(s, row['path'], row['sha256'])
        parts[ident] = dict(path=row['path'], sha256=row['sha256'], T_S_local=IDENTITY)
    parts['EMITTED_ASSEMBLY'] = dict(**emission['assembly_step'], T_S_local=IDENTITY)
    neighbours = {}
    for state in STATES:
        rows = manifest['states'][state]['instances']
        require(len(rows) == manifest['states'][state]['component_count'] == 625, 'Incomplete current state: ' + state)
        require(len({r['id'] for r in rows}) == 625, 'Duplicate current instance IDs: ' + state)
        require(set(REPLACED).issubset({r['id'] for r in rows}), 'Replaced instances absent')
        neighbours[state] = []
        for row in rows:
            path = row['step_path']
            digest = row['source_sha256']
            if 'source_step' in row:
                require(path == row['source_step']['path'] and digest == row['source_step']['sha256'],
                        'Conflicting source references: ' + row['id'])
            pin(s, path, digest)
            key = state + ':' + row['id']
            parts[key] = dict(path=path, sha256=digest, T_S_local=row['T_S_local'])
            neighbours[state].append(dict(id=row['id'], key=key, bbox=box(row['world_bounds_mm']),
                                          representation_role=row['representation_role']))
        byid = {row['id']: row for row in rows}
        for ident, declared in c['sources_by_state'][state].items():
            current = byid[ident]
            require((declared['path'], declared['sha256'], declared['T_S_local']) ==
                    (current['step_path'], current['source_sha256'], current['T_S_local']),
                    'Contract/current neighbourhood mismatch: ' + state + ':' + ident)
    for ident, row in c['sources_by_state']['service'].items():
        parts['OLD:' + ident] = row
    # Independently form the catalogue placements from the declared axial stack.
    for z in (-50, 50):
        for role, source, x, sign in (
            ('screw', 'screw', -195.5, -1), ('washer_head', 'washer', -195, -1),
            ('washer_inner', 'washer', -183, 1), ('nut', 'nut', -182.5, 1)):
            cat = c['catalogue_parts'][source]
            parts['CAT:' + f'WP08_REAR_YPLUS_{z}_{role}'] = dict(path=cat['path'], sha256=cat['sha256'],
                T_S_local=[[0, 0, sign, x], [1, 0, 0, 90], [0, sign, 0, z], [0, 0, 0, 1]])
    # Pin local helper sources before importing any of them. The two explicit
    # readers and cadgen helper package are the only project helper dependency.
    geometry_path = pin(s, c['geometry_reader'])
    bearing_path = pin(s, c['bearing_reader'])
    cadgen_root = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src/cadgen')
    require(cadgen_root.is_dir(), 'Missing installed cadgen helper package')
    for path in sorted(cadgen_root.rglob('*.py')):
        pin(s, path)
    audit.check('HASH_BOUND_INPUTS_AND_EXACT_COVERAGE', True,
                neighbour_count_per_pose=625, new_hardware=8, replacements=list(REPLACED),
                context_not_new=CONTEXT, no_role_filter=True, all_source_steps_sha_checked=True)
    audit.write()
    reader = module(geometry_path, 'wp08_rear_independent_geometry')
    bearing = module(bearing_path, 'wp08_rear_independent_bearing')
    g = reader.Geometry(dict(parts=parts, tolerances=tol), s)
    from build123d import import_step
    g.import_step = import_step
    shapes, facts = {}, {}
    audit.stage = 'EXPORTED_STEP_READBACK'
    for ident in sorted(expected):
        def check_shape(ident=ident):
            shape = g.load(ident)
            fact = g.facts(shape)
            audit.check('READBACK:' + ident, bool(fact['shape_valid'] and fact['solid_count'] == 1 and fact['volume_mm3'] > vtol), fact)
            require(fact['shape_valid'] and fact['solid_count'] == 1 and fact['volume_mm3'] > vtol, 'Invalid candidate ' + ident)
            shapes[ident], facts[ident] = shape, fact
        audit.perform('READBACK_EXCEPTION:' + ident, check_shape)
    require(set(shapes) == expected, 'Cannot continue with missing or invalid candidate STEP')
    assembly_fact = g.facts(g.load('EMITTED_ASSEMBLY'))
    audit.check('ASSEMBLY_STEP_READBACK_11_SOLIDS', bool(assembly_fact['shape_valid'] and assembly_fact['solid_count'] == 11), assembly_fact)
    audit.write()

    def compare(ident, reference):
        a, b = shapes[ident], g.load(reference)
        av, bv = g.volume(a - b), g.volume(b - a)
        audit.check('EXACT_SOURCE_SHAPE:' + ident, bool(av + bv <= vtol),
                    dict(candidate_minus_reference_mm3=av, reference_minus_candidate_mm3=bv,
                         symmetric_difference_mm3=av + bv), reference=reference)

    audit.stage = 'SOURCE_PRESERVATION_AND_BORES'
    for ident in hardware:
        audit.perform('SOURCE_COMPARE_EXCEPTION:' + ident, lambda ident=ident: compare(ident, 'CAT:' + ident))
    audit.perform('CONTEXT_COMPARE_EXCEPTION', lambda: compare(CONTEXT, 'OLD:RB_end_frame_-1'))
    probes = {z: g.Solid.make_cylinder(1.7, 16, g.Plane(origin=(-197, 90, z), z_dir=(1, 0, 0))) for z in (-50, 50)}
    allowance = probes[-50] + probes[50]
    for ident in REPLACED:
        def preservation(ident=ident):
            old, new = g.load('OLD:' + ident), shapes[ident]
            added = g.volume(new - old)
            removed = old - new
            removed_volume, outside = material_outside(g, removed, allowance)
            per_hole = {str(z): g.volume(removed & probe) for z, probe in probes.items()}
            audit.check('ONLY_TWO_BORES_REMOVED:' + ident,
                        bool(added <= vtol and outside <= vtol and all(v > vtol for v in per_hole.values())),
                        dict(added_material_mm3=added, removed_material_mm3=removed_volume,
                             removed_outside_two_declared_cylinders_mm3=outside, removed_per_hole_mm3=per_hole),
                        original_holes_preservation='No added material anywhere, and original material unchanged outside the two new bore cylinders; existing voids remain void.',
                        machining_tolerance_qualified=False)
        audit.perform('SOURCE_PRESERVATION_EXCEPTION:' + ident, preservation)
        for z in (-50, 50):
            def bore(ident=ident, z=z):
                measurement = g.evaluate(dict(kind='axis_bore', part=ident, axis_point=[-197, 90, z],
                                             axis_dir=[1, 0, 0], diameter=3.4, length=16))
                audit.check(f'THROUGH_BORE:{ident}:{z}', measurement.get('status') == 'PASS', measurement)
            audit.perform(f'BORE_EXCEPTION:{ident}:{z}', bore)
    audit.write()

    audit.stage = 'ACTUAL_PLANAR_CONTACT_AND_LOCAL_PAIRS'
    contacts = [(REPLACED[1], REPLACED[0], -189)]
    for z in (-50, 50):
        name = lambda role: f'WP08_REAR_YPLUS_{z}_{role}'
        contacts.extend([(name('screw'), name('washer_head'), -195.5),
                         (name('washer_head'), REPLACED[1], -195),
                         (REPLACED[0], name('washer_inner'), -183),
                         (name('washer_inner'), name('nut'), -182.5)])
    for a, b, plane in contacts:
        def contact(a=a, b=b, plane=plane):
            measurement = bearing.contact_area(shapes[a], shapes[b], [1, 0, 0], plane, ltol)
            area = measurement.get('contact_area_mm2')
            okay = measurement.get('status') == 'MEASURED' and area is not None and area >= tol['minimum_contact_area_mm2']
            audit.check(f'CONTACT:{a}:{b}', bool(okay), measurement,
                        required_nominal_area_mm2=tol['minimum_contact_area_mm2'],
                        scope='Nominal trimmed planar geometry only; no preload, flatness, material, bearing stress or thread qualification.')
        audit.perform(f'CONTACT_EXCEPTION:{a}:{b}', contact)
    thread_regions = {}
    for z in (-50, 50):
        pair = frozenset((f'WP08_REAR_YPLUS_{z}_screw', f'WP08_REAR_YPLUS_{z}_nut'))
        thread_regions[pair] = g.Solid.make_cylinder(1.5, 2.4, g.Plane(origin=(-182.5, 90, z), z_dir=(1, 0, 0)))
    for a, b in itertools.combinations(sorted(expected), 2):
        def local_pair(a=a, b=b):
            common = shapes[a] & shapes[b]
            volume = g.volume(common)
            region = thread_regions.get(frozenset((a, b)))
            excess = volume if region is None else material_outside(g, common, region)[1]
            audit.check(f'LOCAL_PAIR:{a}:{b}', bool(excess <= vtol),
                        dict(actual_intersection_volume_mm3=volume, unallowed_intersection_volume_mm3=excess),
                        allowance=None if region is None else {'x_interval_mm': [-182.5, -180.1], 'diameter_mm': 3,
                            'qualification': 'Only nominal corresponding screw/nut thread-zone overlap; actual thread engagement unqualified'})
        audit.perform(f'LOCAL_PAIR_EXCEPTION:{a}:{b}', local_pair)
    audit.write()

    def screen(probe_id, probe_shape, probe_bbox, targets, prefix, allowed=()):
        separated, brep_count, exception_count, fail_count = [], 0, 0, 0
        allowed = set(allowed)
        for target in targets:
            ident, key = target['id'], target['key']
            try:
                gap = box_gap(probe_bbox, target['bbox'])
                if gap > ltol:
                    separated.append({'id': ident, 'aabb_distance_lower_bound_mm': gap})
                    continue
                brep_count += 1
                other = shapes[key] if key in shapes else g.load(key)
                measured = g.separation(probe_shape, other)
                is_engagement = ident in allowed
                okay = is_engagement or measured['intersection_volume_mm3'] <= vtol
                if not okay:
                    fail_count += 1
                audit.check(f'{prefix}:BREP:{probe_id}:{ident}', bool(okay), measured,
                            representation_role=target.get('representation_role'),
                            final_tool_engagement_exception=is_engagement,
                            exception_scope='Declared same-axis final tool-to-fastener engagement only; actual tool/socket hex-fit unqualified.' if is_engagement else None)
            except Exception as exc:
                exception_count += 1
                audit.error(f'{prefix}:BREP_EXCEPTION:{probe_id}:{ident}', exc)
        audit.check(f'{prefix}:COVERAGE:{probe_id}', bool(len(separated) + brep_count == len(targets) and not exception_count and not fail_count),
                    dict(total_targets=len(targets), aabb_separated_count=len(separated),
                         brep_attempted_count=brep_count, exception_count=exception_count, fail_count=fail_count,
                         aabb_separated=separated), no_role_exclusions=True,
                    source_AABB='Pinned current manifest world AABB for retained neighbours; freshly measured STEP AABB for candidate parts.',
                    absent_brep_for_separated_pairs='Strictly disjoint AABB is a sufficient no-material-intersection screen; no actual minimum distance is asserted.')
        audit.write()
        gc.collect()

    audit.stage = 'NEW_HARDWARE_VS_ALL_CURRENT_NEIGHBOURS'
    for state in STATES:
        targets = [row for row in neighbours[state] if row['id'] not in REPLACED]
        require(len(targets) == 623, 'Unexpected neighbour exclusions')
        for ident in hardware:
            screen(ident, shapes[ident], box(facts[ident]['bbox_mm']), targets, f'NEIGHBOUR:{state}')
    audit.stage = 'DECLARED_TOOL_APPROACH_SWEEPS'
    for state in STATES:
        targets = [row for row in neighbours[state] if row['id'] not in REPLACED]
        for ident in tuple(REPLACED) + tuple(hardware):
            targets.append(dict(id=ident, key=ident, bbox=box(facts[ident]['bbox_mm']),
                                representation_role=emission['parts'][ident]['representation_role']))
        require(len(targets) == len({row['id'] for row in targets}) == 633, 'Tool target set duplicates or misses components')
        require(sum(row['id'] == 'RB_end_frame_-1' for row in targets) == 1, 'Context must remain exactly once')
        for z in (-50, 50):
            for side, start, finish in [('rear', -236.5, -196.5), ('front', -182.5, -142.5)]:
                sweep = g.Solid.make_cylinder(4, finish - start, g.Plane(origin=(start, 90, z), z_dir=(1, 0, 0)))
                allowed = [f'WP08_REAR_YPLUS_{z}_screw']
                if side == 'front':
                    allowed.append(f'WP08_REAR_YPLUS_{z}_nut')
                screen(f'{side}:{z}', sweep, box(g.facts(sweep)['bbox_mm']), targets,
                       f'TOOL:{state}', allowed=allowed)
    audit.stage = 'FINAL_COVERAGE_AND_INPUT_RECHECK'
    prefix_counts = Counter(row['id'].split(':')[0] for row in audit.rows)
    expected_prefix_counts = {'READBACK': 11, 'EXACT_SOURCE_SHAPE': 9, 'ONLY_TWO_BORES_REMOVED': 2,
                              'THROUGH_BORE': 4, 'CONTACT': 9, 'LOCAL_PAIR': 55}
    audit.check('REQUIRED_LOCAL_CHECK_COVERAGE', all(prefix_counts[k] == v for k, v in expected_prefix_counts.items()),
                dict(actual=dict(prefix_counts), required=expected_prefix_counts))
    coverage = [row for row in audit.rows if ':COVERAGE:' in row['id']]
    audit.check('REQUIRED_NEIGHBOUR_AND_TOOL_COVERAGE',
                len(coverage) == 36 and all(row['status'] == 'PASS' for row in coverage),
                dict(hardware_rows_expected=24, tool_rows_expected=12, actual_rows=len(coverage),
                     expected_hardware_pair_screenings=8 * 623 * 3, expected_tool_pair_screenings=4 * 633 * 3))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emission', type=Path, default=R / 'results/rear_rib/EMISSION.json')
    parser.add_argument('--contract', type=Path, default=R / 'inputs/REAR_RIB_DESIGN_CONTRACT.json')
    parser.add_argument('--output', type=Path, default=R / 'results/rear_rib/CHECK.json')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    require(not output.exists() and not output.with_name(output.name + '.tmp').exists(), 'Existing checker output protected')
    require(output not in {args.emission.resolve(), args.contract.resolve(), Path(__file__).resolve()}, 'Output overwrites input')
    output.parent.mkdir(parents=True, exist_ok=True)
    audit = Audit(output)
    audit.write()
    complete = False
    try:
        run(audit, args.emission.resolve(), args.contract.resolve())
        complete = True
    except Exception as exc:
        audit.error('CHECKER_ABORTED_BEFORE_COMPLETE', exc)
    after = {}
    for path in audit.snapshots:
        try:
            after[path] = sha(path)
        except Exception:
            after[path] = None
    unchanged = audit.snapshots == after
    audit.check('INPUT_FILES_UNCHANGED', unchanged, dict(changed=[p for p in audit.snapshots if audit.snapshots[p] != after[p]]))
    okay = complete and unchanged and bool(audit.rows) and all(row['status'] == 'PASS' for row in audit.rows)
    status = 'PASS_LOCAL_REAR_RIB_NOMINAL_GEOMETRY_ONLY' if okay else 'FAIL_CLOSED_LOCAL_REAR_RIB_CHECK'
    audit.write(status, completed_all_planned_checks=complete, input_sha256_after=after,
                input_files_unchanged=unchanged)
    print(json.dumps(dict(status=status, counts=dict(Counter(r['status'] for r in audit.rows)), output=str(output)), ensure_ascii=False), flush=True)
    return 0 if okay else 1


if __name__ == '__main__':
    raise SystemExit(main())
