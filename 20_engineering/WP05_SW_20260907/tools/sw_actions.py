from pathlib import Path
import json,hashlib,time,math,sys
import pythoncom,psutil
from win32com.client import VARIANT
R=Path(__file__).resolve().parents[1]
def val(o,n,*a):
 q=getattr(o,n);return q(*a) if callable(q) and not hasattr(q,'_oleobj_') else q
def wrap(o,name,t):
 if o is None:return None
 k=getattr(t,name);return k(o._oleobj_.QueryInterface(k.CLSID,pythoncom.IID_IDispatch))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def feature_refs(m,t):
 f=m.FirstFeature(); rows=[]
 while f is not None:
  q=wrap(f,'IFeature',t)
  rows.append({'name':q.Name,'type':q.GetTypeName2(),'is_3d_interconnect':bool(q.Is3DInterconnectFeature)})
  f=q.GetNextFeature()
  assert len(rows)<5000
 return rows
def checked_path(p):
 p=Path(p).resolve();assert p.is_relative_to(R.resolve());return p
def body_facts(m,t):
 p=wrap(m,'IPartDoc',t);bs=p.GetBodies2(0,False) or [];sheets=p.GetBodies2(1,False) or []
 rows=[]
 for raw in bs:
  b=wrap(raw,'IBody2',t);mp=b.GetMassProperties(1.0)
  extremes=[]
  for axis in range(3):
   pair=[]
   for sign in [-1,1]:
    d=[0.,0.,0.];d[axis]=sign
    q=b.GetExtremePoint(*d);assert q[0]
    pair.append(q[axis+1]*1000)
   extremes.append(pair)
  rows.append({'volume_mm3':mp[3]*1e9,'bounds_mm':[[x[0] for x in extremes],[x[1] for x in extremes]],'faces':val(b,'GetFaceCount')})
 return {'solid_count':len(bs),'sheet_count':len(sheets),'volume_mm3':sum(x['volume_mm3'] for x in rows),'bounds_mm':[[min(x['bounds_mm'][0][i] for x in rows) for i in range(3)],[max(x['bounds_mm'][1][i] for x in rows) for i in range(3)]] if rows else None,'bodies':rows}
def save(m,t,p):
 ex=wrap(m.Extension,'IModelDocExtension',t);s=ex.SaveAs(str(p),0,1,None,0,0)
 assert isinstance(s,tuple) and s[0] and s[1]==0,(str(p),s)
 assert Path(p).stat().st_size>0
 return {'ok':s[0],'errors':s[1],'warnings':s[2],'sha256':sha(p)}
def import_one(sw,t,source,target,meta=None):
 source=checked_path(source);target=checked_path(target)
 previous={k:sw.GetUserPreferenceToggle(k) for k in [111,291,691]}
 strings={k:sw.GetUserPreferenceStringValue(k) for k in [8,9,10]}
 integers={k:sw.GetUserPreferenceIntegerValue(k) for k in [577,578,579,580]}
 m=None
 try:
  for k in previous:sw.SetUserPreferenceToggle(k,k==111)
  for k,f in [(8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')]:
   sw.SetUserPreferenceStringValue(k,str(Path('C:/ProgramData/SolidWorks/SOLIDWORKS 2024/templates')/f))
  for k,v in {577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
  imp=wrap(sw.GetImportFileData(str(source)),'IImportStepData',t);imp.MapConfigurationData=False
  q=sw.LoadFile4(str(source),'r',imp,0);m=wrap(q[0],'IModelDoc2',t);assert m is not None and q[1]==0,q
  assert val(m,'GetType')==1,val(m,'GetType')
  ex=wrap(m.Extension,'IModelDocExtension',t);ex.BreakAllExternalFileReferences2(True)
  facts=body_facts(m,t)
  assert facts['solid_count']>0,facts
  custom=wrap(ex.CustomPropertyManager(''),'ICustomPropertyManager',t)
  props={'WP05_SOURCE_SHA256':sha(source),'WP05_SOURCE_FILE':source.name,'WP05_STATUS':'DIGITAL_CANDIDATE_NOT_MANUFACTURING_RELEASE','WP05_FEATURE_HISTORY':'IMPORTED_BREP_NOT_PARAMETRIC_FEATURE_RECONSTRUCTION'}
  if meta:
   props.update({'WP05_INSTANCE_ID':meta.get('id',meta.get('part_key','')),'WP05_ROLE':meta.get('representation_role',meta.get('role','UNKNOWN'))})
  for k,v in props.items(): custom.Add3(k,30,str(v),2)
  saved=save(m,t,target);sw.CloseDoc(val(m,'GetTitle'));m=None
  q=sw.OpenDoc6(str(target),1,3,'',0,0);m=wrap(q[0],'IModelDoc2',t);assert m is not None and q[1]==0,q
  cold=body_facts(m,t);assert cold['solid_count']==facts['solid_count']
  assert abs(cold['volume_mm3']-facts['volume_mm3'])<=max(1e-4,abs(facts['volume_mm3'])*1e-8)
  ext=wrap(m.Extension,'IModelDocExtension',t)
  refs=m.ListExternalFileReferencesCount2()
  aux=m.ListAuxiliaryExternalFileReferencesCount()
  features=feature_refs(m,t)
  interconnect=sum(x['is_3d_interconnect'] for x in features)
  result={'source':str(source),'source_sha256':sha(source),'target':str(target),'native_save':saved,'import_error':q[1],'reopen_warning':q[2],'facts':cold,'external_reference_count':refs,'auxiliary_reference_count':aux,'interconnect_feature_count':interconnect,'features':features,'status':'NATIVE_PART_SAVED_AND_REOPENED'}
  if meta and 'expected_volume_mm3' in meta:
   ev=meta['expected_volume_mm3'];diff=abs(cold['volume_mm3']-ev)
   if diff>max(1e-4,abs(ev)*1e-7):
    accurate=ext.GetMassProperties2(2,0,False)
    result['facts']['highest_accuracy_volume_mm3']=accurate[0][3]*1e9
    result['facts']['highest_accuracy_status']=accurate[1]
    result['roundtrip_required']=True
    result['roundtrip_reason']='Cross-kernel scalar volume mismatch; actual material equivalence is pending a separate visible-document export and same-kernel comparison'
  assert refs==0 and aux==0 and interconnect==0,result
  return result
 finally:
  if m is not None:
   sw.CloseDoc(val(m,'GetTitle'))
  for k,v in previous.items():sw.SetUserPreferenceToggle(k,v)
  for k,v in strings.items():sw.SetUserPreferenceStringValue(k,v)
  for k,v in integers.items():sw.SetUserPreferenceIntegerValue(k,v)
def main(sw,t,job):
 if job['action']=='probe':
  a=val(sw,'ActiveDoc')
  d={'revision':val(sw,'RevisionNumber'),'docs':val(sw,'GetDocumentCount'),'active':None}
  if a:
   a=wrap(a,'IModelDoc2',t);d['active']={'title':val(a,'GetTitle'),'path':val(a,'GetPathName'),'type':val(a,'GetType')}
   if job.get('close_known_empty_smoke') and d['active']['title']=='Part1' and d['active']['path']=='':
    assert not (wrap(a,'IPartDoc',t).GetBodies2(0,False) or [])
    sw.CloseDoc('Part1');d['closed_own_empty_smoke']=True
  return d
 if job['action']=='import_one':
  return import_one(sw,t,job['source'],job['target'],job.get('meta'))
 if job['action']=='import_all':
  manifest_path=checked_path(job['manifest']);manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
  dest=R/'results/NATIVE_IMPORTS.json'
  report=json.loads(dest.read_text(encoding='utf-8')) if dest.exists() else {'schema':'WP05_NATIVE_PART_IMPORT_V1','status':'BUILDING','parts':[],'physical_assembly_completed':False,'manufacturing_release':False}
  report['manifest_sha256']=sha(manifest_path)
  allowed_keys={p['part_key'] for p in manifest['parts']}
  extras=[p for p in report['parts'] if p['part_key'] not in allowed_keys]
  if extras:
   write(R/'results/NATIVE_IMPORT_SUPERSEDED_BY_DEDUP.json',{'reason':'Equivalent local geometry now shares canonical native part; earlier smoke files retained','parts':extras})
   report['parts']=[p for p in report['parts'] if p['part_key'] in allowed_keys]
  failed=[p for p in report['parts'] if not p.get('source_comparison',{}).get('pass') and not p.get('roundtrip_required') and not p.get('roundtrip')]
  if failed:
   write(R/'results'/('NATIVE_IMPORT_FAILED_'+str(int(time.time()))+'.json'),{'parts':failed,'reason':'Preserved failed earlier witness; retry requires a new actual readback'})
   report['parts']=[p for p in report['parts'] if p.get('source_comparison',{}).get('pass') or p.get('roundtrip_required') or p.get('roundtrip')]
  done={x['part_key']:x for x in report['parts']}
  old_command=sw.CommandInProgress
  try:
   sw.CommandInProgress=True;sw.DocumentVisible(False,1)
   selected=manifest['parts'][:job['limit']] if job.get('limit') else manifest['parts']
   for p in selected:
    assert sha(p['path'])==p['sha256']
    if p['part_key'] in done:
     x=done[p['part_key']];assert sha(x['target'])==x['native_save']['sha256'];continue
    if psutil.virtual_memory().available<512*1024**2:raise RuntimeError('Available RAM below 512 MiB; progress saved')
    write(R/'results/NATIVE_IMPORT_CURRENT.json',{'part_key':p['part_key'],'completed':len(done),'total':len(selected),'started':time.time()})
    x=import_one(sw,t,p['path'],R/'parts'/(p['part_key']+'.SLDPRT'),p)
    x['part_key']=p['part_key'];x['representation_role']=p['representation_role']
    facts=x['facts'];ev=p['expected_volume_mm3']
    x['source_comparison']={'solid_count_match':facts['solid_count']==p['expected_solid_count'],'volume_difference_mm3':abs(facts['volume_mm3']-ev),'volume_tolerance_mm3':max(1e-4,abs(ev)*1e-7)}
    expected=p['local_bounds_mm'];expected=[expected['min_mm'],expected['max_mm']] if isinstance(expected,dict) else expected
    x['source_comparison']['bbox_difference_mm']=max(abs(facts['bounds_mm'][s][i]-expected[s][i]) for s in range(2) for i in range(3))
    x['source_comparison']['pass']=x['source_comparison']['solid_count_match'] and x['source_comparison']['volume_difference_mm3']<=x['source_comparison']['volume_tolerance_mm3'] and x['source_comparison']['bbox_difference_mm']<=1e-3 and facts['sheet_count']==0
    report['parts'].append(x);done[p['part_key']]=x;write(dest,report)
    if not x['source_comparison']['pass']:
     assert x.get('roundtrip_required') and x['source_comparison']['solid_count_match'] and x['source_comparison']['bbox_difference_mm']<=1e-3 and facts['sheet_count']==0,x['source_comparison']
     x['source_comparison']['status']='PENDING_SAME_KERNEL_MATERIAL_ROUNDTRIP'
     write(dest,report)
    print(json.dumps({'native_parts_completed':len(done),'part':p['part_key']}),flush=True)
   pending=sum(not p['source_comparison']['pass'] for p in report['parts'])
   report['status']=('NATIVE_PARTS_SAVED_REOPENED_ROUNDTRIP_PENDING' if pending else 'NATIVE_PARTS_SAVED_REOPENED_AND_GEOMETRY_MATCHED') if len(done)==len(manifest['parts']) else 'PARTIAL_VERIFIED_BATCH'
   report['roundtrip_pending_count']=pending
   report['part_count']=len(done);write(dest,report)
   return {'part_count':len(done),'status':report['status']}
  finally:
   sw.DocumentVisible(True,1);sw.CommandInProgress=old_command
 raise ValueError(job['action'])
