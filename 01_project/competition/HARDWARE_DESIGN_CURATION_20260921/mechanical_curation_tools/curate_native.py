"""R6H copy-only curation. Original CAD is read-only and hash locked.

Reuses the local proven native_integrate COM wrapper and the closed-document
ReplaceReferencedDocument method from WP09 portable_redirect.py. The delivered
CAD does not require Python; this builder requires the original workspace.
"""
from pathlib import Path
import argparse,csv,gc,hashlib,json,re,shutil,sys,traceback
sys.dont_write_bytecode=True
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'PROJECT_MAP.md').is_file() and (p/'20_engineering').is_dir())
OUT=ROOT/'20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/01_mechanical'
SRC=ROOT/'20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(p):return str(Path(p).resolve()).casefold()
def rel(p):return str(Path(p).resolve().relative_to(ROOT)).replace('\\','/')
def write(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def own(p):
    p=Path(p).resolve();assert p.is_relative_to(OUT.resolve()) and p!=OUT.resolve();return p
def configure():
    sys.path.insert(0,str(ROOT/'20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
    import native_integrate as ni
    ni.OUT=OUT;ni.configure_com();return ni
def verify_sources(j):
    assert all(sha(ROOT/r['path'])==r['sha256'] for r in j['full_source_locks'])
def prepare():
    for name in ['inputs','results','native','step','views','docs','tools']:(OUT/name).mkdir(exist_ok=True,parents=True)
    target=OUT/'inputs/MECHANICAL_COPY_PLAN.json';assert not target.exists()
    plan=read(SRC/'inputs/NATIVE_ASSEMBLY_PLAN.json');cold=read(SRC/'results/NATIVE_HIERARCHICAL_RECHECK_V2.json')
    assert cold['status']=='PASS_HIERARCHICAL_READ_ONLY_NATIVE_RECHECK'
    locks=list(csv.DictReader((SRC/'SOURCE_DEPENDENCIES_SHA256.csv').open(encoding='utf-8-sig')))
    bypath={norm(ROOT/r['path']):r for r in locks}
    source_top=SRC/'native/SERVICE_STAR_SERVICE_R6H.SLDASM'
    active={norm(x['path']):Path(x['path']) for x in cold['groups']+cold['leaves']};active[norm(source_top)]=source_top
    assert len(active)==737 and set(active).issubset(bypath)
    nodes=[]
    for key,p in sorted(active.items()):
        h=bypath[key]['sha256'];assert sha(p)==h
        name='SERVICE_STAR_SERVICE_R6H.SLDASM' if key==norm(source_top) else ('P_' if p.suffix.lower()=='.sldprt' else 'G_')+h[:20]+'_'+hashlib.sha256(key.encode()).hexdigest()[:6]+p.suffix.upper()
        nodes.append(dict(source=rel(p),source_sha256=h,target='native/'+name,bytes=p.stat().st_size,kind='part' if p.suffix.lower()=='.sldprt' else ('top' if key==norm(source_top) else 'group')))
    index={norm(ROOT/n['source']):n for n in nodes};groups=[]
    for row in plan['top_rows']:
        groups.append(dict(id=row['id'],source=rel(row['native_path']),target=index[norm(row['native_path'])]['target'],T_S_local=row['T_S_local']))
    leaves=[]
    for row in plan['expected_leaves']:
        leaves.append(dict(id=row['id'],group=row['group'],source=rel(row['native_path']),target=index[norm(row['native_path'])]['target'],T_S_local=row['T_S_local'],expected_solids=row['expected_solids'],expected_sheets=row.get('expected_sheets',0),representation_role=row.get('representation_role'),material_mass_complete=False))
    j=dict(schema='R6H_COMPACT_COPY_PLAN_V1',status='SOURCE_BOUND_COPY_PLAN',source_plan=dict(path=rel(SRC/'inputs/NATIVE_ASSEMBLY_PLAN.json'),sha256=sha(SRC/'inputs/NATIVE_ASSEMBLY_PLAN.json')),source_cold=dict(path=rel(SRC/'results/NATIVE_HIERARCHICAL_RECHECK_V2.json'),sha256=sha(SRC/'results/NATIVE_HIERARCHICAL_RECHECK_V2.json')),full_source_locks=locks,nodes=nodes,top='native/SERVICE_STAR_SERVICE_R6H.SLDASM',groups=groups,leaves=leaves,expected_leaf_count=1153,hash_bound_solid_instances=1602,active_source_files=737,source_lock_superset=790,excluded_lineage_native_files=53,whole_design_complete=False,ready_to_power=False,flight_ready=False)
    verify_sources(j);write(target,j)
    print('PREPARED',len(nodes),'native files',sum(n['bytes'] for n in nodes),'bytes',flush=True)
def bytes_only():
    j=read(OUT/'inputs/MECHANICAL_COPY_PLAN.json');verify_sources(j);rp=OUT/'results/NATIVE_BYTE_COPY.json';assert not rp.exists();files=[]
    for n in j['nodes']:
        src=ROOT/n['source'];dst=own(OUT/n['target']);assert not dst.exists();shutil.copy2(src,dst);assert sha(dst)==n['source_sha256'];files.append(dict(source=n['source'],target=n['target'],sha256=sha(dst),bytes=dst.stat().st_size))
    verify_sources(j);write(rp,dict(status='PASS_737_NATIVE_FILES_BYTE_COPIED_REFERENCE_RELINK_PENDING',files=files,native_files=737,unique_part_files=721,source_790_hashes_unchanged=True,references_relinked=False,cold_open_verified=False,portable_package=False,reason='Copies still retain original stored references; COM authorization timed out twice before execution.'))
    print('BYTE_COPY_ONLY',len(files),'files; references pending',flush=True)
def copy():
    j=read(OUT/'inputs/MECHANICAL_COPY_PLAN.json');verify_sources(j);rp=OUT/'results/NATIVE_COPY_RELINK.json';assert not rp.exists()
    ni=configure();r=dict(status='RUNNING',progress=[],parts=[],assemblies=[],source_inputs_unchanged=False,method='byte-identical parts and closed-document ReplaceReferencedDocument on assembly copies; not PackAndGo');b=None
    try:
        b=ni.PrototypeBuilder(rp,r);sw=b.sw;assert not b.documents()
        index={norm(ROOT/n['source']):own(OUT/n['target']) for n in j['nodes']}
        for n in j['nodes']:
            src=ROOT/n['source'];dst=own(OUT/n['target'])
            if dst.exists():assert sha(dst)==n['source_sha256'],'Existing copy differs; preserve and stop'
            else:shutil.copy2(src,dst)
            assert sha(dst)==n['source_sha256']
            if n['kind']=='part':r['parts'].append(dict(path=n['target'],sha256=sha(dst),bytes=dst.stat().st_size))
        b.checkpoint('copied_only_current_native_closure',files=len(j['nodes']))
        for n in sorted([n for n in j['nodes'] if n['kind']!='part'],key=lambda n:n['kind']=='top'):
            dst=own(OUT/n['target']);assert not b.documents();raw=sw.GetDocumentDependencies2(str(dst),False,False,False) or [];paths=[raw[i+1] for i in range(0,len(raw),2)]
            expected=set();changed=[]
            for p in paths:
                k=norm(p);assert k in index,('UNLISTED_SOURCE_DEPENDENCY',p);new=index[k];expected.add(norm(new));assert sw.ReplaceReferencedDocument(str(dst),p,str(new)),p;changed.append(dict(old=rel(p),new=str(new.relative_to(OUT)).replace('\\','/')))
            raw=sw.GetDocumentDependencies2(str(dst),False,False,False) or [];actual=[raw[i+1] for i in range(0,len(raw),2)];assert {norm(p) for p in actual}==expected
            recursive=sw.GetDocumentDependencies2(str(dst),True,False,False) or [];deps=[recursive[i+1] for i in range(0,len(recursive),2)];assert all(Path(p).resolve().is_relative_to((OUT/'native').resolve()) for p in deps)
            r['assemblies'].append(dict(path=n['target'],sha256=sha(dst),direct_dependencies=len(actual),recursive_dependencies=len(deps),external_dependencies=0,replacements=changed));b.checkpoint('closed_copy_relinked',assembly=dst.name,complete=len(r['assemblies']))
        verify_sources(j);assert not b.documents();r.update(status='PASS_CURRENT_CLOSURE_COPIED_AND_RELINKED_COLD_PENDING',native_files=737,part_files=721,group_files=15,top_files=1,source_inputs_unchanged=True,all_original_790_hashes_unchanged=True,portable_package=False);b.checkpoint('copy_complete')
        if r['session']['new_process']:sw.ExitApp()
    except Exception as e:r.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());write(rp,r);raise
    finally:
        if b:b.pythoncom.CoUninitialize()
def cold(location):
    j=read(OUT/'inputs/MECHANICAL_COPY_PLAN.json');cr=read(OUT/'results/NATIVE_COPY_RELINK.json');assert cr['status']=='PASS_CURRENT_CLOSURE_COPIED_AND_RELINKED_COLD_PENDING'
    verify_sources(j);P=OUT/('native' if location=='primary' else 'relocated_native')
    if location=='relocated':assert not (OUT/'native').exists(),'Original copy directory must be absent during relocation test'
    rp=OUT/'results'/('NATIVE_COLD_'+location.upper()+'.json');assert not rp.exists();ni=configure();b=doc=None
    r=dict(status='RUNNING',progress=[],location=location,read_only=True,documents_saved=0,body_count_method='1602 inherited from original resolved cold verification through 721 byte-identical native parts; this copy validation does not re-resolve every solid',parts_bytes_identical=False,groups=[],leaves=[],portable_package=False)
    try:
        b=ni.PrototypeBuilder(rp,r);sw=b.sw;assert not b.documents();previous=str(ni.m.val(sw,'GetCurrentWorkingDirectory'));assert sw.SetCurrentWorkingDirectory(str(P));target=P/Path(j['top']).name
        saved={Path(x['path']).name:x['sha256'] for x in cr['parts']+cr['assemblies']}
        assert all(sha(P/n)==h for n,h in saved.items());x=sw.OpenDoc6(str(target),2,195,'',0,0);assert x[0] is not None and x[1]==0 and x[2]==0,x[1:]
        r['open_errors']=x[1];r['open_warnings']=x[2];doc=b.wrap(x[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');groups=b.identity_inventory(asm,j['groups']);assert len(groups)==15
        for row in j['groups']:
            c=groups[row['id']];p=P/Path(row['target']).name;assert norm(c.GetPathName())==norm(p) and c.IsFixed();t=list(b.wrap(c.Transform2,'IMathTransform').ArrayData);e=max(abs(a-z) for a,z in zip(t,ni.h.t16(row['T_S_local'])));assert e<1e-8;r['groups'].append(dict(id=row['id'],file=p.name,transform_error=e,fixed=True))
        expected={x['id']:x for x in j['leaves']};seen=set();nodes=list(asm.GetComponents(False) or []);r['recursive_node_count']=len(nodes);maximum=0
        for raw in nodes:
            c=b.wrap(raw,'IComponent2');p=Path(c.GetPathName())
            if p.suffix.lower()!='.sldprt':continue
            ident=c.ComponentReference;assert ident in expected and ident not in seen;seen.add(ident);row=expected[ident];assert norm(p)==norm(P/Path(row['target']).name) and c.IsFixed();t=list(b.wrap(c.GetTotalTransform(False),'IMathTransform').ArrayData);e=max(abs(a-z) for a,z in zip(t,ni.h.t16(row['T_S_local'])));maximum=max(maximum,e);assert e<1e-8,(ident,e)
            r['leaves'].append(dict(id=ident,file=p.name,transform_error=e,fixed=True,hash_bound_solids=row['expected_solids']))
        assert seen==set(expected) and len(seen)==1153
        deps=doc.GetDependencies2(True,True,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)];assert all(Path(p).resolve().is_relative_to(P.resolve()) for p in paths)
        assert {norm(p) for p in paths}=={norm(P/n) for n in saved if n!=target.name}
        assert not ni.m.val(doc,'GetSaveFlag'),'Unexpected dirty read-only copy'
        sw.CloseDoc(ni.m.val(doc,'GetTitle'));doc=asm=groups=nodes=x=c=None;gc.collect();assert not b.documents();assert all(sha(P/n)==h for n,h in saved.items());verify_sources(j);assert sw.SetCurrentWorkingDirectory(previous)
        r.update(status='PASS_CURRENT_NATIVE_CLOSURE_COLD_OPEN',direct_groups=15,leaf_instances=1153,unique_native_parts=721,hash_bound_solid_instances=1602,maximum_transform_sw16_error=maximum,parts_bytes_identical=True,source_790_hashes_unchanged=True,external_native_dependencies=0,dependency_files=len(paths),native_files_unchanged_after_read=True,physical_relocation_test=(location=='relocated'),portable_package=(location=='relocated'));b.checkpoint('cold_complete')
        if r['session']['new_process']:sw.ExitApp()
    except Exception as e:r.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());write(rp,r);raise
    finally:
        if b:
            if doc is not None:
                try:b.sw.CloseDoc(ni.m.val(doc,'GetTitle'))
                except Exception:pass
            b.pythoncom.CoUninitialize()
def move(location):
    a,b=(OUT/'native',OUT/'relocated_native') if location=='relocated' else (OUT/'relocated_native',OUT/'native')
    own(a);own(b);assert a.is_dir() and not b.exists();before={p.name:sha(p) for p in a.iterdir() if p.is_file()};assert len(before)==737;a.rename(b);assert not a.exists() and all(sha(b/n)==h for n,h in before.items());write(OUT/'results'/('MOVE_'+location.upper()+'.json'),dict(status='PASS_OWN_COPY_DIRECTORY_RELOCATED_BYTES_UNCHANGED',from_path=str(a),to_path=str(b),files=737,source_workspace_moved=False))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','bytes','copy','cold','move']);ap.add_argument('--location',choices=['primary','relocated'],default='primary');a=ap.parse_args()
    {'prepare':prepare,'bytes':bytes_only,'copy':copy,'cold':lambda:cold(a.location),'move':lambda:move(a.location)}[a.mode]()
