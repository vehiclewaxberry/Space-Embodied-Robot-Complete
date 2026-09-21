"""Finite official-source retrieval for the same WP10 load-side circuit."""
from pathlib import Path
import hashlib, json, urllib.request
A=Path(__file__).resolve().parents[1]
specs={
 'lt3013.pdf':'https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf',
 'tlv6700.pdf':'https://www.ti.com/lit/ds/symlink/tlv6700.pdf',
 'ucc27511.pdf':'https://www.ti.com/lit/ds/symlink/ucc27511.pdf',
 'lps300.pdf':'https://www.vishay.com/docs/50052/lps300.pdf',
 'resistor_pulse_capabilities.pdf':'https://www.vishay.com/docs/50060/pulsecapabilities.pdf',
 'ntcle100.pdf':'https://www.vishay.com/docs/29049/ntcle100.pdf',
 'stps30h100c.pdf':'https://www.st.com/resource/en/datasheet/stps30h100c.pdf',
}
rows=[]
for f,u in specs.items():
 p=A/'sources'/f
 try:
  if not p.exists():
   with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as r:b=r.read(12*1024*1024)
   assert b.startswith(b'%PDF'),f
   p.write_bytes(b)
  b=p.read_bytes();assert b.startswith(b'%PDF')
  rows.append(dict(file=f,url=u,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),status='ACQUIRED'))
 except Exception as exc:
  rows.append(dict(file=f,url=u,status='LOCAL_DOWNLOAD_NOT_ACCEPTED',error=repr(exc)))
(A/'sources/LOAD_SIDE_BRAKE_SOURCE_MANIFEST.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows))
