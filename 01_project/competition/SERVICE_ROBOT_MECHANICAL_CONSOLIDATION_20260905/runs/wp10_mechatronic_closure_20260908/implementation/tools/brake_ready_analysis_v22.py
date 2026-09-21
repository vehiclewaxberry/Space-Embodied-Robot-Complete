"""Source-bound READY interface budget. Test-condition transfers stay explicit."""
import itertools, math, re
def resistance(parts,ref):
 m=re.match(r'([0-9.]+)(k|ohm)',parts[ref]['mpn']);assert m,(ref,parts[ref]['mpn'])
 return float(m[1])*(1000 if m[2]=='k' else 1)
def evaluate(parts,definition,bias):
 assert parts['U303']['mpn']=='MAX5048CAUT+T' and parts['U304']['mpn']=='MAX16053AUT+T'
 top=resistance(parts,'R308');bottom=resistance(parts,'R309');pd=resistance(parts,'R310')
 assert parts['C307']['mpn']=='1nF_5pct_50V_C0G'
 cap=definition['parameters']['ready_delay_F'];assert cap==1e-9
 tol=.001+25e-6*100
 trip=[th*(1+h/l)+ib*h for th,h,l,ib in itertools.product([.491,.509],[top*(1-tol),top*(1+tol)],[bottom*(1-tol),bottom*(1+tol)],[-110e-9,110e-9])]
 vmin,vmax=bias['voltage_sensitivity_V'];load=vmax/(pd*.99)+1e-6
 high=.9*vmin;low=.4;vi_high=2.;vi_low=.8
 # C0G temperature allocation covers -40..125 C relative to25 C: |dT|<=100K.
 ct=.05+30e-6*100
 delay_min=cap*(1-ct)*.95/300e-9;delay_max=cap*(1+ct)*1.05/200e-9
 old_r=270000*(1+tol);critical=(vmin-2.4)/old_r-2.4/200000
 old_extra=25e-6;old_high=(vmin/old_r-old_extra)/(1/old_r+1/200000)
 outb_high=vmin-(.3e-6+1e-6)*(10000*1.01)
 outb_sink=vmax/(10000*.99)+1e-6
 # Topology checks are performed against native XML by the caller. These are
 # useful counterexamples, not measurements of leakage, mission or startup.
 falsifiers=[
  dict(name='legacy_270k_plus_25uA_unexcluded_sink',observed_high_V=old_high,rejected=old_high<2.4),
  dict(name='ready_pulldown_10k_exceeds_800uA_test_load',load_A=vmax/(10000*.99)+1e-6,rejected=vmax/(10000*.99)+1e-6>800e-6),
  dict(name='monitor_300k_upper_never_ready_at_low_bias',threshold_V=.491*(1+300000/bottom),rejected=.491*(1+300000/bottom)>vmin),
  dict(name='200us_cold_blanking_does_not_cover_450us',rejected=200e-6<450e-6),
  dict(name='charged_delay_cap_cannot_inherit_zero_start',initial_V=.9,time_to_095_s=cap*(1-ct)*(.95-.9)/300e-9,rejected=cap*(1-ct)*(.95-.9)/300e-9<450e-6)
 ]
 checks={
  'ready_threshold_below_declared_regulated_bias':max(trip)<vmin,
  'steady_bias_within_driver_operating_range':vmin>=4 and vmax<=14,
  'ready_load_under_800uA_characterized_output_load':load<=800e-6,
  'ready_high_static_margin':high>vi_high,
  'ready_low_static_margin':low<vi_low,
  'OV_high_static_margin':outb_high>vi_high,
  'OV_low_load_within_project_2mA_allocation':outb_sink<.002,
  'cold_monotonic_start_note3_covers_comparator_tstartup':500e-6>450e-6,
  'receiver_open_wire_pulldown_screen':1e-6*(pd*1.01)<vi_low,
  'all_controlled_counterexamples_rejected':all(x['rejected'] for x in falsifiers)
 }
 monitor_current=71e-6+vmax/(top*(1-tol)+bottom*(1-tol))+load+300e-9+110e-9
 return dict(schema='WP10_BRAKE_READY_INTERFACE_V22',status='NATIVE_INTERFACE_CHANGED__CONDITIONAL_STATIC_AND_FIRST_COLD_START_SCREEN',
  checks=checks,checks_passed=all(checks.values()),
  monitored_bias_V=[vmin,vmax],rising_threshold_nominal_V=.5*(1+top/bottom),rising_threshold_sensitivity_V=[min(trip),max(trip)],
  input_divider_scope='0.1% +25ppm/K*100K resistor allocation; MAX16053 IIN +/-110nA tested at IN=0 or28V, transferred to0.5V for sensitivity only',
  ready_input_load_max_sensitivity_A=load,ready_output_test_load_A=800e-6,ready_high_min_sensitivity_V=high,ready_low_max_V=low,
  driver_VIH_V=vi_high,driver_VIL_V=vi_low,OV_high_min_sensitivity_V=outb_high,OV_low_sink_sensitivity_A=outb_sink,
  OV_sink_scope='2mA is a project allocation, not a TLV6700 test row. RevB p5 VOL<=0.25V rows: VDD1.3V/0.4mA,1.8V/3mA,5V/5mA. Transfer from5V/5mA to approximately12V/1.259mA is conditional, not an OEM12V guarantee.',
  receiver_input_scope='MAX5048C +/-1uA at V+=14V and IN+=IN-=0 orV+; transferred to the declared approximately12V rails. No production-range I(V) guarantee inferred.',
  first_cold_start=dict(minimum_supervisor_start_s=.0005,maximum_TLV6700_start_s=.00045,margin_s=.00005,
   condition='Both devices see the same initially discharged, continuously rising bias rail; MAX16053 Rev7 p3 Note3. No arbitrary brownout/restart guarantee.'),
  delay_capacitor=dict(MPN='C0603C102J5GACTU',nominal_F=cap,tolerance_plus_temperature=ct,temperature_delta_K=100,
   zero_initial_voltage_charge_sensitivity_s=[delay_min,delay_max],typical_delay_s=4e6*cap+30e-6,
   guarantee_max_s=None,scope='ICD200..300nA specified at CDELAY=0V; full-ramp current, residual charge and PCB leakage unbound. Do not add0.5ms and typical delay as a guaranteed sum.'),
  additional_READY_monitor_output_current_sensitivity_A=monitor_current,
  added_load_at_bus32V_sensitivity_W=32*monitor_current,
  static_supply_scope='MAX16053 71uA at28V transferred conservatively to current rail; driver IQ max1mA at14V separately replaces old driver. Not a total brake power maximum.',
  legacy_PG=dict(diagnostic_only=True,enable_credit=False,retired_200k_model_critical_extra_sink_A=critical),
  gates=dict(native_logic_interface_can_be_checked=True,static_budget_conditional=all(checks.values()),
   whole_bias_ready_function_guaranteed=False,full_brake_function_verified=False,hardware_test_executed=False),
  open_requirements=['Actual receiver/monitor input-current range applicability','C302 effective>=10uF and C305 effective>=1uF with DC bias/temperature/layout',
   'Warm brownout reset, residual CDELAY charge and maximum READY recovery time','Driver thermal shutdown and gate-drive dissipation','PCB parasitic loop, effective bus C, real regeneration history and DM trip bounds'],
  scope_assertions={'typical_delay_not_promoted_to_guaranteed_max':True},falsifiers=falsifiers)
