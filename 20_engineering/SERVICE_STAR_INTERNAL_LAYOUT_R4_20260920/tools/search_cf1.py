from geometry import *
import math

def run():
    impl=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
    receipt=read(impl/'cf1_layout_thermal/results/mechanical/MODULE_POSE_NARROWPHASE_CF1.json');p=impl/receipt['module_step'];assert sha(p)==receipt['module_step_sha256'];module=load(p)
    rows=state_rows()['service'];mount=read(D/'inputs/MOUNT_LAYOUT.json');repl={r['id']:r for r in mount['replacements']};rows=[repl.get(r['id'],r) for r in rows]+mount['additions']
    trials=[];best=None
    for angle,tx,ty,tz in [(90,x,y,z) for x in [-152,-148,-156] for y in [-50,-42,-58] for z in [52,58]]:
        a=math.radians(angle);T=[[math.cos(a),-math.sin(a),0,tx],[math.sin(a),math.cos(a),0,ty],[0,0,1,tz],[0,0,0,1]]
        s=moved(module,T);hits=[];unknown=[];broad=0
        for row in candidates(s,rows):
            broad+=1
            try:v=g.volume(common(s,source(row)))
            except Exception:unknown.append(row['id']);continue
            if v>1e-6:hits.append({'id':row['id'],'volume_mm3':v,'role':row.get('representation_role')})
        score=sum(r['volume_mm3'] for r in hits);trial={'Rz_deg':angle,'translation_mm':[tx,ty,tz],'T_S_module':T,'collisions':hits,'unknown':unknown,'total_overlap_mm3':score,'broad_pairs':broad}
        trials.append(trial);print('CF1',tx,ty,tz,'hits',len(hits),'volume',round(score,3),'unknown',len(unknown),flush=True)
        if best is None or score<best['total_overlap_mm3']:best=trial
        if not hits and not unknown:
            r=emit('CF1_ROTATED_SPACE_CANDIDATE',s,'HISTORICAL_MODULE_SPACE_CANDIDATE_NOT_V36_ELECTRICAL',electrical_version='V30_geometry_only',electrical_qualified=False)
            write(D/'inputs/CF1_SPACE_CANDIDATE.json',{'row':r,'pose':trial,'installed':False});break
    write(D/'results/CF1_ROTATION_SEARCH.json',{'scope':'18 bounded 90-degree rotation/translation candidates; full controlled V30 56-instance module versus current canonical service geometry','source_path':str(p),'source_sha256':sha(p),'trials':trials,'best':best,
        'feasible_pose_found':any(not t['collisions'] and not t['unknown'] for t in trials),'V36_electrical_credit':False,'thermal_credit':False})

if __name__=='__main__':run()
