"""Read-only R5E/V36 source-lock preservation after R6H installation."""
from pathlib import Path
import hashlib,json
D=Path(__file__).resolve().parents[2];ROOT=D.parents[1];P=D.parent/'SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920/results/reviewer'
sources={};expected={};origins={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(name):
 p=P/name;sources[str(p.resolve())]=sha(p);return json.loads(p.read_text(encoding='utf8'))
def add(path,h,origin):
 k=str((ROOT/path).resolve());expected.setdefault(k,set()).add(h);origins.setdefault(k,[]).append(origin)
final=read('FINAL_REVIEW.json');native=read('ECAD_CANDIDATE_INDEPENDENT_REVIEW.json');sch=read('SCHEMATIC_SOURCE_HASH_AUDIT.json');boards=read('LOCKED_249_XML_BOARD_AUDIT.json')
for p,h in final['reviewed_current_files'].items():add(p,h,'R5E final review')
for p,h in native['reviewed_hashes_after'].items():add(p,h,'R5E candidate ECAD review')
for r in sch['schematics']:add(r['path'],r['expected'],'original 15 schematic locks')
for name,r in boards['boards'].items():add(r['path'],r['sha256'],'original board '+name)
add(boards['source_xml'],boards['source_xml_sha256'],'authoritative 249 XML')
checks=[]
for p,hs in expected.items():
 actual=sha(p);checks.append(dict(path=p,expected=sorted(hs),actual=actual,passed=len(hs)==1 and actual in hs,origin=origins[p]))
for p,h in sources.items():checks.append(dict(path=p,expected=[h],actual=sha(p),passed=sha(p)==h,origin=['review receipt read-only preservation']))
out=dict(schema='R6H_ELECTRICAL_SOURCE_PRESERVATION_V1',status='PASS_UNCHANGED_R5E_AND_V36' if all(x['passed'] for x in checks) else 'FAIL_SOURCE_DRIFT',checks=dict(passed=sum(x['passed'] for x in checks),total=len(checks),failed=[x for x in checks if not x['passed']]),checks_detail=checks,schematics_preserved=len(sch['schematics']),boards_preserved=len(boards['boards']),unique_locked_files=len(expected),source_review_locks=sources,ecad_modified_by_R6H=False,functional_wiring_credit=False,manufacturing_release=False,ready_to_power=False,flight_ready=False)
(D/'results/reviewer/ELECTRICAL_SOURCE_PRESERVATION.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:out[k] for k in ['status','checks','schematics_preserved','boards_preserved','unique_locked_files']},ensure_ascii=False))
raise SystemExit(0 if all(x['passed'] for x in checks) else 2)
