"""Source-bound copper integrity and conditional DC loss debit; no thermal release."""
from pathlib import Path
import json,hashlib,collections,math
from erc_source_contract import parse,enc,children,val,properties
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,x):(A/p).write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
candidate='ecad/wp10_main_input_v26_candidate.kicad_pcb';fixed='ecad/wp10_main_input_v26_fixed.kicad_pcb'
c=parse((A/candidate).read_text());f=parse((A/fixed).read_text())
allowed=set(read('results/MAIN_INPUT_SIGNAL_MERGE_V26.json')['allowed_nets'])
def copper(t):return [n for n in t if isinstance(n,list) and n[0] in ['segment','via']]
def canonical(n):return enc([v for v in n if not isinstance(v,list) or v[0]!='uuid'])
def critical(t):return collections.Counter(canonical(n) for n in copper(t) if val(children(n,'net')[0][-1]) not in allowed)
fp=lambda t:{properties(n)['Reference']:enc(n) for n in children(t,'footprint')}
checks=dict(fixed_copper_exact=critical(c)==critical(f),footprints_exact=fp(c)==fp(f),
 no_zones=len(children(c,'zone'))==0,no_extra_copper_graphics=not [n for n in c if isinstance(n,list) and n[0].startswith('gr_') and children(n,'layer') and val(children(n,'layer')[0][-1]) in ['F.Cu','B.Cu']])
native=read('results/MAIN_INPUT_NATIVE_READBACK_V26.json');d=read('power/MAIN_INPUT_BOARD_DEFINITION_V26.json');drc=read('results/MAIN_INPUT_CANDIDATE_DRC_V26.json')
checks.update(native_source_current=native['PCB_sha256']==sha(candidate),all_pad_nets_match=native['all_functional_pad_nets_match'],
 four_split_pad_errors_only=len(drc['unconnected_items'])==4 and not drc['violations'],
 default_DRC_ignores_not_relaxed=drc['ignored_checks']==read('results/MAIN_INPUT_BOARD_DRC_V25.json')['ignored_checks'])
# Actual copper graph: do NOT connect two pads merely because their number matches.
# Pad bounding boxes deliberately overestimate rounded-pad copper. Therefore a
# disconnection proven with these boxes is conservative, not a false isolation pass.
def pd(p,a,b):
 vx,vy=b[0]-a[0],b[1]-a[1];z=vx*vx+vy*vy
 q=0 if z==0 else max(0,min(1,((p[0]-a[0])*vx+(p[1]-a[1])*vy)/z))
 return math.dist(p,(a[0]+q*vx,a[1]+q*vy))
def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def sd(a,b,c,d):
 if max(min(a[0],b[0]),min(c[0],d[0]))<=min(max(a[0],b[0]),max(c[0],d[0]))+1e-9 and max(min(a[1],b[1]),min(c[1],d[1]))<=min(max(a[1],b[1]),max(c[1],d[1]))+1e-9 and orient(a,b,c)*orient(a,b,d)<=0 and orient(c,d,a)*orient(c,d,b)<=0:return 0
 return min(pd(a,c,d),pd(b,c,d),pd(c,a,b),pd(d,a,b))
def br(p,box):return box[0]<=p[0]<=box[2] and box[1]<=p[1]<=box[3]
def edges(box):
 x,y,X,Y=box;v=[(x,y),(X,y),(X,Y),(x,Y)];return list(zip(v,v[1:]+v[:1]))
def touching(a,b):
 if not set(a['layers'])&set(b['layers']):return False
 if 'box' in a and 'box' in b:
  x,y,X,Y=a['box'];u,v,U,V=b['box'];return max(x,u)<=min(X,U)+1e-9 and max(y,v)<=min(Y,V)+1e-9
 if 'box' in a:a,b=b,a
 if 'box' in b:
  if br(a['a'],b['box']) or br(a['b'],b['box']):return True
  return min(sd(a['a'],a['b'],u,v) for u,v in edges(b['box']))<=a['radius']+1e-9
 return sd(a['a'],a['b'],b['a'],b['b'])<=a['radius']+b['radius']+1e-9
objects=[]
for p in d['pads']:
 if p['net']:objects.append(dict(net=p['net'],ref=p['ref'],pin=p['pin'],pos=p['xy_mm'],box=p['bbox_mm'],layers=['F.Cu','B.Cu'] if p['through_hole'] else ['F.Cu']))
for t in native['tracks']:
 if t['type']=='via':objects.append(dict(net=t['net'],a=t['xy_mm'],b=t['xy_mm'],radius=t['diameter_mm']/2,layers=['F.Cu','B.Cu']))
 else:objects.append(dict(net=t['net'],a=t['start_mm'],b=t['end_mm'],radius=t['width_mm']/2,layers=[t['layer']]))
def component(objs,start):
 seen={start};todo=[start]
 while todo:
  a=todo.pop()
  for j,b in enumerate(objs):
   if j not in seen and objs[a]['net']==b['net'] and touching(objs[a],b):seen.add(j);todo.append(j)
 return seen
terminal=[]
for ref,pin in [('R201','1'),('R201','2'),('R202','1'),('R202','2')]:
 ids=[i for i,p in enumerate(objects) if p.get('ref')==ref and p.get('pin')==pin];assert len(ids)==2
 power,sense=sorted(ids,key=lambda i:objects[i]['pos'][1]);reachable=component(objects,sense)
 attached=[(objects[i]['ref'],objects[i]['pin']) for i in reachable if 'ref' in objects[i] and i!=sense]
 expected=[('U201','2')] if (ref,pin)==('R201','1') else [('U201','1')] if (ref,pin)==('R202','2') else []
 row=dict(ref=ref,pin=pin,net=objects[sense]['net'],power_center_mm=objects[power]['pos'],sense_center_mm=objects[sense]['pos'],
  bare_copper_isolated=power not in reachable,attached_other_pads=attached,expected_other_pads=expected,
  passed=power not in reachable and sorted(attached)==sorted(expected),assembly_bridge_required=True)
 terminal.append(row)
checks['Kelvin_graph_isolation_and_no_third_taps']=all(t['passed'] for t in terminal)
# Six deliberate falsifiers exercise the graph implementation on real geometry.
r=terminal[0];start=next(i for i,p in enumerate(objects) if p.get('ref')=='R201' and p.get('pin')=='1' and p['pos'][1]>17)
end=next(i for i,p in enumerate(objects) if p.get('ref')=='R201' and p.get('pin')=='1' and p['pos'][1]<17)
net=r['net'];p=r['power_center_mm'];s=r['sense_center_mm']
def wire(a,b,layer='F.Cu',radius=.1):return dict(net=net,a=a,b=b,radius=radius,layers=[layer])
mutants={
 'direct_gap_bridge':[wire(p,s)],
 'outside_detour_bridge':[wire(p,(29,14.11)),wire((29,14.11),(29,18.3)),wire((29,18.3),s)],
 'double_face_via_bridge':[dict(net=net,a=p,b=p,radius=.3,layers=['F.Cu','B.Cu']),wire(p,s,'B.Cu'),dict(net=net,a=s,b=s,radius=.3,layers=['F.Cu','B.Cu'])],
 'C202_tap':[wire(s,(28,24))],
 'tangent_gap_bridge':[wire((p[0],17.065),(s[0],17.755))]}
mutant_results=[]
for name,added in mutants.items():
 seen=component(objects+added,start)
 caught=any(objects[i].get('ref')=='C202' for i in seen if i<len(objects)) if name=='C202_tap' else end in seen
 mutant_results.append(dict(name=name,caught=caught))
removed=[o for o in objects if not ('a' in o and o['net']==net and o['a']==[31.535,18.3] and o['b']==[31.535,22.0])]
new_start=next(i for i,o in enumerate(removed) if o.get('ref')=='R201' and o.get('pin')=='1' and o['pos'][1]>17)
mutant_results.append(dict(name='Kelvin_wire_cut',caught=not any(removed[i].get('ref')=='U201' for i in component(removed,new_start))))
checks['six_falsifiers_detected']=all(v['caught'] for v in mutant_results)
dump('results/MAIN_INPUT_COPPER_INTEGRITY_V26.json',dict(passed=all(checks.values()),checks=checks,terminals=terminal,falsifiers=mutant_results,
 source_hashes={p:sha(p) for p in [candidate,fixed,'results/MAIN_INPUT_NATIVE_READBACK_V26.json','results/MAIN_INPUT_CANDIDATE_DRC_V26.json','tools/check_main_input_copper_v26.py']},
 method='Physical same-layer copper overlap and via/PTH layer links; duplicate pad numbers do not add edges; rounded-pad bounding boxes conservatively overestimate copper.',PCB_DRC_passed=False,manufacturing_release=False))
rho=.017241;alpha=.00393;t=.07;rows=[]
for s in read('power/MAIN_INPUT_FIXED_COPPER_V26.json')['fixed_segments']:
 if s['role'] in ['MAIN_FORWARD','MAIN_FORWARD_NECK','MAIN_RETURN']:
  q=dict(s);q['R20_ohm']=rho*(q['length_mm']/1000)/(q['width_mm']*t);rows.append(q)
R=sum(q['R20_ohm'] for q in rows);limit=read('power/POWER_LOOP_CALCULATIONS.json')['current_limit_screen_A'][1]
cases=[dict(current_A=i,copper_temperature_C=T,R_ohm=R*(1+alpha*(T-20)),voltage_drop_V=i*R*(1+alpha*(T-20)),loss_W=i*i*R*(1+alpha*(T-20))) for T in [20,100] for i in [20,limit]]
dump('power/MAIN_INPUT_COPPER_LOSS_V26.json',dict(schema='WP10_V26_CONDITIONAL_COPPER_LOSS',PCB_sha256=sha(candidate),
 rho20_ohm_mm2_per_m=rho,R_temperature_coefficient_per_K=alpha,finished_copper_thickness_requirement_mm=t,copper_thickness_qualified=False,
 reference='https://www.govinfo.gov/content/pkg/GOVPUB-C13-3b218703c40cd48e0384d3a8b2aff743/pdf/GOVPUB-C13-3b218703c40cd48e0384d3a8b2aff743.pdf',
 method='Sum rho*centerline_length/(width*thickness), fixed reference geometry; nominal rectangular-segment approximation, not a rigorous bound or IPC ampacity certification.',
 main_path_segments=rows,R20_ohm=R,cases=cases,nearby_sensitivity_current_limit_is_not_short_peak_bound=True,
 excluded=['pad current spreading and necks','solder and wire landing contact','PTH plated barrels','nonuniform current at turns','Q201 and resistor/fuse loss','copper etch/tolerance/temperature gradients'],
 thermal_budget_debit_W_at_20A_20C=cases[0]['loss_W'],not_inherited_as_verified_part_of_legacy_40mOhm_allocation=True,thermal_path_qualified=False,manufacturing_release=False))
print(json.dumps(dict(checks=checks,copper_R20_ohm=R,copper_loss_20A_20C_W=cases[0]['loss_W'])))
assert all(checks.values()),checks
