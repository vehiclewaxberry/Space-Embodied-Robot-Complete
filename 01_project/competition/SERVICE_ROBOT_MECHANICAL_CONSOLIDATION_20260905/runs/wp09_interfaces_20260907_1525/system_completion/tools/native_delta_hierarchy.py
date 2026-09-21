"""Bounded fixed subassemblies; every leaf retains original native/world transform."""
from pathlib import Path
import sys,json,argparse,importlib.util,gc,re,copy,traceback,psutil
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1];D=C/'cad';R=C/'results'
sp=importlib.util.spec_from_file_location('hierarchy_frozen_helper',C.parent/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);m=h.m
ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['groups','integrate','cold']);ap.add_argument('tag');ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=19);ap.add_argument('--state',choices=['service','parking','released']);ap.add_argument('--root',type=Path);a=ap.parse_args()
hp=R/'NATIVE_DELTA_HIERARCHY_INPUTS.json';plan=json.loads(hp.read_text());ip=R/'NATIVE_DELTA_INPUTS.json';j=json.loads(ip.read_text());snapshot=R/'NATIVE_DELTA_IMPORTED_PARTS.json';sealed=json.loads(snapshot.read_text());sealedparts={q['id']:q for q in sealed['parts']}
assert m.sha(ip)==plan['input_manifest_sha256'] and m.sha(snapshot)==plan['imported_parts_snapshot_sha256']
out=R/f"NATIVE_DELTA_{'GROUPS' if a.mode=='groups' else a.mode.upper()}_{a.tag}.json";assert not out.exists()
r={'status':'RUNNING','mode':a.mode,'progress':[],'parts':[],'save_attempts':[],'groups':[],'input_manifest_sha256':m.sha(ip),'imported_parts_snapshot_sha256':m.sha(snapshot),'hierarchy_input_sha256':m.sha(hp),'coordinate_frame':'ORIGINAL_NATIVE_LEAF_T_TO_S_WITH_COLD_VERIFIED_IDENTITY_GROUP_PARENTS','manufacturing_release':False,'mate_based_motion':False,'continuous_motion_verified':False}
b=None;sw=None;prefs={};groups={g['id']:g for g in plan['groups']};I=plan['parent_transform_sw16']
def combine_rss():return (psutil.Process().memory_info().rss+psutil.Process(r['owned_sw_pid']).memory_info().rss)/2**20
def save(model,path):
 ext=b.wrap(model.Extension,'IModelDocExtension');assert not path.exists()
 before={'needs_rebuild2':int(ext.NeedsRebuild2),'save_flag':bool(m.val(model,'GetSaveFlag'))}
 result=ext.SaveAs(str(path),0,9,None,0,0)
 receipt={'path':str(path),'api_return':list(result),'ok':bool(result[0]),'errors':result[1],'warnings':result[2],'options':9}
 r['save_attempts'].append(receipt);b.checkpoint('save_returned',path=str(path),ok=receipt['ok'],errors=receipt['errors'])
 assert result[0] and result[1]==0 and path.exists() and path.stat().st_size>0
 receipt.update(sha256=m.sha(path),bytes=path.stat().st_size)
 after={'needs_rebuild2':int(ext.NeedsRebuild2),'save_flag':bool(m.val(model,'GetSaveFlag'))}
 return receipt,before,after
def make(rows,path,label):
 model=b.wrap(sw.NewDocument(str(m.TEMPLATES/'gb_assembly.asmdot'),0,0.,0.),'IModelDoc2');assert model is not None
 asm=b.wrap(model,'IAssemblyDoc');feature=b.wrap(model.FeatureManager,'IFeatureManager');feature.EnableFeatureTree=False;feature.EnableFeatureTreeWindow=False
 for start in range(0,len(rows),8):
  chunk=rows[start:start+8];b.ram_floor()
  raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[q['native_path'] for q in chunk]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[v for q in chunk for v in h.t16(q['T_S_local'])]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']*len(chunk))) or []
  assert len(raw)==len(chunk);model.ClearSelection2(True)
  for rc,q in zip(raw,chunk):
   comp=b.wrap(rc,'IComponent2');comp.ComponentReference=q['id'];comp.Name2=re.sub(r'[ .()/\\]','_',q['id']);assert comp.Select4(True,None,False)
   if q.get('native_delta_part_id')=='AZUR81442_CIC_GLASS_FOOTPRINT_LAYER':comp.MaterialPropertyValues=b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[.035,.12,.28,.4,.8,.2,.2,0.,0.])
  asm.FixComponent();model.ClearSelection2(True);raw=rc=comp=None;gc.collect();asm.LightweightAllResolved();b.checkpoint('group_inserted',group=label,count=start+len(chunk))
 lookup=b.identity_inventory(asm,rows);lookup=None;gc.collect()
 props=b.wrap(b.wrap(model.Extension,'IModelDocExtension').CustomPropertyManager(''),'ICustomPropertyManager')
 for key,value in {'WP09D_GROUP':label,'WP09D_MOTION':'FIXED_IDENTITY_PARENT_ORIGINAL_LEAF_NATIVE_T','WP09D_LEAF_COUNT':873 if label.startswith('TOP_') else len(rows),'WP09D_TOP_LEVEL_CONTAINER_COUNT':len(rows) if label.startswith('TOP_') else 0,'WP09D_RELEASE':False}.items():props.Add3(key,30,str(value),2)
 saved,pre,post=save(model,path);b.close_own_saved(model,path,saved['sha256']);model=asm=feature=props=None;gc.collect()
 return saved,pre,post
def completed_group(g):
 candidates=[]
 for f in sorted(R.glob('NATIVE_DELTA_GROUPS_*.json')):
  if f==out:continue
  z=json.loads(f.read_text())
  if z.get('hierarchy_input_sha256')!=m.sha(hp):continue
  for row in z.get('groups',[]):
   if row.get('id')==g['id'] and row.get('status')=='PASS_GROUP_SAVED_CLOSED_COLD_METADATA_AND_DEPENDENCIES':candidates.append((f,row))
 assert candidates,('No group save/cold proof',g['id'])
 f,row=candidates[-1];assert m.sha(g['path'])==row['native_save']['sha256']
 return {'id':g['id'],'path':g['path'],'sha256':row['native_save']['sha256'],'save_receipt':str(f),'save_receipt_sha256':m.sha(f),'leaf_count':g['leaf_component_count']}
try:
 b=h.Builder(out,r);sw=b.sw;assert not b.documents(),'Unknown/user documents left untouched'
 r['owned_sw_pid']=int(m.val(sw,'GetProcessID'));r['preflight_available_mib']=psutil.virtual_memory().available/2**20;assert r['preflight_available_mib']>=2048
 sw.UserControl=True;prefs={25:sw.GetUserPreferenceToggle(25)};sw.SetUserPreferenceToggle(25,True);sw.CommandInProgress=True
 if a.mode in ('groups','integrate','cold'):
  sw.DocumentVisible(False,1);sw.DocumentVisible(False,2);r['display_policy']='HIDDEN_NATIVE_DOCUMENTS_DURING_SERIAL_SAVE_NO_GEOMETRY_CHANGE'
 if a.mode=='groups':
  for g in plan['groups'][a.start:a.end]:
   path=Path(g['path']);assert not path.exists()
   assert all(m.sha(q['native_path'])==q['native_sha256'] for q in g['rows'])
   saved,pre,post=make(g['rows'],path,g['id']);row={'id':g['id'],'native_save':saved,'pre_save_state':pre,'post_save_state':post};r['groups'].append(row)
   opened=sw.OpenDoc6(str(path),2,195,'',0,0);assert opened[0] is not None and opened[1]==opened[2]==0
   model=b.wrap(opened[0],'IModelDoc2');lookup,observed=b.metadata(model,g['rows'],False);deps=model.GetDependencies2(True,True,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)]
   assert {m.normalized(p) for p in paths}=={m.normalized(q['native_path']) for q in g['rows']}
   row.update(status='PASS_GROUP_SAVED_CLOSED_COLD_METADATA_AND_DEPENDENCIES',cold_components=observed,dependencies=paths,leaf_count=len(observed),cold_open_errors=0,cold_open_warnings=0)
   b.close_own_saved(model,path,saved['sha256']);model=lookup=observed=None;gc.collect();row['combined_rss_mib_after']=combine_rss();b.checkpoint('group_completed',group=g['id'],leaf_count=row['leaf_count'])
   if row['combined_rss_mib_after']>850:r['early_clean_batch_end']='SAVE_COMPLETED_GROUPS_EXIT_BEFORE_RETAINED_CACHE_LIMIT';break
  r.update(status='PASS_FIXED_GROUP_NATIVE_SAVE_AND_COLD_READ',group_count=len(r['groups']))
 else:
  s=plan['states'][a.state];folder=a.root or D;target=folder/Path(s['target_path']).name;rows=copy.deepcopy(j['states'][a.state]['rows'])
  for q in rows:
   q['native_path']=str(folder/Path(q['native_path']).name)
   if q.get('native_delta_part_id'):q['native_sha256']=sealedparts[q['native_delta_part_id']]['native_sha256']
  assert all(m.sha(q['native_path'])==q['native_sha256'] for q in rows)
  r.update(state=a.state,root=str(folder),rows=rows,leaf_component_count=873,top_level_container_count=len(s['groups']),hierarchy_depth=2)
  if a.mode=='integrate':
   group_seal=[completed_group(groups[k]) for k in s['groups']];r['group_hash_seal']=group_seal
   top_rows=[{'id':g['id'],'native_path':g['path'],'native_sha256':g['sha256'],'T_S_local':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]} for g in group_seal]
   saved,pre,post=make(top_rows,target,'TOP_'+a.state);r.update(native_save=saved,pre_save_state=pre,post_save_state=post,component_count=873,expected_solids=1254,status='PASS_NATIVE_DELTA_SAVED_COLD_INSPECTION_PENDING',native_view_capture_status='DEFERRED_FRESH_COLD')
  else:
   if a.root:assert folder.resolve()!=D.resolve() and not D.exists();r.update(original_root=str(D),original_root_absent_during_cold_open=True)
   saved_path=R/f'NATIVE_DELTA_INTEGRATE_{a.state}.json';saved=json.loads(saved_path.read_text());assert saved['status']=='PASS_NATIVE_DELTA_SAVED_COLD_INSPECTION_PENDING';digest=saved['native_save']['sha256'];assert m.sha(target)==digest
   assert saved['hierarchy_input_sha256']==m.sha(hp) and saved['input_manifest_sha256']==m.sha(ip) and saved['imported_parts_snapshot_sha256']==m.sha(snapshot)
   r.update(assembly_save_receipt=str(saved_path),assembly_save_receipt_sha256=m.sha(saved_path),group_hash_seal=saved['group_hash_seal'])
   for g in saved['group_hash_seal']:
    assert m.sha(folder/Path(g['path']).name)==g['sha256'];assert m.sha(g['save_receipt'])==g['save_receipt_sha256']
   assert sw.SetCurrentWorkingDirectory(str(folder));sw.CommandInProgress=False
   opened=sw.OpenDoc6(str(target),2,195,'',0,0);r.update(open_errors=opened[1],open_warnings=opened[2]);assert opened[0] is not None and opened[1]==opened[2]==0
   model=b.wrap(opened[0],'IModelDoc2');b.checkpoint('cold_hidden_native_open_returned');asm=b.wrap(model,'IAssemblyDoc');lookup=b.identity_inventory(asm,[{'id':k} for k in s['groups']]);parent_observed=[]
   leaf_parent={q['id']:ident for ident in s['groups'] for q in groups[ident]['rows']};assert set(leaf_parent)=={q['id'] for q in rows}
   for ident,comp in lookup.items():
    tv=list(b.wrap(comp.Transform2,'IMathTransform').ArrayData);assert max(abs(x-y) for x,y in zip(tv,I))<=1e-12 and comp.IsFixed()
    assert m.normalized(m.val(comp,'GetPathName'))==m.normalized(folder/Path(groups[ident]['path']).name)
    parent_observed.append({'id':ident,'path':str(folder/Path(groups[ident]['path']).name),'transform_sw16':tv,'fixed':True})
   raw=asm.GetComponents(False) or [];registry={q['id']:q for q in rows};observed=[];containers=[];seen=set()
   for rc in raw:
    comp=b.wrap(rc,'IComponent2');path=Path(m.val(comp,'GetPathName'));ident=comp.ComponentReference
    if path.suffix.lower()=='.sldasm':containers.append(ident);continue
    assert path.suffix.lower()=='.sldprt' and ident in registry and ident not in seen;seen.add(ident);q=registry[ident]
    assert m.normalized(path)==m.normalized(q['native_path']) and m.sha(path)==q['native_sha256']
    parent=b.wrap(comp.GetParent(),'IComponent2');assert parent is not None and parent.ComponentReference==leaf_parent[ident]
    assert m.normalized(m.val(parent,'GetPathName'))==m.normalized(folder/Path(groups[leaf_parent[ident]]['path']).name)
    parent_tv=list(b.wrap(parent.Transform2,'IMathTransform').ArrayData);assert max(abs(x-y) for x,y in zip(parent_tv,I))<=1e-12
    tv=list(b.wrap(comp.Transform2,'IMathTransform').ArrayData);assert max(abs(x-y) for x,y in zip(tv,h.t16(q['T_S_local'])))<=1e-8 and comp.IsFixed() and comp.GetSuppression2() in (1,2,4)
    observed.append({'id':ident,'path':str(path),'sha256':q['native_sha256'],'transform_sw16':tv,'fixed':True,'visible':comp.Visible,'parent_id':parent.ComponentReference,'parent_transform_sw16':parent_tv,'world_transform_rule':'ONE_IDENTITY_PARENT_CHAIN_NO_DOUBLE_MULTIPLICATION'})
    if len(observed)%128==0:b.checkpoint('cold_hidden_leaf_progress',leaves=len(observed))
   assert seen==set(registry) and len(observed)==873 and set(containers)==set(s['groups']) and len(containers)==len(s['groups'])
   deps=model.GetDependencies2(True,True,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)];wanted={m.normalized(q['native_path']) for q in rows}|{m.normalized(folder/Path(groups[k]['path']).name) for k in s['groups']};assert {m.normalized(p) for p in paths}==wanted
   assert all(Path(p).resolve().parent==folder.resolve() for p in paths)
   r.update(status='PASS_COLD_NATIVE_DELTA_IDENTITIES_TRANSFORMS_LOCAL_DEPENDENCIES',component_count=873,components=observed,parent_containers=parent_observed,recursive_container_count=len(containers),expected_solids_hash_bound=1254,external_dependency_count=0,dependencies=paths,native_sha256=digest,actual_all_body_readback_this_cold_open=False)
   r['cold_state_before_optional_view']={'needs_rebuild2':int(b.wrap(model.Extension,'IModelDocExtension').NeedsRebuild2),'save_flag':bool(m.val(model,'GetSaveFlag'))};assert m.sha(target)==digest and not m.val(model,'GetSaveFlag');b.checkpoint('cold_hierarchy_verified')
   raw=comp=parent=lookup=asm=observed=None;gc.collect()
   r['native_view_capture_status']='SEPARATE_FRESH_SESSION_VIEW_DOES_NOT_CHANGE_COLD_METADATA_CREDIT'
   assert m.sha(target)==digest
   if m.val(model,'GetSaveFlag'):sw.CloseDoc(m.val(model,'GetTitle'));r['own_readonly_view_only_change_discarded']=True
   else:b.close_own_saved(model,target,digest)
   model=None
   if a.root:assert not D.exists(),'Original CAD root appeared before relocated cold close'
 sw.CommandInProgress=False
 for key,value in prefs.items():sw.SetUserPreferenceToggle(key,value)
 sw.DocumentVisible(True,1);sw.DocumentVisible(True,2)
 assert not b.documents();sw.ExitApp();r['open_documents_after']=[];b.checkpoint('completed_saved_closed_exit')
except Exception as exc:
 r.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
