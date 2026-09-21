"""Source-bound C203 installation BOM including wire and lacing delta."""
from pathlib import Path
import csv,json,hashlib,copy
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
plan='mechanical/CAP_HARNESS_RETAINED_PLAN_V21.json';p=json.loads((A/plan).read_text())
rows={r['id']:r for r in p['states']['service']['rows']};parent='mechanical/INPUT_CAP_INSTALLATION_BOM.csv'
old=list(csv.DictReader((A/parent).open(encoding='utf-8-sig')))
out=[]
for x in old:
 r=rows[x['instance_id']];v=copy.deepcopy(x);v.update(source_STEP=str(Path(r['step_path']).relative_to(A)),source_sha256=r['source_sha256'])
 if v['instance_id']=='C203_LOWER_B':v.update(MPN='PROJECT_C203_LOWER_B_RETAINED_V21',status='NOMINAL_PEEK_GEOMETRY;STOCK_ALLOWABLE_CREEP_AND_LOAD_OPEN')
 if v['instance_id']=='C203_PCB':v['status']='V20_SOURCE_BOUND_PTH_GEOMETRY_DRC_CLEARED;PROCESS_OPEN'
 out.append(v)
for suffix in ['PLUS','MINUS']:
 for prefix,mpn,status in [('C203_W_','55A0111-18-9','ONE_WHITE_18AWG_WIRE;CUT_LENGTH_52.763077_MM_NOMINAL;TOLERANCE_PROCESS_OPEN'),('C203_LACE_','LTHT3A4NA','ONE_TIE;150_MM_PROJECT_CUT_ALLOWANCE;KNOT_AND_GRIP_OPEN;NOT_ONE_REEL')]:
  name=prefix+suffix;r=rows[name]
  out.append(dict(instance_id=name,electrical_ref='',MPN=mpn,quantity='1',source_STEP=str(Path(r['step_path']).relative_to(A)),source_sha256=r['source_sha256'],status=status))
assert {r['id'] for r in rows.values() if r['id'].startswith('C203_')}=={r['instance_id'] for r in out}
assert len(out)==len({r['instance_id'] for r in out})
target='mechanical/CAP_HARNESS_BOM_V21.csv'
with (A/target).open('w',encoding='utf-8-sig',newline='') as f:
 wr=csv.DictWriter(f,fieldnames=list(out[0]));wr.writeheader();wr.writerows(out)
report=dict(schema='WP10_CAP_RETENTION_BOM_V21',input_hashes={q:sha(q) for q in [plan,parent,'tools/write_cap_retention_bom_v21.py']},output=target,output_sha256=sha(target),rows=len(out),all_cap_instances_covered=True,source_paths_and_hashes_rebound=True,procurement_authorized=False,quantity_basis='Each wire or tie is one installed piece; tape cut allowance is 150 mm each, not 1 reel. Existing electrical C203 is not double-counted.')
(A/'results/CAP_RETENTION_BOM_CHECK_V21.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(rows=len(out),all_cap_instances_covered=True)))

