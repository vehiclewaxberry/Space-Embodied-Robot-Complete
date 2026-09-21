"""Serialize bounded jobs. Own child Job Object prevents orphan or allocation runaway."""
from pathlib import Path
import argparse,json,subprocess,sys,time,datetime,os
import psutil
from portable_win_job import OwnedJob
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument("name");p.add_argument("--timeout",type=float,default=240);p.add_argument("--max-rss-mib",type=float,default=1400);p.add_argument('--sw-owner',type=Path);p.add_argument("command",nargs=argparse.REMAINDER);a=p.parse_args()
cmd=a.command[1:] if a.command[:1]==["--"] else a.command
if not cmd:raise ValueError("Missing command")
if a.max_rss_mib>1400:raise ValueError("Run hard cap may not be increased")
floor=512;v=psutil.virtual_memory()
receipt=dict(name=a.name,command=cmd,cwd=str(R),started_local=datetime.datetime.now().astimezone().isoformat(),available_start_mib=v.available/2**20,total_mib=v.total/2**20,available_floor_mib=floor,max_child_tree_rss_mib=a.max_rss_mib,windows_job_commit_limit_mib=a.max_rss_mib,kill_own_tree_on_monitor_exit=True,timeout_s=a.timeout,guard_basis="THIS_RUN_DECLARED_BOUND; hard OS allocation limit and exception cleanup added after monitor WinError1455",samples=[])
out=R/"logs"/(a.name+".stdout.log");err=R/"logs"/(a.name+".stderr.log");record=R/"logs"/(a.name+".run.json")
def save():record.write_text(json.dumps(receipt,indent=2),encoding="utf-8")
receipt.update(stdout=str(out),stderr=str(err));q=None;job=None;start=time.monotonic();owned_sw=None
if a.sw_owner:
    ownership=json.loads(a.sw_owner.read_text());owned_sw=psutil.Process(ownership['pid'])
    assert owned_sw.name().casefold()=='sldworks.exe' and abs(owned_sw.create_time()-ownership['create_time'])<.01
    receipt.update(owned_sw=ownership,combined_python_and_sw_rss_limit_mib=a.max_rss_mib,
       guard_basis='Python child Windows Job commit cap plus combined Python-tree/owned-COM-server RSS monitor; global512MiB; both task-owned objects stopped on timeout/error')
def stop_owned_sw():
    if owned_sw:
        try:
            if owned_sw.is_running() and abs(owned_sw.create_time()-ownership['create_time'])<.01:
                owned_sw.terminate();owned_sw.wait(timeout=15)
                receipt['owned_sw_stopped_by_guard']=True
        except psutil.NoSuchProcess:pass
try:
    if v.available/2**20<floor:receipt.update(status="RESOURCE_BLOCKED_BEFORE_START",returncode=None)
    else:
        with out.open("wb") as fo,err.open("wb") as fe:
            env=os.environ.copy();env.update(CADGEN_COMPONENT_WORKERS="1",OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1",MKL_NUM_THREADS="1",PYTHONUTF8="1",PYTHONIOENCODING="utf-8")
            receipt["child_environment_limits"]={k:env[k] for k in ["CADGEN_COMPONENT_WORKERS","OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"]}
            job=OwnedJob(a.max_rss_mib)
            q=subprocess.Popen(cmd,cwd=R,stdout=fo,stderr=fe,env=env);job.assign(q)
            receipt.update(pid=q.pid,status="RUNNING");save()
            root=psutil.Process(q.pid);reason=None
            while q.poll() is None:
                try:rss=sum(x.memory_info().rss for x in [root,*root.children(recursive=True)] if x.is_running())/2**20
                except psutil.NoSuchProcess:rss=0
                sw_rss=0
                if owned_sw:
                    try:sw_rss=owned_sw.memory_info().rss/2**20
                    except psutil.NoSuchProcess:pass
                avail=psutil.virtual_memory().available/2**20
                receipt["samples"].append(dict(elapsed_s=time.monotonic()-start,available_mib=avail,child_tree_rss_mib=rss,owned_sw_rss_mib=sw_rss,combined_rss_mib=rss+sw_rss))
                if avail<floor:reason="AVAILABLE_MEMORY_GUARD"
                elif rss+sw_rss>a.max_rss_mib:reason="COMBINED_WORKING_SET_GUARD"
                elif time.monotonic()-start>a.timeout:reason="TIMEOUT_GUARD"
                if reason:
                    job.terminate();stop_owned_sw();q.wait(timeout=15);break
                time.sleep(.25)
            receipt.update(status=reason or ("COMPLETED" if q.returncode==0 else "COMMAND_FAILED"),returncode=q.returncode)
except BaseException as exc:
    receipt.update(status="MONITOR_OR_LAUNCH_ERROR_FAIL_CLOSED",error=repr(exc),returncode=None)
    if job:job.terminate()
    stop_owned_sw()
    if q and q.poll() is None:
        try:q.terminate();q.wait(timeout=15)
        except Exception:pass
finally:
    if job:job.close()
    if receipt.get('status') not in ('COMPLETED',):stop_owned_sw()
    receipt["elapsed_s"]=time.monotonic()-start
    save()
print(json.dumps({k:v for k,v in receipt.items() if k!="samples"}))
sys.exit(0 if receipt.get("returncode")==0 else 2)
