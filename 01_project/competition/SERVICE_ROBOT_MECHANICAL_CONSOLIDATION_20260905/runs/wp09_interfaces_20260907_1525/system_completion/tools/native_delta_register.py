"""Record exact fresh task-launched SolidWorks ownership."""
import sys,json,time,datetime
from pathlib import Path
import psutil
C=Path(__file__).resolve().parents[1]
rows=[p for p in psutil.process_iter(['name']) if (p.info['name'] or '').casefold()=='sldworks.exe']
assert len(rows)==1
p=rows[0];assert time.time()-p.create_time()<120
r=dict(pid=p.pid,create_time=p.create_time(),executable=p.exe(),command_line=p.cmdline(),ownership='Immediately preceding task solidworks_connect start_if_missing returned launched; sole CAD writer; session must be empty before operations')
out=C/'results'/('NATIVE_DELTA_OWNER_'+sys.argv[1]+'.json');assert not out.exists()
out.write_text(json.dumps(r,indent=2),encoding='utf-8');print(str(out))
