"""Recompute current UV/sense corners from safe scalar AST segment only."""
from pathlib import Path
import ast,itertools,json,math
from input_passive_definition import PASSIVES
A=Path(__file__).resolve().parents[1]
s=(A/'tools/integrate_power_loop.py').read_text(encoding='utf-8')
snippet=s[s.index('Rs=.0022;'):s.index("dump(P/'POWER_LOOP_CALCULATIONS.json',calc)")]
tree=ast.parse(snippet)
# No call to native generator, imports or file writers exists in this segment.
for node in ast.walk(tree):
 if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
  assert node.func.id in ['dict','min','max','bool'],ast.unparse(node.func)
ns=dict(itertools=itertools,math=math,PASSIVES=PASSIVES)
exec(compile(tree,'safe_scalar_segment','exec'),ns)
p=json.loads((A/'power/POWER_LOOP_CALCULATIONS.json').read_text(encoding='utf-8-sig'))
for key in ['Rs_including_TCR_and_Kelvin_allocation_ohm','current_limit_screen_A',
 'UVLO_falling_screen_V','OVLO_rising_screen_V','scenarios','main_latched_limit_plus_aux_normal_screen_A']:
 p[key]=ns['calc'][key]
p['UVLO_rising_screen_V']=[min(ns['uvrise']),max(ns['uvrise'])]
p['UVLO_bias_scope']='1uA48V sensitivity; selected0.1pct25ppm and100K multiplicative envelope, life/thermal unverified'
p['Rs_tolerance_combination']='symmetric multiplicative initial1pct and75ppm/K100K envelope, plus Kelvin allocation'
p['precharge']['startup_typical_formula_with_sensitivity_s']=ns['ts']
(A/'power/POWER_LOOP_CALCULATIONS.json').write_text(json.dumps(p,indent=2),encoding='utf-8')
print(json.dumps(dict(UVLO_rise_V=p['UVLO_rising_screen_V'],Rs=p['Rs_including_TCR_and_Kelvin_allocation_ohm'])))

