"""Stream the exact WP07 display cache plus the 34 source-bound retention parts.

No CAD kernel, COM, decimation, whole STEP export or source cache writes.
The 591 retained instance nodes and the baseline BIN payload remain byte exact.
Only display placement/coverage is checked here; native receipts govern CAD.
"""
from __future__ import annotations
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import mmap
from pathlib import Path
import struct
import sys
sys.dont_write_bytecode = True
import numpy as np

RUN = Path(__file__).resolve().parents[1]
R7 = RUN.parent / 'wp07_system_20260907_0610'
OUT = RUN / 'viewer'
SOURCE = R7 / 'viewer/WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb'
SOURCE_SHA = 'c6dc40c19f0205592cb51417a6125c3bd5c982a2e0d0c8d8664a8d6e84e037c1'
TARGET = OUT / 'WP08_SERVICE_RETENTION_DELTA_V2.glb'
REPORT = OUT / 'DISPLAY_DELTA_CHECK_V2.json'

def require(ok, message):
    if not ok: raise ValueError(message)

def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def main():
    OUT.mkdir(exist_ok=True)
    require(not TARGET.exists() and not REPORT.exists(), 'Refuse existing output')
    report = dict(schema='WP08_DISPLAY_DELTA_V2', status='RUNNING', source_sha256={},
        started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), units='metres', frame='S; +Z up',
        scope='Fixed SERVICE display from source-bound CAD tessellation caches; not BRep identity, collision, motion or release proof',
        exact_brep_equivalence_claimed=False, continuous_motion_verified=False, manufacturing_release=False)
    pins = report['source_sha256']
    def bind(path, expected=None):
        path=Path(path).resolve(); value=sha(path)
        require(expected is None or value==expected, 'Hash mismatch: '+str(path))
        require(str(path) not in pins or pins[str(path)]==value, 'Changing input')
        pins[str(path)]=value
        return value
    def save(): REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    save()
    try:
        bind(__file__)
        bind(RUN/'tools/build_delta_view.py')
        bind(OUT/'DISPLAY_DELTA_CHECK.json')
        report['prior_attempt']={'path':str(OUT/'DISPLAY_DELTA_CHECK.json'),'status':'FAILED_OR_INCOMPLETE','reason':'Optional STEP_topology metadata was initially rejected; V2 explicitly omits local topology selector metadata and retains all mesh attributes and BIN bytes.'}
        report['whole_assembly_step_topology_selector_metadata_present']=False
        helpers=R7/'tools/build_review_glb.py'; bind(helpers, '416cf08ab4de8c02105d163bd949357c1116eabd61750a3b9092f651b80bc486')
        spec=importlib.util.spec_from_file_location('frozen_wp07_display_helpers', helpers)
        h=importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
        manifest_path=RUN/'results/INTEGRATION_MANIFEST.json'; bind(manifest_path)
        manifest=read(manifest_path); state=manifest['states']['service']
        expected={x['id']:x for x in state['instances']}
        replaced=set(state['replaced_ids']); added=set(state['added_ids']); changed=replaced|added
        require(len(expected)==state['component_count'] and len(replaced)==6 and len(added)==28, 'Delta coverage differs')
        bind(SOURCE, SOURCE_SHA)
        prior_path=R7/'viewer/REVIEW_GLB_V4_COMPACT_RESULT.json'; bind(prior_path)
        prior=read(prior_path); require(prior['status']=='PASS_EXACT_DISPLAY_COMPACTION', 'Baseline display not qualified')
        model, source_offset, source_length=h.glb_header(SOURCE)
        old_ids=h.instance_map(model)
        require(set(old_ids)|added==set(expected) and replaced<=set(old_ids), 'Baseline/delta identities differ')
        retained=set(old_ids)-replaced
        require(len(retained)==591, 'Retained membership differs')
        preserved={key:copy.deepcopy(model['nodes'][old_ids[key]]) for key in retained}
        groups=[i for i,n in enumerate(model['nodes']) if n.get('extras',{}).get('display_group')=='structure']
        require(len(groups)==1, 'One structure group required')
        require(not any(k in model['nodes'][groups[0]] for k in ('matrix','translation','rotation','scale')), 'Transformed structure group')
        bind(R7/'candidate/retention_detail.py', '14fd2319207e26410d3cb33efd3a523148a3eefe0af376a6bf50419518b1348c')
        bind(R7/'inputs/RETENTION_DESIGN_CONTRACT.json', 'cd4b40745ca081ed7dfa2c89cd7f811a4998ca2baf832e1e73b50dfe2a87ba8c')
        bind(R7/'candidate/retention_station_view.py')
        caches={}
        for station in (0,1):
            cache_path=R7/f'candidate/__cadgen__/models/retention_station{station}.step.py/assembly.json'
            bind(cache_path); cache=read(cache_path)
            bind(R7/f'candidate/retention_station{station}.step.py', cache['sourceHash'])
            require(cache['units']=='mm' and len(cache['occurrences'])==18, 'Unexpected local cache')
            occurrences={x['name']:x for x in cache['occurrences']}
            require(len(occurrences)==18 and len([x for x in occurrences if x.startswith('CONTEXT_PARKING_')])==1, 'Context identity differs')
            caches[station]=(cache_path,cache,occurrences)
        segments=[(SOURCE,source_offset,source_length,0)]
        size=source_length; mappings=[]
        for name in sorted(changed):
            row=expected[name]; bind(row['step_path'],row['source_sha256'])
            bind(row['native_path'],row['native_sha256'])
            cache_path,cache,occurrences=caches[row['station']]
            occ=occurrences[name]
            require(np.allclose(np.asarray(occ['transform']).reshape(4,4),np.eye(4),rtol=0,atol=1e-12), 'Local cache occurrence not identity')
            partfile=(cache_path.parent/cache['components'][occ['component']]['glb']).resolve()
            require(partfile.is_relative_to(cache_path.parent.resolve()), 'Cache path escape')
            digest=bind(partfile); data,offset,length=h.glb_header(partfile)
            require(len(data['nodes'])==len(data['meshes'])==1, 'Expected one mesh per candidate solid')
            require(not any(data.get(k) for k in ('skins','animations','images','textures','extensionsRequired')), 'Unsupported required GLB feature')
            require(set(data.get('extensionsUsed',[])) <= {'STEP_topology'} and set(data.get('extensions',{})) <= {'STEP_topology'}, 'Unsupported optional extension')
            # STEP_topology index/edge/selector JSON is local to each source part.
            # It is not merged into a false whole-assembly topology namespace.
            # Every mesh attribute and all source BIN bytes remain unchanged.
            require(not any(k in data['nodes'][0] for k in ('matrix','translation','rotation','scale','extensions')), 'Unsupported component transform')
            pad=(-size)%4; size+=pad; base=size
            vo,ao,mo=len(model['bufferViews']),len(model['accessors']),len(model['materials'])
            for v in data['bufferViews']:
                v=copy.deepcopy(v); require(v.get('buffer',0)==0 and not v.get('extensions'), 'Unsupported view')
                v['buffer']=0; v['byteOffset']=base+v.get('byteOffset',0); model['bufferViews'].append(v)
            for a in data['accessors']:
                a=copy.deepcopy(a); require('sparse' not in a and 'bufferView' in a, 'Unsupported accessor')
                a['bufferView']+=vo; model['accessors'].append(a)
            color=occ.get('color',[.6,.7,.8,1])
            model['materials'].append(dict(name=name+'_source_cache_color', doubleSided=True,
                pbrMetallicRoughness=dict(baseColorFactor=color,metallicFactor=.28,roughnessFactor=.48)))
            mesh=copy.deepcopy(data['meshes'][0]); require(not mesh.get('extensions'), 'Unsupported mesh extensions')
            for p in mesh['primitives']:
                require(not any(k in p for k in ('targets','extensions')) and p.get('mode',4)==4, 'Unsupported primitive')
                p['attributes']={k:v+ao for k,v in p['attributes'].items()}
                if 'indices' in p: p['indices']+=ao
                p['material']=mo
            mesh['name']=name+'_retention_cache'
            node=dict(name=name,mesh=len(model['meshes']),matrix=h.gltf_matrix(row['T_S_local']),
                extras=dict(instance_id=name,representation_role=row['representation_role'],
                    source_step_sha256=row['source_sha256'], native_sha256=row['native_sha256'],
                    source_revision=row['source_revision'], geometry_sha256=digest,
                    mass_kg=None,mass_source=row['mass_source'],qualification_status=row['qualification_status'],
                    display_geometry_basis='WP07_C02_SOURCE_BOUND_LOCAL_CACHE_WITH_WP08_STATE_TRANSFORM'))
            model['meshes'].append(mesh)
            if name in replaced: model['nodes'][old_ids[name]]=node
            else:
                model['nodes'][groups[0]]['children'].append(len(model['nodes']))
                model['nodes'].append(node)
            segments.append((partfile,offset,length,pad)); size+=length
            mappings.append(dict(id=name,cache=str(cache_path),cache_occurrence_id=occ['id'],
                component_glb=str(partfile),sha256=digest,bin_output_offset=base,bytes=length))
        model['buffers']=[dict(byteLength=size)]
        model['asset']['generator']='WP08 source-bound streaming display delta'
        model['scenes'][0]['name']='WP08 SERVICE retention integrated'
        require(not model['nodes'][0].get('extras',{}).get('instance_id'), 'Expected non-instance root')
        model['nodes'][0]['name']='WP08_SERVICE_RETENTION_DELTA_DISPLAY_ONLY'
        model['nodes'][0]['extras']=dict(scope=report['scope'],
            manifest_sha256=pins[str(manifest_path.resolve())],retained_count=591,replaced_count=6,added_count=28,
            exact_brep_equivalence_claimed=False,continuous_motion_verified=False,manufacturing_release=False)
        ids=h.instance_map(model)
        require(set(ids)==set(expected) and set(ids.values())<=h.reachable(model), 'Output occurrence coverage differs')
        require(all(model['nodes'][ids[k]]==preserved[k] for k in retained), 'Retained instance changed')
        require(sum(k.startswith('CONTEXT_PARKING_') for k in ids)==0, 'Duplicated context')
        metadata=json.dumps(model,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        metadata+=b' '*((-len(metadata))%4); final_pad=(-size)%4
        with TARGET.open('xb') as dst:
            dst.write(struct.pack('<4sII',b'glTF',2,28+len(metadata)+size+final_pad))
            dst.write(struct.pack('<I4s',len(metadata),b'JSON')); dst.write(metadata)
            dst.write(struct.pack('<I4s',size+final_pad,b'BIN\0'))
            for path,offset,length,pad in segments:
                dst.write(b'\0'*pad)
                with path.open('rb') as src:
                    src.seek(offset); left=length
                    while left:
                        block=src.read(min(1024*1024,left)); require(block,'Short input'); dst.write(block); left-=len(block)
            dst.write(b'\0'*final_pad)
        actual,offset,_=h.glb_header(TARGET); require(actual==model,'JSON readback differs')
        with SOURCE.open('rb') as a,TARGET.open('rb') as b:
            a.seek(source_offset); b.seek(offset); left=source_length
            while left:
                n=min(1024*1024,left); require(a.read(n)==b.read(n),'Baseline BIN bytes changed'); left-=n
        bounds=[]
        with TARGET.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
            for name in sorted(changed):
                low,high,count=h.mesh_world_bounds(model,mm,offset,model['nodes'][ids[name]])
                ref=expected[name]['world_bounds_mm']; expected_box=np.array([ref['min_mm'],ref['max_mm']])
                error=float(np.max(np.abs(np.array([low,high])-expected_box)))
                bounds.append(dict(id=name,max_bbox_error_mm=error,position_count=count,passed=error<.1))
        require(all(x['passed'] for x in bounds),'New display bounds differ by >=0.1 mm')
        require(all(sha(p)==v for p,v in pins.items()),'Input changed during build')
        report.update(status='PASS_DISPLAY_DELTA_ONLY',output=dict(path=str(TARGET),sha256=sha(TARGET),bytes=TARGET.stat().st_size),
            instance_count=len(ids),retained_count=len(retained),replaced_count=len(replaced),added_count=len(added),
            retained_nodes_equal=True,baseline_bin_byte_identical=True,source_inputs_unchanged=True,
            local_context_instances_added=0,new_display_bbox_tolerance_mm=.1,
            bbox_scope='Display scale/placement only; 591 unchanged bounds inherited from verified V4 byte-preserved geometry',
            changed_bbox_checks=bounds,mappings=mappings,completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        save(); print(json.dumps({k:report[k] for k in ('status','instance_count','retained_count','replaced_count','added_count','output')}))
    except Exception as exc:
        report.update(status='FAILED_OR_INCOMPLETE',error_type=type(exc).__name__,error=str(exc)); save(); raise

if __name__=='__main__': main()
