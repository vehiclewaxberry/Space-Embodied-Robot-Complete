"""Bind a just-launched task-owned SW singleton to the external-process guard."""
import sys,json,datetime,time
from pathlib import Path
import psutil
C=Path(__file__).resolve().parents[1]
rows=[p for p in psutil.process_iter(['pid','name','create_time','exe','cmdline']) if (p.info.get('name') or '').lower()=='sldworks.exe']
assert len(rows)==1;p=rows[0];assert time.time()-p.create_time()<120
r={'pid':p.pid,'create_time':p.create_time(),'create_time_utc':datetime.datetime.fromtimestamp(p.create_time(),datetime.timezone.utc).isoformat(),
 'executable':p.exe(),'command_line':p.cmdline(),'ownership':'Immediately preceding task-issued solidworks_connect(start_if_missing=true) returned launched; prior owned instance exited; only this role submits CAD operations',
 'scope':'Only this task isolated portable assemblies; writer checks actual empty document session before mutation'}
out=C/'results'/('PORTABLE_SW_OWNER_'+sys.argv[1]+'.json');assert not out.exists();out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'owner_record':str(out),'pid':p.pid,'rss_mib':p.memory_info().rss/1048576}))
