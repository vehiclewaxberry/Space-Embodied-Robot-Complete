"""Record human-visible UI observations and resolve the preparatory scope review."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
D=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def bind(p):return {'path':str(p),'sha256':sha(p)}
def write(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
pub=json.loads((D/'review/MATERIAL_PUBLICATION_CHECK.json').read_text(encoding='utf-8'))
assert pub['status']=='PASS_EXACT_INERTIA_PUBLICATION_SCOPE_AND_INDEPENDENT_SUBSET_SUMS'
assert pub['source_receipt']['sha256']==sha(D/'mechanical_inertia/MATERIAL_INERTIA_DELIVERY.json')
write(D/'review/FINAL_SCOPE_DISPOSITION.json',{'status':'RESOLVED_EXACT_MATERIAL_RECEIPT_BINDING_AND_CLAIM_SCOPE','utc':datetime.now(timezone.utc).isoformat(),
 'preparatory_review':bind(D/'review/FINAL_SCOPE_REVIEW.json'),'finalizer':bind(D/'tools/finalize_review.py'),'material_publication_check':bind(D/'review/MATERIAL_PUBLICATION_CHECK.json'),
 'resolution':'Finalizer requires exact completed partial-supplement state,306 instances,237 sources,unknown whole model,and the source-receipt SHA from an independent units/tensor/source/subset-sum check. Protocol saturation and the research-advice wording are qualified. Later electrical clarifications identify logical ports and explicit NC nets.',
 'old_review_source_hash_not_rewritten':True,'whole_system_release_credit':False,'new_scientific_gate':False})
write(D/'results/VIEW_CHECK.json',{'status':'OBSERVED_RENDERED_REVIEW_PAGE_AND_NATIVE_ECAD_PDF','utc':datetime.now(timezone.utc).isoformat(),
 'review_url':'http://127.0.0.1:3253/wp10_mechatronic_closure_20260908/REVIEW.html','browser':'Codex in-app browser','review_tab_id':'4',
 'review_page':bind(D/'REVIEW.html'),'native_pdf':bind(D/'ecad/exports/WP09_SYSTEM_AND_STOP.pdf'),
 'observations':['Review page visibly shows full-system delivery NOT READY and306 material instances/237 STEP sources','Visible electrical figures identify99 schematic references and97 nets including16 NC nets','Native PDF viewer reports2 pages; first page layout and second-page component/net labels inspected, including second page at100% zoom'],
 'screenshot_file_paths':[],'screenshots_seen_in_UI_tool':True,'current_CAD_image_evidence_added':False,'scope':'Readability and presentation only; no physics or hardware acceptance'})
print('final scope disposition and actual UI observation receipt recorded')
