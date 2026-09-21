"""Review visualization from the checked STEP geometry, never a synthetic CAD image."""
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
    BRepMesh_IncrementalMesh(s,.25,False,.24,False).Perform();ex=TopExp_Explorer(s,TopAbs_FACE);out=[]
    while ex.More():
        face=TopoDS.Face_s(ex.Current());loc=TopLoc_Location();tri=BRep_Tool.Triangulation_s(face,loc)
        if tri is not None:
            v=np.array([[p.X(),p.Y(),p.Z()] for p in [tri.Node(i).Transformed(loc.Transformation()) for i in range(1,tri.NbNodes()+1)]])
            out.extend(v[np.array(tri.Triangle(i).Get())-1] for i in range(1,tri.NbTriangles()+1))
        ex.Next()
    return np.array(out)

lay=read(D/'inputs/INSTALLATION_LAYOUT.json');check=read(D/'results/INCREMENT_STATIC_CHECK.json');assert check['valid']
current={r['id']:r for r in state_rows()['service']};current.update({r['id']:r for r in lay['parts']+lay['replacements']})
def item(k,color,alpha=1):return k,source(current[k]),color,alpha
core=[]
shape=source(current['R6_MAIN_PCBA_INSTALLED']);ex=TopExp_Explorer(shape,TopAbs_SOLID);sol=[]
while ex.More():sol.append(ex.Current());ex.Next()
assert len(sol)==40
for n,s in enumerate(sol):
    col='#d79238' if n>=36 else ('#248c72' if n==25 else '#425771')
    core.append((('待验证高度占位 ' if n>=36 else '主输入板源实体 ')+str(n+1),s,col,.85 if n>=36 else 1))
hw=[item(r['id'],'#899ba9' if 'CARRIER' not in r['id'] else '#62a8bd') for r in lay['parts'] if r['id'].startswith('R6_MAIN') and r['id']!='R6_MAIN_PCBA_INSTALLED']
context=[item('P60_TRAY_B','#8194a7',.14),item('P60_HOST_0_POST','#8794a2',.3)]
# A cropped context deck is a visualization cut only. The delivered part remains complete.
context.append(('设备层板局部',common(source(current['upper_equipment_deck_B']),box(-180,-15,-12,-48,98,-8)),'#bac5cc',.1))
interface=source(current['equipment_arm_drive']);e=TopExp_Explorer(interface,TopAbs_SOLID);ip=[];n=0
while e.More():ip.append((f'接口板功能包络 {n}',e.Current(),'#558c82',.2 if n else .65));n+=1;e.Next()
bridge=[item('R6_IF_THERMAL_BRIDGE','#64a8ba'),item('R6_IF_TOP_ISOLATION_PAD','#e9be5c'),item('thermal_interface_arm_drive','#9b85aa',.6)]+ip
scenes=[
 dict(title='A  主输入板数字安装',note='倾斜20° / 偏转10°；四点PCB安装＋两处机身固定',meshes=context+core+hw,view=(26,-115)),
 dict(title='B  接口板传热接触',note='4 mm传热块＋0.5 mm绝缘垫；热性能待验证',meshes=bridge,view=(17,-118)),
 dict(title='C  推进装配预留区',note='已有包络与功率/数据通道保留；喷口和储箱待OEM绑定',meshes=[item('MIPS_CRADLE_B','#779aac',.8),item('MIPS_OEM_MAX_ENVELOPE','#d39241',.4),item('equipment_adcs_propulsion_allocation','#caaa76',.14),item('adapter_adcs_propulsion_allocation','#8894a1',.2),item('PROP_PWR_ROUTE','#d5604b'),item('PROP_DATA_ROUTE','#368bb3')],view=(22,-60))]
fig=plt.figure(figsize=(19,8.4),facecolor='#f3f6fa');cards=[]
fig.text(.03,.945,'R6 核心电气安装  |  推进装配准备',fontproperties=F,fontsize=25,color='#203a52')
fig.text(.03,.895,'实际STEP几何；三种固定姿态的本轮增量布尔检查：172对，0干涉、0未决。',fontproperties=F,fontsize=12,color='#526a7f')
for j,sc in enumerate(scenes,1):
    ax=fig.add_subplot(1,3,j,projection='3d',computed_zorder=False);ax.set_facecolor('#f3f6fa');vertices=[];p=go.Figure()
    for name,s,color,opacity in sc['meshes']:
        tri=mesh(s)
        if not len(tri):continue
        v=tri.reshape(-1,3);ix=np.arange(len(v)).reshape(-1,3);vertices.append(v)
        ax.add_collection3d(Poly3DCollection(tri,facecolors=color,edgecolors='none',alpha=opacity))
        p.add_trace(go.Mesh3d(x=v[:,0],y=v[:,1],z=v[:,2],i=ix[:,0],j=ix[:,1],k=ix[:,2],name=name,color=color,opacity=opacity,showlegend=True,hovertemplate=name+'<extra></extra>',flatshading=True))
    v=np.concatenate(vertices);lo=v.min(0);hi=v.max(0);m=np.maximum((hi-lo)*.05,2)
    ax.set_xlim(lo[0]-m[0],hi[0]+m[0]);ax.set_ylim(lo[1]-m[1],hi[1]+m[1]);ax.set_zlim(lo[2]-m[2],hi[2]+m[2]);ax.set_box_aspect(np.maximum(hi-lo,1));ax.view_init(*sc['view']);ax.set_axis_off()
    ax.text2D(.01,.98,sc['title'],transform=ax.transAxes,fontproperties=F,fontsize=14,color='#203a52')
    ax.text2D(.01,.02,sc['note'],transform=ax.transAxes,fontproperties=F,fontsize=9,color='#53697d')
    p.update_layout(height=620,margin=dict(l=0,r=0,b=0,t=0),paper_bgcolor='#f3f6fa',scene=dict(aspectmode='data',xaxis_title='X/mm',yaxis_title='Y/mm',zaxis_title='Z/mm'),legend=dict(font=dict(size=9),x=1,y=1))
    cards.append('<section><h2>'+sc['title']+'</h2><p>'+sc['note']+'</p>'+p.to_html(full_html=False,include_plotlyjs=(j==1),config={'responsive':True,'displaylogo':False})+'</section>')
fig.text(.03,.08,'橙色小件为4个位号的高度占位；接口板、推进盒和线路仍含功能包络。颜色是检查标记。',fontproperties=F,fontsize=11,color='#a06124')
fig.text(.03,.035,'固定姿态数字候选：未完成公差/强度、真实接线、STOP/AUX安装、热性能和上电验收。',fontproperties=F,fontsize=11,color='#53697d')
fig.subplots_adjust(left=.01,right=.99,top=.84,bottom=.155,wspace=.03)
png=D/'views/R6_CORE_INSTALLATION.png';fig.savefig(png,dpi=150);plt.close(fig)
html=D/'views/R6_CORE_INSTALLATION_VIEWER.html'
html.write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R6 核心电气安装</title><style>body{font:16px system-ui;background:#f3f6fa;color:#203a52;margin:20px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,550px),1fr));gap:14px}section{min-width:0;border:1px solid #ced9e1;border-radius:10px;padding:12px}h2{font-size:19px}.note{background:white;border-left:4px solid #c48f3b;padding:15px;line-height:1.7}</style><h1>R6 核心电气安装与推进装配准备</h1><p class="note">主输入板35个位号已在数字装配中表示：23个KiCad模型、6个既有目录/OEM参考外形、2个当前型号尺寸包络、4个待验证高度占位。新安装31个叶实例，修改2个支撑零件。三种固定状态本轮172对检查无体积干涉；未包含全运动扫掠和公差验证。STOP/AUX板和实际接线尚待安装。</p><p>拖动旋转，滚轮缩放，点击图例隐藏/显示。层板为局部显示裁切；实际CAD保留整板。所有颜色仅用于审阅。</p><main>'+''.join(cards)+'</main><p class="note">推进系统：保留MIPS支架、最大包络和功率/数据功能通道。OEM孔系、喷口位置/方向、阀脉冲与并发、质量惯量及羽流约束仍未闭合。此版不授予上电或飞行放行。</p></html>',encoding='utf-8')
write(D/'results/INSTALLATION_VISUALIZATION.json',dict(status='PENDING_VISUAL_REVIEW',actual_STEP_geometry=True,source_check_sha256=sha(D/'results/INCREMENT_STATIC_CHECK.json'),material_colors_are_visual_only=True,outputs=[dict(path=str(p),sha256=sha(p)) for p in [png,html]]))
print('RENDERED',png,html,flush=True)
