from pathlib import Path
import urllib.request,hashlib,json,concurrent.futures
from pypdf import PdfReader
C=Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion");S=C/'electrical_delta'/'sources';S.mkdir(parents=True,exist_ok=True)
urls={n:f'https://www.ti.com/lit/ds/symlink/{n}.pdf' for n in ['tps3808','ucc27517','sn74lvc74a','sn74lvc2g17','sn74lvc1g04','sn74lvc1g08']}
urls.update(irl630='https://www.vishay.com/docs/91303/irl630.pdf',gx11='https://www.sensata.com/sites/default/files/a/sensata-gigavac-gx11-series-open-contactors-datasheet.pdf',kemet_c0g='https://content.kemet.com/datasheets/KEM_C1003_C0G_SMD.pdf')
def f(kv):
 n,u=kv;p=S/(n+'.pdf')
 try:
  b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=25).read()
  assert b.startswith(b'%PDF')
  p.write_bytes(b);t='\n'.join(f'--- PAGE {i+1} ---\n'+(pg.extract_text() or '') for i,pg in enumerate(PdfReader(p).pages));p.with_suffix('.txt').write_text(t,encoding='utf8')
  return dict(name=n,url=u,path=str(p),sha256=hashlib.sha256(b).hexdigest(),status='DOWNLOADED_PDF')
 except Exception as e:return dict(name=n,url=u,status='FAILED',error=str(e))
out=list(concurrent.futures.ThreadPoolExecutor(4).map(f,urls.items()));(S/'MANIFEST.json').write_text(json.dumps(out,indent=2),encoding='utf8');print(json.dumps(out))

