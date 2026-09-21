"""Package hash-bound CAD cache + accepted B601 STL; no CAD kernel or simulation."""
from pathlib import Path
import argparse, ast, datetime, hashlib, json, math, shutil, struct, sys
import xml.etree.ElementTree as ET
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = Path('F:/China Graduate Future Flight Vehicle Innovation Competition')
RUNTIME_MAP = Path('F:/codex_skill/AgentSkills/codex-skills/cad-viewer/scripts/viewer/dist/assets/vendor-three-C9GQa7gb.js.map')
URDF = PROJECT/'20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
STATES = ('parking', 'released', 'service')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def ensure(ok,msg):
    if not ok:raise ValueError(msg)

def closure_hash(candidate, names):
    h=hashlib.sha256()
    for name in sorted(names):
        p=(candidate/name).resolve()
        value='ast1:'+hashlib.sha256(ast.dump(ast.parse(p.read_bytes())).encode()).hexdigest() if p.suffix=='.py' else sha(p)
        h.update(name.encode()+b'\0'+value.encode()+b'\0')
    return h.hexdigest()

def copy_asset(src,folder,suffix=None):
    digest=sha(src);dest=folder/(digest+(suffix or src.suffix.lower()))
    if not dest.exists():shutil.copyfile(src,dest)
    ensure(sha(dest)==digest,'COPIED_ASSET_HASH_MISMATCH')
    return {'url':'assets/'+dest.name,'sha256':digest,'bytes':dest.stat().st_size,'source_path':str(src.resolve())}

def mesh_vertices(p):
    """GLB glTF accessor positions are metres; do not confuse CAD's mm matrix."""
    b=p.read_bytes();ensure(b[:4]==b'glTF','NOT_GLB')
    n=struct.unpack_from('<I',b,12)[0];d=json.loads(b[20:20+n]);binary_start=20+n+8
    # CAD component exports have identity nodes. Refuse new unexplained transforms.
    for node in d.get('nodes',[]):
        ensure(not any(k in node for k in ('matrix','rotation','translation','scale')),'UNSUPPORTED_GLB_NODE_TRANSFORM')
    positions=[d['accessors'][prim['attributes']['POSITION']] for mesh in d.get('meshes',[]) for prim in mesh['primitives'] if 'POSITION' in prim.get('attributes',{})]
    ensure(positions,'GLB_NO_POSITIONS')
    arrays=[]
    for a in positions:
        ensure(a['componentType']==5126 and a['type']=='VEC3','UNSUPPORTED_POSITION_ENCODING')
        v=d['bufferViews'][a['bufferView']];offset=binary_start+v.get('byteOffset',0)+a.get('byteOffset',0)
        arrays.append(np.ndarray((a['count'],3),dtype='<f4',buffer=b,offset=offset,strides=(v.get('byteStride',12),4)).astype(float)*1000)
    return np.concatenate(arrays)

def group(row):
    if row.get('arm_link'):return 'arm'
    if row['representation_role']=='FUNCTIONAL_ENVELOPE':return 'envelopes'
    name=row['id']
    parent=row.get('parent_assembly')
    if parent=='SOLAR_WING' or name.startswith('wing_'):return 'wings'
    if parent in ('ROOT_STRUCTURE','PRIMARY_STRUCTURE','COVERS','R01_FASTENERS','R07_CONNECTIONS','LAUNCH_INTERFACE') or name.startswith(('deck_','shear_web','r01_','R01_','R07_','r07_','launch_interface','panel_','edge_angle')) or '_deck' in name:return 'structure'
    if parent in ('EQUIPMENT_BAY','THERMAL','EXTERNAL_INTERFACES'):return 'equipment'
    if name.startswith(('equipment_','adapter_','thermal_','battery_','navigation_','communications_','mount_')):return 'equipment'
    return 'mechanisms'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,default=HERE.parent/'candidate');ap.add_argument('--development',action='store_true');args=ap.parse_args()
    candidate=args.candidate.resolve();assets=HERE/'assets';assets.mkdir(exist_ok=True)
    if not args.development:ensure(candidate==HERE.parent/'candidate','FINAL_REQUIRES_THIS_RUN_CANDIDATE')
    inputs={};checks=[];out={'schema':1,'development':args.development,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate_path':str(candidate),'run_id':candidate.parent.name,'units':'metres','frame':'S; +Z up','representation':'Fresh non-arm BRep tessellation + accepted B601 STL; no monolithic arm STEP rebuild','scope':'Discrete design poses only; no continuous-motion, collision, physical-assembly or flight-release credit','states':{},'arm_assets':{}}
    # Recover unchanged, licensed, locally installed Three.js r161 sources.
    source_map=load(RUNTIME_MAP);inputs[str(RUNTIME_MAP)]=sha(RUNTIME_MAP)
    wanted={'build/three.module.js','examples/jsm/controls/OrbitControls.js','examples/jsm/loaders/GLTFLoader.js','examples/jsm/loaders/STLLoader.js','examples/jsm/utils/BufferGeometryUtils.js'}
    for name,content in zip(source_map['sources'],source_map['sourcesContent']):
        rel=name.split('/node_modules/three/',1)[-1]
        if rel in wanted:
            dest=HERE/'vendor/three'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content,encoding='utf-8');wanted.remove(rel)
    ensure(not wanted,'MISSING_LOCAL_THREE_SOURCE')
    (HERE/'vendor/THIRD_PARTY_NOTICE.txt').write_text('Three.js r161. Copyright 2010-2023 Three.js Authors. MIT license. Sources recovered unchanged from the installed CAD Viewer source map. Original license headers retained.\n'+str(RUNTIME_MAP),encoding='utf-8')
    tree=ET.parse(URDF).getroot();inputs[str(URDF)]=sha(URDF)
    for link in tree.findall('link'):
        visual=link.find('visual');origin=visual.find('origin');mesh=visual.find('geometry/mesh')
        ensure(origin is None or all(float(x)==0 for x in (origin.get('xyz','0 0 0')+' '+origin.get('rpy','0 0 0')).split()),'NONZERO_URDF_VISUAL_ORIGIN')
        ensure(mesh.get('scale','1 1 1')=='1 1 1','UNSUPPORTED_URDF_MESH_SCALE')
        p=(URDF.parent/mesh.get('filename')).resolve();a=copy_asset(p,assets);inputs[str(p)]=a['sha256'];out['arm_assets'][link.get('name')]=a
    for state in STATES:
        rp=candidate/'results'/f'{state}_instances.json';r=load(rp);inputs[str(rp)]=sha(rp)
        ensure(r['state']==state and r['view']=='complete','RECEIPT_NOT_COMPLETE_STATE')
        ensure(r['source_sha256']==sha(candidate/'spacecraft_model.py'),'STALE_RECEIPT_MODEL')
        for name,digest in r['dependency_sha256'].items():
            p=(candidate/name).resolve();ensure(sha(p)==digest,'STALE_RECEIPT_DEPENDENCY:'+name);inputs[str(p)]=digest
        for name,digest in r['geometry_sha256'].items():
            p=Path(name);ensure(sha(p)==digest,'STALE_RECEIPT_GEOMETRY');inputs[str(p)]=digest
        rows={x['id']:x for x in r['instances']};ensure(len(rows)==len(r['instances']),'DUPLICATE_INSTANCE')
        cache=candidate/'__cadgen__/models'/f'servicer_structure_{state}.step.py';mp=cache/'assembly.json';m=load(mp);inputs[str(mp)]=sha(mp)
        ensure(m['units']=='mm','CACHE_UNITS');ensure(m['sourceHash']==sha(candidate/m['sourcePath']),'CACHE_SOURCE_HASH')
        ensure(m['sourceClosureHash']==closure_hash(candidate,m['sourceClosureFiles']),'CACHE_SOURCE_CLOSURE_STALE')
        ensure(datetime.datetime.fromisoformat(m['generatedAt']).timestamp()+2 >= (candidate/'design_parameters.json').stat().st_mtime,'CACHE_OLDER_THAN_PARAMETER_WRITE')
        for name in m['sourceClosureFiles']:
            p=(candidate/name).resolve();inputs[str(p)]=sha(p)
        nonarm={k for k,v in rows.items() if not v.get('arm_link')}
        ensure(len(m['occurrences'])==len(nonarm) and {x['name'] for x in m['occurrences']}==nonarm,'CACHE_RECEIPT_INSTANCE_COVERAGE')
        comps={};bounds_diff=[];vertices={};intrinsic_count=0
        for cid,item in m['components'].items():
            p=(cache/item['glb']).resolve();a=copy_asset(p,assets);inputs[str(p)]=a['sha256'];comps[cid]=a;vertices[cid]=mesh_vertices(p)
        records=[]
        for occurrence in m['occurrences']:
            row=rows[occurrence['name']];outer=[v for line in row['T_S_local'] for v in line];t=occurrence['transform'];matrix=np.array(t).reshape(4,4)
            intrinsic_count+=max(abs(a-b) for a,b in zip(t,outer))>=1e-8
            world=vertices[occurrence['component']]@matrix[:3,:3].T+matrix[:3,3];meshb=[world.min(axis=0),world.max(axis=0)];rb=row['bounds'];diff=max(abs(meshb[j][i]-rb[key][i]) for j,key in enumerate(('min_mm','max_mm')) for i in range(3))
            bounds_diff.append({'id':row['id'],'max_world_bbox_difference_mm':float(diff)})
            records.append({'id':row['id'],'component':occurrence['component'],'matrix_mm':t,'receipt_outer_matrix_mm':outer,'color':occurrence.get('color',[.6,.7,.8,1]),'group':group(row),'representation_role':row['representation_role'],'pn':row.get('pn'),'mass_kg':row.get('mass_kg'),'mass_source':row.get('mass_source'),'mount_interface':row.get('mount_interface'),'parent_assembly':row.get('parent_assembly'),'source_revision':row.get('source_revision'),'qualification_status':row.get('qualification_status')})
        armrows=[v for v in rows.values() if v.get('arm_link')];ensure(len(armrows)==10 and {v['arm_link'] for v in armrows}==set(out['arm_assets']),'ARM_COVERAGE')
        for row in armrows:
            ensure(row['T_S_local']==r['link_transforms'][row['arm_link']],'ARM_POSE_MISMATCH')
            records.append({'id':row['id'],'arm_link':row['arm_link'],'matrix_mm':[v for line in row['T_S_local'] for v in line],'group':'arm','representation_role':'ACCEPTED_STL_DIGITAL_REPRESENTATION','pn':row['pn'],'mass_kg':row.get('mass_kg'),'mass_source':row.get('mass_source'),'mount_interface':row.get('mount_interface'),'parent_assembly':'B601_ARM','qualification_status':'NOT_EVALUATED'})
        # This comparison checks display scale/placement only; meshing can inset curved BRep extrema.
        largest=max(bounds_diff,key=lambda x:x['max_world_bbox_difference_mm'])
        ensure(largest['max_world_bbox_difference_mm']<2,'RENDER_BOUNDS_DIFFER_OVER_2_MM:'+str(largest))
        out['states'][state]={'configuration':r['configuration'],'q_deg':r['q_deg'],'finger_mm':r['finger_mm'],'receipt':ref(rp),'cache':ref(mp),'components':comps,'occurrences':records,'counts':{'total':len(records),'nonarm':len(nonarm),'arm':len(armrows),'unknown_mass':sum(x.get('mass_source')=='UNKNOWN' for x in rows.values())},'nominal_bounds_mm':r['bounds'],'render_bbox_check':{'scope':'Tessellation display scale only; not collision clearance','largest_difference':largest}}
        checks.append({'state':state,'status':'PASS_DISPLAY_BINDING_ONLY','count':len(records),'parts_with_internal_brep_transform':int(intrinsic_count),'transform_basis':'Actual CAD cache occurrence matrices, including internal BRep placements; metres vertices and millimetres translations','mesh_world_bounds_largest_difference':largest})
    hp=candidate/'results/DYNAMICS_HANDOFF.json'
    if hp.is_file():
        h=load(hp);inputs[str(hp)]=sha(hp)
        for state in STATES:
            ensure(h['receipt_bindings'][state]['receipt_sha256']==out['states'][state]['receipt']['sha256'],'HANDOFF_RECEIPT_MISMATCH')
            hs=next(s for s in h['states'] if s['state']==state);g=hs['groups']['ONBOARD_CANDIDATE']
            ensure(g['instance_count']==out['states'][state]['counts']['total'],'HANDOFF_COUNT_MISMATCH')
            out['states'][state]['digital_mass_ledger']={'allocated_mass_kg':g['known_mass_kg'],'allocated_instances':len(g['mass_atoms']),'unknown_instances':len(g['unknown_mass_instances']),'handoff':ref(hp),'physical_mass_complete':hs['onboard_full_physical_mass_properties_complete']}
    for p,h in inputs.items():ensure(sha(p)==h,'INPUT_CHANGED_DURING_PACKAGING:'+p)
    out['input_sha256']=inputs
    from serve_viewer import DELIVERABLES
    labels={'overview.md':'本轮设计总览','assembly_procedure.md':'数字装配工艺','mechanical_inputs.md':'待闭环工程输入','result.json':'本轮机器结果','system_interfaces.json':'整机机械接口','digital_body_contract.json':'具身智能数字身体接口','release_state_contract.json':'释放状态合同','BOM.csv':'全机 BOM','design_parameters.json':'设计参数','structure_parking.step':'非臂停放 STEP','structure_released.step':'非臂释放 STEP','structure_service.step':'非臂服务 STEP'}
    out['deliverables']=[]
    for url,rel in DELIVERABLES.items():
        p=HERE.parent/rel
        if p.is_file():
            copied=HERE/url.lstrip('/');copied.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,copied);ensure(sha(copied)==sha(p),'DELIVERABLE_COPY_HASH_MISMATCH')
            out['deliverables'].append({'url':url,'label':labels[url.rsplit('/',1)[-1]],'file':ref(p),'packaged_file':ref(copied)})
    (HERE/'scene.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    result={'status':'DEVELOPMENT_OLD_BASELINE' if args.development else 'FULL_ROBOT_DISPLAY_PACKAGE_BOUND','scope':out['scope'],'candidate':str(candidate),'scene':ref(HERE/'scene.json'),'checks':checks,'inputs_count':len(inputs),'assets_count':len(list(assets.iterdir())),'source_inputs_unchanged':True}
    (HERE/'VIEWER_BUILD_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
