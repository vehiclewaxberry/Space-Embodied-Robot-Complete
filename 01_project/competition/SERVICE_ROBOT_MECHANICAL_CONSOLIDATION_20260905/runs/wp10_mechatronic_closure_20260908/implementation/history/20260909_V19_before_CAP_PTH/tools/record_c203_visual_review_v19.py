"""Root's actual view_image inspection of the generated local assembly."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
shot=json.loads((A/'results/CAP_HARNESS_SNAPSHOT_V19.json').read_text())
assert shot['target_sha256']==sha(shot['target']) and shot['published_sha256']==sha(shot['published_image'])
v=dict(actual_images_viewed=True,viewer='root via view_image',images={shot['published_image']:sha(shot['published_image'])},
 target=shot['target'],target_sha256=sha(shot['target']),camera='130:22',
 observed=['PCB rear face and four board screw heads are visible in their carrier frame','Capacitor nominal cylinder and upper carrier/yokes are visible','One white routed insulated wire is visible entering the CHB input board; the opposing wire is partly occluded','CHB module and its local input board are present'],
 limitations=['Single static camera; hidden wire and local bearing surfaces are covered by separate exact geometry evidence','The mask/copper thickness, insertion clearance and seating gaps cannot be measured from this image','No physical fabrication, soldering, dynamic motion, preload or full spacecraft assembly demonstrated'],
 visual_defect_requiring_source_change_observed=False,whole_design_complete=False)
(A/'results/CAP_HARNESS_VISUAL_REVIEW_V19.json').write_text(json.dumps(v,indent=2),encoding='utf-8')
print('Recorded actual image inspection with occlusion and measurement limits')
