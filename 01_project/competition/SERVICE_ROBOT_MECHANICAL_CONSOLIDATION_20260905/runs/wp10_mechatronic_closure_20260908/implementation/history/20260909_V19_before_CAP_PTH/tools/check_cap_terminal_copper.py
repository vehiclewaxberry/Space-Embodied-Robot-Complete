"""Physical copper connectivity from native pads/tracks, with real drilled voids.

OCP planar solids at unit thickness; equal pin numbers do not create edges.
This is a geometric circuit check, not a solder-joint/process qualification.
"""
from pathlib import Path
import json,hashlib,math,copy
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder,BRepPrimAPI_MakeBox
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse,BRepAlgoAPI_Cut,BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.STEPControl import STEPControl_Reader
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir,gp_Trsf
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,x):(A/p).write_text(json.dumps(x,indent=2),encoding='utf-8')
g=read('results/CAP_TERMINAL_NATIVE_GEOMETRY.json');d=read('power/CAP_TERMINAL_DEFINITION.json');s=read('results/CAP_TERMINAL_STACKUP.json')
assert g['board_sha256']==s['native_board_sha256']==sha(d['board'])
assert g['extractor_sha256']==sha('tools/cap_terminal_native.py')
assert all(p['circular'] and p['size_mm'][0]==p['size_mm'][1] and p['drill_mm'][0]==p['drill_mm'][1] for p in g['pads'])
assert all(t['kind']=='PCB_TRACK' and t['width_mm']==4 for t in g['tracks']) and len(g['tracks'])==6
assert g['copper_drawing_count']==0 and g['edge_count_is_four_line_segments']
def op(cls,a,b):
    r=cls(a,b);r.Build();assert r.IsDone();return r.Shape()
def union(items):
    if not items:return None
    ans=items[0]
    for item in items[1:]:ans=op(BRepAlgoAPI_Fuse,ans,item)
    return ans
def disk(x,y,r,z=0,h=1):return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,z),gp_Dir(0,0,1)),r,h).Shape()
def vol(x):
    p=GProp_GProps();BRepGProp.VolumeProperties_s(x,p);return p.Mass()
def solids(x):
    e=TopExp_Explorer(x,TopAbs_SOLID);n=0
    while e.More():n+=1;e.Next()
    return n
def capsule(t):
    x0,y0=t['start_mm'];x1,y1=t['end_mm'];w=t['width_mm'];L=math.hypot(x1-x0,y1-y0);assert L>0
    b=BRepPrimAPI_MakeBox(L,w,1).Shape();c=(x1-x0)/L;q=(y1-y0)/L;tr=gp_Trsf();tr.SetValues(c,-q,0,x0+q*w/2,q,c,0,y0-c*w/2,0,0,1,0)
    return union([BRepBuilderAPI_Transform(b,tr,True).Shape(),disk(x0,y0,w/2),disk(x1,y1,w/2)])
holes=[p for p in g['pads'] if p['drill_mm'][0]>0];voids=union([disk(*p['xy_mm'],p['drill_mm'][0]/2,-1,3) for p in holes])
def analyze(data):
    geoms={};detail={}
    nets={p['net'] for p in data['pads'] if p['number']}
    for n in nets:
        pads=[p for p in data['pads'] if p['net']==n and p['number']]
        shapes=[disk(*p['xy_mm'],p['size_mm'][0]/2) for p in pads if 'B.Cu' in p['copper_layers']]
        shapes +=[capsule(t) for t in data['tracks'] if t['net']==n and t['layer']=='B.Cu']
        body=op(BRepAlgoAPI_Cut,union(shapes),voids);geoms[n]=body
        detail[n]=dict(connected_solids=solids(body),copper_plan_area_mm2=vol(body),valid=BRepCheck_Analyzer(body).IsValid(),physical_endpoints=len(pads),drilled_void_intersection_mm2=vol(op(BRepAlgoAPI_Common,body,voids)))
    keys=sorted(nets);short=vol(op(BRepAlgoAPI_Common,geoms[keys[0]],geoms[keys[1]]))
    gap=BRepExtrema_DistShapeShape(geoms[keys[0]],geoms[keys[1]]);gap.Perform();assert gap.IsDone()
    minimum_gap=gap.Value()
    passed=len(nets)==2 and short<1e-7 and minimum_gap>1e-6 and all(x['connected_solids']==1 and x['valid'] and x['physical_endpoints']==2 and x['drilled_void_intersection_mm2']<1e-7 for x in detail.values())
    return dict(passed=passed,nets=detail,short_area_mm2=short,minimum_net_gap_mm=minimum_gap,separation_test_tolerance_mm=1e-6,separation_scope='Geometric separation only; not creepage/clearance or dielectric qualification')
baseline=analyze(g);assert baseline['passed']
regression=[]
def inject(label,x):
    r=analyze(x);regression.append(dict(name=label,rejected=not r['passed'],result=r));assert not r['passed'],label
x=copy.deepcopy(g);x['tracks']=[];inject('all_traces_removed_same_pad_numbers',x)
for net in sorted(baseline['nets']):
    x=copy.deepcopy(g);x['tracks']=[t for t in x['tracks'] if not (t['net']==net and t['start_mm'][1]==104 and t['end_mm'][1]==114)];inject('missing_vertical_segment_'+net,x)
x=copy.deepcopy(g);x['tracks'].append(dict(start_mm=[95,100],end_mm=[105,100],width_mm=1,layer='B.Cu',net='WP10_PRECHARGED_PLUS'));inject('physical_positive_return_bridge',x)
x=copy.deepcopy(g);x['tracks'].append(dict(start_mm=[95,100],end_mm=[102.5,100],width_mm=1,layer='B.Cu',net='WP10_PRECHARGED_PLUS'));inject('zero_area_tangent_copper_contact',x)
checks=[]
def ck(n,v,**kw):checks.append(dict(name=n,passed=bool(v),**kw))
front_pads=[p for p in g['pads'] if p['number'] and 'F.Cu' in p['copper_layers']]
ck('front_copper_only_two_outboard_wire_annuli',len(front_pads)==2 and {tuple(p['xy_mm']) for p in front_pads}=={(86,114),(114,114)} and all(p['size_mm']==[3.5,3.5] and p['drill_mm']==[1.8,1.8] and p['copper_layers']==['F.Cu','B.Cu'] for p in front_pads) and all(t['layer']=='B.Cu' for t in g['tracks']) and g['zone_count']==0)
expected_edges={tuple(sorted([a,b])) for a,b in [((75,76),(125,76)),((125,76),(125,124)),((125,124),(75,124)),((75,124),(75,76))]}
actual_edges={tuple(sorted([tuple(e['start_mm']),tuple(e['end_mm'])])) for e in g['edges']}
ck('native_board_outline_50x48_and_placement',actual_edges==expected_edges)
ck('two_real_wire_PTH_and_six_NPTH',len(holes)==8 and sum(p['type']==g['pad_type_values']['NPTH'] for p in holes)==6 and all(p['type']==g['pad_type_values']['PTH'] and p['number'] in ['1','2'] for p in front_pads))
ck('native_stackup_two_70um_faces_readback',s['layers_mm']==d['native_stackup_mm'] and s['layers_mm']['B.Cu']==.07 and s['layers_mm']['F.Cu']==.07 and abs(sum(s['layers_mm'].values())-1.6)<1e-12)
origin=d['pcb_origin_xy_mm']
for t in d['terminal_features']:
    xy=[t['local_xy_mm'][i]+origin[i] for i in range(2)]
    pp=[p for p in g['pads'] if p['number']==t['logical_pin'] and p['xy_mm']==xy]
    hh=[p for p in holes if p['xy_mm']==xy]
    ck(t['id']+'_physical_copper_and_hole',len(pp)==len(hh)==1 and pp[0]['net']==t['native_net'] and pp[0]['size_mm']==[3.5,3.5] and hh[0]['drill_mm']==[t['drill_mm']]*2)
    if t['id'].startswith('WIRE'):
        side=math.hypot(*t['local_xy_mm'])-15.5-1.75;window=16.5-max(map(abs,t['local_xy_mm']))-1.75
        ck(t['id']+'_front_pad_side_spacing',side>=2 and t['drill_type']=='PTH',nominal_mm=side,tolerances_included=False)
        ck(t['id']+'_pad_only_carrier_window',window>0,nominal_mm=window,tolerances_included=False)
        # The 4 mm trace end cap extends 0.25 mm beyond the 3.5 mm pad.
        # This is the WIRE terminal end envelope, not the entire routed trace.
        ck(t['id']+'_copper_end_envelope_side_spacing',side-.25>=2,nominal_mm=side-.25,tolerances_included=False)
        ck(t['id']+'_copper_end_envelope_carrier_window',window-.25>0,nominal_mm=window-.25,tolerances_included=False)
        ck(t['id']+'_bare_wire_nominal_fit',t['drill_mm']>d['wire']['max_bare_D_mm'],diametral_clearance_mm=t['drill_mm']-d['wire']['max_bare_D_mm'],tinning_and_tolerance_qualified=False)
ck('five_trace_faults_rejected',len(regression)==5 and all(r['rejected'] for r in regression))
# V19 changes material surfaces as well as holes. The old two-cylinder-only
# STEP delta is inapplicable. This circuit audit grants no STEP/contact credit.
from c203_surface_source_contract_v19 import validate_profile
validate_profile(read('mechanical/C203_SURFACE_PROFILE_V19.json'))
ck('nominal_surface_profile_matches_native_source',True)
lengths={n:sum(math.dist(t['start_mm'],t['end_mm']) for t in g['tracks'] if t['net']==n) for n in baseline['nets']}
R={n:1.724e-5*L/(4*.07) for n,L in lengths.items()}
inputs=['tools/check_cap_terminal_copper.py','tools/cap_terminal_native.py','results/CAP_TERMINAL_NATIVE_GEOMETRY.json','results/CAP_TERMINAL_STACKUP.json','power/CAP_TERMINAL_DEFINITION.json',d['board'],'ecad/wp10_system.xml']
inputs += ['mechanical/C203_SURFACE_PROFILE_V19.json','tools/c203_surface_source_contract_v19.py']
out=dict(schema='WP10_C203_PHYSICAL_COPPER_AUDIT_V19_WIRE_PTH',passed=all(c['passed'] for c in checks),checks=checks,check_count=len(checks),baseline=baseline,fault_injections=regression,
    trace_centerline_lengths_mm=lengths,uniform_trace_R20_ohm=R,uniform_trace_pair_heat_at2p4A_W=sum(R.values())*2.4**2,
    resistance_scope='Nominal uniform copper trace-only screen, rho20=1.724e-8 ohm*m; excludes annulus spreading, solder/contact, lead/wire resistance and actual ripple spectrum. Not installed temperature or a main-bus current rating.',
    STEP_surface_profile_checked=False,required_STEP_contact_evidence='results/CAP_HARNESS_EXACT_V19.json',installed_wire_length_mm=None,installed_loop_inductance_H=None,PCB_manufacturing_DRC_clean=False,whole_design_complete=False,inputs={p:sha(p) for p in inputs})
dump('results/CAP_TERMINAL_COPPER_AUDIT.json',out);print(json.dumps(dict(passed=out['passed'],checks=len(checks),regressions=len(regression),trace_mm=lengths,R20_trace_ohm=R)));assert out['passed']
