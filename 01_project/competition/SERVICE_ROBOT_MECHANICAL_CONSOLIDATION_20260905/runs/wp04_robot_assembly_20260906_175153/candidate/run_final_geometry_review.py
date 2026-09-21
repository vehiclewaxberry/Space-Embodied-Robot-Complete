from pathlib import Path
import subprocess,sys,json
H=Path(__file__).resolve().parent
commands=[
    [sys.executable,'../review/review_r07.py','--execute-geometry','--output','../review/R07_REVIEW_FINAL.json'],
    [sys.executable,'../review/r07_three_state.py','--execute-geometry','--service-review','../review/R07_REVIEW_FINAL.json','--output','../review/R07_THREE_STATE.json'],
    [sys.executable,'pose_screen.py'],
    [sys.executable,'render_r07_drawing.py']]
for cmd in commands:
    print(json.dumps(dict(command=cmd)),flush=True)
    subprocess.run(cmd,cwd=H,check=True)
