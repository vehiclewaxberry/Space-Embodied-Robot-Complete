"""Read the existing SolidWorks session without opening/closing/saving documents."""
from pathlib import Path
import json, datetime, psutil
import pythoncom, win32com.client
from win32com.client import gencache
R=Path(__file__).resolve().parents[1]
def val(obj, key):
    value=getattr(obj,key)
    return value() if callable(value) and not hasattr(value,'_oleobj_') else value
def main():
    existing=[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='sldworks.exe']
    assert len(existing)==1, ('Need one existing SolidWorks session',existing)
    pythoncom.CoInitialize()
    t=gencache.GetModuleForTypelib('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,32,0)
    try: raw=win32com.client.GetActiveObject('SldWorks.Application'); route='ROT'
    except Exception: raw=win32com.client.DispatchEx('SldWorks.Application');route='Existing singleton verified by process ID'
    def wrap(x,name):
        if x is None:return None
        cls=getattr(t,name)
        return cls(x._oleobj_.QueryInterface(cls.CLSID,pythoncom.IID_IDispatch))
    sw=wrap(raw,'ISldWorks'); pid=val(sw,'GetProcessID');assert pid in existing
    docs=[]
    for raw_doc in (val(sw,'GetDocuments') or []):
        doc=wrap(raw_doc,'IModelDoc2')
        docs.append({'path':val(doc,'GetPathName'),'title':val(doc,'GetTitle'),
                     'type':val(doc,'GetType'),'unsaved_changes':bool(val(doc,'GetSaveFlag'))})
    active=wrap(val(sw,'ActiveDoc'),'IModelDoc2')
    result={'read_local':datetime.datetime.now().astimezone().isoformat(),'pid':pid,
        'revision':val(sw,'RevisionNumber'),'attachment_route':route,
        'document_count':val(sw,'GetDocumentCount'),'documents':docs,
        'active_path':None if active is None else val(active,'GetPathName'),
        'available_mib':psutil.virtual_memory().available/2**20,
        'documents_opened_closed_or_saved':False}
    (R/'results/SESSION_AFTER_IMPORT_FAILURE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()

