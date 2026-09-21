"""Emit lightweight delivery index for the873 ledger; no CAD import."""
from pathlib import Path
import argparse, datetime, hashlib, json
C=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frame-equivalence-receipt',default=str(C/'results/NATIVE_DELTA_FRAME_EQUIVALENCE.json'))
    ap.add_argument('--native-cold-receipt',action='append',default=[])
    args=ap.parse_args()
    path=C/'review/MASS_ASSIGNMENT_873.json'
    d=json.loads(path.read_text(encoding='utf-8'))
    eq=None
    if args.frame_equivalence_receipt and Path(args.frame_equivalence_receipt).exists():
        p=Path(args.frame_equivalence_receipt)
        obj=json.loads(p.read_text(encoding='utf-8'))
        expected={x['id'] for x in d['delta_accounting']['frame_deltas']}
        assert len(obj['rows'])==8 and {x['id'] for x in obj['rows']}==expected
        assert obj['status']=='PASS_8_NATIVE_ROUNDTRIPS_SAME_KERNEL_GEOMETRY_EQUIVALENCE'
        for row in obj['rows']:
            assert row['pass_geometry_equivalence'] is True
            assert row['relative_volume_error']<=obj['relative_volume_tolerance']<=1e-7
            assert row['original_minus_native_solid_count']==row['native_minus_original_solid_count']==0
            for k in ('source','native','native_roundtrip','old_source'):
                assert sha(row[k])==row[k+'_sha256'], (row['id'],k)
        eq={'path':str(p),'sha256':sha(p),'receipt_status':obj.get('status'),
            'eight_id_and_32_file_sha_bindings_checked':True,'geometry_equivalence_at_kernel_tolerance':True,
            'native_GetMassProperties_scalar_equivalence':obj['native_GetMassProperties_scalar_equivalence'],
            'adaptive_integral_diagnostic_new_eight_mass_kg':obj['new_mass_kg'],
            'adaptive_integral_diagnostic_old_eight_mass_kg':obj['old_mass_kg'],
            'adaptive_integral_diagnostic_matched_delta_mass_kg':obj['matched_algorithm_delta_mass_kg'],
            'retained_default_method_matched_delta_mass_kg':d['delta_accounting']['solar_eight_frame_replacement_delta_kg'],
            'method_delta_difference_kg':d['delta_accounting']['solar_eight_frame_replacement_delta_kg']-obj['matched_algorithm_delta_mass_kg'],
            'adopted_for_mass_values':False,'role':'Geometry round-trip equivalence and volume-algorithm diagnostic. Does not turn this ledger into SW mass values.'}
    cold=[]
    for name in args.native_cold_receipt:
        p=Path(name);obj=json.loads(p.read_text(encoding='utf-8'))
        cold.append({'path':str(p),'sha256':sha(p),'receipt_status':obj.get('status'),'state':obj.get('state')})
    result={'schema':'MASS_ROLLFORWARD_873_DELIVERY_INDEX_V1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'status':'PARTIAL_MODEL_MASS_LEDGER_READY__FULL_MASS_UNKNOWN',
      'ledger':{'path':str(path),'sha256':sha(path)},
      'files':[{'path':str(C/f),'sha256':sha(C/f)} for f in ['review/MASS_ASSIGNMENT_873.json','review/MASS_ASSIGNMENT_873.csv','review/MASS_OWNER_SUMMARY_873.csv','review/REVIEW_AND_MASS_ROLLFORWARD_ZH.md']],
      'summary':{k:d[k] for k in ['coverage','owner_count','unresolved_owner_count','candidate_material_subset_kg','B601_whole_vendor_reference_kg','CIC84_whole_vendor_average_weight_reference_kg','full_spacecraft_mass_kg','COM_S_mm','inertia_C_S_kg_mm2','checks_passed','checks_total']},
      'volume_algorithm_identity':d['frame_volume_algorithm'],'frame_equivalence_receipt':eq,
      'frame_equivalence_binding_status':'RECEIPT_BOUND_FOR_GEOMETRY_ONLY' if eq else 'PENDING_FINAL_EIGHT_FRAME_RECEIPT',
      'native_cold_receipts':cold,'native_cold_receipt_binding_completed':len(cold)==3 and {x['state'] for x in cold}=={'service','parking','released'},
      'native_cold_all_pass':len(cold)==3 and {x['state'] for x in cold}=={'service','parking','released'} and all(str(x['receipt_status']).startswith('PASS') for x in cold),
      'native_cold_status_note':'Only explicit passed CAD writer receipts can demonstrate successful native cold-open. This index does not grant it from ledger coverage.',
      'ledger_mass_from_native_SW':False,'full_mechatronic_design_complete':False,'manufacturing_release':False}
    out=C/'results/MASS_ROLLFORWARD_873.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(str(out))
if __name__=='__main__':main()
