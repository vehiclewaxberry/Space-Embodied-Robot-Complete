from pathlib import Path
import urllib.request,json,hashlib,datetime
A=Path(__file__).resolve().parents[1]
urls={'te_55a0111_drawing.pdf':'https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocFormat=pdf&DocLang=English&DocNm=55A0111&DocType=Customer+Drawing&PartCntxt=216372-000'}
rows=[]
for name,url in urls.items():
 try:
  p=A/'sources'/name
  if p.exists():b=p.read_bytes();cached=True
  else:
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/pdf'})
   with urllib.request.urlopen(req,timeout=20) as r:b=r.read()
   assert b.startswith(b'%PDF-');p.write_bytes(b);cached=False
  rows.append(dict(path='sources/'+name,url=url,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),cached=cached,acquired=True))
 except Exception as e:rows.append(dict(url=url,acquired=False,error=str(e)))
(A/'sources/CAP_CONNECTION_SOURCE_ACQUISITION.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),rows=rows),indent=2),encoding='utf-8')
print(json.dumps(rows))
