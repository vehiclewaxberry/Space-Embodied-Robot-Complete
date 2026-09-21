"""Append-only binding for unchanged arm source geometry before compositional reuse."""
from pathlib import Path
import json,hashlib
from candidate_context import WP01,RUN,SOURCE_WP03,verify_upstream
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    verify_upstream();p=RUN/'inputs/ARM_REUSE_INPUT_EXTENSION.json'
    if p.exists():raise FileExistsError(p)
    old=json.loads((SOURCE_WP03/'results/service_instances.json').read_text(encoding='utf-8'))
    paths=[WP01/'inputs'/(r['arm_link']+'.step') for r in old['instances'] if r.get('arm_link')]
    assert len(paths)==10 and all(q.is_file() for q in paths)
    d=dict(schema='WP03_INPUT_EXTENSION_V1',reason='Hash-lock unchanged arm BRep sources before explicitly declared compositional receipt reuse; no new arm BRep or collision claims',initial_manifest_sha256=sha(RUN/'inputs/INPUT_MANIFEST.json'),source_sha256={str(q):sha(q) for q in paths})
    p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8');print(str(p))
if __name__=='__main__':main()
