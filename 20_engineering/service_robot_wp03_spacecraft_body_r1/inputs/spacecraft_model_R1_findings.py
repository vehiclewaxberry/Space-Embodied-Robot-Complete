"""WP03 whole-spacecraft candidate. Explicit products, sources and mass owners.

No original geometry, hardware, environment or research gate is modified.
"""
from pathlib import Path
import sys,json,csv,math,hashlib,functools
import numpy as np
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from build123d import Box,Cylinder,Compound,Color,Location,Plane,Wire,Face,Solid,Shell,export_step
from OCP.gp import gp_Trsf
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
from kinematics import fk,tf,TREE
from root_structure import build_root
HERE=Path(__file__).resolve().parent
W1=HERE.parent/'service_robot_wp01_20260905';W2=HERE.parent/'service_robot_wp02_20260905'
P=json.loads((HERE/'design_parameters.json').read_text(encoding='utf-8'))
CONTACT=json.loads((W2/'results/CONTACT_REGISTRATION.json').read_text(encoding='utf-8'))
SILVER=Color(.69,.75,.8);DARK=Color(.16,.2,.25);GOLD=Color(.76,.56,.22)
BLUE=Color(.06,.15,.36);TEAL=Color(.08,.48,.44);ORANGE=Color(.85,.32,.08)

def loc(T):
    tr=gp_Trsf();tr.SetValues(*np.asarray(T)[:3,:4].ravel().tolist());return Location(tr)
def box(size,c=(0,0,0)):return Box(*size).moved(Location(tuple(c)))
def cylinder(d,h,c=(0,0,0),axis=(0,0,1)):
    return Cylinder(d/2,h).moved(Plane(origin=tuple(c),z_dir=axis).location)
def bore(s,d,h,c=(0,0,0),axis=(0,0,1)):return s-cylinder(d,h,c,axis)
def plate(size,holes=()):
    s=Box(*size)
    for x,y,d in holes:s=bore(s,d,size[2]+2,(x,y,0))
    return s
def ring(od,idd,h):return cylinder(od,h)-cylinder(idd,h+2)
def rod(a,b,d):
    a=np.asarray(a);b=np.asarray(b);return cylinder(d,np.linalg.norm(b-a),(a+b)/2,b-a)
def bounds(s):
    b=s.bounding_box();return {'min_mm':list(b.min),'max_mm':list(b.max),'size_mm':list(b.size)}
def props(s,mass=None,density=None):
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s.wrapped,g)
    v=g.Mass();c=g.CentreOfMass();a=g.MatrixOfInertia()
    rho=density if density is not None else mass/v if mass is not None and v>0 else None
    return v,[c.X(),c.Y(),c.Z()],None if rho is None else [[a.Value(i,j)*rho for j in range(1,4)] for i in range(1,4)],v*rho if rho is not None else None
@functools.lru_cache(maxsize=10)
def arm_shape(name):
    print('Nominal arm input '+name,file=sys.stderr,flush=True)
    return import_step(W1/'inputs'/f'{name}.step')

def build(state='service',view='complete',include_arm=True,write_parts=False):
    cfg=P['states'][state];root=tf((90,0,125.15));frames=fk(cfg['q_deg'],root,cfg['finger_mm'])
    asm=AssemblyHelper('SERVICER_ONBOARD_CANDIDATE'); records=[];shapes={};local_parts={};interfaces=[]
    def add(s,name,pn=None,parent='PRIMARY_STRUCTURE',mount='FRAME_LONGERONS',role='ONBOARD_CANDIDATE',rep='PHYSICAL_GEOMETRY',
            mass=None,mass_source=None,density=2.7e-6,color=SILVER,source='WP03_PARAMETRIC_DESIGN',T=None,arm_link=None,motion_group='fixed',mass_owner=None,basis=None):
        if T is None:T=np.eye(4)
        world=s.moved(loc(T));pn=pn or 'WP03_'+name.upper()
        obj=asm.add(world,name,color=color);shapes[name]=obj
        if arm_link or rep=='FUNCTIONAL_ENVELOPE':density=None
        if mass is not None:density=None
        v,c,I,m=props(world,mass,density)
        rec=dict(id=name,pn=pn,product_role=role,representation_role=rep,qualification_status='NOT_EVALUATED',
            source_revision=source,parent_assembly=parent,mount_interface=mount,configuration=state,
            mass_source=mass_source or ('CAD_ESTIMATE' if density is not None else 'BUDGET' if mass is not None else 'UNKNOWN'),
            mass_owner=mass_owner or name,mass_kg=m,mass_basis=basis or ('UNIFORM_GEOMETRY_CANDIDATE_DENSITY' if density else 'UNIFORM_ENVELOPE_BUDGET' if mass is not None else 'NOT_ALLOCATED'),
            center_of_mass_S_mm=c,inertia_about_COM_S_kg_mm2=I,volume_mm3=v,
            density_kg_mm3=density,shape_valid=world.is_valid,solid_count=len(world.solids()),
            bounds=bounds(world),T_S_local=np.asarray(T).tolist(),arm_link=arm_link,motion_group=motion_group,
            evidence_scope='NOMINAL_GEOMETRY_ONLY; fit, strength, launch and environment not verified')
        records.append(rec)
        if source=='WP03_PARAMETRIC_DESIGN' and rep=='PHYSICAL_GEOMETRY':local_parts.setdefault(pn,s)
        interfaces.append(dict(instance=name,parent=parent,mount_interface=mount,physical_joint_status='DESIGN_CANDIDATE_UNVERIFIED',source_revision=source))
        return obj
    def placed(s,name,center=(0,0,0),**kw):return add(s,name,T=tf(center),**kw)
    # Source root geometry is rebuilt, not copied from a generated assembly STEP.
    def rootadd(s,pn,xyz=(0,0,0),name=None,classification=None,color=SILVER,basis=None,axis=None):
        # WP03 drill pattern is an explicit delta to reused root rails.
        if name and name.startswith('RB_longeron_'):
            for hx in [-150,-90,-30,30,90,150]:s=bore(s,3.4,16,(hx,-np.sign(xyz[1])*2,0))
        T=tf(xyz)
        if axis is not None:
            t=Plane(origin=xyz,z_dir=axis).location.wrapped.Transformation()
            T=np.array([[t.Value(i,j) for j in range(1,5)] for i in range(1,4)]+[[0,0,0,1]])
        ishw=classification=='STANDARD_HARDWARE_GEOMETRY_CANDIDATE'
        return add(s,name or pn,pn=pn,parent='ROOT_STRUCTURE',mount='M3R_ROOT_CHAIN' if 'M3R' in pn else 'FRAME_ROOT_JOINTS',
            color=color,T=T,density=None if ishw else 2.7e-6,rep='SIMPLIFIED_PROXY' if ishw else 'PHYSICAL_GEOMETRY',
            source='WP02_ROOT_WITH_WP03_SHEAR_ATTACHMENT_HOLES' if name and name.startswith('RB_longeron_') else 'WP02_ROOT_GEOMETRY_REBUILT',basis='THREADLESS_FASTENER_UNSELECTED' if ishw else None)
    build_root(rootadd)
    # Main shear faces are inboard of the outer rails; solar standoff is preserved.
    for side in [-1,1]:
        web=Box(344,2,202.3)
        for x in [-150,-90,-30,30,90,150]:
            for z in [-94,94]:web=bore(web,3.4,6,(x,0,z),(0,1,0))
        placed(web,f'shear_web_{side}',(0,side*100.15,0),mount='LONGERON_INBOARD_SHEAR_CLIPS',color=GOLD)
        for x in [-150,-90,-30,30,90,150]:
            for z in [-94,94]:
                clip=box((16,8,14.3));clip=bore(clip,3.4,12,(0,0,0),(0,1,0));clip=bore(clip,2.5,18)
                placed(clip,f'shear_clip_{side}_{x}_{z}',(x,side*105.15,z),mount='LONGERON_M3_TAPPED_CLIP_INTERFACE')
                axis=(0,0,np.sign(z))
                fast=rod((x,side*105.15,np.sign(z)*113.15),(x,side*105.15,np.sign(z)*91.15),3)
                fast=fast+cylinder(5.5,3,(x,side*105.15,np.sign(z)*114.65),axis)
                add(fast,f'shear_rail_screw_{side}_{x}_{z}',mount=f'shear_clip_{side}_{x}_{z}',rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis='M3_THREADLESS_FASTENER_ENVELOPE')
                add(rod((x,side*98.15,z),(x,side*108.15,z),3),f'shear_web_screw_{side}_{x}_{z}',mount=f'shear_clip_{side}_{x}_{z}',rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis='M3_THREADLESS_FASTENER_ENVELOPE')
        # Service covers have a physical rim and remove outward after wing staging.
        cover=Box(344,1.5,180)
        for x in [-150,0,150]:
            for z in [-82,82]:cover=bore(cover,3.4,5,(x,0,z),(0,1,0))
        if view!='cutaway':placed(cover,f'access_cover_{side}',(0,side*112.4,0),parent='COVERS',mount='COVER_STANDOFFS')
        for x in [-150,0,150]:
            for z in [-82,82]:
                pad=bore(box((12,10.5,12)),2.5,14,(0,0,0),(0,1,0))
                placed(pad,f'cover_mount_{side}_{x}_{z}',(x,side*106.4,z),parent='COVERS',mount=f'shear_web_{side}')
    # Decks and removable equipment adapters. Slots around root columns are explicit.
    for deck,z in [('lower',-99.65),('upper',-10)]:
        d=Box(344,196.3,3)
        for x in [20,160]:
            for y in [-94.15,94.15]:d=d-box((17,17,7),(x,y,0))
        for x in [-150,-50,50,150]:
            for y in [-89,89]:d=bore(d,3.4,7,(x,y,0))
        placed(d,f'{deck}_equipment_deck',(0,0,z),parent='EQUIPMENT_BAY',mount='DECK_EDGE_ANGLES')
        for side in [-1,1]:
            angle=box((334,10,3),(0,-side*3.5,0))+box((334,3,14),(0,side*3.5,-5.5))
            placed(angle,f'{deck}_deck_angle_{side}',(0,side*94.15,z-3),parent='EQUIPMENT_BAY',mount=f'shear_web_{side}')
    # Launch adapter is an internal structure reservation: no invented provider bolt circle.
    rear=Box(6,226.3,226.3)-Box(8,158,158)
    for y in [-107.15,107.15]:
        for z in [-107.15,107.15]:rear=bore(rear,8,10,(0,y,z),(1,0,0))
    placed(rear,'rear_launch_bulkhead',(-186,0,0),mount='REAR_END_FRAME_M4_CONNECTION_REDESIGN',color=GOLD)
    for y in [-86,86]:placed(box((6,18,172)),'rear_vertical_rib_'+str(y),(-192,y,0),mount='rear_launch_bulkhead',color=GOLD)
    for z in [-86,86]:placed(box((6,172,18)),'rear_horizontal_rib_'+str(z),(-192,0,z),mount='rear_launch_bulkhead',color=GOLD)
    placed(cylinder(120,20,axis=(1,0,0)),'launch_interface_reserved_volume',(-205,0,0),parent='LAUNCH_INTERFACE',mount='rear_launch_bulkhead',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE)
    front=Box(2,214,214)
    for y in [-101,101]:
        for z in [-101,101]:front=bore(front,3.4,6,(0,y,z),(1,0,0))
    if view!='cutaway':placed(front,'front_service_cover',(184,0,0),parent='COVERS',mount='FRONT_END_FRAME_INSERTS')
    roof=Box(178,202.3,2)
    for x in [-55,20]:roof=roof-box((20,35,6),(x,-82,0))
    if view!='cutaway':placed(roof,'forward_roof_access',(-88,0,112.15),parent='COVERS',mount='TOP_LONGERONS')
    for eq in P['equipment']:
        name=eq['name'];size=np.array(eq['size_mm'],float);c=np.array(eq['center_mm'],float);base=c[2]-size[2]/2
        holes=[(x,y,3.4) for x in [-size[0]/2+7,size[0]/2-7] for y in [-size[1]/2+7,size[1]/2-7]]
        adapter=plate((size[0]+8,size[1]+8,2),holes)
        placed(adapter,'adapter_'+name,(*c[:2],base+1),parent='EQUIPMENT_BAY',mount='lower_equipment_deck' if base<-50 else 'upper_equipment_deck')
        placed(box((size[0]-10,size[1]-10,.5)),'thermal_interface_'+name,(*c[:2],base+2.25),parent='THERMAL',mount='adapter_'+name,density=None,basis='THERMAL_PAD_MATERIAL_THICKNESS_CANDIDATE')
        c[2]+=2.5
        placed(Box(*size),'equipment_'+name,c,parent='EQUIPMENT_BAY',mount='adapter_'+name,rep='SIMPLIFIED_PROXY',mass=eq['budget_mass_kg'],mass_source='BUDGET',color=TEAL)
        sign=-1 if c[1]>=0 else 1
        outlet=(c[0],c[1]+sign*(size[1]/2+4),base+14)
        placed(box((18,8,10)),'connector_'+name,outlet,parent='EQUIPMENT_BAY',mount='equipment_'+name,rep='FUNCTIONAL_ENVELOPE',density=None,color=DARK)
        # Tool and removal volumes go to interface records, not the displayed hardware layer.
        records[-1]['maintenance']={'tool_axis_S':[0,-sign,0],'removal_direction_S':[0,sign,0],'required_travel_mm':float(size[1]+20),'validation':'NEEDS_COVER_AND_ADJACENT_UNIT_SEQUENCE'}
    # Fixed power/data trunk and a bounded internal branch at the forward roof port.
    for k,(a,b) in enumerate([((-155,0,45),(65,0,45)),((65,0,45),(65,-80,45)),((65,-80,45),(65,-80,118))]):
        add(rod(a,b,6),f'internal_harness_proxy_{k}',parent='HARNESS',mount='EPS_TO_OBC_ARM_RELEASE_CHANNEL',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE)
    for x in [-140,-70,0,65]:
        clip=Box(12,18,10)-cylinder(7,16,(0,0,1),(1,0,0))
        placed(clip,'trunk_clip_'+str(x),(x,0,44),parent='HARNESS',mount='upper_equipment_deck_STANDOFF_TBD',color=TEAL)
        placed(plate((12,18,44),[(0,y,3.4) for y in [-6,6]]),'trunk_clip_standoff_'+str(x),(x,0,17.5),parent='HARNESS',mount='upper_equipment_deck',color=TEAL)
    for k,x in enumerate([-115,-40]):
        for j,(a,b) in enumerate([((65,-80,118),(x,-80,118)),((x,-80,118),(x,-99,139))]):
            add(rod(a,b,4),f'release_power_data_route_{k}_{j}',parent='HARNESS',mount='EPS_DUAL_RELEASE_AND_CONFIRMATION_CHANNEL',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE)
    # Thermal spreader connects internal electronics to the aft uncovered radiator reservation.
    spread=plate((110,80,2),[(x,y,3.4) for x in [-48,48] for y in [-33,33]])
    placed(spread,'radiator_spreader',(-115,0,-113.15),parent='THERMAL',mount='LOWER_LONGERONS_THERMAL_LUGS')
    add(rod((-115,0,-97),(-115,0,-112),10),'battery_thermal_link',parent='THERMAL',mount='adapter_battery_TO_radiator_spreader',rep='SIMPLIFIED_PROXY',density=None,color=GOLD,basis='THERMAL_STRAP_SECTION_AND_MATERIAL_PENDING')
    # Sensing / communication interfaces on +X task face; no invented flight sensor internals.
    bracket=Box(4,50,44)-Box(6,30,24)
    placed(bracket,'navigation_camera_bracket',(187,-72,62),parent='EXTERNAL_INTERFACES',mount='FRONT_END_FRAME_SENSOR_LUGS',color=GOLD)
    placed(Box(35,42,36),'navigation_camera',(206.5,-72,62),parent='EXTERNAL_INTERFACES',mount='navigation_camera_bracket',rep='SIMPLIFIED_PROXY',mass=.15,color=DARK)
    placed(cylinder(20,6,axis=(1,0,0)),'camera_lens',(226,-72,62),parent='EXTERNAL_INTERFACES',mount='navigation_camera',rep='FUNCTIONAL_ENVELOPE',density=None,color=BLUE)
    placed(plate((48,48,3),[(x,y,3.4) for x in [-18,18] for y in [-18,18]]),'antenna_mount',(-142,56,116.15),parent='EXTERNAL_INTERFACES',mount='TOP_LONGERON_ANTENNA_LUGS',color=GOLD)
    placed(Box(40,40,8),'communications_antenna',(-142,56,121.65),parent='EXTERNAL_INTERFACES',mount='antenna_mount',rep='SIMPLIFIED_PROXY',density=None,color=DARK)
    # Two roof-mounted fold-away cradles replace the GSE gantry implementation.
    for k,row in enumerate(CONTACT['stations']):
        x=P['retention']['station_x_mm'][k];sy=-99;z0=125.15;shoe=row['shoe_top_z_mm'];capz=[489.513134,532.814321][k]+8
        placed(plate((22,202.3,10),[(0,y,4.5) for y in [-94.15,94.15]]),f'hold_crossbeam_{k}',(x,0,101.15),parent='ONBOARD_RETENTION',mount='TOP_LONGERON_HOLD_CLIPS',color=GOLD)
        for y in [-94.15,94.15]:
            lug=plate((22,22,12),[(0,0,4.5)])
            placed(lug,f'hold_roof_lug_{k}_{y}',(x,y,112.15),parent='ONBOARD_RETENTION',mount=f'hold_crossbeam_{k}',color=GOLD)
        foot=Box(30,26,20)-box((14,28,16),(0,0,4))
        foot=bore(foot,8.4,36,(0,0,4),(1,0,0))
        placed(foot,f'hold_pivot_clevis_{k}',(x,sy,z0-4),parent='ONBOARD_RETENTION',mount=f'hold_roof_lug_{k}_-94.15',color=GOLD)
        placed(cylinder(8,34,axis=(1,0,0)),f'hold_pivot_pin_{k}',(x,sy,z0),parent='ONBOARD_RETENTION',mount=f'hold_pivot_clevis_{k}',density=7.85e-6,color=DARK)
        fold=cfg['retention_fold_deg'];T=tf((x,sy,z0),(math.radians(fold),0,0))
        h=capz-z0+12
        mast=Box(12,20,h)-Box(8,14,h+2)
        mast=mast.moved(Location((0,0,h/2)))
        mast=mast+cylinder(20,12,(0,0,0),(1,0,0))
        mast=bore(mast,8.4,18,(0,0,0),(1,0,0));mast=bore(mast,6.4,18,(0,0,capz-z0),(1,0,0))
        add(mast,f'hold_fold_mast_{k}',parent='ONBOARD_RETENTION',mount=f'hold_pivot_pin_{k}',T=T,color=GOLD,motion_group=f'cradle_{k}')
        # Cantilever saddle and source-derived replaceable local contact pads.
        drop=0 if state=='parking' else 30
        arm=box((24,174,8),(0,80,shoe-z0-19-drop))
        for y in [87,111]:arm=bore(arm,3.4,14,(0,y,shoe-z0-19-drop))
        add(arm,f'hold_saddle_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=T,color=GOLD,motion_group=f'cradle_{k}')
        for j,pad in enumerate(row['pads']):
            pts=np.array(pad['top_corners_mm']);pts[:,0]-=x;pts[:,1]-=sy;pts[:,2]-=z0
            pts[:,2]-=drop
            low=pts.copy();low[:,2]=shoe-z0-15-drop
            s=Solid.make_loft([Wire.make_polygon([tuple(p) for p in low],close=True),Wire.make_polygon([tuple(p) for p in pts],close=True)])
            add(s,f'hold_contact_pad_{k}_{j}',parent='ONBOARD_RETENTION',mount=f'hold_saddle_{k}',T=T,density=None,color=TEAL,motion_group=f'cradle_{k}',basis='WP02_NOMINAL_CONTACT_GEOMETRY; REAL_ALLOWABLE_ZONE_PENDING')
        # Top cap independently opens about its root X hinge before the cradle folds.
        Tc=T@tf((0,0,capz-z0),(math.radians(cfg['cap_open_deg']),0,0))
        cap=box((20,164,8),(0,82,0))+cylinder(16,20,axis=(1,0,0))
        cap=bore(cap,6.4,26,(0,0,0),(1,0,0))
        add(cap,f'hold_open_cap_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=Tc,color=GOLD,motion_group=f'cap_{k}')
        add(box((18,112,4),(0,99,-6)),f'hold_upper_pad_{k}',parent='ONBOARD_RETENTION',mount=f'hold_open_cap_{k}',T=Tc,density=None,color=TEAL,motion_group=f'cap_{k}',basis='UPPER_CONTACT_ZONE_AND_PRELOAD_PENDING')
        add(cylinder(6,28,(0,0,0),(1,0,0)),f'hold_cap_pin_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=Tc,density=7.85e-6,color=DARK,motion_group=f'cradle_{k}')
        # A captured pin holds the cap tie to the lower cradle; geometry follows stroke.
        tie_h=capz-4-(shoe-19)
        tie=box((6,5,tie_h),(0,158,-tie_h/2-4))
        tie=bore(tie,4.4,10,(0,158,-tie_h-4),(1,0,0))
        add(tie,f'hold_cap_tie_{k}',parent='ONBOARD_RETENTION',mount=f'hold_open_cap_{k}',T=Tc,color=GOLD,motion_group=f'cap_{k}')
        latch_z=shoe-z0-19-drop
        latch=box((22,16,18),(0,158,latch_z))-box((7,18,14),(0,158,latch_z+3))
        latch=bore(latch,4.4,28,(0,158,latch_z),(1,0,0))
        add(latch,f'hold_latch_clevis_{k}',parent='ONBOARD_RETENTION',mount=f'hold_saddle_{k}',T=T,color=GOLD,motion_group=f'cradle_{k}')
        withdraw=0 if state=='parking' else P['retention']['latch_withdraw_mm']
        add(cylinder(4,24,(-withdraw,158,latch_z),(1,0,0)),f'hold_latch_pin_{k}',parent='ONBOARD_RETENTION',mount=f'hold_latch_clevis_{k}',T=T,density=7.85e-6,color=DARK,motion_group=f'cradle_{k}')
        add(box((36,22,22),(-31,158,latch_z)),f'hold_latch_puller_{k}',parent='ONBOARD_RETENTION',mount=f'hold_latch_clevis_{k}',T=T,rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE,motion_group=f'cradle_{k}',basis='PIN_PULLER_FORCE_STROKE_SHOCK_AND_ENERGY_PENDING')
        for yy in [-6,6]:
            add(cylinder(4,70,(0,yy,shoe-z0-35)),f'hold_shoe_guide_{k}_{yy}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=T,density=7.85e-6,color=DARK,motion_group=f'cradle_{k}')
        add(box((16,18,50),(-14,0,shoe-z0-40)),f'hold_shoe_spring_release_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=T,rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE,motion_group=f'cradle_{k}')
        placed(Box(30,24,34),f'hold_electric_release_{k}',(x,sy-23,z0+14),parent='ONBOARD_RETENTION',mount=f'hold_pivot_clevis_{k}',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE,basis='ONBOARD_EPS_PIN_PULLER_FORCE_STROKE_SHOCK_UNKNOWN')
        placed(cylinder(22,20,axis=(1,0,0)),f'hold_torsion_spring_{k}',(x-22,sy,z0),parent='ONBOARD_RETENTION',mount=f'hold_pivot_pin_{k}',rep='FUNCTIONAL_ENVELOPE',density=None,color=DARK)
        placed(Box(12,10,8),f'hold_position_sensor_{k}',(x+23,sy,z0-4),parent='ONBOARD_RETENTION',mount=f'hold_pivot_clevis_{k}',rep='FUNCTIONAL_ENVELOPE',density=None,color=DARK)
        for kind,point in [('latch',(-15,158,latch_z)),('cap',(14,0,capz-z0)),('shoe',(14,0,shoe-z0-20))]:
            add(box((8,8,8),point),f'hold_confirm_{kind}_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=T,rep='FUNCTIONAL_ENVELOPE',density=None,color=DARK,motion_group=f'cradle_{k}')
    # R2 leaves retain planform/mass; WP03 uses a continuous fixed-offset hinge chain.
    from wing_kinematics import frames as wingframes
    wingdata=[]
    for side in [-1,1]:
        leaves=wingframes(side,cfg['wing_angles_deg']);wingdata+=leaves
        for leaf in leaves:
            i=leaf['index'];T=np.asarray(leaf['T_S_leaf_center'])
            add(Box(300,200,2.5),f'wing_{side}_leaf_{i}',parent='SOLAR_WING',mount=f'wing_{side}_hinge_{i}',T=T,rep='SIMPLIFIED_PROXY',mass=.18,mass_source='BUDGET',color=BLUE,motion_group=f'wing_{side}_{i}',source='R2_PLANFORM_WITH_WP03_SERIAL_HINGE_OFFSETS')
            # Perimeter edge strips and clamped hinge shoes are separate hardware.
            for sx in [-1,1]:
                add(box((6,200,1.5),(sx*147,0,2)),f'wing_edge_{side}_{i}_{sx}',parent='SOLAR_WING',mount=f'wing_{side}_leaf_{i}',T=T,color=SILVER,motion_group=f'wing_{side}_{i}')
            for xx in [-120,120]:
                anchor=np.array(leaf['root_S_mm']);anchor[0]=xx
                placed(ring(8,4.4,12).rotate(__import__('build123d').Axis.Y,90),f'wing_hinge_bush_{side}_{i}_{xx}',anchor,parent='SOLAR_WING',mount=f'wing_{side}_hinge_{i}',color=GOLD,motion_group=f'wing_{side}_{i}')
                placed(cylinder(4,24,axis=(1,0,0)),f'wing_hinge_pin_{side}_{i}_{xx}',anchor,parent='SOLAR_WING',mount=f'wing_{side}_hinge_{i}',density=7.85e-6,color=DARK,motion_group=f'wing_{side}_{i}')
                shoe=box((28,18,2.5),(xx,-91,2.5))
                add(shoe,f'wing_leaf_shoe_{side}_{i}_{xx}',parent='SOLAR_WING',mount=f'wing_hinge_bush_{side}_{i}_{xx}',T=T,color=GOLD,motion_group=f'wing_{side}_{i}')
        for xx in [-120,120]:
            bracket=box((30,14,5),(0,0,-5))+box((30,4,16),(0,-side*5,0))
            bracket=bore(bracket,4.4,34,(0,0,0),(1,0,0))
            placed(bracket,f'wing_root_bracket_{side}_{xx}',(xx,side*115.4,-108.15),parent='SOLAR_WING',mount='LOWER_LONGERON_SOLAR_INTERFACE',color=GOLD)
        placed(Box(22,18,18),f'wing_release_budget_{side}',(-132,side*128,0),parent='SOLAR_WING',mount='SIDE_SHEAR_PANEL_RELEASE_LUG_TBD',rep='FUNCTIONAL_ENVELOPE',mass=.08,color=ORANGE)
        placed(Box(12,20,12),f'wing_harness_budget_{side}',(132,side*115.4,-100),parent='SOLAR_WING',mount='WING_ROOT_HARNESS_TRANSITION',rep='FUNCTIONAL_ENVELOPE',mass=.05,color=ORANGE)
    if include_arm:
        for name,T in frames.items():
            add(arm_shape(name),'B601_'+name,parent='B601_ARM',mount='M3R_STAGE_A' if name=='base_link' else 'ACCEPTED_URDF_PARENT_JOINT',T=T,arm_link=name,density=None,color=SILVER if name in ['link2','link3','gripper_left','gripper_right'] else DARK,source='WP01_PINNED_NOMINAL_BREP; DYNAMICS_FROM_ACCEPTED_URDF',basis='ACCEPTED_URDF_DIGITAL_NOT_VENDOR_MEASUREMENT',motion_group='arm_'+name)
    if view=='ground':
        placed(plate((420,310,10),[(x,y,8.5) for x in [-180,180] for y in [-107.15,107.15]]),'GSE_AIT_base',(0,0,-170),role='GSE',parent='GROUND_AIT',mount='LAB_BENCH',color=TEAL)
        for x in [-180,180]:
            for y in [-107.15,107.15]:placed(box((24,24,46)),f'GSE_AIT_pedestal_{x}_{y}',(x,y,-142),role='GSE',parent='GROUND_AIT',mount='GSE_AIT_base_TO_FRAME',color=TEAL)
    # Physical hardware and explicit proxies are separate STEP product layers.
    layers={}
    for r in records:
        key=r['product_role']+'__'+r['representation_role']
        layers.setdefault(key,[]).append(shapes[r['id']])
    model=Compound(label='GROUND_AIT_ASSEMBLY' if view=='ground' else 'SERVICER_ONBOARD_CANDIDATE',children=[Compound(label=k,children=v) for k,v in layers.items()])
    artifact=(state if include_arm else state+'_structure') if view=='complete' else state+'_'+view
    receipt=dict(configuration=P['configuration_id'],state=state,view=view,q_deg=cfg['q_deg'],finger_mm=cfg['finger_mm'],T_S_arm_base=root.tolist(),link_transforms={k:v.tolist() for k,v in frames.items()},wing_frames=wingdata,instances=records,interfaces=interfaces,bounds=bounds(model),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mass_complete=False,physical_assembly_completed=False)
    (HERE/'results'/f'{artifact}_instances.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    if write_parts:
        for pn,s in local_parts.items():export_step(s,str(HERE/'parts'/f'{pn}.step'))
        with (HERE/'BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
            cols=['id','pn','product_role','representation_role','qualification_status','parent_assembly','mount_interface','mass_source','mass_owner','mass_kg','mass_basis','source_revision'];w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(records)
        with (HERE/'INTERFACES.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(interfaces[0]));w.writeheader();w.writerows(interfaces)
    return model,shapes,receipt

if __name__=='__main__':
    for state in ['parking','released','service']:
        model,_,r=build(state,write_parts=state=='service')
        export_step(model,str(HERE/f'servicer_{state}.step'))
        print(state,len(r['instances']),r['bounds'],flush=True)
