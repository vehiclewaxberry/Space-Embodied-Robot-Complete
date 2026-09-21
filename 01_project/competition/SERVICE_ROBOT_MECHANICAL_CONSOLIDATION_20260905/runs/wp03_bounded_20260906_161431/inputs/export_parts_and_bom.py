"""Export custom local parts, then write full product BOM from complete receipts."""
from spacecraft_model import build,HERE
import csv,json,sys
def main():
    if '--bom-only' not in sys.argv:build('service',include_arm=False,write_parts=True)
    p=HERE/'results/service_instances.json'
    if not p.is_file():
        print('Custom parts exported; complete assembly receipt still required for final BOM');return
    r=json.loads(p.read_text(encoding='utf-8'))
    dp=HERE/'results/DYNAMICS_HANDOFF.json'
    if dp.is_file():
        d=json.loads(dp.read_text(encoding='utf-8'));s=next(x for x in d['states'] if x['state']=='service')
        for row in r['instances']:
            row['allocated_dynamics_mass_kg']=s['mass_owner_values'].get(row['mass_owner'])
            row['allocated_dynamics_mass_source']='SOURCE_DIGITAL' if row.get('arm_link') else row['mass_source']
            row['allocated_mass_reference']='results/DYNAMICS_HANDOFF.json'
        total=sum(row['allocated_dynamics_mass_kg'] or 0 for row in r['instances'])
        if abs(total-s['groups']['ONBOARD_CANDIDATE']['known_mass_kg'])>1e-10:raise ValueError('BOM mass mapping mismatch')
    cols=['id','pn','product_role','representation_role','qualification_status','parent_assembly','mount_interface','mass_source','mass_owner','mass_kg','mass_basis','source_revision','allocated_dynamics_mass_kg','allocated_dynamics_mass_source','allocated_mass_reference']
    with (HERE/'BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(r['instances'])
    with (HERE/'INTERFACES.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(r['interfaces'][0]));w.writeheader();w.writerows(r['interfaces'])
    print('Full service BOM',len(r['instances']),'custom STEP',len(list((HERE/'parts').glob('*.step'))))
if __name__=='__main__':main()
