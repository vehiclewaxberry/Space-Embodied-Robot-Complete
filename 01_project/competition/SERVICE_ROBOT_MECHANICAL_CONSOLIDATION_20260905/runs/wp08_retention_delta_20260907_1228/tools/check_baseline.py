"""Re-evaluate current WP07 bytes against its completed cold evidence, no CAD."""
from pathlib import Path
import sys,json,hashlib,datetime,traceback
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
W7=R.parent/'wp07_system_20260907_0610'
sys.path.insert(0,str(W7/'tools'))
import check_native_delivery_v3 as checker

def main():
    for name in ('results','inputs','native','candidate','logs','viewer'):
        (R/name).mkdir(exist_ok=True)
    out=R/'results/BASELINE_CURRENT_CHECK.json'
    assert not out.exists()
    mpath=W7/'results/INTEGRATION_MANIFEST.json'
    manifest=checker.core.read(mpath); msha=checker.core.sha(mpath)
    pins,cache={},{}
    report=dict(schema='WP08_WP07_CURRENT_BASELINE_CHECK',status='RUNNING',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),states={},manifest_sha256=msha,source_manifest=str(mpath),no_CAD_or_COM_executed=True,source_files_modified=False)
    try:
        for p in (Path(__file__),Path(checker.__file__),Path(checker.core.__file__),mpath,W7/'README.md',W7/'results/DELIVERY_STATUS.json',W7/'results/MECHANICAL_MODULE_EXECUTION_STATUS.csv',W7/'results/FINAL_REOPEN_SERVICE_V4.json'):
            checker.pin_file(p,checker.core.sha(p),pins,cache)
        for state in checker.STATES:
            report['states'][state]=checker.check_state(state,manifest,msha,pins,cache)
            print(json.dumps({'state':state,'status':report['states'][state]['status']},ensure_ascii=False),flush=True)
        for k in (0,1):
            p=W7/f'results/RETENTION_NATIVE_S{k}_c03_v1.json'
            checker.pin_file(p,checker.core.sha(p),pins,cache)
            local=checker.core.read(p)
            assert local['status']=='PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY'
        after={p:checker.core.sha(p) for p in pins}
        assert after==pins
        report.update(status='PASS_CURRENT_WP07_THREE_STATE_HASH_BOUND_EVIDENCE',input_sha256_before=pins,input_sha256_after=after,inputs_unchanged=True,inherited_arm_holds_unchanged=True,engineering_release=False,scope='Current source/native bytes, stored body observations, actual COM basis and negative controls. This is not a fresh native reopen or global geometry qualification.')
    except Exception as exc:
        report.update(status='FAIL',error=str(exc),traceback=traceback.format_exc());raise
    finally:
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'pinned_files':len(pins),'output':str(out)},ensure_ascii=False))
if __name__=='__main__':main()
