from geometry import *
import csv
plan=read(D/'inputs/NATIVE_ASSEMBLY_PLAN.json');lay=read(D/'inputs/INSTALLATION_LAYOUT.json')
oldprep=read(R6/'inputs/PROPULSION_ASSEMBLY_PREPARATION.json')
rows={r['id']:r for r in plan['expected_leaves']}
for x in oldprep['source_locks']:assert sha(x['path'])==x['sha256']
for r in oldprep['retained_CAD_objects']:
    new=rows[r['id']]
    if r['id']=='P60_TRAY_B':
        r.update(source_path=new['step_path'],source_sha256=new['source_sha256'],T_S_local=new['T_S_local'],S_frame_AABB_mm=[a.tolist() for a in world_bounds(new)],R4_identity_and_pose_preserved=False,change='P60 support tray local ear and new mounting hole; P60 electronics pose unchanged')
    else:assert new['source_sha256']==r['source_sha256'] and new['T_S_local']==r['T_S_local']
# The propulsion-related P60 tray is the sole changed preparation object. Its
# old shape is not passed off as preserved: nine unchanged, one locally revised.
oldprep.pop('source_R6_layout_sha256')
oldprep.update(schema='R6H_PROPULSION_PREPARATION_V1',source_R6H_layout_sha256=sha(D/'inputs/INSTALLATION_LAYOUT.json'),source_R6H_plan_sha256=sha(D/'inputs/NATIVE_ASSEMBLY_PLAN.json'),unchanged_objects=9,locally_revised_P60_tray=1)
oldprep['source_locks'].append(dict(path=str(R6/'inputs/PROPULSION_ASSEMBLY_PREPARATION.json'),sha256=sha(R6/'inputs/PROPULSION_ASSEMBLY_PREPARATION.json')))
write(D/'inputs/PROPULSION_ASSEMBLY_PREPARATION.json',oldprep)
write(D/'inputs/PROPULSION_OEM_INPUT_TEMPLATE.json',read(R6/'inputs/PROPULSION_OEM_INPUT_TEMPLATE.json'))
with (D/'docs/PROPULSION_NEXT_WORK_ORDERS.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(oldprep['work_orders'][0]));w.writeheader();w.writerows(oldprep['work_orders'])
with (D/'docs/INSTALLATION_BOM_DELTA.csv').open('w',encoding='utf-8-sig',newline='') as f:
    fields=['id','action','role','nominal_size','MPN','material_status','STEP_source','T_S_local']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    modified={r['id'] for r in lay['replacements']}
    for action,rr in [('ADD',lay['parts']),('REPLACE_GEOMETRY',lay['replacements']),('REPOSITION_REUSE',[r for r in lay['pose_changes'] if r['id'] not in modified])]:
        for r in rr:w.writerow(dict(id=r['id'],action=action,role='LOCAL_BEARING_TAB_AND_HOLE_CHANGE_NEW_MACHINING_CANDIDATE' if r['id']=='P60_TRAY_B' else r['representation_role'],nominal_size=r.get('nominal_size',''),MPN=r.get('MPN') or 'UNKNOWN',material_status='See native material receipt; unspecified hardware and mixed-PCBA mass UNKNOWN',STEP_source=r['step_path'],T_S_local=json.dumps(r['T_S_local'])))
with (D/'docs/INSTALLED_PORT_DATUMS.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(lay['ports'][0]));w.writeheader();w.writerows(lay['ports'])
write(D/'results/PROPULSION_PREPARATION_CHECK.json',dict(status='PASS_SOURCE_BOUND_HORIZONTAL_PREPARATION_ONLY',unchanged_objects=9,locally_revised_P60_tray=1,oem_open_items=9,work_orders=12,OEM_selected=False,assembly_frozen=False,ready_to_power=False))
print('Handoff rebound to R6H; 9 preserved objects + 1 revised tray; 12 work orders',flush=True)
