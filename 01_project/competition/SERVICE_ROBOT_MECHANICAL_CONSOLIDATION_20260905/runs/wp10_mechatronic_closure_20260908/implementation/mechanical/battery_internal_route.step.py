"""Continuous static bundle envelope below the sourced maximum battery box."""
from pathlib import Path
import json
from heat_layout_relocation import Route
A=Path(__file__).resolve().parents[1]
def gen_step():
    c=json.loads((A/'mechanical/BATTERY_INTERNAL_ROUTE.json').read_text())
    assert c['outer_diameter_mm']==6
    r=Route(c['start'])
    for cmd in c['commands']:
        if 'line' in cmd:r.line(cmd['line'])
        elif 'offset' in cmd:r.offset(**cmd['offset'])
        else:r.arc(**cmd['arc'])
    s,facts=r.solid('WP10_INTERNAL_BATTERY_BYPASS')
    assert facts['radius_min_mm']>=c['minimum_bend_radius_mm']-1e-9
    assert (r.p-r.start).length>0
    s.label='WP10_INTERNAL_BATTERY_BYPASS__OD6_R21_FUNCTIONAL_ONLY'
    return s
