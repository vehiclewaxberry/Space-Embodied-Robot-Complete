"""Download the cited public component documents; no account/contact/order I/O."""
from pathlib import Path
import hashlib,json,urllib.request,urllib.parse,zipfile,io
A=Path(__file__).resolve().parents[1]
items=[
 ('lxg_2026.pdf','https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/LXGN-e.PDF','pdf'),
 ('chemi_al_precautions_2026.pdf','https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/al-precaution-e.pdf','pdf'),
 ('lxg_2200_100_product.html','https://www.chemi-con.co.jp/en/products/detail-condenser.php?part_number=ELXG101VSN222MR50S','html'),
 ('ELXG101VSN222MR50S_oem.zip','https://www.chemi-con.co.jp/members/download.php?dir1=capacitor&dir2=3dcad&ext=zip&file=ELXG101VSN222MR50S&lang=en','zip')]
rows=[]
for name,url,kind in items:
    row=dict(file=name,url=url)
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
            b=r.read(12*1024*1024+1);row.update(final_url=r.url,http=r.status,content_type=r.headers.get('Content-Type'))
        assert len(b)<=12*1024*1024
        valid=b.startswith(b'%PDF') if kind=='pdf' else zipfile.is_zipfile(io.BytesIO(b)) if kind=='zip' else b'<html' in b.lower() or b'<!doctype' in b.lower()
        if valid:
            p=A/'sources'/name;p.write_bytes(b);row.update(status='ACQUIRED',bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
            if kind=='zip':
                with zipfile.ZipFile(io.BytesIO(b)) as z:row['members']=z.namelist()
        else:row.update(status='NOT_EXPECTED_FILE_TYPE_NO_GEOMETRY_ACQUIRED',response_prefix=b[:90].decode('utf-8','replace'))
    except Exception as e:row.update(status='UNAVAILABLE',error=str(e))
    rows.append(row)
for term in ['ELXG101VSN222MR50S','LXG']:
    url='https://api.step.parts/v1/parts?'+urllib.parse.urlencode(dict(q=term,limit=3))
    for attempt in range(2):
        try:
            with urllib.request.urlopen(url,timeout=8) as r:response=json.load(r)
            rows.append(dict(catalog_query=term,url=url,status='REACHABLE_QUERY_RESULT',response=response));break
        except Exception as e:
            if attempt==1:rows.append(dict(catalog_query=term,url=url,status='UNREACHABLE_NOT_A_CONFIRMED_MISS',error=str(e)))
(A/'sources/INPUT_PASSIVE_SOURCE_MANIFEST.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))
