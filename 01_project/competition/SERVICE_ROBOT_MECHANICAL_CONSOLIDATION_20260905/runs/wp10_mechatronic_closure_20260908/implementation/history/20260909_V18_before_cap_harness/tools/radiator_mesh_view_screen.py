"""Refine opaque-box results using SHA-bound source STEP surface meshes."""
from pathlib import Path
import json,gc,hashlib
import numpy as np
import radiator_view_screen as screen
from thermal_ray_bvh import build_bvh,ray_first_hit
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    bounds=json.loads((A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json').read_text());mesh=json.loads((A/'thermal/RADIATOR_MESH_MANIFEST.json').read_text());cfg=json.loads((A/'thermal/FIXED_HEAT_PATH.json').read_text())
    assert mesh['bounds_input_sha256']==sha(A/'thermal/RADIATOR_OBSTACLE_BOUNDS.json')
    assert mesh['source_plan_sha256']==sha(A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json')
    assert json.loads((A/'results/THERMAL_RAY_BVH_VERIFICATION.json').read_text())['checks_passed']
    faces=[dict(id='FIXED_'+('PLUS' if p['side']>0 else 'MINUS')+'_Y',owner_id=p['parent_id'],normal_axis=1,normal_sign=p['side'],
      tangent_axes=[0,2],origin_S_mm=[0,p['side']*cfg['external_face_abs_y_mm'],0],face_size_mm=p['face_size_mm'],holes_ab_d_mm=p['holes_xz_d_mm'],surface_built=True) for p in cfg['panels']]
    bottom=json.loads((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_text());bg=json.loads((A/'results/BOTTOM_MOUNT_GEOMETRY.json').read_text())
    assert bg['checks_passed'] and bg['source_config_sha256']==sha(A/'thermal/BOTTOM_RADIATOR_MOUNT.json')
    holes=[[*xy,bottom['countersink_outer_diameter_mm']] for xy in bottom['mount_centers_xy_mm']]
    q=bottom['pillar_edge_notches'];holes += [[x,y,q['diameter_mm']] for x in q['x_mm'] for y in q['y_mm']]
    cold=bottom.get('chb_path',{}).get('enabled',False)
    if cold:
        c=bottom['chb_path'];x,y=c['center_xy_mm']
        holes += [[x+dx,y+dy,bottom['countersink_outer_diameter_mm']] for dx in c['oem_hole_x_offsets_mm'] for dy in c['oem_hole_y_offsets_mm']]
    faces += [dict(id='PROPOSED_PLUS_X_FIXED_SKIN',owner_id='PROPOSED_PLUS_X_FIXED_SKIN',normal_axis=0,normal_sign=1,tangent_axes=[1,2],origin_S_mm=[185,0,0],face_size_mm=[214,214],surface_built=False),
      dict(id='FIXED_MINUS_Z_BOTTOM_PLATE',owner_id='radiator_spreader',normal_axis=2,normal_sign=-1,tangent_axes=[0,1],origin_S_mm=[0,0,bottom['outer_z_mm']],face_size_mm=bottom['base_size_mm'][:2],surface_built=True,
        holes_ab_d_mm=holes,exact_CAD_outward_flat_area_mm2=bg['actual_outward_planar_radiating_area_mm2'],thermal_connection_to_CHB_installed=cold,
        placement_basis='Actual bottom flat face with current mounting and CHB countersinks plus partial edge notches; countersink conical walls not credited as extra radiating area.')]
    results=[]
    for state,rows in bounds['states'].items():
        meta=mesh['states'][state];path=A/meta['path'];assert sha(path)==meta['sha256']
        with np.load(path) as data:tri=data['triangles'];owner=data['owners']
        mapping={r['id']:i for i,r in enumerate(meta['rows'])};cache={}
        def trace(points,directions,obstacles):
            key=tuple(r['id'] for r in obstacles)
            if key not in cache:
                cache.clear();gc.collect();assert set(key)<=set(mapping)
                selected=np.array([mapping[k] for k in key]);mask=np.isin(owner,selected)
                reverse=np.full(len(meta['rows']),-1,np.int32);reverse[selected]=np.arange(len(key))
                if not mask.any():cache[key]=None
                else:cache[key]=build_bvh(tri[mask],reverse[owner[mask]])
            if cache[key] is None:return np.full(len(points),-1,np.int32)
            hit,_=ray_first_hit(points,directions,*cache[key]);return hit
        screen.trace=trace
        for face in faces:
            refinement=[screen.sample_face(face,rows,power) for power in [14,16]]
            extended=screen.sample_face(face,rows,16,True)
            delta=abs(refinement[-1]['estimated_opaque_box_obstruction_fraction']-refinement[-2]['estimated_opaque_box_obstruction_fraction'])
            # Common sampling helper's legacy key renamed: these are triangle
            # hits, not opaque-box hits. BBoxes only cull impossible obstacles.
            for r in refinement+[extended]:r['estimated_model_surface_obstruction_fraction']=r.pop('estimated_opaque_box_obstruction_fraction')
            r=dict(state=state,face=face,model_surface_refinement=refinement,geometry_plus_functional_envelopes=extended,
              last_refinement_obstruction_delta=delta,finite_sample_certified_bound=False)
            results.append(r)
            print(json.dumps(dict(state=state,face=face['id'],obstruction=refinement[-1]['estimated_model_surface_obstruction_fraction'],envelope_obstruction=extended['estimated_model_surface_obstruction_fraction'],delta=delta)),flush=True)
        cache.clear();del tri,owner;gc.collect()
    checks=[dict(name='all12state_faces',passed=len(results)==12),dict(name='last_refinement_within0p01_fraction',passed=all(r['last_refinement_obstruction_delta']<.01 for r in results)),
      dict(name='envelopes_do_not_reduce_sampled_obstruction',passed=all(r['geometry_plus_functional_envelopes']['estimated_model_surface_obstruction_fraction']>=r['model_surface_refinement'][-1]['estimated_model_surface_obstruction_fraction'] for r in results))]
    out=dict(schema='WP10_SAME_STATE_STEP_MESH_VIEW_SCREEN_V3_COLD_PATH',inputs={p:sha(A/p) for p in ['thermal/RADIATOR_OBSTACLE_BOUNDS.json','thermal/RADIATOR_MESH_MANIFEST.json','mechanical/FIXED_HEAT_INSTANCE_PLAN.json','thermal/BOTTOM_RADIATOR_MOUNT.json','results/BOTTOM_MOUNT_GEOMETRY.json','thermal/FIXED_HEAT_PATH.json','results/FIXED_HEAT_GEOMETRY.json']},
      source_sha256=sha(__file__),checks=checks,checks_passed=all(c['passed'] for c in checks),results=results,
      method='Cosine-weighted4D Sobol rays against triangulated current STEP solids; AABBs only for conservative candidate culling; scalar area integral independently checked',
      limitations=['Source proxy geometry is not as-built','0.15mm surface mesh nominal deflection; not exact BRep intersection or rigorous view-factor interval','Proposed +X/-Z surfaces are numerical layout probes, not installed radiator area','No orbital Sun/Earth direction or temperature bound','No multi-reflection or grey-body radiosity network'],
      full_thermal_qualification=False,whole_design_complete=False)
    assert out['checks_passed'];(A/'thermal/RADIATOR_MESH_VIEW_SCREEN.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
if __name__=='__main__':main()
