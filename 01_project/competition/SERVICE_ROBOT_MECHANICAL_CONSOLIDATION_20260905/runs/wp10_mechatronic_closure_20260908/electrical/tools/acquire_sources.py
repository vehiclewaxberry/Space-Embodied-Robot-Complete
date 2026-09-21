from pathlib import Path
import urllib.request,json,hashlib,concurrent.futures
from pypdf import PdfReader
E=Path(__file__).resolve().parents[1];S=E/'sources'
urls={'tsr1':'https://www.tracopower.com/tsr1-datasheet','tc4420':'https://ww1.microchip.com/downloads/en/DeviceDoc/21419D.pdf'}
def run(k,u):
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=45);b=r.read();p=S/(k+'.pdf');p.write_bytes(b)
  if not b.startswith(b'%PDF'):raise ValueError('not PDF')
  txt='\n\n'.join('PAGE '+str(i+1)+'\n'+(p.extract_text() or '') for i,p in enumerate(PdfReader(p).pages));(S/(k+'.txt')).write_text(txt,encoding='utf8')
  return dict(id=k,url=u,final_url=r.url,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),status='PDF_DOWNLOADED')
 except Exception as ex:return dict(id=k,url=u,error=str(ex),status='FAILED')
rows=list(concurrent.futures.ThreadPoolExecutor(2).map(lambda kv:run(*kv),urls.items()))
(S/'NEW_SOURCE_MANIFEST.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps(rows))
