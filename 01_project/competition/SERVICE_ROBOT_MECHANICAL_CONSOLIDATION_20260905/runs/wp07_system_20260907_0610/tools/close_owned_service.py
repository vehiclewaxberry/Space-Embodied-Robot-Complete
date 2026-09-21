"""Unload only the saved, hash-pinned WP07 SERVICE and its clean dependencies."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from integrate_native import Integrator,R,normalized,sha,require,val
p=R/'results'/(sys.argv[1] if len(sys.argv)>1 else 'CLOSE_SERVICE_FOR_MEMORY.json')
require(p.resolve().is_relative_to((R/'results').resolve()) and p.suffix=='.json','Invalid output')
require(not p.exists(),'Existing receipt protected')
m=json.loads((R/'results/INTEGRATION_MANIFEST.json').read_text(encoding='utf-8'))
n=json.loads((R/'results/NATIVE_SERVICE.json').read_text(encoding='utf-8'))
saved=n['native_save'];require(saved['ok'] and saved['errors']==0,'No successful native save')
allowed={normalized(r['native_path']):r['native_sha256'] for r in m['states']['service']['instances']}
allowed[normalized(saved['path'])]=saved['sha256']
report=dict(status='RUNNING',progress=[],save_attempts=[],native_path=saved['path'],native_sha256=saved['sha256'])
b=Integrator(p,report)
require(int(val(b.sw,'GetProcessID'))==26208,'Unexpected SW PID')
report['available_before_mib']=b.psutil.virtual_memory().available/2**20
b.close_registered(allowed)
require(all(sha(path)==digest for path,digest in allowed.items()),'Pinned file changed while unloading')
report.update(status='CLEAN_REGISTERED_SERVICE_UNLOADED',available_after_mib=b.psutil.virtual_memory().available/2**20,
              documents_remaining=len(b.documents()),files_saved_modified_deleted=False)
b.checkpoint('completed')
b.pythoncom.CoUninitialize()
print(json.dumps({k:v for k,v in report.items() if k not in ['progress','attachment_attempt']}))
