"""Acquire only the pinned upstream SDK distribution; never install or access devices."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile,sys
from datetime import datetime,timezone
C=Path(__file__).resolve().parents[1]
D=C/'software_native'; D.mkdir(exist_ok=True)
S=D/'sources'; S.mkdir(exist_ok=True)
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'WP09-offline-engineering-source-intake'})
    with urllib.request.urlopen(req,timeout=40) as r:return r.read()
meta=get('https://pypi.org/pypi/motorbridge/0.5.3/json')
(S/'pypi_motorbridge_0.5.3.json').write_bytes(meta)
d=json.loads(meta)
rows=[{'filename':r['filename'],'size':r['size'],'url':r['url'],'sha256':r['digests']['sha256']} for r in d['urls']]
tag=f'cp{sys.version_info.major}{sys.version_info.minor}'
chosen=next((r for r in rows if r['filename'].endswith(f'{tag}-{tag}-win_amd64.whl')),None)
if chosen is None:
    chosen=next((r for r in rows if r['filename'].endswith('none-any.whl')),None)
assert chosen, 'No compatible offline wheel'
assert chosen['size']<40000000,'Unexpected archive size'
p=S/chosen['filename']; b=get(chosen['url'])
assert len(b)==chosen['size'] and hashlib.sha256(b).hexdigest()==chosen['sha256']
p.write_bytes(b)
with zipfile.ZipFile(p) as z:
    names=z.namelist(); assert not any(Path(x).is_absolute() or '..' in Path(x).parts for x in names)
    z.extractall(D/'upstream')
receipt={'utc':datetime.now(timezone.utc).isoformat(),'status':'PINNED_WHEEL_DOWNLOADED_HASH_VERIFIED_NOT_EXECUTED','pypi_metadata_sha256':hashlib.sha256(meta).hexdigest(),'artifact':chosen,'path':str(p),'entries':names,'hardware_io':0,'native_executed':False}
(C/'results/DM_NATIVE_INTAKE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'wheel':str(p),'entries':names},ensure_ascii=False))
