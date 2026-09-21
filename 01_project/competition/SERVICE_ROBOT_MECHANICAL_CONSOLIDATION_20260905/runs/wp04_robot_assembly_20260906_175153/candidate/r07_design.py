"""R07 A/B/C nominal mechanical joints; mm in S, no strength/release credit."""
from pathlib import Path
import json, math, hashlib
from build123d import Box, Cylinder, Plane, Location, RegularPolygon, extrude
HERE=Path(__file__).resolve().parent

def box(size,c=(0,0,0)):return Box(*size).moved(Location(tuple(c)))
def cyl(d,h,c=(0,0,0),axis=(0,0,1)):return Cylinder(d/2,h).moved(Plane(origin=tuple(c),z_dir=tuple(axis)).location)
def bore(s,d,h,c=(0,0,0),axis=(0,0,1)):return s-cyl(d,h,c,axis)
def pnt(p,a,t):return [p[i]+a[i]*t for i in range(3)]

def cap_shape(P,x,side,lower=False):
    r=P['r07'];t=r['cap_thickness_mm'];ox=x+(-5 if x==20 else 5)
    z=-99.65 if lower else 113.15+t/2
    inner=box((14,14,t),(x,side*94.15,z))
    outer=box((12,12 if lower else 14,t),(ox,side*(107.15 if lower else 106.15),z))
    s=inner+outer
    for hx,hy in [(x,side*94.15),(r['left_rail_x_mm'] if x==20 else 164,side*107.15)]:s=bore(s,4.5,12,(hx,hy,z))
    return s

def modify_root(P,s,name,pn,xyz,classification):
    """Returns local geometry/position; source root library remains untouched."""
    xyz=list(xyz);name=name or pn
    if name.startswith('RB_longeron_'):
        s=bore(s,4.5,18,(P['r07']['left_rail_x_mm'],0,0))
        if xyz[2]>0:
            for x in P['retention']['station_x_mm']:s=bore(s,4.5,18,(x-3,0,0))
    elif name.startswith('RB_lower_spacer_'):
        x,y,z=xyz;world=cap_shape(P,x,1 if y>0 else -1,True)
        s=world.moved(Location(tuple(-v for v in xyz)))
    elif name.startswith('RB_pillar_tierod_'):
        xyz[2]+=P['r07']['cap_thickness_mm'];L=228+P['r07']['cap_thickness_mm']
        s=cyl(4,L,(0,0,-L/2))+cyl(7,4,(0,0,2))
        s=bore(s,3,2.01,(0,0,3))
    elif name.startswith('RB_pillar_top_washer_'):xyz[2]+=P['r07']['cap_thickness_mm']
    elif name.startswith('RB_end_screw_'):
        sign=1 if xyz[0]>0 else -1
        L=P['r07']['front_axial_length_mm'] if sign>0 else P['r07']['rear_axial_length_mm']
        if sign<0:xyz[0]=-190
        s=cyl(4,L,(0,0,-L/2))+cyl(7,4,(0,0,2))
        s=bore(s,3,2.01,(0,0,3))
    return s,xyz

def modify_web(P,s,side):
    # Edge slots in the shear web clear the new lower-spacer outer wings.
    for x in [15,165]:
        s=s-box((12.5,8,3.5),(x,0,-99.65))
    return s

def modify_wing_pad(P,s):
    for x in [-164,164]:
        for side in [-1,1]:
            s=bore(s,4.5,8,(x,side*107.15,-114.15))
            s=bore(s,9,40,(x,side*107.15,-135.15))
    for x in [-150,150]:
        for side in [-1,1]:s=bore(s,6.5,30,(x,side*106.15,-125.15))
    return s

def retention_lug(s,x,side):
    # Local origin at the unchanged 22x14x12 inner lug center.
    s=s+box((22,12,5),(0,side*13,3.5))
    s=bore(s,4.5,12,(-3,side*13,3.5))
    if x==-40:s=bore(s,6.5,8,(10,side*12,3.5))
    return s

def retention_foot(s):
    # Counterbores recess the heads flush below the rotating mast boss.
    for x,y in [(0,4.85),(-3,-8.15)]:
        s=bore(s,4.5,12,(x,y,-11.5))
        s=bore(s,8,4.6,(x,y,-10.2))
    return s

def connections(P):
    cs=[];r=P['r07'];t=r['cap_thickness_mm'];left=r['left_rail_x_mm']
    for side in [-1,1]:
        for level in [-1,1]:
            y=side*107.15;z=level*107.15
            for x in [left,164,-164]:
                end=x!=left;sign=1 if x>0 else -1
                cap=x!=-164
                if level>0:
                    low=101.15;high=113.15+(t if cap else 0);a=[0,0,1]
                else:
                    low=-115.15 if end else -113.15;high=-98.15 if cap else -101.15;a=[0,0,-1]
                key=f'R07_RAIL_{side}_{level}_{x}'
                mem=[dict(id=f'RB_longeron_{side}_{level}',z_min=z-6,z_max=z+6)]
                if end:mem.append(dict(id=f'RB_end_plug_{sign}_{side}_{level}',z_min=z-3.9,z_max=z+3.9))
                else:mem.append(dict(id=key+'_sleeve',z_min=z-4,z_max=z+4))
                if cap:
                    rootx=20 if x==left else 160
                    idx={(20,-1):0,(20,1):1,(160,-1):2,(160,1):3}[(rootx,side)]
                    capid=f'R07_upper_cap_{rootx}_{side}' if level>0 else f'RB_lower_spacer_{idx}'
                    mem.append(dict(id=capid,z_min=113.15 if level>0 else -101.15,z_max=113.15+t if level>0 else -98.15))
                if level<0 and end:mem.append(dict(id=f'wing_root_fork_{side}_{sign}',z_min=-115.15,z_max=-113.15))
                head=high if level>0 else low;nut=low if level>0 else high
                outer_member=(capid if cap else f'RB_longeron_{side}_{level}') if level>0 else (f'wing_root_fork_{side}_{sign}' if end else f'RB_longeron_{side}_{level}')
                nut_member=f'RB_longeron_{side}_{level}' if level>0 else capid if cap else f'RB_longeron_{side}_{level}'
                L=25 if abs(high-low)>16 else 22 if abs(high-low)>13 else 20
                cs.append(dict(connection_id=key,body_ids=[q['id'] for q in mem],origin_mm=[x,y,0],axis=a,
                    bore_segments=[dict(instance_id=q['id'],origin_mm=[x,y,(q['z_min']+q['z_max'])/2],axis=[0,0,1],length_mm=q['z_max']-q['z_min'],diameter_mm=4.5) for q in mem],
                    head_surface_z_mm=head,nut_surface_z_mm=nut,underhead_length_mm=L,stack_extent_mm=high-low,
                    bearing_faces=[dict(member_id=outer_member,hardware_id=key+'_washer_head',point_mm=[x,y,head],normal=a,inner_d_mm=4.5,outer_d_mm=8),dict(member_id=nut_member,hardware_id=key+'_washer_nut',point_mm=[x,y,nut],normal=[-v for v in a],inner_d_mm=4.5,outer_d_mm=8)],
                    hardware={k:key+'_'+k for k in ['screw','washer_head','washer_nut','nut']},
                    sleeve_id=None if end else key+'_sleeve',state_scope=['parking','released','service'],
                    assembly_stage='BARE_ROOT_FRAME_WITH_WING_ROOT_FORKS; BEFORE_WEBS_DECKS_EQUIPMENT_COVERS_AND_MOVING_WINGS',
                    physical_thread_engagement_mm=None,preload_N=None,strength_pass=None))
    for k,x in enumerate(P['retention']['station_x_mm']):
        for side in [-1,1]:
            for outer in [False,True]:
                key=f'R07_HOLD_{k}_{side}_'+('OUTER' if outer else 'INNER')
                xx=x-3 if outer else x;y=side*(107.15 if outer else 94.15)
                lug=f'hold_roof_lug_{k}_{side*94.15}'
                mem=[dict(instance_id=lug,origin_mm=[xx,y,115.65 if outer else 112.15],axis=[0,0,1],length_mm=5 if outer else 12,diameter_mm=4.5)]
                if outer:
                    mem += [dict(instance_id=f'RB_longeron_{side}_1',origin_mm=[xx,y,107.15],axis=[0,0,1],length_mm=12,diameter_mm=4.5),dict(instance_id=key+'_sleeve',origin_mm=[xx,y,107.15],axis=[0,0,1],length_mm=8,diameter_mm=4.5)]
                    bottom=101.15;nut_member=f'RB_longeron_{side}_1'
                else:
                    mem += [dict(instance_id=f'hold_crossbeam_{k}',origin_mm=[xx,y,101.15],axis=[0,0,1],length_mm=10,diameter_mm=4.5)]
                    bottom=96.15;nut_member=f'hold_crossbeam_{k}'
                top=118.15;head_member=lug
                if side<0:
                    top=120.65;head_member=f'hold_pivot_clevis_{k}'
                    mem += [dict(instance_id=head_member,origin_mm=[xx,y,119.4],axis=[0,0,1],length_mm=2.5,diameter_mm=4.5)]
                cs.append(dict(connection_id=key,body_ids=[m['instance_id'] for m in mem],origin_mm=[xx,y,0],axis=[0,0,1],bore_segments=mem,
                    head_surface_z_mm=top,nut_surface_z_mm=bottom,underhead_length_mm=25 if outer else 30,stack_extent_mm=top-bottom,
                    bearing_faces=[dict(member_id=head_member,hardware_id=key+'_washer_head',point_mm=[xx,y,top],normal=[0,0,1],inner_d_mm=4.5,outer_d_mm=8),dict(member_id=nut_member,hardware_id=key+'_washer_nut',point_mm=[xx,y,bottom],normal=[0,0,-1],inner_d_mm=4.5,outer_d_mm=8)],
                    hardware={kind:key+'_'+kind for kind in ['screw','washer_head','washer_nut','nut']},sleeve_id=key+'_sleeve' if outer else None,state_scope=['parking','released','service'],
                    assembly_stage='BARE_ROOT_FRAME_WITH_FIXED_RETENTION_FOOT_BEFORE_MAST_PINS_AND_MOVING_RETENTION',
                    counterbore=None if side>0 else dict(member_id=head_member,diameter_mm=8,z_range_mm=[120.65,125.15],remaining_floor_mm=2.5,stress_qualification=None),
                    physical_thread_engagement_mm=None,preload_N=None,strength_pass=None))
    return cs

def hardware(P,c):
    p=c['origin_mm'];a=c['axis'];hz=c['head_surface_z_mm'];nz=c['nut_surface_z_mm'];w=.5;nh=3.2
    under=[p[0],p[1],hz+a[2]*w];L=c['underhead_length_mm']
    screw=cyl(4,L,pnt(under,a,-L/2),a)+cyl(7,4,pnt(under,a,2),a)
    screw=screw-cyl(3,2.02,pnt(under,a,3),a)
    washer=lambda zz:cyl(8,w,(p[0],p[1],zz))-cyl(4.5,w+.1,(p[0],p[1],zz))
    nut=extrude(RegularPolygon(7/math.sqrt(3),6,major_radius=True),amount=nh).moved(Location((0,0,-nh/2)))
    nut=bore(nut,4,nh+.1)
    nut=nut.moved(Location((p[0],p[1],nz-a[2]*(w+nh/2))))
    out={c['hardware']['screw']:screw,c['hardware']['washer_head']:washer(hz+a[2]*w/2),c['hardware']['washer_nut']:washer(nz-a[2]*w/2),c['hardware']['nut']:nut}
    if c['sleeve_id']:
        z=107.15 if a[2]>0 else -107.15
        out[c['sleeve_id']]=cyl(6.5,8,(p[0],p[1],z))-cyl(4.5,8.1,(p[0],p[1],z))
    return out

def additions(P):
    out=[]
    for x in [20,160]:
        for side in [-1,1]:out.append((f'R07_upper_cap_{x}_{side}',cap_shape(P,x,side),False,'ROOT_BRIDGE_TO_LONGERON'))
    for c in connections(P):
        for n,s in hardware(P,c).items():out.append((n,s,True,c['connection_id']))
    for side in [-1,1]:
        for level in [-1,1]:
            y=side*107.15;z=level*107.15
            washer=cyl(8,1,(-189.5,y,z),(1,0,0))-cyl(4.5,1.1,(-189.5,y,z),(1,0,0))
            out.append((f'R07_rear_axial_washer_{side}_{level}',washer,True,'REAR_BULKHEAD_TO_END_FRAME_TO_END_PLUG'))
    return out

def write_contract(P,receipt):
    cs=connections(P)
    physical_ids=[r['id'] for r in receipt['instances'] if r['representation_role']!='FUNCTIONAL_ENVELOPE']
    stage_ids={r['id'] for r in receipt['instances'] if r['parent_assembly'] in ['ROOT_STRUCTURE','R07_ROOT_CONNECTIONS'] or r['id'].startswith(('hold_crossbeam_','hold_roof_lug_','hold_pivot_clevis_','wing_root_fork_','lower_deck_angle_','upper_deck_angle_')) or r['id'] in ['rear_launch_bulkhead','lower_equipment_deck','upper_equipment_deck']}
    absent=sorted(set(physical_ids)-stage_ids)
    for c in cs:
        p=c['origin_mm'];a=c['axis'];h=c['head_surface_z_mm'];n=c['nut_surface_z_mm']
        c['paths']=[dict(path_id=c['connection_id']+'_driver',kind='TOOL_CYLINDER',start_mm=[p[0],p[1],h+a[2]*2.6],end_mm=[p[0],p[1],h+a[2]*34.5],outer_d_mm=2.8,inner_d_mm=0),dict(path_id=c['connection_id']+'_nut_tool',kind='TOOL_TUBE',start_mm=[p[0],p[1],n-a[2]*.51],end_mm=[p[0],p[1],n-a[2]*24],outer_d_mm=9,inner_d_mm=8.2)]
        for key in c['hardware']:
            direction=a if key in ['screw','washer_head'] else [-v for v in a]
            c['paths'].append(dict(path_id=c['connection_id']+'_'+key+'_insertion',kind='PART_TRANSLATION',moving_id=c['hardware'][key],direction=direction,travel_mm=35,sequence='WASHERS_THEN_SCREW_THEN_NUT'))
        for path in c['paths']:
            later=[]
            if path.get('moving_id') in [c['hardware']['washer_head'],c['hardware']['washer_nut']]:later=[c['hardware']['screw'],c['hardware']['nut']]
            elif path.get('moving_id')==c['hardware']['screw']:later=[c['hardware']['nut']]
            path['assembly_absent_ids']=absent+later
            path['present_instance_ids']=sorted(stage_ids-set(later)-{path.get('moving_id')})
            path['allowed_contact_ids']=[]
            path['phase']='FIXED_FRAME_WITH_PREPOSITIONED_DECKS_AND_ANGLES_BEFORE_MOVING_ASSEMBLIES_AND_SHEAR_PANELS'
            path['sweep_basis']='AXIAL_UNION_OF_NOMINAL_HEAD_SHANK_ANNULUS_OR_HEX_PRISMS; NOT_A_DIAMETER_BOUND_THROUGH_CLEARANCE_HOLES'
        if c['sleeve_id']:
            moving=c['sleeve_id'];x,y,_=c['origin_mm'];z=107.15 if c['axis'][2]>0 else -107.15
            keep={r['id'] for r in receipt['instances'] if r['id'].startswith('RB_longeron_')}
            c['paths'].append(dict(path_id=c['connection_id']+'_sleeve_insert',kind='PART_TRANSLATION',moving_id=moving,direction=[-1,0,0],travel_mm=x+185,
                assembly_absent_ids=sorted(set(physical_ids)-keep-{moving}),present_instance_ids=sorted(keep),allowed_contact_ids=[],
                phase='BARE_OPEN_LONGERONS_BEFORE_END_PLUGS_FRAME_AND_BOLTS',sweep_basis='CONSERVATIVE_BOX_INSIDE_8_MM_TUBE_CAVITY',start_center_mm=[-185,y,z],final_center_mm=[x,y,z]))
    d=dict(schema='WP04_R07_CONNECTIONS_V1',run_id=HERE.parent.name,configuration=P['configuration_id'],state=receipt['state'],units='mm',frame='S',
        connections=cs,affected_instance_ids=affected_ids(P,receipt),local_instance_ids=sorted(set(affected_ids(P,receipt))|{r['id'] for r in receipt['instances'] if r['parent_assembly']=='ROOT_STRUCTURE' or r['id'].startswith('hold_crossbeam_')}),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        nominal_hardware=dict(shank_d_mm=4,head_d_mm=7,head_h_mm=4,washer_od_mm=8,washer_id_mm=4.5,washer_h_mm=.5,nut_af_mm=7,nut_h_mm=3.2,threadless=True,selection_status='UNSELECTED_NOMINAL'),
        scope='R07_A_B_C_D_E_NOMINAL_GEOMETRY_CANDIDATE',parent_issue_status='OPEN',physical_assembly_completed=False,manufacturing_release=False,
        load_path_edges=[dict(from_id=f'WP01-RB-BRIDGE-R2',via=f'R07_upper_cap_{x}_{side}',to_id=f'RB_longeron_{side}_1',method='SHARED_COLUMN_TIE_ROD_AND_OUTBOARD_BOLT') for x in [20,160] for side in [-1,1]],
        sleeve_installation='INSERT_EIGHT_SLEEVES_ALONG_OPEN_LONGERON_CAVITY_BEFORE_END_PLUGS; TEMPORARY_LOCATING_MANDREL_AND_ACTUAL_TOLERANCE_NOT_SELECTED',
        intentional_unqualified_thread_regions=[dict(pair=[f'RB_end_screw_{sx}_{sy}_{sz}',f'RB_end_plug_{sx}_{sy}_{sz}'],axis='X',x_interval_mm=[169,177] if sx>0 else [-177,-168],status='M4_SHANK_IN_3_3_TAP_DRILL_PROXY; UNKNOWN_THREAD_GEOMETRY') for sx in [-1,1] for sy in [-1,1] for sz in [-1,1]],
        remaining=['CONNECTION_STRENGTH_PRELOAD_TOLERANCE','ROOT_B601_AS_BUILT_INTERFACE','SLEEVE_TEMPORARY_LOCATION_AND_PHYSICAL_TOLERANCE'])
    (HERE/'results'/'R07_CONNECTION_CONTRACT.json').write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')

def affected_ids(P,receipt):
    return [r['id'] for r in receipt['instances'] if r['id'] in ['rear_launch_bulkhead','front_service_cover'] or (r['id'].startswith('shear_web_screw_') and '_150_' in r['id']) or r['id'].startswith(('R07_','RB_longeron_','RB_lower_spacer_','RB_pillar_tierod_','RB_pillar_top_washer_','RB_end_screw_','shear_web_','wing_root_fork_','hold_roof_lug_','hold_pivot_clevis_'))]
