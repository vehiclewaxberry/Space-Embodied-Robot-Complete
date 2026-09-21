"""Produce one-configuration review BOM, never sum alternative poses as hardware."""
from pathlib import Path
import csv,json,hashlib,collections,math
R=Path(__file__).resolve().parents[1]
p=R/'results/INTEGRATION_MANIFEST.json'
m=json.loads(p.read_text(encoding='utf-8'))
rows=m['states']['service']['instances']
assert len(rows)==597 and len({r['id'] for r in rows})==597
fields=['configuration','instance_id','part_key','quantity','parent_assembly','representation_role','change',
        'expected_solids','source_allocated_mass_kg','mass_source','native_path','native_sha256','source_step_path','source_sha256']
with (R/'results/ASSEMBLY_BOM_SERVICE.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for row in rows:
        w.writerow(dict(configuration='SERVICE_ONLY_ALTERNATIVE_POSES_NOT_ADDITIONAL_HARDWARE',instance_id=row['id'],
            part_key=row['part_key'],quantity=1,parent_assembly=row.get('parent_assembly'),representation_role=row['representation_role'],
            change=row['change'],expected_solids=row['expected_solids'],source_allocated_mass_kg=row.get('source_mass_kg'),
            mass_source=row.get('mass_source'),native_path=row['native_path'],native_sha256=row['native_sha256'],
            source_step_path=row['step_path'],source_sha256=row['source_sha256']))
groups=collections.defaultdict(list)
for row in rows:groups[row['native_path']].append(row)
with (R/'results/PARTS_BOM_SERVICE.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['native_path','native_sha256','quantity','instance_ids','representation_role','purchasing_ready'])
    w.writeheader()
    for path,items in groups.items():
        assert len({x['native_sha256'] for x in items})==1
        w.writerow(dict(native_path=path,native_sha256=items[0]['native_sha256'],quantity=len(items),
            instance_ids=';'.join(x['id'] for x in items),representation_role=';'.join(sorted({x['representation_role'] for x in items})),purchasing_ready=False))
known=[r for r in rows if r.get('source_mass_kg') is not None]
out=dict(schema='WP07_CONFIGURATION_BOM_AUDIT',manifest_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
    configuration='service',instance_count=len(rows),unique_native_parts=len(groups),solid_count=sum(r['expected_solids'] for r in rows),
    roles=dict(collections.Counter(r['representation_role'] for r in rows)),
    changes=dict(collections.Counter(r['change'] for r in rows)),
    allocated_mass_known_instances=len(known),allocated_mass_unknown_instances=len(rows)-len(known),
    allocated_mass_partial_sum_kg=math.fsum(r['source_mass_kg'] for r in known),
    complete_mass_budget=False,physical_mass_measured=False,purchasing_bom=False,
    notes=['Each ID appears once. Parking/released are alternative configurations of the same robot.',
           'Source allocation sum is incomplete and includes source provisional assumptions, not a measured whole-robot mass.',
           'Physical geometry, simplified proxies and functional envelopes are distinguished; they are not all purchasable items.',
           'Native dependencies remain in pinned WP05/WP06 libraries. This is a linked workspace assembly, not a standalone Pack and Go.'])
(R/'results/BOM_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out))
