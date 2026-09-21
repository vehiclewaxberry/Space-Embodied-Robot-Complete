"""Archive selected public primary PDFs, retaining explicit download failures."""
from pathlib import Path
import json,urllib.request,hashlib,concurrent.futures
A=Path(__file__).resolve().parents[1];R=A/'results/stop_v36/pcb';S=R/'sources';S.mkdir(exist_ok=True)
parts=json.loads((R/'PHYSICAL_PARTS.json').read_text());urls=sorted({p['source_url'] for p in parts.values() if '/part-detail/' not in p['source_url']})
urls+=['https://www.molex.com/pdm_docs/sd/430450201_sd.pdf','https://www.molex.com/pdm_docs/sd/436500201_sd.pdf']
def get(u):
    name=u.rstrip('/').split('/')[-1]
    if not name.lower().endswith('.pdf'):name+='.pdf'
    p=S/name
    try:
        if p.exists():data=p.read_bytes()
        else:
            with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'WP10 engineering source archival'}),timeout=25) as r:data=r.read(10000000)
            assert data.startswith(b'%PDF-'), 'Not PDF; not saved'
            p.write_bytes(data)
        assert data.startswith(b'%PDF-')
        return dict(url=u,path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),status='ARCHIVED_PRIMARY_PDF')
    except Exception as e:return dict(url=u,status='NOT_ARCHIVED',error=repr(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(get,urls))
(R/'PUBLIC_PDF_ARCHIVE.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))
