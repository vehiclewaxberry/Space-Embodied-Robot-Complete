"""Build explicit composite instance packages; does not generate a monolithic arm STEP."""
from pathlib import Path
import json,copy
from candidate_context import HERE,RUN,WP01,SOURCE_WP03,verify_upstream
from provenance_binding import sha,verify_hashes,validate_receipt_source
from composition_binding import MODE,validate_composition
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def main():
    verify_upstream();ep=RUN/'inputs/ARM_REUSE_INPUT_EXTENSION.json';ext=load(ep);verify_hashes(ext['source_sha256'])
    pending=[]
    for state in ['parking','released','service']:
        fp=HERE/'results'/f'{state}_structure_instances.json';op=SOURCE_WP03/'results'/f'{state}_instances.json'
        step=HERE/f'servicer_structure_{state}.step';fresh=load(fp);old=load(op);d=copy.deepcopy(fresh)
        arm=[copy.deepcopy(r) for r in old['instances'] if r.get('arm_link')];sources={r['arm_link']:ref(WP01/'inputs'/(r['arm_link']+'.step')) for r in arm}
        for row in arm:row['geometry_reuse']=sources[row['arm_link']]
        d['instances']+=arm
        ids={r['id'] for r in arm};d['interfaces'] += [copy.deepcopy(v) for v in old['interfaces'] if v['instance'] in ids]
        lo=[min(r['bounds']['min_mm'][i] for r in d['instances']) for i in range(3)];hi=[max(r['bounds']['max_mm'][i] for r in d['instances']) for i in range(3)]
        d['bounds']=dict(min_mm=lo,max_mm=hi,size_mm=[hi[i]-lo[i] for i in range(3)])
        d['composition_mode']=MODE;d['monolithic_complete_step_generated']=False
        d['geometry_sha256']={str(step.resolve()):sha(step),str(op.resolve()):sha(op),**{v['path']:v['sha256'] for v in sources.values()}}
        ip=HERE/'results'/f'{state}_COMPOSITE_ASSEMBLY_INDEX.json'
        index=dict(configuration=d['configuration'],state=state,composition_mode=MODE,units='mm',frame='S',nonarm_step=ref(step),nonarm_instance_ids=[r['id'] for r in fresh['instances']],arm_occurrences=[dict(id=r['id'],arm_link=r['arm_link'],geometry=sources[r['arm_link']],T_S_local=r['T_S_local']) for r in arm],collision_credit=None)
        ip.write_text(json.dumps(index,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        d['composition']=dict(builder=ref(__file__),input_extension=ref(ep),original_receipt=ref(op),fresh_nonarm_receipt=ref(fp),fresh_nonarm_step=ref(step),arm_sources=sources,assembly_index=ref(ip))
        d['dependency_sha256'].update({n:sha(HERE/n) for n in ['compose_receipts.py','composition_binding.py','provenance_binding.py']})
        validate_composition(d,HERE);validate_receipt_source(d,HERE)
        pending.append((HERE/'results'/f'{state}_instances.json',d))
    verify_upstream();verify_hashes(ext['source_sha256'])
    for p,d in pending:
        validate_composition(d,HERE);p.write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    print(json.dumps([dict(state=d['state'],instances=len(d['instances']),mode=MODE) for _,d in pending]))
if __name__=='__main__':main()
