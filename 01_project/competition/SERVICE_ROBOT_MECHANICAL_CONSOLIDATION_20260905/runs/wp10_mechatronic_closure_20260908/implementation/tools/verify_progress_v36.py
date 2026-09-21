from pathlib import Path
from html.parser import HTMLParser
import json,hashlib,urllib.request,psutil
A=Path(__file__).resolve().parents[1];C=A/'coupled_closure'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.links.extend(v for k,v in attrs if k=='href')
p=Links();p.feed((C/'PROGRESS_PLAN_V35_V36.html').read_text(encoding='utf-8'))
missing=[x for x in p.links if not x.startswith(('http','mailto','#')) and not (C/x).exists()]
j=json.loads((C/'PROGRESS_PLAN_V35_V36.json').read_text());bad=[q for q,z in j['source_bindings'].items() if hashlib.sha256(Path(q).read_bytes()).hexdigest()!=z]
print(json.dumps(dict(missing_links=missing,stale_bindings=bad,available_MiB=psutil.virtual_memory().available/2**20)));assert not missing and not bad
u='http://127.0.0.1:3253/wp10_mechatronic_closure_20260908/implementation/coupled_closure/PROGRESS_PLAN_V35_V36.html'
with urllib.request.urlopen(u,timeout=5) as r:print('HTTP',r.status,'bytes',len(r.read()))
