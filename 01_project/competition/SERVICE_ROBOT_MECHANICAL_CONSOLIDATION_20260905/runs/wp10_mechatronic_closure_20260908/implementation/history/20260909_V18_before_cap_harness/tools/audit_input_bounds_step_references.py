"""Attribute the preexisting STEP reader warning without importing CAD."""
from pathlib import Path
import re,json,hashlib
A=Path(__file__).resolve().parents[1]
p=json.loads((A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json').read_text())
unique={r['source_sha256']:r for s in p['states'].values() for r in s['rows']};issues=[]
for h,r in unique.items():
 b=Path(r['step_path']).read_bytes();assert hashlib.sha256(b).hexdigest()==h
 s=b.decode('latin1');s=re.sub(r"'(?:[^']|'')*'",'',s);s=re.sub(r'/\*.*?\*/','',s,flags=re.S)
 definitions=set(re.findall(r'#(\d+)\s*=',s));references=set(re.findall(r'#(\d+)',s));missing=sorted(references-definitions,key=int)
 if missing:issues.append(dict(example_id=r['id'],step_path=r['step_path'],source_sha256=h,missing_entity_ids=missing,occurrences=[dict(state=state,id=q['id']) for state,v in p['states'].items() for q in v['rows'] if q['source_sha256']==h]))
out=dict(schema='WP10_STEP_REFERENCE_TEXT_AUDIT_V1',source_plan_sha256=hashlib.sha256((A/'mechanical/ROOT_BUSHING_INSTANCE_PLAN.json').read_bytes()).hexdigest(),unique_sources_scanned=len(unique),unresolved_reference_sources=issues,method='Remove quoted STEP strings and comments; compare #entity uses against definitions. Text integrity only, not BRep validity.',source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(A/'results/INPUT_BOUNDS_STEP_REFERENCE_AUDIT.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
