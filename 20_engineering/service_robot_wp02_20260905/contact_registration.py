"""Local accepted-STL ray measurements, not hardware contact certification."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'service_robot_wp01_20260905'))
from kinematics import TREE,URDF,fk,tf,place
def triangle_data():
    path=URDF.parent/TREE.find("link[@name='link2']").find('visual/geometry/mesh').get('filename')
    with path.open('rb') as f:
        f.read(80);n=int.from_bytes(f.read(4),'little')
        data=np.fromfile(f,dtype=np.dtype([('normal','<f4',3),('vertices','<f4',(3,3)),('attr','<u2')]),count=n)
    p=json.loads((HERE/'inputs/wp01_design_parameters.json').read_text())
    T=fk(p['states']['stowed']['q_deg'],tf((90,0,125.15)),15)['link2']
    return path,place(data['vertices'].reshape(-1,3).astype(float)*1000,T).reshape(-1,3,3),T
def main():
    path,tri,T=triangle_data();a=tri[:,0];u=tri[:,1]-a;v=tri[:,2]-a
    d=u[:,0]*v[:,1]-u[:,1]*v[:,0];idx=np.where(abs(d)>1e-8)[0]
    def ray(x,y):
        q=np.array([x,y])-a[idx,:2];s=(q[:,0]*v[idx,1]-q[:,1]*v[idx,0])/d[idx];h=(u[idx,0]*q[:,1]-u[idx,1]*q[:,0])/d[idx]
        ok=(s>=-1e-9)&(h>=-1e-9)&(s+h<=1+1e-9);k=idx[ok]
        z=a[k,2]+s[ok]*u[k,2]+h[ok]*v[k,2]
        if not len(z):raise ValueError('No shell at proposed pad point')
        return float(z.min()),int(k[np.argmin(z)])
    stations=[]
    for name,x in [('A',-115.),('B',-40.)]:
        pads=[]
        pad_x=x if name=='A' else x+5 # B shift avoids a stepped cover/fastener feature.
        for y in [-12.,12.]:
            xy=np.array([[xx,yy] for xx in np.linspace(pad_x-2,pad_x+2,9) for yy in np.linspace(y-4,y+4,9)])
            rr=[ray(*z) for z in xy];zs=np.array([r[0] for r in rr]);A=np.c_[xy,np.ones(len(xy))]
            coeff=np.linalg.lstsq(A,zs,rcond=None)[0];res=zs-A@coeff
            # Shift the nominal planar pad until its closest sampled point touches.
            coeff[2]+=res.min();gap=zs-A@coeff
            corners=np.array([[pad_x-2,y-4],[pad_x+2,y-4],[pad_x+2,y+4],[pad_x-2,y+4]])
            top=np.c_[corners,np.c_[corners,np.ones(4)]@coeff]
            normals=np.cross(u[rr[40][1]],v[rr[40][1]]);normals/=np.linalg.norm(normals)
            pads.append(dict(center_xy_mm=[pad_x,y],footprint_xy_mm=[4,8],top_plane_z_ax_by_c=coeff.tolist(),top_corners_mm=top.tolist(),ray_count=len(xy),min_sample_gap_mm=float(gap.min()),max_sample_gap_mm=float(gap.max()),triangle_indices_0based=sorted(set(r[1] for r in rr)),center_triangle_vertices_mm=tri[rr[40][1]].tolist(),surface_normal=normals.tolist(),pressure_allowable_MPa=None,wall_thickness_mm=None,internal_support_evidence=None,preload_N=None,contact_state='NOMINAL_STL_TANGENCY_AT_SAMPLED_POINTS; NOT_HARDWARE_CONTACT'))
        floor=min(z[2] for p in pads for z in p['top_corners_mm'])-3
        stations.append(dict(station=name,x_mm=x,pad_bottom_z_mm=floor,pad_min_thickness_mm=3.,pad_compression_mm=None,pads=pads,shoe_top_z_mm=floor))
    out={'method':'VERTICAL_TRIANGLE_RAYS_AND_CONSERVATIVE_PLANAR_FIT; FINITE_9x9_PER_PAD','source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'T_S_link2':T.tolist(),'registration_residual_to_hardware_mm':None,'nominal_BREP_to_STL_residual_mm':None,'stations':stations,'missing':'Vendor allowed clamping zones and shell bearing capacity; conformity requires real surfaces and pad coupon tests.'}
    (HERE/'results/CONTACT_REGISTRATION.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps([{'station':s['station'],'shoe_top_z_mm':s['shoe_top_z_mm'],'max_gaps':[p['max_sample_gap_mm'] for p in s['pads']]} for s in stations]))
if __name__=='__main__':main()
