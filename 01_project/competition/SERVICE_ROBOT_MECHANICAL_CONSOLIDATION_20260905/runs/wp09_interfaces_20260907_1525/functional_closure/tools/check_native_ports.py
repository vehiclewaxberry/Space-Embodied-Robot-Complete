from pathlib import Path
import json,hashlib,sys,importlib.util
sys.dont_write_bytecode=True
F=Path(__file__).resolve().parents[1];R=F.parent
c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text());em=json.loads((F/'results/PORTS_EMISSION.json').read_text());nr=json.loads((F/'results/NATIVE_PORTS.json').read_text())
assert nr['status']=='PASS_NATIVE_PART_IMPORT_COLD_BOUNDS_PENDING_BREP_EQUIVALENCE'
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];parts={}
for k,v in em['parts'].items():
 parts[k]=dict(path=v['path'],sha256=v['sha256'],T_S_local=I);rt=F/'native/roundtrip'/(k+'.step');parts[k+'_rt']=dict(path=str(rt),sha256=hashlib.sha256(rt.read_bytes()).hexdigest(),T_S_local=I)
spec=importlib.util.spec_from_file_location('native_ports_geom',c['geometry_reader']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);g=m.Geometry({'parts':parts,'tolerances':c['acceptance']},{})
records=[]
for k,v in em['parts'].items():
 a=g.load(k);b=g.load(k+'_rt');fa=g.facts(a);fb=g.facts(b);diff=[g.volume(a-b),g.volume(b-a)];err=max(abs(fa['bbox_mm'][t][i]-fb['bbox_mm'][t][i]) for t in ['min_mm','max_mm'] for i in range(3));ve=abs(fa['volume_mm3']-fb['volume_mm3']);ok=fb['shape_valid'] and fb['solid_count']==1 and max(diff)<=1e-5 and err<=1e-5 and ve<=1e-5
 records.append(dict(id=k,roundtrip_material_diff_mm3=diff,bbox_error_mm=err,volume_error_mm3=ve,ok=ok,native_path=str(F/'native/parts'/(k+'.SLDPRT')),native_sha256=hashlib.sha256((F/'native/parts'/(k+'.SLDPRT')).read_bytes()).hexdigest()))
out=dict(status='PASS_NATIVE_PORTS_MATERIAL' if all(r['ok'] for r in records) else 'HOLD_NATIVE_PORTS_MATERIAL',records=records,linear_tolerance_mm=1e-5,volume_tolerance_mm3=1e-5)
(F/'results/NATIVE_PORTS_MATERIAL.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(out['status'])
