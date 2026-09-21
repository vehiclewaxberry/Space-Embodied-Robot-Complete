"""Vacuum thermal sizing of the current fixed-panel candidate.

This is a design calculation, not an orbital or flight thermal qualification.
Finite-volume sheet spreading uses constant k and an adiabatic perimeter.
The perforated face is represented by subcell area integration; no chassis,
battery, second panel, convection or stored energy is credited as a heat sink.
"""
from pathlib import Path
import hashlib,json,math
import numpy as np
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import spsolve

A=Path(__file__).resolve().parents[1]
SIGMA=5.670374419e-8

def radiation_density(T,env,eps=.89,alpha=.17):
    """W/m2 leaving one face. Fractions form the complete outward hemisphere."""
    assert abs(sum(v[0] for v in env['view'])-1)<1e-10
    return eps*SIGMA*sum(f*(T**4-t**4) for f,t in env['view'])-alpha*env['shortwave_W_m2']

def solve_sheet(panel,loads,env,k=130.,thickness_mm=8.,pitch_mm=5.):
    w,h=panel['face_size_mm'];nx=math.ceil(w/pitch_mm);ny=math.ceil(h/pitch_mm)
    dx=w/nx;dy=h/ny;xc=(np.arange(nx)+.5)*dx-w/2;yc=(np.arange(ny)+.5)*dy-h/2
    X,Y=np.meshgrid(xc,yc);fraction=np.ones((ny,nx))
    # Integrate face holes by deterministic 16x16 subcell quadrature.
    if panel.get('holes_xz_d_mm'):
        fraction[:]=0
        for ox in (np.arange(16)+.5)/16-.5:
            for oy in (np.arange(16)+.5)/16-.5:
                keep=np.ones_like(X,dtype=bool)
                for x,y,d in panel['holes_xz_d_mm']:
                    keep&=(X+ox*dx-x)**2+(Y+oy*dy-y)**2>=(d/2)**2
                fraction+=keep/256
    # Fraction of each cell in the 18mm-wide back pockets. Their external
    # radiating skin is continuous but only 3.5mm thick, not the nominal 8mm.
    pocket=np.zeros_like(X)
    for px in [-150,-90,-30,30,90,150]:
        wx=np.maximum(0,np.minimum(X+dx/2,px+9)-np.maximum(X-dx/2,px-9))
        for lo,hi in [(-90.,-86.35),(86.35,90.)]:
            wy=np.maximum(0,np.minimum(Y+dy/2,hi)-np.maximum(Y-dy/2,lo))
            pocket+=wx*wy/(dx*dy)
    thickness=(thickness_mm-(thickness_mm-3.5)*pocket)/1000
    ids=-np.ones_like(X,dtype=int);active=fraction>0;ids[active]=np.arange(active.sum())
    area=(dx*dy*1e-6*fraction)[active];n=len(area);rr=[];cc=[];vv=[]
    # Subcell area/harmonic face occupancy is a sheet approximation near holes.
    for j,i in zip(*np.where(active)):
        for jj,ii in [(j,i+1),(j+1,i)]:
            if jj>=ny or ii>=nx or not active[jj,ii]:continue
            f1,f2=fraction[j,i],fraction[jj,ii];f=2*f1*f2/(f1+f2)
            t1,t2=thickness[j,i],thickness[jj,ii];t=2*t1*t2/(t1+t2)
            g=k*t*(dy/dx if ii!=i else dx/dy)*f
            p,q=ids[j,i],ids[jj,ii]
            rr.extend([p,q,p,q]);cc.extend([p,q,q,p]);vv.extend([g,g,-g,-g])
    L=coo_matrix((vv,(rr,cc)),shape=(n,n)).tocsr();heat=np.zeros(n);weights=[]
    for load in loads:
        x,y=load['center_xz_mm'];lw,lh=load['contact_size_mm']
        # Exact overlap of the rectangular source with each mesh cell.
        wx=np.maximum(0,np.minimum(X+dx/2,x+lw/2)-np.maximum(X-dx/2,x-lw/2))
        wy=np.maximum(0,np.minimum(Y+dy/2,y+lh/2)-np.maximum(Y-dy/2,y-lh/2))
        wt=(wx*wy*fraction)[active];assert wt.sum()>0;wt/=wt.sum()
        weights.append(wt);heat+=load['power_W']*wt
    T=np.full(n,350.)
    for iteration in range(40):
        residual=L@T+area*radiation_density(T,env)-heat
        if np.max(abs(residual))<1e-10:break
        J=L+diags(area*4*.89*SIGMA*T**3)
        step=spsolve(J,-residual);scale=min(1,30/max(np.max(abs(step)),1e-30));T+=scale*step
    assert np.max(abs(residual))<1e-8,'Nonlinear balance not converged'
    emitted=float(np.sum(area*radiation_density(T,env)));input_W=sum(l['power_W'] for l in loads)
    return dict(mesh=[nx,ny],pitch_mm=[dx,dy],effective_area_m2=float(area.sum()),
      peak_sheet_C=float(T.max()-273.15),mean_sheet_C=float(np.dot(T,area)/area.sum()-273.15),
      source_sheet_C=[float(np.dot(T,wt)-273.15) for wt in weights],
      source_peak_sheet_C=[float(T[wt>1e-12].max()-273.15) for wt in weights],
      input_W=input_W,net_outward_W=emitted,balance_error_W=emitted-input_W,
      residual_max_W=float(np.max(abs(residual))),iterations=iteration+1)

def main():
    config_path=A/'thermal/FIXED_HEAT_PATH.json';p=json.loads(config_path.read_text())
    geo=json.loads((A/'results/FIXED_HEAT_GEOMETRY.json').read_text())
    assert geo['checks_passed']
    panels=p['panels'];envs=[
      dict(id='IDEAL_DARK_DEEP_SPACE_BOUND',view=[(1.,3.)],shortwave_W_m2=0.,mission_bound=False),
      dict(id='ILLUSTRATIVE_NORMAL_SUN',view=[(1.,3.)],shortwave_W_m2=1361.,mission_bound=False),
      dict(id='ILLUSTRATIVE_EARTH_AND_SUN',view=[(.5,3.),(.5,255.)],shortwave_W_m2=1361.+400.,mission_bound=False),
      dict(id='ILLUSTRATIVE_HALF_WING_BLOCKED',view=[(.5,3.),(.5,330.)],shortwave_W_m2=1361.,mission_bound=False)]
    rows=[]
    chb=next(x for x in p['devices'] if x['id']=='U202_CHB')
    panel=next(x for x in panels if x['side']==chb['side'])
    for efficiency in [.85,.90,.91]:
        loss=361.*(1/efficiency-1)
        load=dict(center_xz_mm=chb['center_xz_mm'],contact_size_mm=[55.9,59.],power_W=loss)
        for env in envs:
            r=solve_sheet(panel,[load],env)
            # The carrier is monolithic with the web/boss/outer radiator. Its
            # through-thickness R is separate from in-plane sheet spreading.
            through=chb['metal_path_mm']/1000/(130.*geo['CHB_TIM_contact_area_mm2']*1e-6)
            tim=.75*25.4**2/geo['CHB_TIM_contact_area_mm2']
            # Coating resistance is unknown; zero is an optimistic lower bound.
            case=r['source_peak_sheet_C'][0]+loss*(through+tim)
            rows.append(dict(efficiency_scenario=efficiency,environment=env,converter_loss_W=loss,
              metal_path_R_K_W=through,TIM_typical_25psi_R_K_W=tim,
              case_C_with_zero_coating_R=case,below_105C_in_this_unqualified_model=case<=105,
              guaranteed_operating_case=False,coating_R_K_W=None,**r))
    conv=[]
    load=dict(center_xz_mm=chb['center_xz_mm'],contact_size_mm=[55.9,59.],power_W=361*(1/.85-1))
    for pitch in [10.,5.,2.5]:conv.append(solve_sheet(panel,[load],envs[0],pitch_mm=pitch))
    mesh_delta=abs(conv[-1]['source_peak_sheet_C'][0]-conv[-2]['source_peak_sheet_C'][0])
    checks=[dict(name='360W_arm_not_reduced_aux_not_duplicated',passed=abs(load['power_W']-63.7058823529412)<1e-10),
      dict(name='all_energy_balances',passed=all(abs(r['balance_error_W'])<1e-7 for r in rows+conv)),
      dict(name='refinement_source_temperature_delta_below_1C',passed=mesh_delta<1),
      dict(name='external_heat_and_view_counterexamples_retained',passed=len(envs)==4),
      dict(name='no_mission_environment_claim',passed=all(not r['environment']['mission_bound'] for r in rows))]
    area=geo['outward_radiating_face_area_mm2_by_side'][str(chb['side'])]*1e-6
    q85=361*(1/.85-1)
    Rmetal=.01665/(130*geo['CHB_TIM_contact_area_mm2']*1e-6)
    Rtim=.75*25.4**2/geo['CHB_TIM_contact_area_mm2']
    ideal_face_K=(q85/(area*.89*SIGMA)+3**4)**.25
    ideal_case_C=ideal_face_K-273.15+q85*(Rmetal+Rtim)
    checks.append(dict(name='single_side_85pct_rejected_even_isothermal_deep_space',passed=ideal_case_C>105))
    out=dict(schema='WP10_FIXED_RADIATOR_THERMAL_SIZING_V1',checks=checks,check_count=len(checks),
      checks_passed=all(x['passed'] for x in checks),config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
      actual_outward_face_area_m2=area,scenarios=rows,mesh_refinement=conv,mesh_delta_C=mesh_delta,
      k_W_mK=130,k_role='ENGINEERING_SENSITIVITY_BELOW_167_TYPICAL_25C_NOT_CERTIFIED_MINIMUM',
      material_typical_source='sources/hydro_6061_2019.pdf',coating_source='sources/az93_oem.html',
      single_side_85pct_full_power_thermal_design_rejected=ideal_case_C>105,
      isothermal_deep_space_counterexample=dict(loss_W=q85,ideal_face_C=ideal_face_K-273.15,
        optimistic_case_lower_bound_C=ideal_case_C,case_limit_C=105.,not_measured=True),
      other_heat_not_in_this_CHB_only_solve=['THN loss','primary MOSFET/shunt/fuse','battery and PMM','brake task average and transient'],
      brake_task_energy_J=None,continuous_full_vehicle_thermal_verified=False,
      omitted_physics=['through-thickness gradients at source','detailed 3D hole conduction','coating contact/through-thickness R','end-of-life optics','as-built TIM pressure','orbital attitude/view factors','transient storage and duty','GSE convection'],
      model_is_optimistic_for_unmodelled_heat_inputs=True,flight_thermal_release=False)
    (A/'thermal/FIXED_RADIATOR_BUDGET.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(dict(checks=checks,mesh_delta_C=mesh_delta,case_C=[r['case_C_with_zero_coating_R'] for r in rows])))
    assert out['checks_passed']
if __name__=='__main__':main()
