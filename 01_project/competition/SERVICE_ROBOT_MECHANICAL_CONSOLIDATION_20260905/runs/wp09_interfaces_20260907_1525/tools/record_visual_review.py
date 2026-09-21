from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
from PIL import Image
R=Path(__file__).resolve().parents[1]
def fact(p,observations):
    q=R/p
    with Image.open(q) as im:size=list(im.size)
    return dict(path=str(q),sha256=hashlib.sha256(q.read_bytes()).hexdigest(),pixels=size,visually_inspected_by='ROOT',observations=observations)
images=[fact('viewer/WP09_SERVICE_NATIVE.png','Actual SolidWorks isometric service assembly capture. Whole body, arm, covers, solar panels and retained support hardware fit inside the frame. Internal bay is largely concealed by covers; use bay source view for the delta.'),fact('viewer/bay_iso_20260907T065738Z.png','Actual CAD bay source render: raised tray, two static routes and +X propulsion reference carrier visible.'),fact('viewer/bay_top_20260907T065738Z.png','Actual top render reviewed for route separation and host arrangement.'),fact('viewer/bay_reverse_20260907T065738Z.png','Actual reverse render reviewed for deck/cradle arrangement.'),fact('docs/HARNESS_LAYOUT_S_WORLD.png','Final label revision inspected. P1/P2/D1/D2 are legible and cross-reference coordinates. Nominal length/radius and unbound cut lengths are explicit.')]
out=dict(status='VISUAL_REVIEW_COMPLETED_WITH_DECLARED_LIMITS',utc=datetime.now(timezone.utc).isoformat(),images=images,not_verified_by_images=['DIMENSIONAL_CONFORMANCE','CONTINUOUS_MOTION','TOOL_ACCESS','PHYSICAL_HARNESS','FLIGHT_READINESS'],native_input_unchanged_after_capture=True,source_receipts=['results/NATIVE_VIEW_PREPARE.json','viewer/NATIVE_CAPTURE_RECEIPT.json','results/NATIVE_VIEW_CLOSE.json','viewer/BAY_SNAPSHOT_JOB.json'])
(R/'results/VISUAL_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
url='http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525?file=candidate%2Fintegrated_bay.step.py'
handoff=dict(status='LIVE_MODEL_VISIBLE_AND_MARKED_DELIVERABLE',utc=out['utc'],url=url,browser_id='1',tab_id='5',observed_title='text-to-cad | integrated_bay.step.py',observed_zoom='100%',model_fits_live_viewport=True,source_path=str(R/'candidate/integrated_bay.step.py'),source_sha256=hashlib.sha256((R/'candidate/integrated_bay.step.py').read_bytes()).hexdigest(),ui_actions=['Navigate task-owned blank tab to exact source URL','Observe model and AX source breadcrumb','Reset view from 216% to 100% and observe complete model','markDeliverable','Show browser'],live_screenshot_file=None,live_screenshot_evidence='CUA tool output in current conversation; local source renders separately saved',native_session_closed_to_release_memory=True)
(R/'results/VIEWER_HANDOFF.json').write_text(json.dumps(handoff,ensure_ascii=False,indent=2),encoding='utf-8')
print('visual_review_and_live_handoff_recorded')
