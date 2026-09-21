"""Download the published commit archive and check every delivered file without keeping a duplicate checkout."""
from pathlib import Path
from datetime import datetime,timezone
import csv,hashlib,json,subprocess,tempfile,urllib.request,zipfile

A=Path(__file__).resolve().parent;ROOT=A.parents[2]
P=ROOT/'20_engineering/SERVICE_STAR_PUBLICATION_20260921'
repo='https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete.git'
safe='safe.directory='+P.as_posix()
commit=subprocess.check_output(['git','-c',safe,'rev-parse','HEAD'],cwd=P,text=True).strip()
remote=subprocess.check_output(['git','-c',safe,'ls-remote',repo,'refs/heads/main'],cwd=P,text=True,timeout=90).split()[0]
assert remote==commit,'Remote main does not match prepared commit'
url='https://codeload.github.com/vehiclewaxberry/Space-Embodied-Robot-Complete/zip/'+commit
expected={p.relative_to(P).as_posix():p for p in P.rglob('*') if p.is_file() and '.git' not in p.relative_to(P).parts}
downloaded=0;matches=0;errors=[]
with tempfile.TemporaryFile(dir=A,suffix='.zip') as tmp:
    request=urllib.request.Request(url,headers={'User-Agent':'Python-urllib/3.13'})
    with urllib.request.urlopen(request,timeout=45) as response:
        while True:
            chunk=response.read1(1024*1024)
            if not chunk:break
            tmp.write(chunk);downloaded+=len(chunk)
    tmp.seek(0)
    with zipfile.ZipFile(tmp) as archive:
        members={}
        for info in archive.infolist():
            if info.is_dir():continue
            path=info.filename.split('/',1)[1]
            if path in members:errors.append({'path':path,'error':'duplicate ZIP entry'})
            members[path]=info
        if set(members)!=set(expected):
            errors.append({'missing':sorted(set(expected)-set(members)),'unexpected':sorted(set(members)-set(expected))})
        for relative,local in expected.items():
            if relative not in members:continue
            with local.open('rb') as f:local_hash=hashlib.file_digest(f,'sha256').hexdigest()
            with archive.open(members[relative]) as f:remote_hash=hashlib.file_digest(f,'sha256').hexdigest()
            if local_hash!=remote_hash or local.stat().st_size!=members[relative].file_size:
                errors.append({'path':relative,'error':'remote bytes differ'})
            else:matches+=1
receipt={'schema':'GITHUB_HARDWARE_PUBLICATION_RECEIPT_V1','verified_utc':datetime.now(timezone.utc).isoformat(),'repository':'https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete','branch':'main','commit':commit,'remote_main_matches':remote==commit,'remote_archive_files':len(members),'local_expected_files':len(expected),'remote_archive_matches':matches,'archive_download_bytes':downloaded,'local_design_bytes':sum(p.stat().st_size for p in expected.values()),'temporary_archive_retained':False,'ordinary_git_content_no_LFS_fetch_required':True,'old_version_backup_branch_created':False,'publication_strategy':'Single root commit replaces main using exact force-with-lease per user request','errors':errors,'status':'PASS' if not errors and matches==len(expected) else 'FAIL'}
(A/'GITHUB_PUBLICATION_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
raise SystemExit(receipt['status']!='PASS')
