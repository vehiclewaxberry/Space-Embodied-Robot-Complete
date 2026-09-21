"""Recover historical sweep bytes only when they match the prior SHA exactly.
The C02 exporter rewrote same-path sweeps. STEP timestamps are the expected sole
change; no file is credited or saved unless the old receipt hash matches.
"""
from pathlib import Path
import json,hashlib,re,datetime
R=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
old=json.loads((R/'results/C01_PATH_FAILURE.json').read_text())
archive=R/'results/c01_sweep_archive';archive.mkdir(exist_ok=True)
start=datetime.datetime.fromisoformat(old['generated_local']).replace(tzinfo=None,microsecond=0)
rows=[]
for path,digest in old['actual_step_input_hashes'].items():
    p=Path(path)
    if p.parent.name!='sweep_geometry':continue
    data=p.read_bytes();pattern=rb"(FILE_NAME\('Open CASCADE Shape Model',')([^']+)(')"
    m=re.search(pattern,data);found=None
    if m:
        for seconds in range(-10,180):
            timestamp=(start+datetime.timedelta(seconds=seconds)).isoformat().encode()
            candidate=data[:m.start(2)]+timestamp+data[m.end(2):]
            if sha(candidate)==digest:
                dest=archive/p.name;dest.write_bytes(candidate)
                found=dict(original_path=path,archive_path=str(dest),sha256=digest,status='RECONSTRUCTED_BYTE_IDENTICAL_TO_PRIOR_RECEIPT_SHA256',timestamp=timestamp.decode());break
    rows.append(found or dict(original_path=path,expected_sha256=digest,status='HISTORICAL_BINARY_NOT_RECOVERED'))
result=dict(reason='C02 rewrote same-path sweep exports; historical JSON/script retained; archive reconstruction is transparent and exact-hash gated',results=rows,status='PASS_ALL_24_PRIOR_BYTES_RECOVERED' if len(rows)==24 and all(x['status'].startswith('RECONSTRUCTED') for x in rows) else 'INCOMPLETE')
(R/'results/C01_EVIDENCE_RECOVERY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['status'],len(rows),sum(x['status'].startswith('RECONSTRUCTED') for x in rows))
