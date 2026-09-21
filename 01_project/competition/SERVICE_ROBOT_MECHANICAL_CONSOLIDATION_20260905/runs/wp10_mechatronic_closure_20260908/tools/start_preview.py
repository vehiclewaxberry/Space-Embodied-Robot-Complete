from pathlib import Path
import subprocess,sys,json,urllib.request
from datetime import datetime,timezone
D=Path(__file__).resolve().parents[1];logs=D/'logs';logs.mkdir(exist_ok=True)
url='http://127.0.0.1:3253/wp10_mechatronic_closure_20260908/'
try:
    urllib.request.urlopen(url+'ecad/README.md',timeout=3)
    print('existing expected preview responds');raise SystemExit(0)
except Exception:pass
with (logs/'preview_stdout.log').open('ab') as out,(logs/'preview_stderr.log').open('ab') as err:
    p=subprocess.Popen([sys.executable,'-B','-X','utf8',str(D/'tools/review_server.py')],cwd=D,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
(D/'results/PREVIEW_SERVER.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'pid':p.pid,'base_url':url,'root':str(D.parent),'bind':'127.0.0.1','task_owned':True,'hidden':True},indent=2),encoding='utf-8')
print(json.dumps({'pid':p.pid,'url':url+'REVIEW.html'}))
