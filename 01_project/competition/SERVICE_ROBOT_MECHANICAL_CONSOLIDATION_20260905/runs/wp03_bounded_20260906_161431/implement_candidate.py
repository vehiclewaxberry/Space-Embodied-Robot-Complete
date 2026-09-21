from pathlib import Path
import json
C=Path(__file__).resolve().parent/"candidate"
def edit(n,old,new):
    p=C/n;s=p.read_text(encoding="utf-8")
    if s.count(old)!=1:raise ValueError((n,"expected unique source",s.count(old),old[:60]))
    p.write_text(s.replace(old,new),encoding="utf-8")
p=C/"design_parameters.json";P=json.loads(p.read_text(encoding="utf-8"));P["configuration_id"]="WP03_SERVICER_ONBOARD_R1_R01_"+C.parent.name
P["r01"]=dict(revision="R01_CANDIDATE_1",deck_size_mm=[344,196.3,3],deck_z_mm=dict(lower=-99.65,upper=-10),notch_x_mm=[20,160],notch_y_mm=94.15,notch_cut_mm=[17,17,7],deck_hole_x_mm=[-150,-50,50,140],deck_hole_y_abs_mm=92.65,clearance_d_mm=3.4,angle_segments_x_mm=[[-167,11.5],[28.5,151.5]],web_hole_x_mm_by_segment=[[-130,-70],[60,130]],web_hole_z_mm=dict(lower=-94.15,upper=-18.5),hardware=dict(shank_d_mm=3,head_d_mm=5.5,head_h_mm=3,washer_od_mm=6,washer_id_mm=3.4,washer_h_mm=.5,nut_af_mm=5.5,nut_h_mm=2.4,nut_bore_mm=3,deck_underhead_mm=12,web_underhead_mm=10,socket_d_mm=2.6,socket_depth_mm=1.5),tools=dict(driver_d_mm=3,nut_tool_od_mm=8),material_grade=None,preload_N=None,manufacturing_tolerances=None)
p.write_text(json.dumps(P,ensure_ascii=False,indent=2),encoding="utf-8")
edit("root_structure.py","ORIGINAL=Path(__file__).resolve().parent.parent/'service_robot_wp02_20260905'","from candidate_context import WP02\nORIGINAL=WP02")
edit("kinematics.py","ROOT=Path(__file__).resolve().parents[2]","from candidate_context import PROJECT_ROOT\nROOT=PROJECT_ROOT")
edit("spacecraft_model.py","W1=HERE.parent/'service_robot_wp01_20260905';W2=HERE.parent/'service_robot_wp02_20260905'","from candidate_context import WP01 as W1, WP02 as W2\nimport r01_design as r01")
edit("spacecraft_model.py","web=Box(344,2,202.3)\n        for x in [-150,-90,-30,30,90,150]:\n            for z in [-94,94]:web=bore(web,3.4,6,(x+4,0,z),(0,1,0))","web=r01.web_shape(P,side)")
edit("spacecraft_model.py","d=Box(344,196.3,3)\n        for x in [20,160]:\n            for y in [-94.15,94.15]:d=d-box((17,17,7),(x,y,0))\n        for x in [-150,-50,50,150]:\n            for y in [-89,89]:d=bore(d,3.4,7,(x,y,0))","d=r01.deck_shape(P,deck)")
edit("spacecraft_model.py","angle=box((b-a,11,3),(0,-side*3.5,0))+box((b-a,3,14),(0,side*3.5,legz))","angle=r01.angle_shape(P,deck,side,k)")
edit("spacecraft_model.py","    # Launch adapter is an internal structure reservation: no invented provider bolt circle.","    for connection in r01.connections(P):\n        for name,shape in r01.hardware_parts(P,connection).items():\n            add(shape,name,parent='R01_FASTENERS',mount=connection['id'],rep='SIMPLIFIED_PROXY',density=None,color=DARK,basis='R01_NOMINAL_THREADLESS_HARDWARE_UNSELECTED_MASS_UNKNOWN')\n    # Launch adapter is an internal structure reservation: no invented provider bolt circle.")
edit("spacecraft_model.py","['design_parameters.json','root_structure.py','wing_kinematics.py','kinematics.py']","['design_parameters.json','root_structure.py','wing_kinematics.py','kinematics.py','r01_design.py','candidate_context.py']")
# Remove the partial-builder BOM mutation: final BOM has one guarded owner.
start="        with (HERE/'BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:"
s=(C/"spacecraft_model.py").read_text(encoding="utf-8");a=s.index(start);b=s.index("    return model,shapes,receipt",a);s=s[:a]+s[b:];(C/"spacecraft_model.py").write_text(s,encoding="utf-8")
edit("dynamics_handoff.py","ENGINEERING = HERE.parent","from candidate_context import ENGINEERING")
edit("integrate_checks.py","ROOT=HERE.parents[1]","from candidate_context import PROJECT_ROOT, WP02\nROOT=PROJECT_ROOT")
edit("integrate_checks.py","MOTION_PATH=HERE.parent/'service_robot_wp02_20260905/motion_analysis.py'","MOTION_PATH=WP02/'motion_analysis.py'")
print("Candidate isolated resolver and R01 generator integrated.")

