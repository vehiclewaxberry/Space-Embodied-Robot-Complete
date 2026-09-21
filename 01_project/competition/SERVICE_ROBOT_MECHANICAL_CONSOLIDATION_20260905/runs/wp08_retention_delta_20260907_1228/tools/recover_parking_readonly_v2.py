"""Read-only recovery of the WP08 file saved after the Python guard stopped.

The interrupted save's COM return is UNKNOWN. Its on-disk file must pass a new
complete cold read, exact membership, transforms, dependencies and body counts.
No previous body result is reused; no file is re-saved or replaced.
"""
from pathlib import Path
import sys,json,traceback,gc
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'tools'))
import integrate_native_delta as writer
from check_native_delta import read,sha,norm,expected_rows
require=writer.require

def main():
    output=R/'results/NATIVE_PARKING_RECOVERY_V2.json';require(not output.exists(),'Recovery receipt protected')
    mp=R/'results/INTEGRATION_MANIFEST.json';m=read(mp);info=m['states']['parking']
    interrupted=R/'results/NATIVE_PARKING.json';guard=R/'logs/native_parking.run.json'
    old=read(interrupted);g=read(guard)
    require(g['status']=='AVAILABLE_MEMORY_GUARD' and g['command'][-1]=='parking' and norm(g['cwd'])==norm(R),'Wrong interrupted run')
    require(old['manifest_sha256']==sha(mp) and old['state']=='parking','Interrupted provenance differs')
    require(old['after_exact_deletion']['unchanged_survivor_metadata'] and len(old['after_exact_deletion']['retained_ids'])==591,'Deletion provenance incomplete')
    target=R/'native/WP08_ROBOT_PARKING.SLDASM';require(target.is_file(),'No actual native file')
    digest=sha(target)
    report=dict(schema='WP08_READONLY_NATIVE_RECOVERY',status='RUNNING',state='parking',progress=[],save_attempts=[],
        manifest_sha256=sha(mp),save_api_acknowledgement='UNKNOWN_WORKER_TERMINATED_WHILE_SOLIDWORKS_COMPLETED_SAVE',
        prior_body_measurement_credit=0,full_STEP_verified=False,global_collision_verified=False,
        continuous_motion_verified=False,manufacturing_release=False,
        recovery_basis=dict(interrupted_receipt=str(interrupted),interrupted_sha256=sha(interrupted),
            guard_path=str(guard),guard_sha256=sha(guard),guard_status=g['status'],observed_saved_file_sha256=digest,
            source_probe=str(R/'results/SESSION_AFTER_PARKING_GUARD.json')),
        native_save=dict(path=str(target),sha256=digest,bytes=target.stat().st_size,
            source='OBSERVED_EXISTING_FILE_NO_SAVE_API_SUCCESS_CLAIM',ok=None,errors=None,warnings=None))
    builder=None
    try:
        writer.reuse.require_outer_guard(report)
        pins=dict(m['input_sha256_after'])
        for p in (mp,interrupted,guard,target,Path(__file__),Path(writer.__file__),R/'tools/check_native_delta.py',R/'results/SESSION_AFTER_PARKING_GUARD.json'):
            pins[str(p.resolve())]=sha(p)
        for p in (R/'tools/recover_parking_readonly.py',R/'results/NATIVE_PARKING_RECOVERY.json'):
            pins[str(p.resolve())]=sha(p)
        report['preflight_correction']='V1 closed no files: registry slash normalization differed from inherited close_registered; V2 uses the exact inherited normalizer, with same exact-path/hash/dirty guards.'
        report['input_sha256_before']=pins
        require(all(sha(p)==d for p,d in pins.items()),'Input pin changed')
        builder=writer.Builder(output,report);require(int(writer.val(builder.sw,'GetProcessID'))==26208,'Singleton changed')
        report['documents_before']=[d for _,d in builder.documents()]
        report['memory_before_scoped_close']=builder.memory_snapshot()
        allowed={writer.oldbase.normalized(r['native_path']):r['native_sha256'] for s in m['states'].values() for r in s['instances']}
        allowed[writer.oldbase.normalized(target)]=digest
        for p in (R/'results').glob('NATIVE_*.json'):
            d=read(p)
            if d.get('status')=='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN': allowed[writer.oldbase.normalized(d['native_save']['path'])]=d['native_save']['sha256']
        builder.close_registered(allowed);gc.collect()
        report['memory_after_scoped_close']=builder.memory_snapshot();builder.ram_floor()
        cold,report['cold_open']=writer.reuse.open_readonly(builder,target)
        builder.inspect_delta(cold,expected_rows(info),target)
        report['cold_inspection_native_sha256']=digest;report['final_native_sha256']=digest
        require(sha(target)==digest,'File changed during read')
        report['left_open_dirty_flag']=bool(writer.val(cold,'GetSaveFlag'))
        report['no_save_after_cold']=True
        report['inputs_unchanged']=all(sha(p)==d for p,d in pins.items());require(report['inputs_unchanged'],'Source changed')
        report['input_sha256_after']=pins
        report['status']='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN'
        builder.checkpoint('recovered_file_independently_validated_without_save',component_count=625,solid_count=1006)
    except Exception as exc:
        report.update(status='FAILED',error=str(exc),traceback=traceback.format_exc())
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');raise
    finally:
        if builder and builder.initialized: builder.pythoncom.CoUninitialize()

if __name__=='__main__':main()
