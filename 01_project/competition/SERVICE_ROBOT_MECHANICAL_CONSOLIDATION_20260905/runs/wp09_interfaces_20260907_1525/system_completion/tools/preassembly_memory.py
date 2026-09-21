"""Read-only assembly admission check. Never closes unowned applications."""
from pathlib import Path
import ctypes,json,datetime
C=Path(__file__).resolve().parents[1]
class MS(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
m=MS();m.length=ctypes.sizeof(m)
assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'available_MiB':m.available/2**20,'total_MiB':m.total/2**20,'launch_minimum_MiB':2048,'run_global_floor_MiB':512,'owned_Python_plus_SW_max_MiB':1400,'launch_allowed':m.available/2**20>=2048,'processes_closed_by_this_readonly_check':[],'execution_policy':'Fresh owned SW process per state; empty document list required; close saved owned documents and ExitApp after each state. No guarantee of infallibility; stop on guard.','prior_owned_cleanup_receipt':'PORTABLE_OWNED_STOP.json'}
p=C/'results/MEMORY_ADMISSION.json';p.write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
if not r['launch_allowed']:raise SystemExit(2)
