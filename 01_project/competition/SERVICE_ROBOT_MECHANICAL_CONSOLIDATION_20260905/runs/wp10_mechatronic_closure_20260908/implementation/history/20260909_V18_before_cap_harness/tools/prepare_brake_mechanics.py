from pathlib import Path
import hashlib,json,urllib.request,zipfile
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for q in ['LPS300','Vishay LPS 300']:
    u='https://api.step.parts/v1/parts?q='+urllib.parse.quote(q)+'&pageSize=3'
    with urllib.request.urlopen(u,timeout=20) as r:d=json.load(r)
    rows.append(dict(query=q,url=u,total=d['total'],items=d['items']))
with zipfile.ZipFile(A/'sources/lps300_3d_response.bin') as z:
    names=z.namelist();assert set(names)=={'523388-36 LPS 3D.stp','99917_read_me_3D_disclaimer.pdf'},names
    b=z.read(names[0]);assert b.startswith(b'ISO-10303-21')
    target=A/'sources/LPS300_OEM.step';target.write_bytes(b)
    (A/'sources/LPS300_OEM_3D_disclaimer.pdf').write_bytes(z.read('99917_read_me_3D_disclaimer.pdf'))
out=dict(search=rows,official_model=dict(source_pdf='lps300.pdf p1 embedded3D link',
    model_redirect_url='https://www.vishay.com/doc?50061',resolved_zip_url='https://www.vishay.com/docs/50061/_lps_3dmodel.zip',
    zip_file='sources/lps300_3d_response.bin',zip_sha256=sha(A/'sources/lps300_3d_response.bin'),
    selected_member=names[0],step_file='sources/LPS300_OEM.step',step_sha256=sha(target)),
    model_is_resistor_family_geometry_not_confirmed_as_built_revision=True,physical_installation=False)
(A/'sources/BRAKE_MECHANICAL_SOURCE_MANIFEST.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(step_bytes=len(b),step_sha256=sha(target),search_results=[r['total'] for r in rows])))
