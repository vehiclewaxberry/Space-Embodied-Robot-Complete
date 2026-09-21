from pathlib import Path
import sys,json,copy,hashlib
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
import r07_design as r
H=Path(__file__).resolve().parent;p=H/'design_parameters.json';h=hashlib.sha256(p.read_bytes()).hexdigest()
P=json.loads(p.read_text(encoding='utf-8'));Q=copy.deepcopy(P);Q['r07']['left_rail_x_mm']=14
checks=[]
for lower in [False,True]:
    old=r.cap_shape(P,20,1,lower);new=r.cap_shape(Q,20,1,lower);z=-99.65 if lower else 114.65
    for x,old_void,new_void in [(17.2,True,False),(11.8,False,True)]:
        probe=r.cyl(.06,.2,(x,107.15,z));vo=abs((old&probe).volume);vn=abs((new&probe).volume)
        checks.append(dict(case=f'cap_lower{lower}_x{x}',pass_=(vo<1e-7)==old_void and (vn<1e-7)==new_void,old_overlap_mm3=vo,new_overlap_mm3=vn))
rail=r.box((354,12,12))-r.box((356,8,8))
old,_=r.modify_root(P,rail,'RB_longeron_1_1','rail',(0,107.15,107.15),None)
new,_=r.modify_root(Q,rail,'RB_longeron_1_1','rail',(0,107.15,107.15),None)
for x,ov,nv in [(17.2,True,False),(11.8,False,True)]:
    probe=r.cyl(.06,.2,(x,0,5));vo=abs((old&probe).volume);vn=abs((new&probe).volume)
    checks.append(dict(case=f'rail_x{x}',pass_=(vo<1e-7)==ov and (vn<1e-7)==nv,old_overlap_mm3=vo,new_overlap_mm3=vn))
cs=[c for c in r.connections(Q) if c['origin_mm'][0]==14]
checks.append(dict(case='four_rail_axes_and_hardware_follow',pass_=len(cs)==4 and all(abs(r.hardware(Q,c)[c['hardware']['screw']].bounding_box().center().X-14)<1e-7 for c in cs)))
checks.append(dict(case='source_parameter_file_unchanged',pass_=h==hashlib.sha256(p.read_bytes()).hexdigest()))
out=dict(status='PASS' if all(x['pass_'] for x in checks) else 'FAIL',parameter='r07.left_rail_x_mm',from_mm=15,to_mm=14,checks=checks,scope='Declared left root rail hole coordinates only; not complete-system parameterization',parameter_sha256=h)
(H/'results/R07_PARAMETER_PROPAGATION.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out));assert out['status']=='PASS'
