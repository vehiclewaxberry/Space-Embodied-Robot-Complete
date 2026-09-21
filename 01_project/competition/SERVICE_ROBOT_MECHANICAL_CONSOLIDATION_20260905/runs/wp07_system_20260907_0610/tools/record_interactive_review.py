from pathlib import Path
import hashlib,json
from datetime import datetime
R=Path(__file__).resolve().parents[1]
p=R/'results/VISUAL_REVIEW.json'
d=json.loads(p.read_text(encoding='utf-8'))
assert not d['whole_service_reviewed']
source=R/'viewer/WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb'
url='http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer?file=WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb'
group=dict(id='service',reviewed=True,status='REVIEWED_INTERACTIVE_DISPLAY_ONLY',method='CUA getAXState and getScreenshot actually observed in this session; tab.markDeliverable completed',images=[],source=dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest()),viewer_url=url,observations='Complete spacecraft body, B601 arm, two solar wings, side joint geometry and the inherited retention arrangement are visible in isometric view. New C03 local retention candidates and unselected reference PCBs are not integrated into this 597-instance scene.',saved_whole_png=False)
d['groups'].append(group)
d['whole_service_reviewed']=True
d['saved_whole_png']=False
d['status']='LOCAL_PNG_AND_WHOLE_INTERACTIVE_DISPLAY_REVIEWED__NO_WHOLE_SNAPSHOT_PNG'
d['recorded_local']=datetime.now().astimezone().isoformat()
d['whole_snapshot_failures']=[dict(path=str(R/'logs'/f),status=json.loads((R/'logs'/f).read_text(encoding='utf-8'))['status']) for f in ('snapshot_service.run.json','snapshot_service_v4.run.json','snapshot_service_v4_rendered.run.json','snapshot_service_v4_single.run.json')]
d['whole_snapshot_note']='V3 exceeded declared job working-set bound. V4 default and smaller single view ended with browser closed error; rendered display rejected by GLB CLI. No whole PNG was generated; interactive CUA review is distinct from scripts/snapshot validation.'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=d['status'],local_pngs=12,interactive_whole=True)))
