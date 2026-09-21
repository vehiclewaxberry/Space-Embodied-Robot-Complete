"""Compose WP09 host + WP10 installations + R17 mechanical increments explicitly."""
from native_integrate import *
import copy, re
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]

def main():
    baseline=read(OUT/'inputs/NATIVE_COPY_PLAN.json')['hierarchy']
    inc=read(OUT/'inputs/WP10_INCREMENT_MAP.json');r17=read(OUT/'inputs/R17_FORWARD_MAP.json')
    merged=read(OUT/'results/INTERFACE_MERGE.json');imports=read(OUT/'inputs/INCREMENT_IMPORT_PLAN.json')
    assert merged['candidate_count']==9 and merged['blocked_count']==0
    jobs=copy.deepcopy(imports['parts'])
    for row in merged['rows']:
        src=row['output'];facts=row['candidate_facts'];assert m.sha(src['path'])==src['sha256']
        ident='I_'+src['sha256'][:16]
        jobs.append({'id':ident,'step_path':src['path'],'source_sha256':src['sha256'],
            'native_path':str(OUT/'native'/(ident+'.SLDPRT')),'expected_solids':facts['solid_count'],
            'expected_local_bbox_mm':[facts['bbox_mm']['min_mm'],facts['bbox_mm']['max_mm']],
            'expected_volume_mm3':facts['volume_mm3'],'representation_role':'MERGED_HOLE_PRESERVING_INTERFACE_CANDIDATE',
            'material_density_kg_m3':2700.,'material_status':'UNIFORM_ALUMINIUM_GROUND_CANDIDATE',
            'instance_refs':[{'instance_id':row['host_id'],'map':'MERGE'}]})
    assert len({x['source_sha256'] for x in jobs})==len(jobs)
    jobs_by_hash={x['source_sha256']:x for x in jobs}
    write(OUT/'inputs/ALL_IMPORT_PLAN.json',{'status':'SOURCE_BOUND_IMPORT_PLAN','parts':jobs,
        'whole_design_complete':False,'parent_plan_sha256':m.sha(OUT/'inputs/INCREMENT_IMPORT_PLAN.json'),
        'merge_receipt_sha256':m.sha(OUT/'results/INTERFACE_MERGE.json')})
    bgroups={g['id']:g for g in baseline['groups']};merged_by_host={x['host_id']:x for x in merged['rows']}
    plan={'status':'GROUND_INTEGRATION_CANDIDATE_PLAN','groups':[],'states':{},'source_maps':{},
        'whole_design_complete':False,'R01_closed_bearing_edges_inherited':False,
        'motion_mates':False,'power_readiness':False,'flight_readiness':False,
        'CF1_colliding_module_installed':False,'v36_three_complete_PCBA_installed':False,
        'OEM_propulsion_selection_frozen':False,'full_material_assignment':False}
    for f in ['NATIVE_COPY_PLAN.json','WP10_INCREMENT_MAP.json','R17_FORWARD_MAP.json']:
        plan['source_maps'][f]=m.sha(OUT/'inputs'/f)
    group_cache={}
    for state,s in baseline['states'].items():
        rows={q['id']:copy.deepcopy(q) for g in s['groups'] for q in bgroups[g]['rows']}
        assert len(rows)==873
        for q in rows.values():
            q['native_path']=str(OUT/'native'/Path(q['native_path']).name);q['integration_lineage']='WP09_RETAINED'
        for ident in inc['states'][state]['remove_ids']: assert rows.pop(ident,None) is not None,ident
        for q in inc['states'][state]['rows']:
            job=jobs_by_hash[q['source_sha256']]
            prev=rows.get(q['id'],{})
            rows[q['id']]={'id':q['id'],'native_path':job['native_path'],'T_S_local':q['T_S_step'],
                'expected_solids':job['expected_solids'],'step_path':q['step_path'],'source_sha256':q['source_sha256'],
                'representation_role':q['source_record'].get('representation_role','CANDIDATE'),
                'parent_assembly':prev.get('parent_assembly','WP10_ELECTRICAL_THERMAL_INSTALLATION'),
                'integration_lineage':'WP10_'+q['operation']}
        assert len(rows)==974
        for q in r17['states'][state]['rows']:
            ident=q.get('host_id') or q['id']
            if q['operation']=='IDENTITY_CONFLICT':
                mr=merged_by_host[ident];src=mr['output'];job=jobs_by_hash[src['sha256']];T=I
                lineage='R17_WP10_CONSERVATIVE_HOLE_MERGE_BEARING_REVIEW_PENDING'
            else:
                src={'path':q['step_path'],'sha256':q['source_sha256']};job=jobs_by_hash[src['sha256']];T=q['T_S_step'];lineage='R17_'+q['operation']
            if q['operation']=='ADD':assert ident not in rows,ident
            else:assert ident in rows,ident
            rows[ident]={'id':ident,'native_path':job['native_path'],'T_S_local':T,'expected_solids':job['expected_solids'],
                'step_path':src['path'],'source_sha256':src['sha256'],'representation_role':q['representation_role'],
                'parent_assembly':q.get('parent_assembly','R17_MECHANICAL'),'integration_lineage':lineage}
        ordered=sorted(rows.values(),key=lambda x:x['id']);assert len(rows)==1110
        state_groups=[]
        for start in range(0,len(ordered),80):
            chunk=ordered[start:start+80]
            signature=json.dumps([{k:q[k] for k in ('id','native_path','T_S_local')} for q in chunk],sort_keys=True,separators=(',',':'))
            ident='DPG_'+hashlib.sha256(signature.encode()).hexdigest()[:12]
            if ident not in group_cache:
                group_cache[ident]={'id':ident,'path':str(OUT/'native'/(ident+'.SLDASM')),'rows':chunk}
            state_groups.append(ident)
        plan['states'][state]={'path':str(OUT/'native'/('SERVICE_STAR_'+state.upper()+'_R1.SLDASM')),
            'groups':state_groups,'leaf_count':len(rows),'expected_solids':sum(q['expected_solids'] for q in rows.values()),
            'scope':'Fixed pose integrated candidate with declared excluded subassemblies and unresolved engineering'}
    plan['groups']=list(group_cache.values());write(OUT/'inputs/INTEGRATED_ASSEMBLY_PLAN.json',plan)
    # Material choices for new source parts; imported compound equipment remains
    # unknown. Geometric fastener candidates receive a documented ground choice.
    mats=read(OUT/'inputs/NATIVE_MATERIAL_PLAN.json')['materials'];by_rho={x['density_kg_m3']:x for x in mats};mp=[]
    for job in jobs:
        ids=sorted({x['instance_id'] for x in job['instance_refs']});rho=job.get('material_density_kg_m3');status=job['material_status']
        if rho is None and ids and all(re.search(r'(screw|washer|nut|bolt)',x,re.I) for x in ids):
            rho=7900.;status='NEW_GROUND_DESIGN_ASSUMPTION_304_NOT_FASTENER_GRADE_APPROVAL'
        mat=by_rho.get(rho)
        mp.append({'native_path':job['native_path'],'instance_ids':ids,'source_STEP_sha256':job['source_sha256'],
            'material_id':mat['material_id'] if mat else None,'sw_material_name':mat['sw_material_name'] if mat else None,
            'density_kg_m3':rho if mat else None,'status':status if mat else 'UNASSIGNED_COMPOSITE_OR_UNKNOWN',
            'assignment_action':'ASSIGN_NATIVE_BULK_MATERIAL' if mat else 'DO_NOT_ASSIGN_BULK_MATERIAL',
            'procurement_material_note':'Ground candidate only. Uniform density is not hardware certification; source and grade require procurement confirmation.'})
    write(OUT/'inputs/INCREMENT_MATERIAL_PLAN.json',{'materials':mats,'parts':mp,'whole_design_complete':False,
        'source_plan_path':str(OUT/'inputs/ALL_IMPORT_PLAN.json'),'source_plan_sha256':m.sha(OUT/'inputs/ALL_IMPORT_PLAN.json')})
    print('plan',len(jobs),'imports',len(group_cache),'groups', {k:v['leaf_count'] for k,v in plan['states'].items()})

if __name__=='__main__':main()
