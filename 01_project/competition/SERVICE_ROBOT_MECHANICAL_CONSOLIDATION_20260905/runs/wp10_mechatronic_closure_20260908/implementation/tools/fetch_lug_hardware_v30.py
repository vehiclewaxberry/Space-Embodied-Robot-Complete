from pathlib import Path
import requests,json,hashlib
A=Path(__file__).resolve().parents[1];S=A/'sources/lugs_v30';rows=[]
for key in ['flat_washer_normal_m5_simple','flat_washer_normal_m3_simple','iso4032_hex_nut_m3','iso4762_socket_head_cap_screw_m3x30']:
 r=requests.get('https://api.step.parts/v1/parts/'+key,timeout=20)
 if r.status_code!=200:rows.append(dict(id=key,status=r.status_code));continue
 d=r.json();d=d.get('part',d);r2=requests.get(d['stepUrl'],timeout=20);r2.raise_for_status();b=r2.content;assert hashlib.sha256(b).hexdigest()==d['sha256'];(S/(key+'.step')).write_bytes(b);rows.append(d)
(S/'HARDWARE_CATALOG_RESOLVED.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
