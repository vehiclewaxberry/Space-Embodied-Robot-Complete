"""Serialize bounded jobs. Own child Job Object prevents orphan or allocation runaway."""
from pathlib import Path
import argparse,json,subprocess,sys,time,datetime,os
import psutil
from win_job import OwnedJob
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument("name");p.add_argument("--timeout",type=float,default=240);p.add_argument("--max-rss-mib",type=float,default=1400);p.add_argument("command",nargs=argparse.REMAINDER);a=p.parse_args()
cmd=a.command[1:] if a.command[:1]==["--"] else a.command
if not cmd:raise ValueError("Missing command")
if a.max_rss_mib>1400:raise ValueError("Run hard cap may not be increased")
floor=512;v=psutil.virtual_memory()
receipt=dict(name=a.name,command=cmd,cwd=str(R/"candidate"),started_local=datetime.datetime.now().astimezone().isoformat(),available_start_mib=v.available/2**20,total_mib=v.total/2**20,available_floor_mib=floor,max_child_tree_rss_mib=a.max_rss_mib,windows_job_commit_limit_mib=a.max_rss_mib,kill_own_tree_on_monitor_exit=True,timeout_s=a.timeout,guard_basis="THIS_RUN_DECLARED_BOUND; hard OS allocation limit and exception cleanup added after monitor WinError1455",samples=[])
out=R/"logs"/(a.name+".stdout.log");err=R/"logs"/(a.name+".stderr.log");record=R/"logs"/(a.name+".run.json")
def save():record.write_text(json.dumps(receipt,indent=2),encoding="utf-8")
receipt.update(stdout=str(out),stderr=str(err));q=None;job=None;start=time.monotonic()
try:
    if v.available/2**20<floor:receipt.update(status="RESOURCE_BLOCKED_BEFORE_START",returncode=None)
    else:
        with out.open("wb") as fo,err.open("wb") as fe:
            env=os.environ.copy();env.update(CADGEN_COMPONENT_WORKERS="1",OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1",MKL_NUM_THREADS="1",PYTHONUTF8="1",PYTHONIOENCODING="utf-8")
            receipt["child_environment_limits"]={k:env[k] for k in ["CADGEN_COMPONENT_WORKERS","OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"]}
            job=OwnedJob(a.max_rss_mib)
            q=subprocess.Popen(cmd,cwd=R/"candidate",stdout=fo,stderr=fe,env=env);job.assign(q)
            receipt.update(pid=q.pid,status="RUNNING");save()
            root=psutil.Process(q.pid);reason=None
            while q.poll() is None:
                try:rss=sum(x.memory_info().rss for x in [root,*root.children(recursive=True)] if x.is_running())/2**20
                except psutil.NoSuchProcess:rss=0
                avail=psutil.virtual_memory().available/2**20
                receipt["samples"].append(dict(elapsed_s=time.monotonic()-start,available_mib=avail,child_tree_rss_mib=rss))
                if avail<floor:reason="AVAILABLE_MEMORY_GUARD"
                elif rss>a.max_rss_mib:reason="JOB_WORKING_SET_GUARD"
                elif time.monotonic()-start>a.timeout:reason="TIMEOUT_GUARD"
                if reason:
                    job.terminate();q.wait(timeout=15);break
                time.sleep(.25)
            receipt.update(status=reason or ("COMPLETED" if q.returncode==0 else "COMMAND_FAILED"),returncode=q.returncode)
except BaseException as exc:
    receipt.update(status="MONITOR_OR_LAUNCH_ERROR_FAIL_CLOSED",error=repr(exc),returncode=None)
    if job:job.terminate()
    if q and q.poll() is None:
        try:q.terminate();q.wait(timeout=15)
        except Exception:pass
finally:
    if job:job.close()
    receipt["elapsed_s"]=time.monotonic()-start
    save()
print(json.dumps({k:v for k,v in receipt.items() if k!="samples"}))
sys.exit(0 if receipt.get("returncode")==0 else 2)
