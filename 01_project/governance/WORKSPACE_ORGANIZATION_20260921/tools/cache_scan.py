"""Read-only cache candidate evidence; never deletes or executes project modules."""
from pathlib import Path
import os, stat, json, csv, hashlib, struct, subprocess, datetime, re, _imp, collections

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]
DOMAINS=['01_project','10_research','20_engineering','30_simulation','40_evidence','50_literature','70_tools','80_third_party']
SKIP={'.git','.codex','.agents','.claude','.venv','venv','env','site-packages','node_modules','portable','_runtime','cadgen_v30','__cadgen__'}

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf-8')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    g=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'ls-files','-z'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    tracked=set(filter(None,g.stdout.decode('utf-8').split('\0')))
    files=[];excluded=[];errors=[];reparse=[]
    for d in DOMAINS:
        stack=[ROOT/d]
        while stack:
            p=stack.pop()
            try:
                with os.scandir(p) as it:
                    for e in it:
                        ep=Path(e.path);s=e.stat(follow_symlinks=False)
                        if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:reparse.append(rel(ep));continue
                        if stat.S_ISDIR(s.st_mode):
                            if e.name in SKIP or (ep.parent==ROOT/'70_tools' and e.name.startswith('runtime_')):excluded.append(rel(ep));continue
                            stack.append(ep)
                        elif stat.S_ISREG(s.st_mode):files.append((ep,s))
            except OSError as e:errors.append({'path':rel(p),'error':type(e).__name__})
    print('filesystem candidate enumeration complete',flush=True)
    rows=[];uncertain=[]
    for p,s in files:
        kind=None;reason=None;proof={};source=None;scope_marker=None
        if p.suffix.lower()=='.pyc':
            kind='PYTHON_BYTECODE'
            source=p.parent.parent/(p.name.split('.cpython-')[0]+'.py') if p.parent.name=='__pycache__' else p.with_suffix('.py')
            if not source.is_file():
                uncertain.append({'path':rel(p),'bytes':s.st_size,'reason':'PYC_NO_RETAINED_PY_SOURCE'});continue
            b=p.read_bytes();sb=source.read_bytes()
            if len(b)<16:uncertain.append({'path':rel(p),'bytes':s.st_size,'reason':'PYC_HEADER_TOO_SHORT'});continue
            flags=struct.unpack('<I',b[4:8])[0];proof={'magic_hex':b[:4].hex(),'flags':flags,'source_size_bytes':len(sb)}
            if flags==0:
                ts,n=struct.unpack('<II',b[8:16]);proof.update(cache_timestamp=ts,cache_source_size=n,source_mtime_uint32=int(source.stat().st_mtime)&0xffffffff)
                valid=ts==proof['source_mtime_uint32'] and n==len(sb)
            elif flags in (1,3):
                want=_imp.source_hash(int.from_bytes(b[:4],'little'),sb)
                valid=b[8:16]==want;proof['source_hash_header_matches']=valid
            else:valid=False
            if not valid:
                uncertain.append({'path':rel(p),'bytes':s.st_size,'reason':'PYC_SOURCE_HEADER_MATCH_NOT_PROVEN','source':rel(source),'proof':proof});continue
            reason='Retained .py source exists and PEP552 timestamp/size or keyed source-hash header matches. CPython recreates bytecode; source must remain unchanged.'
        elif '.pytest_cache' in p.parts:
            ci=p.parts.index('.pytest_cache');cache=Path(*p.parts[:ci+1]);sub=p.relative_to(cache).as_posix()
            if not (cache/'CACHEDIR.TAG').is_file() or 'Signature: 8a477f597d28d172789f06886806bc55' not in (cache/'CACHEDIR.TAG').read_text('utf-8',errors='ignore'):
                uncertain.append({'path':rel(p),'bytes':s.st_size,'reason':'PYTEST_CACHE_SIGNATURE_NOT_PROVEN'});continue
            ok=False
            if sub=='CACHEDIR.TAG':ok=True
            elif sub=='README.md':ok=p.read_text('utf-8',errors='ignore').startswith('# pytest cache directory #')
            elif sub=='.gitignore':ok='Created by pytest automatically.' in p.read_text('utf-8',errors='ignore')
            elif sub in {'v/cache/nodeids','v/cache/lastfailed','v/cache/stepwise'}:
                try:
                    value=json.loads(p.read_text('utf-8'))
                    ok=isinstance(value,dict) if sub.endswith('lastfailed') else isinstance(value,list)
                except (ValueError,OSError):ok=False
            if not ok:
                uncertain.append({'path':rel(p),'bytes':s.st_size,'reason':'NOT_RECOGNIZED_STANDARD_PYTEST_CACHE_PAYLOAD'});continue
            kind='STANDARD_PYTEST_CACHE';reason='Recognized pytest cache marker and standard cache payload; pytest regenerates collection/history cache. Deletion resets lastfailed/stepwise convenience state, not stored results or gates.'
            source=cache/'CACHEDIR.TAG';scope_marker=rel(cache);proof={'cache_entry':sub,'signature':'8a477f597d28d172789f06886806bc55','structured_payload_verified':True}
        elif '_generated_com' in p.parts:
            uncertain.append({'path':rel(p),'bytes':s.st_size,'reason':'COM_GENERATOR_AND_SEALED_DEPENDENCY_NEED_PER_PACKAGE_BINDING'});continue
        if kind:
            rows.append({'path':rel(p),'bytes':s.st_size,'sha256':sha(p),'tracked':rel(p) in tracked,'kind':kind,'regenerate_reason':reason,'source':rel(source),'source_sha256':sha(source),'source_is_deleted_cache_marker':source==p or kind=='STANDARD_PYTEST_CACHE','proof':proof,'cache_group':scope_marker,'references':[],'recommendation':'PENDING_REFERENCE_CHECK'})
    print(f'{len(rows)} cache/source proofs; reference protection scanning',flush=True)
    hash_to_rows=collections.defaultdict(list)
    for row in rows:hash_to_rows[row['sha256']].append(row)
    ref_count=0;skip_large=[]
    # Inspect evidence/contract/hash inventories and all owned executable source.
    # Read matches are only retained as file names, never content or credentials.
    pattern=re.compile(r'manifest|sha256|(?:asset.*(?:index|register))|gate|contract|source|plan|handoff|input|provenance|receipt',re.I)
    for p,s in files:
        if OUT in p.parents or '__pycache__' in p.parts or '_generated_com' in p.parts or '.pytest_cache' in p.parts:continue
        if p.suffix.lower() not in {'.py','.ps1','.sh','.json','.csv','.yaml','.yml','.toml','.md'}:continue
        if p.suffix.lower() not in {'.py','.ps1','.sh'} and not pattern.search(p.name):continue
        if s.st_size>25*1024*1024:skip_large.append(rel(p));continue
        try:text=p.read_text('utf-8-sig',errors='ignore')
        except OSError as e:errors.append({'path':rel(p),'error':type(e).__name__});continue
        ref_count+=1;ref=rel(p);norm=text.replace('\\\\','/').replace('\\','/').casefold()
        hits=set(re.findall(r'(?<![a-fA-F0-9])[a-fA-F0-9]{64}(?![a-fA-F0-9])',text))
        for digest in hits:
            for row in hash_to_rows.get(digest.casefold(),[]):row['references'].append({'path':ref,'match':'exact_sha256'})
        if any(x in norm for x in ('.pyc','__pycache__','.pytest_cache')):
            for row in rows:
                if row['path'].casefold() in norm:row['references'].append({'path':ref,'match':'exact_workspace_relative_path'})
    for row in rows:
        # A tracked cache could still be required by byte-locked archival builds;
        # preserve it unless a separate explicit historical evidence review clears it.
        row['recommendation']='HOLD_TRACKED_CACHE' if row['tracked'] else ('HOLD_REFERENCED' if row['references'] else 'DELETE_CANDIDATE')
    eligible=[x for x in rows if x['recommendation']=='DELETE_CANDIDATE']
    report={'schema':'WORKSPACE_CACHE_CANDIDATES_V1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Read-only candidate analysis across eight business domains; no deletion, git mutation, module execution or evidence rewriting.','domains':DOMAINS,'excluded_directories':excluded,'reparse_skipped':reparse,'scan_errors':errors,'reference_scan':{'files_read':ref_count,'large_reference_files_not_read':skip_large,'scope':'All py/ps1/sh and named manifest/hash/asset-register/gate/contract/source/plan/handoff/input/provenance/receipt JSON/CSV/YAML/TOML/MD under25MiB; exact full relative path or64hexSHA protection; no universal dynamic dependency proof.'},'candidates':rows,'unproven_preserved':uncertain,'summary':{'files_enumerated_excluding_runtime_and_cadgen':len(files),'proved_cache_rows':len(rows),'eligible_files':len(eligible),'eligible_bytes':sum(x['bytes'] for x in eligible),'held_tracked':sum(x['recommendation']=='HOLD_TRACKED_CACHE' for x in rows),'held_referenced':sum(x['recommendation']=='HOLD_REFERENCED' for x in rows),'unproven_preserved_files':len(uncertain),'actual_deletions':0},'execution_constraints':['Root must cross-check its global protection list and source hash before deleting each named file.','Never recursively delete _work/archive/history/.tmp directories on these findings.','PYC source files remain; pytest cache markers may be deleted together only with their identified group, never project result files.','Do not edit .git, .codex, .agents, live runtime libraries or __cadgen__ diagnostic dependencies.','Preserve tracked caches and any exact evidence path/hash reference until a separate provenance review clears them.']}
    dump(OUT/'CACHE_CANDIDATES.json',report)
    print(json.dumps({'summary':report['summary'],'scan_errors':len(errors),'reference_files_read':ref_count,'large_reference_files_not_read':len(skip_large),'eligible_by_domain':dict(collections.Counter(x['path'].split('/')[0] for x in eligible))},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
