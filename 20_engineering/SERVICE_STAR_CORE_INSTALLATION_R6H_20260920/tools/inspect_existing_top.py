"""Read-only inventory of a top file found after interruption."""
from pathlib import Path
import sys,json,hashlib,traceback
D=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(D.parent/'SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/tools'))
import native_integrate as ni
ni.OUT=D;ni.configure_com();rp=D/'results/EXISTING_TOP_INVENTORY.json'
r=dict(status='RUNNING',progress=[],save_attempts=[]);b=ni.PrototypeBuilder(rp,r);doc=None
target=D/'native/SERVICE_STAR_SERVICE_R6H.SLDASM';before=ni.m.sha(target)
try:
    x=b.sw.OpenDoc6(str(target),2,195,'',0,0);assert x[0] is not None and x[1]==0,x[1:]
    doc=b.wrap(x[0],'IModelDoc2');asm=b.wrap(doc,'IAssemblyDoc');rows=[]
    for raw in asm.GetComponents(True) or []:
        c=b.wrap(raw,'IComponent2');rows.append(dict(id=c.ComponentReference,path=c.GetPathName(),fixed=bool(c.IsFixed()),suppression=int(c.GetSuppression2()),T=list(b.wrap(c.Transform2,'IMathTransform').ArrayData)))
    r.update(status='READ_ONLY_INVENTORY_COMPLETE',sha256=before,top_rows=rows,errors=x[1],warnings=x[2],needs_rebuild2=int(b.wrap(doc.Extension,'IModelDocExtension').NeedsRebuild2))
    b.sw.CloseDoc(ni.m.val(doc,'GetTitle'));doc=None;assert ni.m.sha(target)==before;b.checkpoint('complete')
except Exception as e:r.update(status='FAILED_CLOSED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
finally:
    if doc is not None:b.sw.CloseDoc(ni.m.val(doc,'GetTitle'))
    b.pythoncom.CoUninitialize()
