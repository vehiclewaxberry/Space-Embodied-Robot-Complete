"""Roll forward existing705 mass responsibility into source-bound873 design rows.
Reads actual STEP build receipts, never CAD. Native cold-open proof is a separate
receipt and is not implied by this inventory. Parent705 ledger remains byte exact.
"""
from pathlib import Path
from collections import Counter
import copy, csv, datetime, hashlib, json, math, sys
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1]; OUT=C/'review'; bindings={};checks=[]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source_sha(r): return r.get('source_sha256') or r['source_step']['sha256']
def read(p):
    p=Path(p);bindings[str(p)]=sha(p)
    return json.loads(p.read_text(encoding='utf-8-sig'))
def ck(n,ok,detail=None):
    checks.append(dict(id=n,pass_=bool(ok),detail=detail))
    if not ok: raise AssertionError((n,detail))
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
    basepath=C/'mass/MASS_ASSIGNMENT_705.json'; base=read(basepath); old={r['id']:r for r in base['instances']}
    native_plan_path=C/'results/NATIVE_DELTA_INPUTS.json';nplan=read(native_plan_path)
    solarpath=C/'results/SOLAR_DELTA_STEP_BUILD.json';solar=read(solarpath)
    rpath=C/'mass/r01_geometry_delta/BUILD_RECEIPT.json';r01=read(rpath)
    selection=read(C/'mass/R01_FASTENER_SELECTION.json')
    erratum=read(OUT/'SOURCE_REVISION_ERRATUM.json')
    ck('R01_actual128_not_canonical',r01['CAD_executed'] is True and r01['source_frame_leaves']==128 and r01['canonical_forms_not_added_to_mass'] is True)
    rparts={r['id']:r for r in r01['rows'] if r['scope'].startswith('SOURCE_FRAME')}
    ck('R01128_identity_set',set(rparts)=={r['id'] for r in old.values() if r['responsibility_owner']=='R01_EQUIPMENT_FASTENER_KIT'})
    frames={k:r for k,r in solar['emitted_parts'].items() if k.startswith('wing_edge_frame_')}
    ck('eight_replacement_frames',len(frames)==8)
    for k,p in {**rparts,**frames}.items():
        path=p.get('step_path',p.get('path'))
        ck(k+'_actual_step_hash',sha(path)==p['sha256'])
        ck(k+'_volume_positive',p['volume_mm3']>0)
    canonical_ids={r['id'] for r in r01['rows'] if r['scope']=='REFERENCE_FORM_NOT_CURRENT_ASSEMBLY_INSTANCE'}
    state_indexes={s:{r['id']:r for r in st['rows']} for s,st in nplan['states'].items()}
    ck('three_states_bound',set(state_indexes)=={'service','parking','released'})
    ids=set(state_indexes['service'])
    ck('873_identical_per_state',len(ids)==873 and all(set(v)==ids for v in state_indexes.values()))
    ck('retained705_identity',set(old)<=ids and not (canonical_ids & ids))
    added=ids-set(old);cicids={x for x in added if x.endswith('_CIC')};bondids={x for x in added if x.endswith('_BOND')}
    ck('168_only_new_layers',len(added)==168 and len(cicids)==84 and len(bondids)==84 and cicids|bondids==added)
    rows=[];frame_deltas=[]
    for ident in sorted(ids):
        current={s:v[ident] for s,v in state_indexes.items()};row=current['service'];prior=old.get(ident)
        out=dict(id=ident,responsibility_owner=prior['responsibility_owner'] if prior else 'SOLAR_CIC_WHOLE_VENDOR_REFERENCE' if ident in cicids else 'SOLAR_PANEL_BONDLINE',
          representation_role=row['representation_role'],physical_mass_applicable=prior['physical_mass_applicable'] if prior else True,
          accounting_basis=prior['mass_accounting_basis'] if prior else None,
          candidate_material_mass_kg=prior['candidate_material_mass_kg'] if prior else None,
          vendor_reference_mass_kg=None,as_built_mass_kg=None,
          source_bound_volume_mm3=prior['volume_mm3'] if prior else None,
          density_kg_mm3=prior['density_kg_mm3'] if prior else None,
          retained_legacy_planning_budget_kg=prior['legacy_planning_budget_kg'] if prior else None,
          legacy_budget_additive_to_numeric_mass=False,
          source_step_sha256_by_state={s:source_sha(r) for s,r in current.items()},
          native_import_plan=str(native_plan_path),native_cold_proof='SEPARATE_NATIVE_DELTA_COLD_RECEIPTS_NOT_IMPLIED',
          planned_T_local_to_S_mm_by_state={s:r['native_T_local_to_S'] for s,r in current.items()},
          full_component_COM_S_mm=None,full_component_inertia_kg_mm2=None,
          prior705_id=ident if prior else None,note='')
        if ident in rparts:
            p=rparts[ident];ck(ident+'_native_source_binding',all(source_sha(x)==p['sha256'] for x in current.values()))
            out.update(accounting_basis='SELECTED_STEEL_THREADLESS_STEP_VOLUME_MODEL',candidate_material_mass_kg=p['volume_mm3']*7.85e-6,source_bound_volume_mm3=p['volume_mm3'],density_kg_mm3=7.85e-6,actual_volume_receipt=str(rpath)+'#/rows/id='+ident,note='Replaces original proxy; original705 mass was null. Add this new bound model once, not only the geometric delta and not old+new. No supplier exact unit mass.')
        elif ident in frames:
            p=frames[ident];ck(ident+'_native_source_binding',all(source_sha(x)==p['sha256'] for x in current.values()))
            mass=p['volume_mm3']*2.7e-6
            ck(ident+'_retained_Al_nominal_density',prior['density_kg_mm3']==2.7e-6)
            out.update(accounting_basis='REBUILT_FRAME_STEP_AL2700_CANDIDATE_MODEL',candidate_material_mass_kg=mass,source_bound_volume_mm3=p['volume_mm3'],density_kg_mm3=2.7e-6,actual_volume_receipt=str(solarpath)+'#/emitted_parts/'+ident,volume_algorithm_identity='build123d shape.volume -> Solid.volume -> Shape.compute_mass -> BRepGProp.VolumeProperties_s(shape,properties), default overload without explicit Eps; emitted source shape, not SW GetMassProperties',volume_numerical_error_bound_mm3=None,native_mass_property_adopted=False,note='Remove old recorded source-volume model mass and insert rebuilt source-volume model mass; same default volume-method family and fixed candidate density retained. Numerical integration/model uncertainty is not a physical tolerance. No SW native mass or high-precision integral is substituted into this historical-method delta.')
            frame_deltas.append(dict(id=ident,old_volume_mm3=prior['volume_mm3'],new_volume_mm3=p['volume_mm3'],old_model_mass_kg=prior['candidate_material_mass_kg'],new_model_mass_kg=mass,difference_kg=mass-prior['candidate_material_mass_kg']))
        elif ident in cicids:
            ck(ident+'_scope',row['representation_role']=='GLASS_FOOTPRINT_CIC_LAYER_PROXY' and row['entire_package_bounds_known'] is False)
            out.update(accounting_basis='WHOLE_CIC_VENDOR_AVERAGE_WEIGHT_REFERENCE_NOT_GLASS_MASS',vendor_reference_mass_kg=.0036,source_bound_volume_mm3=solar['emitted_parts']['AZUR81442_CIC_GLASS_FOOTPRINT_LAYER']['volume_mm3'],note='One whole factory CIC reference assigned to this glass-footprint proxy. Covers original cell, coverglass, factory adhesive, bypass diode and factory interconnects; no second coverglass/internal-tab mass. Formed tabs geometry unknown. 3.6g is a datasheet average-weight reference, not measured unit mass or guaranteed as-built bound.')
        elif ident in bondids:
            out.update(accounting_basis='POSITIVE_MASS_UNKNOWN_SELECTED_MATERIAL_MISSING',source_bound_volume_mm3=solar['emitted_parts']['CIC_BONDLINE_0_10MM']['volume_mm3'],density_kg_mm3=None,candidate_material_mass_kg=None,note='External panel mounting adhesive, distinct from factory CIC internal bond. Finite positive volume; no density selected, mass remains null.')
        else:
            ck(ident+'_retained_step_hash',all(source_sha(current[s])==prior['source_step_sha256_by_state'][s] for s in current))
            if prior['responsibility_owner']=='SOLAR_CURRENT_LEAF_LAMINATES':
                out['note']='Current retained bare rectangular substrate proxy. Historic0.18kg/leaf budget has unbound inclusion of CIC; quarantine it as nonadditive history. Do not infer bare substrate mass or add budget to new CIC value.'
            elif prior['responsibility_owner']=='B601_DM_COMPLETE':
                out['note']='Covered by owner-level4.5kg whole arm reference counted once. No per-link apportionment, density or COM invented.'
        rows.append(out)
    material=math.fsum(r['candidate_material_mass_kg'] for r in rows if r['candidate_material_mass_kg'] is not None)
    nominal_cic=math.fsum(r['vendor_reference_mass_kg'] for r in rows if r['vendor_reference_mass_kg'] is not None)
    r01new=math.fsum(rparts[i]['material_mass_kg'] for i in rparts)
    r01old=selection['summary']['existing_128_geometry_with_selected_steel_mass_kg']
    frame_delta=math.fsum(r['difference_kg'] for r in frame_deltas)
    expected=base['summary']['current_candidate_material_subtotal_kg']+r01new+frame_delta
    ck('material_replacement_identity',abs(material-expected)<1e-11)
    ck('CIC84_once',abs(nominal_cic-.3024)<1e-12)
    ck('B601_ten_rows_once_owner',sum(r['responsibility_owner']=='B601_DM_COMPLETE' for r in rows)==10)
    covered=lambda r:r['candidate_material_mass_kg'] is not None or r['vendor_reference_mass_kg'] is not None or r['responsibility_owner']=='B601_DM_COMPLETE'
    counts=dict(instances=len(rows),physical_or_represented=sum(r['physical_mass_applicable'] for r in rows),candidate_geometry_material=sum(r['candidate_material_mass_kg'] is not None for r in rows),whole_module_reference_covered=sum(r['vendor_reference_mass_kg'] is not None or r['responsibility_owner']=='B601_DM_COMPLETE' for r in rows),numeric_coverage=sum(covered(r) for r in rows),unresolved_including_budget=sum(r['physical_mass_applicable'] and not covered(r) for r in rows),pure_reserved=sum(not r['physical_mass_applicable'] for r in rows))
    ck('coverage_partition',counts==dict(instances=873,physical_or_represented=872,candidate_geometry_material=306,whole_module_reference_covered=94,numeric_coverage=400,unresolved_including_budget=472,pure_reserved=1),counts)
    owners=[]
    for owner in sorted({r['responsibility_owner'] for r in rows}):
        items=[r for r in rows if r['responsibility_owner']==owner]
        mats=[r['candidate_material_mass_kg'] for r in items if r['candidate_material_mass_kg'] is not None]
        refs=[r['vendor_reference_mass_kg'] for r in items if r['vendor_reference_mass_kg'] is not None]
        n=4.5 if owner=='B601_DM_COMPLETE' else math.fsum(refs) if refs else None
        budgets=[r['retained_legacy_planning_budget_kg'] for r in items if r['retained_legacy_planning_budget_kg'] is not None]
        owners.append(dict(owner=owner,instance_count=len(items),known_material_subset_kg=math.fsum(mats) if mats else None,module_reference_kg=n,nonadditive_historical_budget_kg=math.fsum(budgets) if budgets else None,numerically_unresolved_instances=sum(r['physical_mass_applicable'] and not covered(r) for r in items),as_built_total_mass_kg=None))
    # Budget values are archival context only; no combined total is emitted.
    snapshot={'schema':'MASS_RESPONSIBILITY_ROLLFORWARD_873_V1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'873_SOURCE_BOUND_RESPONSIBILITY_COMPLETE_NUMERIC_MASS_PARTIAL__NATIVE_VERIFICATION_SEPARATE',
      'scope':'Three state source plans with actual new STEP-volume receipts. Same hardware in three poses, not three sets. This ledger does not certify full hardware realization or native cold-open.',
      'state_instance_counts':{s:len(v) for s,v in state_indexes.items()},'coverage':counts,'owner_count':len(owners),'unresolved_owner_count':sum(o['numerically_unresolved_instances']>0 for o in owners),
      'candidate_material_subset_kg':material,'B601_whole_vendor_reference_kg':4.5,'CIC84_whole_vendor_average_weight_reference_kg':nominal_cic,
      'full_spacecraft_mass_kg':None,'COM_S_mm':None,'inertia_C_S_kg_mm2':None,'as_built_mass_kg':None,'strict_as_built_mass_lower_bound_kg':None,'model_and_nominal_and_budget_sum_emitted':False,
      'delta_accounting':{'old705_material_subset_kg':base['summary']['current_candidate_material_subtotal_kg'],'R01_old_geometry_if_new_material_bound_kg':r01old,'R01_corrected_actual_STEP_model_kg':r01new,'R01_geometric_difference_only_kg':r01new-r01old,'R01_amount_to_add_to_original705_null_entries_kg':r01new,'solar_eight_frame_replacement_delta_kg':frame_delta,'frame_deltas':frame_deltas,'CIC_internal_elements_additional_count':0,'glue84_finite_volume_mm3':sum(r['source_bound_volume_mm3'] for r in rows if r['id'] in bondids),'glue84_mass_kg':None,'parent705_unchanged':True},
      'unmodeled_or_unclosed_hardware_mass_remains':['actual CIC formed interconnect placement and added string wiring/blocking devices','selected solar bonding process/substrate/embedded attachments','selected complete propulsion package and power/communication cabling','high-power arm flight supply and charger system if adopted','hardware stop drivers, mechanical support and regenerative sink if adopted','existing472 numerical mass inputs; no blank filled with zero'],
      'source_revision_erratum':erratum,'native_cold_verification_status':'NOT_CREDITED_BY_MASS_LEDGER','source_bindings':bindings,
      'frame_volume_algorithm':{'current_source_method':'build123d shape.volume; Solid.volume delegates Shape.compute_mass using GProp_GProps and BRepGProp.VolumeProperties_s(shape,properties) default overload, without explicit Eps','runtime_source_read_only':'C:/Users/stude/AppData/Roaming/Python/Python313/site-packages/build123d/topology/shape_core.py:803','frame_volume_origin':'Source CAD shape at generation, SHA-bound to exported STEP; not a native SW integral or native cold-open confirmation','old_frame_origin':'Existing705 recorded source-export volume values retained as historical computational model. No retrospective high-precision or SW redefinition of old mass.','same_algorithm_claim_scope':'Same default shape.volume model family; exact numerical error/runtime reproducibility of historical export is not bounded here.','SW_GetMassProperties_adopted':False,'high_precision_roundtrip_adopted_for_mass':False,'high_precision_roundtrip_role':'Independent shape-equivalence diagnostic only; source/new mass ledger must not mix SW/high-precision values into one side of a historical-method mechanical delta.','source_vs_native_integral_discrepancy_disposition':'External native writer receipt; not suppressed or relabeled as exact mass agreement.','frame_volume_error_bound_mm3':None},
      'whole_mechatronic_design_complete':False,'manufacturing_release':False,'CAD_or_COM_executed_by_rollforward':False,'checks_passed':len(checks),'checks_total':len(checks),'owners':owners,'instances':rows,'checks':checks}
    ck('read_inputs_unchanged',all(sha(p)==h for p,h in bindings.items()))
    snapshot['checks_passed']=snapshot['checks_total']=len(checks)
    save(OUT/'MASS_ASSIGNMENT_873.json',snapshot)
    fields=['id','responsibility_owner','representation_role','accounting_basis','candidate_material_mass_kg','vendor_reference_mass_kg','retained_legacy_planning_budget_kg','source_bound_volume_mm3','density_kg_mm3','as_built_mass_kg','note']
    with (OUT/'MASS_ASSIGNMENT_873.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    with (OUT/'MASS_OWNER_SUMMARY_873.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(owners[0]));w.writeheader();w.writerows(owners)
    print(json.dumps({k:snapshot[k] for k in ['status','coverage','owner_count','unresolved_owner_count','candidate_material_subset_kg','checks_passed']}))
if __name__=='__main__':main()
