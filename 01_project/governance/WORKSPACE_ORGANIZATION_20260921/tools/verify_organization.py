"""Read-only checks of executed cleanup and navigation; writes only its own receipt."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import csv, hashlib, json, re, subprocess

D=Path(__file__).resolve().parents[1]
ROOT=D.parents[2]
def read(name): return json.loads((D/name).read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
failures=[]
checks={}
cache=read('CACHE_CLEANUP_EXECUTED.json')
large=read('LARGE_DUPLICATE_CLEANUP_EXECUTED.json')
archive=read('ROOT_ARCHIVE_ACTIONS.json')
nav=read('NAVIGATION_CHANGES.json')
inv=read('INVENTORY_SUMMARY.json')
def require(ok,label):
    if not ok: failures.append(label)
cache_source_hashes=0
for r in cache['records']:
    require(not (ROOT/r['path']).exists(),'deleted cache reappeared: '+r['path'])
    if r.get('source') and r.get('source_sha256'):
        try: require(sha(ROOT/r['source'])==r['source_sha256'],'cache source changed: '+r['source'])
        except OSError as e: failures.append('cache source unreadable: '+r['source']+' '+type(e).__name__)
        cache_source_hashes+=1
for r in large['files']:
    require(not (ROOT/r['source']).exists(),'display copy still exists: '+r['source'])
    require((ROOT/r['canonical']).stat().st_size==r['bytes'] and sha(ROOT/r['canonical'])==r['sha256'],'canonical STEP changed: '+r['canonical'])
require(large['deleted_bytes']==sum(r['bytes'] for r in large['files']),'large total mismatch')
require(int(cache['bytes'])==sum(r['bytes'] for r in cache['records']),'cache total mismatch')
move=archive['moved']
require(not (ROOT/move['source']).exists(),'retired root source still exists')
require(sha(ROOT/move['target'])==move['sha256_before'],'archived configuration hash changed')
require(not (ROOT/'.playwright-cli').exists(),'empty container reappeared')
require((D/'local_private/.gitignore').read_text().strip()=='*','private ignore missing')
for r in nav:
    require(sha(ROOT/r['backup'])==r['sha256_before'],'navigation backup mismatch: '+r['source'])
    require(sha(ROOT/r['source'])==r['sha256_after'],'current navigation unexpected change: '+r['source'])
    if r['source']!='PROJECT_MAP.md':
        old=(ROOT/r['backup']).read_text(encoding='utf-8')
        new=(ROOT/r['source']).read_text(encoding='utf-8')
        old_heading,_,old_rest=old.partition('\n')
        new_heading,_,new_rest=re.sub(r'<!-- WORKSPACE_NAV_START -->.*?<!-- WORKSPACE_NAV_END -->\s*','',new,flags=re.S).partition('\n')
        require(old_heading==new_heading and old_rest.lstrip('\n')==new_rest.lstrip('\n'),'domain body changed: '+r['source'])

status_path=D/'WORKSPACE_ORGANIZATION_STATUS.json'
# Self link is checked against this intended output, created after all other checks.
local_links=[]
def check_link(origin,target):
    target=target.strip('<>')
    u=urlsplit(target)
    if u.scheme or u.netloc or not u.path: return
    resolved=(origin.parent/unquote(u.path)).resolve()
    local_links.append({'from':origin.relative_to(ROOT).as_posix(),'target':target})
    require(resolved==status_path or resolved.exists(),'missing navigation target: '+str(resolved))
for p in [ROOT/'PROJECT_MAP.md',D/'README.md',ROOT/'40_evidence/artifacts/visualization/cad_showcase_20260916/README.md']:
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8')): check_link(p,target)
for r in nav:
    if r['source']=='PROJECT_MAP.md': continue
    p=ROOT/r['source']
    banner=re.search(r'<!-- WORKSPACE_NAV_START -->(.*?)<!-- WORKSPACE_NAV_END -->',p.read_text(encoding='utf-8'),re.S).group(1)
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',banner): check_link(p,target)
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            for k,v in attrs:
                if k=='href': check_link(D/'WORKSPACE_INDEX.html',v)
page=(D/'WORKSPACE_INDEX.html').read_text(encoding='utf-8')
Links().feed(page)
script=re.search(r'<script>(.*?)</script>',page,re.S).group(1)
syntax=subprocess.run(['node','--check'],input=script,text=True,capture_output=True)
require(syntax.returncode==0,'offline index JavaScript syntax: '+syntax.stderr)
index_rows=json.loads(re.search(r'const data=(.*?);const \$',script,re.S).group(1))
require(len(index_rows)==172,'directory index row count changed')
for r in index_rows: require((ROOT/r['path']).exists()==r['exists'],'directory index stale: '+r['path'])

protection=read('PROTECTED_INTEGRITY_REVIEW.json') if (D/'PROTECTED_INTEGRITY_REVIEW.json').exists() else None
require(protection is not None,'independent protected integrity receipt pending')
if protection:
    require(protection.get('checks_total')==protection.get('matched_total') and protection.get('checks_total',0)>0,'independent protected checks incomplete or mismatched')
    require(protection.get('source_manifests_unchanged_during_review') is True,'independent protected manifests changed')
result={
    'schema':'WORKSPACE_ORGANIZATION_VERIFICATION_V1',
    'generated_utc':datetime.now(timezone.utc).isoformat(),
    'status':'PASS_WITH_ENUMERATION_LIMITATIONS' if not failures else 'NEEDS_ATTENTION',
    'scope':'File organization only; no design or scientific qualification claim',
    'deleted_files':len(cache['records'])+len(large['files']),
    'deleted_bytes':int(cache['bytes'])+large['deleted_bytes'],
    'deleted_paths_absent_checked':len(cache['records'])+len(large['files']),
    'cache_source_hashes_checked':cache_source_hashes,
    'canonical_step_hashes_checked':len(large['files']),
    'retired_configuration_archive_hash_checked':True,
    'navigation_backups_and_current_hashes_checked':len(nav),
    'domain_readme_bodies_preserved_checked':8,
    'new_or_changed_navigation_local_links_checked':len(local_links),
    'historical_embedded_readme_links_repaired':False,
    'offline_index_javascript_syntax_checked':syntax.returncode==0,
    'classified_directory_snapshot_rows':len(index_rows),
    'existing_directory_rows':sum(r['exists'] for r in index_rows),
    'pre_cleanup_readable_bytes':inv['bytes'],
    'pre_cleanup_readable_files':inv['files'],
    'enumeration_access_errors':inv['errors'],
    'complete_enumeration':False,
    'independent_protected_integrity_receipt':'PROTECTED_INTEGRITY_REVIEW.json',
    'independent_protected_checks_total':protection.get('checks_total') if protection else None,
    'independent_protected_matches':protection.get('matched_total') if protection else None,
    'failures':failures,
    'qualification':'Preserves baseline bytes; does not establish every remaining file is necessary or every deeply nested file was reviewed.'
}
status_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['enumeration_access_errors']},ensure_ascii=False,indent=2))
raise SystemExit(bool(failures))
