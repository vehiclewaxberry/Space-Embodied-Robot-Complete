from pathlib import Path
import json
A=Path(__file__).resolve().parents[1];p=A/'tools/reclaim_idle_tool_memory.py'
src=p.read_text(encoding='utf-8').replace('COLD_PATH_MEMORY_RECOVERY.json','FUSE_REVIEW_MEMORY_RECOVERY.json')
exec(compile(src,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
out=A/'results/FUSE_REVIEW_MEMORY_RECOVERY.json';d=json.loads(out.read_text())
for r in d['rows']:r.pop('service_command',None)
d['command_lines_omitted_from_delivery']=True
out.write_text(json.dumps(d,indent=2),encoding='utf-8')
