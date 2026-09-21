"""Build a same-workspace handoff snapshot, not a manufacturing release."""
from pathlib import Path
import datetime,hashlib,json,zipfile,psutil
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';R=A/'results/stop_v36/pcb';N=R/'native_checkpoint_20260916'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    v=json.loads((N/'CHECKPOINT_VERIFICATION.json').read_text())
    for field in ['source_bindings','evidence_bindings']:
        assert all(Path(p).exists() and sha(p)==h for p,h in v[field].items())
    assert v['scoped_check_passed'] and not (A/'ecad/revisions/v36/wp10_stop_control.kicad_pcb').exists()
    review=R/'READONLY_REVIEW_20260916.json'
    dump(review,dict(status='SCOPED_PASS_WITH_RECORDED_OPEN_WORK',reviewer='handoff_source_audit',scope='Readonly current-source, native-export freshness and94footprint mapping review',
      findings_closed=['15missing instance footprint fields','J106 wrong project path and absent sourcing properties','Legacy validator could bind edited source to stale native outputs'],
      independently_checked=dict(electrical_refs=240,pin_records=777,ERC_sheets=15,ERC_violations=0,source_bindings=69,evidence_bindings=4),
      boundary=['STOP PCB absent','9filter parts not implemented','Whole system incomplete'],
      manifest_followup='PHYSICAL_PARTS and BOARD_SCOPE are explicitly SHA256-bound by outer handoff snapshot because native checkpoint did not bind them.'))
    selected=set()
    for directory in [A/'ecad/revisions/v35',A/'ecad/revisions/v36',A/'results/stop_v36']:
        selected.update(p for p in directory.rglob('*') if p.is_file() and p.suffix not in ['.lck','.pyc'])
    selected.update(C/n for n in ['HANDOFF_TO_CLAUDE_CODE_20260916.md','CANDIDATE_V35.json','DELIVERY_STATUS_V35.json','SYSTEM_MATURITY_V35.json','PROGRESS_PLAN_V35_V36.json'])
    selected.add(A/'CURRENT_WORKING_CANDIDATE.json')
    for name in ['build_stop_footprints_v36.py','reconcile_stop_pcb_metadata_v36.py','export_stop_checkpoint_v36.py','audit_stop_v36.py','erc_source_contract.py','native_delta_guard.py','native_delta_win_job.py','memory_reclaim_safe_v24.py','reclaim_cap_terminal_memory.py','reclaim_background_checkpoint.py','package_claude_handoff_20260916.py']:
        selected.add(A/'tools'/name)
    for pattern in ['native_delta_stop_v36_footprints_20260916*','native_delta_stop_v36_current_export_20260916*']:
        selected.update(p for p in (A/'logs').glob(pattern) if p.is_file())
    selected.add(A.parent/'tools/integrate_ecad.py')
    # Snapshot key engineering decisions even when they sit outside native EDA source inputs.
    assert R/'PHYSICAL_PARTS.json' in selected and R/'BOARD_SCOPE.json' in selected
    manifest={str(p.relative_to(A.parent)).replace('\\','/'):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(selected)}
    snapshot=C/'HANDOFF_SNAPSHOT_20260916.json'
    dump(snapshot,dict(schema='WP10_CLAUDE_HANDOFF_SNAPSHOT',created_local=datetime.datetime.now().astimezone().isoformat(),
      original_run_directory=str(A.parent),formal_revision='V35',working_revision='V36',same_workspace_handoff=True,
      electrical_refs=v['electrical_refs'],pin_records=v['pin_records'],selected_board_refs=94,STOP_PCB_implemented=False,
      current_native_evidence=str(N),whole_design_complete=False,manufacturing_release=False,hardware_tests=0,
      selection_tables_bound=True,files=manifest,
      memory_available_MiB=round(psutil.virtual_memory().available/2**20,1),
      resume_priority='Implement9planned thermal filter parts with exact connections and source facts, extend explicit delta contract, fresh export, then STOP PCB layout/routing/DRC. Continue original full thermal/mechanical/propulsion integration goal.',
      portability_note='Snapshot paths are relative to the existing WP10 run. Runtime, external CAD host873 and historical evidence outside this selection stay in the existing workspace. This ZIP is not a complete spacecraft release or relocated runnable repository.'))
    selected.add(snapshot)
    target=C/'WP10_CLAUDE_HANDOFF_20260916.zip'
    assert not target.exists(),'Do not overwrite a published handoff snapshot'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(selected):z.write(p,p.relative_to(A.parent).as_posix())
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name,row in manifest.items():
            assert z.getinfo(name).file_size==row['bytes']
            with z.open(name) as f:
                h=hashlib.sha256()
                while chunk:=f.read(1024*1024):h.update(chunk)
                assert h.hexdigest()==row['sha256'],name
    receipt=dict(status='SNAPSHOT_ZIP_CONTENTS_VERIFIED',zip=str(target),bytes=target.stat().st_size,sha256=sha(target),files=len(selected),manifest=str(snapshot),manifest_sha256=sha(snapshot),all_payload_hashes_matched=True,whole_design_complete=False)
    dump(C/'HANDOFF_PACKAGE_RECEIPT_20260916.json',receipt)
    print(json.dumps(receipt))
if __name__=='__main__':main()
