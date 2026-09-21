"""Independently compare source STEP with an actual SolidWorks roundtrip STEP.

Run serially under the root-owned memory guard. No COM API is imported or called.
Default: write a validation report and a derived imports receipt. --apply also
adds hash-bound roundtrip evidence to NATIVE_IMPORTS.json, after preserving an
exact content-addressed copy of its original bytes. Existing scalar failures,
source_comparison.pass, status, dimensions and all native witnesses are preserved.
Multi-body parts are matched one solid at a time with full one-to-one coverage;
the material gate sums per-body differences and never unions overlapping bodies.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import gc
import hashlib
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CADGEN = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
BBOX_TOL_MM = 1e-4
MATERIAL_TOL_MM3 = 1e-5
VOLUME_TOL_MM3 = 1e-5
INTEGRATION_EPS = 1e-13


class Incomplete(RuntimeError):
    pass


class Failed(RuntimeError):
    pass


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, path)


def require(condition, message):
    if not condition:
        raise Failed(message)


def progress(stage, **fields):
    print(json.dumps(dict(stage=stage, **fields), ensure_ascii=False, allow_nan=False), flush=True)


def path_key(path):
    return str(Path(path).resolve()).replace('\\', '/').casefold()


def bind_file(path, expected, suffix, snapshots):
    if not path or not isinstance(expected, str):
        raise Incomplete('Missing explicit file path or recorded SHA: ' + str(path))
    p = Path(path).resolve()
    require(p.is_relative_to(ROOT.resolve()), 'Evidence file escapes this delivery package: ' + str(p))
    require(p.suffix.casefold() == suffix.casefold(), 'Unexpected evidence file format: ' + str(p))
    if not p.is_file():
        raise Incomplete('Recorded evidence file is absent: ' + str(p))
    digest = sha(p)
    require(digest.casefold() == expected.casefold(), 'Recorded SHA differs from actual file: ' + str(p))
    snapshots[str(p)] = digest
    return p, digest


class Kernel:
    def __init__(self):
        sys.path.insert(0, str(CADGEN))
        import cadgen  # noqa: F401 - font scan guard must precede build123d
        from build123d import import_step
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        from OCP.TopExp import TopExp
        from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
        from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
        import OCP
        self.import_step = import_step
        self.BRepGProp, self.GProps = BRepGProp, GProp_GProps
        self.TopExp, self.IndexMap = TopExp, TopTools_IndexedDataMapOfShapeListOfShape
        self.FACE, self.SHELL, self.SOLID = TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
        doc = BRepGProp.VolumeProperties_s.__doc__ or ''
        require('Eps' in doc and 'OnlyClosed' in doc and 'SkipShared' in doc,
                'Installed OCP lacks the documented adaptive VolumeProperties_s overload')
        self.method = dict(function='OCP.BRepGProp.BRepGProp.VolumeProperties_s',
            call='VolumeProperties_s(shape, props, Eps=1e-13, OnlyClosed=True, SkipShared=False)',
            epsilon=INTEGRATION_EPS, ocp_version=getattr(OCP, '__version__', None),
            local_runtime_signature_and_documentation=doc,
            volume_basis='Adaptive exact-surface volume integration per valid solid; no triangulation or build123d .volume',
            note='Integrator error estimates are diagnostics; acceptance uses unchanged absolute geometric tolerances')

    def load(self, path):
        tree = self.import_step(Path(path))
        location = tree.global_location
        detached = type(tree)(tree.wrapped)
        require(detached.parent is None and not getattr(detached, 'children', ()), 'Unsafe shape detachment')
        result = detached.located(location)
        del tree, detached
        return result

    def measure_solids(self, solids):
        values, estimates = [], []
        for solid in solids:
            require(bool(solid.is_valid), 'Invalid solid supplied to adaptive volume integration')
            props = self.GProps()
            # Named Eps selects the adaptive overload, not the bool third-argument overload.
            estimate = self.BRepGProp.VolumeProperties_s(
                solid.wrapped, props, Eps=INTEGRATION_EPS, OnlyClosed=True, SkipShared=False)
            require(type(estimate) in (float, int) and math.isfinite(float(estimate)) and estimate >= 0,
                    'Adaptive volume integration did not return a finite nonnegative error estimate')
            value = float(props.Mass())
            require(math.isfinite(value), 'Adaptive volume integration returned nonfinite material volume')
            values.append(abs(value))
            estimates.append(float(estimate))
        return dict(volume_mm3=math.fsum(values), integration_error_estimates=estimates, solid_volumes_mm3=values)

    def adaptive_volume(self, shape):
        return self.measure_solids([] if shape is None else shape.solids())

    @staticmethod
    def detached_solids(shape):
        result = []
        for body in shape.solids():
            location = body.global_location
            detached = type(body)(body.wrapped)
            require(detached.parent is None and not getattr(detached, 'children', ()),
                    'Solid detachment left an assembly-parent reference')
            result.append(detached.located(location))
        return result

    def difference_volume(self, shape):
        if shape is not None:
            require(bool(shape.is_valid), 'Boolean material difference is invalid')
            faces = self.ancestor_map(shape, self.FACE, self.SOLID)
            require(all(faces.FindFromIndex(i).Extent() > 0 for i in range(1, faces.Extent()+1)),
                    'Boolean difference contains free faces; volume alone cannot establish material equivalence')
        return self.adaptive_volume(shape)

    def ancestor_map(self, shape, child_type, ancestor_type):
        mapping = self.IndexMap()
        self.TopExp.MapShapesAndAncestors_s(shape.wrapped, child_type, ancestor_type, mapping)
        return mapping

    def facts(self, shape, solids=None):
        # Solid shells are not sheet bodies. Count only shells/faces without solid ancestors.
        shell_solid = self.ancestor_map(shape, self.SHELL, self.SOLID)
        face_solid = self.ancestor_map(shape, self.FACE, self.SOLID)
        face_shell = self.ancestor_map(shape, self.FACE, self.SHELL)
        free_shells = sum(shell_solid.FindFromIndex(i).Extent() == 0 for i in range(1, shell_solid.Extent()+1))
        free_faces = sum(face_solid.FindFromIndex(i).Extent() == 0 for i in range(1, face_solid.Extent()+1))
        standalone_faces = sum(face_shell.FindFromIndex(i).Extent() == 0 for i in range(1, face_shell.Extent()+1))
        bbox = shape.bounding_box()
        solids = list(shape.solids()) if solids is None else solids
        return dict(shape_valid=bool(shape.is_valid), solid_count=len(solids),
                    sheet_count=free_shells+standalone_faces, free_shell_count=free_shells,
                    free_face_count=free_faces, standalone_face_count=standalone_faces,
                    bounds_mm=dict(min_mm=list(bbox.min), max_mm=list(bbox.max)),
                    **self.measure_solids(solids))

    def compare(self, source, returned, expected_solids):
        # References to bodies share the two loaded BReps; no third file or union is built.
        source_bodies = self.detached_solids(source)
        returned_bodies = self.detached_solids(returned)
        sf, rf = self.facts(source, source_bodies), self.facts(returned, returned_bodies)
        basics = (sf['shape_valid'] and rf['shape_valid']
                  and sf['solid_count'] == rf['solid_count'] == expected_solids and expected_solids > 0
                  and sf['sheet_count'] == rf['sheet_count'] == 0
                  and sf['free_face_count'] == rf['free_face_count'] == 0)
        result = dict(source_occ_facts=sf, roundtrip_occ_facts=rf,
            solid_counts_match=sf['solid_count'] == rf['solid_count'] == expected_solids,
            no_free_sheets_or_faces=sf['sheet_count'] == rf['sheet_count'] == sf['free_face_count'] == rf['free_face_count'] == 0,
            volume_difference_mm3=abs(sf['volume_mm3']-rf['volume_mm3']),
            bbox_max_difference_mm=max(abs(sf['bounds_mm'][side][i]-rf['bounds_mm'][side][i])
                                       for side in ('min_mm', 'max_mm') for i in range(3)),
            symmetric_difference_mm3=None,
            body_index_base=0,
            matching_method='Deterministic one-to-one local-solid matching with actual bidirectional BRep material proofs',
            material_total_basis='Sum of matched-body symmetric differences; overlapping bodies are never unioned',
            body_matches=[], body_candidate_comparisons=[], source_body_count=len(source_bodies),
            returned_body_count=len(returned_bodies), complete_body_coverage=False)
        if not basics:
            result.update(status='FAIL', reason='Invalid shape, wrong solid count, or unexpected sheet/free face')
            return result
        def body_records(bodies, facts):
            rows = []
            for i, body in enumerate(bodies):
                bb = body.bounding_box()
                rows.append(dict(body_index=i, volume_mm3=facts['solid_volumes_mm3'][i],
                                 integration_error_estimate=facts['integration_error_estimates'][i],
                                 bounds_mm=dict(min_mm=list(bb.min), max_mm=list(bb.max))))
            return rows

        source_records = body_records(source_bodies, sf)
        returned_records = body_records(returned_bodies, rf)
        result['source_bodies'] = source_records
        result['returned_bodies'] = returned_records

        def body_box_difference(i, j):
            return max(abs(source_records[i]['bounds_mm'][side][k]-returned_records[j]['bounds_mm'][side][k])
                       for side in ('min_mm', 'max_mm') for k in range(3))

        candidates = {i:[j for j in range(len(returned_bodies)) if body_box_difference(i, j) <= BBOX_TOL_MM]
                      for i in range(len(source_bodies))}
        proofs = {}

        def prove_pair(i, j):
            pair = (i, j)
            if pair in proofs:
                return proofs[pair]['status'] == 'PASS'
            sv, rv = source_records[i]['volume_mm3'], returned_records[j]['volume_mm3']
            proof = dict(source_body_index=i, returned_body_index=j,
                         source_volume_mm3=sv, returned_volume_mm3=rv,
                         volume_difference_mm3=abs(sv-rv),
                         bbox_max_difference_mm=body_box_difference(i, j),
                         source_minus_returned_mm3=None, returned_minus_source_mm3=None,
                         symmetric_difference_mm3=None, status='FAIL')
            proofs[pair] = proof
            if proof['volume_difference_mm3'] > VOLUME_TOL_MM3:
                proof['reason'] = 'Body volume exceeds the unchanged absolute tolerance'
                return False
            # Only two individual solids participate in a Boolean. Internal overlap
            # in a multi-body part therefore cannot hide a changed or missing body.
            try:
                forward = source_bodies[i]-returned_bodies[j]
                fp = self.difference_volume(forward)
                del forward
                backward = returned_bodies[j]-source_bodies[i]
                bp = self.difference_volume(backward)
                del backward
            except Exception as exc:
                proof.update(status='FAIL', reason='Actual candidate Boolean/integration failed: '+str(exc),
                             exception_type=type(exc).__name__)
                return False
            proof.update(source_minus_returned_mm3=fp['volume_mm3'],
                         returned_minus_source_mm3=bp['volume_mm3'],
                         symmetric_difference_mm3=math.fsum((fp['volume_mm3'], bp['volume_mm3'])),
                         source_minus_returned_integration=fp, returned_minus_source_integration=bp)
            proof['status'] = 'PASS' if proof['symmetric_difference_mm3'] <= MATERIAL_TOL_MM3 else 'FAIL'
            if proof['status'] != 'PASS':
                proof['reason'] = 'Actual body material symmetric difference exceeds the unchanged tolerance'
            return proof['status'] == 'PASS'

        # Lazy augmenting paths prevent a greedy first candidate from losing a
        # valid bijection. A same-index in-bounds candidate is attempted first.
        # Every graph edge is admitted only by a real material proof, never volume.
        matched_returned = {}

        def augment(source_index, visited_returned):
            order = sorted(candidates[source_index],
                           key=lambda j:(j != source_index, j in matched_returned, j))
            for j in order:
                if j in visited_returned:
                    continue
                if not prove_pair(source_index, j):
                    continue
                visited_returned.add(j)
                previous = matched_returned.get(j)
                if previous is None or augment(previous, visited_returned):
                    matched_returned[j] = source_index
                    return True
            return False

        for i in range(len(source_bodies)):
            augment(i, set())
            if (i+1) % 10 == 0 or i+1 == len(source_bodies):
                progress('roundtrip_body_matching', examined_source_bodies=i+1,
                         source_bodies=len(source_bodies), matched_bodies=len(matched_returned),
                         actual_candidate_proofs=len(proofs))
        matched_source = {i:j for j,i in matched_returned.items()}
        result['body_candidate_comparisons'] = list(proofs.values())
        result['body_matches'] = [proofs[(i, matched_source[i])] for i in sorted(matched_source)]
        result['unmatched_source_body_indices'] = sorted(set(range(len(source_bodies)))-set(matched_source))
        result['unmatched_returned_body_indices'] = sorted(set(range(len(returned_bodies)))-set(matched_returned))
        complete = (len(matched_source) == len(matched_returned) == expected_solids
                    and len({p['source_body_index'] for p in result['body_matches']}) == expected_solids
                    and len({p['returned_body_index'] for p in result['body_matches']}) == expected_solids)
        result['complete_body_coverage'] = complete
        result['unique_returned_index_assignment'] = complete
        result['geometrically_unique_solution_claimed'] = False
        result['matching_uniqueness_scope'] = ('Every source and returned body index is used exactly once; '
                                              'geometrically identical coincident bodies may admit interchangeable indices')
        if complete:
            result['source_minus_roundtrip_mm3'] = math.fsum(p['source_minus_returned_mm3'] for p in result['body_matches'])
            result['roundtrip_minus_source_mm3'] = math.fsum(p['returned_minus_source_mm3'] for p in result['body_matches'])
            result['symmetric_difference_mm3'] = math.fsum(p['symmetric_difference_mm3'] for p in result['body_matches'])
        passed = (complete and result['volume_difference_mm3'] <= VOLUME_TOL_MM3
                  and result['bbox_max_difference_mm'] <= BBOX_TOL_MM
                  and result['symmetric_difference_mm3'] <= MATERIAL_TOL_MM3
                  and all(p['status'] == 'PASS' and p['volume_difference_mm3'] <= VOLUME_TOL_MM3
                          and p['bbox_max_difference_mm'] <= BBOX_TOL_MM
                          and p['symmetric_difference_mm3'] <= MATERIAL_TOL_MM3
                          for p in result['body_matches']))
        result['status'] = 'PASS' if passed else 'FAIL'
        if not passed:
            result['reason'] = ('Incomplete one-to-one body material matching' if not complete else
                                'Per-body or aggregate same-kernel geometry exceeds a frozen absolute tolerance')
        return result


def validate_one(row, part, snapshots, kernel_holder, script_hash):
    evidence = dict(status='INCOMPLETE', part_key=row.get('part_key'),
        validation_script_path=str(Path(__file__).resolve()), validation_script_sha256=script_hash,
        generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_sha256=None, native_sha256=None, roundtrip_path=None, roundtrip_sha256=None,
        symmetric_difference_mm3=None, bbox_max_difference_mm=None, volume_difference_mm3=None,
        tolerances=dict(symmetric_difference_mm3=MATERIAL_TOL_MM3, bbox_max_difference_mm=BBOX_TOL_MM,
                        volume_difference_mm3=VOLUME_TOL_MM3),
        cross_kernel_scalar_failure_preserved=True, com_export_executed_by_this_validator=False)
    source_shape, returned_shape = None, None
    try:
        if part is None:
            raise Incomplete('Import part key is not covered by the bound source manifest')
        require(path_key(row['source']) == path_key(part['path']), 'Import source path differs from bound manifest')
        require(row.get('source_sha256') == part.get('sha256'), 'Import/manifest source SHA differs')
        require(row.get('status') == 'NATIVE_PART_SAVED_AND_REOPENED', 'Native save/reopen witness is not successful')
        require(row.get('import_error') == 0, 'Native import error is nonzero or missing')
        native_save = row.get('native_save', {})
        if native_save.get('ok') is not True or native_save.get('errors') != 0:
            raise Incomplete('No successful native save receipt')
        source, source_hash = bind_file(part['path'], part['sha256'], '.step', snapshots)
        native, native_hash = bind_file(row.get('target'), native_save.get('sha256'), '.sldprt', snapshots)
        evidence.update(source_sha256=source_hash, native_sha256=native_hash,
                        source_path=str(source), native_path=str(native))
        rt = row.get('roundtrip')
        if not isinstance(rt, dict):
            raise Incomplete('No original SolidWorks SaveAsSTEP roundtrip receipt')
        saved = rt.get('save', {})
        if saved.get('ok') is not True or saved.get('errors') != 0:
            raise Incomplete('SolidWorks roundtrip export was absent or did not succeed')
        roundtrip, rt_hash = bind_file(rt.get('path'), saved.get('sha256'), '.step', snapshots)
        require(roundtrip != source, 'Roundtrip path points to original source rather than a native export')
        evidence.update(roundtrip_path=str(roundtrip), roundtrip_sha256=rt_hash,
                        original_solidworks_roundtrip_export=copy.deepcopy(rt))
        expected = part.get('expected_solid_count')
        require(type(expected) is int and expected > 0, 'Invalid expected solid count')
        native_facts = row.get('facts', {})
        if 'sheet_count' not in native_facts or 'solid_count' not in native_facts:
            raise Incomplete('Original native receipt lacks solid/sheet body count')
        require(native_facts['solid_count'] == expected and native_facts['sheet_count'] == 0,
                'Native solid/sheet body count violates the source contract')
        evidence['original_native_solid_count'] = native_facts['solid_count']
        evidence['original_native_sheet_count'] = native_facts['sheet_count']
        if not kernel_holder:
            kernel_holder.append(Kernel())
        kernel = kernel_holder[0]
        evidence['volume_integration_method'] = kernel.method
        progress('import_roundtrip_pair', part_key=row.get('part_key'), source=str(source), roundtrip=str(roundtrip))
        source_shape = kernel.load(source)
        returned_shape = kernel.load(roundtrip)
        evidence.update(kernel.compare(source_shape, returned_shape, expected))
    except Incomplete as exc:
        evidence.update(status='INCOMPLETE', reason=str(exc))
    except Exception as exc:
        evidence.update(status='FAIL', reason=str(exc), exception_type=type(exc).__name__)
    finally:
        del source_shape, returned_shape
        gc.collect()
    return evidence


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--imports', type=Path, default=ROOT/'results/NATIVE_IMPORTS.json')
    ap.add_argument('--manifest', type=Path, default=ROOT/'results/PARTS_SOURCE_MANIFEST_DEDUP.json')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--apply', action='store_true', help='Attach evidence after saving a byte-exact original imports backup')
    args = ap.parse_args(argv)
    require(args.limit is None or args.limit > 0, '--limit must be a positive integer')
    imports_path, manifest_path = args.imports.resolve(), args.manifest.resolve()
    require(imports_path.is_relative_to(ROOT.resolve()) and manifest_path.is_relative_to(ROOT.resolve()),
            'Inputs must be inside the delivery package')
    imports_bytes = imports_path.read_bytes()
    imports_hash = hashlib.sha256(imports_bytes).hexdigest()
    original = json.loads(imports_bytes.decode('utf-8-sig'))
    manifest = read(manifest_path)
    manifest_hash, script_hash = sha(manifest_path), sha(__file__)
    require(original.get('manifest_sha256') == manifest_hash, 'Native imports use another source manifest')
    parts = {p['part_key']:p for p in manifest['parts']}
    require(len(parts) == len(manifest['parts']), 'Duplicate manifest part keys')
    require(len({r['part_key'] for r in original['parts']}) == len(original['parts']), 'Duplicate native import part keys')
    snapshots = {str(imports_path):imports_hash, str(manifest_path):manifest_hash,
                 str(Path(__file__).resolve()):script_hash}
    derived = copy.deepcopy(original)
    candidate_indices = [i for i,r in enumerate(derived['parts'])
                         if isinstance(r.get('roundtrip'), dict) or r.get('source_comparison', {}).get('pass') is not True]
    chosen = candidate_indices if args.limit is None else candidate_indices[:args.limit]
    reports, kernel_holder = [], []
    for i in chosen:
        row = derived['parts'][i]
        old_comparison = copy.deepcopy(row.get('source_comparison', {}))
        evidence = validate_one(row, parts.get(row['part_key']), snapshots, kernel_holder, script_hash)
        row.setdefault('source_comparison', {})['roundtrip_validation'] = evidence
        # Existing scalar pass/status/number evidence may not be modified.
        restored = copy.deepcopy(row['source_comparison'])
        if 'roundtrip_validation' in old_comparison:
            restored['roundtrip_validation'] = old_comparison['roundtrip_validation']
        else:
            restored.pop('roundtrip_validation', None)
        require(restored == old_comparison, 'Original source comparison was altered')
        reports.append(dict(part_key=row['part_key'], original_source_comparison=old_comparison,
                            roundtrip_validation=evidence))
        progress('roundtrip_result', part_key=row['part_key'], status=evidence['status'],
                 volume_difference_mm3=evidence['volume_difference_mm3'],
                 symmetric_difference_mm3=evidence['symmetric_difference_mm3'])
    after = {path:sha(path) for path in snapshots}
    unchanged = after == snapshots
    if not unchanged:
        for report in reports:
            report['roundtrip_validation'].update(status='FAIL', reason='One or more bound inputs changed during validation')
    counts = dict(Counter(r['roundtrip_validation']['status'] for r in reports))
    failed, incomplete = counts.get('FAIL', 0), counts.get('INCOMPLETE', 0)
    limited = len(chosen) < len(candidate_indices)
    status = ('FAIL' if failed or not unchanged else 'INCOMPLETE' if incomplete else
              'PASS_LIMITED_ROUNDTRIP_SCOPE' if limited else 'PASS_RECORDED_ROUNDTRIP_GEOMETRY_ONLY')
    summary = dict(schema='WP05_NATIVE_ROUNDTRIP_VALIDATION_V1', status=status,
        generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(), counts=counts,
        available_native_receipt_count=len(original['parts']), source_manifest_part_count=len(parts),
        candidate_roundtrip_count=len(candidate_indices), examined_count=len(chosen),
        deferred_part_keys=[derived['parts'][i]['part_key'] for i in candidate_indices[len(chosen):]],
        limited_scope=limited, input_sha256_before=snapshots, input_sha256_after=after,
        input_files_unchanged=unchanged, results=reports, original_scalar_witnesses_unchanged=True,
        com_export_executed=False, full_native_delivery_complete=False,
        physical_assembly_completed=False, manufacturing_release=False)
    result_path = ROOT/'results/NATIVE_ROUNDTRIP_VALIDATION.json'
    derived_path = ROOT/'results/NATIVE_IMPORTS_ROUNDTRIP_VALIDATED.json'
    write(derived_path, derived)
    summary['derived_imports'] = dict(path=str(derived_path), sha256=sha(derived_path))
    if args.apply and unchanged:
        backup = ROOT/'results/native_import_history'/('NATIVE_IMPORTS_'+imports_hash+'.json')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists():
            require(sha(backup) == imports_hash, 'Existing history file is not the original imports content')
        else:
            backup.write_bytes(imports_bytes)
        require(sha(imports_path) == imports_hash, 'Native imports changed before evidence attachment')
        write(imports_path, derived)
        summary['applied_imports'] = dict(path=str(imports_path), sha256=sha(imports_path))
        summary['original_imports_preserved'] = dict(path=str(backup), sha256=sha(backup))
    write(result_path, summary)
    progress('roundtrip_validation_finished', status=status, report=str(result_path), counts=counts,
             applied=bool(args.apply and unchanged), limited_scope=limited)
    return 1 if failed or not unchanged else 2 if incomplete else 0


if __name__ == '__main__':
    raise SystemExit(main())
