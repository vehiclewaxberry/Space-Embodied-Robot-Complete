"""Read-only whole-workspace inventory. No symlink traversal or file-content disclosure."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv, gzip, hashlib, json, os, subprocess

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[2]
errors=[]; skipped_links=[]; usage=defaultdict(lambda:{'files':0,'bytes':0})
largest=[]; files=0; total=0; protected=[]

def onerror(err):
    errors.append({'path':str(err.filename),'error':type(err).__name__})

tracked=set(subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}','-c','core.quotepath=false','ls-files','-z'],cwd=ROOT,capture_output=True,check=True).stdout.decode('utf-8').split('\0'))
with gzip.open(HERE/'FILE_INVENTORY.csv.gz','wt',encoding='utf-8',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=['path','bytes','mtime_ns','tracked','area','kind'])
    writer.writeheader()
    for base, dirs, names in os.walk(ROOT,followlinks=False,onerror=onerror):
        basepath=Path(base)
        for dirname in list(dirs):
            child=basepath/dirname
            try:
                if child.is_symlink() or (getattr(child.lstat(),'st_file_attributes',0)&0x400):
                    dirs.remove(dirname); skipped_links.append(child.relative_to(ROOT).as_posix())
            except OSError as err:
                dirs.remove(dirname); onerror(err)
        for name in names:
            p=basepath/name
            rel=p.relative_to(ROOT).as_posix()
            if p.is_relative_to(HERE):
                continue  # Do not inflate the source inventory with its own changing output.
            try:
                stat=p.lstat()
                if p.is_symlink() or (getattr(stat,'st_file_attributes',0)&0x400):
                    skipped_links.append(rel); continue
                size=stat.st_size
            except OSError as err:
                onerror(err); continue
            parts=p.relative_to(ROOT).parts
            area=parts[0] if len(parts)>1 else '(root files)'
            if parts[0]=='.git': kind='ROOT_GIT_METADATA'
            elif '.git' in parts: kind='NESTED_GIT_METADATA'
            elif any(s in parts for s in ['__pycache__','.pytest_cache','_generated_com']): kind='CACHE_NAME_ONLY_NOT_DELETE_APPROVAL'
            elif '__cadgen__' in parts: kind='CAD_DERIVED_WITH_POSSIBLE_EVIDENCE_BINDINGS'
            elif area in ['.codex','.agents','.claude','.playwright-cli']: kind='LOCAL_TOOL_CONFIGURATION'
            else: kind='PROJECT_OR_RUNTIME_ASSET'
            writer.writerow({'path':rel,'bytes':size,'mtime_ns':stat.st_mtime_ns,'tracked':rel in tracked,'area':area,'kind':kind})
            files+=1;total+=size
            for depth in [1,2]:
                key='/'.join(parts[:depth]) if len(parts)>depth else area
                if depth==2 and key==area: continue
                usage[key]['files']+=1;usage[key]['bytes']+=size
            if size>=10*1024**2: largest.append({'path':rel,'bytes':size,'kind':kind,'tracked':rel in tracked})
            lower=p.name.lower()
            protect=area in ['10_research','20_engineering','30_simulation'] and (('gate' in lower and p.suffix.lower()=='.json') or 'sha256' in lower and p.suffix.lower()=='.csv')
            if protect:
                try:
                    protected.append({'path':rel,'bytes':size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
                except OSError as err:
                    onerror(err)

with (HERE/'DIRECTORY_USAGE.csv').open('w',encoding='utf-8-sig',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=['path','files','bytes','GiB'])
    writer.writeheader()
    for key,val in sorted(usage.items()):
        writer.writerow({'path':key,**val,'GiB':round(val['bytes']/1024**3,6)})
with (HERE/'LARGE_FILES_CURRENT.csv').open('w',encoding='utf-8-sig',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=['path','bytes','kind','tracked']);writer.writeheader()
    writer.writerows(sorted(largest,key=lambda r:r['bytes'],reverse=True))
(HERE/'PROTECTED_BASELINE.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
root_git=usage.get('.git',{}).get('bytes',0)
summary={'schema':'WORKSPACE_FILESYSTEM_INVENTORY_V1','generated_utc':datetime.now(timezone.utc).isoformat(),
         'scope':'Read-only metadata; source inventory excludes this audit directory itself; no symlinks followed',
         'files':files,'bytes':total,'root_git_bytes':root_git,'bytes_excluding_root_git':total-root_git,
         'top_level':{k:v for k,v in usage.items() if '/' not in k},
         'large_files_ge_10_MiB':len(largest),'protected_gate_or_hash_manifest_files':len(protected),
         'errors':errors,'complete_enumeration':not errors,'skipped_reparse_paths':skipped_links,
         'notes':['Cache classification is not deletion authorization','Nested Git, runtimes and backups are counted, not declared redundant','Permission errors are not deletions']}
(HERE/'INVENTORY_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['files','bytes','root_git_bytes','bytes_excluding_root_git','large_files_ge_10_MiB','protected_gate_or_hash_manifest_files','complete_enumeration']},ensure_ascii=False))
print(json.dumps({'read_errors':len(errors),'top_level':summary['top_level']},ensure_ascii=False))
