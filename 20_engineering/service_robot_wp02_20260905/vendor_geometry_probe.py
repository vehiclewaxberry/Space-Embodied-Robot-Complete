"""Small vendor STEP analytic-feature audit; does not edit any source geometry."""
from pathlib import Path
import hashlib
import itertools
import json
import math
import sys
import time
import numpy as np

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from cadgen.step_scene import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Cone
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

HERE = Path(__file__).resolve().parent
INPUT = HERE/'inputs/vendor_reference'
OUTPUT = HERE/'results/VENDOR_GEOMETRY_PROBE.json'
NAMES = ['VENDOR_01_BASE_Plate.step','VENDOR_01_BASE_Link.step',
         'VENDOR_02_Base_Reinforcement_Part.step','VENDOR_03_Link2.step','VENDOR_03-Link2.step']


def coord(p): return [p.X(),p.Y(),p.Z()]


def shape_bbox(shape):
    b=Bnd_Box();BRepBndLib.AddOptimal_s(shape,b,False,False)
    values=b.Get();return [list(values[:3]),list(values[3:])]


def member_shapes(shape,kind):
    rows=[];cursor=TopExp_Explorer(shape,kind)
    while cursor.More(): rows.append(cursor.Current());cursor.Next()
    return rows


def properties(shape,surface=False):
    p=GProp_GProps()
    (BRepGProp.SurfaceProperties_s if surface else BRepGProp.VolumeProperties_s)(shape,p)
    return p.Mass()


def read_one(path):
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    shape=import_step(path).wrapped
    solids=member_shapes(shape,TopAbs_SOLID)
    result=dict(path=str(path),bytes=path.stat().st_size,sha256_before=digest,
                bbox_mm=shape_bbox(shape),volume_mm3=properties(shape),solid_count=len(solids),
                solids=[dict(index=i,valid=BRepCheck_Analyzer(s).IsValid(),bbox_mm=shape_bbox(s),volume_mm3=properties(s)) for i,s in enumerate(solids)],
                cylinder_faces=[],plane_faces=[],cone_faces=[])
    for i,raw in enumerate(member_shapes(shape,TopAbs_FACE)):
        face=TopoDS.Face_s(raw);surface=BRepAdaptor_Surface(face,True);kind=surface.GetType()
        if kind not in [GeomAbs_Cylinder,GeomAbs_Plane,GeomAbs_Cone]:continue
        row=dict(face_index=i,bbox_mm=shape_bbox(face),area_mm2=properties(face,True),orientation=str(face.Orientation()))
        if kind==GeomAbs_Cylinder:
            cylinder=surface.Cylinder();axis=cylinder.Axis()
            row.update(radius_mm=cylinder.Radius(),diameter_mm=2*cylinder.Radius(),
                       axis_origin_mm=coord(axis.Location()),axis_direction=coord(axis.Direction()),
                       axial_v_interval_mm=[surface.FirstVParameter(),surface.LastVParameter()],
                       axial_surface_extent_mm=surface.LastVParameter()-surface.FirstVParameter(),
                       angular_u_interval_rad=[surface.FirstUParameter(),surface.LastUParameter()])
            result['cylinder_faces'].append(row)
        elif kind==GeomAbs_Plane:
            plane=surface.Plane()
            row.update(point_mm=coord(plane.Location()),normal=coord(plane.Axis().Direction()))
            result['plane_faces'].append(row)
        else:
            cone=surface.Cone()
            row.update(axis_origin_mm=coord(cone.Axis().Location()),axis_direction=coord(cone.Axis().Direction()),
                       reference_radius_mm=cone.RefRadius(),semi_angle_deg=math.degrees(cone.SemiAngle()))
            result['cone_faces'].append(row)
    result['sha256_after']=hashlib.sha256(path.read_bytes()).hexdigest()
    result['source_unchanged']=result['sha256_after']==digest
    return result


def unique_holes(record,radius):
    rows={}
    for face in record['cylinder_faces']:
        if abs(face['radius_mm']-radius)<1e-6 and abs(abs(face['axis_direction'][2])-1)<1e-9:
            key=tuple(round(x,8) for x in face['axis_origin_mm'][:2])
            rows.setdefault(key,dict(center_xy_mm=list(key),face_indices=[]))['face_indices'].append(face['face_index'])
    return list(rows.values())


def four_hole_fit(source,target):
    sh=unique_holes(source,2.3);th=unique_holes(target,2.3)
    if len(sh)!=4 or len(th)!=4:
        return dict(status='UNEXPECTED_HOLE_COUNT',source_holes=sh,target_holes=th)
    x=np.array([h['center_xy_mm'] for h in sh]);y=np.array([h['center_xy_mm'] for h in th])
    solutions=[]
    for permutation in itertools.permutations(range(4)):
        yp=y[list(permutation)]
        xc=x-x.mean(0);yc=yp-yp.mean(0)
        u,s,vt=np.linalg.svd(xc.T@yc)
        correction=np.diag([1.,np.linalg.det(vt.T@u.T)])
        r=vt.T@correction@u.T;t=yp.mean(0)-r@x.mean(0)
        predicted=x@r.T+t;residual=np.linalg.norm(predicted-yp,axis=1)
        solutions.append(dict(source_to_target_indices=list(permutation),rotation_rows=r.tolist(),
                              translation_xy_mm=t.tolist(),yaw_deg=math.degrees(math.atan2(r[1,0],r[0,0])),
                              determinant=float(np.linalg.det(r)),maximum_residual_mm=float(residual.max()),
                              rms_residual_mm=float(np.sqrt(np.mean(residual**2))),residual_vectors_mm=(predicted-yp).tolist()))
    best=min(s['rms_residual_mm'] for s in solutions)
    equivalent=[s for s in solutions if s['rms_residual_mm']<best+1e-7]
    chosen=min(equivalent,key=lambda s:abs(s['yaw_deg']))
    # This is a stated plane-registration convention, not the actual installed transform.
    transform=np.eye(4);transform[:2,:2]=chosen['rotation_rows'];transform[:2,3]=chosen['translation_xy_mm']
    transform[2,3]=2.405-(-1.3)
    return dict(status='PROPER_RIGID_FOUR_CYLINDER_AXIS_PATTERN_FIT',source_holes=sh,target_holes=th,
                source_pairwise_axis_distances_mm=sorted(float(np.linalg.norm(a-b)) for a,b in itertools.combinations(x,2)),
                target_pairwise_axis_distances_mm=sorted(float(np.linalg.norm(a-b)) for a,b in itertools.combinations(y,2)),
                selected=chosen,equivalent_solutions=equivalent,
                selection='MINIMUM_ABSOLUTE_YAW_AMONG_EQUAL_FITS; UNLABELLED_SQUARE_IS_90_DEG_AMBIGUOUS',
                mirrors_allowed=False,scale_allowed=False,
                conditional_plane_feature_transform_rows_mm=transform.tolist(),
                conditional_plane_feature_mapping='vendor BASE_Plate upper counterbore plane z=-1.3 -> existing M3R Stage A top z=2.405; parallel +Z plane normals retained',
                actual_vendor_assembly_to_accepted_URDF_root_transform=None,
                applicability='FEATURE_COORDINATE_REGISTRATION_ONLY_NOT_CONFIRMED_MATING_OR_AS_INSTALLED_CLOCKING')


def main():
    start=time.perf_counter();records=[]
    for name in NAMES:
        print('Reading',name,flush=True)
        record=read_one(INPUT/name);records.append(record)
        print(json.dumps(dict(name=name,bbox=record['bbox_mm'],solids=record['solid_count'],
                              invalid=sum(not s['valid'] for s in record['solids']),
                              radii=sorted(set(round(c['radius_mm'],6) for c in record['cylinder_faces'])))),flush=True)
    old_m3r=read_one(HERE.parent/'service_robot_wp01_20260905/inputs/m3r_a.step')
    fit=four_hole_fit(records[0],old_m3r)
    base=dict(plate_size_mm=[140.,200.,14.],thickness_from_parallel_plane_faces_mm=14.,
              plate_parallel_faces=[dict(face_index=p['face_index'],point_mm=p['point_mm'],normal=p['normal']) for p in records[0]['plane_faces'] if p['area_mm2']>10000],
              primary_pattern=dict(centers_xy_mm=[h['center_xy_mm'] for h in unique_holes(records[0],2.3)],
                                   square_pitch_mm=64.,pcd_mm=64*math.sqrt(2),clearance_diameter_mm=4.6,
                                   counterbore_diameter_mm=7.5,counterbore_depth_mm=4.5,remaining_small_bore_length_mm=9.5),
              secondary_pattern=dict(centers_xy_mm=[h['center_xy_mm'] for h in unique_holes(records[0],1.6)],
                                     clearance_diameter_mm=3.2,counterbore_diameter_mm=6.2,counterbore_depth_mm=3.5,
                                     locating_function=None,tolerance=None,statement='SMALL_COUNTERBORED_FASTENER_GEOMETRY; NOT_IDENTIFIED_AS_PRECISION_DOWEL_HOLES'),
              base_link_64mm_pattern_nominal_cylinder_diameter_mm=4.5,
              reinforcement_64mm_pattern_nominal_cylinder_diameter_mm=3.6,
              thread_form_or_engagement_authority=None,
              candidate_planar_datums=dict(BASE_Plate_z_mm=[-15.3,-1.3],BASE_Link_z_mm=[-61.2,.5],Base_Reinforcement_z_mm=[-68.2,-63.2,-61.25]),
              as_installed_bearing_plane=None,
              note='Plane stations belong to individual source coordinate systems; do not concatenate or equate to the old M3R physical stack without assembly registration')
    link2=dict(source_names=NAMES[-2:],candidate_shell_geometry=dict(nominal_parallel_face_wall_mm=3.,
                plus_side_outer_x_mm=32.875,plus_side_inner_x_mm=29.875,
                minus_side_outer_x_mm=-32.875,minus_side_inner_x_mm=-29.875,
                center_web_face_x_mm=[9.875,12.875,-9.875,-12.875],
                endpoint_circular_feature_axes_yz_mm=[[-20.,-93.],[244.,-93.]],
                end_aperture_radius_mm=19.,end_outer_arc_radius_mm=28.5,
                central_strip_y_mm=[64.90710678119,159.0928932188],central_strip_z_mm=[-118.5,-83.5]),
                two_load_bearing_regions_confirmed=False,allowable_contact_pressure=None,wall_strength=None,
                selected_saddle_to_vendor_registration=None,
                conclusion='Two end aperture/flange regions and paired three-mm nominal shell faces are geometrically identifiable. Neither two present saddle-contact patches nor their compression capacity are established.',
                variants_are_not_assumed_identical_mirror_copies=True)
    out=dict(units='mm_mm2_mm3',method='OCC_ANALYTIC_CYLINDER_PLANE_EXTRACTION_FROM_VENDOR_STEP',
             sources=records,old_M3R_reference=old_m3r,root_feature_dimensions=base,root_four_hole_registration=fit,
             link2_bearing_region_authority=link2,
             physical_measurement=False,
             changes_to_M3R=dict(hole_pitch_change_required_by_this_evidence=False,
                 four_hole_diameter_change_required_by_this_evidence=False,
                 current_installation_transform_proven=False,
                 full_part_interchangeability=False,
                 decision='KEEP_NOMINAL_64MM_MAIN_PATTERN_AS_A_CANDIDATE; VERIFY_CLOCKING_CENTERING_BEARING_FACE_AND_VENDOR_PART_ASSEMBLY_IDENTITY_BEFORE_MATING; NO_AUTOMATIC_CAD_CHANGE',
                 note='The downloaded 140x200x14 BASE_Plate is not the 150-diameter eight-mm M3R ring and must not silently replace it. The small hole pattern has no established locating fit.'),
             elapsed_s=time.perf_counter()-start,
             scope='SOURCE_NOMINAL_GEOMETRY_ONLY; NO_MATERIAL_THICKNESS_STRENGTH_OR_AS_BUILT_CLAIM')
    OUTPUT.write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(fit,indent=2),flush=True)


if __name__=='__main__':main()
