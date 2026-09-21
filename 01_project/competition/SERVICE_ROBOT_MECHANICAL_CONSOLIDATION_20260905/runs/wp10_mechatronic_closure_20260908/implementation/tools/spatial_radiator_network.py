"""Signed passive multi-panel thermal network, bound to current CAD view samples.

This sizing solver does not instantiate an unbuilt link. Local sampled view
fractions exchange radiation with specified black surroundings; they are not
an area-reduction factor. Unspecified orbit, coating/contact and equipment
heat remain separate from these CHB-only engineering scenarios.
"""
from pathlib import Path
import json,hashlib,math
import numpy as np
from scipy.sparse import coo_matrix,diags,block_diag
from scipy.sparse.linalg import spsolve

A=Path(__file__).resolve().parents[1]
SIGMA=5.670374419e-8
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()

class Sheet:
    def __init__(self,face,bottom=None,pitch=5.,k=130.,uniform_view=None):
        self.face=face;w,h=face['face_size_mm'];nx=math.ceil(w/pitch);ny=math.ceil(h/pitch)
        self.dx=w/nx;self.dy=h/ny;dx,dy=self.dx,self.dy
        self.X,self.Y=np.meshgrid((np.arange(nx)+.5)*dx-w/2,(np.arange(ny)+.5)*dy-h/2)
        X,Y=self.X,self.Y;fraction=np.zeros_like(X);tk=np.zeros_like(X)
        for ox in (np.arange(16)+.5)/16-.5:
            for oy in (np.arange(16)+.5)/16-.5:
                x=X+ox*dx;y=Y+oy*dy;keep=np.ones_like(X,dtype=bool);t=np.full_like(X,8.)
                for xx,yy,d in face.get('holes_ab_d_mm',[]):keep&=(x-xx)**2+(y-yy)**2>=(d/2)**2
                if bottom:
                    q=bottom['beam_reliefs']
                    for xx in q['x_mm']:t=np.where(abs(x-xx)<q['width_mm']/2,q['bottom_z_mm']-bottom['outer_z_mm'],t)
                    for key in ['lower_fastener_blind_pockets','MIPS_blind_pockets']:
                        q=bottom[key]
                        for xx in q['x_mm']:
                            for yy in q['y_mm']:t=np.where((x-xx)**2+(y-yy)**2<(q['diameter_mm']/2)**2,np.minimum(t,q['bottom_z_mm']-bottom['outer_z_mm']),t)
                else:
                    for xx in [-150,-90,-30,30,90,150]:t=np.where((abs(x-xx)<9)&(abs(y)>86.35),3.5,t)
                fraction+=keep/256;tk+=t*keep/256
        self.active=fraction>0;self.fraction=fraction;self.thickness=np.divide(tk,fraction,out=np.zeros_like(tk),where=fraction>0)/1000
        self.area=(dx*dy*1e-6*fraction)[self.active];self.n=len(self.area)
        ids=np.full_like(X,-1,dtype=int);ids[self.active]=np.arange(self.n);self.ids=ids
        rr=[];cc=[];vv=[]
        for j,i in zip(*np.where(self.active)):
            for jj,ii in [(j,i+1),(j+1,i)]:
                if jj>=ny or ii>=nx or not self.active[jj,ii]:continue
                f1,f2=fraction[j,i],fraction[jj,ii];t1,t2=self.thickness[j,i],self.thickness[jj,ii]
                g=k*(2*t1*t2/(t1+t2))*(2*f1*f2/(f1+f2))*(dy/dx if ii!=i else dx/dy)
                p,q=ids[j,i],ids[jj,ii];rr.extend([p,q,p,q]);cc.extend([p,q,q,p]);vv.extend([g,g,-g,-g])
        self.L=coo_matrix((vv,(rr,cc)),shape=(self.n,self.n)).tocsr()
    def weights(self,center,size):
        x,y=center;w,h=size;X,Y=self.X,self.Y;dx,dy=self.dx,self.dy
        wx=np.maximum(0,np.minimum(X+dx/2,x+w/2)-np.maximum(X-dx/2,x-w/2))
        wy=np.maximum(0,np.minimum(Y+dy/2,y+h/2)-np.maximum(Y-dy/2,y-h/2))
        v=(wx*wy*self.fraction)[self.active];assert v.sum()>0;return v/v.sum()
    def view(self,grid):
        # Exact area overlap of thermal rectangles and the measured view-grid
        # rectangles. This conserves the area integral on an unperforated face;
        # per-cell occupancy is the explicitly disclosed near-hole approximation.
        vals=np.asarray(grid['blocked_fraction'],float);assert np.isfinite(vals).all()
        ny,nx=vals.shape;w,h=self.face['face_size_mm'];dx,dy=self.dx,self.dy;X,Y=self.X,self.Y
        out=np.zeros_like(X)
        for j in range(ny):
            wy=np.maximum(0,np.minimum(Y+dy/2,-h/2+(j+1)*h/ny)-np.maximum(Y-dy/2,-h/2+j*h/ny))
            for i in range(nx):
                wx=np.maximum(0,np.minimum(X+dx/2,-w/2+(i+1)*w/nx)-np.maximum(X-dx/2,-w/2+i*w/nx))
                out+=wx*wy*vals[j,i]/(dx*dy)
        assert out.min()>-1e-12 and out.max()<1+1e-12;return np.clip(out[self.active],0,1)

def solve(sheets,loads,links,envs):
    offsets=np.cumsum([0]+[s.n for s in sheets]);n=offsets[-1]
    L=block_diag([s.L for s in sheets],format='csr');heat=np.zeros(n);load_weights=[];link_vectors=[]
    for r in loads:
        i=r['sheet'];v=np.zeros(n);v[offsets[i]:offsets[i+1]]=sheets[i].weights(r['center'],r['size']);heat+=r['power_W']*v;load_weights.append(v)
    rr=[];cc=[];vv=[]
    for r in links:
        assert math.isfinite(r['R_K_W']) and r['R_K_W']>0,'Passive links need finite positive R'
        v=np.zeros(n)
        for tag,sign in [('a',1),('b',-1)]:
            ep=r[tag];i=ep['sheet'];v[offsets[i]:offsets[i+1]]+=sign*sheets[i].weights(ep['center'],ep['size'])
        ids=np.flatnonzero(v);outer=np.outer(v[ids],v[ids])/r['R_K_W']
        rr.extend(np.repeat(ids,len(ids)));cc.extend(np.tile(ids,len(ids)));vv.extend(outer.ravel());link_vectors.append(v)
    if links:L=L+coo_matrix((vv,(rr,cc)),shape=(n,n)).tocsr()
    area=np.concatenate([s.area for s in sheets]);incoming=[]
    for s,e in zip(sheets,envs):
        F=s.view(e['grid']) if e.get('grid') else np.full(s.n,e.get('uniform_F',0.))
        incoming.append(.89*SIGMA*((1-F)*e.get('space_K',3.)**4+F*e.get('occluder_K',330.)**4)+.17*e.get('solar_W_m2',0.))
    incoming=np.concatenate(incoming);T=np.full(n,355.)
    for it in range(60):
        residual=L@T+area*(.89*SIGMA*T**4-incoming)-heat
        if abs(residual).max()<1e-11 and abs(float(np.sum(area*(.89*SIGMA*T**4-incoming))-heat.sum()))<5e-9:break
        delta=spsolve(L+diags(area*4*.89*SIGMA*T**3),-residual);T+=delta*min(1,30/max(abs(delta).max(),1e-30))
    assert abs(residual).max()<1e-8
    radiated=area*(.89*SIGMA*T**4-incoming);panels=[]
    for i,s in enumerate(sheets):
        sl=slice(offsets[i],offsets[i+1]);tt=T[sl];panels.append(dict(face=s.face['id'],area_m2=float(s.area.sum()),min_C=float(tt.min()-273.15),max_C=float(tt.max()-273.15),mean_C=float(np.dot(tt,s.area)/s.area.sum()-273.15),net_outward_W=float(radiated[sl].sum()),mesh=list(s.X.shape)))
    return dict(panels=panels,source_mean_C=[float(np.dot(T,v)-273.15) for v in load_weights],source_peak_C=[float(T[v>1e-12].max()-273.15) for v in load_weights],link_heat_a_to_b_W=[float(np.dot(T,v)/r['R_K_W']) for v,r in zip(link_vectors,links)],net_outward_W=float(radiated.sum()),input_W=float(heat.sum()),balance_error_W=float(radiated.sum()-heat.sum()),residual_max_W=float(abs(residual).max()),iterations=it+1)

def main():
    view=read('thermal/RADIATOR_MESH_VIEW_SCREEN.json');cfg=read('thermal/BOTTOM_RADIATOR_MOUNT.json');g=read('results/FIXED_HEAT_GEOMETRY.json')
    assert all(sha(p)==h for p,h in view['inputs'].items())
    keys=['FIXED_MINUS_Z_BOTTOM_PLATE','FIXED_PLUS_Y','FIXED_MINUS_Y'];faces={r['face']['id']:r['face'] for r in view['results']}
    # Normalize existing plus face ID without guessing its spelling.
    keys[1]=next(k for k in faces if k.endswith('PLUS_Y'))
    sheets=[Sheet(faces[k],cfg if i==0 else None) for i,k in enumerate(keys)]
    c=cfg['chb_path'];geom=read('results/COLD_PATH_GEOMETRY.json');assert geom['checks_passed'] and geom['config_sha256']==sha('thermal/BOTTOM_RADIATOR_MOUNT.json')
    tim_impedance=c.get('TIM_impedance_C_in2_W_at25psi',.75)
    q=361*(1/.85-1);Rc=tim_impedance*25.4**2/g['CHB_TIM_contact_area_mm2']+geom['CHB_nominal_metal_path_mm']/1000/(130*g['CHB_TIM_contact_area_mm2']*1e-6)
    load=dict(sheet=0,center=c['center_xy_mm'],size=[55.9,59],power_W=q)
    fw=c['finger_x_mm'][1]-c['finger_x_mm'][0];ry=c['finger_riser_abs_y_mm'];foot_y=sum(ry)/2
    za,zb=c['finger_arm_z_mm'];arm_z=(za+zb)/2;end=c['wall_seat_abs_y_mm']-c['wall_TIM_thickness_mm']
    foot_area=fw*(ry[1]-ry[0])*1e-6;arm_area=fw*(zb-za)*1e-6;contact=geom['wall_joints'][0]['contact_area_mm2']*1e-6
    terms=dict(bottom_foot_through=8e-3/(130*foot_area),riser=(arm_z-cfg['plate_top_z_mm'])*1e-3/(130*foot_area),
      horizontal_arm=(end-foot_y)*1e-3/(130*arm_area),TIM_typical25psi=tim_impedance*25.4**2/(contact*1e6),wall_through=(113.15-c['wall_seat_abs_y_mm'])*1e-3/(130*contact))
    nominal_R=sum(terms.values())
    endpoints=[dict(a=dict(sheet=0,center=[c['center_xy_mm'][0],sg*foot_y],size=[fw,ry[1]-ry[0]]),b=dict(sheet=i,center=c['wall_contact_center_xz_mm'],size=c['wall_TIM_size_mm'])) for i,sg in [(1,1),(2,-1)]]
    rows=[]
    for state in ['service','parking','released']:
      for occluder in [330.,350.]:
        for sun in [False,True]:
            envs=[]
            for i,k in enumerate(keys):
                row=next(r for r in view['results'] if r['state']==state and r['face']['id']==k)
                envs.append(dict(grid=row['model_surface_refinement'][-1]['spatial_grid'],occluder_K=occluder,space_K=3.,solar_W_m2=1361. if sun and i==1 else 0.))
            for R in [None,nominal_R,1.5,2.]:
                links=[] if R is None else [dict(**ep,R_K_W=R) for ep in endpoints]
                r=solve(sheets,[load],links,envs);r.update(state=state,occluder_K=occluder,sun_on_plus_Y=sun,per_link_R_K_W=R,case_C=r['source_peak_C'][0]+q*Rc,geometry_built=R is not None,resistance_scenario='NOMINAL_1D_TYPICAL_INTERFACE_NOT_GUARANTEED' if R==nominal_R else 'DISCONNECTED_COUNTERFACTUAL' if R is None else 'LINK_R_SENSITIVITY',CHB_only=True)
                rows.append(r)
    tests=[]
    # Independent exact uniform isothermal relation with uniform source.
    f=dict(id='VERIFY_RECTANGLE',face_size_mm=[100,80],holes_ab_d_mm=[]);s=Sheet(f,pitch=10)
    eq=solve([s],[dict(sheet=0,center=[0,0],size=[100,80],power_W=4)],[],[dict(uniform_F=.4,occluder_K=330.)])
    expected=(4/(.008*.89*SIGMA)+.4*330**4+.6*3**4)**.25-273.15
    tests.append(dict(name='uniform_sheet_independent_Stefan_Boltzmann',passed=abs(eq['source_peak_C'][0]-expected)<1e-7))
    # Equal surfaces, no local heat; hot surroundings force negative a->b flow.
    signed=solve([s,s],[],[dict(a=dict(sheet=0,center=[0,0],size=[100,80]),b=dict(sheet=1,center=[0,0],size=[100,80]),R_K_W=.5)],[dict(uniform_F=0,space_K=250),dict(uniform_F=1,occluder_K=350)])
    tests.append(dict(name='unclipped_reverse_heat_flow',passed=signed['link_heat_a_to_b_W'][0]<0 and abs(signed['balance_error_W'])<1e-7))
    tests.append(dict(name='all_energy_balances',passed=all(abs(r['balance_error_W'])<1e-7 for r in rows)))
    actual_areas=[read('results/BOTTOM_MOUNT_GEOMETRY.json')['actual_outward_planar_radiating_area_mm2'],g['outward_radiating_face_area_mm2_by_side']['1'],g['outward_radiating_face_area_mm2_by_side']['-1']]
    errors=[float(s.area.sum()*1e6-a) for s,a in zip(sheets,actual_areas)]
    tests.append(dict(name='all_three_flat_face_masks_match_CAD_within5mm2',passed=max(abs(x) for x in errors)<5,quadrature_area_errors_mm2=errors))
    tests.append(dict(name='actual_joint_R_greater_than_TIM_alone',passed=nominal_R>terms['TIM_typical25psi']))
    # Mesh convergence on the actual, folded330K,+Y solar geometry scenario.
    rr=[next(r for r in view['results'] if r['state']=='released' and r['face']['id']==k) for k in keys]
    env=[dict(grid=r['model_surface_refinement'][-1]['spatial_grid'],occluder_K=330.,space_K=3.,solar_W_m2=1361. if i==1 else 0.) for i,r in enumerate(rr)]
    links=[dict(**ep,R_K_W=nominal_R) for ep in endpoints];refinement=[]
    for pitch in [10.,5.,2.5]:
        ss=[Sheet(faces[k],cfg if i==0 else None,pitch=pitch) for i,k in enumerate(keys)]
        r=solve(ss,[load],links,env);refinement.append(dict(pitch_requested_mm=pitch,case_C=r['source_peak_C'][0]+q*Rc,balance_error_W=r['balance_error_W']))
    delta=abs(refinement[-1]['case_C']-refinement[-2]['case_C']);tests.append(dict(name='last_mesh_refinement_within1C',passed=delta<1,delta_C=delta))
    added=[]
    for watts in [5.,10.]:
        # An explicit heat reserve sensitivity, not an invented actual module.
        r=solve(sheets,[load,dict(sheet=0,center=c['center_xy_mm'],size=[58,62],power_W=watts)],links,env)
        added.append(dict(extra_unassigned_heat_W=watts,case_C=r['source_peak_C'][0]+q*Rc,reserve_allocated=False,**r))
    pressure_sensitivity=[];preload=[]
    for datum in c.get('TIM_impedance_vs_pressure',[]):
        psi=datum['psi'];ip=datum['C_in2_W'];R=nominal_R-terms['TIM_typical25psi']+ip*25.4**2/(contact*1e6)
        rc=Rc-tim_impedance*25.4**2/g['CHB_TIM_contact_area_mm2']+ip*25.4**2/g['CHB_TIM_contact_area_mm2']
        result=solve(sheets,[load],[dict(**ep,R_K_W=R) for ep in endpoints],env)
        pressure_sensitivity.append(dict(psi=psi,typical_C_in2_W=ip,case_C=result['source_peak_C'][0]+q*rc,actual_pressure_verified=False,state='released',occluder_K=330.,sun_on_plus_Y=True,solar_W_m2=1361.,pitch_requested_mm=5.,all_three_TIMs_at_same_reference_pressure=True,balance_error_W=result['balance_error_W'],residual_max_W=result['residual_max_W'],per_link_R_K_W=R,case_interface_R_K_W=rc))
        pressure_N_mm2=psi*.006894757293168
        preload.append(dict(psi=psi,pressure_N_mm2=pressure_N_mm2,CHB_total_uniform_force_N=pressure_N_mm2*g['CHB_TIM_contact_area_mm2'],CHB_mean_per4_screws_N=pressure_N_mm2*g['CHB_TIM_contact_area_mm2']/4,each_wall_total_uniform_force_N=pressure_N_mm2*contact*1e6,each_wall_mean_per2_screws_N=pressure_N_mm2*contact*1e6/2,actual_pressure_distribution_or_torque_verified=False))
    if pressure_sensitivity:
        pp25=next(r for r in pressure_sensitivity if r['psi']==25)
        nominal=next(r for r in rows if r['state']=='released' and r['occluder_K']==330 and r['sun_on_plus_Y'] and r['per_link_R_K_W']==nominal_R)
        tests.append(dict(name='pressure_scenarios_energy_and_25psi_same_case',passed=all(abs(r['balance_error_W'])<1e-7 for r in pressure_sensitivity) and abs(pp25['case_C']-nominal['case_C'])<1e-8))
    out=dict(schema='WP10_SPATIAL_RADIATOR_NETWORK_SCREEN_V2_ACTUAL_COLD_PATH',inputs={p:sha(p) for p in ['thermal/RADIATOR_MESH_VIEW_SCREEN.json','thermal/BOTTOM_RADIATOR_MOUNT.json','results/FIXED_HEAT_GEOMETRY.json','results/COLD_PATH_GEOMETRY.json','mechanical/FIXED_HEAT_INSTANCE_PLAN.json']},source_sha256=sha('tools/spatial_radiator_network.py'),rows=rows,checks=tests,checks_passed=all(t['passed'] for t in tests),checks_are_numerical_not_thermal_release=True,source_load_W=q,case_interface_R_K_W=Rc,links_endpoints=endpoints,links_are_unbuilt=False,link_nominal_1D_terms_K_W=terms,link_nominal_1D_R_K_W=nominal_R,link_model_role='1D centerline sensitivity; bends/3D constriction/partial screw bore sections and mounted contact may change R; not guaranteed maximum R',mesh_refinement=refinement,unassigned_extra_heat_sensitivity=added,environment_is_illustrative_not_orbit_bound=True,other_module_heat_not_included=True,continuous_full_vehicle_thermal_verified=False,omissions=['uncertain local Monte Carlo view fractions and interpolation','gray multi-bounce exchange between components','EOL coating/contact/pressure variation','3D spreading and clamp stresses','PCB/THN/brake/battery/PMM heat','orbital attitude and external flux histories','temperature dependence of k','harness changes and as-built properties'])
    if c.get('TIM_family'):
        out['selected_TIM_family']=c['TIM_family'];out['inputs']['sources/COLD_TIM_SELECTION.json']=sha('sources/COLD_TIM_SELECTION.json')
        out['pressure_sensitivity']=pressure_sensitivity;out['uniform_pressure_clamp_force_requirements']=preload
        out['TIM_pressure_scope']='D5470 reference impedance already includes both interfaces; no extra t/kA. Nominal uncompressed geometry does not prove pressure. Clamp force uses psi*0.006894757293168 N/mm2, not the TDS conversion-page typo.'
    (A/'thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(dict(checks=tests,rows=[{k:r[k] for k in ['state','sun_on_plus_Y','per_link_R_K_W','case_C','link_heat_a_to_b_W']} for r in rows]),indent=2));assert out['checks_passed']
if __name__=='__main__':main()
