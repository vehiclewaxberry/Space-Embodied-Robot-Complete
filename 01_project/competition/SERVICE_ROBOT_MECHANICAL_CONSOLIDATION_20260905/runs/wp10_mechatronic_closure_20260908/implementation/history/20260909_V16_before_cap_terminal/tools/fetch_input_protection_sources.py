"""Public OEM source acquisition; store only verified PDF responses."""
from pathlib import Path
import urllib.request,json,hashlib,datetime
A=Path(__file__).resolve().parents[1]
urls={'eaton_1025hc_2025.pdf':'https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-1025hc-surface-mount-ceramic-tube-fuses-data-sheet.pdf',
      'eaton_mda_2025.pdf':'https://www.eaton.com/content/dam/eaton/products/electronic-components/resources/data-sheet/eaton-mda-time-delay-ceramic-tube-fuses-data-sheet.pdf'}
rows=[]
for name,url in urls.items():
 try:
  p=A/'sources'/name
  if p.exists():
   b=p.read_bytes();assert b.startswith(b'%PDF-')
   rows.append(dict(file='sources/'+name,url=url,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),acquired=True,reused_cached_bytes=True));continue
  request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/pdf'})
  with urllib.request.urlopen(request,timeout=15) as r:b=r.read();final=r.geturl();ctype=r.headers.get('Content-Type')
  assert b.startswith(b'%PDF-'),'Response is not PDF'
  p.write_bytes(b);rows.append(dict(file='sources/'+name,url=url,final_url=final,content_type=ctype,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),acquired=True))
 except Exception as e:rows.append(dict(url=url,acquired=False,error=str(e)))
out=dict(time_local=datetime.datetime.now().astimezone().isoformat(),rows=rows)
(A/'sources/INPUT_PROTECTION_ACQUISITION.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
