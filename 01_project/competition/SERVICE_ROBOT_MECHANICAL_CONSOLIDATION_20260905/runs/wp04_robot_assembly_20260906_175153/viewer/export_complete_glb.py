"""Merge existing GLB buffers and original STL vertices without a CAD kernel."""
from pathlib import Path
import copy,datetime,hashlib,json,struct
import numpy as np

HERE=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def ensure(ok,msg):
    if not ok:raise ValueError(msg)
def read_glb(p):
    b=p.read_bytes();ensure(b[:4]==b'glTF','NOT_GLB');ensure(struct.unpack_from('<I',b,8)[0]==len(b),'GLB_LENGTH')
    n=struct.unpack_from('<I',b,12)[0];d=json.loads(b[20:20+n]);return d,b[28+n:]
def asset_positions(d,b):
    out=[]
    for mesh in d['meshes']:
        for prim in mesh['primitives']:
            a=d['accessors'][prim['attributes']['POSITION']];v=d['bufferViews'][a['bufferView']]
            ensure(a['componentType']==5126 and a['type']=='VEC3','POSITION_FORMAT')
            out.append(np.ndarray((a['count'],3),dtype='<f4',buffer=b,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',12),4)))
    return np.concatenate(out)
def linear_hex(h):
    values=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    return [v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
def main():
    scene_path=HERE/'scene.json';scene=json.loads(scene_path.read_text(encoding='utf-8'));ensure(not scene['development'],'FINAL_GLB_REQUIRES_FINAL_VIEWER_PACKAGE')
    state=scene['states']['service']
    # Freeze the geometry subset separately so later report/download-link refreshes
    # do not make an unchanged mesh export appear stale.
    geometry_snapshot={'configuration':state['configuration'],'state':'service','q_deg':state['q_deg'],'finger_mm':state['finger_mm'],'receipt':state['receipt'],'arm_assets':scene['arm_assets'],'components':state['components'],'occurrences':state['occurrences'],'units':scene['units'],'scope':scene['scope']}
    snapshot_path=HERE/'COMPLETE_GLB_INPUT_SNAPSHOT.json';snapshot_path.write_text(json.dumps(geometry_snapshot,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False),encoding='utf-8')
    input_sha={str(snapshot_path):sha(snapshot_path),state['receipt']['path']:state['receipt']['sha256']}
    gltf={'asset':{'version':'2.0','generator':'WP04 hash-bound buffer compositor; no CAD rebuild'},'scene':0,'scenes':[{'name':'WP04 service digital candidate','nodes':[0]}],'nodes':[{'name':'WP04_SERVICE_ROBOT_DIGITAL_CANDIDATE','children':[],'extras':{'configuration':state['configuration'],'scope':scene['scope'],'collision_credit':None,'physical_assembly_completed':False,'nonarm_representation':'CAD_TESSELLATION','arm_representation':'ACCEPTED_URDF_STL'}}],'meshes':[],'materials':[],'accessors':[],'bufferViews':[],'buffers':[]}
    binary=bytearray();prototypes={};group_ids={};world_min=np.full(3,np.inf);world_max=-world_min.copy()
    labels={'structure':'主承载结构','arm':'B601 accepted STL 机械臂','equipment':'舱内设备','mechanisms':'保持与连接机构','wings':'太阳翼','envelopes':'功能包络_未定型'}
    for group,label in labels.items():
        group_ids[group]=len(gltf['nodes']);gltf['nodes'][0]['children'].append(len(gltf['nodes']));gltf['nodes'].append({'name':label,'children':[],'extras':{'display_group':group}})
    def append_binary(b):
        binary.extend(b'\0'*((-len(binary))%4));offset=len(binary);binary.extend(b);return offset
    def read_prototype(asset,is_stl):
        key=asset['sha256']
        if key in prototypes:return prototypes[key]
        p=HERE/asset['url'];ensure(sha(p)==key,'ASSET_HASH');input_sha[str(p)]=key
        if is_stl:
            raw=p.read_bytes();n=struct.unpack_from('<I',raw,80)[0];ensure(len(raw)==84+n*50,'BINARY_STL_SIZE')
            d=np.frombuffer(raw,dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')]),count=n,offset=84)
            pos=np.ascontiguousarray(d['vertices'].reshape(-1,3));norm=np.repeat(d['normal'],3,axis=0)
            attrs={}
            for name,array in [('POSITION',pos),('NORMAL',norm)]:
                bv=len(gltf['bufferViews']);gltf['bufferViews'].append({'buffer':0,'byteOffset':append_binary(array.tobytes()),'byteLength':array.nbytes,'target':34962})
                ac={'bufferView':bv,'componentType':5126,'count':len(array),'type':'VEC3'}
                if name=='POSITION':ac.update(min=array.min(0).tolist(),max=array.max(0).tolist())
                attrs[name]=len(gltf['accessors']);gltf['accessors'].append(ac)
            prototype={'primitives':[{'attributes':attrs,'mode':4}]}
        else:
            d,b=read_glb(p);ensure(not d.get('images') and not d.get('skins') and not d.get('animations'),'UNSUPPORTED_SOURCE_GLTF')
            ensure(len(d['nodes'])==1 and len(d['meshes'])==1 and not any(x in d['nodes'][0] for x in ('matrix','rotation','scale','translation')),'UNSUPPORTED_COMPONENT_TREE')
            pos=asset_positions(d,b).copy();offset=append_binary(b);vo=len(gltf['bufferViews']);ao=len(gltf['accessors'])
            for view in d['bufferViews']:
                v=copy.deepcopy(view);v['buffer']=0;v['byteOffset']=offset+v.get('byteOffset',0);gltf['bufferViews'].append(v)
            for accessor in d['accessors']:
                a=copy.deepcopy(accessor);ensure('sparse' not in a,'SPARSE_ACCESSOR');a['bufferView']+=vo;gltf['accessors'].append(a)
            prototype=copy.deepcopy(d['meshes'][0]);prototype.pop('extensions',None)
            for prim in prototype['primitives']:
                prim['attributes']={k:v+ao for k,v in prim['attributes'].items()}
                if 'indices'in prim:prim['indices']+=ao
                prim.pop('material',None);prim.pop('extensions',None)
        prototypes[key]=(prototype,pos);return prototypes[key]
    mesh_cache={};material_cache={};expected_ids=[]
    for row in state['occurrences']:
        arm=bool(row.get('arm_link'));asset=scene['arm_assets'][row['arm_link']] if arm else state['components'][row['component']]
        prototype,pos=read_prototype(asset,arm);color=linear_hex('c9b492') if arm else row['color'][:3]
        if row['group']=='wings':color=linear_hex('263e64')
        alpha=.2 if row['group']=='envelopes' else 1;mk=tuple(color)+tuple([alpha])
        if mk not in material_cache:
            material_cache[mk]=len(gltf['materials']);mat={'name':row['group'],'pbrMetallicRoughness':{'baseColorFactor':color+[alpha],'metallicFactor':.4 if arm else .28,'roughnessFactor':.48},'doubleSided':True}
            if alpha<1:mat['alphaMode']='BLEND'
            gltf['materials'].append(mat)
        mi=material_cache[mk];key=(asset['sha256'],mi)
        if key not in mesh_cache:
            mesh=copy.deepcopy(prototype);mesh['name']=row['id']+'_geometry'
            for prim in mesh['primitives']:prim['material']=mi
            mesh_cache[key]=len(gltf['meshes']);gltf['meshes'].append(mesh)
        matrix=np.array(row['matrix_mm'],dtype=float).reshape(4,4);matrix[:3,3]/=1000
        world=pos.astype(float)@matrix[:3,:3].T+matrix[:3,3];world_min=np.minimum(world_min,world.min(0));world_max=np.maximum(world_max,world.max(0))
        node={'name':row['id'],'mesh':mesh_cache[key],'matrix':matrix.T.reshape(-1).tolist(),'extras':{'instance_id':row['id'],'representation_role':row['representation_role'],'part_number':row.get('pn'),'mount_interface':row.get('mount_interface'),'mass_source':row.get('mass_source'),'mass_kg':row.get('mass_kg'),'qualification_status':row.get('qualification_status'),'geometry_sha256':asset['sha256']}}
        gltf['nodes'][group_ids[row['group']]]['children'].append(len(gltf['nodes']));gltf['nodes'].append(node);expected_ids.append(row['id'])
    gltf['buffers']=[{'byteLength':len(binary)}]
    meta=json.dumps(gltf,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();meta+=b' '*((-len(meta))%4);binary.extend(b'\0'*((-len(binary))%4))
    target=HERE/'complete_service_robot.glb'
    with target.open('wb')as f:f.write(struct.pack('<4sII',b'glTF',2,12+8+len(meta)+8+len(binary)));f.write(struct.pack('<I4s',len(meta),b'JSON'));f.write(meta);f.write(struct.pack('<I4s',len(binary),b'BIN\0'));f.write(binary)
    del binary,prototypes
    # Reopen the emitted artifact and traverse exported matrices/accessors, not builder objects.
    reread,payload=read_glb(target);nodes=[n for n in reread['nodes'] if n.get('extras',{}).get('instance_id')];ensure(len(nodes)==len(expected_ids) and {n['name'] for n in nodes}==set(expected_ids),'EXPORTED_INSTANCE_COVERAGE')
    low=np.full(3,np.inf);high=-low.copy();cache={}
    for node in nodes:
        mid=node['mesh']
        if mid not in cache:cache[mid]=asset_positions({**reread,'meshes':[reread['meshes'][mid]]},payload)
        m=np.array(node['matrix']).reshape(4,4).T;vertices=cache[mid].astype(float)@m[:3,:3].T+m[:3,3];low=np.minimum(low,vertices.min(0));high=np.maximum(high,vertices.max(0))
    error=float(max(np.max(np.abs(low-world_min)),np.max(np.abs(high-world_max))))
    ensure(error<1e-9,'EXPORTED_BOUNDS_MISMATCH')
    for p,h in input_sha.items():ensure(sha(Path(p))==h,'SOURCE_CHANGED_DURING_EXPORT')
    result={'status':'COMPLETE_SERVICE_GLTF_DISPLAY_EXPORT_READBACK_PASS','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'output':{'path':str(target),'sha256':sha(target),'bytes':target.stat().st_size},'instance_count':len(nodes),'arm_count':sum(r.get('arm_link')is not None for r in state['occurrences']),'group_count':len(labels),'units':'metres','bounds_m':{'min':low.tolist(),'max':high.tolist()},'emission_vs_readback_max_bound_difference_m':error,'source_scene_sha256_at_export':sha(scene_path),'geometry_input_snapshot':{'path':str(snapshot_path),'sha256':sha(snapshot_path)},'input_sha256':input_sha,'topology_extension_omitted':True,'scope':'Display triangle meshes only; group and instance names retained. Original CAD STEP_topology extension is not merged. No CAD-validity, continuous-motion, collision, physical-assembly or engineering-release credit.'}
    (HERE/'COMPLETE_GLB_EXPORT_RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items()if k!='input_sha256'},ensure_ascii=False))

if __name__=='__main__':main()
