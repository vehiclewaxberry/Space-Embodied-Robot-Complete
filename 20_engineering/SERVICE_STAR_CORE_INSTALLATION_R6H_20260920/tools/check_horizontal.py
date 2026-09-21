from geometry import *
from itertools import combinations
from OCP.BRepCheck import BRepCheck_Analyzer
lay=read(D/'inputs/INSTALLATION_LAYOUT.json');mods={r['id']:r for r in lay['replacements']+lay['pose_changes']};delta=lay['parts']+lay['pose_changes'];states=state_rows()
out=dict(schema='R6H_STATIC_CHECK_V1',status='RUNNING',source_layout_sha256=sha(D/'inputs/INSTALLATION_LAYOUT.json'),scope='Horizontal MAIN + thermal bridge + one relocated P60 support; three fixed states; full-motion/tolerances/strength not qualified',collisions=[],unknown=[],internal_collisions=[],states=[],exact_pair_count=0,unique_pair_count=0,contact_distances=[],modification_checks=[])
cache={}
def overlap(a,b):
    k=tuple(sorted([r['source_sha256']+str(r['T_S_local']) for r in (a,b)]))
    if k not in cache:
        sa,sb=source(a),source(b);assert BRepCheck_Analyzer(sa).IsValid() and BRepCheck_Analyzer(sb).IsValid()
        cache[k]=g.volume(common(sa,sb));out['unique_pair_count']+=1
    return cache[k]
for st,rr in states.items():
    host=[mods.get(r['id'],r) for r in rr];pairs=0
    for a in delta:
        for b in candidates(source(a),host):
            if a['id']==b['id']:continue
            pairs+=1;out['exact_pair_count']+=1
            try:
                v=overlap(a,b)
                if v>1e-5:out['collisions'].append(dict(state=st,a=a['id'],b=b['id'],volume_mm3=v))
            except Exception as e:out['unknown'].append(dict(state=st,a=a['id'],b=b['id'],error=str(e)))
    out['states'].append(dict(state=st,host_rows=len(host),pairs=pairs));print(st,pairs,'collisions',out['collisions'],'unknown',out['unknown'],flush=True)
    write(D/'results/INCREMENT_STATIC_CHECK.json',out)
for a,b in combinations(lay['parts'],2):
    if not candidates(source(a),[b]):continue
    out['exact_pair_count']+=1
    try:
        v=overlap(a,b)
        if v>1e-5:out['internal_collisions'].append(dict(a=a['id'],b=b['id'],volume_mm3=v))
    except Exception as e:out['unknown'].append(dict(a=a['id'],b=b['id'],error=str(e)))
original={r['id']:r for r in states['service']};current=dict(original);current.update(mods);current.update({r['id']:r for r in lay['parts']})
for r in lay['replacements']:
    if r.get('change_kind')=='MOVED_AND_LENGTHENED_ROD':
        added_length=g.volume(source(r))-g.volume(source(original[r['id']]))
        assert abs(added_length-3*np.pi*1.5**2)<1e-5
        out['modification_checks'].append(dict(id=r['id'],nominal_rod_length_extension_mm=3,volume_added_mm3=added_length,whole_moved_rod_in_delta_check=True));continue
    add=g.volume(cut(source(r),source(original[r['id']])));remove=g.volume(cut(source(original[r['id']]),source(r)))
    out['modification_checks'].append(dict(id=r['id'],added_mm3=add,removed_mm3=remove))
    if r['id']=='P60_TRAY_B':
        expected_tab_after_half_bore=5*12*2-np.pi*1.7**2
        if abs(add-expected_tab_after_half_bore)>1e-4:out['unknown'].append(dict(id=r['id'],error='Tray added volume differs from declared bored 5x12x2mm tab'))
        added=cut(source(r),source(original[r['id']]))
        for b in candidates(added,[q for q in current.values() if q['id']!=r['id']]):
            v=g.volume(common(added,source(b)));out['exact_pair_count']+=1
            if v>1e-5:out['collisions'].append(dict(a='P60_TRAY_ADDED_TAB',b=b['id'],volume_mm3=v))
    elif add>1e-5:out['unknown'].append(dict(id=r['id'],error='Undeclared added material'))
for a,b in [('R6H_IF_THERMAL_BRIDGE','R6H_IF_TOP_ISOLATION_PAD'),('R6H_IF_THERMAL_BRIDGE','thermal_interface_arm_drive'),('R6H_IF_TOP_ISOLATION_PAD','equipment_arm_drive')]+[(f'R6H_MAIN_SPACER_{n}','upper_equipment_deck_B') for n in range(1,5)]+[(f'R6H_MAIN_SPACER_{n}','R6H_MAIN_PCBA_INSTALLED') for n in range(1,5)]+[(f'R6H_MAIN_WASHER_TOP_{n}','R6H_MAIN_PCBA_INSTALLED') for n in range(1,5)]:
    out['contact_distances'].append(dict(a=a,b=b,gap_mm=distance(source(current[a]),source(current[b]))))
out['critical_clearances']=[]
for a,b in [('P60_HOST_2_TN','P60_REFERENCE_B'),('R6H_MAIN_SPACER_1','adapter_compute_communications'),('R6H_MAIN_PCBA_INSTALLED','P60_HOST_2_POST')]:
    out['critical_clearances'].append(dict(a=a,b=b,gap_mm=distance(source(current[a]),source(current[b]))))
out['valid']=not(out['collisions'] or out['internal_collisions'] or out['unknown']) and all(x['gap_mm']<1e-6 for x in out['contact_distances'])
out.update(status='PASS_HORIZONTAL_STATIC_DIGITAL_CANDIDATE' if out['valid'] else 'FAIL_HORIZONTAL_STATIC_DIGITAL_CANDIDATE',horizontal=True,PCB_nominal_stack_envelope_mm=1.6,full_tolerance_analysis=False,thermal_performance_pass=False,ready_to_power=False,flight_ready=False)
write(D/'results/INCREMENT_STATIC_CHECK.json',out);print(out['status'],out['exact_pair_count'],out['unique_pair_count'],out['internal_collisions'],out['critical_clearances'],flush=True)
