"""Finite Sobol cosine-ray screening of current CAD bounding-box obstruction.

Boxes enclose model geometry; sampled fractions are estimates, not certified
view-factor bounds or a thermal qualification. Functional envelopes are kept
as a separate stress result. No physical reflectivity/temperature is inferred.
"""
from pathlib import Path
import json,hashlib
import numpy as np
from scipy.stats import qmc
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def classify(r):
    if r['is_ground_only']:return 'GROUND_ONLY'
    if r.get('representation_role') in ['FUNCTIONAL_ENVELOPE','KEEP_OUT_ENVELOPE']:return 'FUNCTIONAL_ENVELOPE'
    return 'CURRENT_MODEL_GEOMETRY'

def trace(points,directions,rows):
    nearest=np.full(len(points),np.inf);which=np.full(len(points),-1,dtype=np.int32)
    with np.errstate(divide='ignore',invalid='ignore'):
        inv=1/directions
        for i,row in enumerate(rows):
            box=np.asarray(row['bbox_S_mm']);v1=(box[:3]-points)*inv;v2=(box[3:]-points)*inv
            near=np.maximum(np.minimum(v1,v2).max(axis=1),0.);far=np.maximum(v1,v2).min(axis=1)
            valid=(far>=near)&(far>1e-5)&(near<nearest)
            which[valid]=i;nearest[valid]=near[valid]
    return which

def sample_face(face,rows,power,include_envelopes=False,seed=307):
    axis=face['normal_axis'];s=face['normal_sign'];tangent=face['tangent_axes'];origin=np.array(face['origin_S_mm'],dtype=float);size=face['face_size_mm']
    rr=[r for r in rows if r['id']!=face['owner_id'] and classify(r)!='GROUND_ONLY' and
        (include_envelopes or classify(r)!='FUNCTIONAL_ENVELOPE') and
        max(s*(r['bbox_S_mm'][axis]-origin[axis]),s*(r['bbox_S_mm'][axis+3]-origin[axis]))>1e-5]
    u=qmc.Sobol(d=4,scramble=True,seed=seed).random_base2(power);total=0;counts=np.zeros(len(rr),dtype=np.int64)
    hits_grid=np.zeros((12,24),dtype=np.int64);samples_grid=np.zeros_like(hits_grid)
    for i in range(0,len(u),32768):
        v=u[i:i+32768];ab=(v[:,:2]-.5)*np.array(size);keep=np.ones(len(v),dtype=bool)
        for x,z,d in face.get('holes_ab_d_mm',[]):keep&=(ab[:,0]-x)**2+(ab[:,1]-z)**2>(d/2)**2
        v=v[keep];ab=ab[keep];points=np.tile(origin,(len(v),1));points[:,axis]+=s*1e-4
        points[:,tangent[0]]+=ab[:,0];points[:,tangent[1]]+=ab[:,1]
        directions=np.zeros_like(points);rad=np.sqrt(v[:,2]);ang=2*np.pi*v[:,3]
        directions[:,axis]=s*np.sqrt(1-v[:,2]);directions[:,tangent[0]]=rad*np.cos(ang);directions[:,tangent[1]]=rad*np.sin(ang)
        hit=trace(points,directions,rr);total+=len(hit)
        counts+=np.bincount(hit[hit>=0],minlength=len(rr))
        ix=np.minimum((v[:,0]*24).astype(int),23);iz=np.minimum((v[:,1]*12).astype(int),11)
        np.add.at(samples_grid,(iz,ix),1);np.add.at(hits_grid,(iz,ix),(hit>=0).astype(int))
    blocked=int(counts.sum());grid=np.divide(hits_grid,samples_grid,out=np.zeros_like(hits_grid,dtype=float),where=samples_grid>0)
    return dict(sample_power=power,seed=seed,rays_on_net_face=total,candidate_obstacle_count=len(rr),include_functional_envelopes=include_envelopes,
      estimated_opaque_box_obstruction_fraction=blocked/total,estimated_unobstructed_fraction=1-blocked/total,
      geometric_area_net_model_mm2=size[0]*size[1]-sum(np.pi*(d/2)**2 for _,_,d in face.get('holes_ab_d_mm',[])),
      first_hits=[dict(id=r['id'],classification=classify(r),hits=int(n),fraction=n/total) for r,n in zip(rr,counts) if n],
      spatial_grid=dict(shape=[12,24],blocked_fraction=grid.tolist(),samples=samples_grid.tolist()))

def main():
    bounds=json.loads((A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json').read_text());cfg=json.loads((A/'thermal/FIXED_HEAT_PATH.json').read_text())
    faces=[dict(id='FIXED_'+('PLUS' if p['side']>0 else 'MINUS')+'_Y',owner_id=p['parent_id'],normal_axis=1,normal_sign=p['side'],
      tangent_axes=[0,2],origin_S_mm=[0,p['side']*cfg['external_face_abs_y_mm'],0],face_size_mm=p['face_size_mm'],holes_ab_d_mm=p['holes_xz_d_mm']) for p in cfg['panels']]
    results=[]
    for state,rows in bounds['states'].items():
        for face in faces:
            r=[sample_face(face,rows,k) for k in [14,16,18]]
            extended=sample_face(face,rows,18,True)
            delta=abs(r[-1]['estimated_opaque_box_obstruction_fraction']-r[-2]['estimated_opaque_box_obstruction_fraction'])
            results.append(dict(state=state,face=face,model_geometry_refinement=r,geometry_plus_functional_envelopes=extended,
               last_refinement_obstruction_delta=delta,finite_sample_certified_bound=False))
            print(json.dumps(dict(state=state,face=face['id'],obstruction=r[-1]['estimated_opaque_box_obstruction_fraction'],envelope_obstruction=extended['estimated_opaque_box_obstruction_fraction'],delta=delta)),flush=True)
    checks=[dict(name='all_six_state_faces',passed=len(results)==6),
      dict(name='last_refinement_within0p01_fraction',passed=all(r['last_refinement_obstruction_delta']<.01 for r in results)),
      dict(name='envelopes_only_increase_sampled_blockage',passed=all(r['geometry_plus_functional_envelopes']['estimated_opaque_box_obstruction_fraction']>=r['model_geometry_refinement'][-1]['estimated_opaque_box_obstruction_fraction'] for r in results))]
    out=dict(schema='WP10_SAME_STATE_RADIATOR_VIEW_SCREEN_V1',checks=checks,checks_passed=all(c['passed'] for c in checks),
      inputs={p:sha(p) for p in ['thermal/RADIATOR_OBSTACLE_BOUNDS.json','thermal/FIXED_HEAT_PATH.json']},source_sha256=sha('tools/radiator_view_screen.py'),results=results,
      surface_role='Current CAD face with bolt/tool holes removed; physical assembly not measured',
      method='4D scrambled Sobol: uniform face origins and cosine-weighted outward directions; first intersection with opaque union of current world AABBs',
      limits=['AABBs conservatively fill curved-part voids and apertures; model proxies remain proxies','Finite samples and refinement do not prove exact geometric upper/lower bounds','No orbital Sun/Earth orientation or temperatures bound','Opaque enclosure source frames must be corrected before independent STEP reproduction','No multi-bounce grey-body radiosity or thermal-network coupling yet'],
      orbit_thermal_verified=False,whole_design_complete=False)
    assert out['checks_passed'];(A/'thermal/RADIATOR_VIEW_SCREEN.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
if __name__=='__main__':main()
