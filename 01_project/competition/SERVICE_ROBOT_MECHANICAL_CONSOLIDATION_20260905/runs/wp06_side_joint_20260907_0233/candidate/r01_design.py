"""Single R01 geometry implementation consumed by local and spacecraft entries.
All lengths mm. Hardware is nominal, unselected, threadless, mass UNKNOWN.
"""
from pathlib import Path
import json,math,hashlib,sys
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # Install the existing font guard before importing build123d.
from build123d import Box,Cylinder,Plane,Location,Compound,Color,RegularPolygon,extrude
from cadgen.assembly import AssemblyHelper
HERE=Path(__file__).resolve().parent
def parameters():return json.loads((HERE/"design_parameters.json").read_text(encoding="utf-8"))
def box(size,c=(0,0,0)):return Box(*size).moved(Location(tuple(c)))
def cyl(d,h,c=(0,0,0),axis=(0,0,1)):return Cylinder(d/2,h).moved(Plane(origin=tuple(c),z_dir=tuple(axis)).location)
def cut(s,d,h,c=(0,0,0),axis=(0,0,1)):return s-cyl(d,h,c,axis)
def position(p,a,t):return [p[i]+a[i]*t for i in range(3)]
def deck_shape(P,deck,legacy=False):
    R=P["r01"];s=Box(*R["deck_size_mm"])
    for x in R["notch_x_mm"]:
        for y in [-R["notch_y_mm"],R["notch_y_mm"]]:s=s-box(R["notch_cut_mm"],(x,y,0))
    xs=[-150,-50,50,150] if legacy else R["deck_hole_x_mm"]
    ys=[-89,89] if legacy else [-R["deck_hole_y_abs_mm"],R["deck_hole_y_abs_mm"]]
    for x in xs:
        for y in ys:s=cut(s,R["clearance_d_mm"],R["deck_size_mm"][2]+4,(x,y,0))
    if not legacy and deck==R["thermal_passage"]["deck"]:
        t=R["thermal_passage"];s=cut(s,t["diameter_mm"],7,(*t["center_xy_mm"],0))
    return s
def angle_center(P,deck,side,k):
    a,b=P["r01"]["angle_segments_x_mm"][k]
    return [(a+b)/2,side*96.15,P["r01"]["deck_z_mm"][deck]-3]
def angle_shape(P,deck,side,k,legacy=False):
    R=P["r01"];a,b=R["angle_segments_x_mm"][k];legz=5.5 if deck=="lower" else -5.5
    s=box((b-a,11,3),(0,-side*3.5,0))+box((b-a,3,14),(0,side*3.5,legz))
    if not legacy:
        for x in R["deck_hole_x_mm"]:
            if a<x<b:s=cut(s,R["clearance_d_mm"],7,(x-(a+b)/2,side*(R["deck_hole_y_abs_mm"]-96.15),0))
        for x in R["web_hole_x_mm_by_segment"][k]:
            s=cut(s,R["clearance_d_mm"],7,(x-(a+b)/2,side*3.5,R["web_hole_z_mm"][deck]-(R["deck_z_mm"][deck]-3)),(0,1,0))
    if not legacy and deck==R["existing_web_screw_clearance"]["deck"]:
        e=R["existing_web_screw_clearance"]
        for x in e["x_mm"]:
            if a<x<b:s=cut(s,e["diameter_mm"],7,(x-(a+b)/2,side*3.5,e["z_mm"]-(R["deck_z_mm"][deck]-3)),(0,1,0))
    if not legacy and P.get("wp06") and deck=="lower" and k==1:
        # Open U-shaped tool relief in the angle only; this is not a closed bore.
        w=P["wp06"];width=w["tool_relief_width_mm"]
        xc=w["joint_x_mm"]-(a+b)/2
        zc=w["lower_axis_z_mm"]-(R["deck_z_mm"][deck]-3)
        top_local=legz+7  # Existing vertical leg top, S Z=-90.15 mm nominal.
        if width<=0 or zc>=top_local:
            raise ValueError("WP06 open relief requires positive width and axis below the angle top")
        rise=top_local-zc+1.0  # Extend above the open edge to avoid coincident faces.
        relief=cyl(width,24,(xc,0,zc),(0,1,0))+box((width,24,rise),(xc,0,zc+rise/2))
        s=s-relief
    return s

def web_shape(P,side,legacy=False):
    s=Box(344,2,202.3)
    for x in [-150,-90,-30,30,90,150]:
        for z in [-94,94]:
            hx,hz,diameter=x+4,z,3.4
            if not legacy and P.get("wp06") and x==150:
                w=P["wp06"];hx=w["joint_x_mm"]
                hz=w["lower_axis_z_mm"] if z<0 else w["upper_axis_z_mm"]
                diameter=w["clearance_diameter_mm"]
            s=cut(s,diameter,6,(hx,0,hz),(0,1,0))
    if not legacy:
        R=P["r01"]
        for deck in ["lower","upper"]:
            for xs in R["web_hole_x_mm_by_segment"]:
                for x in xs:s=cut(s,R["clearance_d_mm"],6,(x,0,R["web_hole_z_mm"][deck]),(0,1,0))
    return s
def structures(P,legacy=False):
    out={}
    for side in [-1,1]:out[f"shear_web_{side}"]=(web_shape(P,side,legacy),[0,side*102.15,0])
    for deck in ["lower","upper"]:
        out[f"{deck}_equipment_deck"]=(deck_shape(P,deck,legacy),[0,0,P["r01"]["deck_z_mm"][deck]])
        for side in [-1,1]:
            for k in range(2):out[f"{deck}_deck_angle_{side}_{k}"]=(angle_shape(P,deck,side,k,legacy),angle_center(P,deck,side,k))
    return out
def connections(P):
    R=P["r01"];rows=[];w=R["hardware"]["washer_h_mm"];nut=R["hardware"]["nut_h_mm"]
    absent_equipment=[prefix+e["name"] for e in P["equipment"] for prefix in ["equipment_","adapter_","thermal_interface_"]]
    for deck in ["lower","upper"]:
        z=R["deck_z_mm"][deck]
        for side in [-1,1]:
            for k,(a,b) in enumerate(R["angle_segments_x_mm"]):
                for x in [x for x in R["deck_hole_x_mm"] if a<x<b]:
                    rows.append(dict(id=f"R01_D_{deck}_{side}_{x}",kind="deck_angle",deck=deck,side=side,segment=k,x_mm=x,axis_S=[0,0,1],
                      axis_point_S_mm=[x,side*R["deck_hole_y_abs_mm"],z-1.5],
                      members=[dict(id=f"{deck}_equipment_deck",axis_interval_mm=[0,3]),dict(id=f"{deck}_deck_angle_{side}_{k}",axis_interval_mm=[-3,0])],
                      nominal_grip_mm=6,underhead_length_mm=R["hardware"]["deck_underhead_mm"]))
                for x in R["web_hole_x_mm_by_segment"][k]:
                    rows.append(dict(id=f"R01_W_{deck}_{side}_{x}",kind="angle_web",deck=deck,side=side,segment=k,x_mm=x,axis_S=[0,side,0],
                      axis_point_S_mm=[x,side*101.15,R["web_hole_z_mm"][deck]],
                      members=[dict(id=f"shear_web_{side}",axis_interval_mm=[0,2]),dict(id=f"{deck}_deck_angle_{side}_{k}",axis_interval_mm=[-3,0])],
                      nominal_grip_mm=5,underhead_length_mm=R["hardware"]["web_underhead_mm"]))
    for c in rows:
        c["hole_diameter_mm"]=R["clearance_d_mm"];c["hardware"]={n:c["id"]+"_"+n for n in ["screw","washer_head","washer_nut","nut"]}
        p=c["axis_point_S_mm"];a=c["axis_S"];outer=c["members"][0]["axis_interval_mm"][1];inner=-3
        c["head_bearing_axis_t_mm"]=outer+w;c["nut_outer_axis_t_mm"]=inner-w-nut
        c["nominal_shank_overlap_nut_mm"]=max(0,min(nut,c["underhead_length_mm"]-(outer+w-(inner-w))))
        c["unverified"]=["actual_thread_engagement","strength_grade","preload","locking_process","physical_fit"]
        c["bearing_planes"]=[dict(hardware_id=c["hardware"]["washer_head"],member_id=c["members"][0]["id"],point_S_mm=position(p,a,outer),normal_S=a,annulus_inner_d_mm=R["hardware"]["washer_id_mm"],annulus_outer_d_mm=R["hardware"]["washer_od_mm"]),
           dict(hardware_id=c["hardware"]["washer_nut"],member_id=c["members"][1]["id"],point_S_mm=position(p,a,inner),normal_S=[-v for v in a],annulus_inner_d_mm=R["hardware"]["washer_id_mm"],annulus_outer_d_mm=R["hardware"]["washer_od_mm"])]
        # Cylindrical straight axial tool envelopes, provisional geometry not selected tools.
        t_head=outer+w+R["hardware"]["head_h_mm"]-R["hardware"]["socket_depth_mm"]+.1;t_nut=inner-w-.02
        absent=absent_equipment+["access_cover_-1","access_cover_1"]
        c["tool_paths"]=[
            dict(id=c["id"]+"_driver",axis_S=a,start_S_mm=position(p,a,t_head),end_S_mm=position(p,a,t_head+30),outer_d_mm=R["tools"]["driver_d_mm"],inner_d_mm=0,assembly_absent_ids=absent,allowed_contact_ids=[],purpose="DRIVER_SHAFT_APPROACH_PROVISIONAL"),
            dict(id=c["id"]+"_nut_tool",axis_S=[-v for v in a],start_S_mm=position(p,a,t_nut),end_S_mm=position(p,a,t_nut-20-nut),outer_d_mm=R["tools"]["nut_tool_od_mm"],inner_d_mm=R["tools"]["nut_tool_id_mm"],assembly_absent_ids=absent,allowed_contact_ids=[],purpose="HOLLOW_NUT_SOCKET_ENGAGEMENT_AND_APPROACH_ENVELOPE_PROVISIONAL")]
        c["installation_sequence"]="JOIN_DECKS_ANGLES_WEBS; INSTALL_WASHERS_THEN_SCREW_THEN_NUT; BEFORE_EQUIPMENT_ADAPTERS_THERMAL_PADS_AND_COVERS"
        c["screw_insertion_axis_S"]=[-v for v in a]
        c["screw_insertion_translation_mm"]=30
        c["nut_insertion_translation_mm"]=20
        c["insertion_paths"]=[]
        for kind,direction,travel,later in [('washer_head',a,30,['screw','nut']),('washer_nut',[-v for v in a],20,['screw','nut']),('screw',a,30,['nut']),('nut',[-v for v in a],20,[])]:
            c["insertion_paths"].append(dict(id=c['id']+'_'+kind+'_insert',moving_id=c["hardware"][kind],direction_S=direction,travel_mm=travel,assembly_absent_ids=absent+[c['hardware'][n] for n in later],allowed_contact_ids=[]))
        c["mass_owner_policy"]="EACH_HARDWARE_INSTANCE_UNKNOWN_UNTIL_SELECTED; NO_PARENT_DOUBLE_COUNT"
    return rows
def hardware_parts(P,c):
    H=P["r01"]["hardware"];p=c["axis_point_S_mm"];a=c["axis_S"];t=c["head_bearing_axis_t_mm"];L=c["underhead_length_mm"];w=H["washer_h_mm"]
    screw=cyl(H["shank_d_mm"],L,position(p,a,t-L/2),a)+cyl(H["head_d_mm"],H["head_h_mm"],position(p,a,t+H["head_h_mm"]/2),a)
    # Nominal recess for driver space; not a supplier-standard socket claim.
    screw=screw-cyl(H["socket_d_mm"],H["socket_depth_mm"]+.01,position(p,a,t+H["head_h_mm"]-H["socket_depth_mm"]/2),a)
    ring=lambda h,at: cyl(H["washer_od_mm"],h,position(p,a,at),a)-cyl(H["washer_id_mm"],h+.02,position(p,a,at),a)
    head_washer=ring(w,t-w/2);nut_washer=ring(w,-3-w/2)
    # Six-sided nominal nut, actual thread omitted; geometric shank overlap is reported separately.
    nutshape=extrude(RegularPolygon(H["nut_af_mm"]/math.sqrt(3),6,major_radius=True),amount=H["nut_h_mm"])
    nutshape=nutshape.moved(Location((0,0,-H["nut_h_mm"]/2)))
    nutshape=nutshape-cyl(H["nut_bore_mm"],H["nut_h_mm"]+.02)
    nutshape=nutshape.moved(Plane(origin=position(p,a,-3-w-H["nut_h_mm"]/2),z_dir=tuple(a)).location)
    return {c["hardware"]["screw"]:screw,c["hardware"]["washer_head"]:head_washer,c["hardware"]["washer_nut"]:nut_washer,c["hardware"]["nut"]:nutshape}
def local_assembly(legacy=False):
    P=parameters();asm=AssemblyHelper("R01_LOCAL_NOMINAL_ASSEMBLY");records=[];parts={}
    for name,(s,c) in structures(P,legacy).items():
        world=s.moved(Location(tuple(c)));obj=asm.add(world,name,color=Color(.73,.76,.8));parts[name]=world
        records.append(dict(id=name,label=name,role="MODIFIED_EXISTING_PHYSICAL",nominal_volume_mm3=world.volume,valid=world.is_valid))
    cs=[] if legacy else connections(P)
    for c in cs:
        for name,s in hardware_parts(P,c).items():
            asm.add(s,name,color=Color(.24,.29,.32));parts[name]=s
            records.append(dict(id=name,label=name,role="NOMINAL_THREADLESS_HARDWARE_UNSELECTED",mass_kg=None,nominal_volume_mm3=s.volume,valid=s.is_valid))
    document=dict(schema="R01_CONNECTIONS_V1",configuration=P["configuration_id"],run_id=HERE.parent.name,units="mm",frame="S",
        step_path=str(HERE/("r01_legacy.step" if legacy else "r01_local.step")),step_sha256=None,instances=records,connections=cs,
        scope="12_CHANGED_PARTS_AND_NOMINAL_HARDWARE; FULL_CONTEXT_SEPARATELY_REQUIRED",physical_assembly=False,manufacturing_release=False)
    (HERE/"results"/("r01_legacy.json" if legacy else "r01_connections.json")).write_text(json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    return asm.build()
