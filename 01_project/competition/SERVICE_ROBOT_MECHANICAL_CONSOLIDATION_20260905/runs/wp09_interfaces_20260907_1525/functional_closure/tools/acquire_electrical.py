from pathlib import Path
import requests,json,hashlib
from pypdf import PdfReader
F=Path(__file__).resolve().parents[1];o=F/'inputs/vendor_sources'
docs={
 'FTDI_RS422_v1_4.pdf':'https://ftdichip.com/wp-content/uploads/2023/07/DS_USB_RS422_CABLES.pdf',
 'SAMTEC_SFSD.pdf':'https://suddendocs.samtec.com/catalog_english/sfsd.pdf',
 'LAPP_STM.html':'https://products.lappgroup.com/online-catalogue/cable-glands/skintop-cable-glands-plastic-metric/standard/skintop-st-m.html',
 'LAPP_LOCKNUT.html':'https://vn.lapp.com/products/53119010',
 'LAPP_110LT.html':'https://products.lappgroup.com/online-catalogue/power-and-control-cables/various-applications/pvc-outer-sheath-and-numbered-cores/oelflex-classic-110-lt.html',
 'BELDEN_8723.html':'https://www.belden.com/products/cable/electronic-wire-cable/multi-pair-cable/8723',
 'MOLEX_51021.pdf':'https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/510/51021/510210700_sd.pdf',
 'FUSE_451.pdf':'https://www.littelfuse.com/assetdocs/fuse-451-and-453-datasheet?assetguid=533cd5cc-956c-4243-867f-6ab5a62f6ba1',
}
r=[]
for name,url in docs.items():
 p=o/name
 try:
  if not p.exists():
   q=requests.get(url,timeout=25,headers={'User-Agent':'Mozilla/5.0'});q.raise_for_status();p.write_bytes(q.content)
  if name.endswith('.pdf'):
   d=PdfReader(p);p.with_suffix('.txt').write_text('\n'.join('PDF PAGE '+str(i+1)+'\n'+x.extract_text() for i,x in enumerate(d.pages)),encoding='utf-8')
  r.append(dict(path=str(p),url=url,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),ok=True))
 except Exception as ex:r.append(dict(url=url,ok=False,error=str(ex)))
 print(name,r[-1]['ok'],flush=True)
search=[]
for q in ['SKINTOP ST-M 16','LAPP 53111010','53119010']:
 try:
  a=requests.get('https://api.step.parts/v1/parts',params={'q':q,'limit':5},timeout=25);a.raise_for_status();j=a.json();search.append(dict(query=q,reachable=True,result=j))
 except Exception as ex:search.append(dict(query=q,reachable=False,error=str(ex)))
(F/'research/ELECTRICAL_ADDITIONAL_SOURCES.json').write_text(json.dumps(dict(downloads=r,step_parts=search),ensure_ascii=False,indent=2),encoding='utf-8')
