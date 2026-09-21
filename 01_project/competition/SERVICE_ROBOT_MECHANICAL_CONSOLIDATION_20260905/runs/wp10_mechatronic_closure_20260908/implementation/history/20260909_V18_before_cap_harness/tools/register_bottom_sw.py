from pathlib import Path
import psutil,time,json,sys
A=Path(__file__).resolve().parents[1];phase=sys.argv[1];assert phase in ['import','assemble','cold'];dataset=sys.argv[2] if len(sys.argv)>2 else 'BOTTOM';assert dataset in ['BOTTOM','COLD']
out=A/'results'/f'NATIVE_{dataset}_OWNER_{phase.upper()}.json';assert not out.exists()
items=[p for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower()=='sldworks.exe'];assert len(items)==1;p=items[0];assert time.time()-p.create_time()<120
r=dict(pid=p.pid,create_time=p.create_time(),executable=p.exe(),command_line=p.cmdline(),ownership='Immediately preceding solidworks_connect returned launched; sole root CAD writer; empty document precondition enforced by build_bottom_native.py',phase=phase)
out.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(dict(owner_path=str(out),pid=p.pid,available_mib=psutil.virtual_memory().available/2**20)))
