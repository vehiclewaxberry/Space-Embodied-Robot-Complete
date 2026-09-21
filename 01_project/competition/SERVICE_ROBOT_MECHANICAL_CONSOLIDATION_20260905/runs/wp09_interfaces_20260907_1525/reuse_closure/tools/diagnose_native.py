from pathlib import Path
import sys,json,importlib.util
sys.dont_write_bytecode=True
N=Path(__file__).resolve().parents[1];F=N.parent/'functional_closure'
s=importlib.util.spec_from_file_location('d',F/'tools/integrate_ports_native.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
r={'progress':[]};b=d.h.Builder(N/'results/NATIVE_TRANSFORM_DIAGNOSIS.json',r);m=d.m
ds=b.documents();assert len(ds)==1;md,meta=ds[0];assert Path(meta['path']).resolve()==(N/'mechanical/native/WP09R_SERVICE.SLDASM').resolve()
rows=json.loads((F/'results/NATIVE_SERVICE.json').read_text())['rows'];reg={x['id']:x for x in rows};raw=b.wrap(md,'IAssemblyDoc').GetComponents(True) or [];wrong=[]
for rc in raw:
 c=b.wrap(rc,'IComponent2');k=c.ComponentReference;q=reg[k];t=list(b.wrap(c.Transform2,'IMathTransform').ArrayData);ex=d.h.t16(q['T_S_local']);e=max(abs(a-v) for a,v in zip(t,ex))
 if e>1e-8:wrong.append(dict(id=k,actual=t,expected=ex,max_sw_units=e,part=q['native_path']))
r.update(status='READ_ONLY_DIAGNOSED',component_count=len(raw),mismatches=wrong,dirty=meta['dirty']);b.checkpoint('completed');b.pythoncom.CoUninitialize();print(json.dumps(wrong,ensure_ascii=False))
