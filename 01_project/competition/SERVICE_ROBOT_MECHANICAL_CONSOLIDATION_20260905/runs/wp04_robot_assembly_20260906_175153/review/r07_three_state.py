"""Independent three-state R07 affected static regression on actual final STEP.

Root executes --execute-geometry serially after every export/inspect is finished.
Only service affected bare shapes survive between imports; no anytree copying.
Parking/released use all actual physical/proxy context, so unchanged metadata is
never taken as proof that hidden interior geometry is unchanged.
"""
from __future__ import annotations
import argparse
import gc
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

RUN=Path(__file__).resolve().parents[1]
REVIEW=RUN/'review'
ENGINE=REVIEW/'review_r07.py'
spec=importlib.util.spec_from_file_location('independent_r07_engine',ENGINE)
r07=importlib.util.module_from_spec(spec);spec.loader.exec_module(r07)
sha256,progress,item=r07.sha256,r07.progress,r07.item
LIN_TOL,VOL_TOL=r07.LIN_TOL,r07.VOL_TOL
STATES=('service','parking','released')
PHYSICAL=r07.PHYSICAL


def read_json(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def numeric_delta(a,b):
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        if len(a)!=len(b):raise ValueError('Incompatible numeric metadata dimensions')
        return max((numeric_delta(x,y) for x,y in zip(a,b)),default=0)
    return abs(float(a)-float(b))


def state_data(receipt,step):
    return dict(step=dict(path=str(step.resolve()),sha256=sha256(step)),connections=[],
                instances=[dict(instance_id=r['id'],step_label=r['id'],role=r['representation_role']) for r in receipt['instances']])


def verify_service_receipt(report,bindings,affected):
    checks=[]
    acceptable={'SCOPED_GEOMETRY_WITH_UNKNOWN','SCOPED_NOMINAL_GEOMETRY_PASS_PARENT_OPEN'}
    checks.append(item('accepted_scoped_service_review',report.get('status') in acceptable))
    checks.append(item('service_review_covers_all_affected',affected<=set(report.get('independently_affected_ids',[]))))
    required=('validity','local_final_equivalence','holes','bearing_faces','paths','sleeves','shared_pillar_stack','rear_and_axial','reliefs_and_counterbores','candidate5_explicit_reliefs','r01_deck_inventory_regression','r01_angle_inventory_regression')
    for field in required:
        rows=report.get(field,[])
        checks.append(item('service_all_pass:'+field,bool(rows) and all(r.get('status')=='PASS' for r in rows)))
    static=report.get('affected_static_pairs',{})
    threads=static.get('thread_geometry_unknown',[])
    expected={frozenset((f'RB_end_plug_{sx}_{sy}_{sz}',f'RB_end_screw_{sx}_{sy}_{sz}')) for sx in (-1,1) for sy in (-1,1) for sz in (-1,1)}
    checks.append(item('service_no_unresolved_static_intersections',static.get('status') in ('PASS','UNKNOWN') and not static.get('findings') and {frozenset(t['ids']) for t in threads}==expected and len(threads)==8))
    checks.append(item('service_negative_controls',report.get('negative_controls',{}).get('status')=='PASS'))
    prior=report.get('input_sha256_after',{})
    checks.append(item('service_inputs_stable_during_review',prior==report.get('input_sha256_before') and bool(prior)))
    for path,wanted in bindings.items():
        # Paths shared by the two independent reviews must bind to precisely the
        # final inspected files. Hash mismatch cannot be healed by editing JSON.
        if path in prior:checks.append(item('final_service_hash:'+Path(path).name,prior[path]==wanted,path=path))
    return checks


def actual_metadata(engine,receipt):
    checks=[]
    for row in receipt['instances']:
        key=row['id'];shape=engine.shapes[key]
        actual_bounds=engine.bounds[key]
        expected=(row['bounds']['min_mm'],row['bounds']['max_mm'])
        delta=numeric_delta(actual_bounds,expected)
        volume=engine.volume(shape);vd=abs(volume-float(row['volume_mm3']))
        checks.append(item('actual_step_receipt:'+key,delta<LIN_TOL and vd<=max(VOL_TOL,abs(volume)*1e-8),max_bounds_delta_mm=delta,volume_delta_mm3=vd))
    return checks


def context_aabb_evidence(engine,reference_registry,current_registry,affected):
    physical={k for k,r in current_registry.items() if r['representation_role'] in PHYSICAL}
    fields=('T_S_local','volume_mm3','bounds','local_bounds','representation_role')
    changed={k for k in physical-affected if any(reference_registry[k].get(f)!=current_registry[k].get(f) for f in fields)}
    strict=0;candidate_pairs=[];min_gap=None
    for context in sorted(changed):
        bmin,bmax=engine.bounds[context]
        for target in sorted(affected):
            amin,amax=engine.bounds[target]
            gaps=[max(0,bmin[i]-amax[i],amin[i]-bmax[i]) for i in range(3)]
            distance=math.sqrt(sum(v*v for v in gaps))
            if distance>LIN_TOL:
                strict+=1;min_gap=distance if min_gap is None else min(min_gap,distance)
            else:candidate_pairs.append([target,context])
    return dict(changed_context_ids=sorted(changed),total_changed_context_pairs=len(changed)*len(affected),strictly_separated_pair_count=strict,minimum_certifying_aabb_distance_mm=min_gap,requires_actual_narrowphase_pairs=candidate_pairs,
                interpretation='AABB overlap is only a candidate, never an assertion of material collision. The full actual state static test below includes every such pair and also all metadata-unchanged context pairs.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate',type=Path,default=RUN/'candidate')
    ap.add_argument('--contract',type=Path,default=RUN/'candidate/results/R07_CONNECTION_CONTRACT.json')
    ap.add_argument('--service-review',type=Path,default=REVIEW/'R07_REVIEW_FINAL_SERVICE.json')
    ap.add_argument('--output',type=Path,default=REVIEW/'R07_THREE_STATE_REVIEW.json')
    ap.add_argument('--execute-geometry',action='store_true')
    args=ap.parse_args();started=time.monotonic()
    out=dict(schema='WP04_R07_THREE_STATE_INDEPENDENT_REVIEW_V1',status='NOT_RUN',scope='Three discrete states; all affected R07 against registered non-arm physical geometry and simplified proxies',parent_issue_closed=False,whole_robot_pass=False,continuous_motion_pass=False,physical_assembly_completed=False,manufacturing_release=False,
             limits=['Eight bounded axial thread-proxy regions remain UNKNOWN; real thread geometry/engagement/preload not accepted','Functional envelopes and all arm geometry are outside this structural scope','Service tool/insertion paths are not automatically credited in other states','Common-plane legacy side-screw/pillar clearance is nominal zero, without physical tolerance qualification'])
    try:
        receipts={s:args.candidate/'results'/f'{s}_structure_instances.json' for s in STATES}
        steps={s:args.candidate/f'servicer_structure_{s}.step' for s in STATES}
        docs={s:read_json(p) for s,p in receipts.items()}
        contract=read_json(args.contract);service_report=read_json(args.service_review)
        registries={s:{r['id']:r for r in d['instances']} for s,d in docs.items()}
        affected=set(contract['affected_instance_ids'])
        inputs=[*receipts.values(),*steps.values(),args.contract,args.service_review,ENGINE,r07.BASE,Path(__file__),args.candidate/'r07_design.py',args.candidate/'spacecraft_model.py',args.candidate/'root_structure.py',args.candidate/'design_parameters.json']
        bindings={str(p.resolve()):sha256(p) for p in inputs}
        out['input_sha256_before']=bindings
        checks=[item('contract_service_frame',contract.get('state')=='service' and contract.get('units')=='mm' and contract.get('frame')=='S')]
        for s in STATES:
            ids=registries[s]
            checks.append(item('unique_complete_same_inventory:'+s,len(ids)==len(docs[s]['instances']) and set(ids)==set(registries['service'])))
            checks.append(item('state_identity:'+s,docs[s].get('state')==s))
            checks.append(item('affected_all_physical_proxy:'+s,affected<=set(ids) and all(ids[k]['representation_role'] in PHYSICAL for k in affected if k in ids)))
        checks.extend(verify_service_receipt(service_report,bindings,affected))
        # Require the central final service files to be explicitly present in the
        # upstream binding, not just compare whichever keys happen to overlap.
        for path in (receipts['service'],steps['service'],args.contract,ENGINE):
            key=str(path.resolve())
            checks.append(item('service_required_binding:'+path.name,service_report.get('input_sha256_after',{}).get(key)==bindings[key]))
        out.update(input_checks=checks,affected_instance_ids=sorted(affected),state_instance_counts={s:len(registries[s]) for s in STATES})
        if any(c['status']=='FAIL' for c in checks):out['status']='INPUT_BINDING_FAIL_GEOMETRY_NOT_RUN'
        elif not args.execute_geometry:out['status']='INPUT_BINDING_PASS_GEOMETRY_NOT_RUN'
        else:
            out['runtime_bootstrap']=r07.base.bootstrap_cad_runtime()
            progress('service_reference_import')
            service=r07.Review(state_data(docs['service'],steps['service']),args.contract)
            out['service_actual_receipt_checks']=actual_metadata(service,docs['service'])
            reference_shapes={key:service.shapes[key] for key in affected}
            reference_bounds={key:service.bounds[key] for key in affected}
            out['service_import_metadata']=service.import_metadata
            del service;gc.collect();progress('only_service_affected_shapes_retained',count=len(reference_shapes))
            out['states']={}
            for state in ('parking','released'):
                progress('state_start',state=state)
                engine=r07.Review(state_data(docs[state],steps[state]),args.contract)
                record=dict(import_metadata=engine.import_metadata,actual_receipt_checks=actual_metadata(engine,docs[state]),validity=engine.validity(),affected_invariance=[])
                for index,key in enumerate(sorted(affected)):
                    shape,ref=engine.shapes[key],reference_shapes[key]
                    delta=engine.volume(shape-ref)+engine.volume(ref-shape)
                    transform_delta=numeric_delta(registries[state][key]['T_S_local'],registries['service'][key]['T_S_local'])
                    bounds_delta=numeric_delta(engine.bounds[key],reference_bounds[key])
                    record['affected_invariance'].append(item('actual_material_and_transform:'+key,delta<=VOL_TOL and transform_delta<1e-9 and bounds_delta<LIN_TOL,symmetric_difference_mm3=delta,transform_max_delta=transform_delta,bounds_max_delta_mm=bounds_delta))
                    if index%25==0:progress('affected_invariance',state=state,checked=index+1,total=len(affected))
                record['changed_context_aabb']=context_aabb_evidence(engine,registries['service'],registries[state],affected)
                record['all_related_static_pairs']=engine.static(affected)
                rows=record['all_related_static_pairs'];numeric=[r['status'] for field in ('actual_receipt_checks','validity','affected_invariance') for r in record[field]]
                thread_pairs={frozenset(t['ids']) for t in rows['thread_geometry_unknown']}
                expected_thread_pairs={frozenset(t['ids']) for t in service_report['affected_static_pairs']['thread_geometry_unknown']}
                record['bounded_thread_region_scope']=item('same_8_named_thread_unknowns',thread_pairs==expected_thread_pairs and len(rows['thread_geometry_unknown'])==8)
                ok=all(s=='PASS' for s in numeric) and rows['status'] in ('PASS','UNKNOWN') and not rows['findings'] and record['bounded_thread_region_scope']['status']=='PASS'
                record['status']='DISCRETE_STATE_RELATED_STATIC_PASS_WITH_8_THREAD_UNKNOWNS' if ok else 'DISCRETE_STATE_RELATED_STATIC_FAIL'
                out['states'][state]=record
                del engine;gc.collect();progress('state_finished',state=state,status=record['status'])
            ok=all(r['status']=='PASS' for r in out['service_actual_receipt_checks']) and all(r['status']=='DISCRETE_STATE_RELATED_STATIC_PASS_WITH_8_THREAD_UNKNOWNS' for r in out['states'].values())
            out['status']='THREE_STATE_RELATED_NOMINAL_STATIC_PASS_WITH_8_THREAD_UNKNOWNS' if ok else 'THREE_STATE_RELATED_STATIC_FAIL'
            del reference_shapes;gc.collect()
        out['input_sha256_after']={path:sha256(path) for path in bindings}
        if out['input_sha256_after']!=bindings:out['status']='INPUT_DRIFT_FAIL'
    except Exception as exc:
        import traceback
        out.update(status='REVIEW_ERROR_FAIL_CLOSED',error=str(exc),traceback=traceback.format_exc())
    out['elapsed_s']=time.monotonic()-started
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(status=out['status'],output=str(args.output)),ensure_ascii=False),flush=True)
    return 1 if 'FAIL' in out['status'] or 'ERROR' in out['status'] else 0


if __name__=='__main__':sys.exit(main())
