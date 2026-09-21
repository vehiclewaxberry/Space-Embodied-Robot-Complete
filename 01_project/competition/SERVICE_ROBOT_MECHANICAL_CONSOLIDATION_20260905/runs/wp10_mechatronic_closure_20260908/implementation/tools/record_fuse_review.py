"""Root records the completed read-only reviewer response, with frozen hashes."""
from pathlib import Path
import hashlib,json
A=Path(__file__).resolve().parents[1]
def read(q):return json.loads((A/q).read_text(encoding='utf-8-sig'))
def sha(q):return hashlib.sha256((A/q).read_bytes()).hexdigest()
def dump(q,v):(A/q).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
expected=read('results/FUSE_REVIEW_EXPECTED_SHA.json')
assert all(sha(q)==h for q,h in expected.items())
result=dict(schema='WP10_INPUT_PASSIVE_READONLY_REVIEW_V3',reviewer='/root/thermal_layout_readonly',recorded_by='root from completed independent read-only messages; reviewer did not write files or run CAD',reviewed_files=expected,review_complete=True,unrepaired_findings=[],scope='V15 selected fuses, current native topology, independent DC/thermal recomputation and unchanged C203 geometry binding; dependency SHA checks do not constitute renewed qualification',
 findings=['F201 OEM pad span12.60 correctly becomes pitch9.35; actual footprint pads match','F202 axial variant/ratings bound to November2025 PDF; no invented formed lead pitch','96 former zero-aux cases now include typical fuse cold resistance; other96 complete cases and SBP132 unchanged','Both fuse losses transferred from existing branch terms, not double counted','657 native pin/network/type mappings unchanged; only F201 footprint and F202 MPN changed','7 ERC violations and ignored checks retained','C203 design/plan/common source/footprint unchanged; exact payload only input SHA changed, interface only bindings changed'],
 independent_recalculation=dict(states=384,method='Newton in two independent branch-current equations; project solver not used',max_current_difference_A=1.066e-14,max_voltage_difference_V=1.066e-14,thermal_cells=4032,max_thermal_cell_difference_W=7.106e-14,max_csv_energy_residual_W=3.411e-13,checked_binding_entries=64),
 open=['Fuse inrush/clearing, BMS response, wiring/PCB damage and STOP dynamics','Installed thermal conditions and hot/life resistance','F202 formed lead footprint and mechanical installation; F201 board trace/thermal path','C203 ripple, near-CHB wiring, clamp/creep qualification and complete assembly','Full spacecraft mechatronic completion and same-revision propulsion ICD'],physical_tests_executed=False,whole_design_complete=False)
dump('results/INPUT_PASSIVE_READONLY_REVIEW.json',result)
prior=read('history/20260909_V14_before_fuse_coordination/results/INPUT_CAP_MOUNT_READONLY_REVIEW.json')
for q in prior['reviewed_files']:
 if q in expected:prior['reviewed_files'][q]=expected[q]
 else:assert sha(q)==prior['reviewed_files'][q]
prior['reviewed_files']['ecad/wp10_system.xml']=expected['ecad/wp10_system.xml']
prior['schema']='WP10_C203_INSTALLATION_READONLY_REVIEW_V2'
prior['scope']='V15 current XML binding and unchanged nominal geometry; independent review of V14-to-V15 exact/interface payload equivalence. Original mechanical qualification limitations retained.'
prior['native_rebinding_review']='results/INPUT_PASSIVE_READONLY_REVIEW.json'
prior['native_rebinding_review_sha256']=sha('results/INPUT_PASSIVE_READONLY_REVIEW.json')
prior['actual_geometry_checker_rerun']='logs/native_delta_cap_binding_v15.run.json'
assert all(sha(q)==h for q,h in prior['reviewed_files'].items())
dump('results/INPUT_CAP_MOUNT_READONLY_REVIEW.json',prior)
print('V15 independent readonly review recorded; all frozen hashes match')
