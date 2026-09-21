from pathlib import Path
import urllib.request,hashlib,json,datetime
A=Path(__file__).resolve().parents[1]
items=[('countersunk_socket_screw_m3_l0020_simple','3811dc212a01dfb2edcd9e049cb2cbdb954646bbc96784ddffe68f307e6d6e57','BOTTOM_M3_CSUNK_CATALOG.step'),
 ('flat_washer_normal_m3_simple','6aaad3e26efa4c59d8c081d53fb38053091648aa8f34c031294b50fbd743f409','BOTTOM_M3_WASHER_CATALOG.step'),
 ('iso4032_hex_nut_m3','7de90cc2ca5eb2c38a27e3aee66939f30bdfde4ac47cd6f19f0324fcf93496bd','BOTTOM_M3_NUT_CATALOG.step')]
out=[]
for key,expected,name in items:
    url='https://media.githubusercontent.com/media/earthtojake/step.parts/c6113328a5695b976a010a203a90fe86191769bf/catalog/step/'+key+'.step'
    with urllib.request.urlopen(url,timeout=25) as r:data=r.read(5*1024*1024+1)
    assert len(data)<=5*1024*1024 and data.lstrip().startswith(b'ISO-10303-21') and hashlib.sha256(data).hexdigest()==expected
    (A/'sources'/name).write_bytes(data)
    out.append(dict(id=key,path='sources/'+name,source_url=url,sha256=expected,bytes=len(data),
      api_url='https://api.step.parts/v1/parts/'+key,page_url='https://www.step.parts/parts/'+key,role='CATALOG_STANDARD_GEOMETRY__NOT_VENDOR_LOT_OR_HARDWARE_QUALIFICATION',accessed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
(A/'sources/BOTTOM_HARDWARE_CATALOG.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out))
