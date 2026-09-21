"""Download the signed official KiCad installer; no installer execution."""
from pathlib import Path
import requests,json,hashlib,time
N=Path(__file__).resolve().parents[1];D=N.parents[4]/'70_tools'/'runtime_wp09_kicad'
# Use explicitly named workspace tools domain, independent of nested run depth.
D=Path(r'F:/China Graduate Future Flight Vehicle Innovation Competition/70_tools/runtime_wp09_kicad');D.mkdir(exist_ok=True)
u='https://mirrors.aliyun.com/kicad/windows/stable/kicad-10.0.6-x86_64.exe';p=D/'kicad-10.0.6-x86_64.exe';part=D/(p.name+'.partial')
t=time.time();r=requests.get(u,stream=True,timeout=(20,45));r.raise_for_status();h=hashlib.sha256();count=0
with part.open('wb') as f:
 for chunk in r.iter_content(1024*1024):
  f.write(chunk);h.update(chunk);count+=len(chunk)
  if count%(100*1024*1024)==0:print('download_MiB',count//1048576,flush=True)
assert count==967765696,(count,r.headers.get('Content-Length'))
part.rename(p)
(N/'results/KICAD_DOWNLOAD.json').write_text(json.dumps(dict(url=u,path=str(p),bytes=count,sha256=h.hexdigest(),elapsed_s=time.time()-t,installer_executed=False),indent=2),encoding='utf-8');print('download_complete',count,flush=True)
