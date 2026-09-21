from pathlib import Path
import requests,json,hashlib,zipfile,io,datetime
A=Path(__file__).resolve().parents[1];S=A/'sources/lugs_v30';S.mkdir(exist_ok=True)
base='https://www.te.com/commerce/DocumentDelivery/DDEController'
docs=[('130191_A3.pdf',dict(DocFormat='pdf',DocNm='130191',DocType='Customer Drawing',PartCntxt='130191')),('130191_C.zip',dict(DocFormat='3d_stp.zip',DocNm='CVM_130191',DocType='Customer View Model',PartCntxt='130191')),('55A0111_R.pdf',dict(DocFormat='pdf',DocNm='55A0111',DocType='Customer Drawing',PartCntxt='216127-000')),('408-1542_U.pdf',dict(DocFormat='pdf',DocNm='408-1542',DocType='Specification Or Standard',PartCntxt='49935'))]
rows=[]
def save(name,r):
 r.raise_for_status();b=r.content;assert b[:4] in [b'%PDF',b'PK\x03\x04'] or name.endswith('.json'),(name,b[:80]);p=S/name;assert not p.exists() or p.read_bytes()==b,'Source drift';p.write_bytes(b);rows.append(dict(path=name,url=r.url,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),retrieved=datetime.datetime.now().astimezone().isoformat()));return b
for name,params in docs:
 params.update(Action='srchrtrv',DocLang='English');b=save(name,requests.get(base,params=params,timeout=30))
 if name.endswith('.zip'):
  z=zipfile.ZipFile(io.BytesIO(b));n=next(n for n in z.namelist() if n.lower().endswith('.stp'));q=S/Path(n).name;q.write_bytes(z.read(n));rows.append(dict(path=q.name,archive=name,sha256=hashlib.sha256(q.read_bytes()).hexdigest(),bytes=q.stat().st_size))
for name,url in [('HPC_SHNbr.pdf','https://shop.hpceurope.com/pdf/gbPDFauto/SHNbr.pdf'),('ETTINGER_00305059.pdf','https://www.ettinger.de/en/product-datasheet/6ab7d4c4f9ed6359332cf1fc77167c9c/create'),('VICTREX_450G_202603.pdf','https://www.victrex.com/-/media/downloads/datasheets/victrex_tds_450g.pdf?rev=66e2f2641768427097e4ad8ce08deb49')]:
 save(name,requests.get(url,timeout=30))
searches=[]
for q in ['130191','SHN-5/BR/B','DIN934 M5','003.05.059','M5 washer','M3 socket 30']:
 r=requests.get('https://api.step.parts/v1/parts',params=dict(q=q,pageSize=4),timeout=30);r.raise_for_status();d=r.json();searches.append(dict(q=q,url=r.url,total=d['total'],items=d['items']))
(S/'STEP_PARTS_SEARCH.json').write_text(json.dumps(searches,indent=2));(S/'SOURCE_MANIFEST.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2));print([(s['q'],s['total']) for s in searches])
