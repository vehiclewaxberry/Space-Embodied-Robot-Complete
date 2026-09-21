from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import wrap,val,body_facts,checked_path
def main(sw,t,job):
 p=checked_path(job['path']);q=sw.OpenDoc6(str(p),1,3,'',0,0);m=wrap(q[0],'IModelDoc2',t)
 try:
  ex=wrap(m.Extension,'IModelDocExtension',t)
  return {'body':body_facts(m,t),'extension_mass_results':{str(a):ex.GetMassProperties2(a,0,False) for a in [0,1,2]}}
 finally:sw.CloseDoc(val(m,'GetTitle'))

