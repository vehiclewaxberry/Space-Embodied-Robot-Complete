"""Close and reopen the final SERVICE file after its optional display Save3.

This is a read-only native-file check of final bytes, component identity, paths,
transforms, fixed state, suppression/visibility and dependency set. It does not
repeat body enumeration or COM point multiplication; body evidence is explicitly
bound to the previous full cold inspection plus unchanged native dependencies.
"""
from pathlib import Path
import json
import math
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from integrate_native import Integrator,require,sha,normalized,val,t16,R


def main():
    state='service';output=R/'results/FINAL_REOPEN_SERVICE.json'
    require(not output.exists(),'Existing final-reopen receipt is protected')
    source=R/'results/NATIVE_SERVICE.json';manifest_path=R/'results/INTEGRATION_MANIFEST.json'
    previous=json.loads(source.read_text(encoding='utf-8'));manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    require(previous.get('status','').startswith('PASS_'),'SERVICE integration did not finish')
    require(previous['manifest_sha256']==sha(manifest_path),'SERVICE manifest binding differs')
    path=R/'native/WP07_ROBOT_SERVICE.SLDASM';digest=sha(path)
    require(digest==previous['final_native_sha256'],'Final SERVICE native SHA differs')
    prior_cold=previous['cold_inspection'];old_rows={p['id']:p for p in prior_cold['components']}
    rows=manifest['states'][state]['instances'];expected={r['id']:r for r in rows}
    require(len(rows)==len(expected)==597 and set(old_rows)==set(expected),'Prior cold coverage differs')
    require(prior_cold['component_count']==597 and prior_cold['solid_count']==978,'Prior full cold body evidence is incomplete')
    pins={str(source):sha(source),str(manifest_path):sha(manifest_path),str(path):digest,str(Path(__file__).resolve()):sha(__file__)}
    allowed={normalized(path):digest}
    # Allow only manifest-bound native dependencies from the three states.
    # Removed legacy components and other stale documents remain unregistered.
    for info in manifest['states'].values():
        for row in info['instances']:
            key=normalized(row['native_path'])
            if key in allowed:
                require(allowed[key]==row['native_sha256'],'Conflicting dependency hash in manifest')
            allowed[key]=row['native_sha256']
    require(len(allowed)-1==460,'Expected exactly 460 bound three-state native dependencies')
    registered_prior_states=[]
    for other in ('parking','released'):
        other_path=R/'native'/('WP07_ROBOT_'+other.upper()+'.SLDASM')
        other_receipt=R/'results'/('NATIVE_'+other.upper()+'.json')
        if not other_path.exists() and not other_receipt.exists():
            continue
        require(other_path.is_file() and other_receipt.is_file(),'Other-state assembly/receipt pair is incomplete')
        other_data=json.loads(other_receipt.read_text(encoding='utf-8'))
        require(other_data.get('status','').startswith('PASS_'),'Other-state assembly has no completed PASS receipt')
        require(other_data['manifest_sha256']==sha(manifest_path),'Other-state manifest binding differs')
        require(sha(other_path)==other_data['final_native_sha256'],'Other-state final native hash differs')
        allowed[normalized(other_path)]=other_data['final_native_sha256']
        pins[str(other_receipt)]=sha(other_receipt)
        registered_prior_states.append(dict(state=other,path=str(other_path),sha256=other_data['final_native_sha256'],
                                           receipt_path=str(other_receipt),receipt_sha256=pins[str(other_receipt)]))
    for native,native_sha in allowed.items():
        require(sha(native)==native_sha,'Native input changed before final reopen: '+native)
        pins[native]=native_sha
    report=dict(schema='WP07_FINAL_NATIVE_REOPEN_V1',state=state,status='RUNNING',progress=[],
                native_path=str(path),final_native_sha256=digest,manifest_sha256=sha(manifest_path),
                prior_receipt=dict(path=str(source),sha256=sha(source)),
                prior_full_cold_native_sha256=previous['native_save']['sha256'],
                prior_full_cold_body_count=978,current_body_count_remeasured=False,
                current_COM_basis_points_remeasured=False,input_sha256_before=pins,
                registered_completed_other_states=registered_prior_states,registered_three_state_dependency_count=460,
                scope='FINAL_FILE_REOPEN_ID_PATH_SHA_MATRIX_FIXED_SUPPRESSION_VISIBILITY_DEPENDENCIES; BODY_COUNTS_FROM_PRIOR_FULL_COLD_WITH_SAME_NATIVE_PART_SHAS',
                physical_assembly_completed=False,manufacturing_release=False)
    builder=None
    try:
        builder=Integrator(output,report)
        require(int(val(builder.sw,'GetProcessID'))==26208,'Unexpected existing SolidWorks PID')
        # Only exact clean, hash-bound SERVICE/finished-state/dependency documents may be closed.
        builder.close_registered(allowed)
        opened=builder.sw.OpenDoc6(str(path),2,195,'',0,0)  # silent + read-only + explicit lightweight
        require(isinstance(opened,tuple) and len(opened)==3 and opened[0] is not None and opened[1]==0,
                'Final SERVICE file could not be reopened read-only')
        model=builder.wrap(opened[0],'IModelDoc2');builder.activate(model,path)
        assembly=builder.wrap(model,'IAssemblyDoc');components=assembly.GetComponents(True) or []
        require(len(components)==597,'Final file component count differs')
        observed=[];cache={}
        for raw in components:
            component=builder.wrap(raw,'IComponent2');identity=component.ComponentReference
            require(identity in expected,'Unknown final-file component ID')
            row=expected[identity];prior=old_rows[identity]
            native=Path(val(component,'GetPathName')).resolve();key=normalized(native)
            require(normalized(native)==normalized(row['native_path'])==normalized(prior['path']),
                    'Final-file dependency path differs')
            if key not in cache:
                cache[key]=sha(native)
            require(cache[key]==row['native_sha256']==prior['sha256'],'Final-file dependency SHA differs')
            matrix=list(builder.wrap(component.Transform2,'IMathTransform').ArrayData)
            require(len(matrix)==16 and all(math.isfinite(v) for v in matrix),'Invalid final-file transform')
            expected_error=max(abs(a-b) for a,b in zip(matrix,t16(row['T_S_local'])))
            prior_error=max(abs(a-b) for a,b in zip(matrix,prior['transform_sw16']))
            require(expected_error<1e-8 and prior_error<1e-8 and component.IsFixed(),'Final-file fixed transform differs')
            suppression=component.GetSuppression2()
            require(suppression in (1,2,4),'Unexpected suppressed or unresolved component state')
            visible=component.Visible
            require(visible==prior['visible'],'Display state was not restored in final file')
            require(prior['solid_count']==row['expected_solids'] and prior['sheet_count']==0,
                    'Prior full-body count does not bind to the current dependency')
            observed.append(dict(id=identity,path=str(native),sha256=cache[key],transform_sw16=matrix,
                expected_transform_max_error=expected_error,prior_transform_max_error=prior_error,fixed=True,
                suppression_state=suppression,visible=visible,prior_full_cold_solid_count=prior['solid_count'],
                body_count_evidence='PRIOR_FULL_COLD_SAME_NATIVE_PART_PATH_AND_SHA_NOT_REMEASURED'))
        require(len({r['id'] for r in observed})==597,'Duplicate final-file IDs')
        deps=model.GetDependencies2(False,True,False) or []
        require(len(deps)%2==0,'Malformed final-file dependency array')
        dep_paths=[Path(deps[i+1]).resolve() for i in range(0,len(deps),2)]
        require({normalized(p) for p in dep_paths}=={normalized(r['native_path']) for r in rows},'Final-file dependency set differs')
        require(len({normalized(p) for p in dep_paths})==445,'Final-file unique dependency count differs')
        require(sha(path)==digest,'Read-only reopen changed native bytes')
        report.update(status='PASS_FINAL_NATIVE_REOPEN_WITH_PRIOR_FULL_BODY_EVIDENCE',component_count=597,
                      unique_dependencies=445,components=observed,cold_open=dict(errors=opened[1],warnings=opened[2],options=195),
                      dependencies=[dict(path=str(p),sha256=cache[normalized(p)]) for p in dep_paths],
                      native_file_unchanged=True,left_open_read_only=True,left_open_dirty_flag=bool(val(model,'GetSaveFlag')))
        after={p:sha(p) for p in pins};require(after==pins,'A pinned input changed during final reopen')
        report['input_sha256_after']=after;report['inputs_unchanged']=True
        builder.checkpoint('final_saved_service_reopened_checked_without_saving',component_count=597,
                           final_native_sha256=digest)
    except Exception as exc:
        report.update(status='FAILED',error=str(exc),traceback=traceback.format_exc())
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    finally:
        if builder and builder.initialized:
            builder.pythoncom.CoUninitialize()


if __name__=='__main__':
    main()
