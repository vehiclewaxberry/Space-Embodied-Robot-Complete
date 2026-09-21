"""Extract frozen WP04 STEP solids into a recoverable SolidWorks source package.

Run under the root-owned resource guard. This never executes a WP04 generator or
writes beside its sources. CAD imports are deferred until after source validation.
The --smoke option selects two non-arm instance IDs in each of the three states;
it writes separate smoke receipts and does not copy the large arm STEP inputs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent
PROJECT = OUTPUT.parents[1]
DEFAULT_CANDIDATE = PROJECT / (
    '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/'
    'runs/wp04_robot_assembly_20260906_175153/candidate'
)
CADGEN = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
STATES = ('service', 'parking', 'released')
LIN_TOL_MM = 1e-4
VOL_TOL_MM3 = 1e-5


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, path)


def progress(stage, **fields):
    print(json.dumps(dict(stage=stage, **fields), ensure_ascii=False, allow_nan=False), flush=True)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def slug(instance_id):
    name = re.sub(r'[^A-Za-z0-9_-]', '_', instance_id)
    return name[:85] + '_' + hashlib.sha256(instance_id.encode()).hexdigest()[:8]


def imported_label(name):
    return str(name).translate(str.maketrans(' .()', '____'))


def inverse_rigid(T):
    require(len(T) == 4 and all(len(row) == 4 for row in T), 'Transform must be 4 by 4')
    require(all(math.isfinite(float(x)) for row in T for x in row), 'Nonfinite transform')
    require(max(abs(T[3][j] - (1 if j == 3 else 0)) for j in range(4)) < 1e-10,
            'Nonhomogeneous transform')
    R = [[T[j][i] for j in range(3)] for i in range(3)]
    require(max(abs(sum(T[k][i] * T[k][j] for k in range(3)) - (1 if i == j else 0))
                for i in range(3) for j in range(3)) < 1e-8, 'Transform rotation is not orthonormal')
    return [R[i] + [-sum(R[i][j] * T[j][3] for j in range(3))] for i in range(3)] + [[0, 0, 0, 1]]


def validate_inputs(candidate):
    snapshots = {}
    docs = {}
    def pin(p, expected=None):
        p = Path(p).resolve()
        digest = sha(p)
        require(expected is None or digest == expected, 'Input SHA mismatch: ' + str(p))
        snapshots[str(p)] = digest
        return p
    for state in STATES:
        receipt_path = pin(candidate / 'results' / f'{state}_instances.json')
        index_path = pin(candidate / 'results' / f'{state}_COMPOSITE_ASSEMBLY_INDEX.json')
        r, index = read(receipt_path), read(index_path)
        require(r['state'] == state and index['state'] == state, 'State mismatch')
        require(r['configuration'] == index['configuration'], 'Configuration mismatch')
        require(index['units'] == 'mm' and index['frame'] == 'S', 'Input coordinate contract mismatch')
        require(len(r['instances']) == 585, 'Expected frozen 585-instance package')
        reg = {x['id']: x for x in r['instances']}
        require(len(reg) == 585, 'Duplicate instance IDs')
        nonarm = {x['id'] for x in r['instances'] if not x.get('arm_link')}
        require(len(nonarm) == 575 and nonarm == set(index['nonarm_instance_ids']), 'Non-arm coverage mismatch')
        require(len({imported_label(x) for x in nonarm}) == 575, 'STEP label sanitization collision')
        step = pin(index['nonarm_step']['path'], index['nonarm_step']['sha256'])
        for path, digest in r['geometry_sha256'].items():
            pin(path, digest)
        pin(candidate / 'spacecraft_model.py', r['source_sha256'])
        for name, digest in r['dependency_sha256'].items():
            pin(candidate / name, digest)
        for a in index['arm_occurrences']:
            pin(a['geometry']['path'], a['geometry']['sha256'])
            require(a['T_S_local'] == reg[a['id']]['T_S_local'], 'Arm transform mismatch')
        docs[state] = dict(receipt=r, index=index, registry=reg, step=step)
    require(len({d['receipt']['configuration'] for d in docs.values()}) == 1, 'Mixed configurations')
    return docs, snapshots


class CAD:
    def __init__(self):
        sys.path.insert(0, str(CADGEN))
        import cadgen  # noqa: F401 - installs the existing guarded font loader first
        from build123d import import_step, export_step, Location
        from OCP.gp import gp_Trsf
        from OCP.GProp import GProp_GProps
        from OCP.BRepGProp import BRepGProp
        self.import_step, self.export_step, self.Location = import_step, export_step, Location
        self.Trsf, self.Props, self.GProp = gp_Trsf, GProp_GProps, BRepGProp

    def location(self, T):
        tr = self.Trsf()
        tr.SetValues(*[float(x) for row in T[:3] for x in row[:4]])
        return self.Location(tr)

    def volume(self, shape):
        return 0.0 if shape is None else sum(abs(float(s.volume)) for s in shape.solids())

    def facts(self, shape):
        bbox = shape.bounding_box()
        return dict(volume_mm3=self.volume(shape), solid_count=len(shape.solids()),
                    shape_valid=bool(shape.is_valid),
                    bounds_mm=dict(min_mm=list(bbox.min), max_mm=list(bbox.max), size_mm=list(bbox.size)))

    def detach_leaves(self, tree):
        out = {}
        def visit(node):
            children = getattr(node, 'children', ())
            if children:
                for child in children:
                    visit(child)
            else:
                label = getattr(node, 'label', '')
                require(bool(label), 'STEP leaf has no instance label')
                require(label not in out, 'Duplicate STEP leaf label: ' + label)
                global_loc = node.global_location
                detached = type(node)(node.wrapped)
                require(detached.parent is None and not getattr(detached, 'children', ()), 'Unsafe leaf detachment')
                # Never call .located() on a node still connected to an anytree.
                out[label] = detached.located(global_loc)
        visit(tree)
        return out

    def equivalent(self, a, b):
        af, bf = self.facts(a), self.facts(b)
        bbox_diff = max(abs(af['bounds_mm'][side][i] - bf['bounds_mm'][side][i])
                        for side in ('min_mm', 'max_mm') for i in range(3))
        result = dict(volume_difference_mm3=abs(af['volume_mm3'] - bf['volume_mm3']),
                      bbox_max_difference_mm=bbox_diff, symmetric_difference_mm3=None)
        if (not af['shape_valid'] or not bf['shape_valid'] or af['solid_count'] != bf['solid_count']
                or result['volume_difference_mm3'] > VOL_TOL_MM3 or bbox_diff > LIN_TOL_MM):
            return False, result
        delta = self.volume(a - b) + self.volume(b - a)
        result['symmetric_difference_mm3'] = delta
        return delta <= VOL_TOL_MM3, result


def check_facts(actual, expected_volume, expected_count, expected_bounds, name):
    diff = max(abs(actual['bounds_mm'][side][i] - expected_bounds[side][i])
               for side in ('min_mm', 'max_mm') for i in range(3))
    require(actual['shape_valid'] and actual['solid_count'] == expected_count, 'Invalid solids: ' + name)
    require(abs(actual['volume_mm3'] - expected_volume) <= VOL_TOL_MM3, 'Volume mismatch: ' + name)
    require(diff <= LIN_TOL_MM, 'Bounding box mismatch: ' + name)
    return dict(status='PASS', volume_difference_mm3=abs(actual['volume_mm3']-expected_volume),
                bbox_max_difference_mm=diff)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate', type=Path, default=DEFAULT_CANDIDATE)
    ap.add_argument('--output', type=Path, default=OUTPUT)
    ap.add_argument('--smoke', action='store_true')
    args = ap.parse_args(argv)
    candidate, output = args.candidate.resolve(), args.output.resolve()
    require(candidate != output and candidate not in output.parents, 'Output must not lie in the frozen candidate')
    docs, inputs = validate_inputs(candidate)
    sources, results = output / 'sources', output / 'results'
    sources.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    suffix = '_SMOKE' if args.smoke else ''
    manifest_path = results / ('PARTS_SOURCE_MANIFEST' + suffix + '.json')
    journal_path = results / ('PARTS_EXPORT_PROGRESS' + suffix + '.json')
    binding = dict(script_sha256=sha(__file__), source_sha256=inputs, smoke=args.smoke,
                   linear_tolerance_mm=LIN_TOL_MM, material_tolerance_mm3=VOL_TOL_MM3)
    signature = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    journal = dict(binding_signature=signature, binding=binding, parts={}, completed_occurrences={}, material_comparisons=[])
    if journal_path.exists():
        old = read(journal_path)
        require(old.get('binding_signature') == signature,
                'Resume binding changed; retain the old receipt and use another output directory')
        journal = old
        for p in journal['parts'].values():
            require(Path(p['path']).is_file() and sha(p['path']) == p['sha256'],
                    'Existing part failed resume SHA: ' + p['part_key'])
    selected = None
    if args.smoke:
        selected = [x['id'] for x in docs['service']['receipt']['instances'] if not x.get('arm_link')][:2]
    out = dict(schema='WP05_SW_PART_SOURCE_V1', status='BUILDING', generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
               source_candidate=str(candidate), units='mm', frame='S', transform_units='mm', smoke=args.smoke,
               binding_signature=signature, source_sha256_before=inputs, parts=[], states={},
               tolerances=dict(linear_mm=LIN_TOL_MM, symmetric_material_difference_mm3=VOL_TOL_MM3),
               hardware_qualified=False, physical_assembly_completed=False, manufacturing_release=False,
               scope='Native-CAD source geometry preservation only; no new mechanical qualification credit')
    cad = CAD()
    reuse_checks = journal.setdefault('material_comparisons', [])
    count = 0
    for state in STATES:
        d, rows = docs[state], docs[state]['receipt']['instances']
        if selected is not None:
            rows = [r for r in rows if r['id'] in selected]
        pending_nonarm = [r for r in rows if not r.get('arm_link') and f'{state}:{r["id"]}' not in journal['completed_occurrences']]
        worlds = {}
        if pending_nonarm:
            progress('import_state', state=state, step=str(d['step']))
            tree = cad.import_step(d['step'])
            worlds = cad.detach_leaves(tree)
            del tree
            gc.collect()
            require(set(worlds) == {imported_label(k) for k in d['index']['nonarm_instance_ids']},
                    'Exported STEP leaf inventory mismatch: ' + state)
        state_out = {k:d['receipt'][k] for k in ('configuration','q_deg','finger_mm','T_S_arm_base')}
        state_out['instances'] = []
        for row in rows:
            occurrence_key = f'{state}:{row["id"]}'
            if occurrence_key in journal['completed_occurrences']:
                key = journal['completed_occurrences'][occurrence_key]
            elif row.get('arm_link'):
                a = next(x for x in d['index']['arm_occurrences'] if x['id'] == row['id'])
                key = 'B601_' + row['arm_link'] + '_LINKLOCAL'
                dest = sources / (key + '.step')
                if key not in journal['parts']:
                    if dest.exists():
                        require(sha(dest) == a['geometry']['sha256'], 'Existing arm copy SHA mismatch: ' + key)
                    else:
                        temp = dest.with_name(dest.name + '.tmp')
                        shutil.copyfile(a['geometry']['path'], temp)
                        require(sha(temp) == a['geometry']['sha256'], 'Arm copy validation failed')
                        os.replace(temp, dest)
                    journal['parts'][key] = dict(part_key=key, path=str(dest), relative_path=str(dest.relative_to(output)),
                        sha256=sha(dest), instance_id=row['id'], source_state=state, arm_link=row['arm_link'],
                        source_geometry=a['geometry'], representation_role=row['representation_role'],
                        expected_volume_mm3=row['volume_mm3'], expected_solid_count=row['solid_count'],
                        local_bounds_mm=row['local_bounds'], source_basis='UNCHANGED_HASH_LOCKED_LINKLOCAL_BREP',
                        readback_validation=dict(status='NOT_EXECUTED', reason='Exact source copy, no CAD conversion in this exporter'),
                        qualification_status=row['qualification_status'])
                else:
                    require(journal['parts'][key]['sha256'] == a['geometry']['sha256'], 'Cross-state arm source drift')
                journal['completed_occurrences'][occurrence_key] = key
                write(journal_path, journal)
            else:
                world = worlds[imported_label(row['id'])]
                world_check = check_facts(cad.facts(world), row['volume_mm3'], row['solid_count'], row['bounds'], row['id']+' world')
                local = world.moved(cad.location(inverse_rigid(row['T_S_local'])))
                local_facts = cad.facts(local)
                local_check = check_facts(local_facts, row['volume_mm3'], row['solid_count'], row['local_bounds'], row['id']+' local')
                key = None
                for prior_key, prior in journal['parts'].items():
                    if prior.get('arm_link') or prior['instance_id'] != row['id']:
                        continue
                    # Reuse requires an actual BRep comparison, never PN or mesh equality.
                    prior_shape = cad.import_step(prior['path'])
                    same, detail = cad.equivalent(local, prior_shape)
                    reuse_checks.append(dict(state=state, id=row['id'], compared_part_key=prior_key,
                                             result='MATERIAL_EQUIVALENT' if same else 'SEPARATE_VARIANT', **detail))
                    del prior_shape
                    if same:
                        key = prior_key
                        break
                if key is None:
                    key = slug(row['id']) + '_' + state + '_solid'
                    dest = sources / (key + '.step')
                    if dest.exists():
                        # Interrupted export without a checkpoint can be adopted only after exact geometry validation.
                        rb = cad.import_step(dest)
                        same, detail = cad.equivalent(local, rb)
                        require(same, 'Uncheckpointed existing STEP differs: ' + str(dest))
                    else:
                        temp = dest.with_name(dest.stem + '.pending.step')
                        # Every nonarm instance is one actual solid. Export the
                        # solid root rather than a one-child assembly container;
                        # otherwise SolidWorks correctly imports it as SLDASM.
                        solid_root = local.solids()[0]
                        solid_root.label = row['id']
                        cad.export_step(solid_root, temp)
                        rb = cad.import_step(temp)
                        same, detail = cad.equivalent(local, rb)
                        require(same, 'STEP export/readback material mismatch: ' + row['id'])
                        os.replace(temp, dest)
                    readback_facts = cad.facts(rb)
                    rebuilt_world = rb.moved(cad.location(row['T_S_local']))
                    world_roundtrip = check_facts(cad.facts(rebuilt_world), row['volume_mm3'], row['solid_count'], row['bounds'], row['id']+' world roundtrip')
                    world_same, world_detail = cad.equivalent(world, rebuilt_world)
                    require(world_same, 'STEP roundtrip changed world material: ' + row['id'])
                    journal['parts'][key] = dict(part_key=key, path=str(dest), relative_path=str(dest.relative_to(output)),
                        sha256=sha(dest), instance_id=row['id'], source_state=state, arm_link=None,
                        source_step=dict(path=str(d['step']), sha256=inputs[str(d['step'])]),
                        representation_role=row['representation_role'], expected_volume_mm3=row['volume_mm3'],
                        expected_solid_count=row['solid_count'], local_bounds_mm=row['local_bounds'],
                        actual_export_facts=readback_facts, source_basis='DETACHED_STEP_LEAF_IN_RECEIPT_LOCAL_FRAME',
                        readback_validation=dict(status='PASS', local_equivalence=detail,
                                                 world_equivalence=world_detail, world_facts=world_roundtrip),
                        source_world_validation=world_check, source_local_validation=local_check,
                        qualification_status=row['qualification_status'])
                    del rb, rebuilt_world
                journal['completed_occurrences'][occurrence_key] = key
                write(journal_path, journal)
                del world, local
            state_out['instances'].append(dict(id=row['id'], part_key=key, T_S_local=row['T_S_local'],
                bounds_mm=row['bounds'], representation_role=row['representation_role'],
                product_role=row['product_role'], parent_assembly=row['parent_assembly'], pn=row['pn'],
                mount_interface=row['mount_interface'], arm_link=row.get('arm_link'),
                source_revision=row['source_revision'], mass_source=row['mass_source'],
                source_mass_kg=row['mass_kg'], qualification_status=row['qualification_status']))
            count += 1
            if count % 20 == 0:
                progress('occurrences_exported', completed=count, state=state, parts=len(journal['parts']))
        out['states'][state] = state_out
        worlds.clear()
        gc.collect()
        write(results / ('PARTS_SOURCE_DRAFT' + suffix + '.json'), out)
        progress('state_finished', state=state, instances=len(state_out['instances']), parts=len(journal['parts']))
    after = {p:sha(p) for p in inputs}
    require(after == inputs, 'Frozen input files changed during export')
    referenced = {r['part_key'] for s in out['states'].values() for r in s['instances']}
    require(referenced == set(journal['parts']), 'Manifest contains missing or unreferenced part entries')
    for p in journal['parts'].values():
        require(sha(p['path']) == p['sha256'], 'Output part changed during export: ' + p['part_key'])
    out.update(status='PASS_SMOKE_ONLY' if args.smoke else 'PASS_SOURCE_GEOMETRY_EXPORT_ONLY',
               parts=list(journal['parts'].values()), source_sha256_after=after, sources_unchanged=True,
               instance_counts={s:len(x['instances']) for s,x in out['states'].items()},
               unique_part_count=len(journal['parts']),
               arm_copy_count=sum(bool(x.get('arm_link')) for x in journal['parts'].values()),
               nonarm_roundtrip_count=sum(x['readback_validation']['status']=='PASS' for x in journal['parts'].values()),
               cross_state_material_comparisons=reuse_checks,
               resume_note='Checkpointed parts and occurrences are retained only under identical input and exporter SHA bindings')
    write(manifest_path, out)
    progress('finished', manifest=str(manifest_path), status=out['status'], unique_parts=len(out['parts']))


if __name__ == '__main__':
    main()
