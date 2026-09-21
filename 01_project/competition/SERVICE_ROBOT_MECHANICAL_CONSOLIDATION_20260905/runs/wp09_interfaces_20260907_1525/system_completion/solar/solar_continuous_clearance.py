"""Bounded continuous clearance certificate for SIX solar leaf/layer envelopes.

Single-joint WP03 deployment path. At each interval midpoint find an OBB
separating projection gap g. Each rotating body's all-point displacement is
bounded by R * half_angle; the interval is certified when g > sum(bounds)+margin.
Uncertified intervals bisect; sampled overlap and resolution exhaustion are
different outcomes. No CAD, hardware, force simulation or whole-spacecraft claim.
"""
from pathlib import Path
import hashlib
import importlib.util
import itertools
import json
import math
import time

C=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hinge',C/'solar/solar_hinge_delta.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
NUMERIC_GUARD_MM=1e-7
TARGET_CLEARANCE_MM=.30
MIN_INTERVAL_DEG=1e-4
MAX_NODES=200000
ORIGINAL_STAGES=[('ROOT_DEPLOY',0,0.,90.,[0.,0.,0.]),
        ('LEAF2_UNFOLD',1,0.,180.,[90.,0.,0.]),
        ('LEAF3_UNFOLD',2,0.,180.,[90.,180.,0.])]
STAGES=[('ROOT_DEPLOY',0,0.,90.,[0.,0.,0.]),
        ('LEAF2_PRE_UNFOLD',1,0.,150.,[90.,0.,0.]),
        ('LEAF3_UNFOLD_AT_H2_150',2,0.,180.,[90.,150.,0.]),
        ('LEAF2_FINISH',1,150.,180.,[90.,0.,180.])]


def configuration(joint,base,angle,step):
    q=list(base);q[joint]=angle
    rows=[r for s in (-1,1) for r in h.frames(s,q,step)]
    out=[]
    for r in rows:
        b=h.obb(r,extra_face_mm=.49,substrate_mm=2.6)
        # Independent absolute-position inflation conservatively covers <=0.1mm
        # error in each upstream offset. The actual correlated fold gap is 0.82mm;
        # leaf2/leaf3 independent inflation uses 0.1+0.2mm, giving 0.62mm here.
        u=(r['leaf']-1)*.10
        b['half'][1]+=u;b['half'][2]+=u
        out.append({'row':r,'obb':b,'active':r['leaf']>=joint+1,
                    'upstream_offset_uncertainty_inflation_mm':u})
    return out


def projection_gap(a,b):
    delta=h.sub(b['center'],a['center'])
    axes=a['axes']+b['axes']+[h.cross(x,y) for x in a['axes'] for y in b['axes']]
    best=-math.inf;best_axis=None
    for axis in axes:
        norm=math.sqrt(h.dot(axis,axis))
        if norm<1e-12:continue
        axis=[v/norm for v in axis]
        ra=sum(v*abs(h.dot(u,axis)) for v,u in zip(a['half'],a['axes']))
        rb=sum(v*abs(h.dot(u,axis)) for v,u in zip(b['half'],b['axes']))
        g=abs(h.dot(delta,axis))-ra-rb
        if g>best:best=g;best_axis=axis
    return best-NUMERIC_GUARD_MM,best_axis


def radius_from_axis(box,axis_point):
    radii=[]
    for sign in itertools.product((-1,1),repeat=3):
        p=[box['center'][i]+sum(sign[k]*box['half'][k]*box['axes'][k][i] for k in range(3)) for i in range(3)]
        # All joints rotate about X. X chord width does not contribute to radius.
        radii.append(math.hypot(p[1]-axis_point[1],p[2]-axis_point[2]))
    return max(radii)*(1+1e-12)+NUMERIC_GUARD_MM


def certify(step=4.5,max_depth=24,save_intervals=True,stages=STAGES):
    stage_out=[];total_nodes=0;failures=[];unknown=[]
    for label,joint,lo,hi,base in stages:
        mid=(lo+hi)/2
        bodies=configuration(joint,base,mid,step)
        axes={s:next(b['row']['root_S_mm'] for b in bodies if b['row']['side']==s and b['row']['leaf']==joint+1) for s in(-1,1)}
        radii={b['row']['id']:radius_from_axis(b['obb'],axes[b['row']['side']]) if b['active'] else 0 for b in bodies}
        # Check stated rigid-axis invariant against both ends as a numerical audit;
        # validity across the interval follows directly from source single-axis FK.
        endpoint_radii={}
        for a in (lo,hi):
            v=configuration(joint,base,a,step)
            endpoint_radii[str(a)]={b['row']['id']:radius_from_axis(b['obb'],axes[b['row']['side']]) if b['active'] else 0 for b in v}
            for b1,b2 in itertools.combinations(v,2):
                gap,axis=projection_gap(b1['obb'],b2['obb'])
                if gap< -NUMERIC_GUARD_MM:
                    failures.append({'stage':label,'angle_deg':a,'ids':[b1['row']['id'],b2['row']['id']],
                                     'largest_projection_gap_mm':gap,'classification':'POSITIVE_OVERLAP_OF_MODELED_CONSERVATIVE_ENVELOPES'})
        max_radius_error=max(abs(v[k]-radii[k]) for v in endpoint_radii.values() for k in radii)
        if max_radius_error>1e-8:raise RuntimeError('The assumed fixed-axis single-joint radius invariant did not hold')
        if failures:
            stage_out.append({'stage':label,'status':'MODELED_ENVELOPE_OVERLAP_AT_ENDPOINT','radii_mm':radii});break
        certified=[];stack=[(lo,hi,0)];nodes=0;invariant_pairs=set()
        min_cert=math.inf
        while stack:
            a,b,depth=stack.pop();nodes+=1;total_nodes+=1
            if total_nodes>MAX_NODES:
                unknown.append({'stage':label,'interval_deg':[a,b],'reason':'NODE_BUDGET'});break
            center=(a+b)/2;half_angle=math.radians((b-a)/2)
            bodies=configuration(joint,base,center,step)
            pair_results=[];sample_overlap=None
            for aa,bb in itertools.combinations(bodies,2):
                aid=aa['row']['id'];bid=bb['row']['id']
                gap,axis=projection_gap(aa['obb'],bb['obb'])
                if gap < -NUMERIC_GUARD_MM:
                    sample_overlap={'stage':label,'interval_deg':[a,b],'angle_deg':center,'ids':[aid,bid],
                                    'largest_projection_gap_mm':gap,'classification':'POSITIVE_OVERLAP_OF_MODELED_CONSERVATIVE_ENVELOPES'};break
                invariant=(not aa['active'] and not bb['active']) or (aa['active'] and bb['active'] and aa['row']['side']==bb['row']['side'])
                displacement=0 if invariant else (radii[aid]+radii[bid])*half_angle
                lower=gap-displacement
                pair_results.append({'ids':[aid,bid],'gap_mm':gap,'axis':axis,
                                     'displacement_bound_mm':displacement,'certified_gap_lower_mm':lower,
                                     'common_rigid_transform_invariant':invariant})
                if invariant:invariant_pairs.add((aid,bid))
            if sample_overlap:
                failures.append(sample_overlap);break
            limiting=min(pair_results,key=lambda x:x['certified_gap_lower_mm'])
            if limiting['certified_gap_lower_mm']>TARGET_CLEARANCE_MM:
                min_cert=min(min_cert,limiting['certified_gap_lower_mm'])
                if save_intervals:
                    certified.append({'interval_deg':[a,b],'mid_deg':center,'limiting_pair':limiting['ids'],
                        'midpoint_separating_axis':limiting['axis'],'midpoint_gap_lower_mm':limiting['gap_mm'],
                        'all_point_displacement_bound_sum_mm':limiting['displacement_bound_mm'],
                        'certified_min_gap_mm':limiting['certified_gap_lower_mm'],
                        'min_is_common_rigid_transform_invariant':limiting['common_rigid_transform_invariant']})
            elif b-a<=MIN_INTERVAL_DEG or depth>=max_depth:
                unknown.append({'stage':label,'interval_deg':[a,b],'limiting_pair':limiting,'reason':'MINIMUM_INTERVAL_OR_DEPTH'})
            else:
                stack.append((center,b,depth+1));stack.append((a,center,depth+1))
        intervals=sorted(certified,key=lambda x:x['interval_deg'][0])
        coverage=bool(intervals) and abs(intervals[0]['interval_deg'][0]-lo)<1e-12 and abs(intervals[-1]['interval_deg'][1]-hi)<1e-12 and all(abs(x['interval_deg'][1]-y['interval_deg'][0])<1e-12 for x,y in zip(intervals,intervals[1:]))
        stage_out.append({'stage':label,'joint_index_zero_based':joint,'joint_angles_deg_base':base,'interval_deg':[lo,hi],
            'status':'CERTIFIED_CONTINUOUS_GAP' if coverage and not failures and not unknown else 'UNKNOWN_OR_OVERLAP',
            'all_point_radius_upper_mm':radii,'radius_endpoint_consistency_error_mm':max_radius_error,
            'nodes':nodes,'certified_interval_count':len(intervals),'complete_interval_cover':coverage,
            'certified_gap_global_lower_mm':min_cert if math.isfinite(min_cert) else None,
            'common_rigid_pair_count':len(invariant_pairs),'certified_intervals':intervals})
        if failures:break
    success=len(stage_out)==len(stages) and all(s['status']=='CERTIFIED_CONTINUOUS_GAP' for s in stage_out) and not failures and not unknown
    return {'status':'CERTIFIED_CONTINUOUS_CLEARANCE_OF_SIX_LAYERED_RECTANGULAR_ENVELOPES' if success else 'MODELED_ENVELOPE_OVERLAP' if failures else 'UNKNOWN',
            'stack_step_mm':step,'success':success,'total_nodes':total_nodes,'stages':stage_out,
            'modeled_overlap_findings':failures,'unknown_intervals':unknown}


def main():
    started=time.perf_counter();good=certify();old=certify(step=3.0);coarse=certify(max_depth=0);original=certify(stages=ORIGINAL_STAGES)
    result={'identity':'SOLAR_CONTINUOUS_INTERVAL_CERTIFICATE_V1',**good,
        'method':{'scope':'Six substrate+full-face CIC/bond rectangular envelopes only, in prescribed staged single-joint path; no bodies outside this set.',
            'path':[{ 'stage':x[0],'joint_index_zero_based':x[1],'sweep_deg':[x[2],x[3]],'other_angles_deg':x[4]} for x in STAGES],
            'interval_rule':'At midpoint find a 15-axis OBB separation projection gap g. Fixed midpoint axis remains a valid separator across interval when g-(R_a+R_b)*half_angle >0.30mm; static/common-rigid pairs use exact distance invariance.',
            'point_displacement_bound':'Rigid rotation chord <= radius*angle; radius is maximum YZ distance of all inflated box corners to actual fixed X hinge axis; verified invariant at stage endpoints.',
            'substrate_upper_thickness_mm':2.60,'each_front_CIC_plus_bond_upper_mm':.49,
            'leaf_absolute_position_inflation_mm':{'leaf1':0,'leaf2':.10,'leaf3':.20},
            'required_continuous_gap_mm':TARGET_CLEARANCE_MM,'minimum_interval_deg':MIN_INTERVAL_DEG,
            'floating_point_projection_guard_mm':NUMERIC_GUARD_MM,
            'not_formal_real_arithmetic_proof':'Numerically guarded geometric certificate, independent of CAD kernel and physical qualification; not an interval-floating-point library proof.'},
        'negative_controls':[
            {'id':'OLD_STACK_3_0MM','detected':not old['success'] and bool(old['modeled_overlap_findings']),
             'verdict':old['status'],'first_finding':old['modeled_overlap_findings'][0] if old['modeled_overlap_findings'] else None},
            {'id':'MIDPOINT_ONLY_WITHOUT_BISECTION','detected':not coarse['success'] and bool(coarse['unknown_intervals']),
             'verdict':coarse['status'],'unknown_intervals':len(coarse['unknown_intervals'])},
            {'id':'ORIGINAL_THREE_STAGE_ORDER','detected':not original['success'] and bool(original['modeled_overlap_findings']),
             'verdict':original['status'],'first_finding':original['modeled_overlap_findings'][0] if original['modeled_overlap_findings'] else None}],
        'source_sha256':{str(Path(__file__)):h.sha(Path(__file__)),str(C/'solar/solar_hinge_delta.py'):h.sha(C/'solar/solar_hinge_delta.py'),str(h.SOURCE):h.sha(h.SOURCE)},
        'elapsed_s':time.perf_counter()-started,
        'excluded':['CIC formed tabs outside the0.49mm front layer','actual discrete wiring','edge frames and pins','spacecraft/arm/cover/camera/propulsion','attachment compliance/temperature/launch loads','other simultaneous or reordered joint paths'],
        'hardware_execution':False,'whole_spacecraft_G_status':'NOT_EVALUATED','manufacturing_release':False}
    path=C/'results/SOLAR_CONTINUOUS_CLEARANCE.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(path),'status':result['status'],'nodes':result['total_nodes'],
                      'intervals':{s['stage']:s.get('certified_interval_count',0) for s in result['stages']},
                      'gap_min_mm':min((s.get('certified_gap_global_lower_mm') or 1e9) for s in result['stages']),
                      'negative_controls':[x['detected'] for x in result['negative_controls']], 'elapsed_s':result['elapsed_s']}))
    return result


if __name__=='__main__':main()
