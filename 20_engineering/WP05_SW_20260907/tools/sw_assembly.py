"""Build fixed-pose native assemblies and audit an actual close/reopen."""
from pathlib import Path
import json,time,sys,re,psutil
import pythoncom
from win32com.client import VARIANT
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import val,wrap,sha,write,save,checked_path
R=Path(__file__).resolve().parents[1]
def transform16(T):return [T[i][j] for j in range(3) for i in range(3)]+[T[i][3]/1000 for i in range(3)]+[1.,0.,0.,0.]
def property_of(m,t,name):
 ex=wrap(m.Extension,'IModelDocExtension',t);cp=wrap(ex.CustomPropertyManager(''),'ICustomPropertyManager',t)
 q=cp.Get2(name);return q[0]
def color(row):
 k=row['id']
 if row.get('arm_link'):return [.72,.66,.50]
 if ('solar_leaf' in k or 'solar_panel' in k or (k.startswith('wing_') and '_leaf_' in k)):return [.08,.19,.39]
 if k.startswith('hold_'):return [.82,.69,.38]
 if row['representation_role']=='FUNCTIONAL_ENVELOPE':return [.67,.35,.72]
 if row['product_role'].lower().find('equipment')>=0:return [.28,.56,.51]
 return [.68,.72,.75]
def inspect(sw,t,m,state,expected,imports,asm_path):
 a=wrap(m,'IAssemblyDoc',t)
 assert psutil.virtual_memory().available>=2048*1024**2,'Bulk resolution needs 2 GiB of available headroom'
 m.ClearSelection2(True)
 assert a.ResolveAllLightweight(),'Failed to resolve assembly components for actual body inspection'
 components=a.GetComponents(True) or []
 math_util=wrap(sw.GetMathUtility(),'IMathUtility',t)
 lookup={r['id']:r for r in expected};actual=[]
 for raw in components:
  assert psutil.virtual_memory().available>=512*1024**2,'Available RAM below floor during per-component inspection'
  c=wrap(raw,'IComponent2',t);id=c.ComponentReference
  assert id in lookup,('unregistered native component',id,c.Name2)
  row=lookup[id];p=checked_path(val(c,'GetPathName'))
  assert p==Path(imports[row['part_key']]['target']).resolve()
  if c.GetSuppression2()!=2:c.SetSuppression2(2)
  doc=wrap(c.GetModelDoc2(),'IModelDoc2',t);assert doc is not None,id
  part=wrap(doc,'IPartDoc',t);bs=part.GetBodies2(0,False) or [];sheets=part.GetBodies2(1,False) or []
  native_transform=wrap(c.Transform2,'IMathTransform',t)
  actualT=list(native_transform.ArrayData)
  error=max(abs(x-y) for x,y in zip(actualT,transform16(row['T_S_local'])))
  basis=[];basis_error=0.
  for local in [[0.,0.,0.],[10.,0.,0.],[0.,10.,0.],[0.,0.,10.]]:
   point=wrap(math_util.CreatePoint(VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,[x/1000 for x in local])),'IMathPoint',t)
   world=wrap(point.MultiplyTransform(native_transform),'IMathPoint',t)
   observed=[float(x)*1000 for x in world.ArrayData]
   T=row['T_S_local'];predicted=[sum(T[i][j]*local[j] for j in range(3))+T[i][3] for i in range(3)]
   basis.append(observed);basis_error=max(basis_error,max(abs(x-y) for x,y in zip(observed,predicted)))
  assert basis_error<=1e-5,('Actual SW point transform disagrees with frozen frame',id,basis_error)
  role=property_of(doc,t,'WP05_ROLE')
  assert role==row['representation_role'],(id,role,row['representation_role'])
  assert error<1e-8 and c.IsFixed() and len(bs)==imports[row['part_key']]['facts']['solid_count'] and not sheets,(id,error,len(bs))
  actual.append({'id':id,'name':c.Name2,'part_key':row['part_key'],'path':str(p),'sha256':sha(p),'transform_sw16':actualT,'transformation_max_error':error,'world_basis_points_mm':basis,'world_basis_max_error_mm':basis_error,'representation_role':role,'fixed':bool(c.IsFixed()),'suppression_state':c.GetSuppression2(),'resolved_solid_count':len(bs),'resolved_sheet_count':len(sheets),'visible':c.Visible})
  bs=None;sheets=None;part=None;doc=None
  actual[-1]['post_inspection_suppression_state']=c.GetSuppression2()
  if len(actual)%25==0:write(R/'results/ASSEMBLY_INSPECTION_CURRENT.json',{'assembly':asm_path.name,'inspected':len(actual),'total':len(expected)})
 assert len(actual)==len(expected) and len({x['id'] for x in actual})==len(expected)
 m.ClearSelection2(True)
 assert a.LightweightAllResolved()
 dep=m.GetDependencies2(False,True,False) or []
 assert len(dep)%2==0
 paths=[checked_path(dep[i+1]) for i in range(0,len(dep),2)]
 assert {str(p).lower() for p in paths}=={x['path'].lower() for x in actual}
 return {'state':state,'target':str(asm_path),'components':actual,'component_count':len(actual),'dependencies':[{'path':str(p),'sha256':sha(p)} for p in paths],'status':'NATIVE_FIXED_POSE_ASSEMBLY_COLD_REOPENED','storage_mode':'LIGHTWEIGHT; BULK_RESOLVED_FOR_INDIVIDUAL_BODY_INSPECTION','physical_assembly_completed':False,'manufacturing_release':False,'continuous_motion_verified':False,'mate_based_motion_model':False}
def main(sw,t,job):
 mf=json.loads(checked_path(job['manifest']).read_text(encoding='utf-8'))
 ip=json.loads((R/'results/NATIVE_IMPORTS.json').read_text(encoding='utf-8'))
 imports={p['part_key']:p for p in ip['parts']}
 state=job.get('state','service');rows=mf['states'][state]['instances']
 if job.get('ids'):rows=[r for r in rows if r['id'] in set(job['ids'])]
 if job.get('limit'):rows=rows[:job['limit']]
 assert all(r['part_key'] in imports for r in rows)
 name=job.get('name','WP05_ROBOT_'+state.upper())
 target=R/'assemblies'/(name+'.SLDASM');assert not target.exists(),'Native assembly already exists; audit existing or use new candidate name'
 old=sw.CommandInProgress; m=None
 try:
  sw.CommandInProgress=True
  m=wrap(sw.NewDocument(str(Path('C:/ProgramData/SolidWorks/SOLIDWORKS 2024/templates/gb_assembly.asmdot')),0,0.,0.),'IModelDoc2',t)
  assert m is not None and val(m,'GetType')==2
  a=wrap(m,'IAssemblyDoc',t)
  view=wrap(m.ActiveView,'IModelView',t);view.EnableGraphicsUpdate=False
  for start in range(0,len(rows),25):
   assert psutil.virtual_memory().available>=512*1024**2,'Available RAM below declared 512 MiB floor'
   batch=rows[start:start+25]
   paths=[imports[r['part_key']]['target'] for r in batch];data=[z for r in batch for z in transform16(r['T_S_local'])]
   parts=a.AddComponents3(VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_BSTR,paths),VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,data),VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_BSTR,['']*len(paths))) or []
   assert len(parts)==len(batch),(len(parts),len(batch))
   m.ClearSelection2(True)
   for raw,row in zip(parts,batch):
    c=wrap(raw,'IComponent2',t);c.ComponentReference=row['id']
    c.Name2=re.sub(r'[ .()/]','_',row['id'])
    actual=list(wrap(c.Transform2,'IMathTransform',t).ArrayData)
    assert max(abs(x-y) for x,y in zip(actual,transform16(row['T_S_local'])))<1e-8,(row['id'],actual)
    c.MaterialPropertyValues=VARIANT(pythoncom.VT_ARRAY|pythoncom.VT_R8,color(row)+[.6,.6,.3,.2,0.,0.])
    if row['representation_role']=='FUNCTIONAL_ENVELOPE':c.Visible=0
    assert c.Select4(True,None,False)
   a.FixComponent()
   m.ClearSelection2(True)
   assert a.LightweightAllResolved(),'Could not switch inserted components to lightweight'
   write(R/'results/ASSEMBLY_CURRENT.json',{'assembly':name,'added':min(start+25,len(rows)),'total':len(rows)})
   print(json.dumps({'assembly':name,'added':min(start+25,len(rows))}),flush=True)
  cp=wrap(wrap(m.Extension,'IModelDocExtension',t).CustomPropertyManager(''),'ICustomPropertyManager',t)
  for k,v in {'WP05_STATUS':'FIXED_POSE_DIGITAL_ASSEMBLY_NOT_HARDWARE_RELEASE','WP05_STATE':state,'WP05_SOURCE_MANIFEST_SHA256':sha(job['manifest']),'WP05_INSTANCES':len(rows)}.items():cp.Add3(k,30,str(v),2)
  m.EditRebuild3()
  view.EnableGraphicsUpdate=True;m.ShowNamedView2('',7);m.ViewZoomtofit2();m.GraphicsRedraw2()
  warm_save=save(m,t,target);sw.CloseDoc(val(m,'GetTitle'));m=None
  q=sw.OpenDoc6(str(target),2,193,'',0,0);m=wrap(q[0],'IModelDoc2',t);assert m is not None and q[1]==0,q
  result=inspect(sw,t,m,state,rows,imports,target)
  result.update(warm_save=warm_save,open_errors=q[1],open_warnings=q[2],target_sha256=sha(target),source_manifest_sha256=sha(job['manifest']),resolved_solid_total=sum(c['resolved_solid_count'] for c in result['components']))
  m.ShowNamedView2('',7);m.ViewZoomtofit2();m.GraphicsRedraw2()
  bmp=R/'screenshots'/(name+'.bmp');result['screenshot_saved']=bool(m.SaveBMP(str(bmp),1600,1200));result['screenshot']=str(bmp)
  write(R/'results'/(name+'_COLD.json'),result)
  if not job.get('keep_open'):sw.CloseDoc(val(m,'GetTitle'));m=None
  return {'name':name,'component_count':len(rows),'status':result['status'],'target':str(target),'screenshot_saved':result['screenshot_saved']}
 finally:
  sw.CommandInProgress=old
