from pathlib import Path
import json
A=Path(__file__).resolve().parents[1]
p=A/'tools/integrate_power_loop.py'; s=p.read_text(encoding='utf-8')
s=s.replace("import ast, collections, csv, hashlib, itertools, json, math, re, shutil, uuid","import ast, collections, csv, hashlib, itertools, json, math, re, shutil, uuid\nfrom input_passive_definition import PASSIVES")
anchor="passive('D201','SMBJ30A-13-F'"
idx=s.index(anchor)
s=s[:idx]+"""# Bind selected inputs without renumbering the original hierarchy.
parts['F201'].update(mpn=PASSIVES['F201']['MPN'],source=PASSIVES['F201']['source_url']+' June2025 p2',role='30A backup fuse; L/R and clearing coordination OPEN',status='SELECTED_CANDIDATE_COORDINATION_OPEN')
parts['C203'].update(mpn=PASSIVES['C203']['MPN'],pins={'1':'PLUS','2':'MINUS'},source=PASSIVES['C203']['source_url'],role='2200uF 100V polarized; pad1+ pad2-; ripple/temp OPEN',status='SELECTED_CANDIDATE_ENVIRONMENT_OPEN',footprint=PASSIVES['C203']['footprint'])
dump(P/'INPUT_PASSIVE_SELECTION.json',PASSIVES)
""" +s[idx:]
old="""  objs.append(textobj(v['role'][:94],x-15, y+min(h+5,52),ref+'role'))"""
new="""  if v.get('footprint'):
   objs[-1].append(parse(f'(property "Footprint" {q(v["footprint"])} (at {x} {y} 0) (effects (font (size 1 1)) hide))'))
  objs.append(textobj(v['role'][:94],x-15, y+min(h+5,52),ref+'role'))"""
assert old in s; s=s.replace(old,new)
s=s.replace('Source-bound pins; fuse/capacitor MPNs, startup supervisor, clamp energy and thermal qualification remain OPEN.','F201/C203 selected; protection coordination, startup dynamics, ripple and thermal qualification remain OPEN.')
s=s.replace("ts=.0022*1.2/2*", "c203_max=PASSIVES['C203']['C_nominal_F']*(1+PASSIVES['C203']['tolerance_fraction'])\nts=c203_max/2*")
s=s.replace("Cmax_F=.0022*1.2,energy_J=.5*.0022*1.2*29.4**2", "Cmax_F=c203_max,energy_J=.5*c203_max*29.4**2")
s=s.replace("Input fuse and capacitor final MPN/clearing/startup/SOA and full-temperature efficiency unverified", "F201/C203 MPNs selected; fuse L/R and clearing, C203 ripple/temperature, startup/SOA and efficiency qualification unverified")
s=s.replace("for r in bom:\n if r['MPN']=='RRC-PMM35'", "bom=[r for r in bom if r['role'].split(':',1)[0] not in parts]\nfor r in bom:\n if r['MPN']=='RRC-PMM35'")
s=s.replace("manufacturer='see source',MPN=v['mpn']", "manufacturer=PASSIVES.get(ref,{}).get('manufacturer','see source'),MPN=v['mpn']")
p.write_text(s,encoding='utf-8')
p=A/'power/SHARED_BATTERY_PATH_DEFINITION.json'; v=json.loads(p.read_text(encoding='utf-8'))
v['schema']='WP10_SHARED_BATTERY_PATH_DEFINITION_V2'
v['cases']['main_leak_A']=.003
v['cases']['main_leak_scope']='C203 max 3mA at20C after5min applied as operating-voltage scenario; not full-temperature guarantee; distinct from controller3mA and startup0.25W.'
v['load_binding']['capacitor_leakage_node']='PRECHARGED_PLUS; only charged ON case. Cold open switch has zero source leakage current; stored capacitor discharge not calculated.'
v['passive_selection']='power/INPUT_PASSIVE_SELECTION.json'
p.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
p=A/'tools/check_shared_battery_path.py';s=p.read_text(encoding='utf-8')
s=s.replace("ctrl=cases['controller_input_A']", "ctrl=cases['controller_input_A']; leak=cases['main_leak_A']")
s=s.replace("aux_w=aw,controller_a=ctrl)", "aux_w=aw,controller_a=ctrl,main_leak_a=leak)")
s=s.replace("dict(args,main_w=0)", "dict(args,main_w=0,main_leak_a=0)")
s=s.replace("cases['controller_input_A'])", "cases['controller_input_A'],cases['main_leak_A'])")
s=s.replace("'ecad/wp10_system.xml',c['active_geometry_plan']", "'ecad/wp10_system.xml','power/INPUT_PASSIVE_SELECTION.json',c['active_geometry_plan']")
s=s.replace("WP10_COUPLED_SHARED_BATTERY_DC_V1", "WP10_COUPLED_SHARED_BATTERY_DC_V2")
s=s.replace("native_schematic_modified=False", "native_schematic_modified=True")
s=s.replace("aux_w=16.8/.8,controller_a=.003)", "aux_w=16.8/.8,controller_a=.003,main_leak_a=.003)")
anchor="def status(value, limits):"
new="""q=solve(25,.1,.04,.005,0,0,0,controller_a=.002,main_leak_a=.003)
expected_v=25-.1*.005-.005*.005-.035*.003
ck('constant_current_leakage_only_matches_KVL',abs(q['main_input_V']-expected_v)<1e-10 and abs(q['heat_W']['input_capacitor_leakage']-.003*expected_v)<1e-10)
ck('selected_C203_polarity_and_leak_bound',parts['C203']['mpn']=='ELXG101VSN222MR50S' and parts['C203']['pins']=={'1':'PLUS','2':'MINUS'} and c['cases']['main_leak_A']==.003)
""" +anchor
assert anchor in s;s=s.replace(anchor,new)
p.write_text(s,encoding='utf-8')
print('Updated selected parts, polarity, footprint property, precharge binding, idempotent BOM and leakage model.')

