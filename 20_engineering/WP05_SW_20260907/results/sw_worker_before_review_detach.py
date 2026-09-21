"""Single STA owner for this run. Executes only run-local tool modules, sequentially."""
from pathlib import Path
import sys,json,time,traceback,importlib.util,os
import pythoncom,win32com.client
from win32com.client import gencache
R=Path(__file__).resolve().parents[1]
Q=R/'queue';Q.mkdir(exist_ok=True)
pythoncom.CoInitialize()
types=gencache.GetModuleForTypelib('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,32,0)
try:
 raw=win32com.client.GetActiveObject('SldWorks.Application');mode='attached'
except Exception:
 raw=win32com.client.DispatchEx('SldWorks.Application');mode='launched_for_WP05'
sw=types.ISldWorks(raw._oleobj_.QueryInterface(types.ISldWorks.CLSID,pythoncom.IID_IDispatch))
sw.Visible=True
sw.UserControl=True
def val(obj,n,*args):
 x=getattr(obj,n);return x(*args) if callable(x) else x
session={'mode':mode,'revision':val(sw,'RevisionNumber'),'worker_pid':os.getpid(),'sw_pid':val(sw,'GetProcessID'),'documents_before':val(sw,'GetDocumentCount'),'single_com_writer':True}
(R/'results/SW_SESSION.json').write_text(json.dumps(session,indent=2),encoding='utf-8')
print(json.dumps(session),flush=True)
while True:
 for p in sorted(Q.glob('*.json')):
  done=Q/(p.stem+'.done')
  if done.exists():continue
  job=json.loads(p.read_text(encoding='utf-8'))
  result={'job':p.name,'started':time.time()}
  try:
   module=(R/'tools'/job['module']).resolve()
   assert module.is_relative_to((R/'tools').resolve()) and module.suffix=='.py'
   spec=importlib.util.spec_from_file_location('wp05_job',module);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   result['result']=m.main(sw,types,job);result['ok']=True
  except Exception as e:
   result.update(ok=False,error=repr(e),traceback=traceback.format_exc())
  result['finished']=time.time()
  done.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'job':p.name,'ok':result['ok'],'error':result.get('error')}),flush=True)
 pythoncom.PumpWaitingMessages()
 time.sleep(.2)

