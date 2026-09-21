from pathlib import Path
import json,hashlib
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=HERE/'results/r01_connections.json';d=json.loads(p.read_text(encoding='utf-8'))
    d['step_sha256']=sha(d['step_path'])
    ids={r['id'] for r in d['instances']}
    context=HERE/'r01_context.step';current=HERE/'results/service_structure_instances.json'
    receipt=HERE/'results/r01_context_instances.json';receipt.write_bytes(current.read_bytes())
    rows=json.loads(receipt.read_text(encoding='utf-8'))['instances']
    for r in rows:
        if r['id'] in ids:continue
        d['instances'].append(dict(id=r['id'],label=r['id'],role=r['representation_role'],step_path=str(context),step_sha256=sha(context)))
    d['context']=dict(state='service',baseline_receipt=str(receipt),baseline_receipt_sha256=sha(receipt),excluded_scope=['ARM_BREP_SELF_GEOMETRY','FUNCTIONAL_ENVELOPES_NOT_PHYSICAL_CLEARANCE','OTHER_MOTION_STATES','CONTINUOUS_MOTION','ACTUAL_SELECTED_TOOL_AND_THREADS'])
    d['source_sha256']={str(HERE/n):sha(HERE/n) for n in ['spacecraft_model.py','design_parameters.json','r01_design.py','r01_context.step.py']}
    d['scope']='R01_FINAL_LOCAL_STEP_PLUS_ALL_FRESH_UNCHANGED_NONARM_SERVICE_CONTEXT'
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(instances=len(d['instances']),connections=len(d['connections']),sha256=sha(p))))
if __name__=='__main__':main()
