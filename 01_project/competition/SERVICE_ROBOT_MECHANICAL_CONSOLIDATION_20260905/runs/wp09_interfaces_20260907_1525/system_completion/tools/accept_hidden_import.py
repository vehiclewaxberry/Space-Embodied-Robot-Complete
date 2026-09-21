"""Accept a completed five-part display-only memory trial using its frozen receipts."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
C=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
marker=json.loads((C/'results/NATIVE_DELTA_HIDDEN_TRIAL_STARTED.json').read_text())
path=Path(marker['result']);r=json.loads(path.read_text())
guard=C/'logs'/('native_delta_'+marker['tag']+'.run.json');g=json.loads(guard.read_text())
assert r['status']=='PASS_DELTA_NATIVE_PART_IMPORT_AND_COLD_BODY_VOLUME_BOUNDS'
assert r['part_count']==r['part_display_trial']['actual_count']==5
assert r['open_documents_after']==[] and r['part_display_trial']['restored_visible_default']
assert g['status']=='COMPLETED' and g['returncode']==0
assert len(r['parts'])==5 and all(p['part_cold_reopen']['facts']['solid_count']==1 for p in r['parts'])
peak=max(p['combined_rss_mib_after'] for p in r['parts'])
assert peak<750
report={'status':'ACCEPTED_DISPLAY_ONLY_HIDDEN_PART_IMPORT','utc':datetime.now(timezone.utc).isoformat(),
 'trial_receipt':str(path),'trial_sha256':sha(path),'guard_receipt':str(guard),'guard_sha256':sha(guard),
 'minimum_next_start':87,'five_parts_geometric_cold_checks_unchanged':True,
 'trial_part_boundary_RSS_MiB':[p['combined_rss_mib_after'] for p in r['parts']],
 'trial_max_part_boundary_RSS_MiB':peak,'guard_peak_combined_MiB':max(s['combined_rss_mib'] for s in g['samples']),
 'adoption_scope':'Future fresh import sessions only; same geometry/import options/thresholds/cold checks. Restore visible part default before normal ExitApp. Assembly integration and screenshot visibility unaffected.',
 'limitations':'No claim of guaranteed memory use or controlled paired speedup. Continue 1400MiB combined sampled guard and 512MiB available floor.'}
(C/'results/NATIVE_DELTA_HIDDEN_IMPORT_ACCEPTANCE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
