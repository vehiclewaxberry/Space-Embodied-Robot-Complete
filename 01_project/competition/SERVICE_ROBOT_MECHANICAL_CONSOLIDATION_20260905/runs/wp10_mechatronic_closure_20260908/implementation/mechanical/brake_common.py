from pathlib import Path
from build123d import Box,Cylinder,Pos,Align,Color,Location
from cadgen.assembly import AssemblyHelper
from cadgen.step_scene import import_step
P=dict(plate_x=150.,plate_y=160.,plate_t=6.,tim_x=56.,tim_y=51.,tim_t=.152,
       slot_width=4.5,slot_length=6.,oem_mount_half_pitch=28.5,frame_x=67.,frame_y=72.,frame_d=4.5,
       centers=[(-37.5,-37.),(37.5,-37.),(0.,37.)],oem_bottom_z=-.2)
def carrier():
    s=Box(P['plate_x'],P['plate_y'],P['plate_t'],align=(Align.CENTER,Align.CENTER,Align.MIN))
    w=P['slot_width']; l=P['slot_length']; t=P['plate_t']
    for x,y in P['centers']:
        for sy in [-P['oem_mount_half_pitch'],P['oem_mount_half_pitch']]:
            # Capsule slot: exact minor width w and overall major length l.
            cut=Box(w,l-w,t,align=(Align.CENTER,Align.CENTER,Align.MIN))
            for dy in [-(l-w)/2,(l-w)/2]:cut+=Pos(0,dy,0)*Cylinder(w/2,t,align=(Align.CENTER,Align.CENTER,Align.MIN))
            s-=Pos(x,y+sy,0)*cut
    for x in [-P['frame_x'],P['frame_x']]:
        for y in [-P['frame_y'],P['frame_y']]:s-=Pos(x,y,0)*Cylinder(P['frame_d']/2,t,align=(Align.CENTER,Align.CENTER,Align.MIN))
    s.label='WP10_BRAKE_CARRIER_6061_CANDIDATE';s.color=Color(.65,.7,.78);return s
def pad():
    s=Box(P['tim_x'],P['tim_y'],P['tim_t'],align=(Align.CENTER,Align.CENTER,Align.MIN))
    s.label='Q2500_PROJECT_CUT_56x51x0p152_NO_PSA_NON_INSULATING';s.color=Color(.12,.15,.18);return s
def assembly():
    asm=AssemblyHelper('WP10_RB301_RB302_RB303_LOCAL_MOUNTING_CANDIDATE')
    plate=asm.add(carrier(),'bearing_heat_plate')
    for i,(x,y) in enumerate(P['centers']):
        tim=asm.add(pad(),f'RB{301+i}_Q2500_interface')
        rs=import_step(Path(__file__).resolve().parents[1]/'sources/LPS300_OEM.step')
        rs=asm.add(rs,f'RB{301+i}_LPS300_OFFICIAL_FAMILY_CAD')
        plate_seat=asm.rigid_frame(plate,f'RB{301+i}_seat',Location((x,y,P['plate_t'])))
        tim_bottom=asm.rigid_frame(tim,'bottom',Location((0,0,0)))
        # Create both local frames while TIM is at its local origin. Creating
        # the second native joint after relocation used a world-space frame.
        tim_top=asm.rigid_frame(tim,'top',Location((0,0,P['tim_t'])))
        resistor_bottom=asm.rigid_frame(rs,'alumina_bottom',Location((0,0,P['oem_bottom_z'])))
        asm.face_to_face(plate_seat,tim_bottom)
        asm.face_to_face(tim_top,resistor_bottom)
    return asm.build()
