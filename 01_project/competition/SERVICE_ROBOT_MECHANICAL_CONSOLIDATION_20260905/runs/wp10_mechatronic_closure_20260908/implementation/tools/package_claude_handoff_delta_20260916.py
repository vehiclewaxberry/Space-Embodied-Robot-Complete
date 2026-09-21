"""Checkpoint current STOP source/placement and pending SES; no native design work."""
from pathlib import Path
import datetime, hashlib, json, zipfile
import psutil

A = Path(__file__).resolve().parents[1]
C = A / 'coupled_closure'
P = A / 'results/stop_v36/pcb'
F = P / 'thermal_filter_20260916'
L = P / 'layout_20260916'
N = F / 'native_20260916_a'
TAG = '20260916_ROUTING_PENDING'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as stream:
        while chunk := stream.read(1024 * 1024): h.update(chunk)
    return h.hexdigest()
def dump(p, value): Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def rel(p): return Path(p).relative_to(A.parent).as_posix()

def main():
    target = C / f'WP10_CLAUDE_HANDOFF_DELTA_{TAG}.zip'
    snapshot = C / f'HANDOFF_SNAPSHOT_DELTA_{TAG}.json'
    assert not target.exists() and not snapshot.exists(), 'Immutable checkpoint already exists'
    base = C / 'WP10_CLAUDE_HANDOFF_20260916.zip'
    base_receipt = read(C / 'HANDOFF_PACKAGE_RECEIPT_20260916.json')
    assert sha(base) == base_receipt['sha256']
    before = read(C / 'HANDOFF_SNAPSHOT_20260916.json')['files']
    v = read(N / 'VERIFICATION.json')
    for key in ('source_bindings', 'evidence_bindings'):
        assert all(sha(p) == h for p, h in v[key].items()), key
    assert (v['electrical_refs'], v['pin_records'], v['board_selected_refs']) == (249, 795, 103)
    board = A / 'ecad/revisions/v36/wp10_stop_control.kicad_pcb'
    assert sha(board) == read(L / 'SILKSCREEN_PLACEMENT.json')['board_after_sha256']
    assert sha(L / 'STOP_ROUTING.dsn') == read(L / 'ROUTING_ALLOCATION.json')['dsn_sha256']
    ses = L / 'STOP_ROUTED_A.ses'
    assert ses.stat().st_size > 0 and ses.read_text().lstrip().startswith('(session STOP_ROUTING')
    route = read(A / 'logs/native_delta_stop_v36_route_20260916.run.json')
    assert route['status'] == 'COMPLETED' and route['returncode'] == 0
    drc = read(L / 'PLACEMENT_DRC_R2.json')
    assert len(drc['violations']) == 0 and len(drc['unconnected_items']) == 254
    review = C / f'READONLY_HANDOFF_REVIEW_{TAG}.json'
    dump(review, dict(reviewer='handoff_source_audit', recorded_by='root',
        provenance='Summary of read-only collaborator findings delivered in this thread, not a hardware test',
        conditional_filter_initial_state_review='PASS_WITHIN_DECLARED_512_CORNERS_AND_INITIAL_VOLTAGE_ENVELOPE',
        independently_recomputed_open_us=293.377711481525,
        independently_recomputed_short_us=2.887258856250,
        traps=['SES generated but not imported; board has zero tracks and vias',
               'Placement DRC zero violations still254unconnected and5ignored checks',
               'Current249/795/103 differs from historical240/777/94; formalV35 unchanged',
               'RC input threshold times are not comparator/contactor/wholeSTOP limits',
               'Whole electromechanical/thermal/propulsion design incomplete']))
    selected = {A.parent / name for name in before if (A.parent / name).is_file()}
    for directory in (A / 'ecad/revisions/v36', A / 'results/stop_v36'):
        selected.update(p for p in directory.rglob('*') if p.is_file() and p.suffix not in ('.lck', '.pyc') and '__pycache__' not in p.parts)
    selected.update((A / 'tools').glob('*stop*v36*.py'))
    selected.update(p for p in (A / 'logs').glob('native_delta_stop_v36_*20260916*') if p.is_file())
    selected.update([Path(__file__), C / f'HANDOFF_DELTA_{TAG}.md', review])
    manifest = {rel(p): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(selected)}
    changed = {name: row for name, row in manifest.items() if before.get(name) != row}
    omitted_base = [name for name in before if name not in manifest]
    assert not omitted_base, 'A base file went missing; investigate rather than silently omit'
    dump(snapshot, dict(schema='WP10_CLAUDE_HANDOFF_INCREMENTAL_SNAPSHOT',
        created_local=datetime.datetime.now().astimezone().isoformat(),
        same_workspace_handoff=True, original_run_directory=str(A.parent),
        base_zip=str(base), base_zip_sha256=sha(base), formal_revision='V35', working_revision='V36',
        electrical_refs=249, pin_records=795, selected_electrical_footprints=103, mounting_holes=4,
        PCB_exists=True, route_session_saved=True, route_session_imported=False, post_route_DRC_executed=False,
        placement_DRC_violations=0, placement_DRC_unconnected=254, placement_DRC_ignored_checks=drc['ignored_checks'],
        whole_design_complete=False, manufacturing_release=False, hardware_tests=0,
        memory_available_MiB=round(psutil.virtual_memory().available / 2**20, 1),
        router_exit_code=route['returncode'], router_elapsed_s=route['elapsed_s'],
        files=manifest, delta_files=changed, unchanged_files_required_from_base=len(manifest)-len(changed),
        next_action='Back up placed PCB, import existing SES serially under memory guard, cold-load pad/net/placement checks, then new full DRC and critical routing review',
        portability_note='Existing workspace required; external CAD host and runtimes not fully packaged. Do not extract old snapshot over current edited source.'))
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=5) as z:
        for name in changed: z.write(A.parent / name, name)
        z.write(snapshot, rel(snapshot))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for name, row in changed.items():
            assert z.getinfo(name).file_size == row['bytes']
            assert hashlib.sha256(z.read(name)).hexdigest() == row['sha256'], name
        assert hashlib.sha256(z.read(rel(snapshot))).hexdigest() == sha(snapshot)
    # A concurrent edit during packaging must not produce a valid latest pointer.
    assert all(sha(A.parent / name) == row['sha256'] for name, row in manifest.items())
    receipt = dict(status='INCREMENTAL_ZIP_CONTENTS_AND_CURRENT_HASHES_VERIFIED', zip=str(target),
        sha256=sha(target), bytes=target.stat().st_size, delta_files=len(changed),
        snapshot=str(snapshot), snapshot_sha256=sha(snapshot), base_zip=str(base), base_zip_sha256=sha(base),
        all_payload_hashes_matched=True, whole_design_complete=False)
    receipt_path = C / f'HANDOFF_DELTA_RECEIPT_{TAG}.json'
    dump(receipt_path, receipt)
    dump(C / 'HANDOFF_LATEST.json', dict(entry=str(C / f'HANDOFF_DELTA_{TAG}.md'),
        snapshot=str(snapshot), snapshot_sha256=sha(snapshot), receipt=str(receipt_path), receipt_sha256=sha(receipt_path),
        delta_zip=str(target), delta_zip_sha256=sha(target), base_zip=str(base), base_zip_sha256=sha(base),
        status='READY_FOR_SAME_WORKSPACE_CONTINUATION__SES_IMPORT_PENDING', whole_design_complete=False))
    print(json.dumps(receipt, ensure_ascii=False))

if __name__ == '__main__': main()
