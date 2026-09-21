from pathlib import Path
import sys,json,importlib.util,hashlib
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('battery_check_diagnostic',R/'tools/check_battery_mount.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
c=m.read(R/'inputs/BATTERY_MOUNT_CONTRACT.json');em=m.read(R/'results/battery_mount/EMISSION.json')
gmod=m.load_helper(c['geometry_reader']) if hasattr(m,'load_helper') else None
if gmod is None:
    s=importlib.util.spec_from_file_location('wp09_diag_reader',c['geometry_reader']);gmod=importlib.util.module_from_spec(s);s.loader.exec_module(gmod)
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cone
parts={k:dict(path=em['parts'][k]['path'],sha256=em['parts'][k]['sha256'],T_S_local=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]) for k in ['adapter_battery','WP09_BAT_-152_-78_screw']}
g=gmod.Geometry(dict(parts=parts,tolerances=c['acceptance']),{})
from build123d import import_step
g.import_step=import_step
s=importlib.util.spec_from_file_location('battery_diag_bearing',Path(c['geometry_reader']).with_name('check_bearing_faces.py'));bearing=importlib.util.module_from_spec(s);s.loader.exec_module(bearing);kernel=bearing._kernel()
rows={}
for name in parts:
    rows[name]=[]
    for f in g.load(name).faces():
        surf=BRepAdaptor_Surface(f.wrapped,True)
        if surf.GetType()!=GeomAbs_Cone:continue
        con=surf.Cone();b=f.bounding_box()
        rows[name].append(dict(apex=list(con.Apex().Coord()),axis=list(con.Axis().Direction().Coord()),location=list(con.Location().Coord()),semiangle=con.SemiAngle(),ref_radius=con.RefRadius(),bbox=[list(b.min),list(b.max)],bearing_bbox=bearing._bbox(f.wrapped,kernel),area=f.area))
out=R/'results/BATTERY_CONE_DIAGNOSTIC.json';assert not out.exists();out.write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(rows))
