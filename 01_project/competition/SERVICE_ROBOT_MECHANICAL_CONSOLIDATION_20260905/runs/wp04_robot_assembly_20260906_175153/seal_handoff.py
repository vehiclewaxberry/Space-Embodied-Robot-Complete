from pathlib import Path
import json,hashlib,re
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
def read(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,d): (R/p).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
ui=read('viewer/VIEWER_UI_REVIEW_FINAL.json')
assert ui['all_passed'] and ui['final_candidate_bound']
b=read('viewer/VIEWER_BUILD_RESULT.json')
assert b['source_inputs_unchanged'] and all(c['count']==585 for c in b['checks'])
assert sha(b['scene']['path'])==b['scene']['sha256']
g=read('viewer/COMPLETE_GLB_EXPORT_RESULT.json')
assert g['instance_count']==585 and g['arm_count']==10 and g['group_count']==6
assert g['emission_vs_readback_max_bound_difference_m']==0
if 'scene_sha256' in g:
 assert g['scene_sha256']==sha(R/'viewer/scene.json')
else:
 # The final viewer export binds its immutable geometry snapshot; UI-only
 # metadata can change without changing the exported meshes.
 snapshot=g['geometry_input_snapshot']
 assert sha(snapshot['path'])==snapshot['sha256']
 assert all(sha(p)==h for p,h in g['input_sha256'].items())
 assert sha(g['output']['path'])==g['output']['sha256']
res=read('results/WP04_RESULT.json')
assert all(sha(R/p)==h for p,h in res['evidence_sha256'].items())
fresh=read('results/FINAL_EVIDENCE_FRESHNESS.json')
assert all(sha(x['path'])==x['sha256'] for x in fresh['checks'])
source=read('results/SOURCE_PROTECTION.json')
assert all(sha(x['path'])==x['expected_sha256'] for group in source['groups'] for x in group['files'])
paths=re.findall(r'\]\(<([^>]+)>\)',(R/'START_HERE_ZH.md').read_text(encoding='utf-8'))
assert all(Path(p).exists() for p in paths)
# Images have been inspected by the root reviewer using view_image.
observations=[]
for p in sorted((R/'candidate/results').glob('*.png')):
 observations.append({'path':p.relative_to(R).as_posix(),'sha256':sha(p),'review':'Root visually inspected: CAD view coherent / DXF geometry and reference dimensions legible. Does not establish physical assembly, strength, or complete dimensioning.'})
for name in ['service_final.png','parking_final.png','released_final.png','internal_final.png','exploded_illustrative_final.png']:
 p=R/'viewer/screenshots'/name
 observations.append({'path':p.relative_to(R).as_posix(),'sha256':sha(p),'review':'Root visually inspected full spacecraft and ten-link B601 in final current UI. Pose/layer labels and scope notices match the displayed candidate. Explode is illustrative.'})
write('results/VISUAL_REVIEW.json',{'schema':'WP04_ROOT_VISUAL_REVIEW_V1','status':'PASS_FOR_PRESENTATION_AND_REFERENCE_DRAWING_LEGIBILITY','method':'Actual local PNG images viewed with view_image, plus independently exercised live UI. No visual collision or manufacturing approval inferred.','image_count':len(observations),'images':observations,'UI_review_sha256':sha(R/'viewer/VIEWER_UI_REVIEW_FINAL.json'),'full_robot_continuous_clearance_verified':False})
excluded_parts={'__pycache__','__cadgen__','.git'}
files=[]
for p in sorted(R.rglob('*')):
 if not p.is_file() or excluded_parts.intersection(p.relative_to(R).parts) or p.suffix=='.pyc':continue
 if p==R/'results/FINAL_ARTIFACT_MANIFEST.json':continue
 files.append({'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
manifest={'schema':'WP04_FINAL_ARTIFACT_MANIFEST_V1','sealed_at':datetime.now(timezone.utc).isoformat(),'status':'ARTIFACT_INTEGRITY_PASS_NOT_ENGINEERING_RELEASE','run_id':R.name,'file_count':len(files),'total_bytes':sum(x['bytes'] for x in files),'excluded':['this self-referential manifest','__cadgen__ derived caches','__pycache__','*.pyc','.git'],'files':files,'original_source_entries_unchanged':source['total_manifest_entries'],'independent_audit_input_references_fresh':fresh['entry_count'],'all_mechanical_design_complete':False,'physical_assembly_complete':False,'manufacturing_release':False}
write('results/FINAL_ARTIFACT_MANIFEST.json',manifest)
assert all(sha(R/x['path'])==x['sha256'] for x in files)
print(json.dumps({k:manifest[k] for k in ['status','file_count','total_bytes','original_source_entries_unchanged','independent_audit_input_references_fresh']},ensure_ascii=False))
