"""Deduplicate final WP05 local STEP parts without changing geometry or placement.

This is a root-run, serial CAD operation. It never writes source STEP files or
the original PARTS_SOURCE_MANIFEST.json. Two non-arm parts can share a native
import only when their declared roles agree, their local solid counts, volumes
and bounds agree within the frozen exporter tolerances, and actual BRep material
symmetric difference is <= 1e-5 mm^3. No recentering, PN matching or new rotations.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import gc
import hashlib
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE.parent / 'results/PARTS_SOURCE_MANIFEST.json'
CADGEN = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
LINEAR_MM = 1e-4
VOLUME_MM3 = 1e-5


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, path)


def progress(stage, **fields):
    print(json.dumps(dict(stage=stage, **fields), ensure_ascii=False, allow_nan=False), flush=True)


def box_delta(a, b):
    return max(abs(float(a[side][i])-float(b[side][i]))
               for side in ('min_mm', 'max_mm') for i in range(3))


def preliminary_match(a, b):
    return (not a.get('arm_link') and not b.get('arm_link')
            and a['representation_role'] == b['representation_role']
            and a['expected_solid_count'] == b['expected_solid_count']
            and abs(a['expected_volume_mm3']-b['expected_volume_mm3']) <= VOLUME_MM3
            and box_delta(a['local_bounds_mm'], b['local_bounds_mm']) <= LINEAR_MM)


class Geometry:
    def __init__(self):
        sys.path.insert(0, str(CADGEN))
        import cadgen  # noqa: F401 - existing guarded font loader must run first
        from build123d import import_step
        self.import_step = import_step

    def load(self, path):
        tree = self.import_step(Path(path))
        root_location = tree.global_location
        detached = type(tree)(tree.wrapped)
        require(detached.parent is None and not getattr(detached, 'children', ()), 'CAD tree detach failed')
        result = detached.located(root_location)
        del tree, detached
        return result

    @staticmethod
    def volume(shape):
        return 0.0 if shape is None else sum(abs(float(s.volume)) for s in shape.solids())

    def facts(self, shape):
        bbox = shape.bounding_box()
        return dict(solid_count=len(shape.solids()), shape_valid=bool(shape.is_valid),
                    volume_mm3=self.volume(shape),
                    local_bounds_mm=dict(min_mm=list(bbox.min), max_mm=list(bbox.max), size_mm=list(bbox.size)))

    def validate(self, shape, part):
        f = self.facts(shape)
        require(f['shape_valid'], 'Invalid source solid: ' + part['part_key'])
        require(f['solid_count'] == part['expected_solid_count'], 'Solid count drift: ' + part['part_key'])
        require(abs(f['volume_mm3']-part['expected_volume_mm3']) <= VOLUME_MM3,
                'Source local volume drift: ' + part['part_key'])
        require(box_delta(f['local_bounds_mm'], part['local_bounds_mm']) <= LINEAR_MM,
                'Source local bounds drift: ' + part['part_key'])
        return f

    def compare(self, left, right, af, bf):
        volume_difference = abs(af['volume_mm3']-bf['volume_mm3'])
        bbox_difference = box_delta(af['local_bounds_mm'], bf['local_bounds_mm'])
        result = dict(actual_volume_difference_mm3=volume_difference,
                      actual_bbox_max_difference_mm=bbox_difference,
                      symmetric_material_difference_mm3=None)
        if (af['solid_count'] != bf['solid_count'] or volume_difference > VOLUME_MM3
                or bbox_difference > LINEAR_MM):
            return False, result
        # The operands are detached local shapes. Never relocate or recenter them.
        result['symmetric_material_difference_mm3'] = self.volume(left-right) + self.volume(right-left)
        return result['symmetric_material_difference_mm3'] <= VOLUME_MM3, result


def validate_manifest(source, manifest_path):
    require(source.get('status') == 'PASS_SOURCE_GEOMETRY_EXPORT_ONLY' and not source.get('smoke'),
            'A completed, full source export manifest is required')
    require(source.get('units') == 'mm' and source.get('frame') == 'S', 'Unexpected coordinate contract')
    require(source.get('sources_unchanged') is True, 'Source export did not close source preservation')
    require(source['tolerances']['linear_mm'] == LINEAR_MM
            and source['tolerances']['symmetric_material_difference_mm3'] == VOLUME_MM3,
            'Exporter tolerances changed; do not silently alter equivalence thresholds')
    parts = source['parts']
    by_key = {p['part_key']:p for p in parts}
    require(len(by_key) == len(parts), 'Duplicate source part keys')
    require(set(source['states']) == {'service', 'parking', 'released'}, 'Three states are required')
    referenced = set()
    all_ids = None
    for state, data in source['states'].items():
        ids = [r['id'] for r in data['instances']]
        require(len(ids) == 585 and len(set(ids)) == 585, 'Expected exactly 585 unique instances: '+state)
        require(all_ids is None or set(ids) == all_ids, 'State instance inventory differs')
        all_ids = set(ids)
        for row in data['instances']:
            key = row['part_key']
            require(key in by_key, 'Instance has missing local part: '+key)
            require(row['representation_role'] == by_key[key]['representation_role'], 'Representation role mismatch')
            require(row.get('arm_link') == by_key[key].get('arm_link'), 'Arm link role mismatch')
            referenced.add(key)
    require(referenced == set(by_key), 'Unreferenced source part entries')
    before = {str(manifest_path):sha(manifest_path)}
    for p in parts:
        path = Path(p['path']).resolve()
        require(path.suffix.lower() in ('.step', '.stp'), 'Expected STEP source: '+str(path))
        actual = sha(path)
        require(actual == p['sha256'], 'Part SHA mismatch: '+p['part_key'])
        if not p.get('arm_link'):
            require(p['readback_validation']['status'] == 'PASS', 'Original non-arm export was not validated')
        before[str(path)] = actual
    return parts, by_key, before


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument('--output-directory', type=Path, default=DEFAULT_MANIFEST.parent)
    args = ap.parse_args(argv)
    manifest_path, output_dir = args.manifest.resolve(), args.output_directory.resolve()
    derived_path = output_dir / 'PARTS_SOURCE_MANIFEST_DEDUP.json'
    review_path = output_dir / 'DEDUP_SOURCE_REVIEW.json'
    require(manifest_path not in (derived_path, review_path), 'Cannot replace the source manifest')
    source = read(manifest_path)
    parts, by_key, before = validate_manifest(source, manifest_path)
    before[str(Path(__file__).resolve())] = sha(__file__)
    geo = Geometry()
    canonical, mapping, aliases, comparisons = [], {}, [], []
    imported_source_keys = set()
    for index, part in enumerate(parts):
        original_key = part['part_key']
        candidates = [p for p in canonical if preliminary_match(part, p)]
        match_key, match_proof = None, None
        current = None
        if candidates:
            current = geo.load(part['path'])
            imported_source_keys.add(original_key)
            current_facts = geo.validate(current, part)
            for candidate in candidates:
                other = geo.load(candidate['path'])
                imported_source_keys.add(candidate['part_key'])
                other_facts = geo.validate(other, candidate)
                same, proof = geo.compare(current, other, current_facts, other_facts)
                proof.update(original_part_key=original_key, compared_canonical_key=candidate['part_key'],
                             original_sha256=part['sha256'], canonical_sha256=candidate['sha256'],
                             same_representation_role=part['representation_role'],
                             result='MATERIAL_EQUIVALENT' if same else 'KEPT_SEPARATE')
                comparisons.append(proof)
                del other
                if same:
                    match_key, match_proof = candidate['part_key'], proof
                    break
            del current
        if match_key is None:
            mapping[original_key] = original_key
            canonical.append(part)
        else:
            mapping[original_key] = match_key
            aliases.append(dict(original_part_key=original_key, canonical_part_key=match_key,
                original_source_path=part['path'], original_sha256=part['sha256'],
                canonical_source_path=by_key[match_key]['path'], canonical_sha256=by_key[match_key]['sha256'],
                representation_role=part['representation_role'], validation=match_proof,
                original_part_record=part))
        if (index+1) % 20 == 0 or index+1 == len(parts):
            progress('dedup_progress', examined=index+1, input_parts=len(parts), canonical_parts=len(canonical),
                     validated_aliases=len(aliases), actual_material_comparisons=len(comparisons))
            gc.collect()
    derived = copy.deepcopy(source)
    derived['parts'] = copy.deepcopy(canonical)
    changed_occurrences = []
    for state, data in derived['states'].items():
        for row in data['instances']:
            prior_key = row['part_key']
            row['part_key'] = mapping[prior_key]
            if row['part_key'] != prior_key:
                changed_occurrences.append(dict(state=state, id=row['id'], original_part_key=prior_key,
                                                canonical_part_key=row['part_key']))
    # Compare all instance fields after removing only the authorized part-key substitution.
    for state in source['states']:
        old_rows, new_rows = source['states'][state]['instances'], derived['states'][state]['instances']
        for old, new in zip(old_rows, new_rows):
            restored = dict(new)
            restored['part_key'] = old['part_key']
            require(restored == old, 'Instance transform or metadata changed: '+state+':'+old['id'])
        require({r['part_key'] for r in new_rows} <= {p['part_key'] for p in canonical}, 'Dangling canonical key')
    require(all(mapping[p['part_key']] == p['part_key'] for p in parts if p.get('arm_link')),
            'Arm source was deduplicated')
    after = {path:sha(path) for path in before}
    require(after == before, 'Source manifest, source STEP, or dedup script changed during run')
    provenance = dict(source_manifest=dict(path=str(manifest_path), sha256=before[str(manifest_path)]),
        method='Same-role local BRep material equivalence; no PN, recentering or transform changes',
        tolerances=dict(linear_mm=LINEAR_MM, symmetric_material_difference_mm3=VOLUME_MM3),
        input_part_count=len(parts), canonical_part_count=len(canonical), alias_part_count=len(aliases),
        changed_instance_references=len(changed_occurrences), original_to_canonical_part_keys=mapping,
        aliases=aliases, transforms_and_instance_metadata_unchanged=True,
        source_manifest_unchanged=True, source_step_files_unchanged=True,
        solidworks_native_import_not_executed=True, no_new_mechanical_credit=True)
    derived['deduplication'] = provenance
    derived['unique_part_count'] = len(canonical)
    # These counts describe the canonical source list; the original counters remain in the source manifest.
    derived['arm_copy_count'] = sum(bool(p.get('arm_link')) for p in canonical)
    derived['nonarm_roundtrip_count'] = sum(p['readback_validation']['status']=='PASS' for p in canonical)
    derived['generated_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    review = dict(schema='WP05_DEDUP_SOURCE_REVIEW_V1', status='PASS_LOCAL_MATERIAL_DEDUPLICATION_ONLY',
        generated_utc=derived['generated_utc'], source_sha256_before=before, source_sha256_after=after,
        source_files_unchanged=True, input_part_count=len(parts), canonical_part_count=len(canonical),
        aliases=aliases, comparisons=comparisons, changed_occurrences=changed_occurrences,
        source_keys_loaded_for_actual_BRep_comparison=sorted(imported_source_keys),
        instance_counts={s:len(x['instances']) for s,x in derived['states'].items()},
        transforms_and_instance_metadata_unchanged=True, arm_sources_unmodified_and_not_deduplicated=True,
        retained_canonical_readback_validation='Original source PASS records retained without alteration',
        material_tolerance_mm3=VOLUME_MM3, linear_tolerance_mm=LINEAR_MM,
        qualification_credit=False, physical_assembly_completed=False, manufacturing_release=False)
    write(derived_path, derived)
    review['derived_manifest'] = dict(path=str(derived_path), sha256=sha(derived_path))
    write(review_path, review)
    progress('dedup_finished', manifest=str(derived_path), review=str(review_path),
             input_parts=len(parts), canonical_parts=len(canonical), validated_aliases=len(aliases))


if __name__ == '__main__':
    main()
