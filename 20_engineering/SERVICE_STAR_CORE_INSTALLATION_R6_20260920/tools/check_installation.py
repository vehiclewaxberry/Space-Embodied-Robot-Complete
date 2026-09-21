from geometry import *
from itertools import combinations
from OCP.BRepCheck import BRepCheck_Analyzer
layout=read(D/'inputs/INSTALLATION_LAYOUT.json');rep={r['id']:r for r in layout['replacements']};new=layout['parts'];states=state_rows()
out={'schema':'R6_INCREMENT_STATIC_CHECK_V1','status':'RUNNING','scope':'New mixed-representation main-board installation and interface thermal bridge; unchanged whole-star overlaps and full-motion/tolerance not requalified',
 'states':[],'collisions':[],'unknown':[],'internal_collisions':[],'cut_subset':[],'contact_distances':[],'exact_pair_count':0,'unique_pair_count':0}
cache={}
def overlap(a,b):
 key=tuple(sorted([a['source_sha256']+str(a['T_S_local']),b['source_sha256']+str(b['T_S_local'])]))
 if key not in cache:
  sa,sb=source(a),source(b)
  assert BRepCheck_Analyzer(sa).IsValid() and BRepCheck_Analyzer(sb).IsValid()
  cache[key]=g.volume(common(sa,sb));out['unique_pair_count']+=1
 return cache[key]
for st,rr in states.items():
 before={r['id']:r for r in rr};host=[rep.get(r['id'],r) for r in rr];count=0
 for r in new:
  for old in candidates(source(r),host):
   count+=1;out['exact_pair_count']+=1
   try:
    v=overlap(r,old)
    if v>1e-5:out['collisions'].append({'state':st,'a':r['id'],'b':old['id'],'volume_mm3':v})
   except Exception as e:out['unknown'].append({'state':st,'a':r['id'],'b':old['id'],'error':str(e)})
 out['states'].append({'state':st,'host_rows':len(host),'pairs':count});print(st,'pairs',count,'collisions',len(out['collisions']),'unknown',len(out['unknown']),flush=True)
 write(D/'results/INCREMENT_STATIC_CHECK.json',out)
for a,b in combinations(new,2):
 lo,hi=world_bounds(a);lo2,hi2=world_bounds(b)
 if np.any(lo>hi2+1e-8) or np.any(lo2>hi+1e-8):continue
 out['exact_pair_count']+=1
 try:
  v=overlap(a,b)
  if v>1e-5:out['internal_collisions'].append({'a':a['id'],'b':b['id'],'volume_mm3':v})
 except Exception as e:out['unknown'].append({'a':a['id'],'b':b['id'],'error':str(e)})
original={r['id']:r for r in states['service']}
for k,r in rep.items():
 extra=g.volume(cut(source(r),source(original[k])));removed=g.volume(cut(source(original[k]),source(r)))
 out['cut_subset'].append({'id':k,'added_mm3':extra,'removed_mm3':removed})
 if extra>1e-5:out['unknown'].append({'id':k,'error':'Modification added material beyond drilled-hole scope'})
newmap={r['id']:r for r in new}
for a,b in [('R6_IF_THERMAL_BRIDGE','R6_IF_TOP_ISOLATION_PAD'),('R6_IF_THERMAL_BRIDGE','thermal_interface_arm_drive'),('R6_IF_TOP_ISOLATION_PAD','equipment_arm_drive'),('R6_MAIN_ANGLED_CARRIER','adapter_compute_communications')]:
 ra=newmap[a];rb=newmap.get(b) or rep.get(b) or original[b]
 out['contact_distances'].append({'a':a,'b':b,'gap_mm':distance(source(ra),source(rb))})
out['valid']=not(out['collisions'] or out['internal_collisions'] or out['unknown'])
out['status']='PASS_STATIC_DIGITAL_CANDIDATE' if out['valid'] else 'FAIL_STATIC_DIGITAL_CANDIDATE'
out.update(PCB_stackup_contact_uncertainty_mm=.085,full_tolerance_analysis=False,all_main_component_heights_verified=False,thermal_performance_pass=False,ready_to_power=False,flight_ready=False)
write(D/'results/INCREMENT_STATIC_CHECK.json',out)
print({k:out[k] for k in ['status','exact_pair_count','unique_pair_count','collisions','internal_collisions','unknown','contact_distances']},flush=True)
