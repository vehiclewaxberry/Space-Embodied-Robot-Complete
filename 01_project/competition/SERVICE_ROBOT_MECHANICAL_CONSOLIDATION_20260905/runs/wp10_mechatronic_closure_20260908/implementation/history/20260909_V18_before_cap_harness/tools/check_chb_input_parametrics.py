"""Check actual BRep response to definition perturbations without changing files."""
from pathlib import Path
import sys,json,copy,hashlib
A=Path(__file__).resolve().parents[1];sys.path.insert(0,str(A/'mechanical'))
import chb_input_common as m
d=m.config();rows=[]
def bound(kind,c):
 m.config=lambda:copy.deepcopy(c)
 s=m.make(kind);b=s.bounding_box();return dict(zmin=b.min.Z,zmax=b.max.Z,volume=s.volume,valid=s.is_valid)
s=bound('screw',d);x=copy.deepcopy(d);x['screw_underhead_length_mm']=10;t=bound('screw',x)
rows.append(dict(name='screw_8_to_10_changes_actual_shaft',baseline=s,perturbed=t,passed=abs(s['zmin']+8)<1e-6 and abs(t['zmin']+10)<1e-6 and t['volume']>s['volume']))
s=bound('spacer',d);x=copy.deepcopy(d);x['spacer_z_mm'][1]+=1;t=bound('spacer',x)
rows.append(dict(name='spacer_height_parameter_changes_actual_solid',baseline=s,perturbed=t,passed=abs(t['zmax']-s['zmax']-1)<1e-6 and t['volume']>s['volume']))
x=copy.deepcopy(d);x['spacer_stem_OD_ID_mm'][1]=3.4;t=bound('spacer',x)
rows.append(dict(name='spacer_bore_parameter_changes_actual_solid',baseline=s,perturbed=t,passed=t['volume']<s['volume']))
out=dict(passed=all(r['passed'] and r['baseline']['valid'] and r['perturbed']['valid'] for r in rows),tests=rows,inputs={p:hashlib.sha256((A/p).read_bytes()).hexdigest() for p in ['power/CHB_INPUT_DEFINITION.json','mechanical/chb_input_common.py','tools/check_chb_input_parametrics.py']},source_files_modified=False)
(A/'results/CHB_INPUT_PARAMETRICS_V18.json').write_text(json.dumps(out,indent=2));print(json.dumps(out));assert out['passed']
