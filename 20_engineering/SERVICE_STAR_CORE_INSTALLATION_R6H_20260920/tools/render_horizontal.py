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
lay=read(D/'inputs/INSTALLATION_LAYOUT.json');chk=read(D/'results/INCREMENT_STATIC_CHECK.json');assert chk['valid']
current={r['id']:r for r in read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json')['expected_leaves']}
def obj(k,col,alpha=1):return k,source(current[k]),col,alpha
core=[];ex=TopExp_Explorer(source(current['R6H_MAIN_PCBA_INSTALLED']),TopAbs_SOLID);n=0
while ex.More():
    core.append((('待核验器件高度 ' if n>=36 else '主输入板实体 ')+str(n+1),ex.Current(),'#d79b38' if n>=36 else ('#248975' if n==25 else '#415b73'),1));n+=1;ex.Next()
hardware=[obj(r['id'],'#79a6b4') for r in lay['parts'] if r['id'].startswith('R6H_MAIN_') and r['id']!='R6H_MAIN_PCBA_INSTALLED']
P60=[obj(r['id'],'#cc8744') for r in lay['pose_changes']]
floor=('层板显示局部',common(source(current['upper_equipment_deck_B']),box(-174,-15,-12,-45,98.15,-8.5)),'#bcc8d1',.15)
top=obj('P60_TRAY_B','#889dae',.15)
heat=[obj('R6H_IF_THERMAL_BRIDGE','#3e9baa'),obj('R6H_IF_TOP_ISOLATION_PAD','#e5ba5b'),obj('thermal_interface_arm_drive','#9886ac',.5),obj('equipment_arm_drive','#4a9b88',.2)]
scenes=[dict(title='A  主输入板水平安装',note='4根20mm隔柱；PCB法向与舱内层板平行',meshes=[floor,top]+core+hardware+P60,view=(20,-112)),
 dict(title='B  后支点局部修正',note='位移(-4,+12,0)mm；小耳台和同轴孔；无需螺母钟向',meshes=P60+[('托盘局部',common(source(current['P60_TRAY_B']),box(-165,73,52,-144,99,56)),'#79a6b4',.6),('层板局部',common(source(current['upper_equipment_deck_B']),box(-166,76,-12,-144,98,-8)),'#bcc8d1',.4),('框架角件局部',common(source(current['upper_deck_angle_1_0']),box(-166,84,-27,-144,101.5,-11.4)),'#8e9aab',.55)],view=(20,-120)),
 dict(title='C  接口板传热接触',note='4mm传热块＋0.5mm绝缘垫；几何接触已闭合',meshes=heat,view=(15,-118)),
 dict(title='D  推进部件装配准备',note='保留已有预留区和线路；喷口、储箱与OEM接口未冻结',meshes=[obj('MIPS_CRADLE_B','#7093a7',.8),obj('MIPS_OEM_MAX_ENVELOPE','#d39a50',.4),obj('equipment_adcs_propulsion_allocation','#cfb384',.16),obj('adapter_adcs_propulsion_allocation','#939fac',.18),obj('PROP_PWR_ROUTE','#d06551'),obj('PROP_DATA_ROUTE','#338eb4')],view=(20,-60))]
fig=plt.figure(figsize=(18,12),facecolor='#f3f6fa');fig.text(.025,.96,'R6H 水平电气安装  |  最小改动方案',fontproperties=F,fontsize=25,color='#203a52')
fig.text(.025,.92,f"实际STEP几何；三种固定姿态增量检查{chk['exact_pair_count']}对：0干涉、0未决。整星外形与原有电池/推进线路未改变。",fontproperties=F,fontsize=12,color='#536c7e')
cards=[]
for i,sc in enumerate(scenes,1):
    ax=fig.add_subplot(2,2,i,projection='3d',computed_zorder=False);ax.set_facecolor('#f3f6fa');verts=[];p=go.Figure()
    for name,s,col,alpha in sc['meshes']:
        tri=mesh(s)
        if not len(tri):continue
        v=tri.reshape(-1,3);ix=np.arange(len(v)).reshape(-1,3);verts.append(v)
        ax.add_collection3d(Poly3DCollection(tri,facecolors=col,edgecolors='none',alpha=alpha))
        p.add_trace(go.Mesh3d(x=v[:,0],y=v[:,1],z=v[:,2],i=ix[:,0],j=ix[:,1],k=ix[:,2],color=col,opacity=alpha,name=name,hovertemplate=name+'<extra></extra>',flatshading=True,showlegend=True))
    v=np.concatenate(verts);lo=v.min(0);hi=v.max(0);m=np.maximum((hi-lo)*.05,1)
    ax.set_xlim(lo[0]-m[0],hi[0]+m[0]);ax.set_ylim(lo[1]-m[1],hi[1]+m[1]);ax.set_zlim(lo[2]-m[2],hi[2]+m[2]);ax.set_box_aspect(np.maximum(hi-lo,1));ax.view_init(*sc['view']);ax.set_axis_off()
    ax.text2D(.01,.98,sc['title'],transform=ax.transAxes,fontproperties=F,fontsize=14,color='#203a52');ax.text2D(.01,.01,sc['note'],transform=ax.transAxes,fontproperties=F,fontsize=10,color='#536c7e')
    p.update_layout(height=600,margin=dict(l=0,r=0,b=0,t=0),paper_bgcolor='#f3f6fa',scene=dict(aspectmode='data',xaxis_title='X/mm',yaxis_title='Y/mm',zaxis_title='Z/mm'),legend=dict(font=dict(size=9)))
    cards.append('<section><h2>'+sc['title']+'</h2><p>'+sc['note']+'</p>'+p.to_html(full_html=False,include_plotlyjs=(i==1),config={'responsive':True,'displaylogo':False})+'</section>')
fig.text(.025,.045,'橙色小件含4项高度占位；颜色为检查标记。固定姿态候选，公差/强度/工具可达、端接及热性能仍需验证。',fontproperties=F,fontsize=11,color='#97632e')
fig.subplots_adjust(left=.02,right=.98,top=.88,bottom=.085,wspace=.02,hspace=.07)
png=D/'views/R6H_HORIZONTAL_INSTALLATION.png';fig.savefig(png,dpi=130);plt.close(fig)
html=D/'views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html'
html.write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R6H 水平安装方案</title><style>body{font:16px system-ui;background:#f3f6fa;color:#203a52;margin:20px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,560px),1fr));gap:14px}section{min-width:0;border:1px solid #cbd8e0;border-radius:10px;padding:12px}h2{font-size:19px}.note{background:white;padding:16px;border-left:4px solid #428b99;line-height:1.7}</style><h1>R6H 水平电气安装与推进装配准备</h1><p class="note">已撤下倾斜方案。MAIN法向保持S_Z，原点[-164,86,11.5]mm。新增23个叶实例；4个既有零件局部改型，5个既有零件仅改变位姿。整星外形、P60设备盒、旧转接板、电池与推进线路保持原样。386对三态增量几何检查通过；这不代替全运动、公差、强度或上电验收。</p><p>拖动旋转、滚轮缩放、点图例隐藏。图中层板/托盘/框架角件仅作显示裁切，实际CAD保留完整几何。</p><main>'+''.join(cards)+'</main><p class="note">35个位号有分级几何表示：23个KiCad模型、6个目录/OEM参考、2个型号尺寸包络、4个待核验高度占位。PCB总层包络按1.60mm名义叠层修正，未据此赋整板质量。STOP/AUX和真实端接仍待布置。推进9项OEM输入与12份工程工作单已备；喷口/储箱装配及上电放行未冻结。</p></html>',encoding='utf-8')
write(D/'results/HORIZONTAL_VISUALIZATION.json',dict(status='PENDING_VISUAL_REVIEW',actual_STEP_geometry=True,source_layout_sha256=sha(D/'inputs/INSTALLATION_LAYOUT.json'),source_check_sha256=sha(D/'results/INCREMENT_STATIC_CHECK.json'),material_colors_are_visual_only=True,outputs=[dict(path=str(p),sha256=sha(p)) for p in [png,html]]))
print('RENDERED',png,html,flush=True)
