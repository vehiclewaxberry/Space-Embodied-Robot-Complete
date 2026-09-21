"""Five-part GSE delta; serial native writer, frozen parent preserved."""
from pathlib import Path
import sys,json,copy,importlib.util,shutil,gc,traceback,argparse
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parents[1];R=F.parent
sp=importlib.util.spec_from_file_location('frozen_native_delta',R/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
m=h.m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('state',choices=['service','parking','released']);a=ap.parse_args()
 material=json.loads((F/'results/NATIVE_PORTS_MATERIAL.json').read_text());assert material['status']=='PASS_NATIVE_PORTS_MATERIAL'
 em=json.loads((F/'results/PORTS_EMISSION.json').read_text());assert json.loads((F/'results/PORTS_CHECK.json').read_text())['status']=='PASS_SCOPED_GSE_PORT_GEOMETRY'
 base=json.loads((R/'results/NATIVE_BINDING_MANIFEST.json').read_text())['states'][a.state]
 rows=copy.deepcopy([r for r in base if r['id'] not in em['removed_parent_ids']]);assert len(base)==701 and len(rows)==700
 for k,p in em['parts'].items():
  q=next(x for x in material['records'] if x['id']==k);assert m.sha(q['native_path'])==q['native_sha256']
  rows.append(dict(id='WP09F_'+k,native_path=q['native_path'],native_sha256=q['native_sha256'],T_S_local=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],expected_solids=1,representation_role=p['representation_role'],source_step={'path':p['path'],'sha256':p['sha256']}))
 pd=json.loads((R/'results/DELIVERY_STATUS.json').read_text());ps=pd['native_states'][a.state];parent=Path(ps['native']['path']);parenthash=m.sha(parent);assert parenthash==ps['native']['sha256']
 receipt=Path(ps['execution_receipt']['path']);assert m.sha(receipt)==ps['execution_receipt']['sha256']
 target=F/'native'/('WP09F_'+a.state.upper()+'.SLDASM');work=F/'native/work'/('W_'+a.state+'.SLDASM');out=F/'results'/('NATIVE_'+a.state.upper()+'.json')
 assert not target.exists() and not work.exists() and not out.exists()
 report=dict(status='RUNNING',state=a.state,parent=str(parent),parent_sha256=parenthash,parent_receipt=ps['execution_receipt'],rows=rows,new_instance_ids=[r['id'] for r in rows[700:]],parts=[],progress=[],save_attempts=[],manufacturing_release=False,mate_based_motion=False,body_counts_are_actual=False,retained_body_evidence='PARENT_DELIVERY_COLD_RECEIPTS_HASH_BOUND; CURRENT_METADATA_ALL_COMPONENTS')
 b=None
 try:
  b=h.Builder(out,report);assert not b.documents(),'Existing documents left untouched';sw=b.sw
  work.parent.mkdir(exist_ok=True);shutil.copy2(parent,work)
  opened=sw.OpenDoc6(str(work),2,193,'',0,0);assert opened[0] is not None and opened[1]==0
  model=b.wrap(opened[0],'IModelDoc2');b.activate(model,work);asm=b.wrap(model,'IAssemblyDoc');asm.LightweightAllResolved()
  lookup=b.identity_inventory(asm,base);model.ClearSelection2(True)
  for k in em['removed_parent_ids']:assert lookup[k].Select4(True,None,False)
  ext=b.wrap(model.Extension,'IModelDocExtension');assert ext.DeleteSelection2(0);model.ClearSelection2(True);b.identity_inventory(asm,rows[:700]);b.checkpoint('retained_identity_verified',count=700)
  view=b.wrap(model.ActiveView,'IModelView');feature=b.wrap(model.FeatureManager,'IFeatureManager');settings=[(sw,'CommandInProgress'),(view,'EnableGraphicsUpdate'),(feature,'EnableFeatureTree'),(feature,'EnableFeatureTreeWindow')];saved=[(o,k,bool(getattr(o,k))) for o,k in settings];report['ui_before']={k:v for _,k,v in saved}
  try:
   for o,k in settings:setattr(o,k,k=='CommandInProgress')
   chunk=rows[700:];raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[r['native_path'] for r in chunk]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[x for r in chunk for x in h.t16(r['T_S_local'])]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']*len(chunk))) or [];assert len(raw)==5
   for rc,row in zip(raw,chunk):
    comp=b.wrap(rc,'IComponent2');comp.ComponentReference=row['id'];comp.Name2=row['id'];assert comp.Select4(True,None,False)
   asm.FixComponent();model.ClearSelection2(True);raw=rc=comp=None;gc.collect();asm.LightweightAllResolved();b.identity_inventory(asm,rows)
   props=b.wrap(ext.CustomPropertyManager(''),'ICustomPropertyManager')
   for k,v in dict(WP09F_STATE=a.state,WP09F_STATUS='GSE_FIXED_POSE_CANDIDATE',WP09F_COMPONENTS=705,WP09F_RELEASE=False,WP09F_NEW_BODY_COUNT=5,WP09F_RETAINED_BODY_CREDIT='HASH_BOUND_PARENT_1081').items():props.Add3(k,30,str(v),2)
   model.EditRebuild3();report['native_save']=b.save_new(model,target)
  finally:
   for o,k,v in reversed(saved):setattr(o,k,v)
  b.close_own_saved(model,target,report['native_save']['sha256']);lookup=asm=model=ext=view=feature=None;gc.collect()
  opened=sw.OpenDoc6(str(target),2,195,'',0,0);assert opened[0] is not None and opened[1]==0;cold=b.wrap(opened[0],'IModelDoc2');b.activate(cold,target)
  av=b.wrap(cold.ActiveView,'IModelView');af=b.wrap(cold.FeatureManager,'IFeatureManager');settings=[(sw,'CommandInProgress'),(av,'EnableGraphicsUpdate'),(af,'EnableFeatureTree'),(af,'EnableFeatureTreeWindow')];saved=[(o,k,bool(getattr(o,k))) for o,k in settings]
  try:
   for o,k in settings:setattr(o,k,k=='CommandInProgress')
   _,observed=b.metadata(cold,rows,True);report['cold_components']=observed
  finally:
   for o,k,v in reversed(saved):setattr(o,k,v)
  assert m.sha(target)==report['native_save']['sha256'] and m.sha(parent)==parenthash
  deps=cold.GetDependencies2(False,True,False) or [];assert {m.normalized(deps[i+1]) for i in range(0,len(deps),2)}=={m.normalized(r['native_path']) for r in rows}
  report.update(status='PASS_FIXED_NATIVE_DELTA_WITH_HASH_BOUND_PARENT',component_count=len(observed),expected_solid_count=sum(r.get('expected_solids',1) for r in rows),new_body_count_actual=sum(x.get('actual_solids',0) for x in observed),retained_solid_count_hash_bound=sum(r.get('expected_solids',1) for r in rows[:700]),all_metadata_verified=True,parent_unchanged=True,continuous_motion_verified=False)
  assert report['expected_solid_count']==1086 and report['new_body_count_actual']==5
  if not m.val(cold,'GetSaveFlag'):b.close_own_saved(cold,target,m.sha(target))
  assert not b.documents();sw.ExitApp();b.checkpoint('verified_empty_exit')
 except Exception as ex:
  report.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc())
  if b:b.checkpoint('failed')
  else:out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  raise
 finally:
  if b:b.pythoncom.CoUninitialize()
if __name__=='__main__':main()
