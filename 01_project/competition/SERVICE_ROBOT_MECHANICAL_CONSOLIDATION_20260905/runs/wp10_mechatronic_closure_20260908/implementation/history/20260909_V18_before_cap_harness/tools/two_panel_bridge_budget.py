"""Passive bridge sizing: preserve heat-flow direction and correlated faces."""
from pathlib import Path
import hashlib,json,math
from scipy.optimize import brentq
from fixed_radiator_budget import solve_sheet,SIGMA
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()

def main():
    p=read('thermal/TWO_PANEL_BRIDGE_SCENARIO.json');c=read('thermal/FIXED_HEAT_PATH.json');g=read('results/FIXED_HEAT_GEOMETRY.json')
    area=[g['outward_radiating_face_area_mm2_by_side'][s]*1e-6 for s in ['1','-1']]
    Q=p['converter_total_output_W']*(1/p['converter_efficiency_sensitivity']-1)
    Rc=.01665/(130*g['CHB_TIM_contact_area_mm2']*1e-6)+.75*25.4**2/g['CHB_TIM_contact_area_mm2']
    eps=.89;alpha=.17;lim=p['case_limit_C']+273.15-Q*Rc
    deep=dict(view=[(1.,3.)],shortwave_W_m2=0)
    sun=dict(view=[(1.,3.)],shortwave_W_m2=1361.)
    wing_dark=dict(view=[(.5,3.),(.5,330.)],shortwave_W_m2=0.)
    wing_sun=dict(view=[(.5,3.),(.5,330.)],shortwave_W_m2=1361.)
    cases=[('DARK_DEEP_SPACE_BOTH',deep,deep),('SUN_ONLY_PLUS_Y',sun,deep),
      ('HOT_WING_PLUS_Y_WITH_SUN',wing_sun,deep),('HOT_WINGS_BOTH_SUN_ONLY_PLUS_Y',wing_sun,wing_dark)]
    def base(e):return sum(f*t**4 for f,t in e['view'])+alpha*e['shortwave_W_m2']/(eps*SIGMA)
    def emission(T,a,e):return a*eps*SIGMA*(T**4-base(e))
    rows=[];sheet_rows=[]
    panels=[next(x for x in c['panels'] if x['side']==s) for s in [1,-1]]
    for cid,eh,ec in cases:
        bh,bc=base(eh),base(ec)
        Tiso=(Q/(sum(area)*eps*SIGMA)+(area[0]*bh+area[1]*bc)/sum(area))**.25
        per_area=eps*SIGMA*(lim**4-(area[0]*bh+area[1]*bc)/sum(area))
        ideal_area=Q/per_area if per_area>0 else None
        q_required=Q-emission(lim,area[0],eh)
        for R in p['bridge_resistance_scenarios_K_W']:
            if R==0:
                Th=Tc=Tiso;q=emission(Tc,area[1],ec)
            else:
                lo=-area[1]*eps*SIGMA*bc+1e-8;hi=Q+area[0]*eps*SIGMA*bh-1e-8
                def temps(q):return ((Q-q)/(area[0]*eps*SIGMA)+bh)**.25,(q/(area[1]*eps*SIGMA)+bc)**.25
                q=brentq(lambda q:temps(q)[0]-temps(q)[1]-R*q,lo,hi,xtol=1e-10)
                Th,Tc=temps(q)
            rows.append(dict(id=cid,plus_y_environment=eh,minus_y_environment=ec,mission_bound=False,
                direct_sun_plus_y_only=True,wing_view_factor_bound_to_actual_CAD=False,bridge_R_K_W=R,
                passive_transfer_W=q,hot_sheet_C=Th-273.15,cold_sheet_C=Tc-273.15,
                optimistic_case_C=Th-273.15+Q*Rc,case_below_105C_in_this_model=Th+Q*Rc<=p['case_limit_C']+273.15,
                total_energy_residual_W=emission(Th,area[0],eh)+emission(Tc,area[1],ec)-Q,
                bridge_residual_K=Th-Tc-R*q,
                ideal_isothermal_minimum_total_area_m2=ideal_area,
                isothermal_minimum_transfer_to_keep_case105C_W=q_required))
        # Sheet-level candidate coupling at R=.25; solve heat transfer from
        # mean contact-node temperatures, use hot patch maximum for case limit.
        cache={}
        def trial(q):
            if q not in cache:
                cache[q]=[solve_sheet(panel,[dict(center_xz_mm=p['hot_and_cold_sheet_contact_centres_xz_mm'][i],
                  contact_size_mm=p['hot_and_cold_sheet_contact_size_mm'][i],power_W=(Q-q if i==0 else q))],env)
                  for i,(panel,env) in enumerate(zip(panels,[eh,ec]))]
            return cache[q]
        def error(q):
            h,k=trial(q);return h['source_sheet_C'][0]-k['source_sheet_C'][0]-.25*q
        if error(0)*error(Q)>0:
            raise ValueError('Declared sheet solver supports only0<=q<=CHB_loss; reverse/environment-fed transfer requires a signed-flow extension before evaluating this environment')
        q=brentq(error,0,Q,xtol=1e-7);h,k=trial(q)
        case=h['source_peak_sheet_C'][0]+Q*Rc
        sheet_rows.append(dict(id=cid,bridge_R_K_W=.25,passive_transfer_W=q,
          bridge_node_temperature_residual_K=error(q),case_peak_C_with_zero_coating_R=case,
          below105C_in_this_unqualified_model=case<=105,
          source_case_margin_to105C_K=105-case,hot_sheet=h,cold_sheet=k,
          total_energy_residual_W=h['net_outward_W']+k['net_outward_W']-Q,
          numerical_contact_allocation_not_installed=True))
    m=p['mechanical_route_screen'];r=m['inside_bend_radius_mm']+m['pipe_outer_diameter_mm']/2
    minimum_length=m['opposing_parallel_contact_leg_separation_mm']-2*r+math.pi*r+2*m['straight_contact_length_each_mm']
    max_length=m['nominal_pipe_length_mm']*(1+m['pipe_length_tolerance_percent']/100)
    # Isothermal low-load diagnostic: contact-node temperatures are not pipe
    # fluid temperatures; temperatures below OEM range remove qualification
    # credit, rather than proving freeze-up or inventing low-T capacity.
    lowload=[]
    for eta in [.85,.90,.91]:
        qloss=361*(1/eta-1)
        def temp_split(q):return ((qloss-q)/(area[0]*eps*SIGMA)+3**4)**.25,(q/(area[1]*eps*SIGMA)+3**4)**.25
        transfer=brentq(lambda q:temp_split(q)[0]-temp_split(q)[1]-.25*q,0,qloss)
        hot,cold=temp_split(transfer)
        lowload.append(dict(efficiency=eta,loss_W=qloss,passive_transfer_W=transfer,
          ideal_hot_node_C=hot-273.15,ideal_cold_node_C=cold-273.15,
          both_ideal_contact_nodes_within_public30_120C_range=30<=cold-273.15<=hot-273.15<=120,
          actual_pipe_temperature_C=None,guaranteed_transport_W=None))
    by={(r['id'],r['bridge_R_K_W']):r for r in rows}
    checks=[dict(name='energy_balance_both_levels',passed=max(abs(r['total_energy_residual_W']) for r in rows+sheet_rows)<1e-6),
      dict(name='passive_bridge_temperature_balance',passed=max(abs(r['bridge_residual_K']) for r in rows)<1e-6 and max(abs(r['bridge_node_temperature_residual_K']) for r in sheet_rows)<1e-6),
      dict(name='40W_not_forced_in_dark_symmetric_case',passed=by[('DARK_DEEP_SPACE_BOTH',.25)]['passive_transfer_W']<40),
      dict(name='physical_paired_hot_wings_reject_even_zero_bridge_R',passed=by[('HOT_WINGS_BOTH_SUN_ONLY_PLUS_Y',0)]['optimistic_case_C']>105),
      dict(name='declared300mm_U_route_with50mm_contacts_rejected_even_longest_tolerance',passed=minimum_length>max_length),
      dict(name='only_plus_Y_receives_direct_sun',passed=all(r['minus_y_environment']['shortwave_W_m2']==0 for r in rows)),
      dict(name='low_load_90_91pct_temperature_credit_withheld',passed=all(not r['both_ideal_contact_nodes_within_public30_120C_range'] for r in lowload[1:]))]
    out=dict(schema='WP10_TWO_PANEL_PASSIVE_BRIDGE_BUDGET_V1',check_count=len(checks),checks=checks,checks_passed=all(x['passed'] for x in checks),
      input_sha256={k:sha(k) for k in ['thermal/TWO_PANEL_BRIDGE_SCENARIO.json','thermal/FIXED_HEAT_PATH.json','results/FIXED_HEAT_GEOMETRY.json']},
      solver_source_sha256=sha('tools/two_panel_bridge_budget.py'),sheet_solver_source_sha256=sha('tools/fixed_radiator_budget.py'),
      sheet_supported_transfer_range_W=[0,Q],reverse_or_environment_fed_flow_evaluated=False,
      converter_loss_W=Q,shared_TIM_metal_R_K_W=Rc,total_area_m2=sum(area),isothermal_scenarios=rows,sheet_coupled_scenarios=sheet_rows,
      low_load_dark_isothermal_diagnostic=lowload,
      pipe_U_route_screen=dict(centerline_bend_radius_mm=r,minimum_undeformed_centreline_length_mm=minimum_length,
          maximum300mm_pipe_with_length_tolerance_mm=max_length,shortfall_even_longest_tolerance_mm=minimum_length-max_length,
          applicable_to_declared_U_geometry_only=True,all_possible_routes_rejected=False),
      design_decision='Do not freeze 300mm pipe/50mm contacts or a forced40W split. First bind actual panel views and extra thermal area, then choose route length/collectors and solve the coupled network.',
      installed_bridge_R_K_W=None,bridge_geometry_built=False,flight_release=False,whole_thermal_design_complete=False,
      limitations=['Only CHB loss included','Sheet-node bridge locations and equal contact patches are numerical allocations, not built or measured interfaces','Bridge .25K/W is a design scenario, not OEM Rth','Both hot-wing views are a possible stress geometry, not actual spacecraft view factors','Optical inputs BOL; coating R zero; TIM typical pressure unmeasured','If branch leaves inner carrier before outer wall, replace shared metal topology instead of reusing Rc','Pipe formula and operational range do not qualify space/freeze-start use'])
    assert out['checks_passed']
    (A/'thermal/TWO_PANEL_BRIDGE_BUDGET.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(dict(checks=checks,sheet_results=[{k:r[k] for k in ['id','passive_transfer_W','case_peak_C_with_zero_coating_R']} for r in sheet_rows],route=out['pipe_U_route_screen'])))
if __name__=='__main__':main()
