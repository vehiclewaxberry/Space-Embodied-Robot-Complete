"""Reversible in-memory shape-healing probe; never overwrites source geometry."""
from pathlib import Path
import hashlib
import json
import sys
import time

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from cadgen.step_scene import import_step
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.ShapeFix import ShapeFix_Shape
from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results/SOURCE_TOPOLOGY_REPAIR_PROBE.json'
TIME_LIMIT_S = 115


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def members(shape, kind):
    rows = []
    cursor = TopExp_Explorer(shape, kind)
    while cursor.More():
        rows.append(cursor.Current())
        cursor.Next()
    return rows


def metrics(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return dict(valid=BRepCheck_Analyzer(shape).IsValid(),
                volume_mm3=props.Mass(), bbox_mm=list(box.Get()),
                solid_count=len(members(shape, TopAbs_SOLID)),
                shell_count=len(members(shape, TopAbs_SHELL)),
                face_count=len(members(shape, TopAbs_FACE)))


def main():
    started = time.perf_counter()
    records = []
    stopped = False
    for name in ['base_link', 'link2']:
        source = HERE / 'inputs' / (name + '.step')
        digest = sha(source)
        print('Reading', name, flush=True)
        shape = import_step(source)
        solids = list(shape.solids())
        record = dict(link=name, source=str(source), source_sha256_before=digest,
                      imported_solid_count=len(solids), invalid_solids=[], valid_solid_count=0)
        for index, solid in enumerate(solids):
            if time.perf_counter() - started > TIME_LIMIT_S:
                stopped = True
                break
            if BRepCheck_Analyzer(solid.wrapped).IsValid():
                record['valid_solid_count'] += 1
                continue
            before = metrics(solid.wrapped)
            row = dict(index=index, before=before)
            print('Invalid', name, index, before['volume_mm3'], flush=True)
            try:
                # ShapeFix mutates an in-memory imported shape only. No export occurs.
                fixer = ShapeFix_Shape(solid.wrapped)
                fixer.Perform()
                fixed = fixer.Shape()
                after = metrics(fixed)
                row.update(method='OCP.ShapeFix_Shape.Perform', after=after,
                           volume_delta_mm3=after['volume_mm3']-before['volume_mm3'],
                           relative_volume_delta=abs(after['volume_mm3']-before['volume_mm3'])/max(abs(before['volume_mm3']),1e-30),
                           bbox_max_abs_delta_mm=max(abs(x-y) for x,y in zip(before['bbox_mm'],after['bbox_mm'])),
                           all_source_solids_retained=after['solid_count']==before['solid_count'])
                row['repair_valid_without_solid_loss'] = after['valid'] and row['all_source_solids_retained']
                print('Repair', name, index, row['repair_valid_without_solid_loss'], row['relative_volume_delta'], row['bbox_max_abs_delta_mm'], flush=True)
            except Exception as exc:
                row.update(error=str(exc), repair_valid_without_solid_loss=False)
            record['invalid_solids'].append(row)
        record['source_sha256_after'] = sha(source)
        record['source_unchanged'] = record['source_sha256_after'] == digest
        records.append(record)
        if stopped:
            break
    invalid = [row for record in records for row in record['invalid_solids']]
    out = dict(method='READ_INPUT_STEP_SCAN_EACH_SOLID_BREPCHECK_THEN_SHAPEFIX_IN_MEMORY',
               sources=records, invalid_solid_count=len(invalid),
               repaired_valid_without_solid_loss_count=sum(row['repair_valid_without_solid_loss'] for row in invalid),
               time_limit_reached=stopped, elapsed_s=time.perf_counter()-started,
               status='INCOMPLETE' if stopped else
                      'ALL_INVALID_SOLIDS_REPAIRABLE_IN_MEMORY' if invalid and all(row['repair_valid_without_solid_loss'] for row in invalid) else
                      'NO_INVALID_SOURCE_SOLIDS_FOUND' if not invalid else 'SOME_REPAIRS_UNSUCCESSFUL',
               files_changed=['probe_source_topology.py','results/SOURCE_TOPOLOGY_REPAIR_PROBE.json'],
               geometry_exported=False, original_solids_deleted=False,
               scope='REPAIR_FEASIBILITY_ONLY; NO_INPUT_OR_FINAL_CAD_MODIFICATION; NO_SYSTEM_PASS')
    OUT.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps({k:out[k] for k in ['status','invalid_solid_count','repaired_valid_without_solid_loss_count','elapsed_s']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
