"""Current bottom radiator source plus a locally raised integral spreading region."""
from pathlib import Path
import hashlib, importlib.util, json
from build123d import Box, Pos, Color
HERE=Path(__file__).resolve().parent
A=HERE.parent

def gen_step():
    d=json.loads((HERE/'SPREADER_PARAMETERS_V28.json').read_text())
    for path,h in d['source_lock'].items():
        assert hashlib.sha256((A/path).read_bytes()).hexdigest()==h,'SOURCE_DRIFT: '+path
    spec=importlib.util.spec_from_file_location('wp10_bottom_source_v28',A/'mechanical/bottom_radiator_common.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    p=old.parameters();s=old.radiator()
    x0,y0,x1,y1=d['region_xy_mm'];z0=d['base_top_z_mm'];z1=d['new_top_z_mm']
    assert abs(z0-p['plate_top_z_mm'])<1e-9 and abs(z1-z0-d['height_mm'])<1e-9
    s += Pos((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)*Box(x1-x0,y1-y0,z1-z0)
    # Extend every existing relief through new metal; never fill old holes.
    q=p['beam_reliefs']
    for x in q['x_mm']:
        s -= Pos(x,0,(q['bottom_z_mm']+z1+1)/2)*Box(q['width_mm'],q['length_mm'],z1+1-q['bottom_z_mm'])
    q=p['pillar_edge_notches']
    for x in q['x_mm']:
        for y in q['y_mm']:s -= old.bore(x,y,q['diameter_mm'],p['outer_z_mm']-1,z1+1)
    for key in ['lower_fastener_blind_pockets','MIPS_blind_pockets']:
        q=p[key]
        for x in q['x_mm']:
            for y in q['y_mm']:s -= old.bore(x,y,q['diameter_mm'],q['bottom_z_mm'],z1+1)
    for x,y in p['mount_centers_xy_mm']:
        s -= old.bore(x,y,p['bore_diameter_mm'],p['outer_z_mm']-1,p['deck_bottom_z_mm']+1)
    c=p['chb_path'];cx,cy=c['center_xy_mm']
    for dx in c['oem_hole_x_offsets_mm']:
        for dy in c['oem_hole_y_offsets_mm']:
            s -= old.bore(cx+dx,cy+dy,c['clearance_bore_mm'],p['outer_z_mm']-1,c['seat_z_mm']+1)
    s.label='WP10_V28_BOTTOM_RADIATOR_INTEGRAL_LEFT_SPREADER_3p5__THERMAL_CLOSURE_OPEN'
    s.color=Color(.75,.82,.89)
    return s
