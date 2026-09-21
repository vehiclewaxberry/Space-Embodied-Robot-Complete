"""Small actual native assembly, using the five material-verified parts."""
from pathlib import Path
import sys,json,importlib.util,traceback
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('d',F/'tools/integrate_ports_native.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d);h=d.h;m=d.m
out=F/'results/NATIVE_LOCAL_PORTS.json';target=F/'native/WP09F_GSE_PORTS.SLDASM';assert not target.exists() and not out.exists()
ck=json.loads((F/'results/NATIVE_PORTS_MATERIAL.json').read_text());assert ck['status']=='PASS_NATIVE_PORTS_MATERIAL';em=json.loads((F/'results/PORTS_EMISSION.json').read_text())
rows=[dict(id=q['id'],native_path=q['native_path'],native_sha256=q['native_sha256'],T_S_local=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],expected_solids=1) for q in ck['records']]
r=dict(status='RUNNING',rows=rows,new_instance_ids=[x['id'] for x in rows],parts=[],progress=[],save_attempts=[],whole_satellite=False,physical_assembly=False,manufacturing_release=False);b=None
try:
 b=h.Builder(out,r);assert not b.documents();sw=b.sw;prior=sw.CommandInProgress
 try:
  sw.CommandInProgress=True;model=b.wrap(sw.NewDocument(str(m.TEMPLATES/'gb_assembly.asmdot'),0,0.,0.),'IModelDoc2');asm=b.wrap(model,'IAssemblyDoc')
  raw=asm.AddComponents3(b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,[x['native_path'] for x in rows]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_R8,[v for x in rows for v in h.t16(x['T_S_local'])]),b.VARIANT(b.pythoncom.VT_ARRAY|b.pythoncom.VT_BSTR,['']*5)) or [];assert len(raw)==5
  for rc,row in zip(raw,rows):
   c=b.wrap(rc,'IComponent2');c.ComponentReference=row['id'];c.Name2=row['id'];assert c.Select4(True,None,False)
  asm.FixComponent();model.ClearSelection2(True);model.EditRebuild3();model.ShowNamedView2('',7);model.ViewZoomtofit2();r['native_save']=b.save_new(model,target);b.close_own_saved(model,target,r['native_save']['sha256'])
 finally:sw.CommandInProgress=prior
 opened=sw.OpenDoc6(str(target),2,1,'',0,0);assert opened[0] is not None and opened[1]==0;cold=b.wrap(opened[0],'IModelDoc2');b.activate(cold,target);_,obs=b.metadata(cold,rows,True)
 r['cold_components']=obs;assert sum(x['actual_solids'] for x in obs)==5
 deps=cold.GetDependencies2(False,True,False) or [];assert {m.normalized(deps[i+1]) for i in range(0,len(deps),2)}=={m.normalized(x['native_path']) for x in rows}
 assert all(m.sha(x['native_path'])==x['native_sha256'] for x in rows);assert m.sha(target)==r['native_save']['sha256']
 r.update(status='PASS_LOCAL_NATIVE_ASSEMBLY_5_COMPONENTS_5_ACTUAL_SOLIDS',component_count=5,actual_solid_count=5,continuous_motion=False,source_parts_material_equivalence=ck['status'],fully_editable_native_feature_history=False)
 b.close_own_saved(cold,target,m.sha(target));assert not b.documents();sw.ExitApp();b.checkpoint('completed_clean_exit')
except Exception as ex:
 r.update(status='FAILED',error=repr(ex),traceback=traceback.format_exc())
 if b:b.checkpoint('failed')
 else:out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 raise
finally:
 if b:b.pythoncom.CoUninitialize()
