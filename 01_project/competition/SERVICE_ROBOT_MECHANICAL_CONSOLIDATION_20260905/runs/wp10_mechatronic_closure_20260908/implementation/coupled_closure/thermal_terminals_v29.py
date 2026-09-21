"""Same electrical source and V28 spreader; redistribute an existing loss allocation."""
from pathlib import Path
import ast,copy,json,math,hashlib,importlib.util
from spreader_design_v28 import augment_sheet
HERE=Path(__file__).resolve().parent;A=HERE.parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def run():
 c=read(HERE/'CANDIDATE_V29.json');oldc=read(HERE/'CANDIDATE.json')
 assert all(sha(p)==h for p,h in c['source_lock'].items())
 expected=copy.deepcopy(oldc['electrical']);expected['main_R_components_ohm']['copper_20C']=read(A/'power/MAIN_INPUT_COPPER_LOSS_V29.json')['R20_ohm'];assert c['electrical']==expected
 assert c['analysis_scenario']==oldc['analysis_scenario'] and c['thermal']==oldc['thermal']
 # Reuse the unchanged actual operating-point function without importing the
 # legacy module's old-candidate import-time guard or its unrelated solvers.
 p=HERE/'coupled_adapter.py';tree=ast.parse(p.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='operating_point')
 ns={'math':math,'power':module('wp10_shared_v29',A/'tools/shared_battery_path.py')};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),ns);op=ns['operating_point']
 sc=c['analysis_scenario'];args=[sc[k] for k in ['pack_V','shared_R_ohm','eta_main','hot_R_multiplier','copper_C']]
 points={'V28_REPLAY':op(oldc,*args),'V29_COPPER':op(c,*args)}
 model=module('wp10_spatial_v29',A/'tools/spatial_radiator_network.py');cfg=read(A/'thermal/BOTTOM_RADIATOR_MOUNT.json');view=read(A/'thermal/RADIATOR_MESH_VIEW_SCREEN.json');prior=read(A/'thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json');params=read(HERE/'SPREADER_PARAMETERS_V28.json')
 # V28 CAD+grid mask are unchanged; all their recorded inputs must still match.
 assert all(sha(A/p)==h for p,h in params['source_lock'].items())
 faces={r['face']['id']:r['face'] for r in view['results']};keys=['FIXED_MINUS_Z_BOTTOM_PLATE','FIXED_PLUS_Y','FIXED_MINUS_Y'];e=c['thermal']['environment'];env=[]
 for i,key in enumerate(keys):
  r=next(r for r in view['results'] if r['state']==e['state'] and r['face']['id']==key);env.append(dict(grid=r['model_surface_refinement'][-1]['spatial_grid'],occluder_K=e['occluder_K'],space_K=e['space_K'],solar_W_m2=e['solar_W_m2'] if i==1 else 0.))
 pr=next(r for r in prior['pressure_sensitivity'] if r['psi']==25);links=[dict(**ep,R_K_W=pr['per_link_R_K_W']) for ep in prior['links_endpoints']];rows=[]
 for pitch in [10.,5.]:
  sheets=[model.Sheet(faces[k],cfg if i==0 else None,pitch=pitch) for i,k in enumerate(keys)];augment_sheet(sheets[0],cfg,params['region_xy_mm'],params['height_mm'],params['conductivity_W_mK'])
  for version,point in points.items():
   h=point['heat_breakdown_W'];q=h['CHB'];base=sum(h[k] for k in ['Q201','shunts','fuse','copper','input_controller','input_startup'])
   for fraction in ([0.] if version=='V28_REPLAY' else [0.,.25,.5,1.]):
    local=h['other_main']*fraction;board=base+local
    loads=[dict(sheet=0,center=cfg['chb_path']['center_xy_mm'],size=[55.9,59],power_W=q),dict(sheet=1,center=[-40.,20.],size=[100.,80.],power_W=board)]
    r=model.solve(sheets,loads,links,env);T=r['source_peak_C'][0]+q*pr['case_interface_R_K_W']
    rows.append(dict(version=version,pitch_mm=pitch,existing_10mOhm_allocation_fraction_dissipated_on_board=fraction,allocated_local_terminal_heat_W=local,remaining_other_wiring_heat_W=h['other_main']-local,board_heat_W=board,CHB_case_C=T,CHB_margin_C=105-T,**r))
 ref=read(HERE/'SPREADER_THERMAL_V28.json');errors=[]
 for r in rows:
  if r['version']=='V28_REPLAY':
   old=next(o for o in ref['cases'] if o['variant']=='integral_left_spreader' and o['pitch_mm']==r['pitch_mm'] and o['case']=='CHB_PLUS_NEW_BOARD_PROPOSED_PATH');errors.append(abs(old['CHB_case_C']-r['CHB_case_C']))
 fine=[r for r in rows if r['version']=='V29_COPPER' and r['pitch_mm']==5]
 mesh=[abs(r['CHB_case_C']-next(s['CHB_case_C'] for s in rows if s['version']==r['version'] and s['pitch_mm']==10 and s['existing_10mOhm_allocation_fraction_dissipated_on_board']==r['existing_10mOhm_allocation_fraction_dissipated_on_board'])) for r in fine]
 checks=dict(same_V28_replay=max(errors)<1e-7,electrical_heat_balance=all(abs(p['heat_balance_residual_W'])<1e-7 for p in points.values()),spatial_heat_balance=all(abs(r['balance_error_W'])<1e-6 for r in rows),allocation_not_double_counted=all(abs(r['allocated_local_terminal_heat_W']+r['remaining_other_wiring_heat_W']-points[r['version']]['heat_breakdown_W']['other_main'])<1e-9 for r in rows),mesh_change_below_1C=max(mesh)<1,monotone_extra_local_heat=all(a['CHB_case_C']<b['CHB_case_C'] for a,b in zip(fine,fine[1:])))
 out=dict(candidate_sha256=sha(HERE/'CANDIDATE_V29.json'),script_sha256=sha(__file__),operating_point_source_sha256=sha(p),checks=checks,points=points,cases=rows,max_replay_error_C=max(errors),mesh_delta_C=mesh,continuous_thermal_closure=False,new_board_heat_patch_installed=False,terminal_resistance_measured=False,source_scope='Conditional allocation-location sensitivity; do not add 10 mOhm twice. Zero local allocation is not proof of zero contact loss.',whole_design_complete=False)
 (HERE/'TERMINAL_THERMAL_V29.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(checks=checks,refined=[dict(fraction=r['existing_10mOhm_allocation_fraction_dissipated_on_board'],case_C=r['CHB_case_C'],board_W=r['board_heat_W']) for r in fine])));assert all(checks.values())
if __name__=='__main__':run()
