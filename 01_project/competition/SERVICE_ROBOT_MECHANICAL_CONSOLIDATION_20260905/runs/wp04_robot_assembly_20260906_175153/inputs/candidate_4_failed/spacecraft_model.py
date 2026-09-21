"""WP03 whole-spacecraft candidate. Explicit products, sources and mass owners.

No original geometry, hardware, environment or research gate is modified.
"""
from pathlib import Path
import sys,json,csv,math,hashlib,functools,builtins
import numpy as np
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from build123d import Box,Cylinder,Compound,Color,Location,Plane,Wire,Face,Solid,Shell,Edge,Circle,sweep,export_step
from OCP.gp import gp_Trsf
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
from kinematics import fk,tf,TREE
from root_structure import build_root
from wing_kinematics import frames as wingframes
HERE=Path(__file__).resolve().parent
from candidate_context import WP01 as W1, WP02 as W2
import r01_design as r01
import r07_design as r07
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
    path=W1/'inputs'/f'{name}.step';st=path.stat()
    key=(str(path),st.st_size,st.st_mtime_ns)
    cache=builtins.__dict__.setdefault('_wp03_pinned_arm_source_cache',{})
    if key not in cache:
        print('Nominal arm input '+name,file=sys.stderr,flush=True)
        cache[key]=import_step(path)
    return cache[key]

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
            bounds=bounds(world),local_bounds=bounds(s),T_S_local=np.asarray(T).tolist(),arm_link=arm_link,motion_group=motion_group,
            evidence_scope='NOMINAL_GEOMETRY_ONLY; fit, strength, launch and environment not verified')
        records.append(rec)
        if source in ['WP03_PARAMETRIC_DESIGN','WP02_ROOT_WITH_WP03_INTERFACE_CORRECTIONS'] and rep=='PHYSICAL_GEOMETRY':local_parts.setdefault(pn,s)
        interfaces.append(dict(instance=name,parent=parent,mount_interface=mount,physical_joint_status='DESIGN_CANDIDATE_UNVERIFIED',source_revision=source))
        return obj
    def placed(s,name,center=(0,0,0),**kw):return add(s,name,T=tf(center),**kw)
    # Source root geometry is rebuilt, not copied from a generated assembly STEP.
    def rootadd(s,pn,xyz=(0,0,0),name=None,classification=None,color=SILVER,basis=None,axis=None):
        # WP03 drill pattern is an explicit delta to reused root rails.
        if name and name.startswith('RB_longeron_'):
            for hx in [-150,-90,-30,30,90,150]:s=bore(s,3.4,16,(hx,-np.sign(xyz[1]),0))
            if xyz[2]<0:
                for hx in [-144,144]:s=bore(s,3.4,16,(hx,0,0))
        if name and name.startswith('RB_end_plug_'):
            s=box((20,7.8,7.8));s=bore(s,3.3,24,(0,0,0),(1,0,0));s=bore(s,4.5,12,(-np.sign(xyz[0])*3,0,0))
        if name and name.startswith(('RB_longeron_','RB_end_plug_')):pn=pn+'_WP03'
        if name and name.startswith('RB_longeron_'):pn += '_LOWER' if xyz[2]<0 else '_UPPER'
        s,xyz=r07.modify_root(P,s,name,pn,xyz,classification)
        T=tf(xyz)
        if axis is not None:
            t=Plane(origin=xyz,z_dir=axis).location.wrapped.Transformation()
            T=np.array([[t.Value(i,j) for j in range(1,5)] for i in range(1,4)]+[[0,0,0,1]])
        ishw=classification=='STANDARD_HARDWARE_GEOMETRY_CANDIDATE'
        return add(s,name or pn,pn=pn,parent='ROOT_STRUCTURE',mount='M3R_ROOT_CHAIN' if 'M3R' in pn else 'FRAME_ROOT_JOINTS',
            color=color,T=T,density=None if ishw else 2.7e-6,rep='SIMPLIFIED_PROXY' if ishw else 'PHYSICAL_GEOMETRY',
            source='WP02_ROOT_WITH_WP03_INTERFACE_CORRECTIONS' if name and name.startswith(('RB_longeron_','RB_end_plug_')) else 'WP02_ROOT_GEOMETRY_REBUILT',basis='THREADLESS_FASTENER_UNSELECTED' if ishw else None)
    build_root(rootadd)
    # Main shear faces are inboard of the outer rails; solar standoff is preserved.
    for side in [-1,1]:
        web=r07.modify_web(P,r01.web_shape(P,side),side)
        placed(web,f'shear_web_{side}',(0,side*102.15,0),mount='LONGERON_INBOARD_SHEAR_CLIPS',color=GOLD)
        for x in [-150,-90,-30,30,90,150]:
            for z in [-94,94]:
                clip=box((16,6,14.3));clip=bore(clip,3.4,12,(4,0,0),(0,1,0));clip=bore(clip,2.5,18)
                placed(clip,f'shear_clip_{side}_{x}_{z}',(x,side*106.15,z),mount='LONGERON_M3_TAPPED_CLIP_INTERFACE')
                axis=(0,0,np.sign(z))
                fast=rod((x,side*106.15,np.sign(z)*113.15),(x,side*106.15,np.sign(z)*91.15),3)
                fast=fast+cylinder(5.5,3,(x,side*106.15,np.sign(z)*114.65),axis)
                add(fast,f'shear_rail_screw_{side}_{x}_{z}',mount=f'shear_clip_{side}_{x}_{z}',rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis='M3_THREADLESS_FASTENER_ENVELOPE')
                add(rod((x+4,side*100.15,z),(x+4,side*110.15,z),3),f'shear_web_screw_{side}_{x}_{z}',mount=f'shear_clip_{side}_{x}_{z}',rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis='M3_THREADLESS_FASTENER_ENVELOPE')
        # Service covers have a physical rim and remove outward after wing staging.
        cover=Box(344,1.5,180)
        for x in [-150,0,150]:
            for z in [-75,75]:cover=bore(cover,3.4,5,(x,0,z),(0,1,0))
        if view!='cutaway':placed(cover,f'access_cover_{side}',(0,side*112.4,0),parent='COVERS',mount='COVER_STANDOFFS')
        for x in [-150,0,150]:
            for z in [-75,75]:
                pad=bore(box((12,8.5,12)),2.5,14,(0,0,0),(0,1,0))
                placed(pad,f'cover_mount_{side}_{x}_{z}',(x,side*107.4,z),parent='COVERS',mount=f'shear_web_{side}')
    # Decks and removable equipment adapters. Slots around root columns are explicit.
    for deck,z in [('lower',-99.65),('upper',-10)]:
        d=r01.deck_shape(P,deck)
        placed(d,f'{deck}_equipment_deck',(0,0,z),parent='EQUIPMENT_BAY',mount='DECK_EDGE_ANGLES')
        for side in [-1,1]:
            for k,(a,b) in enumerate([(-167,11.5),(28.5,151.5)]):
                legz=5.5 if deck=='lower' else -5.5
                angle=r01.angle_shape(P,deck,side,k)
                placed(angle,f'{deck}_deck_angle_{side}_{k}',((a+b)/2,side*96.15,z-3),parent='EQUIPMENT_BAY',mount=f'shear_web_{side}')
    for connection in r01.connections(P):
        for name,shape in r01.hardware_parts(P,connection).items():
            add(shape,name,parent='R01_FASTENERS',mount=connection['id'],rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis='R01_NOMINAL_THREADLESS_HARDWARE_UNSELECTED_MASS_UNKNOWN')
    # Launch adapter is an internal structure reservation: no invented provider bolt circle.
    rear=Box(6,226.3,226.3)-Box(8,158,158)
    for y in [-107.15,107.15]:
        for z in [-107.15,107.15]:rear=bore(rear,4.5,10,(0,y,z),(1,0,0))
    placed(rear,'rear_launch_bulkhead',(-186,0,0),mount='REAR_END_FRAME_M4_CONNECTION_REDESIGN',color=GOLD)
    for y in [-86,86]:placed(box((6,18,172)),'rear_vertical_rib_'+str(y),(-192,y,0),mount='rear_launch_bulkhead',color=GOLD)
    for z in [-86,86]:placed(box((6,154,18)),'rear_horizontal_rib_'+str(z),(-192,0,z),mount='rear_launch_bulkhead',color=GOLD)
    placed(cylinder(120,20,axis=(1,0,0)),'launch_interface_reserved_volume',(-205,0,0),parent='LAUNCH_INTERFACE',mount='rear_launch_bulkhead',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE)
    front=Box(2,214,214)
    for y in [-107.15,107.15]:
        for z in [-107.15,107.15]:front=bore(front,8,6,(0,y,z),(1,0,0))
    for y in [-101,101]:
        for z in [-101,101]:front=bore(front,3.4,6,(0,y,z),(1,0,0))
    if view!='cutaway':placed(front,'front_service_cover',(184,0,0),parent='COVERS',mount='FRONT_END_FRAME_INSERTS')
    roof=Box(178,202.3,2)
    for x in [-55,20]:roof=roof-box((20,35,6),(x,-82,0))
    for x in [-115,-40]:
        for y in [-94.15,94.15]:roof=roof-box((36,40,6),(x+88,y,0))
    if view!='cutaway':placed(roof,'forward_roof_access',(-88,0,112.15),parent='COVERS',mount='TOP_LONGERONS')
    for eq in P['equipment']:
        name=eq['name'];size=np.array(eq['size_mm'],float);c=np.array(eq['center_mm'],float);base=c[2]-size[2]/2
        holes=[(x,y,3.4) for x in [-size[0]/2+7,size[0]/2-7] for y in [-size[1]/2+7,size[1]/2-7]]
        adapter=plate((size[0]+8,size[1]+8,2),holes)
        for px in [20,160]:
            for py in [-94.15,94.15]:adapter=adapter-box((17,17,6),(px-c[0],py-c[1],0))
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
        placed(plate((12,12,47.5),[(0,y,2.5) for y in [-3,3]]),'trunk_clip_standoff_'+str(x),(x,0,15.25),parent='HARNESS',mount='upper_equipment_deck',color=TEAL)
    for k,x in enumerate([-115,-40]):
        for j,(a,b) in enumerate([((65,-80,118),(x,-80,118)),((x,-80,118),(x,-110,149.15))]):
            add(rod(a,b,4),f'release_power_data_route_{k}_{j}',parent='HARNESS',mount='EPS_DUAL_RELEASE_AND_CONFIRMATION_CHANNEL',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE)
    # Reuse two previously studied constant-length candidate service loops.
    harness=json.loads((W2/'results/HARNESS_ANALYSIS.json').read_text(encoding='utf-8'))
    hp=harness['poses'][-1 if state=='service' else 0]
    for name,row in hp['loops'].items():
        pts=row['constant_curvature_candidate']['centerline_points_mm']
        edge=Edge.make_three_point_arc(pts[0],pts[50],pts[-1])
        profile=Circle(3).moved(Plane(origin=tuple(pts[0]),z_dir=edge.tangent_at(0)).location)
        add(sweep(profile,path=edge),'arm_service_loop_'+name,parent='HARNESS',mount='WP02_LOOP_ANCHORS_OUTLET_REGISTRATION_PENDING',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE,source='WP02_CONSTANT_LENGTH_CURVE_PROXY_OD6_NOT_REAL_CABLE')
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
        x=P['retention']['station_x_mm'][k];sy=-99;z0=P['retention']['hinge_z_mm'];shoe=row['shoe_top_z_mm'];capz=[489.513134,532.814321][k]+8
        placed(plate((22,202.3,10),[(0,y,4.5) for y in [-94.15,94.15]]),f'hold_crossbeam_{k}',(x,0,101.15),parent='ONBOARD_RETENTION',mount='TOP_LONGERON_HOLD_CLIPS',color=GOLD)
        for y in [-94.15,94.15]:
            lug=plate((22,14,12),[(0,0,4.5)])
            lug=r07.retention_lug(lug,x,1 if y>0 else -1)
            placed(lug,f'hold_roof_lug_{k}_{y}',(x,y,112.15),parent='ONBOARD_RETENTION',mount=f'hold_crossbeam_{k}',color=GOLD)
        foot=Box(30,26,30)-box((14,28,30),(0,0,7))
        foot=bore(foot,8.4,36,(0,0,2),(1,0,0))
        foot=r07.retention_foot(foot)
        placed(foot,f'hold_pivot_clevis_{k}',(x,sy,z0-2),parent='ONBOARD_RETENTION',mount=f'hold_roof_lug_{k}_-94.15',color=GOLD)
        placed(cylinder(8,34,axis=(1,0,0)),f'hold_pivot_pin_{k}',(x,sy,z0),parent='ONBOARD_RETENTION',mount=f'hold_pivot_clevis_{k}',density=7.85e-6,color=DARK)
        fold=cfg['retention_fold_deg'];T=tf((x,sy,z0),(math.radians(fold),0,0))
        h=capz-z0-18
        mast=Box(12,20,h)-Box(8,14,h+2)
        mast=mast.moved(Location((0,0,h/2)))
        mast=mast+cylinder(20,12,(0,0,0),(1,0,0))
        mast=mast+box((32,20,4),(0,0,h+2))
        for xx in [-14,14]:mast=mast+box((4,20,28),(xx,0,h+14))
        mast=bore(mast,8.4,18,(0,0,0),(1,0,0));mast=bore(mast,6.4,40,(0,0,capz-z0),(1,0,0))
        add(mast,f'hold_fold_mast_{k}',parent='ONBOARD_RETENTION',mount=f'hold_pivot_pin_{k}',T=T,color=GOLD,motion_group=f'cradle_{k}')
        # Cantilever saddle and source-derived replaceable local contact pads.
        drop=0 if state=='parking' else P['retention']['shoe_retreat_mm']
        arm=box((24,157,8),(0,88.5,shoe-z0-19-drop))+box((28,28,8),(0,0,shoe-z0-19-drop))
        arm=arm-box((12.6,20.6,12),(0,0,shoe-z0-19-drop))
        for y in [87,111]:arm=bore(arm,3.4,14,(0,y,shoe-z0-19-drop))
        for xx in [-10,10]:arm=bore(arm,4.4,14,(xx,0,shoe-z0-19-drop))
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
        add(cylinder(6,36,(0,0,0),(1,0,0)),f'hold_cap_pin_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=Tc,density=7.85e-6,color=DARK,motion_group=f'cradle_{k}')
        # A captured pin holds the cap tie to the lower cradle; geometry follows stroke.
        tie_h=capz-4-(shoe-6)
        tie=box((6,8,tie_h+6),(0,160,-(tie_h+6)/2-4))
        tie=bore(tie,4.4,10,(0,160,-tie_h-4),(1,0,0))
        add(tie,f'hold_cap_tie_{k}',parent='ONBOARD_RETENTION',mount=f'hold_open_cap_{k}',T=Tc,color=GOLD,motion_group=f'cap_{k}')
        latch_z=shoe-z0-6-drop
        latch=box((22,16,18),(0,160,latch_z))-box((7,18,17),(0,160,latch_z+1.5))
        latch=bore(latch,4.4,28,(0,160,latch_z),(1,0,0))
        add(latch,f'hold_latch_clevis_{k}',parent='ONBOARD_RETENTION',mount=f'hold_saddle_{k}',T=T,color=GOLD,motion_group=f'cradle_{k}')
        withdraw=0 if state=='parking' else P['retention']['latch_withdraw_mm']
        add(cylinder(4,24,(-withdraw,160,latch_z),(1,0,0)),f'hold_latch_pin_{k}',parent='ONBOARD_RETENTION',mount=f'hold_latch_clevis_{k}',T=T,density=7.85e-6,color=DARK,motion_group=f'cradle_{k}')
        add(box((36,22,22),(-31,160,latch_z)),f'hold_latch_puller_{k}',parent='ONBOARD_RETENTION',mount=f'hold_latch_clevis_{k}',T=T,rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE,motion_group=f'cradle_{k}',basis='PIN_PULLER_FORCE_STROKE_SHOCK_AND_ENERGY_PENDING')
        for xx in [-10,10]:
            guide_length=P['retention']['guide_length_mm']
            add(cylinder(4,guide_length,(xx,0,shoe-z0-guide_length/2)),f'hold_shoe_guide_{k}_{xx}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=T,density=7.85e-6,color=DARK,motion_group=f'cradle_{k}')
        add(box((16,18,100),(-14,0,shoe-z0-65)),f'hold_shoe_spring_release_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=T,rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE,motion_group=f'cradle_{k}')
        placed(Box(30,24,34),f'hold_electric_release_{k}',(x,sy-23,z0+14),parent='ONBOARD_RETENTION',mount=f'hold_pivot_clevis_{k}',rep='FUNCTIONAL_ENVELOPE',density=None,color=ORANGE,basis='ONBOARD_EPS_PIN_PULLER_FORCE_STROKE_SHOCK_UNKNOWN')
        placed(cylinder(22,20,axis=(1,0,0)),f'hold_torsion_spring_{k}',(x-22,sy,z0),parent='ONBOARD_RETENTION',mount=f'hold_pivot_pin_{k}',rep='FUNCTIONAL_ENVELOPE',density=None,color=DARK)
        placed(Box(12,10,8),f'hold_position_sensor_{k}',(x+23,sy,z0-4),parent='ONBOARD_RETENTION',mount=f'hold_pivot_clevis_{k}',rep='FUNCTIONAL_ENVELOPE',density=None,color=DARK)
        for kind,point in [('latch',(-15,160,latch_z)),('cap',(14,0,capz-z0)),('shoe',(14,0,shoe-z0-20))]:
            add(box((8,8,8),point),f'hold_confirm_{kind}_{k}',parent='ONBOARD_RETENTION',mount=f'hold_fold_mast_{k}',T=T,rep='FUNCTIONAL_ENVELOPE',density=None,color=DARK,motion_group=f'cradle_{k}')
    # R2 leaves retain planform/mass; WP03 uses a continuous fixed-offset hinge chain.
    wingdata=[]
    for side in [-1,1]:
        leaves=wingframes(side,cfg['wing_angles_deg']);wingdata+=leaves
        edge_local={(i,sx):box((4,200,2),(sx*152,0,0)) for i in [1,2,3] for sx in [-1,1]}
        for leaf in leaves:
            i=leaf['index'];T=np.asarray(leaf['T_S_leaf_center'])
            add(Box(300,200,2.5),f'wing_{side}_leaf_{i}',parent='SOLAR_WING',mount=f'wing_{side}_hinge_{i}',T=T,rep='SIMPLIFIED_PROXY',mass=.18,mass_source='BUDGET',color=BLUE,motion_group=f'wing_{side}_{i}',source='R2_PLANFORM_WITH_WP03_SERIAL_HINGE_OFFSETS')
            # Hardware is outside the300mm chord; H3 occupies its own X band.
            u1,um,u2=(156,162,168) if i<3 else (182,188,194)
            for sx in [-1,1]:
                moving=cylinder(8,6,(sx*um,-100,0),(1,0,0))
                moving=moving+rod((sx*um,-100,0),(sx*um,-85,0),3)
                moving=moving+box((um+3-152,4,2),(sx*(152+um+3)/2,-85,0))
                moving=bore(moving,4.4,10,(sx*um,-100,0),(1,0,0))
                edge_local[(i,sx)]=bore(edge_local[(i,sx)]+moving,4.4,60,(sx*um,-100,0),(1,0,0))
                # Fixed ears belong to parent leaf; a constant parent offset sets the axis.
                JT=np.eye(4);JT[:3,3]=leaf['root_S_mm']
                if i==1:
                    JT[:3,:3]=np.asarray(wingframes(side,[0,0,0])[0]['T_S_leaf_center'])[:3,:3]
                    zoff=0.
                else:
                    PT=np.asarray(leaves[i-2]['T_S_leaf_center']);JT[:3,:3]=PT[:3,:3]
                    zoff=float((np.asarray(leaves[i-2]['tip_S_mm'])-JT[:3,3])@JT[:3,2])
                fork=None
                for u in [u1,u2]:
                    ear=cylinder(8,4,(sx*u,0,0),(1,0,0))
                    ear=ear+rod((sx*u,0,0),(sx*u,-15,zoff),3)
                    ear=bore(ear,4.4,8,(sx*u,0,0),(1,0,0))
                    fork=ear if fork is None else fork+ear
                bridge=box((u2+2-152,4,2),(sx*(152+u2+2)/2,-15,zoff))
                fork=fork+bridge
                if i==1:
                    fixed=fork.moved(loc(JT))
                    pad=box((36,12,2),(sx*156,side*107.15,-114.15))
                    pad=bore(pad,3.4,6,(sx*144,side*107.15,-114.15))
                    fixed=fixed+pad+box((16,4,10),(sx*162,side*111.15,-119.15))+box((16,12,2),(sx*162,side*116.15,-123.15))
                    fixed=r07.modify_wing_pad(P,fixed)
                    add(fixed,f'wing_root_fork_{side}_{sx}',parent='SOLAR_WING',mount='LOWER_LONGERON_M3_AT_X144_AND_R07_M4_AT_X164',color=GOLD)
                else:
                    edge_local[(i-1,sx)]=edge_local[(i-1,sx)]+fork.moved(loc(np.linalg.inv(PT)@JT))
                anchor=np.asarray(leaf['root_S_mm']);anchor[0]=sx*um
                shaft=cylinder(4,22,axis=(1,0,0))+cylinder(6,2,(sx*12,0,0),(1,0,0))
                placed(shaft,f'wing_hinge_pin_{side}_{i}_{sx}',anchor,parent='SOLAR_WING',mount=f'wing_{side}_hinge_{i}',density=7.85e-6,color=DARK,motion_group=f'wing_{side}_{max(1,i-1)}')
        for leaf in leaves:
            i=leaf['index'];T=np.asarray(leaf['T_S_leaf_center'])
            for sx in [-1,1]:add(edge_local[(i,sx)],f'wing_edge_frame_{side}_{i}_{sx}',parent='SOLAR_WING',mount=f'wing_{side}_leaf_{i}_EDGE_INSERTS_TBD',T=T,color=GOLD,motion_group=f'wing_{side}_{i}',basis='FABRICATED_EDGE_FRAME_WITH_OFFSET_FORKS_CANDIDATE')
        placed(Box(22,18,18),f'wing_release_budget_{side}',(-176,side*128,0),parent='SOLAR_WING',mount='SIDE_SHEAR_PANEL_RELEASE_LUG_TBD',rep='FUNCTIONAL_ENVELOPE',mass=.08,color=ORANGE)
        placed(Box(12,20,12),f'wing_harness_budget_{side}',(132,side*121.15,-100),parent='SOLAR_WING',mount='WING_ROOT_HARNESS_TRANSITION',rep='FUNCTIONAL_ENVELOPE',mass=.05,color=ORANGE)
    for name,s,hardware_flag,mount in r07.additions(P):
        add(s,name,parent='R07_ROOT_CONNECTIONS',mount=mount,rep='SIMPLIFIED_PROXY' if hardware_flag else 'PHYSICAL_GEOMETRY',density=None if hardware_flag else 2.7e-6,color=DARK if hardware_flag else GOLD,source='WP04_R07_DESIGN_CANDIDATE',basis='NOMINAL_THREADLESS_UNSELECTED_MASS_UNKNOWN' if hardware_flag else None)
    if include_arm:
        for name,T in frames.items():
            add(arm_shape(name),'B601_'+name,parent='B601_ARM',mount='M3R_STAGE_A' if name=='base_link' else 'ACCEPTED_URDF_PARENT_JOINT',T=T,arm_link=name,density=None,color=SILVER if name in ['link2','link3','gripper_left','gripper_right'] else DARK,source='WP01_PINNED_NOMINAL_BREP; DYNAMICS_FROM_ACCEPTED_URDF',basis='ACCEPTED_URDF_DIGITAL_NOT_VENDOR_MEASUREMENT',motion_group='arm_'+name)
    if view=='ground':
        placed(plate((420,310,10),[(x,y,8.5) for x in [-180,180] for y in [-107.15,107.15]]),'GSE_AIT_base',(0,0,-170),role='GSE',parent='GROUND_AIT',mount='LAB_BENCH',color=TEAL)
        for x in [-180,180]:
            for y in [-107.15,107.15]:placed(box((12,12,51.85)),f'GSE_AIT_pedestal_{x}_{y}',(x,y,-139.075),role='GSE',parent='GROUND_AIT',mount='GSE_AIT_base_TO_FRAME',color=TEAL)
    # Physical hardware and explicit proxies are separate STEP product layers.
    layers={}
    for r in records:
        if view=='cutaway' and r['parent_assembly'] in ['SOLAR_WING','ONBOARD_RETENTION']:continue
        key=r['product_role']+'__'+r['representation_role']
        layers.setdefault(key,[]).append(shapes[r['id']])
    model=Compound(label='GROUND_AIT_ASSEMBLY' if view=='ground' else 'SERVICER_ONBOARD_CANDIDATE',children=[Compound(label=k,children=v) for k,v in layers.items()])
    artifact=(state if include_arm else state+'_structure') if view=='complete' else state+'_'+view
    receipt=dict(configuration=P['configuration_id'],state=state,view=view,q_deg=cfg['q_deg'],finger_mm=cfg['finger_mm'],T_S_arm_base=root.tolist(),link_transforms={k:v.tolist() for k,v in frames.items()},wing_frames=wingdata,instances=records,interfaces=interfaces,bounds=bounds(model),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),dependency_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['design_parameters.json','root_structure.py','wing_kinematics.py','kinematics.py','r01_design.py','candidate_context.py']},mass_complete=False,physical_assembly_completed=False)
    receipt['dependency_sha256']['r07_design.py']=hashlib.sha256((HERE/'r07_design.py').read_bytes()).hexdigest()
    (HERE/'results'/f'{artifact}_instances.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    if state=='service' and view=='complete':r07.write_contract(P,receipt)
    if write_parts:
        for pn,s in local_parts.items():export_step(s,str(HERE/'parts'/f'{pn}.step'))
    return model,shapes,receipt

if __name__=='__main__':
    for state in ['parking','released','service']:
        model,_,r=build(state,write_parts=state=='service')
        export_step(model,str(HERE/f'servicer_{state}.step'))
        print(state,len(r['instances']),r['bounds'],flush=True)
