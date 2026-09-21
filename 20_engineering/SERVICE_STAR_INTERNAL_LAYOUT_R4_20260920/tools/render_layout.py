"""Render only checked CAD solids. Colors are review markings, not material assignments."""
from geometry import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import plotly.graph_objects as go
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

F=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
def mesh(s):
    BRepMesh_IncrementalMesh(s,.2,False,.22,False).Perform();ex=TopExp_Explorer(s,TopAbs_FACE);out=[]
    while ex.More():
        face=TopoDS.Face_s(ex.Current());loc=TopLoc_Location();tri=BRep_Tool.Triangulation_s(face,loc)
        if tri is not None:
            v=np.array([[p.X(),p.Y(),p.Z()] for p in [tri.Node(i).Transformed(loc.Transformation()) for i in range(1,tri.NbNodes()+1)]])
            out.extend(v[np.array(tri.Triangle(i).Get())-1] for i in range(1,tri.NbTriangles()+1))
        ex.Next()
    return np.array(out)
def near(a,b):
    x=BRepExtrema_DistShapeShape(a,b);x.Perform();assert x.IsDone()
    return {'mm':x.Value(),'points':[[p.X(),p.Y(),p.Z()] for p in [x.PointOnShape1(1),x.PointOnShape2(1)]]}

mount=read(D/'inputs/MOUNT_LAYOUT.json');passage=read(D/'inputs/PASSAGE_LAYOUT.json');check=read(D/'results/INCREMENT_STATIC_CHECK.json');assert check['valid']
current={r['id']:r for r in state_rows()['service']};current.update({r['id']:r for r in mount['replacements']+passage['replacements']+mount['additions']})
interface=source(current['equipment_arm_drive']);e=TopExp_Explorer(interface,TopAbs_SOLID);children=[]
while e.More():children.append(e.Current());e.Next()
assert len(children)==8
pieces=[]
for i,s in enumerate(children):
    color,opacity=('#3d9d80',.8) if i==0 else (('#6eaf98',.1) if i==1 else (('#df9e30',1) if i>=6 else ('#4d7caa',.6)))
    pieces.append((['PCB 厚度占位','元件高度保留区（含工具避让）','预留插头 1','预留插头 2','预留插头 3','预留插头 4','功能连接通道 1','功能连接通道 2'][i],s,color,opacity))
clip=source(current['trunk_clip_standoff_-140']);terminal=source(current['connector_arm_drive'])
hardware=[(r['id'],source(r),'#9cabc0' if 'BOLT' in r['id'] else '#70899d',1) for r in mount['additions']]
crop=box(-139,-78,-16,-61,-19,1)
under=[('转接板（仅显示局部裁切）',common(source(current['adapter_arm_drive']),crop),'#758797',.22),
       ('设备层板（仅显示局部裁切）',common(source(current['upper_equipment_deck_B']),crop),'#a4b0bd',.12)]
route=source(passage['replacements'][0]);m3=source(current['WP01-MT-M3RB-REUSED']);root=source(current['ROOT_BUSH_LEFT'])
scenes=[
 {'title':'A  四点安装支撑已落入 CAD','note':'4 个贯穿孔 + 4 套支撑/紧固件；螺纹、预紧与强度待定','meshes':under+pieces+hardware,'view':(29,-116),'measurement':None},
 {'title':'B  接口线束到支架 2.00 mm','note':'原 0.50 mm → 2.00 mm；插头已避让前排螺钉','meshes':pieces+[('线夹支架',clip,'#bd6c48',.45),('原接口入口',terminal,'#74869a',.23)],'view':(65,-85),'measurement':near(interface,clip)},
 {'title':'C  释放路线到 M3RB 2.87 mm','note':'最近其他障碍 2.63 mm；OD4 / R14 为名义功能通道','meshes':[('R4 释放功能路线',route,'#df9e30',1),('M3RB',m3,'#557b9e',.35),('ROOT_BUSH_LEFT',root,'#7e879e',.48)],'view':(31,-72),'measurement':near(route,m3)}]
fig=plt.figure(figsize=(19,8.5),facecolor='#f3f6fa')
fig.text(.03,.95,'R4 内部布局  |  安装支撑与线束走廊',fontproperties=F,fontsize=25,color='#203a52')
fig.text(.03,.902,'实际 STEP 实体显示；服务 / 停放 / 释放三个固定状态完成本轮增量检查。',fontproperties=F,fontsize=12,color='#53697d')
cards=[];measures=[]
for n,sc in enumerate(scenes,1):
    ax=fig.add_subplot(1,3,n,projection='3d',computed_zorder=False);ax.set_facecolor('#f3f6fa');allv=[];plot=go.Figure()
    for name,s,color,opacity in sc['meshes']:
        triangles=mesh(s)
        if not len(triangles):continue
        v=triangles.reshape(-1,3);ix=np.arange(len(v)).reshape(-1,3);allv.append(v)
        ax.add_collection3d(Poly3DCollection(triangles,facecolors=color,edgecolors='none',alpha=opacity))
        plot.add_trace(go.Mesh3d(x=v[:,0],y=v[:,1],z=v[:,2],i=ix[:,0],j=ix[:,1],k=ix[:,2],color=color,opacity=opacity,
                      name=name,hovertemplate=name+'<extra></extra>',showlegend=True,flatshading=True))
    v=np.concatenate(allv);lo=v.min(0);hi=v.max(0);margin=np.maximum((hi-lo)*.05,2)
    ax.set_xlim(lo[0]-margin[0],hi[0]+margin[0]);ax.set_ylim(lo[1]-margin[1],hi[1]+margin[1]);ax.set_zlim(lo[2]-margin[2],hi[2]+margin[2]);ax.set_box_aspect(np.maximum(hi-lo,1));ax.view_init(*sc['view']);ax.set_axis_off()
    if sc['measurement']:
        mm=sc['measurement'];p=np.array(mm['points']);label=f"{mm['mm']:.2f} mm";measures.append(mm)
        ax.plot(*p.T,color='#b52170',lw=3,marker='o',markersize=3,zorder=50);ax.text(*p.mean(0),label,color='#b52170',fontsize=11)
        plot.add_trace(go.Scatter3d(x=p[:,0],y=p[:,1],z=p[:,2],mode='lines+markers+text',text=[label,''],textposition='top center',line=dict(color='#b52170',width=6),marker=dict(size=3),showlegend=False))
    ax.text2D(.01,.98,sc['title'],transform=ax.transAxes,fontproperties=F,fontsize=14,color='#203a52')
    ax.text2D(.01,.02,sc['note'],transform=ax.transAxes,fontproperties=F,fontsize=9.5,color='#53697d')
    plot.update_layout(height=660,margin=dict(l=0,r=0,b=0,t=10),paper_bgcolor='#f3f6fa',scene=dict(aspectmode='data',xaxis_title='X/mm',yaxis_title='Y/mm',zaxis_title='Z/mm'),legend=dict(orientation='h',y=-.05,font=dict(size=10)))
    cards.append('<section><h2>'+sc['title']+'</h2><p>'+sc['note']+'</p>'+plot.to_html(full_html=False,include_plotlyjs=(n==1),config={'responsive':True,'displaylogo':False})+'</section>')
fig.text(.03,.085,'名义间隙用于本轮 CAD 筛查；制造公差、线缆实物弯曲、振动/热变形与全运动扫掠仍待验证。',fontproperties=F,fontsize=12,color='#8d532b')
fig.text(.03,.04,'CF1 电源/热控模块尚未装入。预留 PCB 与功能线路不等同于已选型 PCBA、可制造线束或可上电系统。',fontproperties=F,fontsize=11,color='#53697d')
fig.subplots_adjust(left=.01,right=.99,top=.845,bottom=.155,wspace=.03)
png=D/'views/R4_INTERNAL_LAYOUT.png';fig.savefig(png,dpi=150);plt.close(fig)
html=D/'views/R4_INTERNAL_LAYOUT_VIEWER.html'
html.write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R4 内部布局</title><style>body{font:16px system-ui;background:#f3f6fa;color:#203a52;margin:18px}p{line-height:1.6}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:16px}section{min-width:0;border:1px solid #d4dce5;padding:8px;border-radius:8px}h2{font-size:18px}.note{background:white;border-left:4px solid #c58b2d;padding:14px}</style><h1>R4 内部装配布局</h1><p class="note">本轮新增四点支撑、20 件安装五金，并调整两处功能线束。三个固定状态增量检查通过。名义间隙：接口侧 2.00 mm；释放线路到 M3RB 2.87 mm；最近其他障碍 2.63 mm。此结果尚不覆盖全星全运动、制造公差及上电验收。CF1 未装入。</p><p>拖动旋转、滚轮缩放，点击图例可隐藏零件。A 图层板仅作局部显示裁切，实际 CAD 保留整板并增加贯穿孔；颜色仅为检查标记。</p><main>'+''.join(cards)+'</main><p>R1–R3 保持封存；R4 为本地固定姿态数字设计增量。两条释放逻辑分支共用功能走廊，未声明为两条已分隔实物电缆。</p></html>',encoding='utf-8')
write(D/'results/LAYOUT_VISUALIZATION.json',{'status':'PENDING_VISUAL_REVIEW','actual_STEP_geometry':True,'source_check_sha256':sha(D/'results/INCREMENT_STATIC_CHECK.json'),
    'material_colors_are_visual_only':True,'measurements':measures,'outputs':[{'path':str(p),'sha256':sha(p)} for p in [png,html]]})
print('Rendered',png,html)
