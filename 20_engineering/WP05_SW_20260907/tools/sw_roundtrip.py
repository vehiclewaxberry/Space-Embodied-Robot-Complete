"""Export only activated visible native documents; independent OCC validates later."""
from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import R,wrap,val,sha,write,checked_path,save
def main(sw,t,job):
 dest=R/'results/NATIVE_IMPORTS.json'
 report=json.loads(dest.read_text(encoding='utf-8'))
 rows=[x for x in report['parts'] if x.get('roundtrip_required') or job.get('all_parts')]
 if job.get('limit'):rows=rows[:job['limit']]
 old=sw.CommandInProgress;sw.CommandInProgress=False;sw.DocumentVisible(True,1)
 try:
  for x in rows:
   native=checked_path(x['target']);assert sha(native)==x['native_save']['sha256']
   if x.get('roundtrip') and Path(x['roundtrip']['path']).exists() and sha(x['roundtrip']['path'])==x['roundtrip']['save']['sha256']:continue
   write(R/'results/ROUNDTRIP_CURRENT.json',{'part_key':x['part_key'],'started':time.time(),'phase':'open_visible_native'})
   m=None
   try:
    q=sw.OpenDoc6(str(native),1,1,'',0,0);m=wrap(q[0],'IModelDoc2',t);assert m is not None and q[1]==0,q
    activation=sw.ActivateDoc3(val(m,'GetTitle'),False,0,0)
    active=wrap(val(sw,'ActiveDoc'),'IModelDoc2',t)
    assert active is not None and Path(val(active,'GetPathName')).resolve()==native
    active.ClearSelection2(True)
    target=R/'roundtrip'/(native.stem+'.step')
    write(R/'results/ROUNDTRIP_CURRENT.json',{'part_key':x['part_key'],'started':time.time(),'phase':'save_active_step'})
    saved=save(active,t,target)
    assert sha(native)==x['native_save']['sha256'],'Native input changed during neutral export'
    x['roundtrip']={'path':str(target),'save':saved,'native_sha256':sha(native),'active_document_confirmed':True,'all_selections_cleared':True,'reason':'Scalar volume diagnostic requires independent same-kernel geometry comparison'}
    write(dest,report)
    print(json.dumps({'step_roundtrip_saved':x['part_key']}),flush=True)
   finally:
    if m is not None:sw.CloseDoc(val(m,'GetTitle'))
  return {'exported_count':sum(bool(x.get('roundtrip')) for x in rows),'selected_count':len(rows),'status':'ACTUAL_STEP_EXPORTS_PENDING_OCC_REVIEW'}
 finally:sw.CommandInProgress=old
