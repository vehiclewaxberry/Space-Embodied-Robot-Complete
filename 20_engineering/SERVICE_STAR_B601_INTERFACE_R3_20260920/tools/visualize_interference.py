"""Evidence-bound interference/proximity viewer. Generates geometry, not illustrative CAD."""
from pathlib import Path
import json,hashlib,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE,TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.TopLoc import TopLoc_Location
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

D=Path(__file__).resolve().parents[1];ROOT=D.parents[1];R1=D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919';R2=D.parent/'SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919'
F=FontProperties(fname='C:/Windows/Fonts/msyh.ttc');LOCKS={}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,expected):
    p=Path(p);assert sha(p)==expected;LOCKS[str(p)]=expected
    r=STEPControl_Reader();assert r.ReadFile(str(p))==1;assert r.TransferRoots()>0
    s=r.OneShape();assert BRepCheck_Analyzer(s).IsValid();return s
def move(s,T):
    tr=gp_Trsf();tr.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(s,tr,True).Shape()
def mass(s):
    p=GProp_GProps();BRepGProp.VolumeProperties_s(s,p);return p.Mass()
def row_shape(r):return move(load(r['step_path'],r['source_sha256']),r['T_S_local'])
def compare(a,b):
    dist=BRepExtrema_DistShapeShape(a,b);dist.Perform();assert dist.IsDone()
    points=[]
    for p in (dist.PointOnShape1(1),dist.PointOnShape2(1)):points.append([p.X(),p.Y(),p.Z()])
    com=BRepAlgoAPI_Common(a,b);com.Build();assert com.IsDone() and BRepCheck_Analyzer(com.Shape()).IsValid()
    return {'distance_mm':dist.Value(),'common_volume_mm3':mass(com.Shape()),'nearest_points_S_mm':points},com.Shape()
def mesh(s):
    BRepMesh_IncrementalMesh(s,.2,False,.22,False).Perform();ex=TopExp_Explorer(s,TopAbs_FACE);tris=[]
    while ex.More():
        face=TopoDS.Face_s(ex.Current());loc=TopLoc_Location();tri=BRep_Tool.Triangulation_s(face,loc)
        if tri is not None:
            v=np.array([[p.X(),p.Y(),p.Z()] for p in [tri.Node(i).Transformed(loc.Transformation()) for i in range(1,tri.NbNodes()+1)]])
            tris.extend(v[np.array(tri.Triangle(i).Get())-1] for i in range(1,tri.NbTriangles()+1))
        ex.Next()
    return np.array(tris)

canonical=read(R1/'inputs/NEUTRAL_SOURCE_MAP.json');state=canonical['states']['service']
rows={r['id']:r for g in canonical['groups'] if g['id'] in state['groups'] for r in g['rows']}
rp=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');a=row_shape(rp['part'])
clip=row_shape(rows['trunk_clip_standoff_-140']);terminal=row_shape(rows['connector_arm_drive'])
near_r3,_=compare(a,clip);assert abs(near_r3['distance_mm']-.5)<1e-6 and near_r3['common_volume_mm3']<=1e-6
terminal_fact,_=compare(a,terminal);assert terminal_fact['common_volume_mm3']<=1e-6
children=[];ex=TopExp_Explorer(a,TopAbs_SOLID)
while ex.More():children.append(ex.Current());ex.Next()

r2plan=read(R2/'inputs/NATIVE_ROUTE_PLAN.json');route=row_shape(r2plan['parts'][0]);mount=row_shape(rows['WP01-MT-M3RB-REUSED'])
near_r2,_=compare(route,mount);assert abs(near_r2['distance_mm']-.75)<1e-6 and near_r2['common_volume_mm3']<=1e-6

impl=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
cfpath=impl/'cf1_layout_thermal/results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json';cf=read(cfpath)
cfmodule=move(load(impl/cf['module_step'],cf['module_step_sha256']),cf['T_S_module'])
hit=next(x for x in cf['states']['service']['collisions'] if x['parent_id']=='CLAMP_DUAL_BASE')
base=move(load(hit['step_path'],hit['source_sha256']),hit['T_S_step'])
near_cf,intersection=compare(cfmodule,base);assert abs(near_cf['common_volume_mm3']-hit['common_volume_mm3'])<1e-3

scenes=[]
r3meshes=[]
for i,s in enumerate(children):
    v=mass(s);color,opacity=('#5bb393',.12) if v>10000 else (('#328a6c',.55) if v>2000 else (('#d89321',1.) if v<300 else ('#326589',.8)))
    r3meshes.append((f'R3 预留实体 {i+1}',s,color,opacity))
r3meshes += [('线夹支架 / trunk_clip_standoff_-140',clip,'#bf613a',.8),('旧接口入口 / connector_arm_drive',terminal,'#52718a',.32)]
scenes.append({'title':'A  R3线路—支架：0.50 mm','subtitle':'当前预留 | 无穿透，公差裕量尚未验收','meshes':r3meshes,'measurement':near_r3,'view':(58,-78)})
scenes.append({'title':'B  R2线路—M3RB：0.75 mm','subtitle':'当前线路 | 已绕开旧穿透，仍需检查变形裕量',
    'meshes':[('R2释放线路（功能包络）',route,'#d89321',1.),('M3RB实体',mount,'#52718a',.4)],'measurement':near_r2,'view':(28,-72)})
scenes.append({'title':'C  CF1旧候选：实体穿透','subtitle':'未装入R3 | 与电池底座交叠 384.10 mm³',
    'meshes':[('CF1历史模块，未装入当前整星',cfmodule,'#4e93a3',.18),('历史位置的电池底座',base,'#71849a',.25),('精确布尔交叠区域',intersection,'#d53643',1.)],
    'measurement':near_cf,'view':(30,-57)})

fig=plt.figure(figsize=(18,8),facecolor='#f3f6fa')
fig.text(.035,.955,'装配干涉查看  |  当前小间距与未装入候选分列',fontproperties=F,fontsize=24,color='#1e364e')
fig.text(.035,.905,'基于锁定 STEP 实体、明确坐标变换和精确距离/布尔运算；颜色仅为检查标记。',fontproperties=F,fontsize=12,color='#53667a')
plot=make_subplots(rows=1,cols=3,specs=[[{'type':'scene'}]*3],subplot_titles=[s['title'] for s in scenes])
for n,s in enumerate(scenes,1):
    ax=fig.add_subplot(1,3,n,projection='3d',computed_zorder=False);ax.set_facecolor('#f3f6fa');allv=[]
    for name,solid,color,opacity in s['meshes']:
        tris=mesh(solid)
        if not len(tris):continue
        allv.append(tris.reshape(-1,3));ax.add_collection3d(Poly3DCollection(tris,facecolors=color,edgecolors='none',alpha=opacity))
        v=tris.reshape(-1,3);ix=np.arange(len(v)).reshape(-1,3)
        plot.add_trace(go.Mesh3d(x=v[:,0],y=v[:,1],z=v[:,2],i=ix[:,0],j=ix[:,1],k=ix[:,2],color=color,opacity=opacity,
            name=name,hovertemplate=name+'<extra></extra>',showlegend=True,flatshading=True),row=1,col=n)
    vertices=np.concatenate(allv);lo=vertices.min(0);hi=vertices.max(0);margin=np.maximum((hi-lo)*.08,2)
    ax.set_xlim(lo[0]-margin[0],hi[0]+margin[0]);ax.set_ylim(lo[1]-margin[1],hi[1]+margin[1]);ax.set_zlim(lo[2]-margin[2],hi[2]+margin[2]);ax.set_box_aspect(np.maximum(hi-lo,1));ax.view_init(*s['view']);ax.set_axis_off()
    pts=np.array(s['measurement']['nearest_points_S_mm'])
    ax.plot(*pts.T,color='#bb2a77',lw=3,marker='o',markersize=4,zorder=50)
    if n<3:
        label=f"{s['measurement']['distance_mm']:.2f} mm"
        ax.text(*pts.mean(0),label,color='#a41765',fontsize=11)
        plot.add_trace(go.Scatter3d(x=pts[:,0],y=pts[:,1],z=pts[:,2],mode='lines+markers+text',text=[label,''],textposition='top center',
            line=dict(color='#bb2a77',width=7),marker=dict(size=3),showlegend=False),row=1,col=n)
    else:
        gp=GProp_GProps();BRepGProp.VolumeProperties_s(intersection,gp);p=gp.CentreOfMass();c=[p.X(),p.Y(),p.Z()]
        ax.scatter(*c,s=100,c='#d53643',edgecolors='white',zorder=60)
        ax.text(*c,'  交叠区',fontproperties=F,fontsize=12,color='#b32636',zorder=61)
        plot.add_trace(go.Scatter3d(x=[c[0]],y=[c[1]],z=[c[2]],mode='markers+text',text=['384.10 mm³ 交叠区'],
            textposition='top center',marker=dict(size=5,color='#d53643'),showlegend=False),row=1,col=n)
    ax.text2D(.02,.98,s['title'],transform=ax.transAxes,fontproperties=F,fontsize=14,color='#223a54')
    ax.text2D(.02,.03,s['subtitle'],transform=ax.transAxes,fontproperties=F,fontsize=10,color='#53667a')
    key='scene'+(str(n) if n>1 else '')
    plot.update_layout(**{key:dict(aspectmode='data',xaxis_title='X / mm',yaxis_title='Y / mm',zaxis_title='Z / mm')})
fig.text(.035,.09,'A/B 的小间距不是已验收工程裕量。C 为历史拒收候选的展示，不代表它已装在当前 R3 中。',fontproperties=F,fontsize=12,color='#8b4b35')
fig.text(.035,.045,'先前 P60 安装柱/拉杆“碰撞”为坐标重复变换误报；正确名义距离为 23.73 / 26.23 mm，几何未因此改动。',fontproperties=F,fontsize=11,color='#53667a')
fig.subplots_adjust(top=.84,bottom=.16,left=.01,right=.99,wspace=.05)
png=D/'views/ASSEMBLY_INTERFERENCE_LOCATIONS.png';fig.savefig(png,dpi=150);plt.close(fig)
plot.update_layout(title='装配位置查看：拖动旋转，滚轮缩放，点击图例隐藏零件',height=750,margin=dict(l=10,r=10,b=10,t=80),legend=dict(orientation='h',y=-.08),paper_bgcolor='#f3f6fa')
html=D/'views/ASSEMBLY_INTERFERENCE_VIEWER.html'
cards=[]
for n,sc in enumerate(scenes,1):
    sid='scene'+(str(n) if n>1 else '')
    traces=[dict(t.to_plotly_json(),scene='scene') for t in plot.data if getattr(t,'scene',None)==sid]
    one=go.Figure(data=traces)
    one.update_layout(height=620,margin=dict(l=0,r=0,b=0,t=30),paper_bgcolor='#f3f6fa',
        scene=dict(aspectmode='data',xaxis_title='X/mm',yaxis_title='Y/mm',zaxis_title='Z/mm'),
        legend=dict(orientation='h',y=-.05,font=dict(size=10)))
    cards.append('<section><h2>'+sc['title']+'</h2><p>'+sc['subtitle']+'</p>'+one.to_html(full_html=False,include_plotlyjs=(n==1),config={'responsive':True,'displaylogo':False})+'</section>')
body='<main>'+''.join(cards)+'</main>'
html.write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>装配干涉查看</title><style>body{font:16px system-ui;margin:18px;background:#f3f6fa;color:#223a54}p{line-height:1.6}.note{padding:15px;background:white;border-left:4px solid #b77721}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:18px}section{min-width:0;padding:8px;border:1px solid #d5dce5;border-radius:8px}h2{font-size:18px}</style><h1>当前装配小间距与历史候选碰撞</h1><p class="note">A：R3预留到线夹支架0.50mm；B：R2线路到M3RB为0.75mm。两处均无精确实体穿透，但未验收制造/热变形/振动裕量。C：未装入当前R3的CF1旧候选与电池底座交叠384.10mm³，红色为实际布尔交集。</p><p>拖动旋转、滚轮缩放；点击各图下方图例可隐藏零件。窄窗口中三图按A、B、C依次向下排列。</p>'+body+'<p>绿色/蓝色为相关几何，黄色为功能线路，红色为精确交叠，洋红线标记最近点。P60安装柱/拉杆误报已通过规范化坐标配对纠正，名义距离23.73/26.23mm。此页面不是全星无干涉或可上电证明。</p></html>',encoding='utf-8')
report={'status':'GENERATED_PENDING_VISUAL_REVIEW','actual_STEP_geometry':True,'current_R3_near_clip':near_r3,'current_R3_terminal':terminal_fact,
    'current_R2_near_M3RB':near_r2,'historical_CF1_vs_base':near_cf,'CF1_installed_in_current_R3':False,
    'geometry_source_locks':LOCKS,'CF1_historical_report_sha256':sha(cfpath),
    'outputs':[{'path':str(p),'sha256':sha(p)} for p in [png,html]],'whole_assembly_interference_free':None,'material_colors_are_visual_only':True}
(D/'results/INTERFERENCE_VISUALIZATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['current_R3_near_clip','current_R2_near_M3RB','historical_CF1_vs_base','outputs']},ensure_ascii=False,indent=2))
