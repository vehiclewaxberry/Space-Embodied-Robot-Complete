"""Preserve10k-initial results and add initial-voltage envelope and reviewer falsifier."""
from pathlib import Path
import itertools,json
import numpy as np
from calculate_stop_filter_v36 import model,crossing,sha,A,P,R
def main():
    base=json.loads((R/'CALCULATIONS.json').read_text());w=base['worst_open_case'];values=w['values'];ia,ib=w['input_leak_A']
    v,ru,rs,rt,rb,ca,cb=values
    aa=.405;raw=aa+ia*rs;bb=(raw/rt-ib)/(1/rt+1/rb)
    rn=raw/((v-raw)/ru-ia-(raw-bb)/rt)
    actual=model(*values,rn,ia,ib)[2];assert np.max(abs(actual-[aa,bb]))<1e-12
    op=model(*values,float('inf'),ia,ib);counter=crossing(op,actual,1,.404,True)*1e6
    assert counter>base['max_open_crossing_us'] and abs(counter-281.629826)<1e-4
    supply=json.loads((A.parent/'electrical/STOP_SUPPLY_CALCULATIONS.json').read_text())
    precision=base['resistor_factor_bounds']['precision'];series=base['resistor_factor_bounds']['series'];cap=[.99*(1-30e-6*25),1.01*(1+30e-6*25)]
    rows=[]
    for v,fu,fs,ft,fb,fa,fc,ia,ib in itertools.product(supply['rail3V3_V'],precision,series,precision,precision,cap,cap,[-25e-9,25e-9],[-15e-9,15e-9]):
        vals=[v,8200*fu,1000*fs,649000*ft,100000*fb,1e-9*fa,1e-9*fc]
        op=model(*vals,float('inf'),ia,ib);sh=model(*vals,0,ia,ib)
        assert op[0][0,1]>=0 and op[0][1,0]>=0 # Metzler => initial state comparison order.
        ot=crossing(op,np.zeros(2),1,.404,True);st=crossing(sh,np.array([6.5,6.5]),0,.387,False)
        assert ot is not None and st is not None
        rows.append(dict(values=vals,input_leak_A=[ia,ib],open_us=ot*1e6,short_us=st*1e6))
    result=dict(schema='WP10_FILTER_INITIAL_STATE_COVERAGE_EXTENSION',previous_result_scope='CALCULATIONS.json max223.302906us assumes10kNTC fault-preceding equilibrium; it is NOT all healthy-temperature maximum.',
      reviewer_counterexample=dict(A_initial_V=aa,B_initial_V=bb,NTC_ohm=rn,open_us=counter,previous10k_max_us=base['max_open_crossing_us'],increase_percent=100*(counter/base['max_open_crossing_us']-1),universally_healthy_initial_voltage=True),
      conditional_initial_voltage_envelope_V=[0,6.5],corner_count=len(rows),
      open_zero_initial_voltage_screen_us=max(x['open_us'] for x in rows),short6V5_initial_voltage_screen_us=max(x['short_us'] for x in rows),
      worst_open_case=max(rows,key=lambda x:x['open_us']),worst_short_case=max(rows,key=lambda x:x['short_us']),
      comparison_basis='For each fixed post-fault R/C/leakage scenario M has nonnegative off-diagonals. exp(Mt) preserves initial-state order. [0,0] gives a lower voltage trajectory for open detection; initialA6.5V bounds short-detection trajectory within declared0..6.5V input envelope. These extremes need not be healthy equilibria.',
      limit='Corner set sensitivity with transferred leakage, ideal opens/shorts, zero harness capacitance, fixed supply. Not a global parameter maximum or guaranteed hardware/STOP latency. Negative or over6.5V initial inputs excluded.',
      comparator_timing_added=False,RAW_or_contactor_timing_added=False,whole_STOP_time_bound=False,whole_design_complete=False,
      source_bindings={str(p):sha(p) for p in [R/'CALCULATIONS.json',A/'tools/calculate_stop_filter_v36.py',P/'sources/tlv6700.pdf',Path(__file__)]})
    (R/'INITIAL_STATE_EXTENSION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['reviewer_counterexample','open_zero_initial_voltage_screen_us','short6V5_initial_voltage_screen_us']}))
if __name__=='__main__':main()
