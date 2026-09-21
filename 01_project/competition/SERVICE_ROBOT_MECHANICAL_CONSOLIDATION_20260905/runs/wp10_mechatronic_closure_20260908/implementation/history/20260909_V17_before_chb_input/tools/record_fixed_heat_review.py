"""Bind completed fixed-bay inspections and retained counterexamples."""
from pathlib import Path
import hashlib,json,datetime,psutil
A=Path(__file__).resolve().parents[1]
def read(p): return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,o): (A/p).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
states={s:read('results/FIXED_HEAT_'+s.upper()+'_INTERFACES.json') for s in ['service','parking','released']}
plan_sha=sha('mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
for s,r in states.items():
    assert r['source_plan_sha256']==plan_sha
    assert r['complete_coverage'] and not r['unknown'] and not r['positive_volume_intersections']
dump('results/FIXED_HEAT_INTERFACE_SUMMARY.json',dict(schema='WP10_FIXED_HEAT_TARGETED_THREE_STATE_V1',
    source_plan_sha256=plan_sha,exact_pairs_by_state={s:len(r['exact_pairs']) for s,r in states.items()},
    results={s:dict(path='results/FIXED_HEAT_'+s.upper()+'_INTERFACES.json',sha256=sha('results/FIXED_HEAT_'+s.upper()+'_INTERFACES.json')) for s in states},
    all_changed_neighborhoods_clear=True,scope='Replaced/new/moved target instances against the current 867-row source table; source STEP transforms, known unchanged thread proxies excluded',
    all_unchanged_pairs_tested=False,continuous_motion_verified=False,tool_access_verified=False,tolerances_verified=False,
    generic_whole_assembly_self_intersection_complete=False,full_native_assembly_generated=False))
names=['fixed_heat_bay_iso','fixed_heat_bay_top','fixed_heat_installation_iso','fixed_heat_wall_neg_iso','fixed_heat_wall_pos_iso','propulsion_power_route_iso','propulsion_data_route_iso','upper_deck_relocated_top']
shots=[]
for name in names:
    p=sorted((A/'review').glob(name+'_*.png'))[-1].relative_to(A).as_posix()
    shots.append(dict(path=p,sha256=sha(p),reviewed=True))
dump('results/FIXED_HEAT_VISUAL_REVIEW.json',dict(schema='WP10_FIXED_HEAT_VISUAL_REVIEW_V1',reviewed_by='root assistant via view_image',recorded_utc=now,
    files=shots,observed=['Two fixed walls and internal carrier seats connected in generated geometry','CHB and three resistor modules placed at opposing walls','DUAL clamp and power/data bundle routes follow the repaired layout','Upper deck is preserved with local hole changes'],
    dimensional_and_contact_credit_source='results/FIXED_HEAT_GEOMETRY.json',
    visual_claims_exclude=['Hidden tolerance fit','Thermal performance','Fastener preload','Whole spacecraft completed','Physical installation']))
names=['native_delta_fixed_heat_final','native_delta_fixed_heat_bounded_review','native_delta_fixed_heat_repair_verify']
guards=[read('logs/'+name+'.run.json') for name in names]
samples=[s for g in guards for s in g.get('samples',[])]
dump('results/FIXED_HEAT_MEMORY_AUDIT.json',dict(schema='WP10_FIXED_HEAT_MEMORY_AUDIT_V1',recorded_utc=now,
    statuses=[dict(name=g['name'],status=g['status'],available_start_mib=g['available_start_mib'],receipt='logs/'+g['name']+'.run.json') for g in guards],
    minimum_available_mib=min(s['available_mib'] for s in samples),maximum_sampled_task_rss_mib=max(s.get('combined_rss_mib',s.get('child_tree_rss_mib',0)) for s in samples),
    current_available_mib=psutil.virtual_memory().available/2**20,task_limit_mib=1400,global_floor_mib=512,
    cleanup_scope='Only guard-owned job process tree; no additional unrelated application killed during fixed heat work',
    terminated_failure_pids_not_running={str(pid):not psutil.pid_exists(pid) for pid in [48904,29896]},
    recovery='Serial per-solid validity plus explicit STEP interface checks; generic whole-assembly self-intersection remains incomplete',
    extra_user_application_closure_required=False))
dump('results/FIXED_HEAT_REVIEW_DISPOSITION.json',dict(schema='WP10_FIXED_HEAT_REVIEW_DISPOSITION_V1',
    sole_writer='root',readonly_reviewer='thermal_layout_readonly',repaired=[
      dict(id='HT01',issue='Single-sided carrier had no sized fixed radiative exit',change='Two monolithic source walls with external faces and actual OEM/TIM seats generated',closed_scope='Source geometry only; single-face heat rejection fails'),
      dict(id='HT02',issue='Back pocket skin modelled as full 8mm; source average masked hotspot',change='3.5mm pocket thickness map and source peak criterion',evidence='thermal/FIXED_RADIATOR_BUDGET.json'),
      dict(id='HT03',issue='New DATA route intersected trunk_clip_65 by45.84572184mm3',change='DUAL S(+6,-10,0), deck holes x106, remove initial DATA S bend',evidence='results/FIXED_HEAT_INTERFACE_SUMMARY.json'),
      dict(id='HT04',issue='Native-normalized transform applied to STEP authored in S caused false P60 penetration',change='Original V6 source manifest and SHA bound to T_S_step; native T separately retained; no extra P60 hole',evidence='tools/prepare_fixed_heat_integration.py'),
      dict(id='HT05',issue='Legacy GSE records had no precomputed AABB',change='Exact source STEP loaded for missing bboxes; source hashes checked; unknown count zero',evidence='tools/check_fixed_heat_interfaces.py')],
    open=['85% CHB heat needs distribution and environmental/area sizing','COTS heat pipe thermal resistance, route, mounting and microgravity/freeze validity','CHB/RB fasteners and measured TIM compression; OEM resistor hole revision mismatch','Battery/PMM installation, rest of sources and complete thermal network','Full native assembly and continuous motion/tool/tolerance closure'],
    failed_geometry_retained='results/FIXED_HEAT_SERVICE_COUNTEREXAMPLE_V1.json',
    new_thermal_negative='Single +Y radiator is above105C case even with ideal isothermal dark deep-space boundary',
    full_design_complete=False))
manifest=read('sources/FIXED_HEAT_PATH_SOURCE_MANIFEST.json')
scope={
 'az93_oem.html':'Optical beginning-of-life ranges and minimum thickness condition; no coating installation credit',
 'nasa_thermal_soa_2026.html':'Vacuum conduction/radiation, view factors and contact-pressure design context',
 'hydro_6061_2019.pdf':'6061 T6/T6511 typical25C conductivity167W/mK; not material certificate or guaranteed minimum',
 'ats_d10l300s66w_170.pdf':'SKU size, tolerances, temperature range and QT/Le/Lc capacity formula; no guaranteed bridge R or orbital qualification',
 'ats_heat_pipe_bender.pdf':'Inside versus centreline bend radius; empirical bend guidance not acceptance test',
 'boyd_copper_water_heatpipes.pdf':'Copper-water SKU comparison and gravity-aided typical performance; no orbital performance inheritance'}
for r in manifest:
    assert sha('sources/'+r['file'])==r['sha256']
    r.update(status='ACQUIRED_RELEVANT_DESIGN_FIELDS_REVIEWED',review_scope=scope[r['file']],reviewed_utc=now,qualification_credit=False)
dump('sources/FIXED_HEAT_PATH_SOURCE_MANIFEST.json',manifest)
print(json.dumps(dict(states={s:len(r['exact_pairs']) for s,r in states.items()},snapshots=len(shots),memory_available_mib=psutil.virtual_memory().available/2**20)))
