from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import R,val,wrap,save,write
def main(sw,t,job):
 m=wrap(val(sw,'ActiveDoc'),'IModelDoc2',t)
 assert m is not None and val(m,'GetType')==2 and val(m,'GetPathName')==''
 a=wrap(m,'IAssemblyDoc',t);n=len(a.GetComponents(True) or []);assert n==275
 m.ClearSelection2(True)
 light=a.LightweightAllResolved()
 target=R/'assemblies/SERVICE_RESOURCE_INTERRUPTED_275.SLDASM'
 saved=save(m,t,target)
 result={'status':'INCOMPLETE_RESOURCE_CHECKPOINT','component_count':n,'target':str(target),'save':saved,'lightweight_api_result':light}
 write(R/'results/SERVICE_RESOURCE_CHECKPOINT.json',result)
 sw.CloseDoc(val(m,'GetTitle'))
 return result
