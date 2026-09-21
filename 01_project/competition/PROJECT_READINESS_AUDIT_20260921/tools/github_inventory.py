"""Read-only repository inventory; writes only this audit package. No file bodies exported."""
from pathlib import Path
import os, stat, json, csv, subprocess, collections, datetime, re

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
MIB = 1024**2

def git(*args, data=None, check=True):
    p = subprocess.run(['git', '-c', 'safe.directory=' + ROOT.as_posix(), *args], cwd=ROOT, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode:
        raise RuntimeError('git ' + ' '.join(args[:2]) + ' failed: ' + p.stderr.decode('utf-8','replace')[:500])
    return p

def csvwrite(name, rows, fields):
    with (OUT/name).open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)

def decode(data): return data.decode('utf-8','replace')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inv={'schema':'github-packaging-readonly-v1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'workspace':ROOT.as_posix(),'scope':'filesystem includes ignored runtime/cache; reparse points skipped; no secret body scan; no Git mutation'}
    tracked_data=git('ls-files','--stage','-z').stdout.split(b'\0')
    tracked={}
    for raw in tracked_data:
        if not raw: continue
        meta,path=raw.split(b'\t',1); mode,oid,stage=decode(meta).split()
        tracked[decode(path)]={'mode':mode,'oid':oid,'stage':stage}
    others=set(filter(None,decode(git('ls-files','--others','--exclude-standard','-z').stdout).split('\0')))
    ignored=set(filter(None,decode(git('ls-files','--others','--ignored','--exclude-standard','-z').stdout).split('\0')))
    rawstatus=git('status','--porcelain=v1','-z','--untracked-files=all')
    states=collections.Counter()
    toks=rawstatus.stdout.split(b'\0'); i=0
    while i<len(toks):
        s=toks[i];i+=1
        if not s:continue
        xy=decode(s[:2]);states[xy]+=1
        if 'R' in xy or 'C' in xy:i+=1
    inv['git']={'head':decode(git('rev-parse','HEAD').stdout).strip(),'branch':decode(git('branch','--show-current').stdout).strip(),'tracked_index_paths':len(tracked),'untracked_nonignored_paths':len(others),'ignored_untracked_paths':len(ignored),'porcelain_counts':dict(states),'warning_lines':len(decode(rawstatus.stderr).splitlines()),'recent_commits':decode(git('log','-8','--format=%h %cs %s').stdout).splitlines(),'remote_names':decode(git('remote').stdout).splitlines(),'count_objects':decode(git('count-objects','-v').stdout).splitlines()}
    tracked_ignored=list(filter(None,decode(git('ls-files','-ci','--exclude-standard','-z').stdout).split('\0')))
    inv['git']['tracked_paths_matching_ignore_rules']=len(tracked_ignored)
    inv['git']['tracked_ignore_extension_counts']=dict(collections.Counter(Path(p).suffix.lower() or '(none)' for p in tracked_ignored))
    print('git status collected',flush=True)
    domain=collections.defaultdict(lambda: {'files':0,'bytes':0,'tracked_files':0,'untracked_files':0,'ignored_files':0})
    category=collections.defaultdict(lambda: {'files':0,'bytes':0})
    large=[];skips=[];errors=[];allfiles=[]
    stack=[ROOT]
    while stack:
        d=stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    rel=Path(e.path).relative_to(ROOT).as_posix()
                    try:
                        s=e.stat(follow_symlinks=False)
                        if stat.S_ISLNK(s.st_mode) or (getattr(s,'st_file_attributes',0)&0x400):
                            skips.append(rel);continue
                        if stat.S_ISDIR(s.st_mode):stack.append(Path(e.path));continue
                        if not stat.S_ISREG(s.st_mode):continue
                        top=rel.split('/')[0] if '/' in rel else '(root files)'
                        dd=domain[top];dd['files']+=1;dd['bytes']+=s.st_size
                        state='tracked' if rel in tracked else ('ignored' if rel in ignored else ('untracked' if rel in others else 'not_git_enumerated'))
                        if state+'_files' in dd:dd[state+'_files']+=1
                        allfiles.append((rel,s.st_size,state))
                        if top!='.git' and s.st_size>50*MIB:large.append({'path':rel,'bytes':s.st_size,'MiB':round(s.st_size/MIB,3),'git_state':state,'over_100_MiB':s.st_size>100*MIB})
                        labels=[]
                        if any(x.startswith(('.tmp','__pycache__','.pytest')) or x=='gen_py' for x in rel.split('/')):labels.append('temporary_or_cache_name_candidate')
                        if '/runtime' in rel.lower() or '/_runtime/' in rel.lower() or '/portable/' in rel.lower():labels.append('runtime_name_candidate')
                        if Path(rel).suffix.lower() in ('.zip','.7z','.tar','.gz'):labels.append('archive')
                        for label in labels:category[label]['files']+=1;category[label]['bytes']+=s.st_size
                    except OSError as x:errors.append({'path':rel,'error':type(x).__name__})
        except OSError as x:errors.append({'path':str(d),'error':type(x).__name__})
    large.sort(key=lambda x:x['bytes'],reverse=True)
    csvwrite('LARGE_FILES.csv',large,['path','bytes','MiB','git_state','over_100_MiB'])
    inv['filesystem']={'domains':dict(sorted(domain.items())),'total_files':sum(x['files'] for x in domain.values()),'total_bytes_including_dot_git':sum(x['bytes'] for x in domain.values()),'over_50_MiB_count':len(large),'over_100_MiB_count':sum(x['over_100_MiB'] for x in large),'large_file_bytes':sum(x['bytes'] for x in large),'name_based_categories_overlap':dict(category),'reparse_skipped':skips,'scan_errors':errors}
    gb=collections.Counter()
    for rel,size,_ in allfiles:
        if rel.startswith('.git/'):gb[rel.split('/')[1]]+=size
    inv['filesystem']['root_dot_git_bytes_by_child']=dict(gb)
    inv['filesystem']['unclassified_nested_git_metadata_note']=f'Git ignored listing may collapse nested repos; domain state counts are exact enumerated paths, not all descendants. Bytes include nested .git and ignored runtime/cache. {len(errors)} inaccessible paths make file/byte totals lower bounds.'
    print('filesystem collected',flush=True)
    unique=sorted({x['oid'] for x in tracked.values()})
    info={}
    data=git('cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)',data=('\n'.join(unique)+'\n').encode()).stdout
    for line in decode(data).splitlines():
        oid,typ,sz=line.split();info[oid]=(typ,int(sz))
    small=[oid for oid,(typ,sz) in info.items() if typ=='blob' and sz<=1024]
    data=git('cat-file','--batch',data=('\n'.join(small)+'\n').encode()).stdout
    ptr={};pos=0
    while pos<len(data):
        end=data.find(b'\n',pos);head=decode(data[pos:end]).split();sz=int(head[2]);body=data[end+1:end+1+sz];pos=end+sz+2
        if body.startswith(b'version https://git-lfs.github.com/spec/v1\n'):
            oidm=re.search(rb'oid sha256:([a-f0-9]{64})',body);sm=re.search(rb'\nsize (\d+)',body)
            ptr[head[0]]={'lfs_oid':decode(oidm[1]) if oidm else None,'size':int(sm[1]) if sm else None}
    attributes=git('check-attr','-z','--stdin','filter',data=('\0'.join(tracked)+'\0').encode()).stdout.split(b'\0')
    attrs={decode(attributes[i]):decode(attributes[i+2]) for i in range(0,len(attributes)-2,3)}
    attrlfs=[p for p in tracked if attrs.get(p)=='lfs']
    mismatch=[{'path':p,'index_blob_bytes':info[tracked[p]['oid']][1]} for p in attrlfs if tracked[p]['oid'] not in ptr]
    lfsrows=[]
    for p,x in tracked.items():
        if x['oid'] in ptr:
            z=ptr[x['oid']];lp=ROOT/'.git/lfs/objects'/z['lfs_oid'][:2]/z['lfs_oid'][2:4]/z['lfs_oid']
            lfsrows.append({'path':p,**z,'local_lfs_object_exists':lp.is_file(),'attribute_filter':attrs.get(p)})
    trackedlarge=[{'path':p,'oid':x['oid'],'bytes':info[x['oid']][1],'MiB':round(info[x['oid']][1]/MIB,3),'lfs_filter':attrs.get(p),'is_lfs_pointer':x['oid'] in ptr} for p,x in tracked.items() if info[x['oid']][0]=='blob' and info[x['oid']][1]>50*MIB]
    trackedlarge.sort(key=lambda x:x['bytes'],reverse=True)
    csvwrite('TRACKED_LARGE_BLOBS.csv',trackedlarge,['path','oid','bytes','MiB','lfs_filter','is_lfs_pointer'])
    csvwrite('LFS_ATTRIBUTE_MISMATCH.csv',mismatch,['path','index_blob_bytes'])
    inv['lfs']={'version':decode(git('lfs','version',check=False).stdout).strip(),'attributes_matching_lfs':len(attrlfs),'index_pointer_paths':len(lfsrows),'unique_index_pointer_objects':len(ptr),'pointer_logical_bytes':sum(z['size'] or 0 for z in lfsrows),'pointer_paths_missing_local_object':sum(not z['local_lfs_object_exists'] for z in lfsrows),'lfs_attributes_but_real_git_blob_count':len(mismatch),'pointer_without_lfs_filter':sum(z['attribute_filter']!='lfs' for z in lfsrows),'tracked_git_blobs_over_50_MiB':len(trackedlarge),'tracked_git_blobs_over_100_MiB':sum(z['bytes']>100*MIB for z in trackedlarge)}
    print('index/LFS collected',flush=True)
    data=git('rev-list','--objects','--all').stdout
    history=git('cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)',data=data).stdout
    historylarge=[];nobj=0;blobn=0;blobtotal=0
    for line in decode(history).splitlines():
        fields=line.split(' ',3);oid,typ,sz=fields[:3];sz=int(sz);nobj+=1
        if typ=='blob':
            blobn+=1;blobtotal+=sz
            if sz>50*MIB:historylarge.append({'path':fields[3] if len(fields)>3 else '', 'oid':oid,'bytes':sz,'MiB':round(sz/MIB,3),'over_100_MiB':sz>100*MIB})
    historylarge.sort(key=lambda x:x['bytes'],reverse=True)
    csvwrite('HISTORY_LARGE_BLOBS.csv',historylarge,['path','oid','bytes','MiB','over_100_MiB'])
    inv['reachable_history']={'scope':'all locally reachable refs; no reflog/unreachable objects; one path label per unique object, not all rename aliases','objects':nobj,'unique_blob_objects':blobn,'logical_blob_bytes':blobtotal,'unique_blobs_over_50_MiB':len(historylarge),'unique_blobs_over_100_MiB':sum(z['over_100_MiB'] for z in historylarge),'largest_10':historylarge[:10]}
    print('history collected',flush=True)
    rootnames={p.name:p.is_file() for p in ROOT.iterdir()}
    requirements=[];ci=[];absolute=[];source_ext={'.py','.ps1','.sh','.json','.yaml','.yml','.toml','.md'}
    counts=collections.Counter()
    absolute_pattern=re.compile(r'(?<![A-Za-z0-9])(?:F|G):[\\/]')
    for rel,size,state in allfiles:
        if rel.startswith(('.git/','80_third_party/')) or '/site-packages/' in rel or '/portable/' in rel or '/_runtime/' in rel:continue
        name=Path(rel).name.lower()
        if name in ('pyproject.toml','requirements.txt','environment.yml','environment.yaml','package.json','poetry.lock','uv.lock','package-lock.json','conda-lock.yml') or name.startswith('requirements-'):requirements.append(rel)
        if rel.startswith('.github/workflows/'):ci.append(rel)
        if Path(rel).suffix.lower() in source_ext and size<10*MIB:
            try:
                s=(ROOT/rel).read_text('utf-8',errors='ignore');n=len(absolute_pattern.findall(s))
                if n:counts[rel.split('/')[0]]+=1;absolute.append({'path':rel,'occurrences':n,'git_state':state})
            except OSError:pass
    csvwrite('ABSOLUTE_FG_PATH_REFERENCES.csv',absolute,['path','occurrences','git_state'])
    inv['entrypoints']={'root_README_present':any(x.lower().startswith('readme') and y for x,y in rootnames.items()),'root_LICENSE_present':any(x.lower().startswith(('license','copying')) and y for x,y in rootnames.items()),'root_CITATION_present':any(x.lower().startswith('citation') and y for x,y in rootnames.items()),'root_dependency_lock_present':any(x.lower() in ('requirements.txt','environment.yml','environment.yaml','pyproject.toml','poetry.lock','uv.lock','package-lock.json','conda-lock.yml') and y for x,y in rootnames.items()),'root_workflow_files':ci,'dependency_files_excluding_vendor_runtime':requirements,'absolute_FG_paths_matching_files':len(absolute),'absolute_path_files_by_domain':dict(counts),'absolute_scan_scope':'utf8-readable py/ps1/sh/json/yaml/yml/toml/md under10MiB; excludes .git,80_third_party,site-packages,portable,_runtime; counts include historical records, not proof every match executes'}
    final=json.loads((ROOT/'20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/results/FINAL_DELIVERY_STATUS.json').read_text('utf-8'))
    inv['portability']={'R6H_final_status_portable_package':final.get('portable_package'),'R6H_native_files_locked':final.get('native_files_locked'),'absolute_path_matches_include_historical_evidence':True,'clean_machine_replay_performed':False}
    (OUT/'GITHUB_INVENTORY.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'git':inv['git'],'domains':inv['filesystem']['domains'],'large_counts':[len(large),inv['filesystem']['over_100_MiB_count']],'lfs':inv['lfs'],'history':{k:v for k,v in inv['reachable_history'].items() if k!='largest_10'},'entrypoints':{k:v for k,v in inv['entrypoints'].items() if k!='dependency_files_excluding_vendor_runtime'}},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
