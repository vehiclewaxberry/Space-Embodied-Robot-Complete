"""Read-only HANDLE check and duplicate-receipt rejection regression."""
from pathlib import Path
import hashlib,json,subprocess,sys,psutil
from memory_reclaim_safe_v24 import K,identity,norm
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
r='results/CAP_TERMINAL_MEMORY_RECOVERY_V17_V24_hardened_20260910_a.json'
before=sha(r)
q=subprocess.run([sys.executable,'-B','-X','utf8','tools/reclaim_cap_terminal_memory.py','V24_hardened_20260910_a'],cwd=A,capture_output=True,text=True)
me=psutil.Process();h=K.OpenProcess(0x1000,False,me.pid)
try:
 assert h
 ct,exe=identity(h)
 matched=abs(ct-me.create_time())<.001 and exe==norm(me.exe())
finally:
 if h:K.CloseHandle(h)
assert q.returncode!=0 and 'FileExistsError' in q.stderr and before==sha(r) and matched
out=dict(schema='WP10_MEMORY_HARDENING_CHECK_V24',passed=True,
 duplicate_receipt_rejected_before_mutation=True,original_receipt_bytes_unchanged=True,
 current_process_HANDLE_creation_and_executable_matched=True,
 source_bindings={p:sha(p) for p in ['tools/memory_reclaim_safe_v24.py','tools/reclaim_background_checkpoint.py',
 'tools/reclaim_cap_terminal_memory.py','tools/check_memory_hardening_v24.py',r]},
 scope='Duplicate and read-only handle regression; termination branch not exercised by this test.')
(A/'results/MEMORY_CLEANUP_HARDENING_CHECK_V24.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,duplicate_rejected=True,handle_identity=True)))

