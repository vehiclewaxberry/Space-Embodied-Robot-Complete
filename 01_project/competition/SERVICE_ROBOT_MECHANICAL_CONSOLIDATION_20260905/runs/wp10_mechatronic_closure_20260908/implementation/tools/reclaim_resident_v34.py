"""User-authorized resident-page reclamation; never terminate apps or services."""
import psutil,sys,json,time
from pathlib import Path
import memory_reclaim_safe_v24 as m
A=Path(__file__).resolve().parents[1]
def main():
    tag=sys.argv[1];assert tag.replace('_','').isalnum()
    me=psutil.Process();user=me.username();exclude={me.pid}|{p.pid for p in me.parents()};rows=[]
    for p in psutil.process_iter():
        h=None;row={}
        try:
            if p.pid in exclude or p.username()!=user or m.session(p.pid)!=m.session(me.pid):continue
            exe=m.norm(p.exe())
            allowed=('/windowsapps/claude_' in exe and exe.endswith('/app/claude.exe')) or exe in [
              'c:/users/stude/appdata/roaming/claude/claude-code/2.1.260/claude.exe',
              'c:/program files (x86)/asus/armourydevice/asus_framework.exe',
              'c:/program files (x86)/asus/armourydevice/dll/acpowernotification/acpowernotification.exe']
            if not allowed or p.memory_info().rss<100*2**20:continue
            created=p.create_time();row=dict(pid=p.pid,exe=exe,rss_before_MiB=p.memory_info().rss/2**20)
            h=m.K.OpenProcess(0x1000|0x0100,False,p.pid)
            if not h:raise OSError('OpenProcess unavailable')
            ct,ex=m.identity(h)
            if abs(ct-created)>.001 or ex!=exe:raise OSError('Identity changed')
            row['trim_ok']=bool(m.P.EmptyWorkingSet(h))
        except (psutil.Error,OSError) as e:
            if row:row['error']=str(e)
        finally:
            if h:m.K.CloseHandle(h)
            if row:rows.append(row)
    out=dict(terminated=0,working_sets_trimmed=sum(r.get('trim_ok',False) for r in rows),
      available_after_MiB=psutil.virtual_memory().available/2**20,rows=rows,
      scope='Resident pages only; all applications, documents, service settings, and committed state preserved')
    (A/'results'/('RESIDENT_RECOVERY_V34_'+tag+'.json')).write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))
if __name__=='__main__':main()
