"""Paired baseline/new-thickness scenarios; keep heat inputs and boundaries fixed."""
import json
import numpy as np
from coupled_adapter import A,HERE,read,sha,module,load_candidate,operating_point
from spreader_design_v28 import augment_sheet

def run():
    dest=HERE/'SPREADER_THERMAL_V28.json';assert not dest.exists()
    c=load_candidate();p=read(HERE/'SPREADER_PARAMETERS_V28.json')
    assert all(sha(A/rel)==h for rel,h in p['source_lock'].items())
    g=read(HERE/'SPREADER_GEOMETRY_V28.json')
    assert g['parameter_sha256']==sha(HERE/'SPREADER_PARAMETERS_V28.json')
    assert g['new_step_sha256']==sha(HERE/'spreader_v28.step')
    sc=c['analysis_scenario'];tc=c['thermal'];e=tc['environment']
    model=module('wp10_spatial_v28',A/'tools/spatial_radiator_network.py')
    cfg=read(A/'thermal/BOTTOM_RADIATOR_MOUNT.json');view=read(A/'thermal/RADIATOR_MESH_VIEW_SCREEN.json')
    old=read(A/'thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json')
    pr=next(r for r in old['pressure_sensitivity'] if r['psi']==25)
    keys=['FIXED_MINUS_Z_BOTTOM_PLATE','FIXED_PLUS_Y','FIXED_MINUS_Y']
    faces={r['face']['id']:r['face'] for r in view['results']};env=[]
    for i,k in enumerate(keys):
        r=next(r for r in view['results'] if r['state']==e['state'] and r['face']['id']==k)
        env.append(dict(grid=r['model_surface_refinement'][-1]['spatial_grid'],occluder_K=e['occluder_K'],
                        space_K=e['space_K'],solar_W_m2=e['solar_W_m2'] if i==1 else 0.))
    links=[dict(**ep,R_K_W=pr['per_link_R_K_W']) for ep in old['links_endpoints']]
    point=operating_point(c,sc['pack_V'],sc['shared_R_ohm'],sc['eta_main'],sc['hot_R_multiplier'],sc['copper_C'])
    heat=point['heat_breakdown_W'];q=heat['CHB']
    board=sum(heat[k] for k in ['Q201','shunts','fuse','copper','input_controller','input_startup'])
    extra_cases={'CHB_ONLY_REPLAY':0.,'CHB_PLUS_NEW_BOARD_PROPOSED_PATH':board,
                 'ALL_KNOWN_NONARM_HEAT_HYPOTHETICAL_ROUTE':sum(heat.values())-q}
    rows=[];matrix_checks=[];area_checks=[]
    for pitch in [10.,5.]:
        sheets=[model.Sheet(faces[k],cfg if i==0 else None,pitch=pitch) for i,k in enumerate(keys)]
        before=sheets[0].L.copy();zero_vol=augment_sheet(sheets[0],cfg,p['region_xy_mm'],0.)
        zero=sheets[0].L-before;zero_error=0. if zero.nnz==0 else float(abs(zero.data).max())
        baseline_area=float(sum(s.area.sum() for s in sheets));sample_volume=0.
        for variant in ['baseline','integral_left_spreader']:
            if variant!='baseline':sample_volume=augment_sheet(sheets[0],cfg,p['region_xy_mm'],p['height_mm'],p['conductivity_W_mK'])
            L=sheets[0].L;asym=L-L.T
            matrix_checks.append(dict(pitch_mm=pitch,variant=variant,zero_height_replay_error=zero_error,
                symmetry_error=0. if asym.nnz==0 else float(abs(asym.data).max()),
                row_sum_error=float(abs(np.asarray(L.sum(axis=1))).max()),
                sampled_added_volume_mm3=sample_volume,
                CAD_added_volume_relative_error=abs(sample_volume-g['added_volume_mm3'])/g['added_volume_mm3'] if variant!='baseline' else None))
            area_checks.append(abs(float(sum(s.area.sum() for s in sheets))-baseline_area)<1e-12)
            for name,extra in extra_cases.items():
                loads=[dict(sheet=0,center=cfg['chb_path']['center_xy_mm'],size=[55.9,59],power_W=q)]
                if extra:loads.append(dict(sheet=1,center=[-40.,20.],size=[100.,80.],power_W=extra))
                r=model.solve(sheets,loads,links,env);temp=r['source_peak_C'][0]+q*pr['case_interface_R_K_W']
                rows.append(dict(case=name,pitch_mm=pitch,variant=variant,CHB_case_C=temp,
                    CHB_margin_C=tc['CHB_case_limit_C']-temp,added_heat_W=extra,**r))
    prior=read(HERE/'THERMAL_RESULTS.json');replays=[]
    for r in rows:
        if r['variant']=='baseline':
            o=next(o for o in prior['spatial_cases'] if o['pitch_mm']==r['pitch_mm'] and o['case']==r['case'])
            replays.append(abs(o['CHB_case_C']-r['CHB_case_C']))
    refined=[r for r in rows if r['pitch_mm']==5 and r['variant']=='integral_left_spreader']
    mesh={r['case']:abs(r['CHB_case_C']-next(o['CHB_case_C'] for o in rows if o['case']==r['case'] and o['pitch_mm']==10 and o['variant']==r['variant'])) for r in refined}
    checks=dict(baseline_replay=max(replays)<1e-7,zero_height_exact=all(r['zero_height_replay_error']==0 for r in matrix_checks),
        symmetric_conservative_matrix=all(r['symmetry_error']<1e-10 and r['row_sum_error']<1e-10 for r in matrix_checks),
        external_radiating_area_unchanged=all(area_checks),
        CAD_to_thermal_added_volume_within_1_percent=all(r['CAD_added_volume_relative_error'] is None or r['CAD_added_volume_relative_error']<.01 for r in matrix_checks),
        energy_balances=all(abs(r['balance_error_W'])<1e-6 for r in rows),mesh_difference_within_1C=max(mesh.values())<1.)
    out=dict(schema='WP10_V28_GEOMETRY_BOUND_LOCAL_SPREADER_SENSITIVITY',script_sha256=sha(__file__),
        thickness_source_sha256=sha(HERE/'spreader_design_v28.py'),candidate_sha256=sha(HERE/'CANDIDATE.json'),
        parameter_sha256=sha(HERE/'SPREADER_PARAMETERS_V28.json'),geometry_sha256=sha(HERE/'SPREADER_GEOMETRY_V28.json'),
        cases=rows,matrix_checks=matrix_checks,checks=checks,mesh_delta_C=mesh,
        frozen_case_interface_R_K_W=pr['case_interface_R_K_W'],frozen_per_link_R_K_W=pr['per_link_R_K_W'],
        added_CAD_mass_kg=g['added_mass_kg'],new_heat_paths_installed=False,
        continuous_thermal_closure=False,orbit_validated=False,
        limitations=['Inherited unbuilt +Y heat patch and illustrative released environment.',
            'Rc/Rl retained for same-port comparison, not new 3D thermal-resistance validation.',
            'No hidden extra heat credit: arm/battery/output-distribution/regen heat still incomplete.',
            'No new transient mass model; sampled added volume is checked against native CAD difference.'])
    with dest.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(dict(checks=checks,refined=[{'case':r['case'],'CHB_C':r['CHB_case_C'],'margin_C':r['CHB_margin_C']} for r in refined])))
    assert all(checks.values())

if __name__=='__main__':run()
