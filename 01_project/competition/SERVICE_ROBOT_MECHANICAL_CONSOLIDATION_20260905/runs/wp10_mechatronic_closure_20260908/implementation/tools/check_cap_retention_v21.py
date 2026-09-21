"""Nominal-space checks and explicitly unqualified structural sensitivities."""
from pathlib import Path
import json,hashlib,sys,math,copy
A=Path(__file__).resolve().parents[1];sys.path.insert(0,str(A/'mechanical'))
from cap_harness_path import fillet_path
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
c=json.loads((A/'power/CAP_HARNESS_RETENTION_V21.json').read_text());w=json.loads((A/c['wire_definition']).read_text());d=c['design'];L=c['lacing']
def check(d):
 straight=[]
 for wire in w['wires']:
  segments=fillet_path(wire['sharp_vertices_S_mm'],wire['bend_radius_mm']);assert len(segments)==7
  seg=segments[4];assert seg['kind']=='line' and seg['start'][1:]==seg['end'][1:]
  assert abs(d['wire_z_mm']-seg['start'][2])<1e-9
  assert abs(d['saddle_center_abs_y_mm']-abs(seg['start'][1]))<1e-9
  assert 0<d['saddle_edge_radius_mm']<min(d['saddle_width_y_mm'],d['saddle_depth_mm'])/2
  assert d['saddle_depth_mm']-d['channel_depth_mm']>2*d['saddle_edge_radius_mm']
  lo,hi=sorted([seg['start'][0],seg['end'][0]]);a,b=d['tie_channel_x_mm'];x0,x1=d['saddle_x_mm'];tx=d['tie_center_x_mm'];width=L['width_min_max_mm'][1]
  assert lo<x0<a<b<x1<hi and a<=tx-width/2 and tx+width/2<=b
  assert x0<=d['bridge_x_mm'][0]<d['bridge_x_mm'][1]<a and d['channel_depth_mm']>=L['thickness_min_max_mm'][1]
  straight.append(dict(wire=wire['id'],straight_x_mm=[lo,hi],straight_length_mm=hi-lo,saddle_bend_margins_mm=[x0-lo,hi-x1],channel_bend_margins_mm=[a-lo,hi-b],tape_channel_total_clearance_mm=b-a-width))
 return straight
straight=check(d);faults=[]
for name,field,value in [('saddle_into_bend','saddle_x_mm',[-32.1,-28.1]),('channel_too_narrow','tie_channel_x_mm',[-30,-29]),('bridge_crosses_lace','bridge_x_mm',[-31.9,-29]),('channel_too_shallow','channel_depth_mm',.2),('saddle_wrong_z','wire_z_mm',-63),('saddle_wrong_y','saddle_center_abs_y_mm',18.78),('channel_cuts_through_saddle','channel_depth_mm',3.1),('channel_outside_saddle','tie_channel_x_mm',[-31.95,-28.4])]:
 b=copy.deepcopy(d);b[field]=value
 try:check(b);rejected=False
 except AssertionError:rejected=True
 faults.append(dict(name=name,rejected=rejected))
assert all(f['rejected'] for f in faults)
# Independent beam idealizations. One force applied to one saddle; no preload,
# fillet stress concentration, fatigue, creep or coupled frame stiffness credit.
vertical_lever=abs(d['wire_z_mm']-sum(d['arm_z_mm'])/2)
root_lever=math.hypot(abs(d['tie_center_x_mm']+23),vertical_lever)
def span(bounds):return bounds[1]-bounds[0]
beam_specs=[dict(name='root_arm',L_mm=root_lever,b_mm=span(d['arm_abs_y_mm']),h_mm=span(d['arm_z_mm'])),
 dict(name='drop',L_mm=vertical_lever,b_mm=span(d['drop_abs_y_mm']),h_mm=span(d['saddle_x_mm'])),
 dict(name='narrow_bridge',L_mm=6.,b_mm=d['saddle_depth_mm']-.8,h_mm=span(d['bridge_x_mm']))]
# 6 mm remains a declared bridge idealization. Actual free gap, load eccentricity
# and coupled torsion are not replaced with a short span to claim a strength pass.
beams=[]
for spec in beam_specs:
 b=spec['b_mm'];h=spec['h_mm'];I=b*h**3/12;Z=b*h*h/6
 for force in c['force_scenarios_N']:
  for E in c['material']['E_sensitivity_MPa']:
   beams.append(dict(**spec,force_N=force,E_MPa=E,sigma_nominal_MPa=force*spec['L_mm']/Z,tip_deflection_mm=force*spec['L_mm']**3/(3*E*I)))
out=dict(schema='WP10_CAP_RETENTION_ANALYTIC_V21',inputs={p:sha(p) for p in ['power/CAP_HARNESS_RETENTION_V21.json',c['wire_definition'],'mechanical/cap_harness_path.py','tools/check_cap_retention_v21.py']},straight_checks=straight,faults=faults,beam_sensitivity=beams,lacing_cut_allowance_g=L['quantity']*L['project_cut_allowance_mm_each']/1000*L['catalog_mass_g_per_m'],strength_allowable_MPa=None,structural_gate='NOT_EVALUATED_NO_ALLOWABLE_OR_LOAD_CONTRACT',geometry_parameter_checks_passed=True,strain_relief_complete=False,notes=['Single prismatic cantilever approximations are sensitivities, not frame certification. Thin bridge dominates.', 'No installed slip capacity is inferred from the 66 N tape catalog value.','Tolerance, knot and tool assembly envelopes need separate evaluation.'])
(A/'results/CAP_RETENTION_ANALYTIC_V21.json').write_text(json.dumps(out,indent=2))
print(json.dumps(dict(parameter_checks='PASS',faults_rejected=len(faults),max_sensitivity_sigma_MPa=max(x['sigma_nominal_MPa'] for x in beams),structural_gate=out['structural_gate'])))
