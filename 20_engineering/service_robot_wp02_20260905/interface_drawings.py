"""Actual part-face projections + parametric interface dimensions, not shop drawings."""
from pathlib import Path
import json,html,sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'runtime_deps'))
import ezdxf
from shapely.affinity import translate
from parts_model import build,P,R,G,C,HERE
from cadgen import flatten
SHEETS=[
 ('WP01-RB-BRIDGE-R2','根部承载桥 / Roof bearing bridge',3.,['170 x 202.3 x 6 mm','Datum A: bottom; B: X centerline; C: Y centerline','4 x D6.6 @ local (+/-70,+/-70)','4 x D4.5 @ local (+/-70,+/-94.15): pillar tie rods','8 x D12 access @ R62.5, 22.5 + k45 deg','Center D44; M5 nuts fit inside access pockets','Frame A0 z=125.150; bearing z=127.555 mm']),
 ('WP01-SA-ADJUSTABLE-SHOE-R2','A 鞍座 / Primary saddle shoe',4.,['24 x 90 x 8 mm; 2 x D6.6 @ (0,+/-30)','Adjustment Z +/-8; independent release drop 30 mm','Local pad x=0; centers y=+/-12 mm','Pad footprint 4 x 8 each; min thickness 3 mm','STL tangent: max sampled gap 0.125863 mm','No preload/allowable pressure has been specified']),
 ('WP01-SB-ADJUSTABLE-SHOE-R2','B 浮动鞍座 / Floating saddle shoe',4.,['24 x 90 x 8 mm; 2 x slots 14.6 x 6.6','Slot centers (0,+/-30); X float +/-4 mm','Pad center x=+5 mm from station x=-40','Adjustment Z +/-8; independent release drop 30 mm','Pads contact a sampled planar patch on link2','Friction and shell stiffness needed for load sharing']),
 ('WP01-HR-KEEPER-CROSSBAR-R2','保持横梁 / Retracting keeper',4.,['18 x 118 x 8 mm; 2 x D4.5 @ (0,+/-45)','Center D10.6; upper contact pad retracts +Z12','Keeper held bottom: A509.513134 / B552.814321','Upper contact is on folded link3, not link2','Y travel 180; lock pin withdrawal 48 mm','Independent holding support required during release']),
 ('WP01-HB-SPLIT-CLAMP-LOWER-R2','线夹下半体 / Split clamp lower',3.,['26 x 14 x 6 mm; 2 x D3.4 @ (+/-9,0)','Proxy cable groove D6 along Y; interchangeable halves','Actual OD / squeeze / bend radius: TBD','OEM XT30 2+2 length does not define free span','Root clamp anchor S=[90,-140,110] mm','No connector load rating or clamp torque selected'])
]
def geometry_rows():
    _,_,parts=build('held');rows=[]
    for pn,title,z,notes in SHEETS:
        shp=parts[pn][0]
        faces=flatten.planar_faces(shp,normal_axis='z',normal_sign=1,coordinate_axis='z',coordinate=z)
        geometry=flatten.union_projected_faces([(faces,lambda v:(v.X,v.Y))])
        rows.append((pn,title,geometry,notes,shp))
    return rows
def gen_dxf():
    doc=ezdxf.new('R2010');doc.units=ezdxf.units.MM
    for name,color in [('REFERENCE_GEOMETRY',7),('REFERENCE_DIMENSIONS',2),('REFERENCE_NOTES',3),('REFERENCE_DATUMS',4)]:doc.layers.new(name,dxfattribs={'color':color})
    msp=doc.modelspace()
    for i,(pn,title,geo,notes,shape) in enumerate(geometry_rows()):
        ox=(i%3)*350;oy=-(i//3)*420
        flatten.add_shapely_geometry(msp,translate(geo,ox,oy),layer='REFERENCE_GEOMETRY')
        x0,y0,x1,y1=geo.bounds
        for pt1,pt2,base,angle in [((x0+ox,y0+oy),(x1+ox,y0+oy),(ox,y0+oy-18),0),((x1+ox,y0+oy),(x1+ox,y1+oy),(x1+ox+18,oy),90)]:
            dim=msp.add_linear_dim(base=base,p1=pt1,p2=pt2,angle=angle,dimstyle='EZDXF',override={'dimtxt':3,'dimasz':2,'dimdec':3},dxfattribs={'layer':'REFERENCE_DIMENSIONS'});dim.render()
        msp.add_line((ox-10,oy),(ox+10,oy),dxfattribs={'layer':'REFERENCE_DATUMS'})
        msp.add_line((ox,oy-10),(ox,oy+10),dxfattribs={'layer':'REFERENCE_DATUMS'})
        msp.add_text(pn,dxfattribs={'height':5,'layer':'REFERENCE_NOTES','insert':(ox+x0,oy+y1+20)})
        for j,line in enumerate(['NOT_FOR_MANUFACTURE | mm | WP02 R1']+notes):
            msp.add_text(line,dxfattribs={'height':3,'layer':'REFERENCE_NOTES','insert':(ox-110,oy+y0-38-j*7)})
    return {'document':doc}
def write_html():
    cards=[];receipts=[]
    for pn,title,geo,notes,shape in geometry_rows():
        x0,y0,x1,y1=geo.bounds;w=x1-x0;h=y1-y0
        path=geo.svg(scale_factor=.35,fill_color='#e0edf5').replace('opacity="0.6"','opacity="1"')
        svg=f'<svg viewBox="{x0-35} {-y1-30} {w+70} {h+60}" xmlns="http://www.w3.org/2000/svg"><g transform="scale(1,-1)">{path}</g><g stroke="#64748b" fill="none" stroke-width="0.3"><path d="M{x0},{-y0+12} H{x1} M{x0},{-y0+7} v10 M{x1},{-y0+7} v10"/><path d="M{x1+12},{-y1} V{-y0} M{x1+7},{-y1} h10 M{x1+7},{-y0} h10"/></g><g fill="#0f172a" font-family="Arial" font-size="6"><text x="{(x0+x1)/2}" y="{-y0+21}" text-anchor="middle">{w:.3f} mm</text><text x="{x1+20}" y="{-(y0+y1)/2}" transform="rotate(-90 {x1+20} {-(y0+y1)/2})" text-anchor="middle">{h:.3f} mm</text></g></svg>'
        cards.append(f'<section><h2>{html.escape(title)}</h2><p class="pn">{pn}</p><div class="drawing">{svg}</div><ul>'+''.join(f'<li>{html.escape(n)}</li>' for n in notes)+'</ul><footer>NOT_FOR_MANUFACTURE · 几何候选 / 材料、配合、公差、紧固力矩待定</footer></section>')
        receipts.append({'part_number':pn,'top_face_z_mm':next(s[2] for s in SHEETS if s[0]==pn),'projected_bounds_mm':geo.bounds,'area_mm2':geo.area,'geometry_valid':geo.is_valid,'source':'parts_model.py generated BRep top faces; wire sampling maximum 0.25 mm','notes':notes})
    text='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>WP02 接口尺寸图册</title><style>body{margin:0;background:#e9eef4;font-family:"Microsoft YaHei",Arial;color:#15263c}header{padding:35px 6%;background:#153450;color:white}h1{margin:0 0 12px}header p{max-width:1000px;line-height:1.7}main{max-width:1400px;margin:26px auto;display:grid;grid-template-columns:repeat(2,1fr);gap:22px}section{background:white;padding:25px;border-radius:10px;break-inside:avoid}h2{font-size:21px;margin:0}.pn{color:#536a82;font-family:monospace}.drawing{height:320px}.drawing svg{width:100%;height:100%}li{line-height:1.8;font-size:14px}footer{border-top:1px solid #d5dde6;padding-top:15px;color:#9a3412;font-size:12px}@media print{body{background:white}main{display:block}section{page-break-after:always;min-height:85vh}.drawing{height:48vh}header{background:white;color:black}}</style><header><h1>WP02 关键组合件接口尺寸图册</h1><p>直接投影自本轮生成的零件 BRep。所有尺寸单位 mm；2D投影轮廓采用不大于0.25 mm弧长采样，是接口评审图，不是公差完备的加工图。根部孔系与实物、线缆端型与装配方向仍需注册；TBD不得读作零。</p></header><main>'''+''.join(cards)+'</main></html>'
    (HERE/'drawings/INTERFACE_DRAWINGS.html').write_text(text,encoding='utf-8')
    (HERE/'results/DRAWING_PROJECTIONS.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
    print('Wrote',len(receipts),'source-derived interface sheets')
if __name__=='__main__':write_html()
