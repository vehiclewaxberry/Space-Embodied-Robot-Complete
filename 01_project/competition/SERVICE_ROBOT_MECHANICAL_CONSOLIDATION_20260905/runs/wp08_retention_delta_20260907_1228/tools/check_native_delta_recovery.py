"""Independent metadata/vector replay with exact IDs and unchanged-neighbour invariants."""
from pathlib import Path
import json,math,copy,hashlib,sys,argparse,datetime
R=Path(__file__).resolve().parents[1]
BASIS=[[0.,0.,0.],[10.,0.,0.],[0.,10.,0.],[0.,0.,10.]]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def norm(p):return str(Path(p).resolve()).casefold()
def t16(T):return [T[i][j] for j in range(3) for i in range(3)]+[T[i][3]/1000 for i in range(3)]+[1.,0.,0.,0.]
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def expected_rows(info):
    prior=read(info['parent_receipt_path'])
    assert sha(info['parent_receipt_path'])==info['parent_receipt_sha256']
    visible={r['id']:r['visible'] for r in prior['cold_inspection']['components']}
    rows=copy.deepcopy(info['instances'])
    for row in rows:row['expected_visible']=visible.get(row['id'],1)
    return rows
def check_rows(observed,expected):
    old={r['id']:r for r in observed};want={r['id']:r for r in expected}
    coverage=len(old)==len(observed)==len(expected)==len(want) and set(old)==set(want)
    results=[]
    for ident in sorted(set(old)&set(want)):
        a,e=old[ident],want[ident];v=a.get('transform_sw16',[]);points=a.get('world_basis_points_mm',[])
        fv=len(v)==16 and all(finite(x) for x in v)
        fp=len(points)==4 and all(isinstance(p,(list,tuple)) and len(p)==3 and all(finite(x) for x in p) for p in points)
        tm=max(abs(x-y) for x,y in zip(v,t16(e['T_S_local']))) if fv else None
        wanted=[[sum(e['T_S_local'][i][j]*p[j] for j in range(3))+e['T_S_local'][i][3] for i in range(3)] for p in BASIS]
        direct=max(abs(points[k][i]-wanted[k][i]) for k in range(4) for i in range(3)) if fp else None
        reconstructed=max(abs(sum(v[3*j+i]*BASIS[k][j]*v[12] for j in range(3))+1000*v[9+i]-wanted[k][i]) for k in range(4) for i in range(3)) if fv else None
        tests=dict(path=norm(a.get('path',''))==norm(e['native_path']),source_hash=a.get('sha256')==e['native_sha256'],fixed=a.get('fixed') is True,visibility_preserved='expected_visible' in e and a.get('visible')==e['expected_visible'],solids=a.get('solid_count')==e['expected_solids'],sheets=a.get('sheet_count')==0,transform=tm is not None and tm<=1e-8,direct_vectors=direct is not None and direct<=1e-5,matrix_vectors=reconstructed is not None and reconstructed<=1e-5)
        results.append(dict(id=ident,status='PASS' if all(tests.values()) else 'FAIL',checks=tests,transform_error=tm,direct_vector_error_mm=direct,matrix_vector_error_mm=reconstructed))
    total=sum(r.get('solid_count',0) for r in observed);deps=len({norm(r.get('path','')) for r in observed})
    ok=coverage and total==sum(r['expected_solids'] for r in expected) and deps==len({norm(r['native_path']) for r in expected}) and all(r['status']=='PASS' for r in results)
    return dict(status='PASS' if ok else 'FAIL',coverage=coverage,component_count=len(observed),solid_count=total,unique_dependencies=deps,results=results)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('state',choices=['service','parking','released']);a=ap.parse_args()
    out=R/f'results/NATIVE_CHECK_{a.state.upper()}.json';assert not out.exists()
    mp=R/'results/INTEGRATION_MANIFEST.json';m=read(mp);info=m['states'][a.state]
    rp=R/f'results/NATIVE_{a.state.upper()}.json'
    if a.state=='parking':rp=R/'results/NATIVE_PARKING_RECOVERY_V2.json'
    receipt=read(rp)
    if a.state=='parking':
        assert receipt['save_api_acknowledgement']=='UNKNOWN_WORKER_TERMINATED_WHILE_SOLIDWORKS_COMPLETED_SAVE' and receipt['prior_body_measurement_credit']==0
        assert sha(receipt['recovery_basis']['interrupted_receipt'])==receipt['recovery_basis']['interrupted_sha256'] and read(receipt['recovery_basis']['guard_path'])['status']=='AVAILABLE_MEMORY_GUARD'
    assert receipt['status']=='PASS_NATIVE_FIXED_POSE_DELTA_COLD_REOPEN' and receipt['inputs_unchanged']
    assert receipt['manifest_sha256']==sha(mp) and receipt['cold_inspection_native_sha256']==receipt['native_save']['sha256']==sha(receipt['native_save']['path'])
    pins=dict(receipt['input_sha256_before']);pins[str(mp)]=sha(mp);pins[str(rp)]=sha(rp);pins[receipt['native_save']['path']]=receipt['native_save']['sha256'];pins[str(Path(__file__))]=sha(__file__)
    for p,d in pins.items():assert sha(p)==d,('Pin changed',p)
    expected=expected_rows(info)
    observed=receipt['cold_inspection']['components'];checked=check_rows(observed,expected);assert checked['status']=='PASS'
    baseline=read(m['base_manifest'])['states'][a.state]['instances'];old={r['id']:r for r in baseline};current={r['id']:r for r in info['instances']}
    replaced=set(info['replaced_ids']);added=set(info['added_ids']);retained=set(old)-replaced
    assert replaced=={f'hold_fold_mast_{k}' for k in (0,1)}|{f'hold_shoe_guide_{k}_{x}' for k in (0,1) for x in (-10,10)}
    assert set(current)==set(old)|added and len(added)==28 and not added&set(old)
    assert all(current[i]['T_S_local']==old[i]['T_S_local'] and current[i]['native_path']==old[i]['native_path'] and current[i]['native_sha256']==old[i]['native_sha256'] for i in retained)
    assert all(sum(r['id']==f'hold_saddle_{k}' for r in observed)==1 for k in (0,1))
    faults=[];index=next(i for i,r in enumerate(observed) if r['id']=='hold_fold_mast_0')
    for kind in ('old_part_substitution','station_shift','mm_m_swap','missing_added_part','duplicate_saddle','missing_actual_vector','unexpected_unfix','solid_count_tamper','hidden_changed_part'):
        test=copy.deepcopy(observed)
        if kind=='old_part_substitution':test[index]['path']=old['hold_fold_mast_0']['native_path'];test[index]['sha256']=old['hold_fold_mast_0']['native_sha256']
        elif kind=='station_shift':test[index]['transform_sw16'][9]+=.001
        elif kind=='mm_m_swap':test[index]['transform_sw16'][11]*=1000
        elif kind=='missing_added_part':test=[r for r in test if r['id']!=next(iter(added))]
        elif kind=='duplicate_saddle':test.append(copy.deepcopy(next(r for r in test if r['id']=='hold_saddle_0')))
        elif kind=='missing_actual_vector':test[index].pop('world_basis_points_mm')
        elif kind=='unexpected_unfix':test[index]['fixed']=False
        elif kind=='solid_count_tamper':test[index]['solid_count']+=1
        else:test[index]['visible']=0
        result=check_rows(test,expected);assert result['status']=='FAIL',kind
        faults.append(dict(name=kind,status='PASS_REJECTED',scope='memory-only observation fault'))
    assert all(sha(p)==d for p,d in pins.items())
    data=dict(schema='WP08_INDEPENDENT_NATIVE_CHECK',status='PASS_SCOPED_NATIVE_DELTA_AND_EXACT_MEMBERSHIP',state=a.state,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),native_path=receipt['native_save']['path'],native_sha256=receipt['native_save']['sha256'],manifest_sha256=sha(mp),checks=checked,retained_instances_verified=len(retained),replaced_instances_verified=len(replaced),added_instances_verified=len(added),context_retained_once=True,negative_controls=faults,input_sha256=pins,inputs_unchanged=True,full_STEP_verified=False,global_geometry_equivalence=False,continuous_motion_verified=False,engineering_release=False)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:data[k] for k in ('status','state','retained_instances_verified','replaced_instances_verified','added_instances_verified')},ensure_ascii=False))
if __name__=='__main__':main()
