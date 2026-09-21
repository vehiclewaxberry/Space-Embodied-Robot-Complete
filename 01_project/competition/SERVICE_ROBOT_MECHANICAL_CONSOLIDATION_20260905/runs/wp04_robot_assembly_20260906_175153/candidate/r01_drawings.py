"""Interface review profiles projected from final STEP planar faces (mm)."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from candidate_context import WP02,HERE
sys.path.insert(0,str(WP02/'runtime_deps'))
from build123d import import_step
from cadgen import flatten
from shapely.affinity import translate
import ezdxf
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gen_dxf():
    path=HERE/'r01_local.step';contract=json.loads((HERE/'results/r01_connections.json').read_text(encoding='utf-8'))
    if sha(path)!=contract['step_sha256']:raise ValueError('Final STEP contract mismatch')
    shapes={}
    def visit(node):
        if node.children:
            for c in node.children:visit(c)
        else:shapes[node.label]=type(node)(node.wrapped).located(node.global_location)
    visit(import_step(path))
    sheets=[]
    for deck,z in [('lower',-99.65),('upper',-10)]:
        sheets.append((deck+'_equipment_deck','z',1,z+1.5,('X','Y'),['344 x 196.3 x 3 mm','8 x D3.4: X=-150,-50,50,140; Y=+/-92.65','4 edge reliefs 17 wide x 12.5 deep','Datum A underside Z='+str(z-1.5),'Hole locations shown in global frame S']+(['1 x D12 thermal clearance at X=-115,Y=0'] if deck=='lower' else [])))
        for k in [0,1]:
            name=f'{deck}_deck_angle_1_{k}'
            sheets.append((name+'_top','z',1,z-1.5,('X','Y'),['Section nominal thickness 3 mm','Deck-facing holes share deck axes','Source instance: '+name]))
            sheets.append((name+'_web','y',1,101.15,('X','Z'),['Web-facing holes D3.4','Source instance: '+name]+(['Extra D3.4 screw-tail relief at Z=-94','X=-146,-86,-26 or 34,94 by segment'] if deck=='lower' else [])))
    sheets.append(('shear_web_1','y',1,103.15,('X','Z'),['344 x 202.3 x 2 mm','New 8 x D3.4: X=-130,-70,60,130','New Z=-94.15 and -18.5','Existing 12 x D3.4 retained','Opposite web mirrors Y only']))
    doc=ezdxf.new('R2010');doc.units=ezdxf.units.MM
    for name,color in [('REFERENCE_GEOMETRY',7),('REFERENCE_DIMENSIONS',2),('REFERENCE_NOTES',3)]:doc.layers.new(name,dxfattribs={'color':color})
    m=doc.modelspace();rows=[]
    for i,(name,axis,sign,coordinate,axes,notes) in enumerate(sheets):
        source=name.removesuffix('_top').removesuffix('_web') if '_angle_' in name else name
        s=shapes[source]
        faces=flatten.planar_faces(s,normal_axis=axis,normal_sign=sign,coordinate_axis=axis,coordinate=coordinate)
        if not faces:raise ValueError('No final planar face '+name)
        g=flatten.union_projected_faces([(faces,lambda v,aa=axes:(getattr(v,aa[0]),getattr(v,aa[1])))])
        if g.is_empty or not g.is_valid:raise ValueError('Invalid face projection '+name)
        x0,y0,x1,y1=g.bounds;ox=i%3*480-x0;oy=-(i//3)*400-y0
        flatten.add_shapely_geometry(m,translate(g,ox,oy),layer='REFERENCE_GEOMETRY')
        for p1,p2,base,angle in [((x0+ox,y0+oy),(x1+ox,y0+oy),(ox,y0+oy-16),0),((x1+ox,y0+oy),(x1+ox,y1+oy),(x1+ox+16,oy),90)]:
            dim=m.add_linear_dim(base=base,p1=p1,p2=p2,angle=angle,dimstyle='EZDXF',override={'dimtxt':3,'dimasz':2,'dimdec':3},dxfattribs={'layer':'REFERENCE_DIMENSIONS'});dim.render()
        for j,line in enumerate([name,'R01 CANDIDATE | mm 1:1 | NOT FOR MANUFACTURE']+notes+['Material / tolerances / finish / preload: TBD']):
            m.add_text(line,dxfattribs={'height':3,'layer':'REFERENCE_NOTES','insert':(x0+ox,y0+oy-34-j*7)})
        rows.append(dict(view=name,instance=source,axis=axis,face_coordinate_mm=coordinate,projected_bounds_mm=list(g.bounds),profile_area_mm2=g.area))
    (HERE/'results/R01_DRAWING_PROVENANCE.json').write_text(json.dumps(dict(final_step=str(path),final_step_sha256=sha(path),contract_sha256=sha(HERE/'results/r01_connections.json'),views=rows,units='mm',manufacturing_release=False),indent=2),encoding='utf-8')
    return {'document':doc}
