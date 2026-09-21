"""Geometry-bound paired V28/V33 test, with unchanged V32 conditional heat."""
from pathlib import Path
import ast,copy,json,math,hashlib,importlib.util
import numpy as np
from spreader_design_v28 import augment_sheet
HERE=Path(__file__).resolve().parent;A=HERE.parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def run():
 dest=HERE/'SPREADER_THERMAL_V33.json';assert not dest.exists()
 replay_sources={'SPREADER_GEOMETRY_V28.json':'2e7760d8d6a386427bccc7ad8981f1a28c551f3b5cb7e0218a5d738acae427da','TERMINAL_THERMAL_V29.json':'fc3ffc712485b2f29cf1fec53c24efa1dd9e6fb602a4b2cd4590caa7797fcfef'}
 assert all(sha(HERE/k)==v for k,v in replay_sources.items())
 p=read(HERE/'SPREADER_PARAMETERS_V33.json');oldp=read(HERE/'SPREADER_PARAMETERS_V28.json')
 assert all(sha(A/k)==v for k,v in p['source_lock'].items())
 c=read(HERE/'CANDIDATE_V30.json');v32=read(HERE/'CANDIDATE_V32.json')
 assert all(sha(k)==v for k,v in c['source_lock'].items())
 assert all(sha(k)==v for k,v in v32['source_lock'].items())
 copper=read(A/'power/MAIN_INPUT_COPPER_LOSS_V32.json')
 assert c['electrical']['main_R_components_ohm']['copper_20C']==copper['R20_ohm']
 c['electrical']['main_R_components_ohm']['copper_20C']=copper['R20_ohm']
 g=read(HERE/'SPREADER_GEOMETRY_V33.json');assert all(g['checks'].values())
 assert g['new_step_sha256']==sha(HERE/'spreader_v33.step')
 assert g['parameter_sha256']==sha(HERE/'SPREADER_PARAMETERS_V33.json')
 tree=ast.parse((HERE/'coupled_adapter.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='operating_point')
 ns={'math':math,'power':module('wp10_shared_v33',A/'tools/shared_battery_path.py')};exec(compile(ast.Module(body=[node],type_ignores=[]),'coupled_adapter.py','exec'),ns)
 sc=c['analysis_scenario'];point=ns['operating_point'](c,*[sc[k] for k in ['pack_V','shared_R_ohm','eta_main','hot_R_multiplier','copper_C']])
 h=point['heat_breakdown_W'];q=h['CHB'];board=sum(h[k] for k in ['Q201','shunts','fuse','copper','input_controller','input_startup'])
 cases={'CHB_ONLY':0.,'BOARD_TERMINAL_ALLOCATION_0':board,'BOARD_TERMINAL_ALLOCATION_100':board+h['other_main'],'ALL_KNOWN_NONARM_HYPOTHETICAL':sum(h.values())-q}
 model=module('wp10_spatial_v33',A/'tools/spatial_radiator_network.py');cfg=read(A/'thermal/BOTTOM_RADIATOR_MOUNT.json');view=read(A/'thermal/RADIATOR_MESH_VIEW_SCREEN.json');prior=read(A/'thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json')
 pr=next(r for r in prior['pressure_sensitivity'] if r['psi']==25);links=[dict(**ep,R_K_W=pr['per_link_R_K_W']) for ep in prior['links_endpoints']]
 keys=['FIXED_MINUS_Z_BOTTOM_PLATE','FIXED_PLUS_Y','FIXED_MINUS_Y'];faces={r['face']['id']:r['face'] for r in view['results']};e=c['thermal']['environment'];env=[]
 for i,key in enumerate(keys):
  r=next(r for r in view['results'] if r['state']==e['state'] and r['face']['id']==key)
  env.append(dict(grid=r['model_surface_refinement'][-1]['spatial_grid'],occluder_K=e['occluder_K'],space_K=e['space_K'],solar_W_m2=e['solar_W_m2'] if i==1 else 0.))
 rows=[];matrices=[]
 for pitch in [10.,5.]:
  for name,param,vol in [('V28',oldp,read(HERE/'SPREADER_GEOMETRY_V28.json')['added_volume_mm3']),('V33',p,g['added_volume_mm3'])]:
   # Fresh original geometry for EACH variant. Never add V33 onto V28 thickness.
   sheets=[model.Sheet(faces[k],cfg if i==0 else None,pitch=pitch) for i,k in enumerate(keys)]
   before=sheets[0].L.copy();area=float(sum(s.area.sum() for s in sheets));augment_sheet(sheets[0],cfg,param['region_xy_mm'],0.)
   z=sheets[0].L-before;zero=0. if z.nnz==0 else float(abs(z.data).max())
   sampled=augment_sheet(sheets[0],cfg,param['region_xy_mm'],param['height_mm'],param['conductivity_W_mK'])
   L=sheets[0].L;asym=L-L.T
   matrices.append(dict(variant=name,pitch_mm=pitch,zero_height_error=zero,symmetry_error=0. if asym.nnz==0 else float(abs(asym.data).max()),row_sum_error=float(abs(np.asarray(L.sum(axis=1))).max()),area_delta_m2=float(sum(s.area.sum() for s in sheets))-area,sampled_volume_mm3=sampled,CAD_volume_mm3=vol,volume_relative_error=abs(sampled-vol)/vol))
   for case,extra in cases.items():
    loads=[dict(sheet=0,center=cfg['chb_path']['center_xy_mm'],size=[55.9,59],power_W=q)]
    if extra:loads.append(dict(sheet=1,center=[-40.,20.],size=[100.,80.],power_W=extra))
    r=model.solve(sheets,loads,links,env);T=r['source_peak_C'][0]+q*pr['case_interface_R_K_W']
    rows.append(dict(variant=name,pitch_mm=pitch,case=case,CHB_case_C=T,CHB_margin_C=c['thermal']['CHB_case_limit_C']-T,CHB_heat_W=q,added_heat_W=extra,**r))
    print(name,pitch,case,round(T,6),flush=True)
 replay=[];ref=read(HERE/'TERMINAL_THERMAL_V29.json')
 for r in rows:
  if r['variant']=='V28' and r['case'].startswith('BOARD_TERMINAL'):
   frac=0. if r['case'].endswith('_0') else 1.
   old=next(v for v in ref['cases'] if v['version']=='V29_COPPER' and v['pitch_mm']==r['pitch_mm'] and v['existing_10mOhm_allocation_fraction_dissipated_on_board']==frac)
   replay.append(abs(r['CHB_case_C']-old['CHB_case_C']))
 refined=[r for r in rows if r['pitch_mm']==5 and r['variant']=='V33']
 mesh={r['case']:abs(r['CHB_case_C']-next(v['CHB_case_C'] for v in rows if v['variant']=='V33' and v['pitch_mm']==10 and v['case']==r['case'])) for r in refined}
 checks=dict(parent_temperature_replay=max(replay)<1e-7,electrical_balance=abs(point['heat_balance_residual_W'])<1e-7,thermal_energy_balance=all(abs(r['balance_error_W'])<1e-6 for r in rows),zero_height_exact=all(r['zero_height_error']==0 for r in matrices),symmetric_conservative_matrix=all(r['symmetry_error']<1e-10 and r['row_sum_error']<1e-10 for r in matrices),radiating_area_unchanged=all(abs(r['area_delta_m2'])<1e-12 for r in matrices),CAD_to_thermal_volume_within_1_percent=all(r['volume_relative_error']<.01 for r in matrices),mesh_change_under_1C=max(mesh.values())<1.)
 out=dict(schema='WP10_V33_GEOMETRY_BOUND_PAIRED_THERMAL',script_sha256=sha(__file__),parameter_sha256=sha(HERE/'SPREADER_PARAMETERS_V33.json'),geometry_sha256=sha(HERE/'SPREADER_GEOMETRY_V33.json'),electrical_candidate_sha256=sha(HERE/'CANDIDATE_V32.json'),operating_point=point,cases=rows,matrix_checks=matrices,mesh_delta_C=mesh,max_parent_replay_error_C=max(replay),checks=checks,increment_vs_V28_mass_kg=g['increment_vs_V28_mass_kg'],case_interface_R_K_W=pr['case_interface_R_K_W'],per_link_R_K_W=pr['per_link_R_K_W'],new_board_heat_path_installed=False,whole_design_complete=False,continuous_thermal_closure=False,limits_C=dict(CHB_case=105,Q201_junction=150),limitations=['360W point and released environment remain illustrative, not approved orbit/load profile.','25psi TIM impedance is typical sensitivity, actual pressure unknown.','+Y board heat patch still hypothetical; V30 cover thermal effects unsolved.','Arm/battery/output-distribution/regen heat incomplete. Existing other_main loss relocated, not added twice.','Mass and conductivity are project assumptions; no preload, tolerance, strength or new 3D interface validation.'])
 out['replay_reference_source_lock']=replay_sources
 with dest.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
 print(json.dumps(dict(checks=checks,mesh_delta_C=mesh,refined=[dict(case=r['case'],CHB_C=r['CHB_case_C']) for r in refined])));assert all(checks.values())
if __name__=='__main__':run()
