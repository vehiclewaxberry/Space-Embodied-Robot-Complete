from pathlib import Path
import json,hashlib
from build123d import import_step
A=Path(__file__).resolve().parents[1];out=[]
for name in ['WSLP2726 (0.002).stp','WSLP2726 (0.2mohm).stp']:
 p=A/'sources/terminal_v29'/name;s=import_step(p);b=s.bounding_box()
 out.append(dict(file=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),valid=s.is_valid,solid_count=len(s.solids()),volume_mm3=s.volume,bounds_mm=list(b.min)+list(b.max)))
(A/'results/SHUNT_OEM_GEOMETRY_V29.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
