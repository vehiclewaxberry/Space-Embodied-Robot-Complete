"""Fixed-material-endpoint, fixed-arclength quadratic Bezier harness candidates.

This is a kinematic centerline construction, not a cable equilibrium solution.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import sys
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
WP01=HERE.parent/'service_robot_wp01_20260905'
spec=importlib.util.spec_from_file_location('harness_wp01_kinematics',WP01/'kinematics.py')
kin=importlib.util.module_from_spec(spec);spec.loader.exec_module(kin)
PARAMETERS=HERE/'design_parameters.json'
P=json.loads(PARAMETERS.read_text(encoding='utf-8'))
H=P['harness']
SAMPLES=sorted(set(np.linspace(0,1,21).tolist()+[.002,.005,.01,.02,.025]))
OUTPUT=HERE/'results/HARNESS_ANALYSIS.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def length_for_amplitude(distance,amplitude):
    if amplitude==0:return distance
    return .5*math.hypot(distance,2*amplitude)+distance**2/(4*amplitude)*math.asinh(2*amplitude/distance)


def partial_length(t,distance,amplitude):
    if amplitude==0:return distance*t
    k=2*amplitude
    def primitive(x):return .5*(x*math.hypot(distance,k*x)+distance**2/k*math.asinh(k*x/distance))
    return .5*(primitive(1)-primitive(1-2*t))


def angle_deg(a,b):
    return math.degrees(math.acos(float(np.clip(np.dot(a,b),-1,1))))


def centerline(p0,p2,free_length,rotations):
    delta=p2-p0;distance=float(np.linalg.norm(delta))
    row=dict(free_length_mm=free_length,endpoint_distance_mm=distance,
             straight_distance_slack_mm=free_length-distance,
             start_point_mm=p0.tolist(),end_point_mm=p2.tolist(),
             length_classification='CANDIDATE_EFFECTIVE_FREE_SPAN_NOT_OEM_ASSEMBLY_LENGTH',
             physical_bend_status='UNKNOWN_NO_DYNAMIC_RADIUS_AUTHORITY')
    if distance>free_length+1e-9:
        return dict(row,status='FAIL_ENDPOINT_DISTANCE_EXCEEDS_FIXED_FREE_LENGTH',centerline_points_mm=None)
    if distance<1e-9:
        return dict(row,status='FAIL_DEGENERATE_ZERO_CHORD',centerline_points_mm=None)
    chord=delta/distance
    negative_y=np.array([0.,-1.,0.])
    projected=negative_y-chord*np.dot(negative_y,chord)
    projection_norm=float(np.linalg.norm(projected))
    if projection_norm<1e-8:
        return dict(row,status='FAIL_NEGATIVE_Y_NORMAL_DEGENERATE',centerline_points_mm=None)
    normal=projected/projection_norm
    if abs(free_length-distance)<1e-9:amplitude=0.
    else:
        upper=free_length
        while length_for_amplitude(distance,upper)<free_length:upper*=2
        amplitude=brentq(lambda a:length_for_amplitude(distance,a)-free_length,0,upper,xtol=1e-12,rtol=1e-14)
    p1=(p0+p2)/2+amplitude*normal
    def point(t):return (1-t)**2*p0+2*t*(1-t)*p1+t*t*p2
    def derivative(t):return delta+2*amplitude*(1-2*t)*normal
    def points_at_material_fraction(count):
        fractions=np.linspace(0,1,count)
        parameters=[0.]+[brentq(lambda t:partial_length(t,distance,amplitude)-float(s)*free_length,0,1,xtol=1e-13) for s in fractions[1:-1]]+[1.]
        points=np.array([point(t) for t in parameters])
        residual=max(abs(partial_length(t,distance,amplitude)-s*free_length) for s,t in zip(fractions,parameters))
        return points.tolist(),parameters,residual
    points101,t101,material_error101=points_at_material_fraction(101)
    points61,t61,material_error61=points_at_material_fraction(61)
    extrema_parameters=[0.,1.]
    for axis in range(3):
        denom=p0[axis]-2*p1[axis]+p2[axis]
        if abs(denom)>1e-12:
            t=(p0[axis]-p1[axis])/denom
            if 0<t<1:extrema_parameters.append(t)
    extrema=np.array([point(t) for t in extrema_parameters]);minimum=extrema.min(0);maximum=extrema.max(0)
    radius=None if amplitude==0 else distance**2/(4*amplitude)
    tangents=[derivative(0)/np.linalg.norm(derivative(0)),-derivative(1)/np.linalg.norm(derivative(1))]
    local_tangents=[rotation.T@tangent for rotation,tangent in zip(rotations,tangents)]
    integrated,error_estimate=quad(lambda t:float(np.linalg.norm(derivative(t))),0,1,epsabs=1e-10,epsrel=1e-12)
    polygon=np.array(points101)
    polyline_length=float(np.linalg.norm(np.diff(polygon,axis=0),axis=1).sum())
    row.update(status='FIXED_LENGTH_CENTERLINE_CONSTRUCTED_ONLY',control_points_mm=[p0.tolist(),p1.tolist(),p2.tolist()],
               projected_negative_Y_normal=normal.tolist(),normal_projection_norm=projection_norm,
               amplitude_mm=amplitude,maximum_midpoint_bow_from_chord_mm=amplitude/2,
               calculated_length_mm=length_for_amplitude(distance,amplitude),length_error_mm=length_for_amplitude(distance,amplitude)-free_length,
               independent_quadrature_length_mm=integrated,quadrature_error_estimate_mm=error_estimate,
               independent_quadrature_minus_target_mm=integrated-free_length,
               centerline_points_mm=points101,centerline_points_61_mm=points61,
               bezier_t_at_101_material_fractions=t101,bezier_t_at_61_material_fractions=t61,
               maximum_material_arclength_error_mm=max(material_error101,material_error61),
               material_coordinate='101 points use s/L = i/100; 61 points use i/60, fixed material labels across poses',
               polyline101_length_mm=polyline_length,polyline101_minus_analytic_length_mm=polyline_length-free_length,
               min_curvature_radius_mm=radius,min_radius_at_bezier_t=None if amplitude==0 else .5,
               curvature_method='EXACT_QUADRATIC_CURVATURE_MAXIMUM: R_min=chord_length^2/(4*control_amplitude)',
               endpoint_tangents_away_from_anchors_S=[t.tolist() for t in tangents],
               endpoint_tangents_away_from_anchors_local=[t.tolist() for t in local_tangents],
               centerline_bbox_mm=[minimum.tolist(),maximum.tolist()],
               proxy_envelopes_by_OD_mm={str(od):dict(OD_mm=od,bbox_mm=[(minimum-od/2).tolist(),(maximum+od/2).tolist()],
                                                       min_centerline_radius_to_OD_ratio=None if radius is None else radius/od,
                                                       classification='CONSERVATIVE_SWEPT_RADIUS_AABB_OF_ASSUMED_CIRCULAR_OD_NOT_COLLISION_TEST') for od in H['proxy_OD_study_mm']},
               inferred_material_twist_deg=None,endpoint_force_N=None,friction_force_N=None,
               cable_equilibrium_verified=False,clamp_axis_tangent_compatibility=None)
    return row


def transformed_point(frame,local):return (frame@np.r_[local,1.])[:3]


def constant_curvature(p0,p2,free_length,rotations):
    delta=p2-p0;distance=float(np.linalg.norm(delta))
    if distance>free_length+1e-9 or distance<1e-9:
        return dict(status='FAIL_DISTANCE_INCOMPATIBLE_WITH_FIXED_LENGTH_CIRCULAR_ARC',centerline_points_mm=None)
    u=delta/distance;projected=np.array([0.,-1.,0.])-u*np.dot(np.array([0.,-1.,0.]),u)
    if np.linalg.norm(projected)<1e-8:
        return dict(status='FAIL_NEGATIVE_Y_NORMAL_DEGENERATE',centerline_points_mm=None)
    n=projected/np.linalg.norm(projected)
    theta=brentq(lambda t:2*math.sin(t/2)/t-distance/free_length,1e-8,2*math.pi-1e-8,xtol=1e-13,rtol=1e-14)
    radius=free_length/theta;half=theta/2;mid=(p0+p2)/2
    center=mid-n*radius*math.cos(half)
    def point(phi):return center+radius*(u*math.sin(phi)+n*math.cos(phi))
    def tangent(phi):return u*math.cos(phi)-n*math.sin(phi)
    phases101=np.linspace(-half,half,101);phases61=np.linspace(-half,half,61)
    points101=np.array([point(phi) for phi in phases101]);points61=np.array([point(phi) for phi in phases61])
    phases_for_extrema=[-half,half]
    for axis in range(3):
        initial=math.atan2(u[axis],n[axis])
        for k in range(-3,4):
            phi=initial+k*math.pi
            if -half<phi<half:phases_for_extrema.append(phi)
    extrema=np.array([point(phi) for phi in phases_for_extrema]);lo=extrema.min(0);hi=extrema.max(0)
    tangents=[tangent(-half),-tangent(half)]
    ab=points101[1]-points101[0];ac=points101[2]-points101[0];bc=points101[2]-points101[1]
    circumradius=float(np.linalg.norm(ab)*np.linalg.norm(ac)*np.linalg.norm(bc)/(2*np.linalg.norm(np.cross(ab,ac))))
    polyline_length=float(np.linalg.norm(np.diff(points101,axis=0),axis=1).sum())
    return dict(status='FIXED_LENGTH_CONSTANT_CURVATURE_CANDIDATE_ONLY',model='CONSTANT_CURVATURE_CIRCULAR_ARC',
                free_length_mm=free_length,endpoint_distance_mm=distance,
                arc_angle_rad=theta,arc_angle_deg=math.degrees(theta),major_arc=theta>math.pi,
                center_mm=center.tolist(),chord_unit=u.tolist(),normal_unit=n.tolist(),radius_mm=radius,
                min_curvature_radius_mm=radius,curvature_inverse_mm=1/radius,
                calculated_length_mm=radius*theta,length_error_mm=radius*theta-free_length,
                reconstructed_endpoint_distance_mm=2*radius*math.sin(half),
                endpoint_fit_error_mm=max(float(np.linalg.norm(points101[0]-p0)),float(np.linalg.norm(points101[-1]-p2))),
                centerline_points_mm=points101.tolist(),centerline_points_61_mm=points61.tolist(),
                material_coordinate='101 point i: phi=-theta/2+theta*i/100, s=L*i/100; fixed material labels across poses',
                centerline_bbox_mm=[lo.tolist(),hi.tolist()],
                polyline101_length_mm=polyline_length,polyline101_minus_analytic_length_mm=polyline_length-free_length,
                independently_reconstructed_radius_from_3_points_mm=circumradius,
                radius_3_point_residual_mm=circumradius-radius,
                endpoint_tangents_away_from_anchors_S=[t.tolist() for t in tangents],
                endpoint_tangents_away_from_anchors_local=[(r.T@t).tolist() for r,t in zip(rotations,tangents)],
                proxy_envelopes_by_OD_mm={str(od):dict(OD_mm=od,bbox_mm=[(lo-od/2).tolist(),(hi+od/2).tolist()],min_centerline_radius_to_OD_ratio=radius/od,
                                                        classification='CONSERVATIVE_RADIUS_PROXY_ENVELOPE_NOT_CONTACT_CHECK') for od in H['proxy_OD_study_mm']},
                connector_tangent_or_strain_relief_axes_bound=False,endpoint_tangent_lock=False,
                dynamic_bend_status='UNKNOWN_NO_OEM_DYNAMIC_LIMIT',material_twist_deg=None,
                cable_equilibrium_verified=False,contact_collision_status='NOT_EVALUATED')


def main():
    paths=[PARAMETERS,WP01/'kinematics.py',kin.URDF,
           HERE/'inputs/vendor_reference/B601_DM_BOM_readme.md',
           HERE/'inputs/vendor_reference/VENDOR_DM_Motor1_wiring_harness_clip.stp']
    pins={str(p):sha(p) for p in paths}
    root=np.array(P['T_S_A0'],float)
    poses=[];initial={}
    q0=np.array(P['q_parking_deg'],float);q1=np.array(P['q_work_deg'],float)
    for i,fraction in enumerate(SAMPLES):
        q=q0+fraction*(q1-q0);frames=kin.fk(q,root,P['finger_mm'])
        definitions={
            'root_service_loop':(np.array(H['root_fixed_anchor_S_mm'],float),np.array(H['root_port_proxy_S_mm'],float),float(H['root_service_loop_effective_length_mm']),[np.eye(3),np.eye(3)]),
            'joint2_loop':(transformed_point(frames['link1'],H['joint2_proximal_anchor_link1_mm']),transformed_point(frames['link2'],H['joint2_distal_anchor_link2_mm']),float(H['joint2_effective_length_mm']),[frames['link1'][:3,:3],frames['link2'][:3,:3]])}
        rows={key:centerline(*definition) for key,definition in definitions.items()}
        for key,row in rows.items():
            row['constant_curvature_candidate']=constant_curvature(*definitions[key])
            row['selected_model']='constant_curvature_candidate'
            row['quadratic_bezier_disposition']='REJECTED_GEOMETRY_CONCENTRATION_RETAINED_AS_COUNTEREXAMPLE'
            if row['centerline_points_mm'] is None:continue
            if key not in initial:initial[key]=row
            for coordinate in ['S','local']:
                name='endpoint_tangents_away_from_anchors_'+coordinate
                row['endpoint_tangent_change_from_parking_'+coordinate+'_deg']=[angle_deg(a,b) for a,b in zip(row[name],initial[key][name])]
                circular=row['constant_curvature_candidate'];base_circular=initial[key]['constant_curvature_candidate']
                if circular['centerline_points_mm'] is not None:
                    circular['endpoint_tangent_change_from_parking_'+coordinate+'_deg']=[angle_deg(a,b) for a,b in zip(circular[name],base_circular[name])]
        poses.append(dict(index=i,path_fraction=fraction,q_deg=q.tolist(),finger_mm=P['finger_mm'],loops=rows))
    summaries={}
    for key in ['root_service_loop','joint2_loop']:
        valid=[p for p in poses if p['loops'][key]['centerline_points_mm'] is not None]
        failed=[dict(index=p['index'],fraction=p['path_fraction'],status=p['loops'][key]['status']) for p in poses if p['loops'][key]['centerline_points_mm'] is None]
        data=[p['loops'][key] for p in valid]
        finite_radii=[r['min_curvature_radius_mm'] for r in data if r['min_curvature_radius_mm'] is not None]
        bounds=np.array([r['centerline_bbox_mm'] for r in data]) if data else None
        summaries[key]=dict(constructed_pose_count=len(valid),failed_poses=failed,
                            global_min_curvature_radius_mm=min((r['min_curvature_radius_mm'] for r in data if r['min_curvature_radius_mm'] is not None),default=None),
                            radius_range_mm=[min(finite_radii),max(finite_radii)] if finite_radii else None,
                            endpoint_distance_range_mm=[min(r['endpoint_distance_mm'] for r in data),max(r['endpoint_distance_mm'] for r in data)] if data else None,
                            max_abs_length_error_mm=max((abs(r['length_error_mm']) for r in data),default=None),
                            max_abs_quadrature_error_mm=max((abs(r['independent_quadrature_minus_target_mm']) for r in data),default=None),
                            max_endpoint_local_tangent_change_deg=[max(r['endpoint_tangent_change_from_parking_local_deg'][i] for r in data) for i in range(2)] if data else None,
                            sampled_centerline_union_bbox_mm=None if bounds is None else [bounds[:,0].min(0).tolist(),bounds[:,1].max(0).tolist()],
                            bending_status='UNKNOWN_NO_REAL_OD_OR_DYNAMIC_BEND_LIMIT',
                            twist_status='UNKNOWN_NO_MATERIAL_DIRECTOR_OR_TORSION_LIMIT',
                            contact_collision_status='NOT_EVALUATED',
                            root_loop_caveat='BOTH_ROOT_ANCHORS_ARE_FIXED_IN_S; IDENTICAL_ROOT_CURVES_DO_NOT_VALIDATE_JOINT_HARNESS' if key=='root_service_loop' else None)
        circles=[r['constant_curvature_candidate'] for r in data if r['constant_curvature_candidate']['centerline_points_mm'] is not None]
        cbounds=np.array([r['centerline_bbox_mm'] for r in circles])
        summaries[key]['selected_model']='constant_curvature_candidate'
        summaries[key]['constant_curvature_candidate']=dict(constructed_pose_count=len(circles),radius_range_mm=[min(r['radius_mm'] for r in circles),max(r['radius_mm'] for r in circles)],
            major_arc_pose_count=sum(r['major_arc'] for r in circles),arc_angle_range_deg=[min(r['arc_angle_deg'] for r in circles),max(r['arc_angle_deg'] for r in circles)],
            max_endpoint_fit_error_mm=max(r['endpoint_fit_error_mm'] for r in circles),
            max_length_error_mm=max(abs(r['length_error_mm']) for r in circles),
            max_endpoint_local_tangent_change_deg=[max(r['endpoint_tangent_change_from_parking_local_deg'][i] for r in circles) for i in range(2)],
            sampled_centerline_union_bbox_mm=[cbounds[:,0].min(0).tolist(),cbounds[:,1].max(0).tolist()],
            minimum_radius_improvement_factor_over_bezier=min(r['radius_mm'] for r in circles)/min(finite_radii),
            interpretation='GEOMETRIC_CURVATURE_REDISTRIBUTION_ONLY; SAME_ANCHORS_SAME_LENGTH; NO_CONNECTOR_TANGENT_LOCK_OR_PHYSICAL_BEND_APPROVAL')
    overstretch=centerline(np.array([0.,0.,0.]),np.array([200.,0.,0.]),180.,[np.eye(3),np.eye(3)])
    parallel=centerline(np.array([0.,0.,0.]),np.array([0.,-100.,0.]),180.,[np.eye(3),np.eye(3)])
    negative_controls=dict(overlength_endpoint_case_status=overstretch['status'],
                           overlength_case_did_not_generate_or_stretch=overstretch['centerline_points_mm'] is None and overstretch['free_length_mm']==180.,
                           parallel_negative_Y_chord_status=parallel['status'],
                           degenerate_normal_not_silently_reoriented=parallel['centerline_points_mm'] is None)
    after={str(p):sha(p) for p in paths}
    out=dict(schema='WP02_HARNESS_FIXED_LENGTH_CENTERLINE_V2',units=dict(length='mm',joint_angles='deg',tangent_change='deg'),
             selected_model='constant_curvature_candidate',
             CAD_read_path='poses[i].loops[loop_name].constant_curvature_candidate.centerline_points_mm',
             quadratic_bezier_disposition='REJECTED_GEOMETRY_CONCENTRATION_RETAINED_AS_COUNTEREXAMPLE_AT_EXISTING_LOOP_FIELDS',
             circular_arc_construction='Solve d/L=2*sin(theta/2)/theta for 0<theta<2*pi; R=L/theta; center=mid-n*R*cos(theta/2); point=center+R*(u*sin(phi)+n*cos(phi)); phi=-theta/2+theta*s/L',
             construction='quadratic B(t)=(1-t)^2*p0+2*t*(1-t)*p1+t^2*p2; p1=(p0+p2)/2+A*project(-S.Y onto chord-normal plane); positive A solves fixed analytic arc length by brentq',
             pose_sampling_rule='21 uniform path fractions plus 0.002,0.005,0.01,0.02,0.025; path fraction is not time',
             pose_count=len(poses),poses=poses,summary=summaries,
             material_anchor_definitions=dict(root_fixed=dict(frame='S',point_mm=H['root_fixed_anchor_S_mm']),root_port_proxy=dict(frame='S',point_mm=H['root_port_proxy_S_mm']),
                                              joint2_proximal=dict(frame='link1',point_mm=H['joint2_proximal_anchor_link1_mm']),joint2_distal=dict(frame='link2',point_mm=H['joint2_distal_anchor_link2_mm'])),
             effective_free_lengths_mm=dict(root_service_loop=H['root_service_loop_effective_length_mm'],joint2_loop=H['joint2_effective_length_mm']),
             actual_free_lengths_measured_mm=None,
             OEM_reference=dict(connector_family='XT30 2+2',assembly_lengths_mm=[200,350],free_span_authority=False,
                                notes='OEM lengths are end-to-end harness assembly lengths; connector tails and clamp capture lengths not known. No free length derived by subtracting guessed tails.',
                                clip_STEP=str(paths[-1]),clip_scope='OEM_MOTOR1_RESTRAINT_REFERENCE_NOT_VERIFIED_DYNAMIC_JOINT2_CLAMP',
                                vendor_commit=H['vendor_commit']),
             real_outer_diameter_mm=None,dynamic_minimum_bend_radius_mm=None,allowed_twist_deg_per_m=None,
             prescribed_connector_tangent_axes=None,endpoint_loads_N=None,friction_properties=None,
             positive_Y_release_corridor_claim='DESIGN_INTENT_SEPARATE_FROM_NEGATIVE_Y_ROOT_CLAMP; FULL_3D_PROXY_OR_CABLE_CONTACT_NOT_CHECKED',
             unmodelled=['joint3_to_wrist','gripper_internal_wiring','solar_wing_hinges','continuous_pose_swept_volume','cable_elastic_equilibrium','clamp_tail_local_bend','material_twist','torsional_strain','connector_pullout_force','friction_and_abrasion','thermal_vacuum_and_cycle_life'],
             source_hashes_before=pins,source_hashes_after=after,sources_unchanged=pins==after,
             negative_controls=negative_controls,
             scope='GEOMETRIC_FIXED_LENGTH_FAMILY_ONLY; NO_HARNESS_BENDING_PASS_NO_SYSTEM_PASS')
    OUTPUT.write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(summaries,indent=2))


if __name__=='__main__':main()
