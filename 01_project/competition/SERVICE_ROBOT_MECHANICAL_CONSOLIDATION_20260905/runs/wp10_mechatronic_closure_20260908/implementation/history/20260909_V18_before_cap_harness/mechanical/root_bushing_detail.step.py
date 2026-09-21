"""Five full source components only; bridge intentionally absent from this detail view."""
from pathlib import Path
import hashlib,json
from build123d import Plane,Compound
from cadgen.step_scene import import_step
A=Path(__file__).resolve().parents[1]
def gen_step():
    p=json.loads((A/'mechanical/ROOT_BUSHING_PREVIEW_INPUTS.json').read_text());assert all(hashlib.sha256((A/q).read_bytes()).hexdigest()==h for q,h in p['inputs'].items())
    parts=[]
    for r in p['rows']:
        if r['id'] not in p['detail_ids']:continue
        path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256'];T=r['T_S_step']
        s=Plane(origin=tuple(T[i][3] for i in range(3)),x_dir=tuple(T[i][0] for i in range(3)),z_dir=tuple(T[i][2] for i in range(3))).location*import_step(str(path));s.label=r['id'];parts.append(s)
    assert len(parts)==5
    return Compound(label='WP10_ROOT_BUSHING_5COMP_DETAIL__BRIDGE_NOT_SHOWN',children=parts)
