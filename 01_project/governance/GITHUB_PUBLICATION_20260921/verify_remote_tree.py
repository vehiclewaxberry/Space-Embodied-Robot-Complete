"""Independently verify the public main ref and all Git blob identities, without another full download."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,urllib.request

A=Path(__file__).resolve().parent;ROOT=A.parents[2]
P=ROOT/'20_engineering/SERVICE_STAR_PUBLICATION_20260921'
git=['git','-c','safe.directory='+P.as_posix(),'-C',str(P)]
commit=subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip()
tree=subprocess.check_output(git+['rev-parse','HEAD^{tree}'],text=True).strip()
def api(path):
    request=urllib.request.Request('https://api.github.com/repos/vehiclewaxberry/Space-Embodied-Robot-Complete'+path,headers={'User-Agent':'Python-urllib/3.13','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=30) as response:
        body=b''
        while len(body)<4_000_000:
            chunk=response.read1(65536)
            if not chunk:break
            body+=chunk
            try:return json.loads(body)
            except (json.JSONDecodeError,UnicodeDecodeError):pass
        return json.loads(body)
ref=api('/git/ref/heads/main')
remote=ref['object']['sha']
receipt={'verified_utc':datetime.now(timezone.utc).isoformat(),'expected_commit':commit,'remote_main':remote,'remote_main_matches':remote==commit,'method':'Public GitHub ref and recursive tree, with local file bytes bound to their Git blob identities'}
if remote!=commit:
    receipt.update(status='NOT_PUBLISHED_AS_EXPECTED',expected_files=989)
else:
    received=api('/git/trees/'+tree+'?recursive=1')
    assert received.get('sha')==tree and received.get('truncated') is False
    remote_files={r['path']:r for r in received['tree'] if r['type']=='blob'}
    local={}
    for entry in subprocess.check_output(git+['ls-tree','-r','-z','HEAD']).split(b'\0'):
        if not entry:continue
        meta,path=entry.split(b'\t',1);mode,kind,sha=meta.decode().split();path=path.decode()
        assert kind=='blob';local[path]={'mode':mode,'sha':sha}
    errors=[]
    if set(local)!=set(remote_files):errors.append('Remote path set differs')
    matches=0
    for name,row in local.items():
        raw=(P/name).read_bytes()
        git_hash=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        target=remote_files.get(name,{})
        if git_hash==row['sha']==target.get('sha') and row['mode']==target.get('mode') and len(raw)==target.get('size'):matches+=1
        else:errors.append(name)
    receipt.update(status='PASS' if not errors else 'FAIL',tree=tree,remote_files=len(remote_files),local_files=len(local),matching_blob_identities=matches,errors=errors)
(A/'GITHUB_REMOTE_TREE_VERIFICATION.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
raise SystemExit(receipt['status']!='PASS')
