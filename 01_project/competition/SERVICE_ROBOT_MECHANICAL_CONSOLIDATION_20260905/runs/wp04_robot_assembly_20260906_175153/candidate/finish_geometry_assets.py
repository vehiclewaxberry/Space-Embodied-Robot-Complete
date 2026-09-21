from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
commands=[
    [sys.executable,'check_r07_parameters.py'],
    [sys.executable,'-c',"from r07_drawings import gen_dxf; gen_dxf()['document'].saveas('r07_interfaces.dxf')"],
    [sys.executable,'F:/codex_skill/AgentSkills/codex-skills/dxf/scripts/gen','r07_interfaces.dxf','--validate'],
    [sys.executable,'render_r07_drawing.py'],
    [sys.executable,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/inspect','refs','r07_local.step.py','--facts','--planes','--positioning'],
    [sys.executable,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/inspect','validate','r07_local.step.py'],
    [sys.executable,'render_wp04_snapshots.py']]
for cmd in commands:
    print(json.dumps(dict(command=cmd)),flush=True)
    subprocess.run(cmd,cwd=H,check=True)
