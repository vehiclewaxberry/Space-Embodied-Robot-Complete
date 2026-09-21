from pathlib import Path
from pypdf import PdfReader
import json,hashlib
E=Path(__file__).resolve().parents[1];S=E/'sources';C=E.parents[1]/'wp09_interfaces_20260907_1525/system_completion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for name,url in [('tc4420','https://ww1.microchip.com/downloads/en/DeviceDoc/21419D.pdf'),('vishay_pr','https://www.vishay.com/doc?28729=')]:
 p=S/(name+'.pdf');reader=PdfReader(p);txt='\n'.join('PAGE '+str(i+1)+'\n'+(p.extract_text() or '') for i,p in enumerate(reader.pages));p.with_suffix('.txt').write_text(txt,encoding='utf8');rows.append(dict(id=name,url=url,status='OFFICIAL_PDF_DOWNLOADED',path=p.name,sha256=sha(p),bytes=p.stat().st_size,pages=len(reader.pages)))
for p in S.glob('tsr1*.pdf'):
 if not p.read_bytes().startswith(b'%PDF'):p.rename(p.with_suffix('.403.html'))
rows.append(dict(id='traco_tsr1',url='https://www.tracopower.com/tsr1-datasheet',status='OFFICIAL_INDEXED_TEXT_LOCKED_BINARY_403',path='TRACO_OFFICIAL_WEB_RETRIEVAL.json',sha256=sha(S/'TRACO_OFFICIAL_WEB_RETRIEVAL.json'),official_pdf_sha256=None,selected_visible_revision='February7 2024',not_claimed_latest_pdf_revision=True))
par=C/'electrical_delta/sources/FINAL_SOURCE_LOCK.json';rows.append(dict(id='inherited17',path=str(par),sha256=sha(par),status='INHERITED_FROZEN_SOURCE_LOCK',new_acquisition=False))
(S/'SOURCE_LOCK.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps(rows))
