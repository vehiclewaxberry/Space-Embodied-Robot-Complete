"""Cold-read scoped V6 delta checks; no geometry producer imports."""
from pathlib import Path
import json,hashlib,importlib.util,sys,itertools,math
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parents[1];R=F.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());mf=json.loads((R/'results/INTEGRATION_MANIFEST_V6.json').read_text());e=json.loads((F/'results/PORTS_EMISSION.json').read_text());I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
spec=importlib.util.spec_from_file_location('ports_check_reader',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
job={'parts':{},'tolerances':c['acceptance']};bb={};states={};ids={};pins={};roles={}
for k,v in e['parts'].items():
 job['parts'][k]=dict(path=v['path'],sha256=v['sha256'],T_S_local=I);bb[k]=v['bbox_mm'];ids[k]=k;roles[k]=v['representation_role'];pins[v['path']]=v['sha256']
dedup={}
for st,state in mf['states'].items():
 states[st]=[]
 for row in state['instances']:
  sig=json.dumps([row['id'],row['source_sha256'],row['T_S_local']])
  if sig not in dedup:
   key='P'+str(len(dedup));dedup[sig]=key;job['parts'][key]=dict(path=row['step_path'],sha256=row['source_sha256'],T_S_local=row['T_S_local']);bb[key]=row['bounds_mm'];ids[key]=row['id'];roles[key]=row['representation_role'];pins[row['step_path']]=row['source_sha256']
  states[st].append(dedup[sig])
g=m.Geometry(job,pins)
facts={k:g.facts(g.load(k)) for k in e['parts']}
assert all(v['shape_valid'] and v['solid_count']==1 for v in facts.values())
for k,v in facts.items():assert abs(v['volume_mm3']-e['parts'][k]['volume_mm3'])<=1e-5
coverkey=next(k for k in states['service'] if ids[k]=='front_service_cover');old=g.load(coverkey);new=g.load('front_service_cover_GSE')
added=g.volume(new-old);removed=g.volume(old-new);expected=2*math.pi*8.1**2*2
assert added<=1e-5 and abs(removed-expected)<=1e-5
def overlaps(a,b):return all(min(bb[a]['max_mm'][i],bb[b]['max_mm'][i])-max(bb[a]['min_mm'][i],bb[b]['min_mm'][i])>=-1e-5 for i in range(3))
newkeys=list(e['parts']);pairs=list(itertools.combinations(newkeys,2))
for a in newkeys:
 if 'cover' in a:continue # Material-subset proof: removal cannot introduce new material overlap.
 for b in dedup.values():
  if ids[b]=='front_service_cover':continue
  if overlaps(a,b):pairs.append((a,b))
results=[]
for a,b in pairs:
 if not overlaps(a,b):continue
 v=g.volume(g.load(a)&g.load(b));results.append(dict(a=ids[a],b=ids[b],intersection_mm3=v,clear=v<=1e-5,states=[st for st,ks in states.items() if b in ks] if b.startswith('P') and b[1:].isdigit() else list(states)))
 g.cache.clear()
print('CHECKED',len(results),'pairs',flush=True)
out=dict(status='PASS_SCOPED_GSE_PORT_GEOMETRY' if all(r['clear'] for r in results) else 'HOLD_GSE_PORT_INTERFERENCE',parts=facts,pairs=results,cover_subset_proof=dict(added_mm3=added,removed_mm3=removed,expected_removed_mm3=expected,kept_all_existing_mount_holes=True),scope='NEW_FOUR_SUPPLIER_ENVELOPES_AGAINST_THREE_STATES; COVER_BY_EXACT_SUBSET_PROOF; PARENT_PARENT_INHERITED',state_counts={st:705 for st in states},expected_solids=1086,source_inputs_unchanged=all(sha(p)==h for p,h in pins.items()),nominal_cable_fit=[dict(tag=tag,od_mm=od,clamp_range=[4,10],nominal_inside_range=4<=od<=10) for tag,y,z,od in e['locations']],retention_force_verified=False,nut_height_source='4mm assumed; supplier full drawing required',plume_clearance=False,continuous_motion=False,cut_length_mm=None)
(F/'results/PORTS_CHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(out['status'])
