"""Actual STEP tessellation plus a source-derived existing-allocation map."""
from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from mpl_toolkits.mplot3d.art3d import Poly3DCollection,Line3DCollection
from OCP.STEPControl import STEPControl_Reader
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
D=Path(__file__).resolve().parents[1]
FONT=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
def label(ax,x,y,t,**kw):return ax.text2D(x,y,t,transform=ax.transAxes,fontproperties=FONT,**kw)
def mesh(s):
    BRepMesh_IncrementalMesh(s,.08,False,.15,False).Perform();e=TopExp_Explorer(s,TopAbs_FACE);tri=[]
    while e.More():
        f=TopoDS.Face_s(e.Current());loc=TopLoc_Location();t=BRep_Tool.Triangulation_s(f,loc)
        v=np.array([[p.X(),p.Y(),p.Z()] for p in [t.Node(i).Transformed(loc.Transformation()) for i in range(1,t.NbNodes()+1)]])
        tri.extend(v[np.array(t.Triangle(i).Get())-1] for i in range(1,t.NbTriangles()+1));e.Next()
    return np.array(tri)
def wirebox(ax,lo,hi,color,alpha=.8):
    pts=np.array([[x,y,z] for x in [lo[0],hi[0]] for y in [lo[1],hi[1]] for z in [lo[2],hi[2]]])
    edges=[(pts[i],pts[j]) for i in range(8) for j in range(i+1,8) if np.count_nonzero(pts[i]!=pts[j])==1]
    ax.add_collection3d(Line3DCollection(edges,colors=color,alpha=alpha,linewidths=1.2))
r=STEPControl_Reader();assert r.ReadFile(str(D/'cad/B601_INTERFACE_RESERVATION.step'))==1;r.TransferRoots();e=TopExp_Explorer(r.OneShape(),TopAbs_SOLID);solids=[]
while e.More():solids.append(e.Current());e.Next()
fig=plt.figure(figsize=(16,8),facecolor='#f5f7fa')
fig.text(.05,.94,'R3  |  既有舱位细化与 B601 控制接口预留',fontproperties=FONT,fontsize=23,color='#18364d')
fig.text(.05,.895,'左：现有五个设备预算包络     右：本轮 STEP 实体预览     主机可连接为用户认可的设计假设',fontproperties=FONT,fontsize=12,color='#526578')
ax=fig.add_subplot(121,projection='3d');ax.set_facecolor('#f5f7fa')
slots=[('臂控接口',[-142.5,-83,-6],[-57.5,-13,34],'#e18327'),('主机/通信',[-35,-85.5,-6],[55,-10.5,34],'#317baa'),('导航',[-25,13,-6],[45,83,34],'#67a486'),('ADCS/推进',[20,-80,-95.65],[130,80,-20.65],'#8a73a7'),('电池',[-159,-85,-95.65],[-69,85,-30.65],'#a48b65')]
for name,lo,hi,col in slots:
    wirebox(ax,lo,hi,col);c=(np.array(lo)+hi)/2;ax.text(*c,name,fontproperties=FONT,fontsize=10,color=col)
for s in solids:ax.add_collection3d(Poly3DCollection(mesh(s),facecolors='#d78127',edgecolors='none',alpha=.8))
ax.set_xlim(-180,150);ax.set_ylim(-110,110);ax.set_zlim(-110,55);ax.set_box_aspect((330,220,165));ax.view_init(28,-62);ax.set_axis_off()
label(ax,.04,.02,'空间来自既有装配计划；这里只显示设备分配区',fontsize=11,color='#526578')
ax=fig.add_subplot(122,projection='3d');ax.set_facecolor('#f5f7fa');wirebox(ax,[-142.5,-83,-6],[-57.5,-13,34],'#8293a5',.5)
for i,s in enumerate(solids):
    # Match by volume instead of relying on STEP writer solid order.
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g=GProp_GProps();BRepGProp.VolumeProperties_s(s,g);vol=g.Mass()
    color,alpha=('#71b8a4',.15) if vol>10000 else (('#238064',1) if vol>2000 else (('#dda52c',1) if vol<200 else ('#315371',1)))
    ax.add_collection3d(Poly3DCollection(mesh(s),facecolors=color,edgecolors='none',alpha=alpha))
ax.set_xlim(-147,-53);ax.set_ylim(-86,-9);ax.set_zlim(-7,35);ax.set_box_aspect((94,77,42));ax.view_init(32,-62);ax.set_axis_off()
label(ax,.07,.86,'85×70×40 mm 原预留边界',fontsize=12,color='#526578')
label(ax,.07,.10,'60×40 PCB预留  /  4组端口包络  /  2条局部功能线路',fontsize=11,color='#18364d')
label(ax,.07,.04,'器件高度18 mm；孔位与接头均为设计候选',fontsize=11,color='#526578')
fig.text(.05,.04,'尚未进行元件电路、整臂动态布线或材料/质量定型。灰框与半透明体均表示空间预留。',fontproperties=FONT,fontsize=11,color='#526578')
fig.subplots_adjust(left=.01,right=.99,bottom=.12,top=.84,wspace=.04)
p=D/'views/R3_INTERFACE_ASSEMBLY_REVIEW.png';fig.savefig(p,dpi=140);plt.close(fig);print(p)
