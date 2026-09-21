"""Serialized native import, copied-baseline delta, and cold metadata proof."""
from pathlib import Path
import sys,json,argparse,importlib.util,traceback,gc,copy,shutil,re,psutil
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1];R=C.parent;D=C/'cad'
sp=importlib.util.spec_from_file_location('frozen_delta_helper',R/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);m=h.m
ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['import','integrate','cold']);ap.add_argument('tag');ap.add_argument('--start',type=int,default=0);ap.add_argument('--end',type=int,default=138);ap.add_argument('--state',choices=['service','parking','released']);ap.add_argument('--root',type=Path);a=ap.parse_args()
j=json.loads((C/'results/NATIVE_DELTA_INPUTS.json').read_text());out=C/'results'/f'NATIVE_DELTA_{a.mode.upper()}_{a.tag}.json';assert not out.exists()
r=dict(status='RUNNING',mode=a.mode,progress=[],parts=[],save_attempts=[],coordinate_frame='EXPLICIT_NATIVE_PART_LOCAL_TO_S_WORLD_MM',input_manifest_sha256=m.sha(C/'results/NATIVE_DELTA_INPUTS.json'),manufacturing_release=False,mate_based_motion=False,continuous_motion_verified=False)
b=None;prefs=None
try:
 b=h.Builder(out,r);sw=b.sw;assert not b.documents(),'Unknown/user documents left untouched'
 r['preflight_available_mib']=psutil.virtual_memory().available/2**20;assert r['preflight_available_mib']>=2048
 r['owned_sw_pid']=int(m.val(sw,'GetProcessID'));sw.UserControl=True
 if a.mode=='import':
  prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,291,691)},strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (577,578,579,580)})
  for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k==111)
  for k,n in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(m.TEMPLATES/n))
  for k,v in {577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
  # One bounded trial in a fresh session. Geometry/import/save/cold checks are unchanged.
  display_trial_marker=C/'results/NATIVE_DELTA_HIDDEN_TRIAL_STARTED.json'
  display_acceptance=C/'results/NATIVE_DELTA_HIDDEN_IMPORT_ACCEPTANCE.json'
  hidden_adopted=False
  if display_acceptance.exists():
   approved=json.loads(display_acceptance.read_text())
   assert approved['status']=='ACCEPTED_DISPLAY_ONLY_HIDDEN_PART_IMPORT'
   assert m.sha(approved['trial_receipt'])==approved['trial_sha256'] and m.sha(approved['guard_receipt'])==approved['guard_sha256']
   hidden_adopted=a.start>=approved['minimum_next_start']
   r['part_display_adoption']=dict(acceptance_path=str(display_acceptance),acceptance_sha256=m.sha(display_acceptance),active=hidden_adopted)
  hidden_trial=a.start>=82 and not display_trial_marker.exists()
  import_end=min(a.end,a.start+5) if hidden_trial else a.end
  hide_part_documents=hidden_trial or hidden_adopted
  if hide_part_documents:
   r['part_display_trial']=dict(mode='HIDDEN_PART_DOCUMENTS',start=a.start,end=import_end,planned_count=import_end-a.start,api='DocumentVisible(False,1)',geometry_and_validation_unchanged=True,scope='One fresh-session trial only; later batches revert unless explicitly adopted after review')
   if hidden_trial:display_trial_marker.write_text(json.dumps(dict(tag=a.tag,result=str(out),start=a.start,end=import_end),indent=2),encoding='utf-8')
   if hidden_adopted:r['part_display_trial']['scope']='Adopted only for part imports from frozen successful display trial; geometry and all checks unchanged'
   r['part_display_trial']['api_return']=sw.DocumentVisible(False,1)
   r['part_display_trial']['combined_rss_mib_before']=(psutil.Process().memory_info().rss+psutil.Process(r['owned_sw_pid']).memory_info().rss)/2**20
   b.checkpoint('hidden_part_document_trial_started',start=a.start,end=import_end)
  for row in j['parts'][a.start:import_end]:
   row=dict(row);bbox=row['expected_local_bbox_mm'];row['expected_local_bbox_mm']={'min_mm':bbox[0],'max_mm':bbox[1]}
   original=Path(row['step_path']);short=D/('S'+Path(row['native_path']).stem[1:]+'.step')
   if not short.exists():shutil.copy2(original,short)
   assert m.sha(original)==m.sha(short)==row['source_sha256']
   row['step_path']=str(short)
   if Path(row['native_path']).exists():
    candidates=[]
    for rp in (C/'results').glob('NATIVE_DELTA_IMPORT_*.json'):
     if rp==out:continue
     prior=json.loads(rp.read_text())
     for p in prior.get('parts',[]):
      saved=p.get('native_save',{})
      if saved.get('path')==row['native_path'] and p.get('source_sha256')==row['source_sha256'] and saved.get('sha256')==m.sha(row['native_path']):candidates.append(str(rp))
    assert candidates,'Existing native not hash-bound to our saved import receipt'
    opened=sw.OpenDoc6(row['native_path'],1,1,'',0,0);assert opened[0] is not None and opened[1]==0
    cold=b.wrap(opened[0],'IModelDoc2');got=b.part_facts(cold)
    assert got['solid_count']==1 and got['sheet_count']==0 and m.bbox_max_error(got['bounds_mm'],row['expected_local_bbox_mm'])<=m.job_linear_tolerance_mm()
    assert cold.ListExternalFileReferencesCount2()==0 and cold.ListAuxiliaryExternalFileReferencesCount()==0
    r['parts'].append(dict(id=row['id'],source_sha256=row['source_sha256'],status='RECOVERED_OWN_SAVED_PART_COLD_GEOMETRY_VALIDATED',prior_receipts=candidates,native_save=dict(path=row['native_path'],sha256=m.sha(row['native_path'])),part_cold_reopen=dict(facts=got)))
    b.close_own_saved(cold,Path(row['native_path']),m.sha(row['native_path']));cold=None
   else:
    b.import_part(row);got=r['parts'][-1]['part_cold_reopen']['facts']
   err=abs(got['volume_mm3']-row['expected_volume_mm3'])
   if row['id'].startswith('wing_edge_frame_'):
    r['parts'][-1]['native_mass_property_estimate_not_geometry_equivalence']=True
    p=Path(row['native_path']);roundtrip=p.with_suffix('.step')
    assert not roundtrip.exists()
    opened=sw.OpenDoc6(str(p),1,1,'',0,0);assert opened[0] is not None and opened[1]==0
    doc=b.wrap(opened[0],'IModelDoc2');b.activate(doc,p)
    r['parts'][-1]['geometry_roundtrip']=b.save_new(doc,roundtrip)
    b.close_own_saved(doc,p,m.sha(p));doc=None
    r['parts'][-1]['geometry_equivalence']='PENDING_SAME_KERNEL_BOOLEAN_AND_ADAPTIVE_VOLUME_CHECK'
   else:
    assert err<=max(1e-5,row['expected_volume_mm3']*1e-7),(row['id'],err)
   r['parts'][-1]['source_native_volume_error_mm3']=err;gc.collect()
   combined=psutil.Process().memory_info().rss+psutil.Process(r['owned_sw_pid']).memory_info().rss
   r['parts'][-1]['combined_rss_mib_after']=combined/2**20
   if combined/2**20>1050:
    r['early_clean_batch_end']='PREVENT_RETAINED_SW_IMPORT_CACHE_REACHING_1400_MIB';break
  if hide_part_documents:
   r['part_display_trial']['restore_api_return']=sw.DocumentVisible(True,1)
   r['part_display_trial']['restored_visible_default']=True
   r['part_display_trial']['actual_count']=len(r['parts'])
  r.update(status='PASS_DELTA_NATIVE_PART_IMPORT_AND_COLD_BODY_VOLUME_BOUNDS',part_count=len(r['parts']))
 else:
  sealed_path=C/'results/NATIVE_DELTA_IMPORTED_PARTS.json';sealed=json.loads(sealed_path.read_text(encoding='utf-8'))
  assert sealed['status']=='PASS_138_IMPORTED_PARTS_HASH_SNAPSHOT_SEALED' and sealed['input_manifest_sha256']==r['input_manifest_sha256']
  sealed_parts={p['id']:p for p in sealed['parts']};assert len(sealed_parts)==len(sealed['parts'])==sealed['part_count']==138
  assert set(sealed_parts)=={p['id'] for p in j['parts']}
  r['imported_parts_snapshot_sha256']=m.sha(sealed_path)
  assert m.sha(sealed['frame_equivalence']['path'])==sealed['frame_equivalence']['sha256']
  for p in sealed_parts.values():
   assert m.sha(p['import_receipt'])==p['import_receipt_sha256']
   assert m.sha(p['source_path'])==p['source_sha256']
  s=j['states'][a.state];rows=copy.deepcopy(s['rows']);folder=a.root or D;target=folder/Path(s['target_path']).name
  for q in rows:
   q['native_path']=str(folder/Path(q['native_path']).name)
   if q.get('native_delta_part_id'):
    expected_part=sealed_parts[q['native_delta_part_id']]
    assert Path(q['native_path']).name==Path(expected_part['native_path']).name
    q['native_sha256']=expected_part['native_sha256']
  r.update(state=a.state,rows=rows,root=str(folder),new_instance_ids=s['changed_existing_ids']+s['new_instance_ids'])
  assert all(m.sha(q['native_path'])==q['native_sha256'] for q in rows)
  assert sw.SetCurrentWorkingDirectory(str(folder))
  if a.mode=='integrate':
   assert m.sha(s['parent_path'])==s['parent_sha256'] and not target.exists()
   work=folder/f'W_{a.state}.SLDASM';assert not work.exists();shutil.copy2(s['parent_path'],work)
   # Relink all original dependencies while the copied document is closed.
   sourceparts={q['copy_name']:q for q in s['parent_rows']}
   needed={Path(q['native_path']).name for q in rows}
   redirects=[]
   for name,q in sourceparts.items():
    if name not in needed:continue
    old=C/'mechanical/portable/package'/name;new=folder/name
    ok=sw.ReplaceReferencedDocument(str(work),str(old),str(new));assert ok,(name,'redirect failed')
    redirects.append(name)
   r['closed_reference_redirect_count']=len(redirects);b.checkpoint('copied_parent_redirected')
   opened=sw.OpenDoc6(str(work),2,193,'',0,0);assert opened[0] is not None and opened[1]==0,opened[1:]
   model=b.wrap(opened[0],'IModelDoc2');b.activate(model,work);asm=b.wrap(model,'IAssemblyDoc');asm.LightweightAllResolved();lookup=b.identity_inventory(asm,s['parent_rows'])
   model.ClearSelection2(True)
   for ident in s['changed_existing_ids']:assert lookup[ident].Select4(True,None,False)
   ext=b.wrap(model.Extension,'IModelDocExtension');assert ext.DeleteSelection2(0);model.ClearSelection2(True)
   lookup=None;gc.collect();asm.LightweightAllResolved();b.checkpoint('removed_changed_instances',count=152)
   insert=[q for q in rows if q['id'] in set(s['changed_existing_ids']+s['new_instance_ids'])];assert len(insert)==320
   view=b.wrap(model.ActiveView,'IModelView');feature=b.wrap(model.FeatureManager,'IFeatureManager')
   settings=[(sw,'CommandInProgress'),(view,'EnableGraphicsUpdate'),(feature,'EnableFeatureTree'),(feature,'EnableFeatureTreeWindow')];before=[(o,k,bool(getattr(o,k))) for o,k in settings]
   try:
    for o,k in settings:setattr(o,k,k=='CommandInProgress')
    for start in range(0,len(insert),8):
     b.ram_floor();chunk=insert[start:start+8]
     raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[q['native_path'] for q in chunk]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[x for q in chunk for x in h.t16(q['T_S_local'])]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']*len(chunk))) or []
     assert len(raw)==len(chunk);model.ClearSelection2(True)
     for rc,q in zip(raw,chunk):
      comp=b.wrap(rc,'IComponent2');comp.ComponentReference=q['id'];comp.Name2=re.sub(r'[ .()/\\]','_',q['id']);assert comp.Select4(True,None,False)
      if q.get('native_delta_part_id')=='AZUR81442_CIC_GLASS_FOOTPRINT_LAYER':
       comp.MaterialPropertyValues=b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[.035,.12,.28,.4,.8,.2,.2,0.,0.])
     asm.FixComponent();model.ClearSelection2(True);raw=rc=comp=None;gc.collect();asm.LightweightAllResolved();b.checkpoint('inserted',count=start+len(chunk))
    b.identity_inventory(asm,rows)
    props=b.wrap(ext.CustomPropertyManager(''),'ICustomPropertyManager')
    for k,v in dict(WP09D_STATE=a.state,WP09D_COMPONENTS=873,WP09D_RELEASE=False,WP09D_SOLAR='GLASS_FOOTPRINT_CIC_LAYER_PROXY_NOT_COMPLETE_CIC_PACKAGE',WP09D_MOTION='FIXED_POSES_ONLY').items():props.Add3(k,30,str(v),2)
    r['pre_save_state']=dict(needs_rebuild2=int(ext.NeedsRebuild2),save_flag=bool(m.val(model,'GetSaveFlag')))
    r['save_policy']='Fixed imported component graph: save before optional graphics; swSaveAsOptions_Silent|AvoidRebuildOnSave (1|8). Actual state verified by fresh cold membership/T/hash/dependencies.'
    b.checkpoint('saving_fixed_component_graph_without_force_rebuild')
    assert not target.exists();result=ext.SaveAs(str(target),0,9,None,0,0)
    saved=dict(path=str(target),api_return=list(result),ok=bool(result[0]),errors=result[1],warnings=result[2],options=9)
    r['save_attempts'].append(saved);b.checkpoint('save_attempt',**saved)
    assert result[0] and result[1]==0 and target.exists() and target.stat().st_size>0
    saved.update(sha256=m.sha(target),bytes=target.stat().st_size);r['native_save']=saved
    r['post_save_state']=dict(needs_rebuild2=int(ext.NeedsRebuild2),save_flag=bool(m.val(model,'GetSaveFlag')))
    b.close_own_saved(model,target,saved['sha256']);r['closed_before_restoring_graphics']=True
   finally:
    for o,k,v in reversed(before):
     if k=='CommandInProgress' or not r.get('closed_before_restoring_graphics'):setattr(o,k,v)
   before=settings=[];view=feature=props=lookup=ext=asm=None;gc.collect()
   r['native_view_capture_status']='DEFERRED_TO_FRESH_READ_ONLY_COLD_SESSION';model=None;gc.collect()
   r.update(status='PASS_NATIVE_DELTA_SAVED_COLD_INSPECTION_PENDING',component_count=873,expected_solids=1254)
  else:
   if a.root:
    assert folder.resolve()!=D.resolve() and not D.exists(),'Relocation cold check requires original CAD root absent'
    r.update(original_root=str(D),original_root_absent_during_cold_open=True)
   assembly_receipt_path=C/'results'/f'NATIVE_DELTA_INTEGRATE_{a.state}.json';assembly_receipt=json.loads(assembly_receipt_path.read_text(encoding='utf-8'))
   assert assembly_receipt['status']=='PASS_NATIVE_DELTA_SAVED_COLD_INSPECTION_PENDING' and assembly_receipt['state']==a.state
   assert assembly_receipt['input_manifest_sha256']==r['input_manifest_sha256'] and assembly_receipt['imported_parts_snapshot_sha256']==r['imported_parts_snapshot_sha256']
   digest=assembly_receipt['native_save']['sha256'];assert m.sha(target)==digest
   r.update(assembly_save_receipt=str(assembly_receipt_path),assembly_save_receipt_sha256=m.sha(assembly_receipt_path))
   opened=sw.OpenDoc6(str(target),2,195,'',0,0);r['open_errors']=opened[1];r['open_warnings']=opened[2];assert opened[0] is not None and opened[1]==0
   if a.root:assert not D.exists(),'Original CAD root appeared during relocation cold open'
   model=b.wrap(opened[0],'IModelDoc2');b.activate(model,target)
   av=b.wrap(model.ActiveView,'IModelView');af=b.wrap(model.FeatureManager,'IFeatureManager');settings=[(sw,'CommandInProgress'),(av,'EnableGraphicsUpdate'),(af,'EnableFeatureTree'),(af,'EnableFeatureTreeWindow')];old=[(o,k,bool(getattr(o,k))) for o,k in settings]
   try:
    for o,k in settings:setattr(o,k,k=='CommandInProgress')
    lookup,observed=b.metadata(model,rows,False)
   finally:
    for o,k,v in reversed(old):setattr(o,k,v)
   deps=model.GetDependencies2(True,True,False) or [];paths=[deps[i+1] for i in range(0,len(deps),2)]
   assert {m.normalized(p) for p in paths}=={m.normalized(q['native_path']) for q in rows}
   assert all(Path(p).resolve().is_relative_to(folder.resolve()) for p in paths)
   r.update(status='PASS_COLD_NATIVE_DELTA_IDENTITIES_TRANSFORMS_LOCAL_DEPENDENCIES',component_count=len(observed),expected_solids_hash_bound=1254,components=observed,dependencies=paths,external_dependency_count=0,native_sha256=digest,actual_all_body_readback_this_cold_open=False,
    body_credit='138 unique new native parts individually cold-measured; retained geometry exact hash-bound parent. Assembly current membership and transforms read back.')
   r['cold_state_before_optional_view']=dict(needs_rebuild2=int(b.wrap(model.Extension,'IModelDocExtension').NeedsRebuild2),save_flag=bool(m.val(model,'GetSaveFlag')))
   assert m.sha(target)==digest and not m.val(model,'GetSaveFlag')
   lookup=observed=None;av=af=None;settings=old=[];gc.collect()
   if not a.root:
    model.ShowNamedView2('',7);model.ViewZoomtofit2();model.GraphicsRedraw2()
    bmp=folder/f'WP09D_{a.state.upper()}.bmp';assert not bmp.exists()
    r['native_view_capture']=dict(path=str(bmp),api_ok=bool(model.SaveBMP(str(bmp),1600,1200)),native_sha256=digest,view='ACTUAL_COLD_NATIVE_ISOMETRIC_FIT_NO_FORCE_REBUILD')
    assert r['native_view_capture']['api_ok'] and bmp.exists() and m.sha(target)==digest
    r['native_view_capture'].update(sha256=m.sha(bmp),bytes=bmp.stat().st_size)
    r['read_only_view_dirty_flag']=bool(m.val(model,'GetSaveFlag'))
    if r['read_only_view_dirty_flag']:
     assert Path(m.val(model,'GetPathName')).resolve()==target.resolve()
     sw.CloseDoc(m.val(model,'GetTitle'));r['own_readonly_view_only_change_discarded']=True
    else:b.close_own_saved(model,target,digest)
   else:b.close_own_saved(model,target,digest)
   model=None
 if prefs:
  for k,v in prefs['toggles'].items():sw.SetUserPreferenceToggle(k,v)
  for k,v in prefs['strings'].items():sw.SetUserPreferenceStringValue(k,v)
  for k,v in prefs['integers'].items():sw.SetUserPreferenceIntegerValue(k,v)
  prefs=None
 assert not b.documents();sw.ExitApp();r['open_documents_after']=[];b.checkpoint('completed_saved_closed_exit')
except Exception as exc:
 r.update(status='FAILED',error=repr(exc),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
