"""Bind existing outputs and checks without creating a qualification/release gate."""
from pathlib import Path
from collections import Counter
import hashlib,json,csv,datetime
HERE=Path(__file__).resolve().parent
TARGETS=['servicer_service','servicer_parking','servicer_released','body_equipment_cutaway','body_exploded','wing_module','retention_module','ground_ait']
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads((HERE/p).read_text(encoding='utf-8'))
def main():
    sha=digest(HERE/'spacecraft_model.py');configs={}
    for state in ['parking','released','service']:
        p=HERE/f'results/{state}_instances.json';r=read(p)
        if r['source_sha256']!=sha:raise ValueError('Stale '+state)
        if r['T_S_arm_base']!=[[1.,0.,0.,90.],[0.,1.,0.,0.],[0.,0.,1.,125.15],[0.,0.,0.,1.]]:raise ValueError('Root changed')
        for name,h in r['dependency_sha256'].items():
            if digest(HERE/name)!=h:raise ValueError('Stale dependency '+name)
        if any(x['product_role']=='GSE' for x in r['instances']):raise ValueError('GSE in onboard')
        configs[state]={'receipt':str(p.relative_to(HERE)),'receipt_sha256':digest(p),'instance_count':len(r['instances']), 'representation_counts':dict(Counter(x['representation_role'] for x in r['instances'])),'display_geometry_bounds':r['bounds']}
    geo=read('results/GEOMETRY_CHECK.json')
    if geo['source_sha256']!=sha:raise ValueError('Stale geometry check')
    outputs=[]
    for name in TARGETS:
        source=HERE/(name+'.step.py');step=HERE/(name+'.step')
        if not step.is_file() or not source.is_file():raise FileNotFoundError(name)
        package=read(f'__cadgen__/models/{name}.step.py/assembly.json')
        ref=read(f'results/{name}_refs.json')['tokens'][0]
        if ref['stepHash']!=digest(step):raise ValueError('Final STEP/exported-inspection hash mismatch '+name)
        snaps=sorted((HERE/'snapshots').glob(name+'_*.png'))
        if not snaps:raise FileNotFoundError('Missing reviewed snapshot '+name)
        outputs.append({'source':source.name,'step':step.name,'bytes':step.stat().st_size,'sha256':digest(step),'final_inspection_step_hash_matches':True,'render_package_recorded_step_hash':package.get('stepHash'),'render_package_byte_match':package.get('stepHash')==digest(step),'package_source_closure_hash':package.get('sourceClosureHash'),'serialization_note':'Official inspect refs regenerated the same source and reserialized STEP. Original render-package STEP byte hash can differ or be absent; four complete instance receipts remained byte-identical. Rendering and dimensions are checked separately in BOUNDING_METHOD_COMPARISON.','snapshots':[str(x.relative_to(HERE)) for x in snaps]})
    for p in ['BOM.csv','INTERFACES.csv','wp03_interfaces.dxf','drawings/WP03_INTERFACE_DRAWINGS.pdf','drawings/WP03_ASSEMBLY_REVIEW.pdf','results/DYNAMICS_HANDOFF.json','results/INTEGRATE_CHECKS.json','results/CONFIGURATION_DIMENSIONS.json']:
        if not (HERE/p).is_file():raise FileNotFoundError(p)
    result={'schema':'WP03_DESIGN_DELIVERY_RECEIPT_V1','status':'SPACECRAFT_INTEGRATION_CANDIDATE_WITH_DECLARED_LIMITATIONS',
        'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha,
        'configuration_source':'design_parameters.json','configuration_receipts':configs,'outputs':outputs,
        'custom_part_step_count':len(list((HERE/'parts').glob('*.step'))),
        'non_arm_physical_checks':[{'state':c['state'],'physical_instances':c['physical_instance_count'],'pair_count':c['pair_count'],'positive_or_error_pairs':len(c['positive_or_error_pairs']),'invalid_or_open':[v for v in c['validity'] if not(v['valid'] and v['positive_volumes'] and v['shells_closed'])]} for c in geo['checks']],
        'cad_cli_inspection_runs':read('results/CAD_INSPECT_RUNS.json'),'snapshot_runs':read('results/CAD_SNAPSHOT_RUNS.json'),
        'pinned_sources_unchanged':read('results/SOURCE_PRESERVATION_CHECK.json')['all_unchanged'],
        'visual_review':'results/VISUAL_REVIEW.md','dynamics':'results/DYNAMICS_HANDOFF.json','integration':'results/INTEGRATE_CHECKS.json',
        'preserved_path_failure':'results/INTEGRATE_PATH_R1_MATERIAL_REFINEMENT.json',
        'physical_assembly_performed':False,'complete_mass_properties_known':False,'launch_stow_verified':False,'continuous_motion_certified':False,
        'manufacturing_release':False,'flight_qualification':False,'new_dynamics_or_control_validation_performed':False,
        'scope_note':'Source CAD and scoped numerical checks only. Original project gates and accepted hardware geometry are not modified.'}
    (HERE/'results/DELIVERY_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[]
    for p in HERE.rglob('*'):
        if not p.is_file() or any(s in p.parts for s in ['__cadgen__','__pycache__','runtime']):continue
        if p.name=='OUTPUT_SHA256.csv':continue
        files.append({'path':str(p.relative_to(HERE)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':digest(p)})
    with (HERE/'OUTPUT_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(sorted(files,key=lambda x:x['path']))
    print('Bound',len(outputs),'primary STEP outputs;',result['custom_part_step_count'],'custom parts;',len(files),'manifest entries')
if __name__=='__main__':main()
