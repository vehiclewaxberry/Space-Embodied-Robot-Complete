from geometry import *
from itertools import combinations

mount=read(D/'inputs/MOUNT_LAYOUT.json');passage=read(D/'inputs/PASSAGE_LAYOUT.json')
changes={r['id']:r for r in mount['replacements']+passage['replacements']};new=mount['additions']
routeids={r['id'] for r in passage['replacements']}
junctions={'WP10_INTERNAL_BATTERY_BYPASS','release_power_data_route_0_1','release_power_data_route_1_1'}
report={'schema':'R4_INCREMENT_CHECK_V1','status':'RUNNING','states':[],'comparisons':[],'excluded_functional_junctions':[],
        'collisions':[],'unknown':[],'unchanged_legacy_pairs_recertified':False,'whole_motion_checked':False}
cache={}
def test(st,r,o):
    key=(r['id'],r['source_sha256'],str(r['T_S_local']),o['id'],o['source_sha256'],str(o['T_S_local']))
    if key not in cache:
        try:cache[key]={'common_mm3':g.volume(common(source(r),source(o))),'distance_mm':distance(source(r),source(o))}
        except Exception as e:cache[key]={'error':str(e)}
    item=dict(state=st,a=r['id'],b=o['id'],**cache[key]);report['comparisons'].append(item)
    if 'error' in item:report['unknown'].append(item)
    elif item['common_mm3']>1e-6:report['collisions'].append(item)

for st,rows in state_rows().items():
    current=[dict(changes.get(r['id'],r),group=r['group']) for r in rows]+new
    lookup={r['id']:r for r in current};seen=set()
    for ident in ['equipment_arm_drive']+sorted(routeids)+[r['id'] for r in new]:
        r=lookup[ident]
        for o in candidates(source(r),current,3.0 if ident in routeids else 0):
            if r['id']==o['id']:continue
            pair=tuple(sorted([r['id'],o['id']]))
            if pair in seen:continue
            seen.add(pair)
            if ident in routeids and o['id'] in routeids|junctions:
                report['excluded_functional_junctions'].append({'state':st,'a':ident,'b':o['id'],
                    'reason':'Inherited shared functional routing corridor or intentional logical junction; not two qualified physical wires'})
                continue
            test(st,r,o)
    report['states'].append({'state':st,'instances':len(current),'unique_ids':len(lookup),'tested_pairs':len(seen)})
report['mount_check_sha256']=sha(D/'results/MOUNT_STATIC_CHECK.json')
report['mount_pass']=read(D/'results/MOUNT_STATIC_CHECK.json')['valid']
report['interface_clip_gap_mm']=read(D/'results/MOUNT_STATIC_CHECK.json')['interface_to_clip_nominal_mm']
routepairs=[x for x in report['comparisons'] if x['a'] in routeids and 'distance_mm' in x]
report['route_minimum_nominal_gap_mm']=min(x['distance_mm'] for x in routepairs)
report['route_to_M3RB_mm']=min(x['distance_mm'] for x in routepairs if x['b']=='WP01-MT-M3RB-REUSED')
report['route_continuity']=[{'id':r['id'],'max_tangent_error':r['parameters']['tangent_continuity_max_error'],
    'analytic_volume_error_mm3':r['parameters']['analytic_volume_error_mm3'],'start':r['parameters']['start'],'end':r['parameters']['end']} for r in passage['replacements']]
report['nominal_2mm_screen_pass']=min(report['interface_clip_gap_mm'],report['route_minimum_nominal_gap_mm'])>=2.-1e-7
report['source_locks']=[{'path':p,'sha256':s} for p,s in SOURCE_CHECKS.items()]
report['valid']=report['mount_pass'] and report['nominal_2mm_screen_pass'] and not(report['collisions'] or report['unknown'])
report['status']='PASS_BOUNDED_R4_STATIC_LAYOUT' if report['valid'] else 'FAIL_CLOSED'
write(D/'results/INCREMENT_STATIC_CHECK.json',report)
print(json.dumps({k:v for k,v in report.items() if k not in ('comparisons','source_locks','excluded_functional_junctions')},ensure_ascii=False,indent=2))
assert report['valid']
