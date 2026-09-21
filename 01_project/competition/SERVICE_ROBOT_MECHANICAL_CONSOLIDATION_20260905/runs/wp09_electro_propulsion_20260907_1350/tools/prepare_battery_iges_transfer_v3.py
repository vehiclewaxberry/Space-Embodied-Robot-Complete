"""Export four unchanged battery screw STEP shapes as IGES BRep and verify readback.

Only main execution loads OCP. No producer, build123d, native builder or COM is
imported. This receipt provides neutral-format transfer evidence only; original
source STEP files remain the material reference for later native checks.

V2 corrects V1's invalid effective-fuzzy-equals-zero assertion. OCCT 7.9.3
clamps a requested zero to Precision::Confusion(); no fuzzy enlargement above
the kernel default is permitted. Existing acceptance thresholds are unchanged.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback
import time

sys.dont_write_bytecode = True
R = Path(__file__).resolve().parents[1]
IDS = tuple(f'WP09_BAT_{x}_{y}_screw' for x in (-152, -76) for y in (-78, 78))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def normalized(path):
    return os.path.normcase(str(Path(path).resolve()))


class Audit:
    def __init__(self, output):
        self.output = output
        self.data = dict(
            schema='WP09_SOURCE_STEP_IGES_TRANSFER_V3_FILE_REPLACE_RETRY', status='IN_PROGRESS',
            started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            parts={}, results=[], input_sha256_before={},
            source_reference_remains_original_step=True,
            no_producer_or_build123d_imported=True, no_com_used=True,
            geometry_edit_or_healing_requested=False,
            mathematical_zero_tolerance_claimed=False,
            acceptance_thresholds_changed=False,
            boolean_tolerance_policy=dict(
                requested_fuzzy_mm=0.0,
                effective_fuzzy_policy='Measured runtime value must equal '
                    'Precision::Confusion() and must not exceed the measured '
                    'fresh algorithm default; no user-added enlargement.',
                limit_of_claim='Kernel numerical floor and existing per-shape '
                    'tolerances remain operative; this is not a mathematical '
                    'zero-tolerance equivalence proof.',
                implementation_source='https://raw.githubusercontent.com/Open-Cascade-SAS/OCCT/'
                    'V7_9_3/src/BOPAlgo/BOPAlgo_Options.cxx',
                precision_source='https://raw.githubusercontent.com/Open-Cascade-SAS/OCCT/'
                    'V7_9_3/src/Precision/Precision.hxx',
                api_inheritance_source='https://raw.githubusercontent.com/Open-Cascade-SAS/OCCT/'
                    'V7_9_3/src/BRepAlgoAPI/BRepAlgoAPI_Algo.hxx'),
            writer=dict(api='IGESControl_Writer', unit='MM', mode=1,
                        mode_meaning='BRep', transforms_applied=False),
            native_material_equivalence_verified=False,
            integrated_into_wp08=False, battery_self_retention_verified=False,
            electrical_complete=False, manufacturing_release=False,
            scope='Four existing catalogue proxy screw solids; STEP-to-IGES '
                  'material transfer within contract limits and the measured '
                  'OCCT numerical floor only. Not SolidWorks import equivalence, '
                  'actual screw qualification, preload, thread or load evidence.')

    def pin(self, path, expected=None):
        path = str(Path(path).resolve())
        actual = sha(path)
        require(expected is None or actual == expected, 'SHA256 mismatch: ' + path)
        previous = self.data['input_sha256_before'].get(path)
        require(previous is None or previous == actual, 'Input changed: ' + path)
        self.data['input_sha256_before'][path] = actual
        return path

    def check(self, ident, okay, measurement):
        self.data['results'].append(dict(id=ident, status='PASS' if okay is True else 'FAIL',
                                         measurement=measurement))

    def write(self, status='IN_PROGRESS'):
        self.data['status'] = status
        self.data['checkpoint_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        self.data['counts'] = dict(Counter(r['status'] for r in self.data['results']))
        temporary = self.output.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(self.data, indent=2, ensure_ascii=False,
                                       allow_nan=False), encoding='utf-8')
        for attempt in range(20):
            try:
                temporary.replace(self.output)
                break
            except PermissionError:
                if attempt==19:raise
                time.sleep(0.1)


def execute(audit, emission_path, contract_path, outdir):
    emission_path = audit.pin(emission_path)
    contract_path = audit.pin(contract_path)
    audit.pin(__file__)
    audit.data['superseded_checker_lineage'] = dict(
        script=audit.pin(R / 'tools/prepare_battery_iges_transfer.py'),
        failed_receipt=audit.pin(R / 'results/battery_iges_transfer/CHECK.json'),
        reason='V1 incorrectly required effective fuzzy readback to be zero; '
               'V1 receipt and generated IGES files are preserved unchanged.')
    emission = read_json(emission_path)
    contract = read_json(contract_path)
    require(emission['schema'] == 'WP09_BATTERY_MOUNT_EMISSION', 'Wrong emission schema')
    require(contract['revision'] == 'V2_SOURCE_CONE_MATCHED_AFTER_V2_ACTUAL_ZERO_CONTACT',
            'This transfer requires the battery V2 contract')
    require(normalized(emission['contract_path']) == normalized(contract_path),
            'Emission/contract path mismatch')
    audit.pin(contract_path, emission['contract_sha256'])
    audit.pin(emission['producer_path'], emission['producer_sha256'])
    acceptance = contract['acceptance']
    linear = float(acceptance['linear_mm'])
    material = float(acceptance['volume_mm3'])
    eps = float(acceptance['integration_eps'])
    require(all(math.isfinite(v) and v > 0 for v in (linear, material, eps)),
            'Invalid acceptance thresholds')
    audit.data['acceptance'] = dict(acceptance)
    audit.data['emission_path'] = emission_path
    audit.data['contract_path'] = contract_path
    found = {p for p in emission['parts'] if p.endswith('_screw')}
    require(found == set(IDS), 'Unexpected battery screw IDs')
    for ident in IDS:
        part = emission['parts'][ident]
        source = audit.pin(part['path'], part['sha256'])
        catalogue = part['catalogue_source']
        audit.pin(catalogue['path'], catalogue['sha256'])
        require(catalogue == contract['catalogue_parts']['screw'],
                'Catalogue provenance differs from contract')
        audit.data['parts'][ident] = dict(
            status='NOT_EXECUTED', source_step=source, source_sha256=part['sha256'],
            iges_path=str((outdir / (ident + '.igs')).resolve()), iges_sha256=None,
            representation_role=part['representation_role'],
            qualification=part.get('qualification'), catalogue_source=catalogue)
    audit.write()

    # Deliberately local imports: reading or compiling this script never runs CAD.
    import OCP
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.IGESControl import IGESControl_Reader, IGESControl_Writer
    from OCP.STEPControl import STEPControl_Reader
    from OCP.Precision import Precision
    from OCP.TopAbs import (TopAbs_SOLID, TopAbs_SHELL, TopAbs_FACE,
                            TopAbs_WIRE, TopAbs_EDGE, TopAbs_VERTEX)
    from OCP.TopExp import TopExp
    from OCP.TopTools import TopTools_IndexedMapOfShape, TopTools_ListOfShape

    audit.data['ocp_version'] = getattr(OCP, '__version__', 'NOT_EXPOSED')
    for name, module in sorted(sys.modules.items()):
        if name == 'OCP' or name.startswith('OCP.'):
            path = getattr(module, '__file__', None)
            if path and Path(path).is_file():
                audit.pin(path)

    def mapped(shape, kind):
        items = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(shape, kind, items)
        return items

    def volume(shape):
        items = mapped(shape, TopAbs_SOLID)
        values, errors = [], []
        for number in range(1, items.Extent() + 1):
            solid = items.FindKey(number)
            require(BRepCheck_Analyzer(solid).IsValid(), 'Invalid solid in integration')
            props = GProp_GProps()
            error = BRepGProp.VolumeProperties_s(solid, props, Eps=eps,
                                                OnlyClosed=True, SkipShared=False)
            value = float(props.Mass())
            require(error is not None and math.isfinite(float(error)) and error >= 0,
                    'Invalid adaptive integration result')
            require(math.isfinite(value), 'Nonfinite volume')
            values.append(abs(value))
            errors.append(float(error))
        return dict(volume_mm3=math.fsum(values), integration_error_estimates=errors,
                    solid_count=items.Extent())

    def facts(shape):
        require(not shape.IsNull(), 'Null transferred shape')
        solids = mapped(shape, TopAbs_SOLID)
        bounds = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, bounds, False, False)
        require(not bounds.IsVoid() and not bounds.IsOpen(), 'Invalid/unbounded bbox')
        bbox = [float(v) for v in bounds.Get()]
        require(all(math.isfinite(v) for v in bbox), 'Nonfinite bbox')
        free = {}
        if solids.Extent() == 1:
            solid = solids.FindKey(1)
            for label, kind in [('shell', TopAbs_SHELL), ('face', TopAbs_FACE),
                                ('wire', TopAbs_WIRE), ('edge', TopAbs_EDGE),
                                ('vertex', TopAbs_VERTEX)]:
                all_items, body_items = mapped(shape, kind), mapped(solid, kind)
                free[label] = sum(not body_items.Contains(all_items.FindKey(i))
                                  for i in range(1, all_items.Extent() + 1))
        return dict(valid=bool(BRepCheck_Analyzer(shape).IsValid()), bbox_mm=bbox,
                    free_topology_outside_sole_solid=free, **volume(shape))

    def read_shape(path, is_iges):
        reader = IGESControl_Reader() if is_iges else STEPControl_Reader()
        status = reader.ReadFile(str(path))
        require(status == IFSelect_RetDone, 'Neutral file ReadFile failed: ' + str(path))
        transferred = int(reader.TransferRoots())
        require(transferred > 0, 'No transferred roots: ' + str(path))
        return reader.OneShape(), dict(read_status=int(status), transferred_roots=transferred,
                                       reader='IGESControl_Reader' if is_iges else 'STEPControl_Reader')

    def directed_cut(a, b):
        args, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
        args.Append(a)
        tools.Append(b)
        operation = BRepAlgoAPI_Cut()
        default_fuzzy = float(operation.FuzzyValue())
        confusion = float(Precision.Confusion_s())
        observation = dict(requested_fuzzy_mm=0.0,
                           fresh_algorithm_default_fuzzy_mm=default_fuzzy,
                           precision_confusion_mm=confusion,
                           effective_fuzzy_before_mm=None, effective_fuzzy_mm=None)
        audit.data.setdefault('boolean_tolerance_observations', []).append(observation)
        require(math.isfinite(confusion) and confusion > 0.0,
                'Invalid runtime Precision::Confusion()')
        require(default_fuzzy == confusion,
                'Fresh algorithm fuzzy default differs from documented kernel floor')
        operation.SetArguments(args)
        operation.SetTools(tools)
        # Preserve input shapes across the two independent directed cuts.
        operation.SetNonDestructive(True)
        require(operation.NonDestructive(), 'Non-destructive Boolean mode not enabled')
        requested = 0.0
        operation.SetFuzzyValue(requested)
        effective_before = float(operation.FuzzyValue())
        observation['effective_fuzzy_before_mm'] = effective_before
        require(effective_before == max(requested, confusion)
                and effective_before <= default_fuzzy,
                'Effective fuzzy exceeds kernel default or violates documented clamp')
        operation.Build()
        require(operation.IsDone(), 'Directed BRep cut did not complete')
        fuzzy = float(operation.FuzzyValue())
        observation['effective_fuzzy_mm'] = fuzzy
        require(fuzzy == effective_before and fuzzy <= default_fuzzy,
                'Boolean execution changed or enlarged the effective fuzzy value')
        result = operation.Shape()
        require(not result.IsNull(), 'Null Boolean result')
        valid = bool(BRepCheck_Analyzer(result).IsValid())
        require(valid, 'Invalid Boolean result')
        return dict(done=True, valid=valid, fuzzy_mm=fuzzy,
                    requested_fuzzy_mm=requested,
                    effective_fuzzy_before_mm=effective_before,
                    effective_fuzzy_mm=fuzzy, precision_confusion_mm=confusion,
                    fresh_algorithm_default_fuzzy_mm=default_fuzzy,
                    effective_not_above_default=True,
                    non_destructive=bool(operation.NonDestructive()),
                    mathematical_zero_tolerance=False, **volume(result))

    for ident in IDS:
        row = audit.data['parts'][ident]
        row['status'] = 'IN_PROGRESS'
        audit.write()
        try:
            source, source_reader = read_shape(row['source_step'], False)
            original = facts(source)
            row['source'] = dict(reader=source_reader, **original)
            expected = emission['parts'][ident]['bbox_mm']
            expected_bbox = expected['min_mm'] + expected['max_mm']
            source_bbox_delta = max(abs(a-b) for a, b in zip(original['bbox_mm'], expected_bbox))
            okay_source = (original['valid'] and original['solid_count'] == 1
                           and original['volume_mm3'] > material
                           and not any(original['free_topology_outside_sole_solid'].values())
                           and source_bbox_delta <= linear)
            audit.check(ident + ':source', okay_source,
                        dict(**original, emission_bbox_max_delta_mm=source_bbox_delta))
            require(okay_source, 'Source STEP validation failed')
            destination = Path(row['iges_path'])
            require(not destination.exists(), 'Refusing to overwrite IGES: ' + str(destination))
            writer = IGESControl_Writer('MM', 1)
            require(writer.AddShape(source), 'IGES AddShape failed')
            writer.ComputeModel()
            require(writer.Write(str(destination)), 'IGES Write failed')
            require(destination.is_file() and destination.stat().st_size > 0, 'No IGES output')
            row['iges_sha256'] = sha(destination)
            # Reload the original STEP independently, so writer-side in-memory
            # modifications cannot define the reference used in comparison.
            reference, _ = read_shape(row['source_step'], False)
            transferred, readback_reader = read_shape(destination, True)
            recovered = facts(transferred)
            row['iges_readback'] = dict(reader=readback_reader, **recovered)
            okay_readback = (recovered['valid'] and recovered['solid_count'] == 1
                             and recovered['volume_mm3'] > material
                             and not any(recovered['free_topology_outside_sole_solid'].values()))
            audit.check(ident + ':readback', okay_readback, recovered)
            require(okay_readback, 'IGES readback validation failed')
            bbox_delta = max(abs(a-b) for a, b in zip(original['bbox_mm'], recovered['bbox_mm']))
            volume_delta = abs(original['volume_mm3'] - recovered['volume_mm3'])
            row['bbox_max_delta_mm'] = bbox_delta
            row['volume_abs_delta_mm3'] = volume_delta
            audit.check(ident + ':bbox', bbox_delta <= linear,
                        dict(max_delta_mm=bbox_delta, limit_mm=linear))
            audit.check(ident + ':volume', volume_delta <= material,
                        dict(abs_delta_mm3=volume_delta, limit_mm3=material))
            for label, a, b in [('source_minus_iges', reference, transferred),
                                 ('iges_minus_source', transferred, reference)]:
                measurement = directed_cut(a, b)
                row[label] = measurement
                audit.check(ident + ':' + label, measurement['volume_mm3'] <= material,
                            dict(**measurement, limit_mm3=material))
            own_results = [r for r in audit.data['results'] if r['id'].startswith(ident + ':')]
            row['status'] = ('PASS_SOURCE_STEP_IGES_TRANSFER'
                             if len(own_results) == 6 and all(r['status'] == 'PASS' for r in own_results)
                             else 'FAIL_SOURCE_STEP_IGES_TRANSFER')
        except Exception as exc:
            row['status'] = 'FAIL_SOURCE_STEP_IGES_TRANSFER'
            audit.check(ident + ':exception', False,
                        dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
        audit.write()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emission', type=Path, default=R / 'results/battery_mount_v2/EMISSION.json')
    parser.add_argument('--contract', type=Path, default=R / 'inputs/BATTERY_MOUNT_CONTRACT_V2.json')
    parser.add_argument('--output-dir', type=Path, default=R / 'results/battery_iges_transfer_v3')
    args = parser.parse_args()
    outdir = args.output_dir.resolve()
    output = outdir / 'CHECK.json'
    # Existing results, including interrupted checkpoints, are immutable here.
    require(not output.exists(), 'Refusing to overwrite existing CHECK.json')
    require(not output.with_suffix('.json.tmp').exists(), 'Existing incomplete checkpoint')
    for ident in IDS:
        require(not (outdir / (ident + '.igs')).exists(), 'Existing IGES output: ' + ident)
    outdir.mkdir(parents=True, exist_ok=True)
    audit = Audit(output)
    audit.write()
    try:
        execute(audit, args.emission, args.contract, outdir)
    except Exception as exc:
        audit.check('execution_exception', False,
                    dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
    after = {}
    for path, expected in audit.data['input_sha256_before'].items():
        try:
            after[path] = sha(path)
        except Exception as exc:
            after[path] = dict(error=str(exc))
    audit.data['input_sha256_after'] = after
    audit.check('inputs_unchanged', after == audit.data['input_sha256_before'],
                dict(input_count=len(after)))
    output_after = {}
    for ident, part in audit.data['parts'].items():
        if part.get('iges_sha256'):
            try:
                current = sha(part['iges_path'])
                output_after[part['iges_path']] = current
                audit.check(ident + ':iges_hash_unchanged', current == part['iges_sha256'],
                            dict(sha256=current))
            except Exception as exc:
                audit.check(ident + ':iges_hash_unchanged', False, dict(error=str(exc)))
    audit.data['output_sha256_after'] = output_after
    success = (set(audit.data['parts']) == set(IDS)
               and all(p['status'] == 'PASS_SOURCE_STEP_IGES_TRANSFER' for p in audit.data['parts'].values())
               and all(r['status'] == 'PASS' for r in audit.data['results']))
    status = 'PASS_SOURCE_STEP_IGES_TRANSFER' if success else 'FAIL_SOURCE_STEP_IGES_TRANSFER'
    audit.write(status)
    print(json.dumps(dict(status=status, output=str(output), counts=audit.data['counts']),
                     ensure_ascii=False), flush=True)
    return 0 if success else 2


if __name__ == '__main__':
    raise SystemExit(main())
