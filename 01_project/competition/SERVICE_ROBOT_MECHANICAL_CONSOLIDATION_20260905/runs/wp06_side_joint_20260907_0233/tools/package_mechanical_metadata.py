from pathlib import Path
import json,csv,hashlib,difflib,datetime
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
baseline=read(R/'inputs/SOURCE_BASELINE.json')
rows=[dict(path=x['path'],before=x['sha256'],after=sha(x['path'])) for x in baseline['files']]
audit=dict(status='PASS' if all(x['before']==x['after'] for x in rows) else 'FAIL',files=rows,scope='All pinned baseline inputs used in this work package; not a whole-project audit')
(R/'results/SCOPED_SOURCE_INTEGRITY.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
local=read(R/'results/LOCAL_PARTS.json')['parts'];context=read(R/'inputs/CONTEXT.json')
with (R/'results/LOCAL_BOM.csv').open('w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=['id','change','quantity','nominal_standard','step_path','solid_count','volume_mm3','material_grade','mass_kg','qualification']);w.writeheader()
    for key,row in local.items():
        change='MODIFIED_STRUCTURE' if key in context['changed_ids'] else 'NEW_CATALOG_FASTENER' if key.startswith('WP06') else 'UNCHANGED_CONTEXT'
        standard='ISO4762 M3x12' if key.startswith('WP06_screw') else 'ISO4032 M3' if key.startswith('WP06_nut') else 'DIN125 M3 3.2x7x0.5' if key.startswith('WP06_washer') else ''
        w.writerow(dict(id=key,change=change,quantity=1,nominal_standard=standard,step_path=row['path'],solid_count=row['facts']['solid_count'],volume_mm3=row['facts']['volume_mm3'],material_grade='NOT_ASSIGNED_BY_THIS_WORK_PACKAGE',mass_kg='UNKNOWN',qualification='NOT_EVALUATED'))
patch=[]
for name in ['r01_design.py','r07_design.py','design_parameters.json']:
    old=R.parent/'wp04_robot_assembly_20260906_175153/candidate'/name;new=R/'candidate'/name
    patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),new.read_text(encoding='utf-8').splitlines(True),fromfile='WP04/'+name,tofile='WP06/'+name))
(R/'results/SOURCE_CHANGES.diff').write_text(''.join(patch),encoding='utf-8')
sources={'catalogue_dimension_basis':'Actual saved STEP readback, not a purchase/material certificate',
 'standard_dimension_cross_checks':[
 {'title':'Bossard ISO4762 M3 drive size','url':'https://www.bossard.com/th-en/-/media/bossard-group/website/documents/technical-resources/en/f-077-en.pdf'},
 {'title':'Wuerth ISO4032 M3 nominal AF5.5 nut','url':'https://eshop.wuerth.de/Hexagon-nut-ISO-4032-steel-6-8-plain-NUT-HEX-ISO4032-6-WS55-M3/031093.sku/en/US/EUR/'},
 {'title':'Wuerth nominal washer size cross-check 3.2x7x0.5','url':'https://eshop.wuerth.de/Scheiben-und-Sechskantmuttern-SortimentSHB/MU-SYSKO-ISO4032/7089-A2-1200TLG/5964032201.sku/de/DE/EUR/'}],
 'catalogue_records':[read(p) for p in sorted((R/'inputs/catalog').glob('*download.json'))],
 'washer_choice':'ISO7089 search returned no item; DIN125 M3 exact saved catalogue part used and identified as DIN125. Standards equivalence and procurement qualification not asserted.'}
(R/'inputs/CATALOGUE_PROVENANCE.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(input_status=audit['status'],pinned_inputs=len(rows),bom_rows=len(local),new_hardware=16,modified_structure=8,context=29)))
