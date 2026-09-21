"""Endpoint identity, true arc length and strip placement; no CAD execution."""
from pathlib import Path
import json,sys,math,copy,hashlib,xml.etree.ElementTree as ET
A=Path(__file__).resolve().parents[1];sys.path.insert(0,str(A/'mechanical'))
from cap_harness_path import fillet_path,slice_path,point,tangent,norm,sub
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
c=json.loads((A/'power/CAP_HARNESS_DEFINITION_V19.json').read_text());cap=json.loads((A/'power/CAP_TERMINAL_DEFINITION.json').read_text());chb=json.loads((A/'power/CHB_INPUT_DEFINITION.json').read_text())
native={(n.get('ref'),n.get('pin')):net.get('name') for net in ET.parse(A/'ecad/wp10_system.xml').getroot().findall('./nets/net') for n in net.findall('node')}
def evaluate(config):
 checks=[];detail=[]
 def ck(n,v):checks.append(dict(name=n,passed=bool(v)))
 expected_wire={k:v for k,v in cap['wire'].items() if k not in ['installed_cut_length_mm','minimum_installation_bend_radius_mm','physical_termination_and_strain_relief_complete']}
 ck('manufacturer_wire_parameters_bound',config['wire']==expected_wire and all(config['wire'][k]>0 for k in ['max_bare_D_mm','max_insulation_D_mm','max_R20_ohm_per_m']))
 ck('two_exact_wire_identifiers',sorted(w['id'] for w in config['wires'])==['C203_W_MINUS','C203_W_PLUS'])
 for w in config['wires']:
  name=w['id'].removeprefix('C203_W_');pin='1' if name=='PLUS' else '4';cpin='1' if name=='PLUS' else '2'
  a=next(x for x in cap['terminal_features'] if x['id']=='WIRE_'+name);b=next(x for x in chb['pads'] if x['id']=='CAP_'+pin)
  cap_face=a['S_face_mm'][0];cap_back=a['solder_exit_S_x_mm'];chb_bottom=chb['board_bounds_S_mm'][2];chb_top=chb['board_bounds_S_mm'][5]
  ck(name+'_native_net_and_terminal_identity',w['net']==native['C203',cpin]==native['U203',pin] and w['to_feature']=='CHB_INPUT_PCB.CAP_'+pin and w['from_feature']=='C203_PCB.WIRE_'+name and w['logical_to']=='U203.'+pin)
  p=fillet_path(w['sharp_vertices_S_mm'],w['bend_radius_mm']);L=sum(s['length'] for s in p);ins=slice_path(p,w['strip_start_mm'],L-w['strip_end_mm'])
  ck(name+'_exact_native_hole_axes',p[0]['start'][1:]==a['S_face_mm'][1:] and p[-1]['end'][:2]==b['S_xy_mm'])
  ck(name+'_bare_tip_projection',w['C203_solder_projection_mm']>0 and w['CHB_solder_projection_mm']>0 and abs(p[0]['start'][0]-(cap_back+w['C203_solder_projection_mm']))<1e-8 and abs(p[-1]['end'][2]-(chb_bottom-w['CHB_solder_projection_mm']))<1e-8)
  ck(name+'_tip_metadata_matches_actual_path',norm(sub(w['conductor_tip_start_S_mm'],p[0]['start']))<1e-8 and norm(sub(w['conductor_tip_end_S_mm'],p[-1]['end']))<1e-8)
  ck(name+'_specified_strip_boundaries',norm(sub(ins[0]['start'],w['insulation_start_S_mm']))<1e-8 and norm(sub(ins[-1]['end'],w['insulation_end_S_mm']))<1e-8)
  ck(name+'_insulation_setback_at_both_boards',ins[0]['start'][0]<=cap_face-1+1e-8 and ins[-1]['end'][2]>=chb_top+1-1e-8)
  ck(name+'_bare_conductor_spans_entire_board',p[0]['start'][0]>cap_back and ins[0]['start'][0]<cap_face and p[-1]['end'][2]<chb_bottom and ins[-1]['end'][2]>chb_top)
  ck(name+'_wire_radius_allocation',w['bend_radius_mm']>=6*config['wire']['max_insulation_D_mm'])
  ck(name+'_straight_entry_to_both_holes',tangent(p[0],0)==[-1.,0.,0.] and tangent(p[-1],1)==[0.,0.,-1.])
  # Independent polygon length convergence, not another sum of the stored arc lengths.
  sampled=[point(s,i/200) for s in p for i in range(201)]
  chord=sum(math.dist(a,b) for a,b in zip(sampled,sampled[1:]));ck(name+'_sampled_length_converges',0<=L-chord<.001)
  R=L/1000*config['wire']['max_R20_ohm_per_m']
  detail.append(dict(id=w['id'],analytic_cut_length_mm=L,insulated_length_mm=L-w['strip_start_mm']-w['strip_end_mm'],strip_lengths_mm=[w['strip_start_mm'],w['strip_end_mm']],arc_count=sum(s['kind']=='arc' for s in p),minimum_centerline_bend_radius_mm=w['bend_radius_mm'],minimum_inner_insulation_radius_mm=w['bend_radius_mm']-config['wire']['max_insulation_D_mm']/2,sampled_length_error_mm=L-chord,R20_max_ohm=R,wire_heat_at_2p4A_W=R*2.4**2,segments=p))
 return dict(passed=all(x['passed'] for x in checks),checks=checks,wires=detail)
assert all(sha(p)==h for p,h in c['inputs'].items())
baseline=evaluate(c);assert baseline['passed'],baseline
faults=[]
def fault(name,mutate):
 x=copy.deepcopy(c);mutate(x)
 try:r=evaluate(x);rejected=not r['passed'];why=[q['name'] for q in r['checks'] if not q['passed']]
 except (AssertionError,ValueError,StopIteration) as e:rejected=True;why=[str(e)]
 assert rejected,name
 faults.append(dict(name=name,rejected=rejected,reasons=why))
fault('wrong_positive_net',lambda x:x['wires'][0].update(net='WP10_INPUT_RETURN'))
fault('CHB_positive_endpoint_shift_1mm',lambda x:x['wires'][0]['sharp_vertices_S_mm'][-1].__setitem__(1,-16.78))
fault('insulation_inside_C203_hole',lambda x:x['wires'][0].update(strip_start_mm=1.0))
fault('radius_consumes_neighbor_segment',lambda x:x['wires'][0].update(bend_radius_mm=100))
fault('bend_radius_below_project_allocation',lambda x:x['wires'][0].update(bend_radius_mm=2))
fault('swap_positive_and_return_destination',lambda x:x['wires'][0].update(to_feature='CHB_INPUT_PCB.CAP_4'))
fault('stale_tip_metadata',lambda x:x['wires'][0]['conductor_tip_start_S_mm'].__setitem__(0,999))
fault('manufacturer_wire_resistance_zero',lambda x:x['wire'].update(max_R20_ohm_per_m=0))
def short_cap(x):
 w=x['wires'][0];w.update(C203_solder_projection_mm=-.5,strip_start_mm=2.1);w['sharp_vertices_S_mm'][0][0]=-5.9;w['conductor_tip_start_S_mm'][0]=-5.9
def short_chb(x):
 w=x['wires'][0];w.update(CHB_solder_projection_mm=-.5,strip_end_mm=2.1);w['sharp_vertices_S_mm'][-1][2]=-80.8;w['conductor_tip_end_S_mm'][2]=-80.8
fault('C203_conductor_stops_inside_board',short_cap)
fault('CHB_conductor_stops_inside_board',short_chb)
inputs=['power/CAP_HARNESS_DEFINITION_V19.json','mechanical/cap_harness_path.py','tools/check_cap_harness_path_v19.py',*c['inputs']]
out=dict(schema='WP10_C203_ROUTE_ANALYTIC_V19',**baseline,faults=faults,inputs={p:sha(p) for p in inputs},
 total_pair_R20_max_ohm=sum(w['R20_max_ohm'] for w in baseline['wires']),total_pair_heat_at_2p4A_W=sum(w['wire_heat_at_2p4A_W'] for w in baseline['wires']),
 thermal_scope='Wire-only 20degC manufacturer resistance bound at an example2.4A RMS; excludes contacts/solder/ripple-frequency/temperature rise; not installed electrical qualification',
 installed_loop_inductance_H=None,strain_relief_complete=False,whole_design_complete=False)
(A/'results/CAP_HARNESS_PATH_V19.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(passed=out['passed'],checks=len(out['checks']),faults=len(faults),cut_lengths_mm=[x['analytic_cut_length_mm'] for x in out['wires']],pair_R20_ohm=out['total_pair_R20_max_ohm'])))
