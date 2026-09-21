"""Bounded official CAD CLI inspection; stdout is kept verbatim per target."""
from pathlib import Path
import subprocess,json,hashlib,time,os
HERE=Path(__file__).resolve().parent
PY='G:/Windows_program_file/Anaconda/python.exe'
CLI='F:/codex_skill/AgentSkills/codex-skills/cad/scripts/inspect'
def main():
    rows=[]
    for target in ['key_assembly_held','key_assembly_released','root_connection','key_assembly_context']:
        for mode in ['refs','validate']:
            args=[PY,CLI,mode,target+'.step.py']+(['--facts','--planes','--positioning'] if mode=='refs' else ['--skip-self-intersection'])
            t=time.monotonic()
            env=dict(os.environ,PYTHONUTF8='1')
            r=subprocess.run(args,cwd=HERE,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,env=env)
            out=HERE/'results'/f'{target}_{mode}.json';out.write_text(r.stdout,encoding='utf-8')
            (HERE/'results'/f'{target}_{mode}.stderr.log').write_text(r.stderr,encoding='utf-8')
            rows.append(dict(target=target,mode=mode,exit_code=r.returncode,elapsed_s=time.monotonic()-t,output=str(out.relative_to(HERE)),output_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),args=args))
            print(target,mode,r.returncode,flush=True)
    (HERE/'results/CLI_VALIDATION_RECEIPT.json').write_text(json.dumps({'runs':rows,'all_commands_succeeded':all(r['exit_code']==0 for r in rows),'skip_self_intersection':True,'meaning':'per-solid geometry validity; no whole-assembly collision or physical certification'},indent=2),encoding='utf-8')
if __name__=='__main__':main()
