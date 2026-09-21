"""Independent STEP-only check of the WP09 battery-carrier mount local candidate.

Run explicitly, under the root's serial CAD resource guard. The producer is
hashed but never imported. All geometry comes from exported, hash-bound STEP.
Default output is a new results/battery_mount/CHECK.json; existing output is protected.
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
REPLACED = ('adapter_battery', 'lower_equipment_deck')
CONTEXT_IDS = ('equipment_battery', 'thermal_interface_battery')
CONTEXT = tuple('CONTEXT_' + name for name in CONTEXT_IDS)
XY = tuple(itertools.product((-152, -76), (-78, 78)))
HARDWARE = tuple(f'WP09_BAT_{x}_{y}_{role}' for x, y in XY for role in ('screw', 'washer', 'nut'))
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
        data = dict(schema='WP09_BATTERY_MOUNT_INDEPENDENT_STEP_CHECK_V1', status=status,
                    started_utc=self.started, checkpoint_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    stage=self.stage, counts=dict(Counter(r['status'] for r in self.rows)), results=self.rows,
                    input_sha256_before=self.snapshots, no_producer_generator_loaded=True,
                    integrated_into_wp08_three_state=False, physical_assembly_completed=False,
                    battery_self_retention_verified=False, electrical_closure=False,
                    pressure_hardware_qualified=False, native_integration_verified=False,
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



def cone_contact(a, b, xy, top, linear, bearing):
    """Common of actual trimmed main conical faces; no projected substitute."""
    from OCP.GeomAbs import GeomAbs_Cone
    k = bearing._kernel()
    selected = []
    for shape in (a, b):
        faces = []
        for face in bearing._faces(shape.wrapped, k):
            surface = k['BRepAdaptor_Surface'](face, True)
            if surface.GetType() != GeomAbs_Cone:
                continue
            cone = surface.Cone()
            apex = tuple(float(v) for v in cone.Apex().Coord())
            axis = tuple(float(v) for v in cone.Axis().Direction().Coord())
            bbox = bearing._bbox(face, k)
            if (math.hypot(axis[0], axis[1]) > 1e-10 or
                abs(abs(float(cone.SemiAngle())) - math.pi / 4) > 1e-10 or
                max(abs(apex[i] - (xy[0], xy[1], top - 3.2)[i]) for i in range(3)) > linear or
                bbox is None or bbox['min_mm'][2] < top - 1.7 - linear or
                bbox['max_mm'][2] > top + linear):
                continue
            faces.append((face, dict(apex_mm=list(apex), axis=list(axis), bbox_mm=bbox,
                                    area_mm2=bearing._area(face, k),
                                    occt_face_tolerance_mm=float(k['BRep_Tool'].Tolerance_s(face)))))
        require(bool(faces), 'No actual coaxial main head/seat cone at ' + str(xy))
        # Reject duplicate overlapping patches before summing pairwise Common.
        for (left, _), (right, _) in itertools.combinations(faces, 2):
            require(bearing._common(left, right, k)['area_mm2'] == 0,
                    'Ambiguous duplicated conical face area')
        selected.append(faces)
    pairs = []
    for i, (left, _) in enumerate(selected[0]):
        for j, (right, _) in enumerate(selected[1]):
            measured = bearing._common(left, right, k)
            pairs.append(dict(a_face=i, b_face=j, **measured))
    return dict(status='MEASURED', contact_area_mm2=math.fsum(p['area_mm2'] for p in pairs),
                a_faces=[x[1] for x in selected[0]], b_faces=[x[1] for x in selected[1]],
                actual_trimmed_face_common=pairs, fuzzy_tolerance_mm=0.0,
                nominal_apex_S_mm=[xy[0], xy[1], top - 3.2],
                scope='Coincident trimmed main cones only; no stress, preload or machining-tolerance credit.')


def run(audit, emission_path, contract_path):
    s = audit.snapshots
    pin(s, __file__)
    pin(s, contract_path)
    c = read(contract_path)
    require(c['schema'] == 'WP09_BATTERY_CARRIER_MOUNT_CONTRACT' and c['frame'] == 'S_WORLD_MM',
            'Wrong battery mount contract/frame')
    p, tol, tool = c['parameters'], c['acceptance'], c['tool_envelopes']
    require(tol == dict(linear_mm=1e-5, volume_mm3=1e-5, integration_eps=1e-7,
                        min_bearing_area_mm2=0.01), 'Unreviewed acceptance change')
    fixed = dict(axis_x_mm=[-152.0, -76.0], axis_y_mm=[-78.0, 78.0], axis_direction=[0, 0, 1],
                 adapter_bottom_z_mm=-98.15, adapter_top_z_mm=-96.15,
                 deck_bottom_z_mm=-101.15, deck_top_z_mm=-98.15, hole_d_mm=3.4,
                 countersink_top_virtual_d_mm=6.4, countersink_included_angle_deg=90.0,
                 countersink_cone_depth_mm=1.5, screw_top_z_mm=-96.15, screw_tip_z_mm=-106.15,
                 washer_top_z_mm=-101.15, washer_bottom_z_mm=-101.65,
                 nut_top_z_mm=-101.65, nut_bottom_z_mm=-104.05, nominal_protrusion_mm=2.1)
    require(all(p[k] == v for k, v in fixed.items()), 'Unreviewed dimensional/stack contract change')
    require(tuple(c['replaced_ids']) == REPLACED and tuple(c['context_ids']) == CONTEXT_IDS,
            'Unexpected replaced/context IDs')
    fixed_tools = dict(top_driver_d_mm=4.0, top_driver_length_mm=40.0,
                       top_driver_z_min_mm=-96.15, bottom_socket_d_mm=8.0,
                       bottom_socket_inner_clearance_d_mm=4.0, bottom_socket_length_mm=40.0,
                       bottom_socket_z_max_mm=-104.05,
                       top_stage_removed_ids=list(CONTEXT_IDS))
    require(all(tool.get(k) == v for k, v in fixed_tools.items()), 'Unreviewed tool or removal scope')
    audit.extra.update(contract_path=str(contract_path), thresholds=dict(tol), unknowns=c['unknowns'],
        scope='Independent exported local STEP nominal geometry only; not battery retention or whole electrical/mechanical closure.',
        tool_scope={'initial_carrier_fastening_removed_ids':list(CONTEXT_IDS),
                    'upper': 'OD4 x 40 mm straight driver; final battery and pad conflicts reported independently.',
                    'lower': 'OD8/ID4 annular 40 mm approach ending at nut outer face z=-104.05 mm.',
                    'actual_tool_model':None, 'hex_engagement_verified':False,
                    'removal_sequence_verified':False,
                    'exceptions':'No positive structural overlap permitted. Only corresponding hardware terminal face contact; no blanket hardware volume exemption.'},
        final_state_upper_tool_diagnostics=[], final_state_upper_tool_clearance=None)
    for path, digest in c['source_inputs'].items():
        pin(s, path, digest)
    pin(s, emission_path)
    emission = read(emission_path)
    require(emission['contract_sha256'] == s[str(contract_path.resolve())], 'Emission contract hash mismatch')
    require(Path(emission['contract_path']).resolve() == contract_path.resolve(), 'Emission contract path mismatch')
    pin(s, emission['producer_path'], emission['producer_sha256'])
    pin(s, emission['assembly_step']['path'], emission['assembly_step']['sha256'])
    manifest = read(pin(s, c['manifest_path'], c['manifest_sha256']))
    require(set(manifest['states']) == set(STATES), 'Exactly three poses required')
    expected = set(REPLACED) | set(CONTEXT) | set(HARDWARE)
    require(len(expected) == 16 and set(emission['parts']) == expected,
            'Expected exactly 2 modifications, 12 hardware, 2 context solids')
    for key, value in [('replacement_count',2), ('addition_count',12), ('context_count',2)]:
        if key in emission:
            require(emission[key] == value, 'Wrong emitted ' + key)
    parts = {}
    for ident, row in emission['parts'].items():
        pin(s, row['path'], row['sha256'])
        require(row.get('T_S_local', IDENTITY) == IDENTITY, 'Candidate STEP must be S-world identity: '+ident)
        parts[ident] = dict(path=row['path'], sha256=row['sha256'], T_S_local=IDENTITY)
        box(row['bbox_mm'])
    parts['EMITTED_ASSEMBLY'] = dict(**emission['assembly_step'], T_S_local=IDENTITY)
    neighbours = {}
    for state in STATES:
        rows = manifest['states'][state]['instances']
        require(len(rows) == manifest['states'][state]['component_count'] == 625, 'Incomplete pose '+state)
        require(len({r['id'] for r in rows}) == 625, 'Duplicate IDs in '+state)
        byid = {r['id']:r for r in rows}
        require(set(REPLACED + CONTEXT_IDS).issubset(byid), 'Missing replacement/context in '+state)
        neighbours[state] = []
        for row in rows:
            path, digest = row['step_path'], row['source_sha256']
            if 'source_step' in row:
                require((path,digest) == (row['source_step']['path'],row['source_step']['sha256']),
                        'Conflicting manifest source references '+row['id'])
            pin(s, path, digest)
            key = state + ':' + row['id']
            parts[key] = dict(path=path, sha256=digest, T_S_local=row['T_S_local'])
            neighbours[state].append(dict(id=row['id'], key=key, bbox=box(row['world_bounds_mm']),
                                          representation_role=row['representation_role']))
        require(set(c['sources_by_state'][state]) == set(REPLACED + CONTEXT_IDS),
                'Incomplete contract sources in '+state)
        for ident, declared in c['sources_by_state'][state].items():
            row = byid[ident]
            require((declared['path'],declared['sha256'],declared['T_S_local']) ==
                    (row['step_path'],row['source_sha256'],row['T_S_local']), 'Source/T mismatch '+state+':'+ident)
    for ident, row in c['sources_by_state']['service'].items():
        parts['OLD:'+ident] = row
    # Independent rigid matrices: screw retains +Z; bottom hardware local +Z -> S -Z.
    for x, y in XY:
        for role, z, sign in [('screw',p['screw_top_z_mm'],1),
                              ('washer',p['washer_top_z_mm'],-1),('nut',p['nut_top_z_mm'],-1)]:
            cat = c['catalogue_parts'][role]
            pin(s, cat['path'], cat['sha256'])
            name = f'WP09_BAT_{x}_{y}_{role}'
            parts['CAT:'+name] = dict(path=cat['path'], sha256=cat['sha256'],
                T_S_local=[[1,0,0,x],[0,sign,0,y],[0,0,sign,z],[0,0,0,1]])
    geometry_path = Path(pin(s, c['geometry_reader']))
    bearing_path = Path(pin(s, geometry_path.with_name('check_bearing_faces.py')))
    cadgen_root = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src/cadgen')
    require(cadgen_root.is_dir(), 'Missing cadgen helper package')
    for path in sorted(cadgen_root.rglob('*.py')):
        pin(s, path)
    audit.check('HASH_BOUND_INPUTS_AND_COVERAGE', True,
                neighbour_count_per_pose=625, hardware_count=12, replacements=list(REPLACED),
                context_not_added=list(CONTEXT_IDS), all_source_steps_sha_checked=True, no_role_filter=True)
    audit.write()
    reader = module(geometry_path, 'wp09_independent_battery_geometry')
    bearing = module(bearing_path, 'wp09_independent_battery_faces')
    g = reader.Geometry(dict(parts=parts, tolerances=tol), s)
    from build123d import import_step
    g.import_step = import_step
    ltol, vtol = tol['linear_mm'], tol['volume_mm3']
    shapes, facts = {}, {}
    audit.stage = 'EXPORTED_LOCAL_STEP_READBACK'
    for ident in sorted(expected):
        def candidate(ident=ident):
            shape = g.load(ident)
            fact = g.facts(shape)
            bound = box(emission['parts'][ident]['bbox_mm'])
            delta = max(abs(fact['bbox_mm'][side][i]-bound[side][i]) for side in ('min_mm','max_mm') for i in range(3))
            good = bool(fact['shape_valid'] and fact['solid_count']==1 and fact['volume_mm3']>vtol and delta<=ltol)
            audit.check('READBACK:'+ident, good, fact, max_emission_bbox_error_mm=delta)
            require(good, 'Invalid candidate/readback '+ident)
            shapes[ident], facts[ident] = shape, fact
        audit.perform('READBACK_EXCEPTION:'+ident, candidate)
    require(set(shapes)==expected, 'Missing valid local STEP')
    assembly = g.load('EMITTED_ASSEMBLY')
    assembly_fact = g.facts(assembly)
    audit.check('ASSEMBLY_STEP_READBACK_16_SOLIDS',
                bool(assembly_fact['shape_valid'] and assembly_fact['solid_count']==16), assembly_fact)
    require(assembly_fact['shape_valid'] and assembly_fact['solid_count']==16, 'Invalid local assembly STEP')
    remaining = list(assembly.solids())
    for ident in sorted(expected):
        candidates = []
        for i, solid in enumerate(remaining):
            fb = box(g.facts(solid)['bbox_mm'])
            error = max(abs(fb[k][n]-facts[ident]['bbox_mm'][k][n]) for k in ('min_mm','max_mm') for n in range(3))
            if error<=ltol:
                difference = g.volume(solid-shapes[ident])+g.volume(shapes[ident]-solid)
                if difference<=vtol:
                    candidates.append((i,difference))
        require(len(candidates)==1, 'Ambiguous/missing assembly occurrence '+ident)
        index, diff = candidates[0]
        remaining.pop(index)
        audit.check('ASSEMBLY_MEMBER:'+ident, True, dict(symmetric_difference_mm3=diff))
    require(not remaining, 'Unmatched local assembly solids')
    del remaining, assembly
    audit.write()

    def compare(ident, reference):
        current, original = shapes[ident], g.load(reference)
        added, lost = g.volume(current-original), g.volume(original-current)
        audit.check('EXACT_SOURCE_SHAPE:'+ident, bool(added+lost<=vtol),
                    dict(candidate_minus_reference_mm3=added, reference_minus_candidate_mm3=lost,
                         symmetric_difference_mm3=added+lost), reference=reference)
    audit.stage = 'SOURCE_PRESERVATION_AND_MATCHING_BORES'
    for ident in HARDWARE:
        audit.perform('SOURCE_COMPARE_EXCEPTION:'+ident, lambda ident=ident: compare(ident,'CAT:'+ident))
    for ident in CONTEXT_IDS:
        audit.perform('CONTEXT_COMPARE_EXCEPTION:'+ident, lambda ident=ident: compare('CONTEXT_'+ident,'OLD:'+ident))
    cylinders, cones = {}, {}
    for x,y in XY:
        cylinders[(x,y)] = g.Solid.make_cylinder(1.7, 7, g.Plane(origin=(x,y,-102.15),z_dir=(0,0,1)))
        cones[(x,y)] = g.Solid.make_cone(1.7, 3.2, 1.5, g.Plane(origin=(x,y,-97.65),z_dir=(0,0,1)))
    def merged(values):
        iterator = iter(values)
        value = next(iterator)
        for other in iterator:
            value = value + other
        return value
    for ident in REPLACED:
        def preservation(ident=ident):
            tools = cones if ident=='adapter_battery' else cylinders
            allowance = merged(tools.values())
            old, new = g.load('OLD:'+ident), shapes[ident]
            added = g.volume(new-old)
            removed = old-new
            removed_volume, outside = material_outside(g,removed,allowance)
            per_hole = {f'{x}_{y}':g.volume(removed & probe) for (x,y),probe in tools.items()}
            independently_expected = old-allowance
            expected_difference = g.volume(new-independently_expected)+g.volume(independently_expected-new)
            audit.check('ONLY_DECLARED_MODIFICATIONS:'+ident,
                        bool(added<=vtol and outside<=vtol and expected_difference<=vtol and all(v>vtol for v in per_hole.values())),
                        dict(added_material_mm3=added,removed_material_mm3=removed_volume,
                             removed_outside_allowance_mm3=outside,removed_per_hole_mm3=per_hole,
                             symmetric_difference_from_independent_expected_cut_mm3=expected_difference),
                        allowed_operation='Four specified countersinks only' if ident=='adapter_battery' else 'Four diameter3.4 through bores only',
                        original_voids_preserved=True, tolerance_strength_qualified=False)
        audit.perform('MODIFICATION_EXCEPTION:'+ident,preservation)
        for x,y in XY:
            def bore(ident=ident,x=x,y=y):
                measured=g.evaluate(dict(kind='axis_bore',part=ident,axis_point=[x,y,-102.15],
                                         axis_dir=[0,0,1],diameter=3.4,length=7))
                audit.check(f'THROUGH_BORE:{ident}:{x}:{y}',measured.get('status')=='PASS',measured)
            audit.perform(f'BORE_EXCEPTION:{ident}:{x}:{y}',bore)
    audit.write()
    audit.stage = 'ACTUAL_CONTACT_AND_LOCAL_PAIRS'
    contacts = [('adapter_battery','lower_equipment_deck',-98.15),
                ('adapter_battery','CONTEXT_thermal_interface_battery',-96.15),
                ('CONTEXT_thermal_interface_battery','CONTEXT_equipment_battery',-95.65)]
    thread_regions={}
    for x,y in XY:
        name=lambda role:f'WP09_BAT_{x}_{y}_{role}'
        contacts += [('lower_equipment_deck',name('washer'),-101.15),
                     (name('washer'),name('nut'),-101.65)]
        thread_regions[frozenset((name('screw'),name('nut')))] = g.Solid.make_cylinder(
            1.5,2.4,g.Plane(origin=(x,y,-104.05),z_dir=(0,0,1)))
        def countersink(x=x,y=y):
            measurement=cone_contact(shapes[f'WP09_BAT_{x}_{y}_screw'],shapes['adapter_battery'],(x,y),-96.15,ltol,bearing)
            audit.check(f'CONE_CONTACT:{x}:{y}',bool(measurement['contact_area_mm2']>=tol['min_bearing_area_mm2']),measurement,
                        required_minimum_contact_mm2=tol['min_bearing_area_mm2'],positive_preload_or_strength_credit=False)
        audit.perform(f'CONE_CONTACT_EXCEPTION:{x}:{y}',countersink)
        def stack(x=x,y=y):
            prefix=f'WP09_BAT_{x}_{y}_'
            expected_intervals={'screw':[-106.15,-96.15],'washer':[-101.65,-101.15],'nut':[-104.05,-101.65]}
            errors={role:max(abs(facts[prefix+role]['bbox_mm'][key][2]-z) for key,z in zip(('min_mm','max_mm'),interval))
                    for role,interval in expected_intervals.items()}
            protrusion=facts[prefix+'nut']['bbox_mm']['min_mm'][2]-facts[prefix+'screw']['bbox_mm']['min_mm'][2]
            audit.check(f'AXIAL_STACK:{x}:{y}',bool(max(errors.values())<=ltol and abs(protrusion-2.1)<=ltol),
                        dict(interval_error_mm=errors,nominal_exposed_tip_mm=protrusion),actual_thread_engagement_verified=False)
        audit.perform(f'STACK_EXCEPTION:{x}:{y}',stack)
    for a,b,z in contacts:
        def planar(a=a,b=b,z=z):
            measured=bearing.contact_area(shapes[a],shapes[b],[0,0,1],z,ltol)
            area=measured.get('contact_area_mm2')
            okay=measured.get('status')=='MEASURED' and area is not None and area>=tol['min_bearing_area_mm2']
            audit.check(f'PLANAR_CONTACT:{a}:{b}',bool(okay),measured,
                        required_minimum_contact_mm2=tol['min_bearing_area_mm2'],
                        scope='Actual trimmed planar-face Common; no thermal, load, preload, or battery retention credit.')
        audit.perform(f'PLANAR_CONTACT_EXCEPTION:{a}:{b}',planar)
    for a,b in itertools.combinations(sorted(expected),2):
        def pair(a=a,b=b):
            common=shapes[a]&shapes[b]
            total=g.volume(common)
            region=thread_regions.get(frozenset((a,b)))
            excess=total if region is None else material_outside(g,common,region)[1]
            audit.check(f'LOCAL_PAIR:{a}:{b}',bool(excess<=vtol),
                        dict(actual_intersection_volume_mm3=total,unallowed_intersection_volume_mm3=excess),
                        allowance=None if region is None else dict(type='Corresponding nominal screw/nut thread region only',
                            diameter_mm=3,z_interval_mm=[-104.05,-101.65],actual_thread_qualified=False))
        audit.perform(f'LOCAL_PAIR_EXCEPTION:{a}:{b}',pair)
    audit.write()

    def screen(probe_id,probe_shape,probe_bbox,targets,prefix,terminal_hardware=()):
        separated,brep_count,exceptions,failures=[],0,0,0
        for target in targets:
            ident,key=target['id'],target['key']
            try:
                gap=box_gap(probe_bbox,target['bbox'])
                if gap>ltol:
                    separated.append(dict(id=ident,aabb_distance_lower_bound_mm=gap))
                    continue
                brep_count+=1
                other=shapes[key] if key in shapes else g.load(key)
                measurement=g.separation(probe_shape,other)
                okay=measurement['intersection_volume_mm3']<=vtol
                failures+=int(not okay)
                audit.check(f'{prefix}:BREP:{probe_id}:{ident}',bool(okay),measurement,
                            representation_role=target.get('representation_role'),
                            corresponding_terminal_hardware=ident in terminal_hardware,
                            positive_volume_exemption_applied=False,
                            scope='No role exclusion; terminal touching is allowed but no structural or full-hardware volume exemption.')
            except Exception as exc:
                exceptions+=1
                audit.error(f'{prefix}:BREP_EXCEPTION:{probe_id}:{ident}',exc)
        audit.check(f'{prefix}:COVERAGE:{probe_id}',bool(len(separated)+brep_count==len(targets) and not exceptions and not failures),
                    dict(total_targets=len(targets),aabb_separated_count=len(separated),brep_attempted_count=brep_count,
                         exception_count=exceptions,fail_count=failures,aabb_separated=separated),
                    no_role_filter=True,scope='AABB disjointness screens material intersection only, not actual minimum clearance.')
        audit.write()
        gc.collect()

    audit.stage='NEW_HARDWARE_VS_ALL_THREE_STATE_NEIGHBOURS'
    for state in STATES:
        targets=[row for row in neighbours[state] if row['id'] not in REPLACED]
        require(len(targets)==623,'Wrong neighbour exclusion set')
        for ident in HARDWARE:
            screen(ident,shapes[ident],box(facts[ident]['bbox_mm']),targets,'NEIGHBOUR:'+state)
    audit.stage='TOOL_APPROACH_AND_FINAL_STATE_DIAGNOSTIC'
    for state in STATES:
        final_targets=[row for row in neighbours[state] if row['id'] not in REPLACED]
        for ident in REPLACED+HARDWARE:
            final_targets.append(dict(id=ident,key=ident,bbox=box(facts[ident]['bbox_mm']),
                                      representation_role=emission['parts'][ident].get('representation_role','CANDIDATE_PHYSICAL')))
        require(len(final_targets)==len({row['id'] for row in final_targets})==637,'Incorrect local-delta tool target set')
        require(all(sum(t['id']==ident for t in final_targets)==1 for ident in CONTEXT_IDS),'Context duplicated or lost')
        top_targets=[row for row in final_targets if row['id'] not in CONTEXT_IDS]
        require(len(top_targets)==635,'Top-stage exclusion must be exactly battery and pad')
        for x,y in XY:
            driver=g.Solid.make_cylinder(2,40,g.Plane(origin=(x,y,-96.15),z_dir=(0,0,1)))
            socket_outer=g.Solid.make_cylinder(4,40,g.Plane(origin=(x,y,-144.05),z_dir=(0,0,1)))
            socket_void=g.Solid.make_cylinder(2,42,g.Plane(origin=(x,y,-145.05),z_dir=(0,0,1)))
            socket=socket_outer-socket_void
            require(socket.is_valid and len(socket.solids())==1,'Invalid annular socket probe')
            screen(f'top:{x}:{y}',driver,box(g.facts(driver)['bbox_mm']),top_targets,'TOOL:'+state,
                   terminal_hardware=(f'WP09_BAT_{x}_{y}_screw',))
            screen(f'bottom:{x}:{y}',socket,box(g.facts(socket)['bbox_mm']),final_targets,'TOOL:'+state,
                   terminal_hardware=(f'WP09_BAT_{x}_{y}_nut',))
            for ident in CONTEXT_IDS:
                def diagnostic(ident=ident,x=x,y=y,driver=driver,state=state):
                    measurement=g.separation(driver,g.load(state+':'+ident))
                    collision=measurement['intersection_volume_mm3']>vtol
                    audit.extra['final_state_upper_tool_diagnostics'].append(dict(
                        state=state,axis_xy_S_mm=[x,y],target_id=ident,
                        status='CONFLICT' if collision else 'NO_MATERIAL_INTERSECTION',measurement=measurement,
                        scope='Final-state observation, not a waived clearance pass. Initial fastening explicitly removes this item.'))
                audit.perform(f'FINAL_TOOL_DIAGNOSTIC_EXCEPTION:{state}:{x}:{y}:{ident}',diagnostic)
            audit.write()
    diagnostics=audit.extra['final_state_upper_tool_diagnostics']
    audit.extra['final_state_upper_tool_clearance']=False if any(r['status']=='CONFLICT' for r in diagnostics) else None
    audit.check('FINAL_STATE_UPPER_TOOL_DIAGNOSTICS_COMPLETE',len(diagnostics)==24,
                dict(observed_pairs=len(diagnostics),expected_pairs=24,
                     conflict_pairs=sum(r['status']=='CONFLICT' for r in diagnostics)),
                assertion='Measurement completeness only; conflicts remain explicit and do not confer final-state tool clearance.')
    audit.stage='FINAL_COVERAGE_AND_INPUT_RECHECK'
    prefix_counts=Counter(row['id'].split(':')[0] for row in audit.rows)
    required={'READBACK':16,'ASSEMBLY_MEMBER':16,'EXACT_SOURCE_SHAPE':14,
              'ONLY_DECLARED_MODIFICATIONS':2,'THROUGH_BORE':8,'CONE_CONTACT':4,
              'AXIAL_STACK':4,'PLANAR_CONTACT':11,'LOCAL_PAIR':120}
    audit.check('REQUIRED_LOCAL_CHECK_COVERAGE',all(prefix_counts[k]==v for k,v in required.items()),
                dict(actual=dict(prefix_counts),required=required))
    coverage=[row for row in audit.rows if ':COVERAGE:' in row['id']]
    audit.check('REQUIRED_NEIGHBOUR_AND_TOOL_COVERAGE',
                len(coverage)==60 and all(row['status']=='PASS' for row in coverage),
                dict(hardware_rows_expected=36,tool_rows_expected=24,actual_rows=len(coverage),
                     hardware_pair_screenings_expected=12*623*3,
                     tool_pair_screenings_expected=(4*635+4*637)*3,
                     top_stage_targets_per_pose=635,bottom_stage_targets_per_pose=637,
                     final_context_diagnostic_pairs_expected=24))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emission',type=Path,default=R/'results/battery_mount/EMISSION.json')
    parser.add_argument('--contract',type=Path,default=R/'inputs/BATTERY_MOUNT_CONTRACT.json')
    parser.add_argument('--output',type=Path,default=R/'results/battery_mount/CHECK.json')
    args=parser.parse_args(argv)
    output=args.output.resolve()
    require(not output.exists() and not output.with_name(output.name+'.tmp').exists(),'Existing checker output protected')
    require(output not in {args.emission.resolve(),args.contract.resolve(),Path(__file__).resolve()},'Output overwrites input')
    output.parent.mkdir(parents=True,exist_ok=True)
    audit=Audit(output)
    audit.write()
    complete=False
    try:
        run(audit,args.emission.resolve(),args.contract.resolve())
        complete=True
    except Exception as exc:
        audit.error('CHECKER_ABORTED_BEFORE_COMPLETE',exc)
    after={}
    for path in audit.snapshots:
        try:after[path]=sha(path)
        except Exception:after[path]=None
    unchanged=audit.snapshots==after
    audit.check('INPUT_FILES_UNCHANGED',unchanged,dict(changed=[p for p in audit.snapshots if audit.snapshots[p]!=after[p]]))
    okay=complete and unchanged and bool(audit.rows) and all(row['status']=='PASS' for row in audit.rows)
    status='PASS_LOCAL_BATTERY_CARRIER_NOMINAL_GEOMETRY_ONLY' if okay else 'FAIL_CLOSED_LOCAL_BATTERY_MOUNT_CHECK'
    audit.write(status,completed_all_planned_checks=complete,input_sha256_after=after,input_files_unchanged=unchanged)
    print(json.dumps(dict(status=status,counts=dict(Counter(r['status'] for r in audit.rows)),output=str(output)),ensure_ascii=False),flush=True)
    return 0 if okay else 1


if __name__=='__main__':
    raise SystemExit(main())
