"""Acquire publicly versioned B601-DM reference mappings; never import motor control."""
from pathlib import Path
import hashlib,json,urllib.request
D=Path(__file__).resolve().parent
S=D/'sources/seeed_dm_config'; S.mkdir(parents=True,exist_ok=True)
repo='Seeed-Projects/reBotArm_control_py'
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'WP09-source-check'}),timeout=30) as r:return r.read()
meta=json.loads(get('https://api.github.com/repos/'+repo))
branch=meta['default_branch']
commit=json.loads(get('https://api.github.com/repos/'+repo+'/commits/'+branch))['sha']
tree=json.loads(get('https://api.github.com/repos/'+repo+'/git/trees/'+commit+'?recursive=1'))
(S/'sdk_tree.json').write_text(json.dumps({'repository':repo,'commit':commit,'tree':tree},indent=2),encoding='utf-8')
paths=[x['path'] for x in tree['tree'] if x['type']=='blob' and ((x['path'].startswith('config/') and x['path'].endswith('.yaml') and 'rs' not in x['path'].lower()) or x['path']=='LICENSE')]
rows=[]
for rel in paths:
    url=f'https://raw.githubusercontent.com/{repo}/{commit}/{rel}'
    b=get(url);p=S/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    rows.append({'path':p.relative_to(S).as_posix(),'url':url,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
(S/'manifest.json').write_text(json.dumps({'repository':repo,'commit':commit,'rows':rows,'scope':'Public reference configuration, not as-built binding'},indent=2),encoding='utf-8')
print(json.dumps({'commit':commit,'paths':paths}))
