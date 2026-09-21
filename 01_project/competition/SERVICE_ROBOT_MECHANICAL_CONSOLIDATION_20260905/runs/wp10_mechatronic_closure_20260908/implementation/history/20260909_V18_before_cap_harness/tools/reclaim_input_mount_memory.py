from pathlib import Path
A=Path(__file__).resolve().parents[1]
p=A/'tools/reclaim_idle_tool_memory.py'
src=p.read_text(encoding='utf-8').replace('COLD_PATH_MEMORY_RECOVERY.json','INPUT_MOUNT_MEMORY_RECOVERY.json')
exec(compile(src,str(p),'exec'),{'__name__':'__main__','__file__':str(p)})
