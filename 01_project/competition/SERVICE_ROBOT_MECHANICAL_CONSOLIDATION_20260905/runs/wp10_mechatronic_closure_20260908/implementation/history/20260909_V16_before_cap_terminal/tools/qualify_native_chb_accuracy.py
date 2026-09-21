"""Bind the retained SW accuracy probe to current, source-bound STEP evidence."""
from pathlib import Path
import json, hashlib, math
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
probe=read('results/NATIVE_CHB_ACCURACY_SCREEN.json')
parts=read('mechanical/NATIVE_COLD_INPUTS.json')
part=next(x for x in parts['parts'] if x['id']=='C09')
match=read('results/THERMAL_CORE_SOURCE_MATCH.json')
chb=next(x for x in match['checks'] if x['id']=='U202_CHB')
assert sha(part['step_path'])==part['source_sha256']==probe['input_sha256']['sources/CHB500W_STANDARD_OEM.step']
assert sha(part['native_path'])==probe['native_sha256']==probe['native_sha256_after']
assert sha(A/'mechanical/NATIVE_COLD_INPUTS.json')==match['native_input_sha256']==probe['input_sha256']['mechanical/NATIVE_COLD_INPUTS.json']
assert sha(A/'mechanical/thermal_core.step')==match['step_sha256']
assert match['checks_passed'] and chb['passed'] and part['expected_solids']==1
assert [r['accuracy_level'] for r in probe['rows']]==[0,1,2]
assert probe['relative_threshold']==1e-6 and not probe['threshold_changed']
assert probe['dirty_before'] is False and probe['dirty_after'] is False
assert all(sha(A/p)==v for p,v in probe['input_sha256'].items())
assert sha(A/'tools/check_native_chb_accuracy.py')==probe['source_script_sha256']
ref=chb['S_frame_reference_volume_mm3']
assert math.isfinite(ref) and ref>0
rows=[]
for r in probe['rows']:
    v=r['volume_mm3'];assert math.isfinite(v) and v>0
    e=abs(v-ref)/ref
    old=abs(v-probe['reference_GK']['volume_mm3'])/probe['reference_GK']['volume_mm3']
    assert abs(old-r['relative_difference_to_GK'])<1e-15
    rows.append(dict(accuracy_level=r['accuracy_level'],volume_mm3=v,relative_difference_to_source_bound_S_GK=e,within_original_threshold=e<1e-6))
assert all(not r['within_original_threshold'] for r in rows)
names=['results/NATIVE_CHB_ACCURACY_SCREEN.json','results/THERMAL_CORE_SOURCE_MATCH.json','mechanical/NATIVE_COLD_INPUTS.json','mechanical/thermal_core.step','sources/CHB500W_STANDARD_OEM.step','results/NATIVE_COLD_COLD.json']
result=dict(schema='WP10_NATIVE_CHB_ACCURACY_QUALIFICATION_V1',status='SOURCE_BOUND_RECOMPARISON_OPEN',
 input_sha256={p:sha(A/p) for p in names},source_script_sha256=sha(__file__),
 original_probe_unchanged=True,reference_S_GK_volume_mm3=ref,rows=rows,relative_threshold=1e-6,
 input_binding_checks_passed=True,source_geometry_equivalence_verified=False,
 limitations=['Original standalone diagnostic did not record generator/source hashes; it is not treated as self-proving provenance.',
 'Recomparison uses the separate STEP source-match receipt bound to current native inputs and assembly STEP; it does not retroactively add provenance to the earlier diagnostic.',
 'Probe cleared selection and included hidden bodies but did not read back SelectedItems or body count in that session; body count comes from the separate cold-read receipt.',
 'GK estimated relative integration error remains about3.55e-7; matching/refinement is not an absolute-volume or physical-mass guarantee.',
 'All three SW accuracy levels agree, which does not establish whether translation or integration caused the cross-kernel difference.'])
(A/'results/NATIVE_CHB_ACCURACY_QUALIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=result['status'],source_bound_relative_difference=rows[-1]['relative_difference_to_source_bound_S_GK'])))
