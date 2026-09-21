from pathlib import Path
import json, shutil, hashlib, urllib.request
A=Path("F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation")
H=A/'history/20260909_V12_before_input_passives'
H.mkdir(parents=True,exist_ok=True)
items=['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv','tools/shared_battery_path.py','tools/check_shared_battery_path.py','tools/integrate_power_loop.py','tools/seal_completed_package.py']
items += [p.relative_to(A).as_posix() for folder in ['power','ecad','results','thermal'] for p in (A/folder).glob('*') if p.is_file()]
for item in items:
 p=A/item; dst=H/item
 if p.exists() and not dst.exists(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dst)
url='https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-1025hc-surface-mount-ceramic-tube-fuses-data-sheet.pdf'
with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as r: b=r.read()
assert b.startswith(b'%PDF')
p=A/'sources/eaton_1025hc_2025.pdf'; p.write_bytes(b)
m=A/'sources/INPUT_PASSIVE_SOURCE_MANIFEST.json'; rows=json.loads(m.read_text(encoding='utf-8'))
rows=[r for r in rows if r.get('file')!=p.name]
rows.append(dict(file=p.name,url=url,status='ACQUIRED',bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
m.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(dict(archived=len(items),downloaded=p.name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())))

