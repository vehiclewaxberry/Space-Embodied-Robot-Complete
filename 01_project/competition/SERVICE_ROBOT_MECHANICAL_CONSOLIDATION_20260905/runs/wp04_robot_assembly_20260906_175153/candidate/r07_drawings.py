"""Final STEP face projections, six reference views. No manufacturing release."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from candidate_context import WP02
sys.path.insert(0,str(WP02/'runtime_deps'))
from build123d import import_step
from cadgen import flatten
from shapely.affinity import translate
import ezdxf
H=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gen_dxf():
    step=H/'servicer_structure_service.step';root=import_step(step);shapes={}
    def visit(n):
        if n.children:
            for child in n.children:visit(child)
        else:shapes[n.label]=type(n)(n.wrapped).located(n.global_location)
    visit(root)
    views=[
        ('R07_upper_cap_20_1','z',1,116.15,('X','Y'),['Top bridge clamp; thickness 3','Pillar axis X20,Y94.15 / rail axis X15,Y107.15','2 x D4.5; global S coordinates']),
        ('RB_lower_spacer_0','z',-1,-101.15,('X','Y'),['Extended lower spacer; thickness 3','Pillar X20,Y-94.15 / rail X15,Y-107.15','Outer wing 12 x 12; inner leg 14 x 14']),
        ('hold_roof_lug_0_94_15','z',1,118.15,('X','Y'),['Retention lug / integral rail foot','Inner block 22 x 14 x 12; outer foot 22 x 12 x 5','Axes X-115,Y94.15 / X-118,Y107.15']),
        ('hold_pivot_clevis_0','z',-1,118.15,('X','Y'),['Foot underside; 2 x D4.5 through','Head counterbores D8, floor Z120.65, opening Z125.15','Remaining floor 2.5; strength UNKNOWN']),
        ('rear_launch_bulkhead','x',-1,-189,('Y','Z'),['Internal bulkhead interface; thickness 6','4 x D4.5 at Y/Z +/-107.15','Not a provider separation or deployment ICD']),
        ('shear_web_1','y',1,103.15,('X','Z'),['Shear web with lower edge assembly reliefs','Relief centers X15,165; width12.5; top Z-97.9','R01 closed hole patterns retained'])]
    doc=ezdxf.new('R2010');doc.units=ezdxf.units.MM
    for n,col in [('GEOMETRY',7),('DIMENSIONS',2),('NOTES',3)]:doc.layers.new(n,dxfattribs={'color':col})
    m=doc.modelspace();records=[]
    for i,(name,axis,sign,coord,axes,notes) in enumerate(views):
        faces=flatten.planar_faces(shapes[name],normal_axis=axis,normal_sign=sign,coordinate_axis=axis,coordinate=coord)
        if not faces:raise ValueError('Missing source face '+name)
        g=flatten.union_projected_faces([(faces,lambda p,aa=axes:(getattr(p,aa[0]),getattr(p,aa[1])))])
        if g.is_empty or not g.is_valid:raise ValueError('Invalid face '+name)
        x0,y0,x1,y1=g.bounds;ox=(i%3)*430-x0;oy=-(i//3)*400-y0
        flatten.add_shapely_geometry(m,translate(g,ox,oy),layer='GEOMETRY')
        for p1,p2,base,angle in [((x0+ox,y0+oy),(x1+ox,y0+oy),(ox,y0+oy-12),0),((x1+ox,y0+oy),(x1+ox,y1+oy),(x1+ox+12,oy),90)]:
            d=m.add_linear_dim(base=base,p1=p1,p2=p2,angle=angle,dimstyle='EZDXF',override={'dimtxt':2.5,'dimasz':1.5,'dimdec':3},dxfattribs={'layer':'DIMENSIONS'});d.render()
        for j,line in enumerate([name,'WP04 R07 | mm 1:1 | REFERENCE ONLY']+notes+['Material, threads, tolerances, preload: unqualified']):
            m.add_text(line,dxfattribs={'height':2.5,'layer':'NOTES','insert':(ox+x0,oy+y0-27-j*6)})
        records.append(dict(instance=name,source_face_coordinate_mm=coord,plane=axes,bounds_mm=list(g.bounds),area_mm2=g.area))
    (H/'results/R07_DRAWING_PROVENANCE.json').write_text(json.dumps(dict(step=str(step),step_sha256=sha(step),views=records,units='mm',manufacturing_release=False),indent=2),encoding='utf-8')
    return {'document':doc}
