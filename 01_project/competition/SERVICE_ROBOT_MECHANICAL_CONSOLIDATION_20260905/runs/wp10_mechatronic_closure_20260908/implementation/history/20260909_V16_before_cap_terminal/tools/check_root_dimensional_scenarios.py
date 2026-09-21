"""Declared nominal and tolerance scenarios, explicitly not as-built qualification."""
import json
from battery_variant_context import A,read,sha
c=read('mechanical/ROOT_BUSHING_DESIGN.json');d=c['declared_dimensional_scenarios'];m=c['material_source']
assert sha(A/m['file'])==m['sha256'];rho=m['density_g_cm3'];alpha=m['CLTE_below_Tg_average_per_K']
radial=[(d['hole_D_mm'][0]-d['stem_D_mm'][1])/2,(d['hole_D_mm'][1]-d['stem_D_mm'][0])/2]
wire=(d['bore_D_mm'][0]-d['bundle_OD_mm'][1])/2
eccentric=wire-radial[1]
rows=[]
for temp in [-20,23,80]:
    dt=temp-23;assumed_metal_alpha=23e-6
    min_hole=d['hole_D_mm'][0]*(1+assumed_metal_alpha*dt);max_stem=d['stem_D_mm'][1]*(1+alpha*dt)
    rows.append(dict(temperature_C=temp,minimum_hole_to_stem_radial_mm=(min_hole-max_stem)/2,metal_CLTE_assumed_per_K=assumed_metal_alpha))
out=dict(schema='WP10_ROOT_DIMENSIONAL_SCENARIOS_V1',source_script_sha256=sha(__file__),inputs={q:sha(A/q) for q in ['mechanical/ROOT_BUSHING_DESIGN.json','mechanical/root_bushing_common.py',m['file']]},
    hole_to_stem_radial_mm=radial,concentric_bore_to_max_bundle_radial_mm=wire,after_max_eccentricity_radial_mm=eccentric,
    minimum_nominal_wall_mm=(d['stem_D_mm'][0]-d['bore_D_mm'][1])/2,minimum_flange_capture_radial_overlap_mm=(d['flange_D_mm'][0]-d['hole_D_mm'][1])/2,
    temperature_scenarios=rows,nominal_screw_cylindrical_overlap_in_bridge_mm=c['keeper_z_local_mm'][0]+c['screw_nominal_total_length_mm'],nominal_screw_tip_to_blind_end_mm=c['thread_envelope_depth_mm']-(c['keeper_z_local_mm'][0]+c['screw_nominal_total_length_mm']),
    selected_material_density_for_local_estimates_g_cm3=rho,geometric_scenarios_positive=radial[0]>0 and eccentric>0 and all(r['minimum_hole_to_stem_radial_mm']>0 for r in rows),
    missing_in_tolerance_proof=['actual bundle OD and shape','hole location and split-half alignment','real machined stock anisotropy','actual temperature field','thread form/runout/locking','6D extraction, vibration and wear'],
    tolerance_qualified=False,effective_thread_engagement_proved=False,flight_temperature_range_qualified=False,strain_relief_verified=False,whole_design_complete=False)
assert out['geometric_scenarios_positive'] and abs(out['nominal_screw_tip_to_blind_end_mm']-.5)<1e-9
(A/'results/ROOT_DIMENSIONAL_SCENARIOS.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
