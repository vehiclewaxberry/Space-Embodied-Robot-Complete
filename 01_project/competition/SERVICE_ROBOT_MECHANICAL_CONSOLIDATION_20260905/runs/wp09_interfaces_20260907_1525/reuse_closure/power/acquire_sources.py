"""Acquire bounded official datasheets. Never accesses hardware."""
from pathlib import Path
import hashlib,json,shutil,urllib.request,requests
from pypdf import PdfReader
N=Path(__file__).resolve().parents[1]
S=N/'sources'/'power'
old=N.parent/'functional_closure'/'inputs'/'vendor_sources'
rows=[]
for name in ['P60_DOCK_3_1','P60_PDU200_2_6','PDU200_OPTION_1021197_4_5','BPX100WH_DS1076870_1_1_0','A3200_DS1006901_2_0','RSP_500_20250926','ETA_ESX10_16A_2405','SAMTEC_SFSD']:
    p=old/(name+'.pdf'); q=S/p.name; shutil.copy2(p,q)
    rows.append({'file':q.name,'source_path':str(p),'source_type':'inherited_official_pdf','sha256':hashlib.sha256(q.read_bytes()).hexdigest()})
urls={
 'ACU200_DS1014406_2_3.pdf':'https://gomspace.com/wp-content/uploads/2025/09/gs-ds-nanopower-p60-acu200-23.pdf',
 'DOCK_OSF1014114_5_2.pdf':'https://gomspace.com/wp-content/uploads/2025/09/gs-osf-nanopower-p60-dock-52.pdf',
 'ACU200_OSF1014027_4_0.pdf':'https://gomspace.com/wp-content/uploads/2025/09/gs-os-nanopower-p60-acu200-401014027.pdf',
 'GX11_OFFICIAL.pdf':'https://www.sensata.com/sites/default/files/a/sensata-gigavac-gx11-series-open-contactors-datasheet.pdf',
 'EV200_OFFICIAL_CATALOG_2013.pdf':'https://www.te.com/content/dam/te-com/documents/aerospace-defense-and-marine/aerospace/global/hpg/5-1773450-5editable_section7.pdf',
 'AZUR_3G30_ADV_4x8_DB00010891_01.pdf':'https://www.azurspace.com/media/uploads/file_links/file/bdb_00010891-01-00_tj3g30-advanced_4x8.pdf',
 'ODRIVE_REGEN_0_6_12.html':'https://docs.odriverobotics.com/v/latest/hardware/regen-clamp-datasheet.html',
 'TE_EV200HAANA_PRODUCT.html':'https://www.te.com/en/product-1-1618002-8.html'}
for name,url in urls.items():
    q=S/name
    try:
        if not q.exists():
            r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=25)
            r.raise_for_status(); data=r.content
            if name.endswith('.pdf') and not data.startswith(b'%PDF'): raise ValueError('not PDF')
            q.write_bytes(data)
        rows.append({'file':name,'url':url,'sha256':hashlib.sha256(q.read_bytes()).hexdigest(),'download':'OK'})
    except Exception as e: rows.append({'file':name,'url':url,'download':'FAILED','error':str(e)})
    (S/'SOURCE_MANIFEST.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
for p in S.glob('*.pdf'):
    try:
        reader=PdfReader(p)
        (S/(p.stem+'.txt')).write_text('\n'.join(f'\nPDF PAGE {i+1}\n'+(x.extract_text() or '') for i,x in enumerate(reader.pages)),encoding='utf-8')
    except Exception as e: print(p.name,str(e))
print(json.dumps(rows,ensure_ascii=False,indent=2))
