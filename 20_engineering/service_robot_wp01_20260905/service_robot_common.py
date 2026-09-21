"""WP01 reproducible assembly; positions are mm and all joint angles are degrees.

Imported nominal BRep is kept intact. Functional equipment/line volumes are
labelled envelopes. This code does not imply physical fit, flight mass or strength.
"""
from pathlib import Path
import csv, json, math
import numpy as np
from scipy.spatial.transform import Rotation
from OCP.gp import gp_Trsf
from build123d import Box, Cylinder, Compound, Color, Location, Vector, Plane
from cadgen.assembly import AssemblyHelper
from cadgen.step_scene import import_step
from kinematics import fk, tf, place, raw_vertices, TREE

HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'design_parameters.json').read_text(encoding='utf-8'))
SILVER=Color(0.70,0.76,0.82); GOLD=Color(0.80,0.58,0.22)
DARK=Color(0.16,0.20,0.25); BLUE=Color(0.06,0.17,0.43)
ORANGE=Color(0.95,0.34,0.08); TEAL=Color(0.13,0.55,0.51)

def loc(t):
    # Transfer the homogeneous matrix directly. build123d defaults to intrinsic
    # XYZ, whereas scipy lower-case xyz uses extrinsic rotations.
    transform=gp_Trsf();transform.SetValues(*np.asarray(t)[:3,:4].ravel().tolist())
    result=Location(transform)
    actual=np.array([[result.wrapped.Transformation().Value(i,j) for j in range(1,5)] for i in range(1,4)])
    if not np.allclose(actual,np.asarray(t)[:3,:4],rtol=0,atol=1e-12):raise ValueError('CAD/FK matrix roundtrip mismatch')
    return result

def centered_box(size,center):return Box(*size).moved(Location(tuple(center)))

def tube_x(length,outer,wall):
    return Box(length,outer,outer)-Box(length+2,outer-2*wall,outer-2*wall)

def tube_z(length,outer,wall):
    return Box(outer,outer,length)-Box(outer-2*wall,outer-2*wall,length+2)

def round_between(a,b,r):
    a=np.array(a,float);b=np.array(b,float);delta=b-a
    return Cylinder(r,float(np.linalg.norm(delta))).moved(Plane(origin=tuple((a+b)/2),z_dir=tuple(delta)).location)

def box_record(shape):
    b=shape.bounding_box();return dict(min_mm=list(b.min),max_mm=list(b.max),size_mm=list(b.size))

def build(state,structure_only=False):
    p=P; L,W,H=p['bus_mm']; top=H/2; e=p['end_frame_thickness_mm']; rail=p['longeron_outer_mm']
    # Nominal BRep bearing surface is local z=2.405, not the frame origin.
    root=np.array([*p['root_xy_mm'],top+p['m3r_B_thickness_mm']])
    root_t=tf(root,np.deg2rad(p['root_rotation_rpy_deg']))
    q=p['states'][state]['q_deg'];frames=fk(q,root_t,p['states'][state]['finger_mm'])
    asm=AssemblyHelper('WP01_'+state); records=[]; parts={}
    def add(shape,name,group,color=SILVER,kind='NEW_CANDIDATE_METAL',mass=None):
        obj=asm.add(shape,name,color=color);parts[name]=obj
        volume=sum(x.volume for x in obj.solids())
        if mass is None and kind in ('NEW_CANDIDATE_METAL','IMPORTED_M3R_METAL'):mass=volume*p['candidate_aluminum_density_kg_mm3']
        records.append(dict(part=name,group=group,representation=kind,solids=len(obj.solids()),volume_mm3=volume,mass_kg=mass,mass_basis=('CAD_VOLUME_CANDIDATE_DENSITY' if kind in ('NEW_CANDIDATE_METAL','IMPORTED_M3R_METAL') else 'SOURCE_OR_BUDGET_NOT_MEASURED' if mass is not None else 'UNKNOWN'),**box_record(obj)))
        return obj

    # Open serviceable frame. Separate parts share faces, never fuse entire spacecraft.
    for sy in (-1,1):
        for sz in (-1,1):
            add(tube_x(L-2*e,rail,p['longeron_wall_mm']).moved(Location((0,sy*(W-rail)/2,sz*(H-rail)/2))),f'longeron_y{sy}_z{sz}','frame')
    for sx in (-1,1):
        frame=Box(e,W,H)-Box(e+2,W-2*rail,H-2*rail)
        add(frame.moved(Location((sx*(L-e)/2,0,0))),f'end_frame_{sx}','frame')
    decksize=(L-2*e,W-2*rail,p['deck_thickness_mm'])
    add(centered_box(decksize,(0,0,-H/2+rail+p['deck_thickness_mm']/2)),'lower_equipment_deck','frame')
    # Cutouts reserve access to the vertical root pillars, not modelled as bonded plates.
    mid=Box(*decksize)
    for x in (root[0]-70,root[0]+70):
        for y in (-94.15,94.15):mid=mid-centered_box((16,16,8),(x,y,0))
    add(mid.moved(Location((0,0,-10))),'upper_equipment_deck','frame')
    rootplate=Box(170,W-2*rail,p['root_bearing_plate_thickness_mm'])
    for x in (-70,70):
        for y in (-70,70):rootplate=rootplate-Cylinder(3.3,12).moved(Location((x,y,0)))
    rootplate=rootplate-Cylinder(22,12)
    bearing=add(rootplate.moved(Location((root[0],0,top-3))),'root_load_plate','root',GOLD)
    for x in (root[0]-70,root[0]+70):
        beam=Box(14,W-2*rail,12)
        for y in (-70,70):beam=beam-Cylinder(3.3,16).moved(Location((0,y,0)))
        add(beam.moved(Location((x,0,top-12))),f'root_upper_crossbeam_x{x:g}','root',GOLD)
        add(centered_box((14,W-2*rail,6),(x,0,-H/2+9)),f'root_lower_crossbeam_x{x:g}','root',GOLD)
        lo=-H/2+rail+3; hi=top-18
        for sy in (-1,1):
            add(tube_z(hi-lo,14,2).moved(Location((x,sy*94.15,(lo+hi)/2))),f'root_pillar_x{x:g}_y{sy}','root',GOLD)

    # Both original M3R stages share their local origin. A seats in B's pocket.
    m3r_t=tf((root[0],0,top+p['m3r_B_thickness_mm']))
    a=add(import_step(HERE/'inputs/m3r_a.step').moved(loc(m3r_t)),'M3R_stage_A','root',GOLD,'IMPORTED_M3R_METAL')
    b=add(import_step(HERE/'inputs/m3r_b.step').moved(loc(m3r_t)),'M3R_stage_B','root',GOLD,'IMPORTED_M3R_METAL')
    asm.rigid_frame(b,'bus_contact',Location((0,0,-12)))
    asm.rigid_frame(a,'arm_contact',Location((0,0,2.405)))
    if structure_only:
        model=asm.build();out=HERE/'results';out.mkdir(exist_ok=True)
        (out/'structure_build_receipt.json').write_text(json.dumps(dict(configuration=p['configuration_id'],parts=records,assembly_bounds=box_record(model),solid_count=sum(r['solids'] for r in records),mass_estimate_kg=sum(r['mass_kg'] or 0 for r in records),mass_basis='NEW_GEOMETRY_VOLUME_TIMES_ASSUMED_AL_DENSITY',T_S_arm_base=root_t.tolist(),T_S_m3r_local=m3r_t.tolist(),loads_verified=False),indent=2),encoding='utf-8')
        return model
    # Placement is driven by the matrices in the receipt, not invented STEP mates.
    arm_mass={l.get('name'):float(l.find('inertial/mass').get('value')) for l in TREE.findall('link')}
    arm=[]
    for name,t in frames.items():
        print('Loading arm BRep: '+name,flush=True)
        shape=import_step(HERE/'inputs'/f'{name}.step').moved(loc(t))
        obj=add(shape,'B601_'+name,'arm',SILVER if name in ('link2','link3','gripper_left','gripper_right') else DARK,'IMPORTED_NOMINAL_BREP',arm_mass[name]);arm.append(obj)

    # Stow cradle stations derive from the accepted link2 cross-section at fixed S.x.
    # Two millimetre setup allowance remains, so these are not claimed load contacts.
    stowframes=fk(p['states']['stowed']['q_deg'],root_t)
    cloud=place(raw_vertices()['link2'],stowframes['link2']); support_rows=[]
    for i,x in enumerate(p['support_station_x_mm'],1):
        section=cloud[np.abs(cloud[:,0]-x)<p['support_section_half_width_mm']]
        lower=float(section[:,2].min())-p['support_mesh_clearance_mm']; upper=float(section[:,2].max())+p['support_mesh_clearance_mm']
        support_rows.append(dict(station=i,x_mm=x,source='accepted_link2_mesh_section',section_z_mm=[float(section[:,2].min()),float(section[:,2].max())],pad_top_z_mm=lower,retainer_bottom_z_mm=upper,setup_gap_mm=p['support_mesh_clearance_mm'],load_contact_status='NOT_CLOSED_SETUP_ALLOWANCE'))
        add(centered_box((18,W-2*rail,6),(x,0,top-3)),f'cradle_crossrail_{i}','stow_support',GOLD)
        for sy in (-1,1):
            height=upper-top
            add(centered_box((10,10,height),(x,sy*52,top+height/2)),f'cradle_post_{i}_{sy}','stow_support',GOLD)
        add(centered_box((14,94,6),(x,0,lower-3)),f'cradle_saddle_{i}','stow_support',TEAL)
        slide=p['states'][state]['retainer_slide_mm']
        add(centered_box((18,118,6),(x,slide,upper+3)),f'retainer_{i}','stow_support',ORANGE)
        # Motion drive support is a functional volume until stroke/force are selected.
        add(centered_box((24,170,16),(x,139,upper+10)),f'release_drive_envelope_{i}','mechanism',ORANGE,'FUNCTIONAL_ENVELOPE')

    for eq in p['equipment']:
        add(centered_box(eq['size_mm'],eq['center_mm']),'equipment_'+eq['name'],'equipment',TEAL,'EQUIPMENT_ENVELOPE',eq['budget_mass_kg'])

    # Two fold-out wings. This is new area/hinge allocation, not a qualified solar array.
    pl,pw,pt=p['solar_panel_mm']; y0=W/2+p['solar_side_gap_mm']; z0=p['solar_hinge_z_mm']
    angle=p['states'][state]['solar_angle_deg']
    for side in (-1,1):
        wing_t=tf((0,side*y0,z0),(-side*math.radians(angle),0,0))
        substrate=Box(pl,pt,pw).moved(Location((0,side*pt/2,pw/2))).moved(loc(wing_t))
        add(substrate,f'wing_substrate_{side}','solar',SILVER,'COMPOSITE_PANEL_ENVELOPE',0.4)
        for ix in range(8):
            for iz in range(4):
                cell=Box((pl-18)/8-2,0.5,(pw-14)/4-2).moved(Location((-pl/2+9+(ix+.5)*(pl-18)/8,side*(pt+.25),7+(iz+.5)*(pw-14)/4))).moved(loc(wing_t))
                add(cell,f'solar_cell_visual_{side}_{ix}_{iz}','solar',BLUE,'VISUAL_ONLY_NO_MASS')
        for x in (-120,120):
            add(Cylinder(8,16,rotation=(0,90,0)).moved(Location((x,side*y0,z0))),f'wing_hinge_{side}_{x}','solar',GOLD,'HINGE_ENVELOPE')
            add(centered_box((22,18,12),(x,side*(W/2+3),z0)),f'wing_bracket_{side}_{x}','solar',GOLD)

    # Sensor allocation and fixed trunk are intentionally separate from true parts.
    add(centered_box((35,42,36),(L/2+18,-72,62)),'body_camera_envelope','sensing',DARK,'SENSOR_ENVELOPE',0.15)
    add(Cylinder(10,6,rotation=(0,90,0)).moved(Location((L/2+38,-72,62))),'camera_lens_visual','sensing',BLUE,'VISUAL_ONLY_NO_MASS')
    camera_bracket=Box(4,50,44)-Box(6,30,24)
    add(camera_bracket.moved(Location((L/2+2,-72,62))),'body_camera_bracket','sensing',GOLD)
    trunk=[(-160,87,48),(90,87,48),(90,120,95),(90,120,150)]
    for i,(start,end) in enumerate(zip(trunk[:-1],trunk[1:]),1):add(round_between(start,end,3),f'harness_route_envelope_{i}','harness',ORANGE,'ROUTING_ENVELOPE')
    # The gripper origin is not its bearing surface. Its negative local X brings
    # the palm back toward link6 through the fixed Ry(-90) transform. Do not
    # invent a wrist spacer just from the 159.71 mm joint-origin translation.

    model=asm.build();out=HERE/'results';out.mkdir(exist_ok=True)
    receipt=dict(configuration=p['configuration_id'],state=state,bus_mm=p['bus_mm'],T_S_arm_base=root_t.tolist(),T_S_m3r_local=m3r_t.tolist(),link_transforms={k:v.tolist() for k,v in frames.items()},q_deg=q,assembly_bounds=box_record(model),part_count=len(records),solid_count=sum(r['solids'] for r in records),parts=records,supports=support_rows,arm_digital_mass_kg=sum(arm_mass.values()),allocated_mass_subtotal_kg=sum(r['mass_kg'] or 0 for r in records),unallocated_mass_parts=[r['part'] for r in records if r['mass_kg'] is None and r['representation']!='VISUAL_ONLY_NO_MASS'],mass_complete=False,representation_warning=p['geometry_policy'])
    (out/f'{state}_build_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    with (out/f'{state}_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
        keys=['part','group','representation','solids','volume_mm3','mass_kg','mass_basis'];w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(records)
    return model
