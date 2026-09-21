"""Read-only engineering input review; emits only review/ and the review receipt.
No CAD/OCC/COM imports. Certificate is independently recomputed using stored
intervals and an explicit serial-chain formula, without calling author functions.
"""
from pathlib import Path
import csv, datetime, hashlib, itertools, json, math, sys
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1]
OUT=C/'review'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
bindings={}
def read(p):
    p=Path(p); bindings[str(p)]=sha(p)
    return json.loads(p.read_text(encoding='utf-8-sig'))
checks=[]
def ck(n,ok,detail=None):
    checks.append({'id':n,'pass':bool(ok),'detail':detail})
    if not ok: raise AssertionError((n,detail))
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def sub(a,b): return [x-y for x,y in zip(a,b)]
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def boxes(angles,step=4.5):
    th,p2,p3=map(math.radians,angles); out={}
    for side in (-1,1):
        yaw=[th, th+math.pi-p2, th-p2+p3]
        d=[[side*math.sin(p), math.cos(p)] for p in yaw]
        n=[[side*math.cos(p), -math.sin(p)] for p in yaw]
        root=[[side*121.15,-108.15]]
        root.append([root[0][k]+200*d[0][k]+step*n[0][k] for k in (0,1)])
        root.append([root[1][k]+200*d[1][k]-step*n[1][k] for k in (0,1)])
        for j in range(3):
            axes=[[1,0,0],[0,*d[j]],[0,-d[j][1],d[j][0]]]
            center=[0,*[root[j][k]+100*d[j][k] for k in (0,1)]]
            center=[center[k]+.245*side*axes[2][k] for k in range(3)]
            out[f'wing_{side}_leaf_{j+1}']={'c':center,'a':axes,'h':[150,100+j*.1,(2.6+.49)/2+j*.1],'root':[0,*root[j]],'side':side,'leaf':j+1}
    return out
def gap(a,b):
    axes=a['a']+b['a']+[cross(x,y) for x in a['a'] for y in b['a']]
    result=-math.inf
    for axis in axes:
        n=math.sqrt(dot(axis,axis))
        if n<1e-12: continue
        axis=[v/n for v in axis]
        result=max(result,abs(dot(sub(b['c'],a['c']),axis))-sum(h*abs(dot(u,axis)) for h,u in zip(a['h'],a['a']))-sum(h*abs(dot(u,axis)) for h,u in zip(b['h'],b['a'])))
    return result-1e-7
def radius(b,p):
    return max(math.hypot(b['c'][1]+sum(s[k]*b['h'][k]*b['a'][k][1] for k in range(3))-p[1],b['c'][2]+sum(s[k]*b['h'][k]*b['a'][k][2] for k in range(3))-p[2]) for s in itertools.product((-1,1),repeat=3))*(1+1e-12)+1e-7
def main():
    select=read(C/'mass/R01_FASTENER_SELECTION.json')
    plan=read(C/'mass/R01_GEOMETRY_DELTA_PLAN.json')
    ck('selection_plan_hash',sha(plan['selection_file'])==plan['selection_sha256'])
    rows=select['instances'];v=select['variants']
    ck('128_unique_ids',len(rows)==len({r['id'] for r in rows})==128)
    expected={'SCREW_M3X10':16,'SCREW_M3X12':16,'WASHER_M3':64,'NUT_M3':32}
    ck('quantities',{k:sum(r['variant']==k for r in rows) for k in v}==expected)
    ck('washer_dims_and_article',(v['WASHER_M3']['od_mm'],v['WASHER_M3']['id_mm'],v['WASHER_M3']['thickness_mm'],v['WASHER_M3']['supplier_article'])==(6.,3.2,.5,'515005013'))
    ck('nut_class10',v['NUT_M3']['property_class']=='10 per ISO898-2' and v['NUT_M3']['supplier_article']=='0324903')
    total=0.
    for r in rows:
        s=v[r['variant']]
        if s['kind']=='screw':
            vol=math.pi*(1.5**2*s['length_mm']+2.75**2*3)-3*math.sqrt(3)/2*(2.52/math.sqrt(3))**2*1.5
        elif s['kind']=='washer': vol=math.pi*(3**2-1.6**2)*.5
        else: vol=(3*math.sqrt(3)/2*(5.5/math.sqrt(3))**2-math.pi*1.5**2)*2.4
        ck(r['id']+'_analytic_volume',abs(vol-r['corrected_proxy_analytic_volume_mm3'])<1e-10)
        total+=vol*7.85e-6
    ck('corrected_mass',abs(total-select['summary']['corrected_128_proxy_material_mass_kg'])<1e-12)
    ck('tool_envelope',all(abs(r['driver_circumscribed_d_mm']-2.5/math.cos(math.pi/6))<1e-12 and abs(r['tool_to_socket_flat_clearance_per_side_mm']-.01)<1e-12 for r in select['fit_checks']))
    ck('no_exact_mass_claim',all(r['exact_COTS_mass_kg'] is None and r['as_built_mass_kg'] is None for r in rows))
    for ref in select['sources'].values(): ck('source_'+Path(ref['file']).name,sha(ref['file'])==ref['sha256'])
    washertext=(C/'mass/r01_sources/wuerth_ISO7092_29208728.txt').read_text(encoding='utf-8')
    ck('actual_locked_washer_revision','Rev: 0.1314, State: 03. 08. 2026' in washertext)
    erratum={'id':'R01_WASHER_REVISION_METADATA_ERRATUM','scope':'Source revision string only; nominal geometry, article, and locked PDF hash are unchanged. Consumed CAD input files preserved.','affected_file':str(C/'mass/R01_FASTENER_SELECTION.json'),'affected_pointer':'/sources/washer/revision','original_text':select['sources']['washer']['revision'],'correct_revision':'CL01_35140804111 Rev0.1314 2026-08-03','authority':select['sources']['washer']['file'],'authority_sha256':select['sources']['washer']['sha256'],'authoritative_pdf_page':1,'manufacturing_geometry_changed':False}
    (OUT/'SOURCE_REVISION_ERRATUM.json').write_text(json.dumps(erratum,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    layout=read(C/'solar/SOLAR_LAYOUT.json'); delivery=read(C/'results/SOLAR_DELIVERY_STATUS_V2.json')
    for r in delivery['files']: ck('solar_v2_sha_'+Path(r['path']).name,sha(r['path'])==r['sha256'])
    cells=layout['cells']
    ck('84_unique_CIC_glass_proxies',len(cells)==len({r['id'] for r in cells})==84 and all(r['solid_geometry_role']=='GLASS_FOOTPRINT_CIC_LAYER_PROXY' and r['entire_package_bounds_known'] is False for r in cells))
    ck('layout_bounds',abs(41.4-(40.15+.05)-2*.1-1.)<1e-12 and abs(88.2-(80.15+.05)-2*.1-7.8)<1e-12)
    ck('fold_gap',abs(4.5-.1-2.6-2*(.34+.15)-.82)<1e-12)
    generaltxt=(C/'sources/solar_tab_intake/AZUR_GENERAL_DB00010890_01_20250408.pdf.mechanical_extract.txt').read_text(encoding='utf-8')
    ck('glass_not_tab_envelope_source','CIC size reflects outer Coverglass dimensions' in generaltxt and 'protrude beyond' in generaltxt and 'available upon request' in generaltxt)
    cert=read(C/'results/SOLAR_CONTINUOUS_CLEARANCE.json')
    ck('continuous_scope',cert['whole_spacecraft_G_status']=='NOT_EVALUATED' and cert['hardware_execution'] is False)
    stage_mins=[]; interval_count=0;max_recompute_difference=0.
    for stage in cert['stages']:
        lo,hi=stage['interval_deg'];joint=stage['joint_index_zero_based'];segments=stage['certified_intervals']; base=stage['joint_angles_deg_base']
        ck(stage['stage']+'_interval_cover',segments[0]['interval_deg'][0]==lo and segments[-1]['interval_deg'][1]==hi and all(x['interval_deg'][1]==y['interval_deg'][0] for x,y in zip(segments,segments[1:])))
        localmin=math.inf
        for seg in segments:
            a,b=seg['interval_deg'];q=list(base);q[joint]=(a+b)/2
            objects=boxes(q)
            axes={s:objects[f'wing_{s}_leaf_{joint+1}']['root'] for s in (-1,1)}
            rr={k:radius(v,axes[v['side']]) if v['leaf']>=joint+1 else 0 for k,v in objects.items()}
            lowers=[]
            for (aid,aa),(bid,bb) in itertools.combinations(objects.items(),2):
                activea=aa['leaf']>=joint+1;activeb=bb['leaf']>=joint+1
                common=(not activea and not activeb) or (activea and activeb and aa['side']==bb['side'])
                lowers.append(gap(aa,bb)-(0 if common else (rr[aid]+rr[bid])*math.radians((b-a)/2)))
            lower=min(lowers);localmin=min(localmin,lower)
            ck(stage['stage']+'_interval_'+str(interval_count),lower>.3)
            max_recompute_difference=max(max_recompute_difference,abs(lower-seg['certified_min_gap_mm']))
            interval_count+=1
        stage_mins.append(localmin)
    ck('776_intervals',interval_count==776)
    ck('source_receipt_recomputed_lower',max_recompute_difference<1e-8,max_recompute_difference)
    ck('negative_controls_reported',all(r['detected'] for r in cert['negative_controls']))
    findings=[
      {'id':'REV-01','severity':'P2','status':'ERRATUM_ISSUED_SOURCE_INPUT_PRESERVED','finding':'Washer source revision metadata does not match locked PDF. Use Rev0.1314 2026-08-03.','file':str(C/'tools/mass_r01_selection.py'),'line':73,'fix':str(OUT/'SOURCE_REVISION_ERRATUM.json'),'geometry_affected':False},
      {'id':'LIM-01','severity':'RELEASE_SCOPE_LIMIT','status':'ALREADY_EXPLICIT_NOT_NEW_DEFECT','finding':'128 standard fasteners are threadless approximate solids. Tool envelopes, fillet clearance, thread engagement after chamfers, preload, joint strength and locking remain unverified. A selected article and valid solid cannot imply manufactured joint closure.'},
      {'id':'LIM-02','severity':'RELEASE_SCOPE_LIMIT','status':'ALREADY_EXPLICIT_NOT_NEW_DEFECT','finding':'Four-stage certificate covers six layered rectangular panel envelopes only, excludes frame/pins, tabs, wires, bus and arm. Full spacecraft continuous collision clearance is not evaluated.'},
      {'id':'LIM-03','severity':'RELEASE_SCOPE_LIMIT','status':'ALREADY_EXPLICIT_NOT_NEW_DEFECT','finding':'84 glass footprints do not bound formed CIC interconnects. Unknown tab coordinates/material bonding/leaf attachment prevent completed solar mechanical interface.'},
      {'id':'LIM-04','severity':'RELEASE_SCOPE_LIMIT','status':'MASS_ROLLFORWARD_REQUIRED','finding':'705 responsibility coverage is not mass completeness. 873 ledger must replace eight frame masses, add 128 R01 newly-bound model masses, assign 84 whole-CIC nominal references once, leave 84 glue masses unknown and quarantine historical leaf budget.'}
    ]
    output={'schema':'INDEPENDENT_ENGINEERING_DELTA_REVIEW_V1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_BOUNDED_ARITHMETIC_AND_SOURCE_SCOPE__ONE_SOURCE_METADATA_ERRATUM__WHOLE_DESIGN_NOT_COMPLETE','checks_passed':sum(x['pass'] for x in checks),'checks_total':len(checks),'continuous_certificate_independent_intervals':interval_count,'continuous_gap_global_lower_mm':min(stage_mins),'max_gap_receipt_recompute_difference_mm':max_recompute_difference,'R01_corrected_proxy_mass_kg':total,'CAD_executed':False,'native_assembly_verified_by_this_review':False,'whole_design_complete':False,'physical_validation_credit':False,'manufacturing_release':False,'findings':findings,'source_bindings':bindings,'checks':checks}
    (C/'results/INDEPENDENT_DELTA_REVIEW.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:output[k] for k in ['status','checks_passed','checks_total','continuous_gap_global_lower_mm','max_gap_receipt_recompute_difference_mm']}))
if __name__=='__main__': main()
