"""Repeat the bounded cleanup with unique receipts; never close working apps."""
from pathlib import Path
import sys
A=Path(__file__).resolve().parents[1]
tag=sys.argv[1];assert tag.replace('_','').isalnum()
name='BACKGROUND_MEMORY_CLEANUP_'+tag+'.json'
assert not (A/'results'/name).exists(), 'Keep prior cleanup evidence'
s=(A/'tools/reclaim_background_v21.py').read_text(encoding='utf-8-sig')
s=s.replace('BACKGROUND_MEMORY_CLEANUP_V21.json',name).replace('WP10_BACKGROUND_CLEANUP_V21','WP10_BACKGROUND_CLEANUP_CHECKPOINT')
s=s.replace("        if role:\n", "        if exe=='c:/windows/explorer.exe':role='trim_only_preserve_explorer_session'\n        if role:\n")
s=s.replace('Claude desktop resident pages trimmed only;', 'Claude desktop and Windows Explorer resident pages trimmed only;')
exec(compile(s,str(A/'tools/reclaim_background_v21.py'),'exec'),{'__file__':str(A/'tools/reclaim_background_v21.py'),'__name__':'__main__'})
