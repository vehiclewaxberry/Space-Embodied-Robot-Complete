"""Read OEM BReps, without editing the downloaded source models."""
from pathlib import Path
import json,hashlib
from build123d import import_step
A=Path(__file__).resolve().parents[1];rows=[]
for name in ['74651195_rev1.stp','MP_Wurth_WP-THRSH_74651195.step']:
 p=A/'sources/terminal_v29'/name;s=import_step(p);b=s.bounding_box()
 rows.append(dict(file=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),valid=s.is_valid,solids=len(s.solids()),volume_mm3=s.volume,bounds_mm=list(b.min)+list(b.max)))
(A/'results/TERMINAL_OEM_GEOMETRY_V29.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(rows))
