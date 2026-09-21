"""Start one owned, loopback-only lightweight preview with no visible shell."""
from pathlib import Path
import socket,subprocess,sys,json,time
C=Path(__file__).resolve().parents[1]
with socket.socket() as s:
    active=s.connect_ex(('127.0.0.1',3252))==0
if active:
    print('PORT_ALREADY_LISTENING_NO_NEW_PROCESS')
else:
    out=(C/'logs/review_server.stdout.log').open('ab');err=(C/'logs/review_server.stderr.log').open('ab')
    p=subprocess.Popen([sys.executable,'-B',str(C/'tools/review_server.py')],stdout=out,stderr=err,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    out.close();err.close()
    r={'pid':p.pid,'url':'http://127.0.0.1:3252/','script':str(C/'tools/review_server.py'),'launch_epoch':time.time(),'purpose':'Local design artifact preview; no CAD or hardware'}
    (C/'results/REVIEW_SERVER.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
