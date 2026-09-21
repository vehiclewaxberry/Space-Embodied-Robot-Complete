from pathlib import Path
import json,hashlib,datetime,psutil
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,r):(A/p).write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
plan=read('mechanical/FIXED_HEAT_INSTANCE_PLAN.json');ph=sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json');counts={};inputs={}
for st in ['service','parking','released']:
    path=f'results/FIXED_HEAT_{st.upper()}_INTERFACES.json';r=read(path)
    assert r['source_plan_sha256']==ph and r['zero_positive_volume_intersections'] and r['complete_coverage']
    counts[st]=len(r['exact_pairs']);inputs[path]=sha(A/path)
dump('results/FIXED_HEAT_INTERFACE_SUMMARY.json',dict(schema='WP10_FIXED_HEAT_INTERFACE_SUMMARY_V3',source_plan_sha256=ph,inputs=inputs,exact_pairs_by_state=counts,
 all_changed_neighborhoods_clear=True,candidate_components=plan['candidate_component_count'],whole_assembly_verified=False,continuous_motion_verified=False,full_tool_insertion_verified=False,tolerance_verified=False))
shots=['bottom_mount_assembly_bottom_revision_iso_20260908T220521Z.png','bottom_mount_assembly_bottom_revision_bottom_20260908T220521Z.png','bottom_mount_assembly_bottom_revision_top_20260908T220521Z.png','fixed_heat_bay_bottom_revision_iso_20260908T220527Z.png','fixed_heat_bay_bottom_revision_bottom_20260908T220527Z.png']
dump('results/BOTTOM_VISUAL_REVIEW.json',dict(schema='WP10_BOTTOM_VISUAL_REVIEW_V1',source_plan_sha256=ph,
 inspected_by_root=['iso bottom mount','bottom bottom mount','top bottom mount','iso current thermal bay','bottom current thermal bay'],snapshots=[dict(path='review/'+f,sha256=sha(A/'review'/f)) for f in shots],
 findings=['Six flush countersunk screw heads visible on exterior bottom face','Four existing angle sections remain separate and align with deck','New bottom plate is visibly integrated with two sidewalls and current routes in local bay','No whole884 assembly, hidden-equipment clearance or thermal performance is inferred from images'],
 actual_geometric_checks='results/BOTTOM_MOUNT_GEOMETRY.json',source_level_mates=True,motion_mates_in_STEP_or_SW=False))
dump('results/BOTTOM_REVIEW_DISPOSITION.json',dict(schema='WP10_BOTTOM_REVIEW_DISPOSITION_V1',source_plan_sha256=ph,root_only_writer=True,one_readonly_reviewer_per_wave=True,
 dispositions=[dict(id='BR01',finding='Catalog washer actual1.1mm differs from label0.55 and supplier nominal0.5',action='Reject catalogsolid; reconstruct sourced0.5mm washer',evidence='sources/BOTTOM_VENDOR_SOURCES.json'),
 dict(id='BR02',finding='Catalog screw claimedISO10642 but headbounds5.639 differ from current6.72',action='Reconstruct project nominal6.72/1.86/20 from Wuerth4123 53 20; do not claim OEM CAD'),
 dict(id='BR03',finding='First6mount layout yielded28 positive common-volume intersections with adapters/equipment',action='Preserve counterexample under history; relocate supports and use existing angles',evidence='history/20260909_bottom_mount_first_fit_failed/FIXED_HEAT_SERVICE_INTERFACES.json'),
 dict(id='BR04',finding='Outer4bosses crossed existing angle flanges',action='Shorten4bosses to-104.15; drill four hash-bound original angles; keep2inner at-101.15',evidence='results/BOTTOM_MOUNT_GEOMETRY.json'),
 dict(id='BR05',finding='Old source/native pose inference lost later wing spacing',action='Current-versus-baseline native rigid delta applied to identical STEP source;18wing readbacks',evidence='results/FIXED_HEAT_STEP_FRAME_REPAIR.json'),
 dict(id='BR06',finding='Early z=-114 bottom view probe was inside old plate',action='Correct outerplane to-114.15, then bind actual current bottom planar face holes',evidence='thermal/RADIATOR_MESH_VIEW_SCREEN.json'),
 dict(id='BR07',finding='Expanded hot radiator would inherit unqualified battery_thermal_link',action='Remove old link in candidate only; battery controlled thermal path stays open'),
 dict(id='BR08',finding='BRIEF lagged source while reviewer was reading',action='Final brief updated to(-140,+/-93.5),(-60,+/-33),(120,+/-93.5),fourangle/twodeck/24body')],
 full_engineering_completion=False))
records=[]
for f in sorted((A/'logs').glob('native_delta_bottom*.run.json')):
    r=json.loads(f.read_text());samples=r.get('samples',[])
    records.append(dict(path=f.relative_to(A).as_posix(),status=r['status'],available_start_mib=r['available_start_mib'],
      min_available_mib=min((s['available_mib'] for s in samples),default=r['available_start_mib']),peak_combined_rss_mib=max((s.get('combined_rss_mib',s['child_tree_rss_mib']) for s in samples),default=0),own_tree_cleanup_by_job=True,unrelated_processes_terminated=False))
dump('results/BOTTOM_MEMORY_AUDIT.json',dict(schema='WP10_BOTTOM_MEMORY_AUDIT_V1',recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),available_now_mib=psutil.virtual_memory().available/2**20,
 runs=records,unrelated_processes_terminated=[],idle_task_geometry_processes_found=0,review_server_pid4112_retained=True,
 explanation='User freed other pages; task began above2GiB. No eligible orphan geometry process identified.240s review timeout cleaned owned child tree; completed8leaf checks reused only after sourceSTEPsha binding.'))
print(json.dumps(dict(states=counts,components=plan['candidate_component_count'],shots=len(shots))))
