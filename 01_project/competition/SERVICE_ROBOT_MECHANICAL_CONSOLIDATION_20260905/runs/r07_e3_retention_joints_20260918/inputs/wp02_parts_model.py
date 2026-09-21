"""WP02 editable key assembly. mm, explicit local datums; no hardware commands.

Sources are generated from parameters; STEP exports are exchange snapshots.
Threadless hardware is a space/installation candidate, not a selected fastener.
"""
from pathlib import Path
import sys,json,csv,math
import numpy as np
from scipy.spatial import ConvexHull
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen # process-local guard against an unrelated malformed system font
from build123d import Box,Cylinder,Compound,Color,Location,Plane,Axis,Wire,Face,Shell,Solid,Edge,Circle,sweep,export_step
from cadgen.assembly import AssemblyHelper
from cadgen.step_scene import import_step
from OCP.gp import gp_Trsf
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'design_parameters.json').read_text(encoding='utf-8'))
C=json.loads((HERE/'results/CONTACT_REGISTRATION.json').read_text(encoding='utf-8'))
G=P['gse'];R=P['root']
SILVER=Color(.68,.74,.81);GOLD=Color(.79,.58,.24);TEAL=Color(.08,.54,.47)
ORANGE=Color(.96,.39,.09);DARK=Color(.18,.23,.29);BLUE=Color(.12,.38,.65)
ON='ONBOARD_HARDWARE_CANDIDATE';GSE='GROUND_SUPPORT_EQUIPMENT';HW='STANDARD_HARDWARE_GEOMETRY_CANDIDATE';ENV='FUNCTIONAL_ENVELOPE'

def loc(T):
    tr=gp_Trsf();tr.SetValues(*np.asarray(T)[:3,:4].ravel().tolist());return Location(tr)
def box(size,xyz=(0,0,0)):return Box(*size).moved(Location(tuple(xyz)))
def tube(size,wall,axis='z'):
    inner=list(size)
    for i in range(3):inner[i]+=(2 if 'xyz'[i]==axis else -2*wall)
    return Box(*size)-Box(*inner)
def bore(shape,diam,height,xyz,axis=(0,0,1)):
    return shape-Cylinder(diam/2,height).moved(Plane(origin=tuple(xyz),z_dir=axis).location)
def plate(size,holes=()):
    shape=Box(*size)
    for x,y,d in holes:shape=bore(shape,d,size[2]+2,(x,y,0))
    return shape
def slot(shape,center,length,width,axis='x',depth=30):
    x,y,z=center;delta=(length-width)/2
    cut=box((length-width,width,depth) if axis=='x' else (width,length-width,depth),center)
    for side in [-1,1]:cut=cut+Cylinder(width/2,depth).moved(Location((x+side*delta if axis=='x' else x,y+side*delta if axis=='y' else y,z)))
    return shape-cut
def ring(od,id_,height):return Cylinder(od/2,height)-Cylinder(id_/2,height+2)
def screw(d,length,head_d,head_h):
    # Local z=0 is the underside of the head; shaft points toward -z.
    return Cylinder(d/2,length).moved(Location((0,0,-length/2)))+Cylinder(head_d/2,head_h).moved(Location((0,0,head_h/2)))
def pin(d,length):return Cylinder(d/2,length)
def pad_shape(row,bottom_z,xstation):
    xy=np.array(row['top_corners_mm']);xy[:,0]-=xstation
    xy[:,2]-=bottom_z
    low=xy.copy();low[:,2]=0
    return Solid.make_loft([Wire.make_polygon([tuple(p) for p in low],close=True),Wire.make_polygon([tuple(p) for p in xy],close=True)])
def hull_shape(vertices):
    h=ConvexHull(vertices);faces=[]
    for ids,eq in zip(h.simplices,h.equations):
        tri=vertices[ids]
        if np.dot(np.cross(tri[1]-tri[0],tri[2]-tri[0]),eq[:3])<0:tri=tri[::-1]
        faces.append(Face(Wire.make_polygon([tuple(x) for x in tri],close=True)))
    return Solid(Shell(faces))
def bounds(s):
    b=s.bounding_box();return {'min_mm':list(b.min),'max_mm':list(b.max),'size_mm':list(b.size)}

def build(state='held',include_context=False,write_parts=False):
    if state not in ['held','released']:raise ValueError(state)
    released=state=='released';slide=G['Y_slide_stroke_mm'] if released else 0
    drop=G['shoe_release_drop_mm'] if released else 0
    lift=G['upper_pad_release_lift_mm'] if released else 0
    asm=AssemblyHelper('WP02_KEY_'+state.upper());records=[];unique={};placed={};interfaces=[]
    def add(local,pn,xyz=(0,0,0),name=None,classification=GSE,color=SILVER,basis='NEW_PARAMETRIC_CANDIDATE',axis=None):
        world=local.moved(Location(tuple(xyz)) if axis is None else Plane(origin=tuple(xyz),z_dir=axis).location)
        label=name or pn;obj=asm.add(world,label,color=color);placed[label]=obj
        unique.setdefault(pn,(local,classification,basis))
        records.append({'instance':label,'part_number':pn,'classification':classification,'geometry_basis':basis,'solid_count':len(obj.solids()),'volume_mm3':sum(s.volume for s in obj.solids()),'origin_S_mm':list(xyz),'axis_S':axis,'mass_kg':None if classification in [ENV,HW] or 'PAD' in pn else sum(s.volume for s in obj.solids())*R['density_kg_mm3'],'mass_basis':'ASSUMED_ALUMINUM_DENSITY_NOT_AS_BUILT' if classification not in [ENV,HW] and 'PAD' not in pn else 'NOT_ALLOCATED',**bounds(obj)})
        return obj
    # Flight-candidate root frame, with actual separate interfaces.
    L,W,H=P['bus_mm']
    for sy in [-1,1]:
        for sz in [-1,1]:
            rail=tube((354,12,12),2,'x')
            for x in [-164,164]:rail=bore(rail,4.5,16,(x,0,0))
            add(rail,'WP01-RB-LONGERON-R2',(0,sy*107.15,sz*107.15),f'RB_longeron_{sy}_{sz}',ON)
    for sx in [-1,1]:
        f=Box(6,W,H)-Box(8,202.3,202.3)
        for y in [-107.15,107.15]:
            for z in [-107.15,107.15]:f=bore(f,4.5,8,(0,y,z),(1,0,0))
        add(f,'WP01-RB-END-FRAME-R2',(sx*180,0,0),f'RB_end_frame_{sx}',ON)
        for sy in [-1,1]:
            for sz in [-1,1]:
                plug=box((20,9.8,9.8));plug=bore(plug,3.3,24,(0,0,0),(1,0,0));plug=bore(plug,4.5,12,(sx*-3,0,0))
                add(plug,'WP01-RB-END-PLUG-R2',(sx*167,sy*107.15,sz*107.15),f'RB_end_plug_{sx}_{sy}_{sz}',ON)
                add(screw(4,22,7,4),'WP01-MT-M4X22-ENVELOPE',(sx*183,sy*107.15,sz*107.15),f'RB_end_screw_{sx}_{sy}_{sz}',HW,DARK,axis=(sx,0,0))
    holes=[(x,y,6.6) for x,y in R['M6_local_xy_mm']]+[(x-90,y,4.5) for x,y in R['pillar_xy_mm']]
    for i in range(8):
        a=math.radians(22.5+45*i);holes.append((62.5*math.cos(a),62.5*math.sin(a),12))
    holes.append((0,0,44));bridge=plate(R['bridge_mm'],holes)
    rootplate=add(bridge,'WP01-RB-BRIDGE-R2',R['bridge_center_mm'],classification=ON,color=GOLD)
    for x in R['crossbeam_x_mm']:
        beam=plate(R['upper_crossbeam_mm'],[(0,y,6.6) for y in [-70,70]]+[(0,y,4.5) for y in [-94.15,94.15]])
        add(beam,'WP01-RB-UPPER-BEAM-R2',(x,0,101.15),f'RB_upper_beam_{x}',ON,GOLD)
        low=plate(R['lower_crossbeam_mm'],[(0,y,4.5) for y in [-94.15,94.15]])
        add(low,'WP01-RB-LOWER-BEAM-R2',(x,0,-104.15),f'RB_lower_beam_{x}',ON,GOLD)
    for i,(x,y) in enumerate(R['pillar_xy_mm']):
        length=193.3;p=tube((14,14,length),2)
        add(p,'WP01-RB-PILLAR-R2',(x,y,-1.5),f'RB_pillar_{i}',ON,GOLD)
        for end,z in [('top',87.15),('bottom',-90.15)]:
            plug=plate((9.9,9.9,16),[(0,0,4.5)])
            add(plug,'WP01-RB-PILLAR-PLUG-R2',(x,y,z),f'RB_pillar_plug_{i}_{end}',ON,GOLD)
        shim=plate((14,14,3),[(0,0,4.5)])
        add(shim,'WP01-RB-LOWER-SPACER-R2',(x,y,-99.65),f'RB_lower_spacer_{i}',ON)
        add(screw(4,228,7,4),'WP01-MT-M4-TIEROD228-ENVELOPE',(x,y,114.15),f'RB_pillar_tierod_{i}',HW,DARK)
        add(ring(9,4.5,1),'WP01-MT-WASHER4-ENVELOPE',(x,y,113.65),f'RB_pillar_top_washer_{i}',HW,DARK)
        add(ring(9,4.5,1),'WP01-MT-WASHER4-ENVELOPE',(x,y,-107.65),f'RB_pillar_bottom_washer_{i}',HW,DARK)
        add(ring(7,4.2,4),'WP01-MT-NUT4-ENVELOPE',(x,y,-110.15),f'RB_pillar_nut_{i}',HW,DARK)
        # Continuous tie rod carries tension; tube/end faces carry compression.
        # No transverse pin intersects its axial load path.
    ma=add(import_step(HERE/'inputs/m3r_a.step'),'WP01-MT-M3RA-REUSED',(90,0,125.15),classification=ON,color=GOLD,basis='UNCHANGED_IMPORTED_NOMINAL_BREP')
    mb=add(import_step(HERE/'inputs/m3r_b.step'),'WP01-MT-M3RB-REUSED',(90,0,125.15),classification=ON,color=GOLD,basis='UNCHANGED_IMPORTED_NOMINAL_BREP')
    asm.rigid_frame(ma,'nominal_B601_bearing_local',Location((0,0,2.405)))
    asm.rigid_frame(rootplate,'roof_seat_local',Location((0,0,3)))
    for x,y in R['M6_local_xy_mm']:
        X=x+90
        add(ring(12,6.6,1),'WP01-MT-WASHER6-ENVELOPE',(X,y,125.65),f'M6_top_washer_{x}_{y}',HW,DARK)
        add(screw(6,40,10,6),'WP01-MT-M6X40-ENVELOPE',(X,y,126.15),f'M6_root_bolt_{x}_{y}',HW,DARK)
        add(ring(12,6.6,1),'WP01-MT-WASHER6-ENVELOPE',(X,y,94.65),f'M6_bottom_washer_{x}_{y}',HW,DARK)
        add(ring(10,6.2,5),'WP01-MT-NUT6-ENVELOPE',(X,y,91.15),f'M6_root_nut_{x}_{y}',HW,DARK)
    for i in range(8):
        a=math.radians(22.5+45*i);x=90+62.5*math.cos(a);y=62.5*math.sin(a)
        add(screw(5,25,8.5,5),'WP01-MT-M5X25-ENVELOPE',(x,y,128.555),f'M5_interstage_bolt_{i}',HW,DARK)
        add(ring(10,5.5,1),'WP01-MT-WASHER5-ENVELOPE',(x,y,128.055),f'M5_top_washer_{i}',HW,DARK)
        add(ring(10,5.5,1),'WP01-MT-WASHER5-ENVELOPE',(x,y,112.65),f'M5_bottom_washer_{i}',HW,DARK)
        add(ring(8.5,5.2,4),'WP01-MT-NUT5-ENVELOPE',(x,y,110.15),f'M5_interstage_nut_{i}',HW,DARK)
    # Standalone GSE; no tall posts through spacecraft decks.
    gseholes=sorted(set((x if y<0 else G['shared_positive_post_x_mm'],y-105,8.5) for x in G['station_x_mm'] for y in G['post_y_mm']))
    base=plate(G['base_mm'],gseholes)
    add(base,'WP01-GSE-BASE-R2',G['base_center_mm'],color=DARK)
    for sx in [-1,1]:
        for sy in [-1,1]:
            foot=plate((24,24,27),[(0,0,6.6)])
            add(foot,'WP01-GSE-FRAME-FOOT-R2',(sx*180,sy*107.15,-126.65),f'GSE_frame_foot_{sx}_{sy}',color=BLUE)
    for k,(station,x) in enumerate(zip(C['stations'],G['station_x_mm'])):
        name=station['station'];shoe=station['shoe_top_z_mm'];maxz=G['parking_local_arm_max_z_mm'][k]
        for y in G['post_y_mm']:
            if y>0 and k>0:continue
            postx=x if y<0 else G['shared_positive_post_x_mm']
            h=G['post_top_z_mm']-G['post_base_z_mm']
            add(tube((20,20,h),2),f'WP01-GSE-TOWER-R2',(postx,y,(G['post_top_z_mm']+G['post_base_z_mm'])/2),f'{name}_tower_{y}',color=BLUE)
            add(plate((40,40,8),[(0,0,8.5)]),'WP01-GSE-TOWER-FOOT-R2',(postx,y,-136.15),f'{name}_tower_foot_{y}',color=BLUE)
        # Fixed saddle support beam and independent screw-driven vertical carrier.
        fixedtop=shoe-55
        fixed=plate((24,330,12),[(0,y,6.6) for y in [-155,155]]+[(0,0,12)])
        add(fixed,f'WP01-S{name}-FIXED-CROSSBEAM-R2',(x,0,fixedtop-6),color=BLUE)
        offset=G['shared_positive_post_x_mm']-x
        add(box((offset,20,12)),f'WP01-HR-LOWER-OFFSET-{name}-R2',(x+offset/2,155,fixedtop-6),f'{name}_lower_offset_bridge',color=BLUE)
        lower=plate(G['shoe_crossbeam_mm'],[(0,y,6.6) for y in [-30,30]])
        if name=='B':
            for y in [-30,30]:lower=slot(lower,(0,y,0),14.6,6.6,'x',12)
        add(lower,f'WP01-S{name}-ADJUSTABLE-SHOE-R2',(x,0,shoe-4-drop),color=TEAL)
        for j,pad in enumerate(station['pads']):
            add(pad_shape(pad,shoe,x),f'WP01-S{name}-PAD-{j+1}-R2',(x,0,shoe-drop),color=TEAL,basis='ACCEPTED_STL_LOCAL_PLANE_CANDIDATE_NOT_MEASURED')
        # Round guides, bushings and a manual jack. +8/-8 setup independent of -30 release.
        for y in [-30,30]:
            add(pin(6,80),'WP01-HR-Z-GUIDE6-R2',(x,y,shoe-40),f'{name}_lower_guide_{y}',HW,DARK)
            add(ring(10,6.4,12),'WP01-HR-Z-BUSH-R2',(x,y,shoe-16-drop),f'{name}_lower_bush_{y}',HW,GOLD)
        add(pin(10,85),'WP01-HR-Z-JACK10-R2',(x,0,shoe-39-drop),f'{name}_lower_jackscrew',HW,DARK)
        add(ring(22,10.6,12),'WP01-HR-Z-NUT-BLOCK-R2',(x,0,fixedtop-6),f'{name}_lower_nut_block',HW,GOLD)
        # A has setup lateral buttons; B remains x-floating and has no opposed rigid clamp.
        if name=='A':
            for side in [-1,1]:
                bracket=box((12,8,24))-box((14,5,14),(0,-side*3,5))
                add(bracket,'WP01-SA-Y-LOCATOR-BRACKET-R2',(x,side*41,shoe+4-drop),f'A_Y_locator_{side}',color=TEAL)
                add(screw(4,12,7,4),'WP01-MT-M4X12-ENVELOPE',(x,side*45,shoe+8-drop),f'A_Y_locator_screw_{side}',HW,DARK,axis=(0,side,0))
        # Rail supported from GSE tower collars; carrier is captive around a square guide.
        railz=maxz+65
        rail=box((20,250,14));fixedrail=add(rail,'WP01-HR-Y-RAIL-R2',(x,200,railz),f'{name}_fixed_Y_rail',color=BLUE)
        for y in ([155,315] if k==0 else []):
            collar=box((36,36,24))-box((20.4,20.4,26))
            add(collar,'WP01-HR-TOWER-COLLAR-R2',(40,y,G['overhead_z_mm']),f'{name}_rail_collar_{y}',color=BLUE)
            add(box((155,20,12)),'WP01-HR-OVERHEAD-OFFSET-R2',(-37.5,y,G['overhead_z_mm']),f'{name}_overhead_offset_{y}',color=BLUE)
        add(box((20,266,12)),'WP01-HR-OVERHEAD-LONGITUDINAL-R2',(x,200,G['overhead_z_mm']),f'{name}_overhead_longitudinal',color=BLUE)
        for y in [78,322]:
            hh=G['overhead_z_mm']-6-(railz+7)
            add(box((20,6,hh)),f'WP01-HR-END-HANGER-{name}-R2',(x,y,railz+7+hh/2),f'{name}_rail_end_hanger_{y}',color=BLUE)
        carrier=box((40,36,36))-box((20.4,38,14.4))
        carrier=bore(carrier,6.4,44,(0,0,12),(1,0,0))
        mover=add(carrier,'WP01-HR-Y-CARRIER-R2',(x,110+slide,railz),f'{name}_Y_carrier',color=ORANGE)
        # These native frames record the Y DOF; explicit transformations are the placement authority.
        asm.linear_frame(fixedrail,'Y_axis_local',Axis((0,-90,0),(0,1,0)),linear_range=(0,180))
        asm.rigid_frame(mover,'carrier_zero_local',Location((0,0,0)))
        # Cantilever is below the carrier, above the complete folded-arm local envelope.
        arm=plate((18,122,8),[(0,-49,10.6),(0,-4,4.5)])
        add(arm,'WP01-HR-CANTILEVER-R2',(x,49+slide,maxz+36),f'{name}_cantilever',color=ORANGE)
        add(box((18,24,7)),'WP01-HR-CARRIER-NECK-R2',(x,110+slide,maxz+43.5),f'{name}_carrier_neck',color=ORANGE)
        keeper=plate(G['keeper_bar_mm'],[(0,y,4.5) for y in [-45,45]]+[(0,0,10.6)])
        add(keeper,'WP01-HR-KEEPER-CROSSBAR-R2',(x,slide,maxz+24),f'{name}_keeper_crossbar',color=ORANGE)
        add(plate((18,24,4),[(0,0,10.6)]),'WP01-HR-KEEPER-NECK-R2',(x,slide,maxz+30),f'{name}_keeper_neck',color=ORANGE)
        # Upper contact floats in Z and lifts before the Y stage can move.
        upper=plate(G['upper_pad_mm'],[(0,y,4.5) for y in [-45,45]])
        add(upper,'WP01-HR-UPPER-PAD-R2',(x,slide,maxz+2+lift),f'{name}_upper_contact_pad',color=TEAL,basis='WHOLE_FOLDED_ARM_LOCAL_MAX_TANGENCY; CONTACT_LINK3_UNQUALIFIED')
        for y in [-45,45]:
            add(pin(4,26),'WP01-HR-UPPER-GUIDE4-R2',(x,y+slide,maxz+17+lift),f'{name}_upper_guide_{y}',HW,DARK)
        add(pin(10,32),'WP01-HR-UPPER-JACK10-R2',(x,slide,maxz+20+lift),f'{name}_upper_jack',HW,DARK)
        # Independent cross-pin latch, a hard stop, captive ends and manually driven screw.
        for y in [78,322]:
            add(box((42,6,30)),'WP01-HR-Y-ENDSTOP-R2',(x,y,railz),f'{name}_Y_endstop_{y}',color=BLUE)
        latch=box((12,20,22));latch=bore(latch,6.4,18,(0,0,5),(1,0,0))
        add(latch,'WP01-HR-LATCH-CLEVIS-R2',(x-26,110,railz+7),f'{name}_fixed_latch_clevis',color=BLUE)
        # A real stationary path connects the latch to the suspended fixed frame.
        lh=G['overhead_z_mm']-6-(railz+18)
        add(box((12,20,lh)),f'WP01-HR-LATCH-HANGER-{name}-R2',(x-26,110,railz+18+lh/2),f'{name}_latch_fixed_hanger',color=BLUE)
        add(box((22,20,12)),'WP01-HR-LATCH-TOP-BRIDGE-R2',(x-21,110,G['overhead_z_mm']),f'{name}_latch_top_bridge',color=BLUE)
        lockpin=pin(6,64)+Cylinder(6,4).moved(Location((0,0,-34)))
        add(lockpin,'WP01-HR-CAPTIVE-LOCK-PIN6-R2',(x-12-(G['latch_pin_withdrawal_mm'] if released else 0),110,railz+12),f'{name}_lock_pin',HW,DARK,axis=(1,0,0))
        add(ring(16,12.4,58),'WP01-HR-PIN-CAPTIVE-HOUSING-R2',(x-70,110,railz+12),f'{name}_pin_captive_housing',color=BLUE,axis=(1,0,0))
        for xx in [-100,-40]:add(ring(16,6.4,2),'WP01-HR-PIN-HOUSING-ENDCAP-R2',(x+xx,110,railz+12),f'{name}_pin_endcap_{xx}',color=BLUE,axis=(1,0,0))
        add(box((68,16,4)),'WP01-HR-PIN-HOUSING-SEAT-R2',(x-66,110,railz+2),f'{name}_pin_housing_seat',color=BLUE)
        add(pin(8,270),'WP01-HR-MANUAL-LEADSCREW8-R2',(x+32,200,railz-5),f'{name}_manual_Y_screw',HW,DARK,axis=(0,1,0))
        nut=box((12,20,12));nut=bore(nut,8.4,24,(0,0,0),(0,1,0))
        add(nut,'WP01-HR-Y-DRIVE-NUT-R2',(x+32,110+slide,railz-5),f'{name}_Y_drive_nut',HW,GOLD)
        drive_link=box((12,20,8));drive_link=bore(drive_link,8.6,24,(6,0,4),(0,1,0))
        add(drive_link,'WP01-HR-DRIVE-NUT-LINK-R2',(x+26,110+slide,railz-9),f'{name}_nut_carrier_link',color=ORANGE)
        for y in [67,333]:
            bearing=box((16,8,18));bearing=bore(bearing,8.6,12,(0,0,0),(0,1,0))
            add(bearing,'WP01-HR-SCREW-END-BEARING-R2',(x+32,y,railz-5),f'{name}_screw_bearing_{y}',HW,GOLD)
            between=73 if y==67 else 327
            bmount=box((11,8,18),(18.5,y,0))+box((10,4,18),(21,between,0))
            add(bmount,f'WP01-HR-SCREW-END-MOUNT-{y}-R2',(x,0,railz-5),f'{name}_screw_end_mount_{y}',color=BLUE)
        # Sensor mount and target are mechanical parts; no selected sensor model is fabricated.
        for y,label in [(78,110),(322,290)]:
            sb=plate((20,6,3),[(-6,0,3.4),(6,0,3.4)])+box((20,3,18),(0,-1.5 if y==78 else 1.5,10.5))
            add(sb,f'WP01-HS-END-SWITCH-{label}-R2',(x,y,railz+16.5),f'{name}_switch_bracket_{label}',color=BLUE)
        flag=plate((12,12,2),[(-3,0,3.4),(3,0,3.4)])
        add(flag,'WP01-HS-CARRIER-FLAG-R2',(x,110+slide,railz+19),f'{name}_carrier_flag',color=ORANGE)
        interfaces.append({'station':name,'shoe_drop_mm':drop,'upper_pad_lift_mm':lift,'Y_slide_mm':slide,'upper_pad_contact_target':'link3','hardware_contact_proven':False,'GSE_return_to_park':'Independent arm support maintained; reverse sequence and manual reset required.'})
    # Fixed root cable hardware: split clamp, bracket and open slot/grommet.
    h=P['harness'];d=h['proxy_od_mm'];anchor=h['root_fixed_anchor_S_mm']
    for suffix,sgn in [('LOWER',-1),('UPPER',1)]:
        clamp=plate((26,14,6),[(-9,0,3.4),(9,0,3.4)])
        clamp=bore(clamp,d,18,(0,0,-sgn*3),(0,1,0))
        add(clamp,f'WP01-HB-SPLIT-CLAMP-{suffix}-R2',(anchor[0],anchor[1],anchor[2]+sgn*3),color=TEAL)
    bracket=plate((40,70,4),[(-9,-28,3.4),(9,-28,3.4),(-12,25,4.5),(12,25,4.5)])
    add(bracket,'WP01-HB-ROOT-OUTRIGGER-R2',(90,-113,102),classification=ON,color=GOLD)
    add(box((26,14,4)),'WP01-HB-CLAMP-SPACER-R2',(90,-140,106),classification=ON,color=GOLD)
    connector=plate((45,30,4),[(-17,0,4.5),(17,0,4.5)])
    connector=slot(connector,(0,0,0),24,12,'x',8)
    add(connector,'WP01-HB-CONNECTOR-SLIDE-BRACKET-R2',(90,-120,160),classification=ON,color=GOLD,basis='ADJUSTABLE_INTERFACE_BLANK; OEM_TAIL_NOT_BOUND')
    mast=box((4,24,54));mast=bore(mast,4.5,6,(0,0,-20),(1,0,0));mast=bore(mast,4.5,6,(0,0,20),(1,0,0))
    add(mast,'WP01-HB-CONNECTOR-MAST-R2',(110.5,-120,131),classification=ON,color=GOLD)
    # Optional context hulls help read this key assembly. They have no mating authority.
    if include_context:
        sys.path.insert(0,str(HERE.parent/'service_robot_wp01_20260905'))
        from kinematics import raw_vertices,fk
        verts=raw_vertices();frames=fk(P['q_parking_deg'],np.array(P['T_S_A0']),P['finger_mm'])
        for n in ['link2','link3']:
            shp=hull_shape(verts[n]);add(shp.moved(loc(frames[n])),f'CONTEXT_{n}_CONVEX_HULL',classification=ENV,color=Color(.43,.5,.58,.45),basis='ACCEPTED_STL_CONVEX_HULL_DISPLAY_ONLY; NO_CONTACT_AUTHORITY')
        if (HERE/'results/HARNESS_ANALYSIS.json').exists():
            hr=json.loads((HERE/'results/HARNESS_ANALYSIS.json').read_text())
            for n,row in hr['poses'][0]['loops'].items():
                pts=row['constant_curvature_candidate']['centerline_points_mm']
                edge=Edge.make_three_point_arc(pts[0],pts[50],pts[-1])
                profile=Circle(P['harness']['proxy_od_mm']/2).moved(Plane(origin=tuple(pts[0]),z_dir=edge.tangent_at(0)).location)
                cable=sweep(profile,path=edge)
                add(cable,'CONTEXT_HARNESS_'+n,classification=ENV,color=ORANGE,basis='CONSTANT_LENGTH_CURVATURE_PROXY; OD_AND_OUTLET_TANGENTS_NOT_MEASURED')
    model=asm.build()
    receipt={'configuration':P['configuration_id'],'state':state,'physical_state':P['physical_state'],'parts':records,'unique_part_count':len(unique),'occurrence_count':len(records),'solid_count':sum(r['solid_count'] for r in records),'context_included':include_context,'assembly_bounds':bounds(model),'mechanism':interfaces,'classification_totals':{c:{'occurrences':sum(r['classification']==c for r in records),'CAD_assumed_Al_mass_kg':sum(r['mass_kg'] or 0 for r in records if r['classification']==c)} for c in [ON,GSE,HW,ENV]},'mass_complete':False,'native_STEP_constraints':False,'thread_engagement_preload_and_materials_verified':False}
    (HERE/'results'/f'{state}{"_context" if include_context else ""}_build_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    if write_parts:
        for pn,(local,classification,basis) in unique.items():
            if classification in [ENV,HW] or basis=='UNCHANGED_IMPORTED_NOMINAL_BREP':continue
            local.label=pn;export_step(local,HERE/'parts'/f'{pn}.step')
        with (HERE/'BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
            keys=['part_number','quantity','classification','geometry_basis','part_STEP','manufacturing_status'];w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
            for pn,(local,classification,basis) in unique.items():
                w.writerow(dict(part_number=pn,quantity=sum(r['part_number']==pn for r in records),classification=classification,geometry_basis=basis,part_STEP=f'parts/{pn}.step' if (HERE/'parts'/f'{pn}.step').exists() else 'INPUT_STEP_OR_ASSEMBLY_ENVELOPE',manufacturing_status='NOT_FOR_MANUFACTURE'))
    return model,placed,unique

if __name__=='__main__':
    model,parts,unique=build('held',write_parts=True)
    print('Parts exported:',len(unique),'occurrences',len(parts))
