"""Read-only acquisition of public OEM sources. Never executes downloaded code."""
from pathlib import Path
import urllib.request, urllib.parse, json, hashlib, datetime, concurrent.futures, time

OUT = Path(__file__).resolve().parents[1]
SRC = OUT / 'sources'
SRC.mkdir(parents=True, exist_ok=True)
def fetch(url):
    for attempt in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Service-star-engineering-audit'}), timeout=25).read()
        except Exception:
            if attempt == 2: raise
            time.sleep(1)
def save(name, url):
    raw = fetch(url)
    (SRC / name).write_bytes(raw)
    return {'file': 'sources/' + name, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
manifest = {'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'read_only': True, 'repositories': [], 'files': []}
jobs=[]
for repo, prefix in [('Seeed-Projects/reBot-DevArm','b601'),('vectorBH6/reBotArm_control_py','sdk')]:
    meta=json.loads(fetch('https://api.github.com/repos/'+repo))
    commit=json.loads(fetch('https://api.github.com/repos/'+repo+'/commits/'+meta['default_branch']))
    sha=commit['sha']; tree_sha=commit['commit']['tree']['sha']
    tree=json.loads(fetch('https://api.github.com/repos/'+repo+'/git/trees/'+tree_sha+'?recursive=1'))
    (SRC/(prefix+'_tree.json')).write_text(json.dumps(tree,ensure_ascii=False,indent=2),encoding='utf-8')
    (SRC/(prefix+'_commit.json')).write_text(json.dumps(commit,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest['repositories'].append({'repo':repo,'commit':sha,'tree':tree_sha,'truncated':tree.get('truncated')})
    for row in tree['tree']:
        p=row['path']; lp=p.lower()
        choose = (prefix=='b601' and (lp in ['readme.md','license'] or (p.startswith('hardware/reBot_B601_DM/') and lp.endswith('.md')))) or (prefix=='sdk' and ((lp.endswith(('.yaml','.yml')) and ('dm' in lp or 'rebotarm.yaml' in lp)) or lp=='readme.md'))
        if choose:
            jobs.append((prefix+'__'+p.replace('/','__'),'https://raw.githubusercontent.com/'+repo+'/'+sha+'/'+urllib.parse.quote(p)))
jobs += [('seeed_quickstart_ja.html','https://wiki.seeedstudio.com/ja/rebot_b601_dm_getting_started/'),('seeed_dm_series.html','https://wiki.seeedstudio.com/cn/damiao_series/'),('nasa_avionics.html','https://www.nasa.gov/smallsat-institute/sst-soa/small-spacecraft-avionics/'),('nasa_thermal.html','https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/'),('nasa5017b.pdf','https://standards.nasa.gov/sites/default/files/standards/NASA/B/2022-12-06-NASA-STD-5017B-Approved.pdf')]
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    futs={pool.submit(save,*j):j for j in jobs}
    for f,j in futs.items():
        try: manifest['files'].append(f.result())
        except Exception as e: manifest['files'].append({'file':'sources/'+j[0],'url':j[1],'error':str(e)})
(SRC/'PUBLIC_SOURCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'repos':manifest['repositories'],'saved':len([x for x in manifest['files'] if 'sha256' in x]),'errors':[x for x in manifest['files'] if 'error' in x]},ensure_ascii=False,indent=2))
