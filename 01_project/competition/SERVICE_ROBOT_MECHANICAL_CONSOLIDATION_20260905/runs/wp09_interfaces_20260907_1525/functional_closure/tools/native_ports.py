"""Serial SolidWorks imports. Reads frozen helper; writes only this child."""
from pathlib import Path
import sys,json,importlib.util,traceback
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parents[1];R=F.parent
spec=importlib.util.spec_from_file_location('proven_native_module',R.parent/'wp09_electro_propulsion_20260907_1350/tools/build_module_native.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
em=json.loads((F/'results/PORTS_EMISSION.json').read_text());ck=json.loads((F/'results/PORTS_CHECK.json').read_text());assert ck['status']=='PASS_SCOPED_GSE_PORT_GEOMETRY'
out=F/'results/NATIVE_PORTS.json';assert not out.exists();(F/'native/parts').mkdir(exist_ok=True);(F/'native/roundtrip').mkdir(exist_ok=True)
report=dict(status='RUNNING',coordinate_frame='S_WORLD_MM_WITH_IDENTITY_NATIVE_TRANSFORMS',parts=[],progress=[],save_attempts=[],roundtrip=[],manufacturing_release=False,source_sha256=m.sha(F/'results/PORTS_EMISSION.json'));b=None;prefs=None
try:
 b=m.ModuleBuilder(out,report);assert not b.documents(),'Existing user documents left untouched';sw=b.sw
 cmd=sw.CommandInProgress;prefs=dict(toggles={k:sw.GetUserPreferenceToggle(k) for k in (111,161,290,291,691,690,769)},strings={k:sw.GetUserPreferenceStringValue(k) for k in (8,9,10)},integers={k:sw.GetUserPreferenceIntegerValue(k) for k in (12,140,207,577,578,579,580)})
 report['preferences_before']=prefs;b.checkpoint('preferences_saved')
 for k in prefs['toggles']:sw.SetUserPreferenceToggle(k,k in (111,161,290))
 for k,v in {12:0,140:0,207:0,577:0,578:1,579:2,580:0}.items():sw.SetUserPreferenceIntegerValue(k,v)
 for k,n in ((8,'gb_part.prtdot'),(9,'gb_assembly.asmdot'),(10,'gb_a4.drwdot')):sw.SetUserPreferenceStringValue(k,str(m.TEMPLATES/n))
 sw.CommandInProgress=False
 for k,v in em['parts'].items():
  target=F/'native/parts'/(k+'.SLDPRT');assert not target.exists()
  row=dict(id=k,step_path=v['path'],source_sha256=v['sha256'],native_path=str(target),expected_solids=1,expected_local_bbox_mm=v['bbox_mm'],representation_role=v['representation_role']);b.import_part(row)
  opened=sw.OpenDoc6(str(target),1,1,'',0,0);assert opened[0] is not None and opened[1]==0;doc=b.wrap(opened[0],'IModelDoc2');b.activate(doc,target)
  rt=F/'native/roundtrip'/(k+'.step');report['roundtrip'].append(dict(id=k,**b.save_new(doc,rt)));b.close_own_saved(doc,target,m.sha(target));b.checkpoint('roundtrip',id=k)
 report['status']='PASS_NATIVE_PART_IMPORT_COLD_BOUNDS_PENDING_BREP_EQUIVALENCE'
except Exception as ex:
 report.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc());raise
finally:
 if b:
  if prefs:
   for grp,method in [('toggles','SetUserPreferenceToggle'),('strings','SetUserPreferenceStringValue'),('integers','SetUserPreferenceIntegerValue')]:
    for k,v in prefs[grp].items():getattr(b.sw,method)(k,v)
   b.sw.CommandInProgress=cmd
  report['documents_after']=[d for _,d in b.documents()]
  if not report['documents_after']:b.sw.ExitApp()
  b.checkpoint('end');b.pythoncom.CoUninitialize()
 else:out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
