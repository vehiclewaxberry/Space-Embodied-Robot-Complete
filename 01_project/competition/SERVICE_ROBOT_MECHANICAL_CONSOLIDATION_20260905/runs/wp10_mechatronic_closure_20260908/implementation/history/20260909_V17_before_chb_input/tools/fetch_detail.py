from pathlib import Path
import urllib.request,json,hashlib,zipfile
A=Path(__file__).resolve().parents[1]; S=A/'sources'
items=[('pmm35.pdf','https://www.rrc-ps.com/fileadmin/Dokumente/Data-Sheets/DS_RRC-PMM35_A_01.pdf'),('mc35.pdf','https://www.rrc-ps.com/fileadmin/Dokumente/Data-Sheets/DS_RRC-MC35-180-30_A.PDF'),('chb500w_application.pdf','https://www.cincon.com/productdownload/CHB500W-series-application-note.pdf'),('chb500w_3d.zip','https://www.cincon.com/productdownload/CHB500W-3D.zip'),('vacco_0414.pdf','https://www.vacco.com/images/uploads/pdfs/ReactionControlPropulsionModule-X13003000-01_0414.pdf')]
out=[]
for name,url in items:
 try:
  p=S/name
  if not p.exists():p.write_bytes(urllib.request.urlopen(url,timeout=25).read())
  row=dict(path=str(p),url=url,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
  if name.endswith('.zip'):
   with zipfile.ZipFile(p) as z:
    row['members']=z.namelist(); dest=S/'cincon_oem';dest.mkdir(exist_ok=True)
    for n in z.namelist():
     target=(dest/n).resolve();assert target.is_relative_to(dest.resolve());z.extract(n,dest)
  out.append(row)
 except Exception as e:out.append(dict(url=url,error=str(e)))
(S/'DETAIL_SOURCE_MANIFEST.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
