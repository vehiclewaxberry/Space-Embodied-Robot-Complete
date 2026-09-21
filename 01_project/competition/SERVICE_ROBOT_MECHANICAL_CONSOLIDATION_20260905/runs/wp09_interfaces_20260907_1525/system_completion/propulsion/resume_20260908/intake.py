from pathlib import Path
import datetime, hashlib, json, urllib.request, urllib.error
from pypdf import PdfReader

P=Path(__file__).resolve().parent
S=P/'sources'; S.mkdir(parents=True,exist_ok=True)
urls={
 'CPOD_2023_author_paper.pdf':'https://digitalcommons.usu.edu/cgi/viewcontent.cgi?article=5645&context=smallsat',
 'CPOD_2023_author_slides.pdf':'https://digitalcommons.usu.edu/cgi/viewcontent.cgi?article=5645&context=smallsat&filename=0&type=additional',
 'CPOD_2023_author_landing.html':'https://digitalcommons.usu.edu/smallsat/2023/all2023/119/',
}
rows=[]
for name,url in urls.items():
 row={'file':name,'url':url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=25) as r:
   data=r.read(); row.update(http_status=r.status,resolved_url=r.url,content_type=r.headers.get('Content-Type'))
  if name.endswith('.pdf') and not data.startswith(b'%PDF'): raise ValueError('Response not PDF')
  path=S/name; path.write_bytes(data); row.update(status='DOWNLOADED',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
  if name.endswith('.pdf'):
   pdf=PdfReader(path); row['pages']=len(pdf.pages)
   path.with_suffix('.txt').write_text('\n\n'.join(f'PAGE {i+1}\n{p.extract_text()}' for i,p in enumerate(pdf.pages)),encoding='utf-8')
 except Exception as e: row.update(status='FETCH_FAILED',error=str(e))
 rows.append(row)
(S/'INTAKE_MANIFEST.json').write_text(json.dumps({'documents':rows,'no_forms_submitted':True,'no_supplier_contact':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))
