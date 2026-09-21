"""Record root's actual image review and bind this revision's independent checks."""
from pathlib import Path
import argparse,json,hashlib,datetime,psutil
A=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser()
ap.add_argument('--reviewed',nargs=5,required=True,help='Five actual images inspected by root: core iso/front/top/bottom, bay iso')
args=ap.parse_args()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,r):(A/p).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
keys=['thermal_core_iso','thermal_core_front','thermal_core_top','thermal_core_bottom','fixed_heat_bay_iso']
shots={}
for key,name in zip(keys,args.reviewed):
    path=(A/name).resolve();assert path.is_file() and path.suffix=='.png' and path.is_relative_to(A/'review')
    shots[key]=path.relative_to(A).as_posix()
plan=read('mechanical/FIXED_HEAT_INSTANCE_PLAN.json');assert plan['candidate_component_count']==894
ph=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
files=[
 'mechanical/FIXED_HEAT_INSTANCE_PLAN.json','mechanical/NATIVE_COLD_INPUTS.json',
 'thermal/BOTTOM_RADIATOR_MOUNT.json','thermal/FIXED_HEAT_PATH.json','sources/COLD_TIM_SELECTION.json',
 'thermal/COLD_TIM_INTERFACE_CONTRACT.json','mechanical/COLD_PATH_INSTANCE_BOM.csv',
 'results/COLD_PATH_GEOMETRY.json','results/BOTTOM_MOUNT_GEOMETRY.json','results/FIXED_HEAT_GEOMETRY.json',
 'results/COLD_PATH_TOOL_ACCESS.json','results/THERMAL_CORE_SOURCE_MATCH.json',
 'thermal/RADIATOR_MESH_VIEW_SCREEN.json','thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json',
 'results/NATIVE_COLD_IMPORT.json','results/NATIVE_COLD_ASSEMBLE.json','results/NATIVE_COLD_COLD.json',
 'tools/spatial_radiator_network.py','tools/radiator_mesh_view_screen.py','mechanical/thermal_core.step',
 'mechanical/thermal_core.step.py','mechanical/bottom_radiator_common.py','mechanical/fixed_heat_common.py',
 'tools/build_bottom_native.py','tools/check_thermal_core_source.py',
 'results/COLD_SOURCE_MATCH_DIAGNOSTIC.json',
 'results/NATIVE_CHB_ACCURACY_SCREEN.json','tools/check_native_chb_accuracy.py',
 'results/NATIVE_CHB_ACCURACY_QUALIFICATION.json','tools/qualify_native_chb_accuracy.py',
 'power/BATTERY_INSTALLATION_INTERFACE.json','results/RRC_BATTERY_PACKAGING_SCREEN.json',
 'tools/record_battery_installation_intake.py','tools/scan_rrc_packaging.py',
 *[f'results/FIXED_HEAT_{s}_INTERFACES.json' for s in ['SERVICE','PARKING','RELEASED']],
 *[f'results/COLD_CAD_{p}.json' for p in ['CORE','LEAVES','ASSEMBLIES','SNAPSHOTS']]
]
for key in ['COLD_PATH_GEOMETRY','BOTTOM_MOUNT_GEOMETRY','FIXED_HEAT_GEOMETRY','COLD_PATH_TOOL_ACCESS','THERMAL_CORE_SOURCE_MATCH']:
    assert read('results/'+key+'.json')['checks_passed']
for phase in ['CORE','LEAVES','ASSEMBLIES','SNAPSHOTS']:
    assert all(c['returncode']==0 for c in read('results/COLD_CAD_'+phase+'.json')['commands'])
match=read('results/THERMAL_CORE_SOURCE_MATCH.json')
assert match['step_sha256']==sha(A/'mechanical/thermal_core.step') and match['native_input_sha256']==sha(A/'mechanical/NATIVE_COLD_INPUTS.json')
native=read('results/NATIVE_COLD_COLD.json')
assert native['status']=='PASS_COLD_NATIVE_38_INSTANCES_38_SOLIDS_TRANSFORMS_LOCAL_DEPENDENCIES'
assert native['source_plan_sha256']==ph
dump('results/COLD_PATH_REVIEW_DISPOSITION.json',dict(schema='WP10_COLD_PATH_REVIEW_DISPOSITION_V1',
 source_plan_sha256=ph,inputs={p:sha(A/p) for p in files},snapshots=shots,
 snapshot_sha256={key:sha(A/p) for key,p in shots.items()},snapshots_actually_reviewed=True,
 all_current_source_checks_recorded=True,root_only_writer=True,one_readonly_reviewer_per_wave=True,
 native_source_volume_comparison_all_passed=False,native_source_volume_comparison_open_ids=['C09'],
 geometric_findings=['CHB actual horizontal OEM body is on central bottom pedestal, pins face upward',
 'Two L cold fingers are integral to bottom plate; nominal pads separate their endpoints from sidewall seats',
 'Four underside CHB mounting heads and six retained base mounting groups are represented',
 'Local thermal bay contains current walls, heat devices and neighboring project carriers',
 'Images do not prove hidden clearance, preload, thermal performance or complete894 native assembly'],
 dispositions=[
 dict(id='CR01',finding='Old actual TSP1600S cold path exceeded105C in refined folded330K/+Ysun CHB-only case',action='Preserve105.141870C counterexample; change three real TIMs to sourced TSP1800ST and update seat/finger geometry, retain360W arm duty and105C limit'),
 dict(id='CR02',finding='New material lower typical dielectric breakdown and nominal thickness differs from compressed interface',action='Record3000vs5500Vac tradeoff, metal-screw electrical bypass, pressure/force sensitivity and unverified compression/preload'),
 dict(id='CR03',finding='Folded-state tool oracle originally omitted PV cell and bond solids attached to solar wings',action='Recognize exact PV cell/bond IDs as expected blockers; retain8 blocked tools and require deployed preassembly'),
 dict(id='CR04',finding='Publication could reuse old algorithm/image evidence',action='Bind solver/view source SHA, current plan/native receipts and all reviewed image bytes in publisher'),
 dict(id='CR05',finding='Pressure sweep context was absent from individual results',action='Record released/330K/+Y1361Wm2/5mm and equal pressure on all3TIMs, residuals and25psi baseline agreement')
 ,dict(id='CR06',finding='Independent cold SW session was previously a text field',action='Assert distinct owned PID/create_time from both import and assembly; persist cleanup receipt')
 ,dict(id='CR07',finding='Main BOM and component-study brief still referenced old converter seat/TIM',action='Point current selected BOM to bottom pedestal and TSP1800ST; emit current3TIM interface and38-instance map; mark retained old local study as predecessor')
 ,dict(id='CR08',finding='CHB default volume integration differs by1.765e-4mm3 after serialization; ordinary adaptive Gauss did not converge',action='Retain negative diagnostics; use GK spline-span integration and two eps levels on local/S/assembly; preserve bbox1e-5mm and same-method volume1e-4mm3 screen. GK/default absolute volumes differ0.1046%; reported error estimate is not removed by relative agreement; no absolute volume, mass or BRep-equivalence certification.')
 ,dict(id='CR09',finding='SW C09 differs from default and GK reference volumes; SW/GK difference1.16178e-6 exceeds original1e-6',action='Archive initial failed import unchanged. Keep C09 cross-kernel comparison OPEN in import/assembly/cold/ZIP/page and keep original threshold. Proceed only with saved-file, body-count, fixed-pose and dependency readback. Do not transfer sourceSTEP contact/clearance to native C09.')
 ],continuous_thermal_verified=False,whole894_native_verified=False,whole_engineering_complete=False))
review=read('results/COLD_PATH_REVIEW_DISPOSITION.json')
review['dispositions'].append(dict(id='CR10',finding='Existing body mass API has density argument but no explicit accuracy selection',action='Read the unchanged C09 in a separate owned SW session using IMassProperty2, SI units, cleared selection, included hidden bodies, Recalculate and levels0/1/2. All levels returned the same volume; maximum accuracy still exceeds original threshold. Keep OPEN; do not claim accuracy setting explains the discrepancy or that volume alone proves shape damage.'))
review['dispositions'].append(dict(id='CR11',finding='Old90x170x65 battery proxy cannot stand for the selected189.5x85.5x82.2 RRC pack; website MC35 wording can be misread as7mm power-contact pitch',action='Bind D outline/max tolerances and connector drawing B; record actual29mm power-contact separation without inventing electrical pin mapping. Preserve unknown battery socket datum and retention interfaces; current A manual does not override D. Readonly manufacturer-review wave completed.'))
review['dispositions'].append(dict(id='CR12',finding='Conservative box packing can falsely be presented as actual geometric impossibility',action='Keep service-state CAD, explicit domain and2mm project gap, six axis permutations, retained legacy battery, nonconvex deferred-check branch, and full_geometry_infeasibility_proved=false. Readonly reviewer found no blocking error; no battery CAD added or whole design pass claimed.'))
dump('results/COLD_PATH_REVIEW_DISPOSITION.json',review)
records=[]
for f in sorted([q for q in (A/'logs').glob('native_delta_*.run.json') if q.name.startswith(('native_delta_cold','native_delta_battery_packaging'))]):
    r=json.loads(f.read_text());samples=r.get('samples',[])
    records.append(dict(path=f.relative_to(A).as_posix(),sha256=sha(f),status=r['status'],
     available_start_mib=r['available_start_mib'],
     min_available_mib=min((s['available_mib'] for s in samples),default=r['available_start_mib']),
     peak_combined_rss_mib=max((s.get('combined_rss_mib',s['child_tree_rss_mib']) for s in samples),default=0),
     own_tree_cleanup_by_job=True,unrelated_processes_terminated=False))
assert not any(r['status']=='RUNNING' for r in records)
dump('results/COLD_PATH_MEMORY_AUDIT.json',dict(schema='WP10_COLD_PATH_MEMORY_AUDIT_V1',
 recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 available_now_mib=psutil.virtual_memory().available/2**20,runs=records,
 recovery='results/COLD_PATH_MEMORY_RECOVERY.json',applications_terminated=[],
 start_floor_mib=2048,runtime_available_floor_mib=512,combined_owned_rss_cap_mib=1400,
 explanation='Only identified idle Codex Python tool-service working sets reclaimed; reloadable pages, no session/process termination. A blocked before-start attempt and all actual earlier counterexamples remain in logs.'))
print(json.dumps(dict(reviewed_images=len(shots),source_instances=894,native_core_instances=38)))
