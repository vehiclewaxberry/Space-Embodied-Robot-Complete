"""Incorporate the independent review wording and repack checked artifacts."""
from pathlib import Path
import json,hashlib,zipfile,shutil
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
replacements={
 '24正交朝向、18000位置有限筛查':'枚举24个正交朝向，其中8个能在声明搜索箱内生成网格、16个不适配，共18000位置有限筛查',
 '24个正交朝向、18,000个有限网格位置':'枚举24个正交朝向，其中8个在声明搜索箱内生成网格、16个不适配，共18,000个有限网格位置'}
for path in [A/'tools/publish_spreader_v33.py',C/'README_V33.md',C/'REVIEW_V33.html']:
 s=path.read_text(encoding='utf-8')
 for old,new in replacements.items():s=s.replace(old,new)
 path.write_text(s,encoding='utf-8')
screen=read(C/'LAYOUT_SCREEN_V33.json');assert sum(v>0 for v in screen['positions_per_rotation'])==8
record=dict(reviewer='/root/v31_mechanical',mode='READ_ONLY',date='2026-09-13',verdict='PASS_SCOPED',matrix_source_alignment_verified=True,trial_three_states_974_single_replacement=True,active_candidate_remains_V32=True,orientation_count=24,orientations_with_nonempty_grid=8,positions=18000,native_shortlist=3,collisions_each_state=[8,7,7],global_layout_infeasibility_proven=False,whole_design_complete=False,source_lock={str(p.relative_to(A)):sha(p) for p in [C/'layout_screen_v33.py',C/'layout_exact_v33.py',C/'LAYOUT_SCREEN_V33.json',C/'LAYOUT_EXACT_V33.json',C/'SPREADER_INSTANCE_PLAN_V33_TRIAL.json']})
review=C/'LAYOUT_INDEPENDENT_REVIEW_V33.json'
with review.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2,ensure_ascii=False)
manifest_path=C/'V33_REVIEW_SOURCE_MANIFEST.json';manifest=read(manifest_path)
manifest[str(review.relative_to(A))]=sha(review);manifest[str(Path(__file__).relative_to(A))]=sha(__file__)
for p in list(manifest):manifest[p]=sha(A/p)
manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
archive=C/'WP10_RESUME_V32_V33_REVIEW.zip';history=C/'history/V33_initial_replay'
shutil.copy2(archive,history/'review_before_final_wording.zip')
tmp=C/'WP10_RESUME_V32_V33_REVIEW.tmp.zip';assert not tmp.exists()
with zipfile.ZipFile(tmp,'x',zipfile.ZIP_DEFLATED) as z:
 for name in list(manifest)+[str(manifest_path.relative_to(A))]:z.write(A/name,name.replace('\\','/'))
with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
tmp.replace(archive)
receipt=read(C/'PUBLISH_RECEIPT_V33.json');receipt.update(archive_sha256=sha(archive),files=len(manifest)+1,final_independent_review='LAYOUT_INDEPENDENT_REVIEW_V33.json');(C/'PUBLISH_RECEIPT_V33.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
assert all(sha(A/k)==v for k,v in manifest.items())
print(json.dumps(dict(files=len(manifest)+1,source_hash_mismatches=0,ZIP_CRC='PASS',active_revision=read(A/'CURRENT_WORKING_CANDIDATE.json')['revision'])))
