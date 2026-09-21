from pathlib import Path
import shutil,json,hashlib
A=Path(__file__).resolve().parents[1]; D=A.parent
for n in ['native_delta_guard.py','native_delta_win_job.py']:
 shutil.copy2(D/'mechanical_inertia/tools'/n,A/'tools'/n)
p=next((A/'sources/cincon_oem').rglob('*Standard*.STEP'))
shutil.copy2(p,A/'sources/CHB500W_STANDARD_OEM.step')
(A/'sources/OEM_MODEL_BINDING.json').write_text(json.dumps({'source':str(p),'alias':'CHB500W_STANDARD_OEM.step','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'model_scope':'standard family mechanical model; N logic variant uses same mechanical drawing; not -PC'},indent=2),encoding='utf-8')
for p in (A/'sources').glob('*.pdf'):
 if not p.read_bytes().startswith(b'%PDF-'):
  (A/'sources'/f'{p.stem}_FETCH_REJECTED.json').write_text(json.dumps({'path':str(p),'error':'response is not a PDF; rejected as engineering evidence','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}),encoding='utf-8')
print('prepared isolated guard and OEM alias')
