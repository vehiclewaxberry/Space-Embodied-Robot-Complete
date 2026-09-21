"""Read-only verification of the sealed candidate ZIP and local review links."""
from pathlib import Path
import csv,hashlib,json,zipfile,urllib.parse,urllib.request
from html.parser import HTMLParser
A=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
rows=list(csv.DictReader((A/'results/OUTPUT_SHA256.csv').open(encoding='utf-8-sig')))
bad=[]
with zipfile.ZipFile(A/'WP10_IMPLEMENTATION_DELTA.zip') as z:
    assert z.testzip() is None
    for r in rows:
        disk=(A/r['path']).read_bytes();packed=z.read(r['path'])
        if len(disk)!=int(r['bytes']) or sha(disk)!=r['sha256'] or disk!=packed:bad.append(r['path'])
    assert len(z.namelist())==len(rows)+1
    assert z.read('results/OUTPUT_SHA256.csv')==(A/'results/OUTPUT_SHA256.csv').read_bytes()
assert not bad,bad
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ['href','src']:self.links.append(v)
p=Links();p.feed((A/'REVIEW.html').read_text(encoding='utf-8'))
missing=[]
for link in p.links:
    u=urllib.parse.urlparse(link)
    if u.scheme or not u.path:continue
    if not (A/urllib.parse.unquote(u.path)).exists():missing.append(link)
assert not missing,missing
decision=json.loads((A/'results/DELIVERY_DECISION.json').read_text())
assert not decision['goal_complete'] and not decision['engineering_prototype_design_complete']
assert len(decision['remaining_open_ids'])==23
http={}
for url in ['http://127.0.0.1:3245/','http://127.0.0.1:3253/wp10_mechatronic_closure_20260908/implementation/REVIEW.html']:
    try:
        with urllib.request.urlopen(url,timeout=8) as r:http[url]=r.status
    except Exception as e:http[url]=str(e)
assert (A/'mechanical/fixed_heat_bay.step.py').exists() and (A/'mechanical/fixed_heat_bay.step').exists()
print(json.dumps(dict(manifest_files=len(rows),zip_entries=len(rows)+1,zip_bytes=(A/'WP10_IMPLEMENTATION_DELTA.zip').stat().st_size,
  sha256_mismatches=bad,missing_local_review_links=missing,http=http,status=decision['status'],
  fixed_heat_exact_interface_pairs_by_state=decision['fixed_heat_exact_interface_pairs_by_state'],
  parent_integrity=json.loads((A/'results/PARENT_INTEGRITY.json').read_text()),
  goal_complete=decision['goal_complete']),ensure_ascii=False))
