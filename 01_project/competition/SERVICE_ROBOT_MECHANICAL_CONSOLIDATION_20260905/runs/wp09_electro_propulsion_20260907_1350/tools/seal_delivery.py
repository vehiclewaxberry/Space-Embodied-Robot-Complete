from pathlib import Path
import hashlib,json,csv,re,datetime
R=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
status=read(R/'results/DELIVERY_STATUS.json');pins=read(R/'results/VERIFIED_INPUT_SHA256.json')
changed=[p for p,h in pins.items() if not Path(p).is_file() or sha(p)!=h];assert not changed,changed
readme=(R/'README.md').read_text(encoding='utf-8');targets=[]
for item in re.findall(r'\]\(<?([^\)\n]+?)>?\)',readme):
    item=item.strip('<>')
    if re.match(r'^[A-Za-z]:[/\\]',item):
        p=Path(item);assert p.is_file(),item;targets.append(str(p))
assert targets
rows=[];exclude={'results/FINAL_INTEGRITY.json','results/OUTPUT_SHA256.csv'}
for p in sorted(R.rglob('*')):
    if p.is_file() and p.relative_to(R).as_posix() not in exclude:
        rows.append(dict(path=p.relative_to(R).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
seal=R/'results/OUTPUT_SHA256.csv';assert not seal.exists()
with seal.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['path','sha256','bytes']);w.writeheader();w.writerows(rows)
assert all(sha(R/x['path'])==x['sha256'] for x in rows)
assert all(sha(p)==h for p,h in pins.items())
out=R/'results/FINAL_INTEGRITY.json';assert not out.exists()
result=dict(schema='WP09_FINAL_FILE_INTEGRITY',status='PASS_FILE_HASH_AND_DELIVERY_LINK_INTEGRITY_ONLY',date=datetime.datetime.now().astimezone().isoformat(),
 delivery_status=status['status'],delivery_status_sha256=sha(R/'results/DELIVERY_STATUS.json'),
 readonly_bound_input_count=len(pins),all_bound_inputs_unchanged=True,output_inventory=str(seal),output_inventory_sha256=sha(seal),sealed_file_count=len(rows),
 local_readme_link_count=len(targets),all_local_readme_targets_exist=True,engineering_scope_unchanged=True,scientific_gate_credit=False,manufacturing_release=False)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
