"""Same-candidate fixed thermal wall, global S frame in mm."""
from pathlib import Path
import importlib.util,json
from build123d import Box,Cylinder,Pos,Rot,Plane,Compound,Color,Location
from cadgen.step_scene import import_step
from cadgen.assembly import AssemblyHelper
from carrier_common import thermal_pad as converter_tim
from bottom_radiator_common import parameters as bottom_parameters

A=Path(__file__).resolve().parents[1]
BASE=A.parents[1]
W6=BASE/'wp06_side_joint_20260907_0233/candidate'

def parameters():return json.loads((A/'thermal/FIXED_HEAT_PATH.json').read_text())

def original_walls():
    spec=importlib.util.spec_from_file_location('wp10_bound_wp06_thermal',W6/'side_joint_design.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod.build_changed()

def cyl_y(d,y0,y1,x,z):
    return Pos(x,(y0+y1)/2,z)*Rot(90,0,0)*Cylinder(d/2,abs(y1-y0))

def device_frame(d,at='back'):
    if d.get('mount_type')=='BOTTOM_PEDESTAL':
        x,y,z=d['seat_origin_S_mm'];z+=d['TIM_mm'][2] if at=='OEM' else 0
        return Location((x,y,z))
    x,z=d['center_xz_mm'];s=d['side'];a=d['carrier_back_abs_y_mm']
    if at=='TIM':a-=d['carrier_size_mm'][2]
    if at=='OEM':a-=d['carrier_size_mm'][2]+d['TIM_mm'][2]
    # Pad/base CHB has ordinary RotX(90); resistor localX -> S+Z.
    return (Plane(origin=(x,s*a,z),x_dir=(1,0,0),z_dir=(0,-s,0)).location
            if d['id']=='U202_CHB' else
            Plane(origin=(x,s*a,z),x_dir=(0,0,1),z_dir=(0,1,0)).location)

def thermal_wall(side):
    p=parameters();q=next(q for q in p['panels'] if q['side']==side)
    wall=original_walls()[q['parent_id']]
    yout=p['external_face_abs_y_mm'];t=p['radiator_thickness_mm']
    panel=Pos(0,side*(yout-t/2),0)*Box(344,t,180)
    # Each integral solid spans from the device seat through the original wall
    # to the external plate. No fictitious dry-interface conductance is used.
    for d in [d for d in p['devices'] if d['side']==side and d.get('mount_type')!='BOTTOM_PEDESTAL']:
        x,z=d['center_xz_mm'];w,h,ct=d['carrier_size_mm'];inner=d['carrier_back_abs_y_mm']-ct
        back=d['carrier_back_abs_y_mm']
        seat=Pos(x,side*(back-ct/2),z)*Box(w,ct,h)
        bw,bh=(70,72) if d['id']=='U202_CHB' else (44,45)
        bridge_z=z if d['id']=='U202_CHB' else 62.5
        boss=Pos(x,side*((yout-t+back)/2),bridge_z)*Box(bw,yout-t-back+.02,bh)
        wall=wall+boss+seat
    wall=wall+panel
    c=bottom_parameters().get('chb_path')
    if c and c['enabled']:
        x,z=c['wall_contact_center_xz_mm'];w,h=c['wall_TIM_size_mm'];inner=c['wall_seat_abs_y_mm'];back=yout-t+.02
        wall=wall+Pos(x,side*(inner+back)/2,z)*Box(w,back-inner,h)
    for x in [-150,-90,-30,30,90,150]:
        for sz in [-1,1]:
            # Blind outer-plate back pockets preserve the original shear clips.
            wall=wall-Pos(x,side*106.4,sz*93.75)*Box(18,6.5,14.8)
    # Clear original outer washer/head/tool geometry without cutting its
    # original 2mm web bearing annulus. Exact x,z positions enter the config.
    for x,z,diameter in q['tool_holes_xz_d_mm']:
        wall=wall-cyl_y(diameter,side*103.15,side*(yout+1),x,z)
    # OEM mounting patterns remain explicit candidates; no as-built threads.
    for d in [d for d in p['devices'] if d['side']==side and d.get('mount_type')!='BOTTOM_PEDESTAL']:
        x,z=d['center_xz_mm'];inner=d['carrier_back_abs_y_mm']-d['carrier_size_mm'][2]
        if d['id']=='U202_CHB':
            for xx in [-24.15,24.15]:
                for zz in [-25.4,25.4]:wall=wall-cyl_y(4.,side*(inner-.1),side*(yout+1),x+xx,z+zz)
        else:
            for xx in [-28.5,28.5]:
                # After OEM rotation its two mount positions run along S X.
                wall=wall-cyl_y(4.5,side*(inner-.1),side*(yout+1),x+xx,z)
    if c and c['enabled']:
        from build123d import Cone
        for x,z in c['wall_screw_centers_xz_mm']:
            wall=wall-cyl_y(3.4,side*(c['wall_seat_abs_y_mm']-1),side*(yout+1),x,z)
            hh=(6.72-3.4)/2
            fr=Plane(origin=(x,side*yout,z),x_dir=(1,0,0),z_dir=(0,-side,0)).location
            wall=wall-fr*(Pos(0,0,hh/2)*Cone(3.36,1.7,hh))
    wall.label=f'WP10_FIXED_RADIATOR_WALL_{side:+d}_6061_CANDIDATE'
    wall.color=Color(.88,.90,.93)
    return wall

def tim_local(d):
    if d['id']=='U202_CHB':return converter_tim(d['TIM_mm'][2],d.get('TIM_family','TSP1600S')) if d.get('mount_type')=='BOTTOM_PEDESTAL' else converter_tim()
    w,h,t=d['TIM_mm'];pad=Pos(0,0,t/2)*Box(w,h,t)
    pad.label=d['id']+'_Q2500_NO_PSA';pad.color=Color(.15,.16,.17);return pad

def assembly():
    p=parameters();walls={s:thermal_wall(s) for s in [-1,1]}
    asm=AssemblyHelper('WP10_FIXED_HEAT_PATH_S_FRAME')
    handles={s:asm.add(walls[s],f'WALL_{s:+d}') for s in [-1,1]}
    # Both source solids are authored in S; an identity-to-identity rigid mate
    # preserves that convention and prevents applying the S transform twice.
    neg=asm.rigid_frame(handles[-1],'S_origin',Location())
    pos=asm.rigid_frame(handles[1],'S_origin',Location())
    asm.face_to_face(neg,pos)
    for d in p['devices']:
        key=d['id'];s=d['side'];parent=handles[s];t=d['TIM_mm'][2]
        pad=asm.add(tim_local(d),key+'_TIM')
        bottom=asm.rigid_frame(pad,'bottom',Location())
        top=asm.rigid_frame(pad,'top',Location((0,0,t)))
        seat=asm.rigid_frame(parent,key+'_seat',device_frame(d,'TIM'))
        raw=import_step(str(A/'sources'/('CHB500W_STANDARD_OEM.step' if key=='U202_CHB' else 'LPS300_OEM.step')))
        if key=='U202_CHB':
            # Reuse exactly the already checked baseplate orientation; the
            # physical base datum becomes z=0, rather than bbox minimum.
            raw=Pos(0,0,1.6)*Rot(90,0,0)*raw;datum=Location()
        else:datum=Location((0,0,-.2))
        raw=asm.add(raw,key+'_OEM');base=asm.rigid_frame(raw,'base',datum)
        asm.face_to_face(seat,bottom);asm.face_to_face(top,base)
    return asm.build()
