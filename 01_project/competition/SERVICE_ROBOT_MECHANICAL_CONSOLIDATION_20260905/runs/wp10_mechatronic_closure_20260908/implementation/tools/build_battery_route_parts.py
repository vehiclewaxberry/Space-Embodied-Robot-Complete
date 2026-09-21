"""Generate only explicitly requested route/support sources, one process at a time."""
from pathlib import Path
import sys,subprocess,json,argparse
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
ap=argparse.ArgumentParser();ap.add_argument('--stems',nargs='+',required=True);args=ap.parse_args();out=[]
for stem in args.stems:
    source=A/f'mechanical/{stem}.step.py';assert source.exists() and source.parent==A/'mechanical'
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/'gen'),str(source),'--write'],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for ext,s in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'battery_route_{stem}_gen.{ext}.log').write_text(s,encoding='utf-8')
    out.append(dict(stem=stem,returncode=q.returncode));print(stem,q.returncode,flush=True);assert q.returncode==0,q.stderr[-2500:]
print(json.dumps(out))
