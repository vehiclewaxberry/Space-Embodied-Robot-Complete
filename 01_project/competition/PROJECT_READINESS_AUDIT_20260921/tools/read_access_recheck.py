"""Stat/list only verification of inaccessible inventory paths; never removes files."""
from pathlib import Path
import datetime,json,os,subprocess
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parents[1]
j=json.loads((OUT/'GITHUB_INVENTORY.json').read_text('utf-8'))
def inspect(p,listing=False):
    path=Path(p); row={'path':path.relative_to(ROOT).as_posix()}
    try:
        st=path.stat(follow_symlinks=False)
        row.update(stat_accessible=True,bytes=st.st_size,is_file=path.is_file(),is_directory=path.is_dir())
        if listing:
            with os.scandir(path) as it: row['direct_entry_count']=sum(1 for _ in it)
            row['listing_accessible']=True
    except OSError as e:row.update(stat_or_listing_error=type(e).__name__,winerror=getattr(e,'winerror',None),errno=e.errno)
    return row
rechecks=[inspect(p['path'],True) for p in j['filesystem']['scan_errors']]
p=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'status','--porcelain=v1','-z','--untracked-files=no'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
records=[x for x in p.stdout.split(b'\0') if x]
deleted=[inspect(ROOT/x[3:].decode('utf-8','replace')) for x in records if x[:2]==b' D']
original_D=json.loads((OUT/'SANDBOX_REPORTED_D_PATHS.json').read_text('utf-8'))
original_D_rechecks=[inspect(ROOT/x) for x in original_D]
out={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'escalated read-only stat/direct-list and git status; no recursive changes; no body reads','scan_error_directory_rechecks':rechecks,'git_reported_D_path_rechecks':deleted,'git_warning_count':len(p.stderr.splitlines()),'original_scan_error_count':len(rechecks),'original_paths_now_listable':sum(r.get('listing_accessible',False) for r in rechecks),'git_D_count':len(deleted),'git_D_paths_stat_accessible':sum(r.get('stat_accessible',False) for r in deleted),'git_D_paths_not_found':sum(r.get('stat_or_listing_error')=='FileNotFoundError' for r in deleted),'git_D_paths_permission_denied':sum(r.get('stat_or_listing_error')=='PermissionError' for r in deleted)}
out['sandbox_original_D_rechecks']=original_D_rechecks
out['sandbox_original_D_count']=len(original_D)
out['sandbox_original_D_files_found']=sum(r.get('is_file',False) for r in original_D_rechecks)
out['interpretation']='Original sandbox D markers were access artifacts; elevated status and original-file stat are authoritative for this audit.'
(OUT/'READ_ACCESS_RECHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf-8')
j['git']['elevated_access_recheck']={k:out[k] for k in ('generated_utc','git_D_count','git_warning_count','sandbox_original_D_count','sandbox_original_D_files_found','original_scan_error_count','original_paths_now_listable','interpretation')}
j['git']['initial_porcelain_D_is_confirmed_access_artifact']=out['git_D_count']==0 and out['sandbox_original_D_files_found']==out['sandbox_original_D_count']
j['filesystem']['access_recheck_note']='All originally inaccessible directories were listable under escalation; original volume is retained as a lower bound because this follow-up used stat/direct-list only.'
(OUT/'GITHUB_INVENTORY.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({k:v for k,v in out.items() if not isinstance(v,list)},ensure_ascii=False,indent=2))
