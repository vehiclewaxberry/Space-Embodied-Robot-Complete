from pathlib import Path
import urllib.request, hashlib, json
from pypdf import PdfReader
C=Path(__file__).resolve().parents[1]
D=C/'sources/power_intake';D.mkdir(parents=True,exist_ok=True)
sources={
 'TDK_i7C_spec.pdf':'https://product.tdk.com/system/files/dam/doc/product/power/switching-power/dc-dc-converter/specification/i7c_spec.pdf',
 'TDK_i7C_parallel_EVK.pdf':'https://product.tdk.com/system/files/dam/doc/product/power/switching-power/pwr-acc/instruction_manual/i7cxxa-cc3-evk-p2_apl.pdf',
 'Inventus_MB2590_300.pdf':'https://inventuspower.com/wp-content/uploads/IP_TDS_MB-2590-300_Sept-2023_V1_Web.pdf',
 'TPS1H100_datasheet.pdf':'https://www.ti.com/lit/ds/symlink/tps1h100-q1.pdf',
 'TPS3431_datasheet.pdf':'https://www.ti.com/lit/ds/symlink/tps3431.pdf',
 'LTC4020_datasheet.pdf':'https://www.analog.com/media/en/technical-documentation/data-sheets/4020fd.pdf',
}
out=[]
for name,url in sources.items():
 p=D/name
 try:
  if not p.exists():
   req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
   b=urllib.request.urlopen(req,timeout=45).read()
   assert b.startswith(b'%PDF'),str(b[:50]);p.write_bytes(b)
  pages=PdfReader(p).pages
  (D/(name+'.txt')).write_text('\n'.join(f'\n--- PAGE {i+1} ---\n'+(pg.extract_text() or '') for i,pg in enumerate(pages)),encoding='utf8')
  out.append(dict(file=name,url=url,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pages=len(pages),status='DOWNLOADED_PRIMARY_PDF'))
 except Exception as e:out.append(dict(file=name,url=url,status='FAILED',error=str(e)))
(D/'SOURCE_RECEIPT.json').write_text(json.dumps(out,indent=2),encoding='utf8')
print(json.dumps(out,indent=2))
