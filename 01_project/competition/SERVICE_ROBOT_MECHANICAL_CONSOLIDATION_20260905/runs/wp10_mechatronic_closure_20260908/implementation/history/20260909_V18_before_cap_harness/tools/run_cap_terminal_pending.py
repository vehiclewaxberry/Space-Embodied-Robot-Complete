"""Bounded serial retry after authorized cleanup; never lower the RAM guard."""
from pathlib import Path
import psutil,time,subprocess,sys,json
A=Path(__file__).resolve().parents[1]
jobs=[('assembly',sys.executable,['tools/review_cap_terminal_cad.py','assembly']),('pcb_shot',sys.executable,['tools/review_cap_terminal_cad.py','pcb_shot']),('assembly_shot',sys.executable,['tools/review_cap_terminal_cad.py','assembly_shot']),('pdf',sys.executable,['tools/export_cap_terminal_pdf.py'])]
if '--finish-silk' in sys.argv:
    root=next(p for p in A.parents if (p/'PROJECT_MAP.md').exists());kpy=str(root/'70_tools/runtime_wp09_kicad/portable/bin/python.exe')
    jobs=[(label,kpy,['tools/cap_terminal_native.py',phase]) for label,phase in [('silk','label_polarity'),('stackup','finalize'),('extract','extract')]]
    jobs += [('copper',sys.executable,['tools/check_cap_terminal_copper.py']),('interface',sys.executable,['tools/integrate_input_cap_mount.py']),('assembly_shot',sys.executable,['tools/review_cap_terminal_cad.py','assembly_shot']),('pdf',sys.executable,['tools/export_cap_terminal_pdf.py'])]
deadline=time.monotonic()+600
for phase,exe,args in jobs:
    for attempt in range(1,4):
        print(json.dumps(dict(phase=phase,attempt=attempt,waiting_for_start_MiB=2112)),flush=True)
        while psutil.virtual_memory().available/2**20<2112:
            if time.monotonic()>deadline:raise SystemExit('RESOURCE_WAIT_TIMEOUT; preserve completed source and results')
            time.sleep(5)
        name='native_delta_terminal_finish_'+phase+'_'+str(attempt)+'_v17' if '--finish-silk' in sys.argv else 'native_delta_terminal_pending_'+phase+'_'+str(attempt)+'_v17'
        code=subprocess.run([sys.executable,'-B','-X','utf8',str(A/'tools/native_delta_guard.py'),'--timeout','240',name,'--',exe,'-B','-X','utf8',*args],cwd=A).returncode
        if code==0:break
        receipt=json.loads((A/('logs/'+name+'.run.json')).read_text())
        if not receipt['status'].startswith('RESOURCE_'):raise SystemExit(code)
        subprocess.run([sys.executable,'-B','-X','utf8','tools/reclaim_cap_terminal_memory.py','pending_'+phase+'_'+str(attempt)],cwd=A,check=True)
    else:raise SystemExit('Resource retries exhausted')
print('All pending terminal visual phases complete',flush=True)
