from pathlib import Path
import json,hashlib
C=Path(__file__).resolve().parents[1]
j=json.loads((C/'results/NATIVE_DELTA_INPUTS.json').read_text());done={}
for f in sorted((C/'results').glob('NATIVE_DELTA_IMPORT_*.json')):
 for p in json.loads(f.read_text()).get('parts',[]):
  if 'source_native_volume_error_mm3' in p:
   s=p.get('native_save',{})
   if s and Path(s['path']).exists() and hashlib.sha256(Path(s['path']).read_bytes()).hexdigest()==s['sha256']:
    done[p['id']]=dict(receipt=str(f),source_sha256=p['source_sha256'],native_sha256=s['sha256'])
pending=[i for i,q in enumerate(j['parts']) if q['id'] not in done or done[q['id']]['source_sha256']!=q['source_sha256']]
print(json.dumps(dict(done=len(done),pending_count=len(pending),first_pending=pending[0] if pending else None,pending=pending)))
