"""Unload only clean, hash-registered saved outputs and dependencies of this run."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import resume_service as recovery
import check_native_delivery_v3 as check
from integrate_native import Integrator,R,normalized,sha,require,val
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--include-retention',action='store_true');a=p.parse_args()
out=(R/'results'/a.output).resolve();require(out.is_relative_to((R/'results').resolve()) and out.suffix=='.json' and not out.exists(),'New output required')
mf=R/'results/INTEGRATION_MANIFEST.json';m=json.loads(mf.read_text(encoding='utf-8'))
recovery.RECOVERY=check.preferred_receipt('service')
allowed,receipts=recovery.registered_inputs(m,sha(mf),include_service_recovery=True)
if a.include_retention:
    for path in (R/'results').glob('RETENTION_NATIVE_S*.json'):
        data=json.loads(path.read_text(encoding='utf-8'))
        require(str(data.get('status','')).startswith('PASS'),'Only completed retention records may be registered')
        saves=[data.get('assembly_save',{})]+[row.get('native_save',{}) for row in data.get('parts',[])]
        for save in saves:
            target=Path(save.get('path','')).resolve()
            require(target.is_relative_to((R/'native').resolve()) and save.get('ok') is True and save.get('errors')==0,'Invalid retention save record')
            require(sha(target)==save['sha256'],'Retention output changed')
            allowed[normalized(target)]=save['sha256']
        receipts[str(path.resolve())]=sha(path)
report=dict(status='RUNNING',progress=[],save_attempts=[],allowed_inputs=allowed,receipt_pins=receipts,no_files_saved_or_deleted=True)
recovery.require_outer_guard(report)
b=Integrator(out,report)
try:
    require(int(val(b.sw,'GetProcessID'))==26208,'Unexpected SW process')
    report['available_before_mib']=b.psutil.virtual_memory().available/2**20
    b.close_registered(allowed)
    require(all(sha(path)==digest for path,digest in {**allowed,**receipts}.items()),'Pinned file bytes changed')
    report.update(status='PASS_CLEAN_REGISTERED_NATIVE_DOCUMENTS_UNLOADED',documents_remaining=len(b.documents()),available_after_mib=b.psutil.virtual_memory().available/2**20,inputs_unchanged=True)
    require(report['documents_remaining']==0,'Unexpected documents remain')
    b.checkpoint('completed')
finally:
    b.pythoncom.CoUninitialize()
