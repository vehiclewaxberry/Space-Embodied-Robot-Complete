"""Read back current source locks, immutable archives and the delivered delta."""
from pathlib import Path
import json,csv,hashlib,zipfile
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads((C/'CANDIDATE_V30.json').read_text());act=json.loads((C/'SOURCE_ACTIVATION_V30.json').read_text());assert all(sha(Path(p))==h for p,h in c['source_lock'].items());assert sha(C/'CANDIDATE_V30.json')==act['candidate_sha256']
old=list(csv.DictReader((C/'SHA256.csv').read_text(encoding='utf-8-sig').splitlines()));assert len(old)==40;assert all(sha(C/r['file'])==r['sha256'] for r in old)
z29=C/'WP10_V29_TERMINAL_DELTA.zip';assert sha(z29)=='16ce1b031fbe38ff578e2b7983d0e7173df69f1ddcce56097df46428427f04c7'
oldbom=A/'history/20260910_V30_before_lugs/power/SELECTED_BOM.csv';newbom=A/'power/SELECTED_BOM.csv';assert sha(oldbom)=='fba46213f216bd80c9ca56fa54728a9963d66beac00c674ff4984418e01ea088';assert newbom.read_bytes().startswith(oldbom.read_bytes());assert len(list(csv.DictReader(newbom.read_text(encoding='utf-8-sig').splitlines())))-len(list(csv.DictReader(oldbom.read_text(encoding='utf-8-sig').splitlines())))==9
manifest=C/'SHA256_V30.csv';rows=list(csv.DictReader(manifest.read_text().splitlines()));r=json.loads((C/'DELIVERY_PACKAGE_CHECK_V30.json').read_text());zp=C/'WP10_V30_LUG_HARNESS_DELTA.zip';assert sha(zp)==r['zip_sha256'] and sha(manifest)==r['manifest_sha256']
with zipfile.ZipFile(zp) as z:
 assert z.testzip() is None;assert len(z.namelist())==len(rows)+1==r['files']
 for x in rows:
  assert sha(A/x['file'])==x['sha256'];assert hashlib.sha256(z.read(x['file'])).hexdigest()==x['sha256']
 s=json.loads(z.read('coupled_closure/DELIVERY_STATUS_V30.json'));assert all(s[k] is False for k in ['whole_design_complete','host_installed','manufacturing_release','physical_tests_executed','continuous_thermal_closed'])
print(json.dumps(dict(passed=True,current_source_locks=len(c['source_lock']),original_artifact_locks=len(old),previous_archive_unchanged=True,old_BOM_preserved=True,delta_files=r['files'],ZIP_SHA256=r['zip_sha256'],whole_design_complete=False)))
