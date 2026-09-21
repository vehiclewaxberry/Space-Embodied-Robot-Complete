"""Archive the current working ECAD before the V22 brake interface change."""
from pathlib import Path
import datetime, hashlib, json, shutil, urllib.request
A=Path(__file__).resolve().parents[1]
H=A/'history/20260910_V22_before_brake_enable'
assert not H.exists(), 'Do not overwrite the prior candidate snapshot'
paths=set()
for pattern in ['*.kicad_sch','*.kicad_pro','*.kicad_sym','*.csv','*.xml']:
    paths.update(p for p in (A/'ecad').glob(pattern) if p.is_file())
for name in ['brake_circuit_definition.py','verify_load_side_brake.py','integrate_power_loop.py']:
    paths.add(A/'tools'/name)
for name in ['POWER_LOOP_PARTS.json','LOAD_SIDE_BRAKE_DEFINITION.json','LOAD_SIDE_BRAKE_CALCULATIONS.json','POWER_LOOP_CALCULATIONS.json','STOP_FULL_FAULT_BUDGET.json','STARTUP_CIRCUIT_CALCULATIONS.json']:
    paths.add(A/'power'/name)
for name in ['LOAD_SIDE_BRAKE_VERIFICATION.json','SYSTEM_ERC_CHECK_V20.json','SYSTEM_ERC_NATIVE_V20.json','CAP_RETENTION_WORKING_STATUS_V21.json']:
    paths.add(A/'results'/name)
for name in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','results/DELIVERY_DECISION.json']:
    paths.add(A/name)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for p in sorted(paths):
    rel=p.relative_to(A);out=H/rel;out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,out);assert sha(out)==sha(p)
    rows.append(dict(path=rel.as_posix(),sha256=sha(p),bytes=p.stat().st_size))
(H/'MANIFEST.json').write_text(json.dumps(dict(created=datetime.datetime.now().astimezone().isoformat(),files=rows,scope='Electrical source and calculation snapshot; no CAD regeneration or release upgrade.'),indent=2),encoding='utf-8')
sources=[]
for fn,url in [('max5048c.pdf','https://www.analog.com/media/en/technical-documentation/data-sheets/MAX5048C.pdf'),('max16052_max16053.pdf','https://www.analog.com/media/en/technical-documentation/data-sheets/MAX16052-MAX16053.pdf')]:
    p=A/'sources'/fn
    if not p.exists():
        data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40).read()
        assert data.startswith(b'%PDF-'), 'Non-PDF response'
        p.write_bytes(data)
    sources.append(dict(file=fn,url=url,sha256=sha(p),bytes=p.stat().st_size))
(A/'sources/BRAKE_ENABLE_SOURCE_MANIFEST_V22.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
print(json.dumps(dict(archived_files=len(rows),source_files=sources)))
