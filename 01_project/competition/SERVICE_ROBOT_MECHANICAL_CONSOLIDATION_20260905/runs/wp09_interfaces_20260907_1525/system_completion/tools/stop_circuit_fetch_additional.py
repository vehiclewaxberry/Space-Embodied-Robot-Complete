from pathlib import Path
import urllib.request,json,hashlib,concurrent.futures
from pypdf import PdfReader
E=Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion")/'electrical_delta';S=E/'sources'
urls={'sn74lvc1g17':'https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf','vishay_crcw':'https://www.vishay.com/docs/20035/dcrcwe3.pdf','vishay_tnpw':'https://www.vishay.com/doc?28758=','kemet_kit29':'https://content.kemet.com/datasheets/CER_ENG_KIT_29.pdf','kemet_1u':'https://search.kemet.com/download/specsheet/C0603C105K4RACTU','kemet_120p':'https://search.kemet.com/download/specsheet/C0603C121F5GACTU'}
def f(kv):
 n,u=kv;p=S/(n+'.pdf')
 try:
  b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read();assert b.startswith(b'%PDF');p.write_bytes(b)
  p.with_suffix('.txt').write_text('\n'.join(f'--- PAGE {i+1} ---\n'+(pg.extract_text() or '') for i,pg in enumerate(PdfReader(p).pages)),encoding='utf8')
  return dict(name=n,url=u,path=str(p),sha256=hashlib.sha256(b).hexdigest(),status='DOWNLOADED_PDF')
 except Exception as e:return dict(name=n,url=u,status='FAILED',error=str(e))
r=list(concurrent.futures.ThreadPoolExecutor(4).map(f,urls.items()));(S/'MANIFEST_ADDITIONAL.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
