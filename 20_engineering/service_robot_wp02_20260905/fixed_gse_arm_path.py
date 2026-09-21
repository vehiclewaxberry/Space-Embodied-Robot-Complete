"""26-pose accepted-STL check against final fixed GSE receipt boxes.

No BRep imports. Strict bounds are only rejection tests; overlap proceeds to
original-triangle clipping. Hollow/holed part boxes remain envelopes.
"""
from pathlib import Path
import hashlib
import json
import sys
import time
import numpy as np
import motion_analysis as motion

HERE=Path(__file__).resolve().parent
RECEIPT=HERE/'results/released_build_receipt.json'
OUTPUT=HERE/'results/FIXED_GSE_ARM_PATH.json'
TOL=1e-8

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def selected(name):
    lower=name.lower()
    return any(token in lower for token in ['fixed_y_rail','rail_end_hanger','overhead_longitudinal',
               'overhead_offset','lower_offset_bridge','fixed-crossbeam','latch_fixed_hanger',
               'latch_top_bridge','pin_housing_seat','screw_end_mount']) or ('_tower_' in lower and '_foot_' not in lower)

def main():
    started=time.monotonic();receipt_source=RECEIPT
    if '--key-receipt' in sys.argv:
        receipt_source=HERE/'results/KEY_GEOMETRY_CHECK.json'
        key=json.loads(receipt_source.read_text(encoding='utf-8'))
        assert key['source_hashes_at_import'][str(HERE/'parts_model.py')]==sha(HERE/'parts_model.py')
        assert not key['source_changed_during_run']
        receipt=key['released_receipt_snapshot']
    else:
        receipt=json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert receipt['state']=='released'
    parts=[]
    for rec in receipt['parts']:
        if not selected(rec['instance']):continue
        lo=np.asarray(rec['min_mm'],float);hi=np.asarray(rec['max_mm'],float);box_volume=float(np.prod(hi-lo))
        volume=float(rec['volume_mm3']);tower='_tower_' in rec['instance'].lower()
        equal_volume=abs(box_volume-volume)<=max(1e-4,box_volume*1e-7)
        representation='HOLLOW_TOWER_OUTER_ENVELOPE' if tower else 'DECLARED_AXIS_ALIGNED_SOLID_BOX' if equal_volume else 'HOLED_OR_NONBOX_OUTER_ENVELOPE'
        parts.append({'instance':rec['instance'],'part_number':rec['part_number'],'min_mm':lo.tolist(),'max_mm':hi.tolist(),
                      'volume_from_receipt_mm3':volume,'bbox_volume_mm3':box_volume,'representation':representation,
                      'bbox_is_material_geometry':representation=='DECLARED_AXIS_ALIGNED_SOLID_BOX',
                      'classification_basis':'Selected part construction is axis-aligned; receipt solid volume equals box volume within1e-7 relative tolerance, or explicitly marked envelope.'})
    raw,sources=motion.read_triangles();samples=[];hits=[];candidates=[];plane_separated=0
    for fraction in motion.SAMPLES:
        q=motion.Q0+fraction*(motion.Q1-motion.Q0);world=motion.transform_meshes(raw,q)
        sample={'fraction':fraction,'q_deg':q.tolist(),'aabb_strictly_separated_pairs':0,'triangle_clip_pairs':0,'hits':[]}
        for name,tris in world.items():
            lo=tris.min(axis=(0,1));hi=tris.max(axis=(0,1))
            for part in parts:
                box_lo=np.asarray(part['min_mm']);box_hi=np.asarray(part['max_mm'])
                overlap=np.minimum(hi,box_hi)-np.maximum(lo,box_lo)
                if np.any(overlap < -TOL):
                    sample['aabb_strictly_separated_pairs']+=1;plane_separated+=1;continue
                limits={axis:(box_lo[axis],box_hi[axis]) for axis in range(3)}
                clipped=motion.clipped_bounds(tris,limits);sample['triangle_clip_pairs']+=1
                pair={'fraction':fraction,'link':name,'fixture':part['instance'],'fixture_representation':part['representation'],
                      'aabb_axis_overlap_mm':overlap.tolist(),'triangle_surface_intersection':clipped is not None}
                candidates.append(pair)
                if clipped:
                    hit=dict(pair,intersection_geometry=clipped,actual_material_common_volume_mm3=None,
                             finding='DECLARED_SOLID_BOX_SURFACE_INTERSECTION' if part['bbox_is_material_geometry'] else 'ENVELOPE_OVERLAP_REQUIRES_BREP_REFINEMENT')
                    sample['hits'].append(hit);hits.append(hit)
                    print(json.dumps({'event':'FIXED_GSE_ARM_FINDING','data':hit}),flush=True)
        samples.append(sample)
        print(json.dumps({'event':'sample_complete','fraction':fraction,'narrow_pairs':sample['triangle_clip_pairs'],'hits':len(sample['hits'])}),flush=True)
    result={'schema':'FIXED_GSE_ACCEPTED_ARM_SAMPLED_PATH_V1',
            'status':'SAMPLED_PATH_CHECK_NO_SURFACE_INTERSECTION_IN_TESTED_BOXES' if not hits else 'SAMPLED_PATH_CHECK_WITH_EXPLICIT_FINDINGS',
            'sample_count':len(samples),'arm_link_count':len(raw),'fixed_fixture_count':len(parts),
            'total_sample_link_fixture_pairs':len(samples)*len(raw)*len(parts),'strict_aabb_separation_count':plane_separated,
            'triangle_clip_pair_count':len(candidates),'surface_hit_count':len(hits),'hits':hits,'parts':parts,'samples':samples,
            'triangle_clip_pairs':candidates,'q_park_deg':motion.Q0.tolist(),'q_work_deg':motion.Q1.tolist(),
            'root_transform':motion.BASE.tolist(),'finger_mm':motion.FINGER_MM,
            'state_scope':'Fixed hardware from final released receipt; lower shoes/upper pads/movingYgroup excluded. Moving group endpoint plane separation is a separate receipt.',
            'contains_status':'UNKNOWN_NOT_TESTED','continuous_rotating_path_status':'UNKNOWN_BETWEEN26_SAMPLES',
            'actual_material_intersection_volume_status':'NOT_COMPUTED_FOR_ANY_STL_OR_ENVELOPE_PAIR',
            'limitations':['No BRep import or full assembly collision test.','Strict AABB separation is a sufficient rejection only; overlap is never automatically a collision.',
                           'Original accepted-STL triangles are clipped against actual receipt boxes. No hit does not establish mesh volume containment absence.',
                           'Holed fixed beams and hollow towers use outer envelopes; positive overlap would require actual-material refinement.',
                           'No qualification of contact forces, shell loads, harness routing or wing swing.'],
            'released_receipt_source':str(receipt_source),'released_receipt_is_embedded_snapshot':receipt_source!=RECEIPT,
            'source_hashes':{str(receipt_source):sha(receipt_source),str(HERE/'parts_model.py'):sha(HERE/'parts_model.py'),
                             str(HERE/'design_parameters.json'):sha(HERE/'design_parameters.json'),
                             str(HERE/'motion_analysis.py'):sha(HERE/'motion_analysis.py'),str(Path(__file__)):sha(Path(__file__))},
            'mesh_sources':sources,'elapsed_seconds':time.monotonic()-started}
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:result[key] for key in ['status','sample_count','fixed_fixture_count','total_sample_link_fixture_pairs','strict_aabb_separation_count','triangle_clip_pair_count','surface_hit_count','elapsed_seconds']}),flush=True)

if __name__=='__main__':main()
