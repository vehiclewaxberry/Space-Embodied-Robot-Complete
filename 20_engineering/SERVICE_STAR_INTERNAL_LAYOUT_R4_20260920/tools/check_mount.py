from geometry import *
from itertools import combinations

layout=read(D/'inputs/MOUNT_LAYOUT.json');replace={r['id']:r for r in layout['replacements']};new=layout['additions']
states=state_rows();report={'status':'RUNNING','scope':'R4 mounting and interface increment; unchanged legacy overlaps not re-certified','states':[],
    'new_interferences':[],'cut_subset_checks':[],'new_internal_interferences':[],'exact_pairs':0,'unknown_pairs':[]}
origin={r['id']:r for r in states['service']}
for ident in ('adapter_arm_drive','upper_equipment_deck_B','thermal_interface_arm_drive'):
    a=source(replace[ident]);b=source(origin[ident]);extra=g.volume(cut(a,b));removed=g.volume(cut(b,a));assert extra<=1e-6
    report['cut_subset_checks'].append({'id':ident,'volume_added_mm3':extra,'volume_removed_mm3':removed})
targets=[replace['equipment_arm_drive']]+new
cache={}
def overlap(a,b):
    key=tuple(sorted([a['id'],b['id']]))+(a['source_sha256'],b['source_sha256'],str(a['T_S_local']),str(b['T_S_local']))
    if key not in cache:
        try:cache[key]=g.volume(common(source(a),source(b)))
        except Exception as e:report['unknown_pairs'].append({'a':a['id'],'b':b['id'],'error':str(e)});return None
    return cache[key]
for st,rows in states.items():
    current=[replace.get(r['id'],r) for r in rows];pairs=0
    for r in targets:
        for o in candidates(source(r),current):
            if o['id']==r['id']:continue
            v=overlap(r,o);pairs+=1;report['exact_pairs']+=1
            if v is not None and v>1e-6:report['new_interferences'].append({'state':st,'new':r['id'],'old':o['id'],'volume_mm3':v})
    report['states'].append({'state':st,'host_instances':len(current),'new_mount_instances':len(new),'exact_pairs':pairs})
for a,b in combinations(targets,2):
    alo,ahi=world_bounds(a);blo,bhi=world_bounds(b)
    if np.any(alo>=bhi) or np.any(blo>=ahi):continue
    v=overlap(a,b)
    if v is not None and v>1e-6:report['new_internal_interferences'].append({'a':a['id'],'b':b['id'],'volume_mm3':v})
report['interface_to_clip_nominal_mm']=distance(source(replace['equipment_arm_drive']),source(origin['trunk_clip_standoff_-140']))
report['valid']=not(report['new_interferences'] or report['new_internal_interferences'] or report['unknown_pairs'])
report['status']='PASS_MOUNT_STATIC_CANDIDATE' if report['valid'] else 'FAIL_MOUNT_STATIC_CANDIDATE'
write(D/'results/MOUNT_STATIC_CHECK.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
