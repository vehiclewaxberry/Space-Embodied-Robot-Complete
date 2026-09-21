"""Promote only individually verified rows from an interrupted import receipt."""
from native_integrate import *

ap=argparse.ArgumentParser();ap.add_argument('receipt');a=ap.parse_args()
source=OUT/'results'/a.receipt;r=read(source)
assert r['status']=='FAILED'
plan={q['id']:q for q in read(OUT/'inputs/ALL_IMPORT_PLAN.json')['parts']}
rows=[]
for q in r['parts']:
    if q.get('volume_numeric_screen_pass') is not True:continue
    p=plan[q['id']];cold=q['part_cold_reopen'];facts=cold['facts']
    assert q['status']=='NATIVE_PART_SAVED_CLOSED_REOPENED_VERIFIED_AND_CLOSED'
    assert q['source_sha256']==p['source_sha256']==m.sha(p['step_path'])
    assert q['native_save']['sha256']==m.sha(p['native_path'])
    assert q['import_errors']==cold['errors']==q['external_reference_count']==q['auxiliary_reference_count']==0
    assert facts['solid_count']==p['expected_solids'] and facts['sheet_count']==0
    assert cold['bbox_max_error_mm']<=cold['tolerance_mm']
    assert abs(facts['volume_mm3']-p['expected_volume_mm3'])<=max(1e-4,p['expected_volume_mm3']*1e-5)
    rows.append(q)
assert rows
target=source.with_name(source.stem+'_verified_subset.json');assert not target.exists()
write(target,{'status':'PASS_VERIFIED_SUBSET_OF_INTERRUPTED_IMPORT','parts':rows,
    'import_plan_sha256':m.sha(OUT/'inputs/ALL_IMPORT_PLAN.json'),
    'interrupted_receipt':str(source),'interrupted_receipt_sha256':m.sha(source),
    'scope':'Existing saved-and-cold-read per-part records independently checked against current files; no new COM read and no failed row promoted.',
    'whole_design_complete':False})
print(len(rows),target)
