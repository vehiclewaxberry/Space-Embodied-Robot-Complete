"""Candidate interface drawings projected from actual WP03 BRep planar faces."""
from pathlib import Path
import sys,json,hashlib,functools
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'service_robot_wp02_20260905/runtime_deps'))
from spacecraft_model import build,HERE
from cadgen import flatten
import ezdxf
from shapely.affinity import translate

SHEETS=[
 ('upper_equipment_deck','上层设备甲板','z',-8.5,('X','Y'),[
  '344 x 196.3 x 3 mm; global S coordinates shown.',
  '4 edge reliefs: 17 wide x12.5 deep (17-square cutter).',
  'D3.4 drill centers: X-150/-50/50/150, Y+/-89.',
  '6 closed holes; X150 pair breaks into pillar reliefs.',
  'X150 bearing land / matching fastener support: TBD.',
  'Datum A: underside Z-11.5; top Z-8.5.',
  'Edge angles / adapters: final joint details TBD.']),
 ('shear_web_1','正 Y 侧剪力板','y',103.15,('X','Z'),[
  '344 x 202.3 x 2 mm; plane Y=103.15.',
  '12 x D3.4 @ X-146/-86/-26/34/94/154, Z+/-94.',
  'Clip rail screws offset X by 4 mm from web screws.',
  'Datum A: inner face Y101.15; B: X=0; C: Z=0.',
  'Shear transfer / bolt preload / buckling: TBD.']),
 ('rear_launch_bulkhead','后端发射接口承力框','x',-183,('Y','Z'),[
  '226.3 x 226.3 x 6 mm; inner window 158 square.',
  '4 x D8 clearance @ Y/Z +/-107.15.',
  'Datum A: front face X-183; rear face X-189.',
  'Existing end-frame fastener head access only.',
  'D120 x 20 reservation is NOT a provider bolt pattern.',
  'Attachment / separator / launch loads remain TBD.']),
 ('hold_crossbeam_0','随星保持器屋顶承载横梁','z',106.15,('X','Y'),[
  '22 x 202.3 x 10 mm; station A global X=-115.',
  '2 x D4.5 @ X=-115, Y+/-94.15.',
  'Station B shares shape, global X=-40.',
  'Datum A: underside Z96.15; top Z106.15.',
  'Load enters roof longerons through physical lugs.',
  'Fastener retention / load capacity: TBD.']),
 ('hold_pivot_clevis_0','随星保持器根部转轴叉座','x',-100,('Y','Z'),[
  '30 x 26 x 30 mm; station A X=-115, Y=-99.',
  'Pivot axis +X at Y=-99, Z=135.15; D8.4 bore.',
  '14 mm fork opening; mating mast boss 12 mm.',
  'Pin D8 x 34; axial capture method remains TBD.',
  'Pin26 -> cap100deg -> shoe80 -> mast90deg.',
  'Sequence is sampled geometry, not release qualification.']),
 ('radiator_spreader','电池区导热扩散板','z',-112.15,('X','Y'),[
  '110 x 80 x 2 mm; center S[-115,0,-113.15].',
  '4 x D3.4 @ local X+/-48, Y+/-33.',
  'Datum A: lower surface Z-114.15.',
  'Thermal link / contact conductance / radiator area TBD.',
  'No orbit heat balance or temperature margin claimed.'])
]

@functools.lru_cache(maxsize=1)
def geometry_rows():
    _,shapes,_=build('parking',include_arm=False)
    rows=[]
    for name,title,axis,coordinate,axes,notes in SHEETS:
        shape=shapes[name]
        faces=flatten.planar_faces(shape,normal_axis=axis,normal_sign=1,coordinate_axis=axis,coordinate=coordinate)
        geo=flatten.union_projected_faces([(faces,lambda v,aa=axes:(getattr(v,aa[0]),getattr(v,aa[1])))])
        if geo.is_empty or not geo.is_valid:raise ValueError('Invalid projection '+name)
        rows.append((name,title,geo,axes,notes))
    return rows

def gen_dxf():
    doc=ezdxf.new('R2010');doc.units=ezdxf.units.MM
    for name,color in [('REFERENCE_GEOMETRY',7),('REFERENCE_DIMENSIONS',2),('REFERENCE_NOTES',3)]:doc.layers.new(name,dxfattribs={'color':color})
    m=doc.modelspace()
    for i,(name,title,geo,axes,notes) in enumerate(geometry_rows()):
        x0,y0,x1,y1=geo.bounds;ox=(i%3)*480-x0;oy=-(i//3)*530-y0
        flatten.add_shapely_geometry(m,translate(geo,ox,oy),layer='REFERENCE_GEOMETRY')
        for p1,p2,base,angle in [((x0+ox,y0+oy),(x1+ox,y0+oy),(ox,y0+oy-20),0),((x1+ox,y0+oy),(x1+ox,y1+oy),(x1+ox+20,oy),90)]:
            d=m.add_linear_dim(base=base,p1=p1,p2=p2,angle=angle,dimstyle='EZDXF',override={'dimtxt':3,'dimasz':2,'dimdec':3},dxfattribs={'layer':'REFERENCE_DIMENSIONS'});d.render()
        for j,line in enumerate([name,'WP03 R1 | mm | NOT_FOR_MANUFACTURE']+notes):
            m.add_text(line,dxfattribs={'height':3,'layer':'REFERENCE_NOTES','insert':(x0+ox,y0+oy-42-j*8)})
    return {'document':doc}

def render_interfaces():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.font_manager import FontProperties
    font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc');records=[]
    with PdfPages(HERE/'drawings/WP03_INTERFACE_DRAWINGS.pdf') as pdf:
        for i,(name,title,geo,axes,notes) in enumerate(geometry_rows(),1):
            fig=plt.figure(figsize=(11.7,8.3),facecolor='white')
            fig.text(.06,.93,title,fontproperties=font,fontsize=19,color='#183951');fig.text(.06,.875,name,fontsize=11,color='#51647a')
            ax=fig.add_axes([.07,.23,.46,.6]);ax.set_aspect('equal');ax.set_axis_off()
            polys=[geo] if geo.geom_type=='Polygon' else list(geo.geoms)
            for p in polys:
                xy=list(p.exterior.coords);ax.fill(*zip(*xy),facecolor='#dfeaf0',edgecolor='#102d40',lw=1)
                for ring in p.interiors:ax.fill(*zip(*ring.coords),facecolor='white',edgecolor='#102d40',lw=.8)
            x0,y0,x1,y1=geo.bounds;w=x1-x0;h=y1-y0;off=max(w,h)*.13
            ax.annotate('',(x0,y0-off),(x1,y0-off),arrowprops=dict(arrowstyle='<->',lw=.8))
            ax.text((x0+x1)/2,y0-off*1.4,f'{w:.3f} mm ({axes[0]})',ha='center',va='top',fontsize=10)
            ax.annotate('',(x1+off,y0),(x1+off,y1),arrowprops=dict(arrowstyle='<->',lw=.8))
            ax.text(x1+off*1.4,(y0+y1)/2,f'{h:.3f} mm ({axes[1]})',rotation=90,ha='center',fontsize=10)
            for x in [x0,x1]:ax.plot([x,x],[y0,y0-off*1.2],color='#64748b',lw=.6)
            for y in [y0,y1]:ax.plot([x1,x1+off*1.2],[y,y],color='#64748b',lw=.6)
            ax.set_xlim(x0-off,x1+off*3);ax.set_ylim(y0-off*2.5,y1+off)
            fig.text(.57,.79,'INTERFACE / DATUM NOTES',fontsize=12,weight='bold',color='#183951')
            for j,line in enumerate(notes):fig.text(.57,.73-j*.064,line,fontsize=8.6,color='#263a4f')
            fig.text(.06,.16,'ACTUAL BREP FACE PROJECTION | GLOBAL S COORDINATES | mm',fontsize=10,color='#183951')
            fig.text(.06,.12,'NOT_FOR_MANUFACTURE',fontsize=13,weight='bold',color='#aa3a16')
            fig.text(.06,.073,'Candidate dimensions. Material, fit, tolerances, inserts, preload and as-built registration remain unverified.\nCurves sampled <=0.25 mm by CAD flatten; exact holes remain in STEP. This is not a manufacturing drawing.',fontsize=8,color='#596a7c')
            fig.text(.91,.045,f'{i:02d}/{len(SHEETS):02d}',fontsize=9)
            pdf.savefig(fig);fig.savefig(HERE/'drawings'/f'{i:02d}_{name}.png',dpi=140);plt.close(fig)
            records.append(dict(id=name,bounds_mm=geo.bounds,area_mm2=geo.area,valid=geo.is_valid,projection_axes=axes,notes=notes))
    (HERE/'results/DRAWING_PROJECTIONS.json').write_text(json.dumps({'source_sha256':hashlib.sha256((HERE/'spacecraft_model.py').read_bytes()).hexdigest(),'sheets':records},indent=2),encoding='utf-8')
    print('Six BRep-derived interface sheets exported')

if __name__=='__main__':render_interfaces()
