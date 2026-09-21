"""Record actual root visual observations of saved browser captures; retain CLI failures."""
from pathlib import Path
import json,hashlib
from PIL import Image
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
for view in ['ISO','TOP','FRONT']:
 p=C/f'LUG_BROWSER_{view}_V30.jpg';previous=p.with_suffix('.png')
 if previous.exists():
  assert previous.read_bytes()[:3]==b'\xff\xd8\xff' and not p.exists();previous.rename(p)
 with Image.open(p) as im:w,h=im.size;assert im.format=='JPEG'
 rows.append(dict(file=p.name,sha256=sha(p),view=view,width=w,height=h))
fail=[]
for p in sorted((A/'logs').glob('*lug30*.run.json')):
 d=json.loads(p.read_text());cmd=' '.join(d.get('command',[]))
 if ('snapshot' in cmd or 'render_precleaned' in p.name) and d.get('status')!='COMPLETED':fail.append(dict(receipt=p.name,status=d.get('status'),available_start_MiB=d.get('available_start_mib')))
out=dict(reviewed=True,reviewer='/root',method='CUA browser screenshot and actual displayed CAD assembly; not a cadgen snapshot CLI success',model_sha256=sha(C/'main_input_lugs_v30.step'),model_url='http://127.0.0.1:3246/?file=main_input_lugs_v30.step',viewer_version='0.5.1',viewer_tree_occurrences=56,images=rows,observations=['All three captures show the same main_input_lugs_v30.step document.','Two cover/guide groups and four opposed local wire outlets are visible.','The top and front views show the PCB/carrier arrangement and mounting fasteners without evident gross misplaced parts.','The board is intentionally partly populated; hidden lug internals, preload, torque, electrical clearance and whole-host fit are not accepted from these views.'],native_snapshot_CLI_completed=False,native_snapshot_failures=fail,hidden_interfaces_visually_verified=False,whole_design_complete=False)
(C/'VISUAL_REVIEW_V30.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(browser_views_reviewed=len(rows),native_snapshot_failures=len(fail))))
