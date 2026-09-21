"""Two-state RC response and tolerance sensitivity; no comparator/STOP time credit."""
from pathlib import Path
import itertools,json,hashlib
import numpy as np
A=Path(__file__).resolve().parents[1];P=A/'results/stop_v36/pcb';R=P/'thermal_filter_20260916'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def model(v,ru,rs,rt,rb,ca,cb,rn,ia=0.,ib=0.):
    if rn==0:
        M=np.diag([-1/(rs*ca),-(1/rt+1/rb)/cb]);b=np.array([-ia/ca,-ib/cb])
    else:
        g=1/ru+1/rs+1/rt+(0 if np.isinf(rn) else 1/rn)
        M=np.array([[(1/(rs*g)-1)/(rs*ca),1/(rt*g*rs*ca)],
                    [1/(rs*g*rt*cb),(1/(rt*g)-1)/(rt*cb)-1/(rb*cb)]])
        b=np.array([(v/(ru*g)/rs-ia)/ca,(v/(ru*g)/rt-ib)/cb])
    end=np.linalg.solve(M,-b)
    ev,vec=np.linalg.eig(M)
    assert all(np.real(ev)<0) and np.max(abs(np.imag(ev)))<1e-6
    return M,b,end,ev,vec
def response(m,x0,t):
    _,_,end,ev,vec=m
    return np.real(end+vec@(np.exp(ev*t)*np.linalg.solve(vec,x0-end)))
def crossing(m,x0,index,threshold,rising):
    end=m[2][index]
    if (end<=threshold if rising else end>=threshold):return None
    low=0.;high=1e-6
    hit=lambda t:response(m,x0,t)[index]>=threshold if rising else response(m,x0,t)[index]<=threshold
    if hit(0):return 0.
    while not hit(high):
        high*=2
        if high>1:raise RuntimeError('Crossing not bounded within1s')
    for _ in range(60):
        mid=(low+high)/2
        if hit(mid):high=mid
        else:low=mid
    return high
def case(values,ia=0.,ib=0.):
    v,ru,rs,rt,rb,ca,cb=values
    x0=model(*values,10000,ia,ib)[2]
    op=model(*values,float('inf'),ia,ib);sh=model(*values,0,ia,ib)
    ot=crossing(op,x0,1,.404,True);st=crossing(sh,x0,0,.387,False)
    return dict(initial_V=x0.tolist(),open_end_V=op[2].tolist(),short_end_V=sh[2].tolist(),open_crossing_us=None if ot is None else ot*1e6,short_crossing_us=None if st is None else st*1e6,open_poles_us=sorted((-1/op[3]*1e6).tolist()),input_leak_A=[ia,ib])
def main():
    nominal=case([3.3,8200,1000,649000,100000,1e-9,1e-9])
    assert abs(nominal['open_crossing_us']-166.070343)<1e-4
    assert abs(nominal['short_crossing_us']-1.538419)<1e-5
    supply=json.loads((A.parent/'electrical/STOP_SUPPLY_CALCULATIONS.json').read_text())
    precision=[.999*(1-25e-6*25),1.001*(1+25e-6*25)]
    series=[.99*(1-100e-6*25),1.01*(1+100e-6*25)]
    cap=[.99*(1-30e-6*25),1.01*(1+30e-6*25)]
    rows=[]
    for v,fu,fs,ft,fb,fa,fc,ia,ib in itertools.product(supply['rail3V3_V'],precision,series,precision,precision,cap,cap,[-25e-9,25e-9],[-15e-9,15e-9]):
        vals=[v,8200*fu,1000*fs,649000*ft,100000*fb,1e-9*fa,1e-9*fc]
        row=case(vals,ia,ib);row['values']=vals;rows.append(row)
    assert all(x['open_crossing_us'] is not None and x['short_crossing_us'] is not None for x in rows)
    # Algebraic DC cross-check for nominal branch loading, independent of dynamic matrix.
    raw=3.3/(1+8200*(1/10000+1/749000));bp=raw*100000/749000
    assert np.max(abs(np.array(nominal['initial_V'])-[raw,bp]))<1e-12
    # A mismatched100k->82k open-divider choice must fail the hardest upper threshold.
    rejected=case([min(supply['rail3V3_V']),8200,1000,649000,82000,1e-9,1e-9],25e-9,15e-9)
    assert rejected['open_crossing_us'] is None
    result=dict(schema='WP10_STOP_FILTER_TWO_STATE_CONDITIONAL_RC',scope='0..50C component tolerance/temperature and transferred input-leakage sensitivity; NOT guaranteed STOP timing',
      model='Eliminate algebraic raw node; state=[INA+,INB-]. dA=(raw-A)/(RsCa)-Ia/Ca; dB=(raw-B)/(RtCb)-B/(RbCb)-Ib/Cb.',
      nominal=nominal,screened_corner_count=len(rows),
      max_open_crossing_us=max(x['open_crossing_us'] for x in rows),max_short_crossing_us=max(x['short_crossing_us'] for x in rows),
      minimum_open_end_B_V=min(x['open_end_V'][1] for x in rows),maximum_short_end_A_V=max(x['short_end_V'][0] for x in rows),
      worst_open_case=max(rows,key=lambda x:x['open_crossing_us']),worst_short_case=max(rows,key=lambda x:x['short_crossing_us']),
      negative_control=dict(name='100k_open_divider_misloaded_as82k',result=rejected,detected=True),
      C_initial_tolerance=.01,C_TCR_per_K=30e-6,temperature_C=[0,50],resistor_factor_bounds=dict(precision=precision,series=series),
      timing_credit=dict(input_RC_threshold_crossing_only=True,comparator_propagation_max_known=False,RAW_delay_bound=False,contactor_release_bound=False,whole_STOP_time_bound=False),
      limitations=['Input leakage +/-25nA and+/-15nA transferred from manufacturer test points, not proven bounds at all actual input voltages.',
       '18us/29us propagation delays are NOM atVDD5V and10mV overdrive; not added as a guaranteed upper time.',
       'Harness capacitance/ESD/cross-short/24V miswire, temperature-to-NTC thermal lag and arbitrary supply ramps not included.',
       'Corner enumeration is a stated sensitivity set, not proof of a global mathematical maximum or hardware qualification.'],
      source_bindings={str(p):sha(p) for p in [P/'sources/tlv6700.pdf',P/'sources/C0603C102F5GACTU.pdf',P/'sources/kem_c1003_c0g_smd.pdf',P/'sources/dcrcwe3.pdf',P/'sources/tnpw_e3.pdf',A.parent/'electrical/STOP_SUPPLY_CALCULATIONS.json',R/'FILTER_INTENT.json',Path(__file__)]},
      calculation_passed=True,whole_design_complete=False)
    (R/'CALCULATIONS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['screened_corner_count','max_open_crossing_us','max_short_crossing_us','minimum_open_end_B_V','calculation_passed']}))
if __name__=='__main__':main()
