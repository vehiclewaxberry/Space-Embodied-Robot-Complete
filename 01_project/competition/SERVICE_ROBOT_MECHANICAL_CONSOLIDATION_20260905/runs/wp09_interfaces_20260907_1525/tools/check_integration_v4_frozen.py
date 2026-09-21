"""Independent cold STEP delta check; no design-generator import."""
from pathlib import Path
import json,hashlib,sys,importlib.util,math,itertools,argparse
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
REPLACE=['lower_equipment_deck','upper_equipment_deck','adapter_power_distribution','equipment_power_distribution','thermal_interface_power_distribution','connector_power_distribution']
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
    c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V4.json').read_text());e=json.loads((R/'results/EMISSION_V4.json').read_text());pins=dict(c['source_inputs'])
    assert all(sha(p)==h for p,h in pins.items())
    spec=importlib.util.spec_from_file_location('independent_wp09_geometry',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    job={'parts':{},'tolerances':c['acceptance']};bb={};roles={};dedup={};statekeys={};ident={}
    for k,row in e['parts'].items():
        key='NEW:'+k;job['parts'][key]={'path':row['path'],'sha256':row['sha256'],'T_S_local':I};bb[key]=row['bbox_mm'];roles[key]=row['representation_role'];ident[key]=k
    for st,record in c['states'].items():
        statekeys[st]=[]
        for row in record['instances']:
            if row['id'] in REPLACE:continue
            sig=(row['source_sha256'],json.dumps(row['T_S_local']),row['id'])
            if sig not in dedup:
                key='OLD:'+str(len(dedup))+':'+row['id'];dedup[sig]=key
                job['parts'][key]={'path':row['step_path'],'sha256':row['source_sha256'],'T_S_local':row['T_S_local']};bb[key]=row['bounds_mm'];roles[key]=row['representation_role'];ident[key]=row['id']
            statekeys[st].append(dedup[sig])
    g=m.Geometry(job,pins);rows=[];new=list(e['parts']);facts={}
    for k in new:
        key='NEW:'+k;s=g.load(key);f=g.facts(s);ref=e['parts'][k]
        err=max(abs(f['bbox_mm'][t][i]-ref['bbox_mm'][t][i]) for t in ['min_mm','max_mm'] for i in range(3))
        ok=f['shape_valid'] and f['solid_count']==1 and abs(f['volume_mm3']-ref['volume_mm3'])<=c['acceptance']['volume_mm3'] and err<=c['acceptance']['linear_mm']
        facts[k]=dict(**f,bbox_max_delta_mm=err,ok=ok);assert ok, k
    def overlap(a,b):return all(min(bb[a]['max_mm'][i],bb[b]['max_mm'][i])-max(bb[a]['min_mm'][i],bb[b]['min_mm'][i])>=-1e-5 for i in range(3))
    pairs=[];nk=['NEW:'+k for k in new]
    for a,b in itertools.combinations(nk,2):
        if overlap(a,b):pairs.append((a,b))
    for b in dedup.values():
        for a in nk:
            if overlap(a,b):pairs.append((a,b))
    def intent(a,b):
        ka,kb=ident[a],ident[b]
        # Only exact, same-fastener proxy thread engagements are permitted volume overlaps.
        for prefix in ['MIPS_FOOT_','P60_HOST_']:
            if ka.startswith(prefix) and kb.startswith(prefix) and ka.rsplit('_',1)[0]==kb.rsplit('_',1)[0] and {ka.rsplit('_',1)[1],kb.rsplit('_',1)[1]}=={'SCREW','NUT'}:return 'DECLARED_SIMPLIFIED_THREAD_ENGAGEMENT'
        for n in range(4):
            for tag in ['TN','BN']:
                if {ka,kb}=={f'P60_HOST_{n}_ROD',f'P60_HOST_{n}_{tag}'}:return 'DECLARED_SIMPLIFIED_THREAD_ENGAGEMENT'
        for st in c['clamp_stations']:
            for n in range(2):
                rod=f'TIEROD_{st["id"]}_{n}'
                for tag in ['TN','BN']:
                    if {ka,kb}=={rod,f'CLAMP_{st["id"]}_{n}_{tag}'}:return 'DECLARED_SIMPLIFIED_THREAD_ENGAGEMENT'
        # Conservative original harness budget retained, clashes still reported separately.
        if (a.startswith('OLD:') and roles[a]=='FUNCTIONAL_ENVELOPE') or (b.startswith('OLD:') and roles[b]=='FUNCTIONAL_ENVELOPE'):return 'EXISTING_FUNCTIONAL_RESERVATION_OVERLAP_REQUIRES_RECONCILIATION'
        return None
    for n,(a,b) in enumerate(pairs):
        try:
            sa=g.load(a);sb=g.load(b);common=sa & sb;v=g.volume(common)
            rec=dict(a=ident[a],b=ident[b],a_key=a,b_key=b,intersection_volume_mm3=v,declared_relation=intent(a,b),classification='CLEAR' if v<=c['acceptance']['volume_mm3'] else 'OVERLAP',states=[st for st,ks in statekeys.items() if b in ks] if b.startswith('OLD:') else list(c['states']))
        except Exception as ex:rec=dict(a=ident[a],b=ident[b],classification='ERROR',error=str(ex))
        rows.append(rec)
        if n%25==0:print('PAIR',n,len(pairs),flush=True)
    # Exact scalar curve check against independently evaluated 90-degree fillet formula.
    routechecks={}
    for k,p in c['routes'].items():
        pts=p['waypoints'];poly=sum(math.dist(a,b) for a,b in zip(pts,pts[1:]));nom=poly-4*p['radius_mm']+math.pi*p['radius_mm'];actual=e['routes'][k]['actual_curve_length_mm']
        routechecks[k]=dict(polyline_mm=poly,expected_curve_mm=nom,actual_curve_mm=actual,delta_mm=actual-nom,ok=abs(actual-nom)<=1e-5)
    # Two options only: exact deck obstruction for A; front access prism for B is not a plume cone.
    def box(lo,hi):return g.Solid.make_box(*(hi[i]-lo[i] for i in range(3)),g.Plane(origin=lo))
    old={r['id']:r for r in c['states']['service']['instances']}
    optiontests=[]
    for opt,probe,targets in [('A_Z_FRONT',box([30,-44.5008,-95.65],[119.0016,44.5008,-105.65]) if False else box([30,-44.5008,-125.65],[119.0016,44.5008,-95.65]),['lower_equipment_deck']),('B_X_FRONT',box([170,-44.5008,-94.15],[220,44.5008,-5.1484]),['RB_end_frame_1'])]:
        for target in targets:
            row=old[target];job['parts']['OPT']=dict(path=row['step_path'],sha256=row['source_sha256'],T_S_local=row['T_S_local']);g.cache.pop('OPT',None)
            v=g.volume(probe & g.load('OPT'));optiontests.append(dict(option=opt,target=target,intersection_volume_mm3=v,clear=v<=1e-5,qualification='DESIGN_SERVICE_PRISM_NOT_PLUME_OR_OEM_KEEP_OUT'))
    unapproved=[r for r in rows if r['classification']=='ERROR' or (r['classification']=='OVERLAP' and r.get('declared_relation') is None)]
    functional=[r for r in rows if r.get('classification')=='OVERLAP' and r.get('declared_relation')=='EXISTING_FUNCTIONAL_RESERVATION_OVERLAP_REQUIRES_RECONCILIATION']
    result=dict(status='DELTA_GEOMETRY_CLEAR' if not unapproved and not functional else 'DELTA_GEOMETRY_HOLD',part_cold_facts=facts,pair_count=len(rows),broadphase_skipped_nonoverlapping_pairs=True,pairs=rows,unapproved=unapproved,functional_conflicts=functional,route_checks=routechecks,layout_options=optiontests,source_pin_count=len(pins),all_source_pins_unchanged=all(sha(p)==h for p,h in pins.items()),removed_parent_ids=REPLACE,full_parent_parent_check=False,continuous_motion_clearance=False,plume_clearance=False)
    write(R/'results/INTEGRATION_CHECK_V4.json',result)
    print(json.dumps(dict(status=result['status'],pairs=len(rows),unapproved=len(unapproved),functional_conflicts=len(functional),layout_options=optiontests)),flush=True)
if __name__=='__main__':main()
