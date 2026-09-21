"""Bottom fixed radiator and real deck mount, S frame mm. Source-first candidate."""
from pathlib import Path
import json,hashlib
from build123d import Box,Cylinder,Cone,Pos,Rot,Compound,Color,Location,Align,RegularPolygon,extrude,Plane
import math
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper

A=Path(__file__).resolve().parents[1]
def parameters():return json.loads((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_text())
def bore(x,y,d,z0,z1):return Pos(x,y,(z0+z1)/2)*Cylinder(d/2,z1-z0)

def radiator():
    p=parameters();z0=p['outer_z_mm'];zt=p['plate_top_z_mm'];s=Pos(0,0,(z0+zt)/2)*Box(*p['base_size_mm'])
    c=p.get('chb_path')
    if c and c['enabled']:
        x,y=c['center_xy_mm'];w,h=c['seat_size_mm'];zs=c['seat_z_mm']
        s=s+Pos(x,y,(zt-.01+zs)/2)*Box(w,h,zs-zt+.01)
        ya,yb=c['finger_riser_abs_y_mm'];za,zb=c['finger_arm_z_mm'];end=c['wall_seat_abs_y_mm']-c['wall_TIM_thickness_mm']
        for sign in [-1,1]:
            s=s+Pos(x,sign*(ya+yb)/2,(zt-.01+zb)/2)*Box(w,yb-ya,zb-zt+.01)
            s=s+Pos(x,sign*(ya+end)/2,(za+zb)/2)*Box(w,end-ya,zb-za)
            for xx,zz in c['wall_screw_centers_xz_mm']:
                lo=end-c['finger_thread_nominal_depth_mm'];hi=end+1
                s=s-Pos(xx,sign*(lo+hi)/2,zz)*Rot(90,0,0)*Cylinder(c['finger_thread_nominal_major_d_mm']/2,hi-lo)
    for i,(x,y) in enumerate(p['mount_centers_xy_mm']):
        s=s+bore(x,y,2*p['boss_radius_mm'],zt-.01,p['mount_support_z_mm'][i])
    q=p['beam_reliefs']
    for x in q['x_mm']:s=s-Pos(x,0,(q['bottom_z_mm']+zt+1)/2)*Box(q['width_mm'],q['length_mm'],zt+1-q['bottom_z_mm'])
    q=p['pillar_edge_notches']
    for x in q['x_mm']:
        for y in q['y_mm']:s=s-bore(x,y,q['diameter_mm'],z0-1,zt+1)
    for k in ['lower_fastener_blind_pockets','MIPS_blind_pockets']:
        q=p[k]
        for x in q['x_mm']:
            for y in q['y_mm']:s=s-bore(x,y,q['diameter_mm'],q['bottom_z_mm'],zt+1)
    for x,y in p['mount_centers_xy_mm']:
        s=s-bore(x,y,p['bore_diameter_mm'],z0-1,p['deck_bottom_z_mm']+1)
        # ISO10642 nominal90deg seat, cone plane datum equals head plane.
        h=(p['countersink_outer_diameter_mm']-p['bore_diameter_mm'])/2
        s=s-Pos(x,y,z0+h/2)*Cone(p['countersink_outer_diameter_mm']/2,p['bore_diameter_mm']/2,h)
    if c and c['enabled']:
        x,y=c['center_xy_mm']
        for dx in c['oem_hole_x_offsets_mm']:
            for dy in c['oem_hole_y_offsets_mm']:
                s=s-bore(x+dx,y+dy,c['clearance_bore_mm'],z0-1,c['seat_z_mm']+1)
                h=(p['countersink_outer_diameter_mm']-c['clearance_bore_mm'])/2
                s=s-Pos(x+dx,y+dy,z0+h/2)*Cone(p['countersink_outer_diameter_mm']/2,c['clearance_bore_mm']/2,h)
    s.label='radiator_spreader__WP10_BOTTOM_FIXED_WITH_INTEGRAL_BOSSES';s.color=Color(.9,.91,.94);return s

def deck():
    p=parameters();q=p['baseline_deck'];path=Path(q['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==q['sha256']
    s=import_step(str(path))
    for x,y in p['mount_centers_xy_mm']:s=s-bore(x,y,p['bore_diameter_mm'],p['deck_bottom_z_mm']-1,p['deck_top_z_mm']+1)
    c=p.get('chb_path')
    if c and c['enabled']:
        x,y=c['deck_window_center_xy_mm'];w,h=c['deck_window_size_mm']
        s=s-Pos(x,y,(p['deck_bottom_z_mm']+p['deck_top_z_mm'])/2)*Box(w,h,p['deck_top_z_mm']-p['deck_bottom_z_mm']+2)
    s.label='lower_equipment_deck_B__BOTTOM_RADIATOR_MOUNT_BORES';s.color=Color(.72,.75,.79);return s

def angle(key):
    p=parameters();r=p['baseline_angles'][key];path=Path(r['path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['sha256']
    T=r['T_S_step'];assert all(abs(T[i][j]-(1 if i==j else 0))<1e-9 for i in range(3) for j in range(3))
    s=Pos(*[T[i][3] for i in range(3)])*import_step(str(path))
    for i,(x,y) in enumerate(p['mount_centers_xy_mm']):
        if p['mount_support_ids'][i]==key:s=s-bore(x,y,p['bore_diameter_mm'],-105,-97)
    s.label=key+'__BOTTOM_RADIATOR_CLAMP_BORES';return s

def washer():
    # Catalog washer is rejected (actual1.1mm vs listed0.55). Explicit nominal
    # reconstruction, not an unaltered OEM solid or a measured delivered part.
    q=parameters()['hardware'];t=q['washer_thickness_mm']
    s=Pos(0,0,t/2)*(Cylinder(q['washer_od_mm']/2,t)-Cylinder(q['washer_id_mm']/2,t+1))
    s.label='M3_WASHER_NOMINAL_RECONSTRUCTED_CATALOG_ERROR_CORRECTED';return s

def screw():
    q=parameters()['hardware'];h=q['screw_head_height_mm'];L=q['screw_length_mm']
    s=Pos(0,0,h/2)*Cone(q['screw_head_diameter_mm']/2,1.5,h)
    s=s+Pos(0,0,(h+L)/2)*Cylinder(1.5,L-h)
    s=s-extrude(RegularPolygon(q['screw_socket_af_mm']/math.sqrt(3),6),amount=q['screw_socket_depth_mm'])
    s.label='M3X20_ISO10642_NOMINAL_PROJECT_MODEL__THREAD_SIMPLIFIED';return s
def nut():
    q=parameters()['hardware'];h=q['nut_height_mm']
    s=extrude(RegularPolygon(q['nut_af_mm']/math.sqrt(3),6,rotation=30),amount=h)-bore(0,0,3,-1,h+1)
    s.label='M3_DIN934_NOMINAL_PROJECT_MODEL__THREAD_SIMPLIFIED';return s

def wall_tim():
    c=parameters()['chb_path'];w,h=c['wall_TIM_size_mm'];t=c['wall_TIM_thickness_mm']
    s=Pos(0,0,t/2)*Box(w,h,t);cx,cz=c['wall_contact_center_xz_mm']
    for x,z in c['wall_screw_centers_xz_mm']:s=s-bore(x-cx,z-cz,4.5,-1,t+1)
    s.label='WP10_COLD_FINGER_'+c.get('TIM_family','TSP1600S').replace(' ','_')+'_PROJECT_CUT';s.color=Color(.1,.4,.85);return s

def cold_path_hardware_rows():
    p=parameters();c=p.get('chb_path');out=[]
    if not c or not c['enabled']:return out
    x,y=c['center_xy_mm']
    for i,(dx,dy) in enumerate(( (dx,dy) for dx in c['oem_hole_x_offsets_mm'] for dy in c['oem_hole_y_offsets_mm'])):
        out.append(dict(id=f'WP10_CHB_{i}_SCREW',kind='screw',T=[[1,0,0,x+dx],[0,1,0,y+dy],[0,0,1,p['outer_z_mm']],[0,0,0,1]]))
    for sign in [-1,1]:
        x,z=c['wall_contact_center_xz_mm'];y=sign*c['wall_seat_abs_y_mm']
        out.append(dict(id=f'WP10_COLD_{sign}_TIM',kind='tim',T=[[1,0,0,x],[0,0,-sign,y],[0,sign,0,z],[0,0,0,1]]))
        for i,(x,z) in enumerate(c['wall_screw_centers_xz_mm']):
            out.append(dict(id=f'WP10_COLD_{sign}_{i}_SCREW',kind='screw',T=[[1,0,0,x],[0,0,-sign,sign*113.15],[0,sign,0,z],[0,0,0,1]]))
    return out
def hardware_rows():
    p=parameters();out=[]
    for i,(x,y) in enumerate(p['mount_centers_xy_mm']):
        for tag,path,z,rot in [('SCREW','mechanical/bottom_mount_screw.step',p['outer_z_mm'],False),('WASHER','mechanical/bottom_mount_washer.step',p['deck_top_z_mm'],False),('NUT','mechanical/bottom_mount_nut.step',p['deck_top_z_mm']+p['hardware']['washer_thickness_mm'],False)]:
            T=[[1,0,0,x],[0,-1 if rot else 1,0,y],[0,0,-1 if rot else 1,z],[0,0,0,1]]
            out.append(dict(id=f'WP10_BOTTOM_{i}_{tag}',step_path=str(A/path),T_S_step=T,source_sha256=hashlib.sha256((A/path).read_bytes()).hexdigest(),representation_role='PUBLIC_DIMENSION_BOUND_PROJECT_NOMINAL_GEOMETRY'))
    return out

def assembly():
    p=parameters();asm=AssemblyHelper('WP10_BOTTOM_RADIATOR_AND_DECK_MOUNT')
    plate=asm.add(radiator(),'radiator_spreader');d=asm.add(deck(),'lower_equipment_deck_B')
    asm.face_to_face(asm.rigid_frame(plate,'S_origin',Location()),asm.rigid_frame(d,'S_origin',Location()))
    for key in p['baseline_angles']:
        ang=asm.add(angle(key),key)
        asm.face_to_face(asm.rigid_frame(plate,key+'_S',Location()),asm.rigid_frame(ang,'S_origin',Location()))
    for i,(x,y) in enumerate(p['mount_centers_xy_mm']):
        b=asm.add(screw(),f'WP10_BOTTOM_{i}_SCREW');w=asm.add(washer(),f'WP10_BOTTOM_{i}_WASHER');n=asm.add(nut(),f'WP10_BOTTOM_{i}_NUT')
        # All local datums are declared before any of the hardware is moved.
        bh=asm.rigid_frame(b,'head_plane',Location());wb=asm.rigid_frame(w,'under_face',Location());wt=asm.rigid_frame(w,'top_face',Location((0,0,p['hardware']['washer_thickness_mm'])))
        nb=asm.rigid_frame(n,'bearing_face',Location())
        ps=asm.rigid_frame(plate,f'seat_{i}',Location((x,y,p['outer_z_mm'])));ds=asm.rigid_frame(d,f'washer_seat_{i}',Location((x,y,p['deck_top_z_mm'])))
        asm.face_to_face(ps,bh);asm.face_to_face(ds,wb);asm.face_to_face(wt,nb)
    for row in cold_path_hardware_rows():
        shape=wall_tim() if row['kind']=='tim' else screw();h=asm.add(shape,row['id']);T=row['T']
        origin=tuple(T[i][3] for i in range(3));xd=tuple(T[i][0] for i in range(3));zd=tuple(T[i][2] for i in range(3))
        local=asm.rigid_frame(h,'nominal_head_or_TIM_face',Location())
        target=asm.rigid_frame(plate,row['id']+'_S_datum',Plane(origin=origin,x_dir=xd,z_dir=zd).location)
        asm.face_to_face(target,local)
    return asm.build()
