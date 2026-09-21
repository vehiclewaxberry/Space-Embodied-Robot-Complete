"""Recover the owned, fully saved assembly after a stopped read-only inspection."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sw_actions import R,wrap,val,save,sha,write
from sw_assembly import inspect
def main(sw,t,job):
 name=job.get('name','WP05_ROBOT_SERVICE');state=job.get('state','service');target=R/'assemblies'/(name+'.SLDASM')
 mf=R/'results/PARTS_SOURCE_MANIFEST_DEDUP.json';manifest=json.loads(mf.read_text(encoding='utf-8'))
 ip=json.loads((R/'results/NATIVE_IMPORTS.json').read_text(encoding='utf-8'));imports={x['part_key']:x for x in ip['parts']}
 active=wrap(val(sw,'ActiveDoc'),'IModelDoc2',t)
 if active is not None:
  assert Path(val(active,'GetPathName')).resolve()==target.resolve()
  sw.CloseDoc(val(active,'GetTitle')) # only temporary inspection load-state changes
 q=sw.OpenDoc6(str(target),2,193,'',0,0);m=wrap(q[0],'IModelDoc2',t);assert m is not None and q[1]==0
 m.ClearSelection2(True);a=wrap(m,'IAssemblyDoc',t);assert a.LightweightAllResolved()
 before_save=save(m,t,target);sw.CloseDoc(val(m,'GetTitle'));m=None
 q=sw.OpenDoc6(str(target),2,193,'',0,0);m=wrap(q[0],'IModelDoc2',t);assert m is not None and q[1]==0
 result=inspect(sw,t,m,state,manifest['states'][state]['instances'],imports,target)
 result.update(warm_save=before_save,open_errors=q[1],open_warnings=q[2],target_sha256=sha(target),source_manifest_sha256=sha(mf),resolved_solid_total=sum(c['resolved_solid_count'] for c in result['components']))
 m.ShowNamedView2('',7);m.ViewZoomtofit2();m.GraphicsRedraw2()
 bmp=R/'screenshots'/(name+'.bmp');result['screenshot_saved']=bool(m.SaveBMP(str(bmp),1600,1200));result['screenshot']=str(bmp)
 write(R/'results'/(name+'_COLD.json'),result);sw.CloseDoc(val(m,'GetTitle'))
 return {'name':name,'component_count':result['component_count'],'status':result['status'],'screenshot_saved':result['screenshot_saved']}
