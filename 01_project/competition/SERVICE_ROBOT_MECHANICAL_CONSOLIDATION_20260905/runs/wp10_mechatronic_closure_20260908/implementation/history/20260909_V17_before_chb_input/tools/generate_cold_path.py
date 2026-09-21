from pathlib import Path
import json,subprocess,sys,argparse
A=Path(__file__).resolve().parents[1];cad=Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts')
ap=argparse.ArgumentParser();ap.add_argument('--tim-upgrade',action='store_true');args=ap.parse_args()
stems=['bottom_radiator','cold_finger_tim','chb_bottom_tim','fixed_heat_installation','bottom_mount_assembly','fixed_heat_bay'] if args.tim_upgrade else ['bottom_radiator','lower_deck_bottom_mount','cold_finger_tim','fixed_heat_wall_neg','fixed_heat_wall_pos','fixed_heat_installation','bottom_mount_assembly','fixed_heat_bay']
for stem in stems:
    q=subprocess.run([sys.executable,'-B','-X','utf8',str(cad/'gen'),'mechanical/'+stem+'.step.py','--write'],cwd=A,capture_output=True,text=True,encoding='utf-8',errors='replace')
    for tag,s in [('stdout',q.stdout),('stderr',q.stderr)]:(A/'logs'/f'cold_path_gen_{stem}.{tag}.log').write_text(s,encoding='utf-8')
    print(stem,q.returncode,flush=True);assert q.returncode==0,(stem,q.stderr[-4000:])
