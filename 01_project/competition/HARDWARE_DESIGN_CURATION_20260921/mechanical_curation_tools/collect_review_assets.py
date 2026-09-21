"""Collect exact current local mechanical assets, without reading/modifying CAD."""
from curate_native import *
from collections import Counter
J=read(OUT/'inputs/MECHANICAL_COPY_PLAN.json');plan=read(SRC/'inputs/NATIVE_ASSEMBLY_PLAN.json')
CUR=ROOT/'01_project/competition/HARDWARE_DESIGN_CURATION_20260921';CUR.mkdir(exist_ok=True,parents=True)
records=[];active={n['source']:n for n in J['nodes']};bygroup={x['id']:x for x in J['groups']}
def item(source,role,reason,include_type='public_candidate',deps=None,**kw):
    source=Path(source);source=source if source.is_absolute() else ROOT/source
    r=dict(source=rel(source),role=role,reason=reason,include_type=include_type,deps=deps or [],sha256=sha(source),bytes=source.stat().st_size,public_redistribution_clearance='NOT_GRANTED_BY_THIS_SELECTION',**kw);records.append(r);return r
for lock in J['full_source_locks']:
    src=lock['path'];node=active.get(src)
    if node:
        kind=node['kind'];deps=[]
        if kind=='top':deps=[g['source'] for g in J['groups']]
        elif kind=='group':
            ids=[g['id'] for g in J['groups'] if g['source']==src];assert len(ids)==1
            deps=sorted({x['source'] for x in J['leaves'] if x['group']==ids[0]})
        item(src,'CURRENT_R6H_NATIVE_'+kind.upper(),'Current R6H cold-open hierarchy member; required independently of its historical source folder name',deps=deps,target=node['target'])
    else:item(src,'LOCKED_NATIVE_LINEAGE_NOT_CURRENT_SERVICE_DEPENDENCY','Retain original locally for source history; not in current R6H service 15-group / 1153-leaf reference tree','local_only')
copied=[]
def copy_asset(src,dest,role,reason,include_type='public_candidate',deps=None):
    src=Path(src);dst=own(OUT/dest);dst.parent.mkdir(exist_ok=True,parents=True);assert not dst.exists();h=sha(src);shutil.copy2(src,dst);assert sha(dst)==h
    x=item(src,role,reason,include_type,deps,target=str(dst.relative_to(OUT)).replace('\\','/'));copied.append(dict(source=rel(src),target=x['target'],sha256=h,bytes=dst.stat().st_size));return x
for p in sorted({Path(x['step_path']) for x in plan['parts']}):
    copy_asset(p,'step/'+p.name,'CURRENT_R6H_LOCAL_INCREMENT_STEP','27 current local added/replaced part geometries; not a whole-spacecraft STEP export')
for p in sorted((SRC/'views').iterdir()):
    if p.name in ['R6H_HORIZONTAL_INSTALLATION.png','R6H_HORIZONTAL_INSTALLATION_VIEWER.html']:copy_asset(p,'views/'+p.name,'CURRENT_R6H_OFFLINE_LOCAL_VIEW','Actual STEP mesh views of horizontal installation / supports / interface thermal bridge / propulsion context; not full spacecraft render')
for name in ['INSTALLATION_BOM_DELTA.csv','INSTALLED_PORT_DATUMS.csv','PROPULSION_ASSEMBLY_HANDOFF.md','PROPULSION_NEXT_WORK_ORDERS.csv']:
    copy_asset(SRC/'docs'/name,'docs/source_R6H/'+name,'CURRENT_INSTALLATION_DOCUMENT','Preserve existing versioned installation / interface / propulsion preparation with original scope and hash')
copy_asset(SRC/'docs/hardware/HORIZONTAL_INSTALLATION.md','docs/source_R6H/HORIZONTAL_INSTALLATION.md','CURRENT_HORIZONTAL_INSTALLATION_INSTRUCTION','Current minimal-change horizontal installation dimensions, assembly order and engineering holds')
for name in ['FINAL_DELIVERY_STATUS.json','NATIVE_HIERARCHICAL_RECHECK_V2.json','INCREMENT_STATIC_CHECK.json','HORIZONTAL_VISUALIZATION.json']:
    copy_asset(SRC/'results'/name,'docs/source_R6H/'+name,'CURRENT_SOURCE_PROOF','Fixed source result only; new compact-reference status is issued separately')
for name in ['FIVE_DIMENSION_REVIEW.md','NATIVE_FINAL_REVIEW.json','GEOMETRY_REVIEW.json','BEARING_STACK_REVIEW.json','SOLIDWISE_CONFIRMATION_REVIEW.json']:
    copy_asset(SRC/'results/reviewer'/name,'docs/source_R6H/reviewer/'+name,'CURRENT_INDEPENDENT_SOURCE_REVIEW','Retain accepted scope, geometry / support limitations and exact native closure evidence')
R1=ROOT/'20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919'
for name in ['NATIVE_MATERIAL_PLAN.json','INCREMENT_MATERIAL_PLAN.json','REFERENCE_MATERIAL_BASIS.json']:
    copy_asset(R1/'inputs'/name,'docs/source_materials/'+name,'INHERITED_MATERIAL_SOURCE','Source trace only; assignment coverage does not automatically become all-current-instance material completeness')
copy_asset(R1/'native/GROUND_CANDIDATE_MATERIALS.sldmat','docs/source_materials/GROUND_CANDIDATE_MATERIALS.sldmat','LOCAL_CUSTOM_MATERIAL_LIBRARY','Preserve optional local edit support; public rights / external library references require separate review','local_only')
oldbom=R1/'docs/BOM_SERVICE_1110.csv';item(oldbom,'HISTORICAL_MATERIAL_METADATA_ONLY','Used only for source-hash-matched metadata; do not present this 1110-row BOM as the current R6H assembly','local_only')
old={x['instance_id']:x for x in csv.DictReader(oldbom.open(encoding='utf-8-sig'))};nodes={x['source']:x for x in J['nodes']};bom=[]
for leaf in J['leaves']:
    n=nodes[leaf['source']];prior=old.get(leaf['id'],{});same=prior.get('native_current_sha256')==n['source_sha256']
    material=prior.get('candidate_material','') if same else '';status=prior.get('material_status','UNKNOWN') if same else 'UNKNOWN_CURRENT_CHANGED_OR_NEW_GEOMETRY'
    if leaf['id']=='R6H_IF_THERMAL_BRIDGE':material='6061 Alloy';status='R6H_NATIVE_MATERIAL_READBACK_CANDIDATE'
    bom.append(dict(instance_id=leaf['id'],parent_group=leaf['group'],quantity=1,native_file=Path(leaf['target']).name,native_source=leaf['source'],native_source_sha256=n['source_sha256'],expected_solids=leaf['expected_solids'],representation_role=leaf['representation_role'],T_S_local_mm_json=json.dumps(leaf['T_S_local'],separators=(',',':')),candidate_material=material,material_status=status,material_metadata_inherited_by_exact_native_hash=same,as_built_mass_kg='',whole_mass_complete=False))
bompath=OUT/'docs/CURRENT_ASSEMBLY_BOM_1153.csv';assert not bompath.exists()
with bompath.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(bom[0]));w.writeheader();w.writerows(bom)
item(bompath,'DERIVED_CURRENT_INSTANCE_BOM','1153 current leaf instances and compact-native mapping; candidate material metadata only when native bytes match, no fabricated whole mass',deps=[J['source_plan']['path'],rel(oldbom)],target='docs/CURRENT_ASSEMBLY_BOM_1153.csv')
W=ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion'
for name in ['portable_prepare.py','portable_redirect.py','portable_cold_v2.py','portable_finalize.py']:
    item(W/'tools'/name,'LOCAL_RELOCATION_METHOD_REFERENCE','Existing hardcoded WP09 method reference; do not execute unadapted against R6H','local_only')
item(OUT/'tools/curate_native.py','CURRENT_COPY_RELINK_VERIFIER','Runs only owned compact copies and read-only cold verification; original-workspace import dependency is explicit','local_only',deps=['20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools/native_integrate.py'])
html=(OUT/'views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html').read_text(encoding='utf-8');external_scripts=re.findall(r'<script[^>]+src=[\"\']([^\"\']+)',html,re.I)
result=dict(schema='HARDWARE_MECHANICAL_SELECTION_V1',scope='Mechanical digital assembly, materials, installation and engineering interface assets only; excludes higher research/control layer',current_top=rel(SRC/'native/SERVICE_STAR_SERVICE_R6H.SLDASM'),current_top_sha256=sha(SRC/'native/SERVICE_STAR_SERVICE_R6H.SLDASM'),current_counts=dict(groups=15,leaf_instances=1153,hash_bound_solid_instances=1602,unique_native_parts=721,current_native_files=737),source_lock_superset=790,excluded_historical_native_files=53,current_native_bytes=sum(x['bytes'] for x in J['nodes']),native_by_source_package=dict(Counter(Path(x['source']).parts[1] for x in J['nodes'])),R7_installed=False,whole_spacecraft_STEP_provided=False,local_current_STEP_files=27,offline_viewer_external_script_sources=external_scripts,records=records,generated_assets=[str(bompath.relative_to(ROOT)).replace('\\','/')],source_files_modified=False,selection_does_not_grant_public_rights=True)
write(CUR/'MECHANICAL_SELECTION.json',result);write(OUT/'results/SUPPLEMENTAL_ASSET_COPY.json',dict(status='PASS_BYTE_IDENTICAL_SELECTED_REVIEW_ASSETS',copies=copied,derived_bom_rows=len(bom),viewer_external_scripts=external_scripts,full_spacecraft_STEP=False));print('SELECTED',len(records),'records; copied',len(copied),'supplemental files; BOM',len(bom),flush=True)
