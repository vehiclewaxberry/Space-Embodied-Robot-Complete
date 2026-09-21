"""CF1 conduction path: carrier return-TIM boss, two +/-Y thermal straps and their two shear-web lugs.

Every dimension is read from THERMAL_PATH_GEOMETRY_CF1.json, the same file thermal_cf1.py turns into
link resistances, so the solids and the thermal screen cannot drift apart. Parts are authored in the
module frame of coupled_closure/mechanical_parts.py; the host pose T_S_module is applied by the
narrowphase, not baked in here.

These are project-nominal aluminium bodies. No fastener, no preload, no clamp force that would realise
the assumed 25 psi TIM pressure, and no native SolidWorks feature tree exists for any of them.
"""
from pathlib import Path
import json
from build123d import Box, Color, Compound, Pos

HERE = Path(__file__).resolve().parent
SPEC = HERE / 'THERMAL_PATH_GEOMETRY_CF1.json'


def box_at(x, y, z, l, w, h):
    """Same corner-anchored box helper as coupled_closure/mechanical_parts.py."""
    return Pos(x + l / 2, y + w / 2, z + h / 2) * Box(l, w, h)


def gen_step():
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    parts = []
    for p in spec['parts']:
        boxes = p['boxes_module_mm']
        s = box_at(*boxes[0])
        for b in boxes[1:]:
            s = s + box_at(*b)
        s.label = p['label']
        s.color = Color(*p['colour'])
        parts.append(s)
    return Compound(label='CF1_THERMAL_PATH__NO_FASTENERS_NO_PRELOAD_NO_NATIVE_CAD', children=parts)
