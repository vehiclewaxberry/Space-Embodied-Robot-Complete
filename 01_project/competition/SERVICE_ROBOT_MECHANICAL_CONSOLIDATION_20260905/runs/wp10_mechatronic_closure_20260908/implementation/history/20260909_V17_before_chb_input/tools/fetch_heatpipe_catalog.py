from pathlib import Path
import urllib.request,hashlib,json,datetime
A=Path(__file__).resolve().parents[1];url='https://www.qats.com/DataSheet/Heat-Pipes'
with urllib.request.urlopen(url,timeout=25) as r:
    data=r.read(8*1024*1024+1);ctype=r.headers.get('Content-Type','');final=r.url
assert data.startswith(b'%PDF') and len(data)<=8*1024*1024,(ctype,len(data))
p=A/'sources/ATS_HEATPIPE_CATALOG.pdf';p.write_bytes(data)
(A/'sources/ATS_HEATPIPE_CATALOG_SOURCE.json').write_text(json.dumps(dict(url=url,resolved_url=final,accessed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),file=p.name,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),content_type=ctype,qualification_credit=False),indent=2),encoding='utf-8')
print(json.dumps(dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())))
