from pathlib import Path
from urllib.parse import quote
import hashlib,json
from datetime import datetime
R=Path(__file__).resolve().parents[1]
paths=[R/'viewer/WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb',R/'candidate/pcb_reference_panels.step.py',R/'candidate/retention_station0.step.py']
entries=[]
for p,tab,observation in zip(paths,['1','2','3'],['Complete spacecraft/arm/solar-wing scene observed','Assembly 4; four bare reference boards observed','Assembly 18; mast, saddle, split collars and guides observed']):
    entries.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url='http://127.0.0.1:3245/'+quote(p.parent.as_posix(),safe='/:')+'?file='+quote(p.name,safe=''),tab_id=tab,actual_ax_state_loaded=True,actual_screenshot_reviewed=True,marked_deliverable=True,observation=observation))
out=R/'results/VIEWER_HANDOFF.json'
assert not out.exists()
out.write_text(json.dumps(dict(schema='WP07_INTERACTIVE_VIEWER_HANDOFF',recorded_local=datetime.now().astimezone().isoformat(),status='THREE_INTERACTIVE_VIEWS_ACTUALLY_OPENED_AND_REVIEWED',entries=entries,scope='UI viewing only. Source STEP/BRep checks are separate. Local retention and reference PCB are not part of the 597-instance whole assembly.',engineering_release=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(str(out))
