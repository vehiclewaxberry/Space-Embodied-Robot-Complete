"""Actual upper-deck source edit for four moved P60 supports, S frame mm."""
from pathlib import Path
import json,hashlib
from build123d import Pos,Cylinder,Color
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def gen_step():
    p=json.loads((A/'mechanical/BATTERY_BAY_LAYOUT.json').read_text())['upper_deck_edit']
    source=A/p['baseline_step'];assert hashlib.sha256(source.read_bytes()).hexdigest()==p['baseline_sha256']
    part=import_step(str(source));z0,z1=p['deck_z_mm']
    for x,y in p['P60_new_through_hole_xy_mm']:
        part=part-Pos(x,y,(z0+z1)/2)*Cylinder(p['hole_diameter_mm']/2,z1-z0+2)
    part.label='upper_equipment_deck_B__BATTERY_LAYOUT_P60_FOUR_NEW_BORES'
    part.color=Color(.68,.72,.76)
    return part
