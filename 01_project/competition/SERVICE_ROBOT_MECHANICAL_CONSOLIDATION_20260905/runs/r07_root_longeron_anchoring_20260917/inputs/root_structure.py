"""Literal WP02 root geometry reused in WP03; no call to WP02 build or writes to WP02."""
from pathlib import Path
import importlib.util,math,json
from build123d import Box,Cylinder,Location
from cadgen.step_scene import import_step
ORIGINAL=Path(__file__).resolve().parent.parent/'service_robot_wp02_20260905'
spec=importlib.util.spec_from_file_location('wp02_readonly_helpers',ORIGINAL/'parts_model.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
P=w.P;R=w.R;HERE=ORIGINAL
box=w.box;tube=w.tube;bore=w.bore;plate=w.plate;screw=w.screw;ring=w.ring
ON=w.ON;HW=w.HW;GOLD=w.GOLD;DARK=w.DARK
def build_root(add):
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
