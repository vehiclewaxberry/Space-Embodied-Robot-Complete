from pathlib import Path
import sys,json,hashlib,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
gp=R.parent/'wp06_side_joint_20260907_0233/tools/verify_joint_geometry.py'
s=importlib.util.spec_from_file_location('source_geometry',gp);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
p=R/'inputs/catalog/iso10642_socket_countersunk_screw_m3x10.step'
g=m.Geometry({'parts':{'screw':{'path':str(p),'T_S_local':I}},'tolerances':{'linear_mm':1e-5,'volume_mm3':1e-5,'integration_eps':1e-7}}, {})
from build123d import import_step
g.import_step=import_step
a=g.load('screw');faces=[]
for f in a.faces():
    b=f.bounding_box()
    faces.append(dict(type=str(f.geom_type),area=f.area,center=list(f.center()),min=list(b.min),max=list(b.max)))
out=R/'results/CATALOGUE_M3_CSK_FACTS.json'
assert not out.exists()
out.write_text(json.dumps(dict(source=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),facts=g.facts(a),faces=faces),indent=2),encoding='utf-8')
print(json.dumps(dict(facts=g.facts(a),faces=[f for f in faces if 'CONE' in f['type'] or 'CYLINDER' in f['type'] or f['min'][2]==f['max'][2]])))
