"""Functional parity, real copper connectivity and deliberate disconnect falsifiers."""
import ast,math,json,collections,copy
from terminals_v29 import A,H,ROWS,sha,dump
from erc_source_contract import physical_netlist,parse,children,val,properties,native_erc_summary
oldc,oldp=physical_netlist(H/'ecad/wp10_system.xml');newc,newp=physical_netlist(A/'ecad/wp10_system_v29.xml')
checks={};checks['old_207_components_unchanged']=len(oldc)==207 and all(newc.get(k)==v for k,v in oldc.items())
checks['only_four_declared_new_components']=set(newc)-set(oldc)=={r[0] for r in ROWS}
checks['all_original_673_pin_networks_and_types_preserved']=len(oldp)==673 and all(newp.get(k)==v for k,v in oldp.items())
checks['four_new_pins_on_intended_nets']=len(newp)==677 and all(newp.get((r,'1'))==(n,'passive') for r,_,_,n in ROWS)
erc=json.loads((A/'results/SYSTEM_ERC_V29.json').read_text());normalized=copy.deepcopy(erc)
# --severity-all includes exclusions as well; the legacy helper expected exactly
# error+warning. Keep all violations and accept this explicitly stronger report.
assert set(erc['included_severities'])=={'error','warning','exclusion'}
normalized['included_severities']=['error','warning'];er=native_erc_summary(normalized);er['actual_included_severities']=erc['included_severities']
checks['native_ERC_0_error_0_warning']=er['ERC_clean']
dr=json.loads((A/'results/MAIN_INPUT_DRC_V29.json').read_text());prior=json.loads((A/'results/MAIN_INPUT_CANDIDATE_DRC_V26.json').read_text())
checks['DRC_no_new_rule_violations']=not dr['violations'] and len(dr['unconnected_items'])==4
checks['DRC_ignored_rules_unchanged']=dr['ignored_checks']==prior['ignored_checks']
d=json.loads((A/'power/MAIN_INPUT_BOARD_DEFINITION_V29.json').read_text());native=json.loads((A/'results/MAIN_INPUT_NATIVE_READBACK_V29.json').read_text())
checks['native_hash_current']=native['PCB_sha256']==sha(A/'ecad/wp10_main_input_v29_candidate.kicad_pcb') and native['source_xml_sha256']==sha(A/'ecad/wp10_system_v29.xml')
checks['definition_pad_fields_bound_to_native_source']=native['definition_sha256']==sha(A/'power/MAIN_INPUT_BOARD_DEFINITION_V29.json') and native['pad_records']==d['pads'] and d['PCB_sha256']==native['PCB_sha256'] and d['source_xml_sha256']==native['source_xml_sha256']
# Reuse just the pure geometry functions; never execute the V26 script body.
src=ast.parse((A/'tools/check_main_input_copper_v26.py').read_text());names={'pd','orient','sd','br','edges','touching','component'};ns={'math':math}
exec(compile(ast.Module(body=[n for n in src.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'pure_copper_graph','exec'),ns)
component=ns['component'];objects=[]
for p,uid in zip(d['pads'],native['pad_uuids'],strict=True):
 if p['net']:objects.append(dict(uuid=uid,net=p['net'],ref=p['ref'],pin=p['pin'],pos=p['xy_mm'],box=p['bbox_mm'],layers=['F.Cu','B.Cu'] if p['through_hole'] else ['F.Cu']))
for t,uid in zip(native['tracks'],native['track_uuids'],strict=True):
 if t['type']=='via':objects.append(dict(uuid=uid,net=t['net'],a=t['xy_mm'],b=t['xy_mm'],radius=t['diameter_mm']/2,layers=['F.Cu','B.Cu']))
 else:objects.append(dict(uuid=uid,net=t['net'],a=t['start_mm'],b=t['end_mm'],radius=t['width_mm']/2,layers=[t['layer']]))
# The AABB graph remains conservative only for proving Kelvin isolation.
# Positive terminal continuity uses circular annuli, not their bounding boxes.
exact=copy.deepcopy(objects)
for o in exact:
 if o.get('ref') in {r[0] for r in ROWS}:o.pop('box');o.update(ring_center=o['pos'],outer=1.6,inner=.925)
def exact_touch(a,b):
 if not set(a['layers'])&set(b['layers']):return False
 if 'ring_center' not in a and 'ring_center' not in b:return ns['touching'](a,b)
 if 'ring_center' not in a:a,b=b,a
 c=a['ring_center'];R=a['outer'];r=a['inner']
 if 'ring_center' in b:
  z=math.dist(c,b['ring_center']);return z<=R+b['outer']+1e-9 and z+R>=b['inner']-1e-9 and z+b['outer']>=r-1e-9
 if 'box' in b:
  x,y,X,Y=b['box'];lo=math.dist(c,(max(x,min(X,c[0])),max(y,min(Y,c[1]))));hi=max(math.dist(c,v) for v in [(x,y),(x,Y),(X,y),(X,Y)])
 else:lo=max(0,ns['pd'](c,b['a'],b['b'])-b['radius']);hi=max(math.dist(c,b['a']),math.dist(c,b['b']))+b['radius']
 return lo<=R+1e-9 and hi>=r-1e-9
def exact_component(obs,start):
 seen={start};todo=[start]
 while todo:
  i=todo.pop()
  for j,o in enumerate(obs):
   if j not in seen and obs[i]['net']==o['net'] and exact_touch(obs[i],o):seen.add(j);todo.append(j)
 return seen
electrodes=[]
for ref,_,_,_ in ROWS:
 ids=[i for i,p in enumerate(exact) if p.get('ref')==ref];reachable=exact_component(exact,ids[0]);ok=len(ids)==9 and set(ids)<=reachable
 electrodes.append(dict(reference=ref,nine_pins_physically_connected=ok,component_pad_count=sum('ref' in objects[i] for i in reachable)))
checks['36_terminal_pins_have_actual_copper_paths']=all(x['nine_pins_physically_connected'] for x in electrodes)
kelvin=[];expected_drc=set()
for ref,pin in [('R201','1'),('R201','2'),('R202','1'),('R202','2')]:
 ids=sorted([i for i,p in enumerate(objects) if p.get('ref')==ref and p.get('pin')==pin],key=lambda i:objects[i]['pos'][1]);power,sense=ids;seen=component(objects,sense)
 attached=sorted((objects[i]['ref'],objects[i]['pin']) for i in seen if 'ref' in objects[i] and i!=sense)
 expected=[('U201','2')] if (ref,pin)==('R201','1') else [('U201','1')] if (ref,pin)==('R202','2') else []
 expected_drc.add(frozenset([min(component(objects,power)),min(seen)]))
 kelvin.append(dict(ref=ref,pin=pin,isolated=power not in seen,attached=attached,expected=expected,passed=power not in seen and attached==expected))
checks['all_four_Kelvin_splits_preserved']=all(x['passed'] for x in kelvin)
uidmap={o['uuid']:i for i,o in enumerate(objects)}
def drc_pairs(report):
 pairs=[]
 for v in report['unconnected_items']:
  if len(v['items'])!=2 or any(i['uuid'] not in uidmap for i in v['items']):return None
  pairs.append(frozenset(min(component(objects,uidmap[i['uuid']])) for i in v['items']))
 return set(pairs) if len(pairs)==4 and len(set(pairs))==4 else None
checks['four_DRC_items_identify_exact_Kelvin_components']=drc_pairs(dr)==expected_drc
falsifiers=[]
for ref,_,pos,net in ROWS:
 # Remove both complete outer row/column copper bars on both faces. A real
 # missing corner connection must fail even though all nine pads remain #1.
 corner=[round(pos[0]+(4.435 if pos[0]>50 else -4.435),6),round(pos[1]-4.435,6)]
 def cut(o):
  if 'a' not in o or o['net']!=net or abs(o['radius']-1.6)>1e-9:return False
  a,b=o['a'],o['b'];return (abs(a[1]-corner[1])<1e-6 and abs(b[1]-corner[1])<1e-6 and abs(min(a[0],b[0])-(pos[0]-4.435))<1e-6) or (abs(a[0]-corner[0])<1e-6 and abs(b[0]-corner[0])<1e-6 and abs(min(a[1],b[1])-corner[1])<1e-6)
 mutant=[o for o in exact if not cut(o)];start=next(i for i,p in enumerate(mutant) if p.get('ref')==ref and all(abs(p['pos'][j]-corner[j])<1e-6 for j in range(2)));seen=exact_component(mutant,start)
 connected=sum(mutant[i].get('ref')==ref for i in seen);falsifiers.append(dict(ref=ref,removed_bars=len(objects)-len(mutant),remaining_reachable_pads=connected,caught=connected<9))
 if ref=='J204':
  fake=dict(net=net,a=[4.115,12.115],b=[7,12.115],radius=.15,layers=['F.Cu']);q=exact_component(mutant+[fake],start)
  falsifiers.append(dict(name='reviewer_AABB_corner_false_bridge',real_gap_mm=ns['pd'](corner,fake['a'],fake['b'])-1.6-.15,caught=sum((mutant+[fake])[i].get('ref')==ref for i in q)==1))
checks['four_same_number_pad_disconnects_detected']=all(f['caught'] for f in falsifiers)
wrong=copy.deepcopy(dr);wrong['unconnected_items'][0]['items'][0]['uuid']=next(o['uuid'] for o in objects if o.get('ref')=='J204')
checks['same_count_wrong_DRC_identity_rejected']=drc_pairs(wrong)!=expected_drc
wrongpads=copy.deepcopy(d['pads']);wrongpads[0]['xy_mm'][0]+=.001
checks['wrong_pad_source_rejected']=wrongpads!=native['pad_records']
# Preserve the historical series-path approximation, updated to real moved
# endpoints. No resistance credit is taken for added parallel pad-grid copper.
fixed=json.loads((A/'power/MAIN_INPUT_FIXED_COPPER_V26.json').read_text());path=[]
for t in fixed['fixed_segments']:
 if t['role'] not in ['MAIN_FORWARD','MAIN_FORWARD_NECK','MAIN_RETURN']:continue
 q=copy.deepcopy(t)
 for key in ['start_mm','end_mm']:
  p=q[key]
  if q['role']=='MAIN_RETURN' and p[0] in [17,83]:p[0]=18 if p[0]==17 else 82
  if q['role']=='MAIN_FORWARD' and p in [[13.325,15],[22.675,15]]:p[0]+=2
 q['length_mm']=math.dist(q['start_mm'],q['end_mm']);q['R20_ohm']=.017241*q['length_mm']/1000/(q['width_mm']*.07);path.append(q)
R=sum(t['R20_ohm'] for t in path)
loss=dict(schema='WP10_V29_CONDITIONAL_COPPER_LOSS',PCB_sha256=sha(A/'ecad/wp10_main_input_v29_candidate.kicad_pcb'),R20_ohm=R,reference_copper_thickness_mm=.07,qualified=False,method='Existing series centerline approximation updated to moved endpoints; no added-grid parallel-copper credit.',main_path_segments=path,excluded=['lug and stud contacts','solder and pad spreading','PTH plating','etch/tolerance and temperature gradients'],loss_20A_100C_W=400*R*(1+.00393*80))
dump(A/'power/MAIN_INPUT_COPPER_LOSS_V29.json',loss)
dump(A/'results/TERMINAL_ELECTRICAL_AUDIT_V29.json',dict(passed=all(checks.values()),checks=checks,electrodes=electrodes,kelvin=kelvin,falsifiers=falsifiers,ERC=er,DRC_unconnected=4,whole_design_complete=False,PCB_DRC_passed=False,manufacturing_release=False,input_hashes={p:sha(A/p) for p in ['power/MAIN_INPUT_BOARD_DEFINITION_V29.json','results/MAIN_INPUT_NATIVE_READBACK_V29.json','results/MAIN_INPUT_DRC_V29.json','results/SYSTEM_ERC_V29.json','ecad/wp10_system_v29.xml','ecad/wp10_main_input_v29_candidate.kicad_pcb','tools/audit_terminals_v29.py']}))
print(json.dumps(dict(checks=checks,falsifiers=falsifiers,R20_ohm=R)));assert all(checks.values()),checks
