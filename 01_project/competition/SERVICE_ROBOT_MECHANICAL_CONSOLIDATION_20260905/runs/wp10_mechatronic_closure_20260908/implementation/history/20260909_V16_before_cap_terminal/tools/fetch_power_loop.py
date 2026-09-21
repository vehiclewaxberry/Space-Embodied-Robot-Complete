"""Archive the previous active receipt, then acquire bounded official sources."""
from pathlib import Path
import csv, hashlib, json, shutil, urllib.request, datetime
A=Path(__file__).resolve().parents[1]
H=A/'history'/'20260908_before_power_integration'
H.mkdir(parents=True,exist_ok=True)
for n in ['WP10_IMPLEMENTATION_DELTA.zip','results/OUTPUT_SHA256.csv','results/DELIVERY_DECISION.json','SYSTEM_CLOSURE_MATRIX.csv','REVIEW.html']:
 p=A/n; t=H/Path(n).name
 if not t.exists(): shutil.copy2(p,t)
items=[
 ('lm5069_rev_g.pdf','https://www.ti.com/lit/ds/symlink/lm5069.pdf'),
 ('csd19536ktt.pdf','https://www.ti.com/lit/ds/symlink/csd19536ktt.pdf'),
 ('lm7480_q1.pdf','https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf'),
 ('thn30wir_20260901.pdf','https://www.tracopower.com/thn30wir-datasheet'),
 ('rrc3570_4_E.pdf','https://www.rrc-ps.com/fileadmin/user_upload/DS_RRC3570-4_E.pdf'),
 ('ixth75n10l2.pdf','https://www.littelfuse.com/assetdocs/Littelfuse-Discrete-MOSFETs-N-Channel-Linear-IXT-75N10-Datasheet.PDF?assetguid=EA051E16-AAA9-4983-A975-8D0C07325D72'),
 ('wslp2726.pdf','https://www.vishay.com/docs/30179/wslp2726.pdf'),
 ('tsp1600s.pdf','https://datasheets.tdx.henkel.com/BERGQUIST-SIL-PAD-TSP-1600S-en_GL.pdf')]
rows=[]
for name,url in items:
 p=A/'sources'/name
 try:
  if p.exists(): data=p.read_bytes()
  else:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
   data=urllib.request.urlopen(req,timeout=25).read()
  if not data.startswith(b'%PDF-'): raise ValueError('Not a PDF: rejected; no content accepted')
  digest=hashlib.sha256(data).hexdigest()
  if name=='thn30wir_20260901.pdf': assert digest=='bab935ed6f57de25f6a8045c2a76320f07a59e4ccd1b2ff68b43c01bb7d20390'
  if name=='tsp1600s.pdf': assert digest=='7f44e98400f795caf39e84dd5793324256c28f748015e3d9fa7b3b3e8120fc29'
  p.write_bytes(data)
  rows.append(dict(path=p.relative_to(A).as_posix(),url=url,bytes=len(data),sha256=digest,status='PDF_RECEIVED_CONTENT_REVIEW_REQUIRED'))
 except Exception as e: rows.append(dict(url=url,status='NOT_ACCEPTED',error=str(e)))
(A/'sources/POWER_LOOP_SOURCE_MANIFEST.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))
