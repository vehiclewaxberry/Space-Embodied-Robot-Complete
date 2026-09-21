from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,csv,copy
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sel=json.loads((A/'power/LUG_HARNESS_SELECTION_V30.json').read_text());g=json.loads((C/'LUG_GEOMETRY_CHECK_V30.json').read_text());cl=json.loads((C/'LUG_CLAMP_CHECK_V30.json').read_text());el=json.loads((C/'LUG_ELECTROMECHANICAL_CHECK_V30.json').read_text());assert all(d['passed'] for d in [g,cl,el]);assert g['source_sha256']==cl['source_sha256']==sha(C/'main_input_lugs_v30.step.py')
assert all(sha(A/p)==h for p,h in el['source_lock'].items())
xml=A/'ecad/wp10_system.xml';tree=ET.parse(xml);components=tree.findall('./components/comp');mapping={}
for net in tree.findall('./nets/net'):
 for node in net.findall('node'):
  if node.get('ref') in ['J204','J205','J206','J207']:mapping[(node.get('ref'),node.get('pin'))]=net.get('name')
pin_count=len(tree.findall('./nets/net/node'))
assert len(components)==211 and pin_count==677 and all(mapping[(r['ref'],'1')]==r['net'] for r in sel['net_mapping'])
with (C/'LUG_PARTIAL_ASSEMBLY_BOM_V30.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=['occurrence','label','quantity','volume_mm3','mass_kg','scope']);w.writeheader()
 for i,r in enumerate(g['component_bounds'],1):w.writerow(dict(occurrence=f'o1.{i}',label=r['label'],quantity=1,volume_mm3=r['volume_mm3'],mass_kg='',scope='reference geometry; mass/material as-built unbound'))
with (C/'LUG_NET_BINDING_V30.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=['ref','net','wire_id','wire_mpn','lug_mpn','local_outside_barrel_mm','local_conductor_total_mm','remote_end_bound']);w.writeheader()
 for r in sel['net_mapping']:w.writerow(dict(**r,wire_mpn=sel['wire']['mpn'],lug_mpn=sel['lug']['mpn'],local_outside_barrel_mm=40,local_conductor_total_mm=46.35,remote_end_bound=False))
c=json.loads((C/'CANDIDATE_V29.json').read_text());assert all(sha(p)==h for p,h in c['source_lock'].items());c['schema']='WP10_COUPLED_CANDIDATE_V30';c['parent']='Same WP10 V29 electrical/PCB + V30 lug/cover/local harness + V28 unchanged full-instance spreader branch'
extra=[C/'main_input_lugs_v30.step.py',C/'main_input_lugs_v30.step',C/'LUG_SOURCE_LOCK_V30.json',C/'LUG_GEOMETRY_CHECK_V30.json',C/'LUG_CLAMP_CHECK_V30.json',C/'LUG_ELECTROMECHANICAL_CHECK_V30.json',C/'LUG_PARTIAL_ASSEMBLY_BOM_V30.csv',C/'LUG_NET_BINDING_V30.csv',A/'power/LUG_HARNESS_SELECTION_V30.json',A/'tools/check_lugs_v30.py',A/'tools/check_lug_clamp_v30.py',A/'tools/calculate_lug_harness_v30.py']
for rel in json.loads((C/'LUG_SOURCE_LOCK_V30.json').read_text()):extra.append(A/rel)
for p in extra:c['source_lock'][str(p)]=sha(p)
c['mechanical_local_delta']=dict(generator='coupled_closure/main_input_lugs_v30.step.py',solid_count=60,occurrence_count=56,whole_host_instance_plan='coupled_closure/SPREADER_INSTANCE_PLAN_V28.json',host_installed=False,full_harness_complete=False,clamp_retention_qualified=False,terminal_torque_bypass_qualified=False,partial_electrical_component_models_missing=23)
c['thermal_local_delta']=dict(cover_added=True,post_cover_thermal_solution_executed=False,prior_uncovered_case_still_failed=True,continuous_thermal_closure=False)
(C/'CANDIDATE_V30.json').write_text(json.dumps(c,indent=2));out=dict(revision='V30',same_WP10_candidate=True,electrical_refs=len(components),pin_network_records=pin_count,net_binding=[dict(ref=k[0],pin=k[1],net=v) for k,v in sorted(mapping.items())],PCB_unchanged_sha256=sha(A/'ecad/wp10_main_input.kicad_pcb'),XML_unchanged_sha256=sha(xml),V29_source_locks_still_valid=True,new_model_installed_in_whole_host=False,whole_design_complete=False,checks=dict(source_bound_geometry=True,source_bound_clamp=True,all_four_canonical_nets_match=True,V29_preserved=True),candidate_sha256=sha(C/'CANDIDATE_V30.json'))
(C/'SOURCE_ACTIVATION_V30.json').write_text(json.dumps(out,indent=2));(A/'CURRENT_WORKING_CANDIDATE.json').write_text(json.dumps(dict(revision='V30',same_WP10_candidate=True,entry='coupled_closure/REVIEW_V30.html',candidate='coupled_closure/CANDIDATE_V30.json',whole_design_complete=False,source_activation='coupled_closure/SOURCE_ACTIVATION_V30.json'),indent=2));print(json.dumps(out))
