"""Current terminal PCB envelope; copper layout is in the native KiCad board."""
from pathlib import Path
import json
from input_cap_mount_common import make,cx
def gen_step():
    a=Path(__file__).resolve().parents[1]
    c=json.loads((a/'power/CAP_TERMINAL_DEFINITION.json').read_text())
    board=make('PCB')
    for t in c['terminal_features']:
        if t['id'].startswith('WIRE_'):
            _,y,z=t['S_face_mm'];board=board-cx(t['drill_mm']/2,-8,-4,y,z)
    board.label='WP10_C203_PCB_V17_FINISHED_ENVELOPE_TWO_WIRE_NPTH_ADDED'
    return board
