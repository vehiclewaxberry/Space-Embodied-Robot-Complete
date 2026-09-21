from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
C=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('probe_frozen',C.parent/'tools/integrate_native_v5.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h);m=h.m
out=C/'results/NATIVE_DELTA_SW_VOLUME_PROBE.json';r=dict(status='RUNNING',progress=[],save_attempts=[]);b=h.Builder(out,r)
assert not b.documents();p=C/'cad/D000.SLDPRT';digest=m.sha(p)
opened=b.sw.OpenDoc6(str(p),1,1,'',0,0);assert opened[0] is not None and opened[1]==0
doc=b.wrap(opened[0],'IModelDoc2');b.activate(doc,p);ext=b.wrap(doc.Extension,'IModelDocExtension')
mp=b.wrap(ext.CreateMassProperty2(),'IMassProperty2');mp.UseSystemUnits=True
r['accuracy_sweep']=[]
for a in (0,1,2):
 mp.AccuracyLevel=a;mp.Recalculate();r['accuracy_sweep'].append(dict(requested=a,actual=mp.AccuracyLevel,volume_mm3=mp.Volume*1e9))
r['roundtrip']=b.save_new(doc,C/'cad/D000_probe.step')
assert m.sha(p)==digest
b.close_own_saved(doc,p,digest);assert not b.documents();b.sw.ExitApp();r['status']='SW_VOLUME_ACCURACY_SWEEP_COMPLETED';b.checkpoint('finished');b.pythoncom.CoUninitialize()
