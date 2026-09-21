"""Same electrical points -> existing spatial radiation model + transient screen."""
import math
import numpy as np
from coupled_adapter import A,HERE,read,dump,sha,module,load_candidate,operating_point

def run(c=None,output_name='THERMAL_RESULTS.json'):
    c=load_candidate() if c is None else c;sc=c['analysis_scenario'];tc=c['thermal'];ec=tc['environment']
    old=read(A/'thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json')
    view=read(A/'thermal/RADIATOR_MESH_VIEW_SCREEN.json')
    geometry=read(A/'thermal/BOTTOM_RADIATOR_MOUNT.json')
    model=module('wp10_spatial_sheet',A/'tools/spatial_radiator_network.py')
    keys=['FIXED_MINUS_Z_BOTTOM_PLATE',next(r['face']['id'] for r in view['results'] if r['face']['id'].endswith('PLUS_Y')),'FIXED_MINUS_Y']
    faces={r['face']['id']:r['face'] for r in view['results']}
    pressure=next(x for x in old['pressure_sensitivity'] if x['psi']==25)
    Rc=pressure['case_interface_R_K_W'];Rl=pressure['per_link_R_K_W']
    links=[dict(**ep,R_K_W=Rl) for ep in old['links_endpoints']]
    env=[]
    for i,k in enumerate(keys):
        r=next(r for r in view['results'] if r['state']==ec['state'] and r['face']['id']==k)
        env.append(dict(grid=r['model_surface_refinement'][-1]['spatial_grid'],occluder_K=ec['occluder_K'],space_K=ec['space_K'],solar_W_m2=ec['solar_W_m2'] if i==1 else 0.))
    on=operating_point(c,sc['pack_V'],sc['shared_R_ohm'],sc['eta_main'],sc['hot_R_multiplier'],sc['copper_C']);stress=operating_point(c,sc['pack_V'],.1,sc['eta_main'],sc['hot_R_multiplier'],sc['copper_C'])
    base=dict(sheet=0,center=geometry['chb_path']['center_xy_mm'],size=[55.9,59],power_W=on['heat_breakdown_W']['CHB'])
    results=[];last_sheets=None
    for pitch in [10.,5.]:
        sheets=[model.Sheet(faces[k],geometry if i==0 else None,pitch=pitch) for i,k in enumerate(keys)]
        cases=[('CHB_ONLY_REPLAY',on,[])]
        for name,point,all_known in [('CHB_PLUS_NEW_BOARD_PROPOSED_PATH',on,False),
                                     ('ALL_KNOWN_NONARM_HEAT_HYPOTHETICAL_ROUTE',on,True),
                                     ('HIGH_CONTACT_R_ALL_KNOWN_HEAT_HYPOTHETICAL_ROUTE',stress,True)]:
            heat=point['heat_breakdown_W']
            extra=sum(heat.values())-heat['CHB'] if all_known else sum(heat[k] for k in ['Q201','shunts','fuse','copper','input_controller','input_startup'])
            # Prospective +Y attachment patch; this is a boundary requirement,
            # not a claim that existing uninstalled hardware has this path.
            cases.append((name,point,[dict(sheet=1,center=[-40.,20.],size=[100.,80.],power_W=extra)]))
        for name,point,extra in cases:
            r=model.solve(sheets,[base]+extra,links,env)
            r.update(case=name,pitch_mm=pitch,CHB_case_C=r['source_peak_C'][0]+base['power_W']*Rc,
              CHB_margin_C=tc['CHB_case_limit_C']-(r['source_peak_C'][0]+base['power_W']*Rc),
              added_power_W=sum(x['power_W'] for x in extra),
              new_paths_installed=False,unknown_arm_battery_distribution_heat_included=False,
              phase_duration_s=None,analysis_scope='STEADY_SENSITIVITY_WITH_EXPLICIT_UNBUILT_HEAT_ROUTES')
            if extra:
                h=point['heat_breakdown_W'];r['Q201_required_total_case_to_radiator_R_K_W']=(tc['Q201_junction_limit_C']-r['source_peak_C'][1])/h['Q201']-tc['Q201_Rjc_K_W']
            results.append(r)
        last_sheets=sheets
    refinement={name:abs(next(r['CHB_case_C'] for r in results if r['case']==name and r['pitch_mm']==5)-
                        next(r['CHB_case_C'] for r in results if r['case']==name and r['pitch_mm']==10)) for name in {r['case'] for r in results}}
    # Optimistic isothermal transient: no fictional convection or fixed infinite
    # sink. External heating, radiation, storage and heater are integrated once.
    area=sum(s.area.sum() for s in last_sheets)
    C=sum(float(np.sum(s.area*s.thickness[s.active]))*tc['aluminum_density_kg_m3']*tc['aluminum_cp_J_kgK'] for s in last_sheets)
    incoming_hot=sum(float(np.sum(s.area*(.89*model.SIGMA*((1-s.view(e['grid']))*ec['space_K']**4+s.view(e['grid'])*ec['occluder_K']**4)+.17*e['solar_W_m2']))) for s,e in zip(last_sheets,env))
    off=operating_point(c,sc['pack_V'],sc['shared_R_ohm'],active=False)
    def transient(step,cold=False):
        T=273.15+(sc['cold_initial_C'] if cold else sc['hot_initial_C']);E=c['electrical']['nominal_energy_Wh']*sc['initial_energy_fraction'];heater_Wh=0.;residual=0.;times=[]
        phases=[(p['mode'],p['duration_s'],on if p['mode']=='RUN' else off) for p in sc['phases']] if not cold else [('SAFE_COOLDOWN',sc['cold_duration_s'],off)]
        elapsed=0.;initial=T;sum_in=0.;sum_out=0.
        incoming=area*.89*model.SIGMA*sc['cold_environment_K']**4 if cold else incoming_hot
        for mode,duration,p in phases:
            n=math.ceil(duration/step);dt=duration/n
            for j in range(n):
                heater=min(tc['cold_safe_heater_limit_W'],max(0.,(273.15+tc['heater_setpoint_C']-T)*tc['heater_gain_W_K'])) if cold else 0.
                q=p['accounted_non_arm_heat_W']+heater/tc['heater_efficiency']
                def rate(temp):return (q+incoming-area*.89*model.SIGMA*temp**4)/C
                k1=rate(T);k2=rate(T+.5*dt*k1);k3=rate(T+.5*dt*k2);k4=rate(T+dt*k3)
                Tnext=T+dt*(k1+2*k2+2*k3+k4)/6
                # Same RK quadrature for radiative energy gives an audit of
                # the discretized balance, independent of state differences.
                out=area*.89*model.SIGMA*(T**4+2*(T+.5*dt*k1)**4+2*(T+.5*dt*k2)**4+(T+dt*k3)**4)/6
                sum_in+=(q+incoming)*dt;sum_out+=out*dt;T=Tnext
                E-=(p['input_power_W']+heater/tc['heater_efficiency'])*dt/3600;heater_Wh+=heater*dt/3600;elapsed+=dt
            times.append(dict(mode=mode,time_s=elapsed,radiator_bulk_C=T-273.15,energy_Wh=E))
        residual=C*(T-initial)-(sum_in-sum_out)
        return dict(step_s=step,cold=cold,trace=times,heater_output_Wh=heater_Wh,heater_conversion_loss_Wh=heater_Wh*(1/tc['heater_efficiency']-1),
                    heat_balance_residual_J=residual,heat_capacity_J_K=C,
                    assumption='PERFECT_SURFACE_MIXING_WITH_ALUMINUM_CP900; OPTIMISTIC SCREEN',
                    battery_and_semiconductor_temperatures=None,actual_heater_installed=False)
    trans=[transient(dt,cold) for cold in [False,True] for dt in [2.,1.]]
    out=dict(candidate_sha256=sha(HERE/'CANDIDATE.json'),script_sha256=sha(__file__),
      adapter_sha256=sha(HERE/'coupled_adapter.py'),spatial_cases=results,
      mesh_delta_C=refinement,reference_replay_difference_C=next(r['CHB_case_C'] for r in results if r['case']=='CHB_ONLY_REPLAY' and r['pitch_mm']==5)-pressure['case_C'],
      energy_balance_max_W=max(abs(r['balance_error_W']) for r in results),
      radiator_area_m2=float(area),transient_screens=trans,
      continuous_thermal_closure=False,orbit_validated=False,
      conclusion='Added known heat consumes CHB-only margin. Unknown heat routes and mission environment remain blockers.')
    if output_name:
        dump(output_name,out)
        print([(r['case'],round(r['CHB_case_C'],3),round(r['added_power_W'],3)) for r in results if r['pitch_mm']==5])
    assert out['energy_balance_max_W']<1e-6
    assert abs(out['reference_replay_difference_C'])<1e-7
    return out

if __name__=='__main__':run()
