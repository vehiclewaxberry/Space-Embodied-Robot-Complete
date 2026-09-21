"""Read-only exact positive-volume intersection audit of the small root module."""
from pathlib import Path
import hashlib
import json
import sys
import time

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # Apply the packaged invalid-font guard before build123d imports.
from cadgen.step_scene import import_step
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'frame_root_module.step'
OUT = HERE / 'results' / 'STRUCTURE_CONTACT_CHECK.json'
TIME_LIMIT_S = 115
VOLUME_TOL_MM3 = 1e-7


def bbox(shape):
    b = shape.bounding_box()
    return [list(b.min), list(b.max)]


def main():
    started = time.perf_counter()
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    shape = import_step(SOURCE)
    solids = list(shape.solids())
    receipt = json.loads((HERE / 'results' / 'structure_build_receipt.json').read_text())
    rows = []
    used = set()
    for i, solid in enumerate(solids):
        bounds = bbox(solid)
        candidates = []
        for j, part in enumerate(receipt['parts']):
            if j in used or part['solids'] != 1:
                continue
            reference = [part['min_mm'], part['max_mm']]
            error = max(abs(bounds[a][b] - reference[a][b]) for a in (0, 1) for b in range(3))
            candidates.append((error, j))
        error, match = min(candidates) if candidates else (None, None)
        accepted = match is not None and error < 0.01
        if accepted:
            used.add(match)
        rows.append(dict(index=i, part=receipt['parts'][match]['part'] if accepted else None,
                         name_source='UNIQUE_RECEIPT_BBOX_MATCH' if accepted else 'UNMATCHED',
                         bbox_match_error_mm=error, bbox_mm=bounds, volume_mm3=solid.volume))
    checked, overlaps, errors = [], [], []
    exhausted = False
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            a, b = rows[i]['bbox_mm'], rows[j]['bbox_mm']
            widths = [min(a[1][k], b[1][k]) - max(a[0][k], b[0][k]) for k in range(3)]
            if min(widths) <= 1e-6:
                continue
            if time.perf_counter() - started > TIME_LIMIT_S:
                exhausted = True
                break
            pair = dict(indices=[i, j], parts=[rows[i]['part'], rows[j]['part']],
                        aabb_overlap_width_mm=widths,
                        source_bboxes_mm=[a, b])
            try:
                common = BRepAlgoAPI_Common(solids[i].wrapped, solids[j].wrapped)
                if not common.IsDone():
                    raise RuntimeError('OCC boolean common did not complete')
                result = common.Shape()
                prop = GProp_GProps()
                BRepGProp.VolumeProperties_s(result, prop)
                pair['common_volume_mm3'] = abs(prop.Mass())
                pair['positive_volume_overlap'] = pair['common_volume_mm3'] > VOLUME_TOL_MM3
                checked.append(pair)
                if pair['positive_volume_overlap']:
                    overlaps.append(pair)
            except Exception as exc:
                pair['error'] = str(exc)
                errors.append(pair)
        if exhausted:
            break
    out = dict(source=str(SOURCE), source_sha256=source_hash,
               source_hash_after=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
               method='AABB_BROADPHASE_THEN_OCC_BREP_BOOLEAN_COMMON_VOLUME',
               units='mm_and_mm3', solid_count=len(solids), solids=rows,
               exact_pairs=checked, positive_volume_overlaps=overlaps,
               errors=errors, time_limit_reached=exhausted,
               elapsed_s=time.perf_counter()-started,
               volume_threshold_mm3=VOLUME_TOL_MM3,
               status='INCOMPLETE' if exhausted or errors else
                      'POSITIVE_VOLUME_OVERLAPS_FOUND' if overlaps else 'NO_POSITIVE_VOLUME_OVERLAPS',
               scope='STATIC_EXPORTED_STRUCTURE_ONLY; FACE_CONTACT_NOT_CLASSIFIED; NO_STRENGTH_OR_ASSEMBLY_FIT_CLAIM')
    OUT.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps({k: out[k] for k in ['status','solid_count','elapsed_s','time_limit_reached']}, indent=2))
    print(json.dumps(overlaps, indent=2))


if __name__ == '__main__':
    main()
