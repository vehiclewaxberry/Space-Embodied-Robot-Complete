"""One-time source derivation; old runner and core are immutable."""
from pathlib import Path
A=Path(__file__).resolve().parents[1]
old=(A/'tools/verify_hotswap_transient_v23.py').read_text(encoding='utf-8')
s=old.replace('V23','V24').replace('verify_hotswap_transient_v23.py','verify_hotswap_transient_v24.py')
s=s.replace("from hotswap_transient_model_v23 import Circuit, timer_pulse_train","from hotswap_transient_model_v23 import Circuit, timer_pulse_train\nfrom timer_passive_definition_v24 import TIMING_PASSIVES as T")
s=s.replace("'results/BRAKE_ENABLE_NATIVE_V22.json'","'results/TIMER_PASSIVES_NATIVE_V24.json','power/TIMER_PASSIVE_SELECTION_V24.json','power/TIMER_PASSIVE_CALCULATIONS_V24.json','tools/timer_passive_definition_v24.py'")
s=s.replace("ck('C201_value_unchanged_not_new_physical_part',nc['C201']=='1uF_10pct_16V')","ck('selected_C201_native_MPN',nc['C201']==T['C201']['MPN'])")
start=s.index('    match=re.fullmatch')
end=s.index('    profiles=[]',start)
s=s[:start]+"""    rp_nom=T['R207']['resistance_ohm']
    rp_tol=T['R207']['initial_tolerance_fraction']+T['R207']['TCR_per_K']*100
    ck('R207_selected_native_code_and_bounds',nc['R207']==T['R207']['MPN'] and rp_nom==30100 and abs(rp_tol-.0035)<1e-12)
"""+s[end:]
s=s.replace("active_electrical_native_revision='V22_UNCHANGED'","active_electrical_native_revision='V24'")
s=s.replace("C201_nominal_tolerance=.1,C201_MPN_bound=False","C201_effective_tolerance_requirement=.1,C201_initial_tolerance=.05,C201_MPN_bound=True,C201_environment_verified=False")
s=s.replace("initial_tolerance=.1,","effective_tolerance_requirement=.1,")
s=s.replace("chosen_new_part=False","chosen_new_part=cv==1e-6")
s=s.replace("Retain C201 1uF allocation. 680nF fails this sampled1.5 allowance;820nF remains unselected, effective C/leakage/gate dynamics and SOA open.","Select WIMA1uF5pct initial; use retained0.9..1.1uF effective-C requirement only as conditional screen. R207 selected0.1pct25ppm with100K allocation. Full temperature/leakage/gate dynamics and SOA open.")
s=s.replace("native_rerun=False,native_revision_unchanged='V22'","native_export_separate_from_this_scalar_job=True,native_revision='V24'")
path=A/'tools/verify_hotswap_transient_v24.py';assert not path.exists()
path.write_text(s,encoding='utf-8')
print('Derived V24 runner; V23 pure core reused unchanged')

