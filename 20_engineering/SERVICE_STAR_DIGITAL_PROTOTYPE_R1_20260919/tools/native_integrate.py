"""Isolated native prototype construction; source assemblies are never modified."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, shutil, sys, traceback
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
RUNS = ROOT/'01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs'
C = RUNS/'wp09_interfaces_20260907_1525/system_completion'
SPEC = importlib.util.spec_from_file_location('verified_native_helper', C.parent/'tools/integrate_native_v5.py')
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)
m = h.m

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,d): Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def configure_com():
    import win32com, win32com.client, win32com.gen_py
    from win32com.client import gencache
    cache=OUT/'tools/_generated_com'
    cache.mkdir(exist_ok=True)
    win32com.__gen_path__=str(cache)
    win32com.gen_py.__path__=[str(cache)]
    gencache.is_readonly=False
    gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,32,0)

class PrototypeBuilder(h.Builder):
    def __init__(self, report_path, report):
        import pythoncom, psutil, win32com.client
        from win32com.client import gencache, VARIANT
        self.pythoncom,self.psutil,self.VARIANT=pythoncom,psutil,VARIANT
        self.report_path,self.report=report_path,report
        pythoncom.CoInitialize();self.initialized=True
        self.types=gencache.GetModuleForTypelib('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,32,0)
        before=[p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='sldworks.exe']
        # A separate desktop COM context may have no ROT entry. Dispatch is
        # permitted only if its document inventory is empty; no other process
        # is stopped, and no unknown document is closed or changed.
        try:raw=win32com.client.GetActiveObject('SldWorks.Application')
        except Exception:raw=win32com.client.DispatchEx('SldWorks.Application')
        self.sw=self.wrap(raw,'ISldWorks')
        pid=int(m.val(self.sw,'GetProcessID'))
        report['session']={'pid':pid,'processes_before':before,'new_process':pid not in before,
                           'documents_before':[d for _,d in self.documents()]}
        self.checkpoint('attached_document_inventory')
        assert not self.documents(),'Unknown documents left untouched'
        self.sw.Visible=True;self.sw.UserControl=True

def prepare():
    src = read(C/'results/NATIVE_DELTA_DELIVERY.json')
    hierarchy = read(C/'results/NATIVE_DELTA_HIERARCHY_INPUTS.json')
    plan = {'status':'SOURCE_BOUND_COPY_PLAN', 'source_delivery':str(C/'results/NATIVE_DELTA_DELIVERY.json'),
            'source_delivery_sha256':m.sha(C/'results/NATIVE_DELTA_DELIVERY.json'), 'parts':[], 'assemblies':[],
            'whole_design_complete':False, 'ground_power_authorized_by_this_file':False}
    old = Path(src['package_dir'])
    for f in src['package_files']:
        if Path(f['file']).suffix.lower() not in ('.sldprt','.sldasm'): continue
        source = old/f['file']; target = OUT/'native'/f['file']
        assert m.sha(source)==f['sha256'],str(source)
        row = {'source':str(source),'target':str(target),'source_sha256':f['sha256']}
        plan['parts' if source.suffix.lower()=='.sldprt' else 'assemblies'].append(row)
    plan['hierarchy']=hierarchy
    write(OUT/'inputs/NATIVE_COPY_PLAN.json',plan)
    print('verified plan',len(plan['parts']),len(plan['assemblies']))

def copy_native():
    configure_com()
    plan=read(OUT/'inputs/NATIVE_COPY_PLAN.json')
    report={'status':'BUILDING','progress':[],'copied':[],'redirected':[]}
    rp=OUT/'results/NATIVE_COPY.json'
    b=PrototypeBuilder(rp,report)
    try:
        assert not b.documents(),'Open documents left untouched'
        targets={m.normalized(x['source']):x['target'] for x in plan['parts']+plan['assemblies']}
        for x in plan['parts']+plan['assemblies']:
            assert m.sha(x['source'])==x['source_sha256']
            p=Path(x['target']);assert p.resolve().is_relative_to(OUT) and not p.exists()
            shutil.copy2(x['source'],p)
            report['copied'].append(x)
        b.checkpoint('copied_verified_whitelist',files=len(report['copied']))
        groups=[x for x in plan['assemblies'] if Path(x['target']).name.startswith('G_')]
        tops=[x for x in plan['assemblies'] if x not in groups]
        for x in groups+tops:
            deps=b.sw.GetDocumentDependencies2(x['target'],False,False,False) or []
            paths=[deps[i+1] for i in range(0,len(deps),2)]
            for p in paths:
                assert m.normalized(p) in targets,p
                assert b.sw.ReplaceReferencedDocument(x['target'],p,targets[m.normalized(p)]),p
            actual=b.sw.GetDocumentDependencies2(x['target'],True,False,False) or []
            actual=[actual[i+1] for i in range(0,len(actual),2)]
            assert all(Path(p).resolve().is_relative_to(OUT/'native') for p in actual),actual
            report['redirected'].append({'path':x['target'],'direct_count':len(paths),'recursive_count':len(actual),'sha256':m.sha(x['target'])})
            b.checkpoint('closed_reference_redirect_verified',assembly=Path(x['target']).name)
        assert all(m.sha(x['source'])==x['source_sha256'] for x in report['copied'])
        report.update(status='PASS_ISOLATED_COPY_STORED_DEPENDENCIES_ONLY',source_files_unchanged=True,cold_reopen_verified=False)
        b.checkpoint('copy_complete')
    except Exception as e:
        report.update(status='FAILED',error=str(e),traceback=traceback.format_exc());b.checkpoint('failed');raise
    finally:b.pythoncom.CoUninitialize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','copy']);args=ap.parse_args()
    {'prepare':prepare,'copy':copy_native}[args.mode]()
