"""Independent lightweight WP02 BRep checks; never imports the arm BRep assembly.

Writes only results/KEY_GEOMETRY_CHECK.json. Suppresses parts_model's automatic
receipt writes while keeping their content in memory for this check.
"""
from pathlib import Path
import hashlib
import itertools
import json
import time
import sys
import numpy as np
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'results/KEY_GEOMETRY_CHECK.json'
MOVING_TOKENS=['Y_carrier','cantilever','carrier_neck','keeper_crossbar','keeper_neck','upper_contact_pad',
               'upper_guide','upper_jack','Y_drive_nut','nut_carrier_link','carrier_flag']
SOURCE_PATHS=[HERE/'parts_model.py',HERE/'design_parameters.json',HERE/'results/CONTACT_REGISTRATION.json']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
SOURCE_HASHES={str(path):digest(path) for path in SOURCE_PATHS}
import parts_model as model
from build123d import Location
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SHELL
from OCP.BRep import BRep_Tool

BOX_TOL=1e-6
VOLUME_TOL=1e-6
def save(result):
    result['source_hashes_after_latest_stage']={str(path):digest(path) for path in SOURCE_PATHS}
    result['source_changed_during_run']=SOURCE_HASHES!=result['source_hashes_after_latest_stage']
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

def build_without_receipt_writes(state,include_context=False):
    captured={};original=Path.write_text
    def capture(path,text,*args,**kwargs):
        if path.parent==HERE/'results' and path.name.endswith('_build_receipt.json'):
            captured[path.name]=json.loads(text);return len(text)
        raise RuntimeError(f'Unexpected write attempted by model builder: {path}')
    Path.write_text=capture
    try:assembly,placed,unique=model.build(state,include_context=include_context,write_parts=False)
    finally:Path.write_text=original
    return assembly,placed,unique,next(iter(captured.values()))

def bounds(shape):
    b=shape.bounding_box();return np.array([list(b.min),list(b.max)])

def overlap(a,b):return np.minimum(a[1],b[1])-np.maximum(a[0],b[0])

def common(a,b,measure_distance=False):
    started=time.monotonic()
    try:
        operation=BRepAlgoAPI_Common(a.wrapped,b.wrapped);operation.Build()
        if not operation.IsDone():return {'status':'BOOLEAN_NOT_DONE','volume_mm3':None}
        shape=operation.Shape();props=GProp_GProps();BRepGProp.VolumeProperties_s(shape,props)
        volume=props.Mass();area=GProp_GProps();BRepGProp.SurfaceProperties_s(shape,area)
        result={'status':'POSITIVE_VOLUME_INTERSECTION' if abs(volume)>VOLUME_TOL else 'NO_POSITIVE_COMMON_VOLUME',
                'volume_mm3':volume,'common_surface_area_mm2':area.Mass(),'boolean_result_topology_valid':BRepCheck_Analyzer(shape).IsValid()}
        if measure_distance:
            distance=BRepExtrema_DistShapeShape(a.wrapped,b.wrapped);distance.Perform()
            result['minimum_distance_mm']=distance.Value() if distance.IsDone() else None
        result['elapsed_seconds']=time.monotonic()-started
        return result
    except Exception as exc:return {'status':'BOOLEAN_ERROR','volume_mm3':None,'error':repr(exc),'elapsed_seconds':time.monotonic()-started}

def at_y(shape,y):return shape.moved(Location((0,y-180,0)))
def is_moving(name):return any(token in name for token in MOVING_TOKENS)
def station(name):return name[0] if name.startswith(('A_','B_')) else None

def check_pair(placed,a,b,y=None,distance=False):
    first=at_y(placed[a],y) if y is not None and is_moving(a) else placed[a]
    second=at_y(placed[b],y) if y is not None and is_moving(b) else placed[b]
    result={'parts':[a,b],'Y_mm':y,'aabb_axis_overlap_mm':overlap(bounds(first),bounds(second)).tolist()}
    result.update(common(first,second,distance));return result

def validate_placed(placed,receipt):
    metadata={r['instance']:r for r in receipt['parts']};rows=[]
    for name,shape in placed.items():
        rec=metadata[name];solids=[]
        for index,solid in enumerate(shape.solids()):
            volume=solid.volume;topology=BRepCheck_Analyzer(solid.wrapped).IsValid()
            shells=[];explorer=TopExp_Explorer(solid.wrapped,TopAbs_SHELL)
            while explorer.More():
                shells.append(bool(BRep_Tool.IsClosed_s(explorer.Current())));explorer.Next()
            solids.append({'solid_index':index,'topology_valid':topology,'volume_mm3':volume,'positive_volume':volume>VOLUME_TOL,'shells_closed':shells})
        rows.append({'instance':name,'basis':rec['geometry_basis'],'classification':rec['classification'],'solid_count':len(solids),'solids':solids,
                     'all_solids_valid_closed_positive':bool(solids) and all(s['topology_valid'] and s['positive_volume'] and all(s['shells_closed']) for s in solids)})
    return {'occurrences':len(rows),'solid_count':sum(r['solid_count'] for r in rows),
            'failing_occurrences':[r['instance'] for r in rows if not r['all_solids_valid_closed_positive']],
            'rows':rows,'scope':'Per-solid topology, shell closure and positive volume only; single-solid self-intersection Boolean not run.'}

def main():
    started=time.monotonic()
    result={'schema':'WP02_KEY_GEOMETRY_CHECK_V1','status':'RUNNING','source_hashes_at_import':SOURCE_HASHES,
            'script_sha256':digest(Path(__file__)),'thresholds':{'aabb_mm':BOX_TOL,'positive_common_volume_mm3':VOLUME_TOL},
            'scope':'Current224 noncontext engineering occurrences per held/released state, including two reused root interface inputs; context hulls and harness envelopes checked separately. NO508-occurrence imported arm BRep; sampledY0/90/180 only.',
            'priority_pairs':[],'sampled_cross_fixed_moving':[],'same_moving_group_internal_checks':[],
            'fixed_join_checks':[],'root_thread_envelope_checks':[],'clearance_interface_checks':[],
            'prior_findings_file':'results/KEY_GEOMETRY_CHECK_R1_FINDINGS.json',
            'prior_findings_sha256':digest(HERE/'results/KEY_GEOMETRY_CHECK_R1_FINDINGS.json'),
            'prior_clearance_file':'results/KEY_GEOMETRY_CHECK_R2_CLEARANCE.json',
            'prior_clearance_sha256':digest(HERE/'results/KEY_GEOMETRY_CHECK_R2_CLEARANCE.json')}
    _,released,unique,receipt=build_without_receipt_writes('released')
    result['released_receipt_snapshot']=receipt
    moving=[name for name in released if is_moving(name)];fixed=[name for name in released if name not in moving]
    result['moving_names']=moving;result['fixed_names']=fixed
    save(result);print(json.dumps({'event':'built_released','occurrences':len(released),'moving':len(moving),'fixed':len(fixed),'source_hash':SOURCE_HASHES[str(HERE/'parts_model.py')]}),flush=True)
    # A released pin can remain geometrically engaged in a bore with zero volume.
    # Probe first motion as well as the three requested large travel positions.
    for prefix in ['A','B']:
        for y in [0,0.25,1,2]:
            row=check_pair(released,f'{prefix}_Y_carrier',f'{prefix}_lock_pin',y,distance=True)
            row['purpose']='Released cross-pin clearance and firstYmotion';result['priority_pairs'].append(row)
            print(json.dumps({'event':'priority_pair','data':row}),flush=True);save(result)
        pin_box=bounds(released[f'{prefix}_lock_pin']);carrier_box=bounds(at_y(released[f'{prefix}_Y_carrier'],0))
        direction=-1 if pin_box[:,0].mean()<carrier_box[:,0].mean() else 1
        axial_gap=float(carrier_box[0,0]-pin_box[1,0]) if direction<0 else float(pin_box[0,0]-carrier_box[1,0])
        result.setdefault('released_lock_pin_engagement',[]).append({'station':prefix,'pin_bounds_mm':pin_box.tolist(),'carrier_atY0_bounds_mm':carrier_box.tolist(),
            'withdrawal_direction_x_sign':direction,'pin_carrier_axial_x_envelope_overlap_mm':max(0,float(overlap(pin_box,carrier_box)[0])),
            'released_axial_plane_gap_mm':axial_gap,
            'required_additional_shift_along_actual_withdrawal_direction_mm':max(0,-axial_gap),
            'scope':'Axial overlap alone is engagement risk, not material collision; firstYmotion Boolean receipts determine obstruction.'})
        for a,b in [(f'{prefix}_nut_carrier_link',f'{prefix}_manual_Y_screw'),
                    (f'{prefix}_nut_carrier_link',f'{prefix}_fixed_latch_clevis'),
                    (f'{prefix}_Y_drive_nut',f'{prefix}_fixed_latch_clevis'),
                    (f'{prefix}_cantilever',f'{prefix}_Y_endstop_78')]:
            row=check_pair(released,a,b,0,distance=True);result['priority_pairs'].append(row)
            print(json.dumps({'event':'priority_pair','data':row}),flush=True);save(result)
    # Only explicit functional moving/moving interfaces, not an indiscriminate self-test.
    for prefix in ['A','B']:
        for a,b,purpose in [(f'{prefix}_upper_jack',f'{prefix}_keeper_neck','UpperZsliding clearance'),
                            (f'{prefix}_upper_jack',f'{prefix}_cantilever','UpperZsliding clearance'),
                            (f'{prefix}_upper_guide_45',f'{prefix}_cantilever','UpperZsliding clearance'),
                            (f'{prefix}_carrier_neck',f'{prefix}_Y_carrier','Intended joined endpoint'),
                            (f'{prefix}_carrier_neck',f'{prefix}_cantilever','Intended joined endpoint'),
                            (f'{prefix}_keeper_neck',f'{prefix}_keeper_crossbar','Intended joined endpoint')]:
            row=check_pair(released,a,b,None,distance=True);row['purpose']=purpose
            result['same_moving_group_internal_checks'].append(row)
            print(json.dumps({'event':'functional_interface_pair','data':row}),flush=True);save(result)
        for a,b,purpose in [(f'{prefix}_Y_carrier',f'{prefix}_fixed_Y_rail','Square rail/slider clearance'),
                            (f'{prefix}_Y_drive_nut',f'{prefix}_manual_Y_screw','Threadless screw/nut bore geometry only'),
                            (f'{prefix}_upper_guide_45',f'{prefix}_keeper_crossbar','Upper guide/bore clearance'),
                            (f'{prefix}_upper_guide_-45',f'{prefix}_keeper_crossbar','Upper guide/bore clearance'),
                            (f'{prefix}_upper_jack',f'{prefix}_keeper_crossbar','Upper jack/bore clearance'),
                            (f'{prefix}_lower_guide_30',f'{prefix}_lower_bush_30','Lower guide/bush clearance'),
                            (f'{prefix}_lower_guide_-30',f'{prefix}_lower_bush_-30','Lower guide/bush clearance'),
                            (f'{prefix}_lower_jackscrew',f'{prefix}_lower_nut_block','Threadless lower jack/nut bore geometry only'),
                            (f'{prefix}_lock_pin',f'{prefix}_pin_captive_housing','Released pin/head captive housing clearance'),
                            (f'{prefix}_lock_pin',f'{prefix}_pin_endcap_-100','Released pin/head rear endcap clearance'),
                            (f'{prefix}_lock_pin',f'{prefix}_pin_endcap_-40','Released pin/front endcap bore clearance')]:
            row=check_pair(released,a,b,0 if is_moving(a) else None,distance=True);row['purpose']=purpose
            result['clearance_interface_checks'].append(row)
            print(json.dumps({'event':'clearance_interface','data':row}),flush=True)
        for y,bracket_y in [(0,110),(180,290)]:
            row=check_pair(released,f'{prefix}_carrier_flag',f'{prefix}_switch_bracket_{bracket_y}',y,distance=True)
            row['purpose']='Carrier flag to actual endstop-mounted switch bracket nominal clearance; bracket suffix110/290 is retained legacy label, not currentYcoordinate'
            result['clearance_interface_checks'].append(row)
        save(result)
    # Full cross-category pairing includes opposite-station parts. Internal same
    # moved-group construction contacts are excluded from this global sweep.
    for y in [0,90,180]:
        moved={name:at_y(released[name],y) for name in moving}
        boxes={name:bounds(shape) for name,shape in {**{n:released[n] for n in fixed},**moved}.items()}
        phase={'Y_mm':y,'upper_contact_retreat_mm':model.G['upper_pad_release_lift_mm'],
               'lower_shoe_retreat_mm':model.G['shoe_release_drop_mm'],'total_fixed_moving_pairs':len(moving)*len(fixed),
               'strictly_separated_aabb_pairs':0,'narrow_phase_pairs':[],'opposite_station_candidate_pairs':0}
        for m in moving:
            for f in fixed:
                delta=overlap(boxes[m],boxes[f])
                if np.any(delta < -BOX_TOL):phase['strictly_separated_aabb_pairs']+=1;continue
                record={'moving':m,'fixed':f,'aabb_axis_overlap_mm':delta.tolist(),
                        'opposite_station':bool(station(m) and station(f) and station(m)!=station(f))}
                record.update(common(moved[m],released[f]));phase['narrow_phase_pairs'].append(record)
                if record['opposite_station']:phase['opposite_station_candidate_pairs']+=1
                if record['status'] in ['POSITIVE_VOLUME_INTERSECTION','BOOLEAN_ERROR','BOOLEAN_NOT_DONE']:
                    print(json.dumps({'event':'sweep_finding','Y_mm':y,'data':record}),flush=True)
        phase['positive_volume_intersections']=[r for r in phase['narrow_phase_pairs'] if r['status']=='POSITIVE_VOLUME_INTERSECTION']
        phase['boolean_failures']=[r for r in phase['narrow_phase_pairs'] if r['status'] in ['BOOLEAN_ERROR','BOOLEAN_NOT_DONE']]
        result['sampled_cross_fixed_moving'].append(phase);save(result)
        print(json.dumps({'event':'phase_complete','Y_mm':y,'narrow_pairs':len(phase['narrow_phase_pairs']),
                          'positive_volume_pairs':len(phase['positive_volume_intersections']),'failures':len(phase['boolean_failures'])}),flush=True)
    # Deliberate joined fixture boundaries are reported separately.
    for prefix in ['A','B']:
        for a,b in [(f'{prefix}_overhead_offset_155',f'{prefix}_overhead_longitudinal'),
                    (f'{prefix}_rail_end_hanger_78',f'{prefix}_fixed_Y_rail'),
                    (f'{prefix}_rail_end_hanger_322',f'{prefix}_fixed_Y_rail')]:
            if a not in released or b not in released:
                result['fixed_join_checks'].append({'parts':[a,b],'status':'PART_NOT_PRESENT_IN_REVISED_SHARED_FRAME','not_a_check_pass':True});continue
            row=check_pair(released,a,b,None,distance=True);row['interpretation']='INTENDED_JOIN_OR_SUPPORT_CANDIDATE; fastener/weld detail not validated'
            result['fixed_join_checks'].append(row)
    for a in [n for n in released if n.startswith('M6_root_bolt_')]:
        candidates=[n for n in released if n.startswith('M6_root_nut_') and n.removeprefix('M6_root_nut_')==a.removeprefix('M6_root_bolt_')]
        for b in candidates:
            row=check_pair(released,a,b,None,distance=True);row['interpretation']='THREADLESS_ENVELOPE; material overlap/clearance is NOT thread engagement, preload or selected fastener evidence'
            result['root_thread_envelope_checks'].append(row)
    result['released_solid_validation']=validate_placed(released,receipt);save(result)
    _,held,held_unique,held_receipt=build_without_receipt_writes('held',include_context=True)
    context={name:shape for name,shape in held.items() if name.startswith('CONTEXT_')}
    engineering={name:shape for name,shape in held.items() if name not in context}
    result['held_solid_validation']=validate_placed(engineering,held_receipt)
    result['held_receipt_snapshot']=held_receipt
    hulls={name:shape for name,shape in context.items() if not name.startswith('CONTEXT_HARNESS_')}
    harness={name:shape for name,shape in context.items() if name.startswith('CONTEXT_HARNESS_')}
    result['context_hulls']={'status':'DISPLAY_HULL_VALIDITY_CHECK_SEPARATE_NO_CONTACT_AUTHORITY',
                             'validation':validate_placed(hulls,held_receipt),
                             'reason':'Two accepted-STL convex hulls, no imported arm BRep; hull validity is not contact geometry validity.'}
    result['context_harness_envelopes']={'status':'DISPLAY_HARNESS_ENVELOPE_VALIDITY_ONLY',
                                        'validation':validate_placed(harness,held_receipt),
                                        'reason':'Envelope validity does not validate outlet tangents, bend radius, strain, routing collision or real harness geometry.'}
    for prefix in ['A','B']:
        for b in [f'{prefix}_Y_carrier',f'{prefix}_pin_captive_housing',f'{prefix}_pin_endcap_-100',f'{prefix}_pin_endcap_-40']:
            row=check_pair(held,f'{prefix}_lock_pin',b,None,distance=True);row['state']='held';row['purpose']='Held captive pin interface geometry only'
            result['clearance_interface_checks'].append(row)
    result['status']='CHECK_COMPLETED_WITH_EXPLICIT_FINDINGS_NOT_ASSEMBLY_PASS'
    result['elapsed_seconds']=time.monotonic()-started;save(result)
    print(json.dumps({'event':'complete','status':result['status'],'solid_failures_released':result['released_solid_validation']['failing_occurrences'],
                      'solid_failures_held':result['held_solid_validation']['failing_occurrences'],'source_changed':result['source_changed_during_run']}),flush=True)

def supplement_flags_and_context():
    result=json.loads(OUTPUT.read_text(encoding='utf-8'))
    assert result['source_hashes_at_import']==SOURCE_HASHES, 'Functional/context source changed; a complete new run is required.'
    _,placed,_,_=build_without_receipt_writes('released')
    for prefix in ['A','B']:
        for y,bracket_y in [(0,110),(180,290)]:
            row=check_pair(placed,f'{prefix}_carrier_flag',f'{prefix}_switch_bracket_{bracket_y}',y,distance=True)
            row['purpose']='Carrier flag to active side switch bracket nominal clearance'
            result['clearance_interface_checks'].append(row);print(json.dumps(row),flush=True)
    old=result['context_hulls']['validation'];rows=old['rows']
    def subset(selected):
        return dict(old,rows=selected,occurrences=len(selected),solid_count=sum(r['solid_count'] for r in selected),
                    failing_occurrences=[r['instance'] for r in selected if not r['all_solids_valid_closed_positive']])
    result['context_hulls']['validation']=subset([r for r in rows if not r['instance'].startswith('CONTEXT_HARNESS_')])
    result['context_hulls']['reason']='Two accepted-STL convex hulls, no imported arm BRep; hull validity is not contact geometry validity.'
    result['context_harness_envelopes']={'status':'DISPLAY_HARNESS_ENVELOPE_VALIDITY_ONLY',
        'validation':subset([r for r in rows if r['instance'].startswith('CONTEXT_HARNESS_')]),
        'reason':'Envelope validity does not validate outlet tangents, bend radius, strain, routing collision or real harness geometry.'}
    result['script_sha256']=digest(Path(__file__));save(result)

if __name__=='__main__':
    supplement_flags_and_context() if '--supplement-flags-and-context' in sys.argv else main()
