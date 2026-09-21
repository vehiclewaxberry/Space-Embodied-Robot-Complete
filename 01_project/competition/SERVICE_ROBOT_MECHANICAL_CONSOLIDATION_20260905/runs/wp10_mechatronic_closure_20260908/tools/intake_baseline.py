"""Read-only intake of the complete sealed WP09 child baseline."""
import csv,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
D=Path(__file__).resolve().parents[1]
C=D.parent/'wp09_interfaces_20260907_1525/system_completion'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
manifest=C/'results/OUTPUT_SHA256.csv'
seal=read(C/'results/FINAL_INTEGRITY.json')
assert sha(manifest)==seal['manifest_sha256']
rows=list(csv.DictReader(manifest.open(encoding='utf-8-sig')))
bad=[]
for r in rows:
    p=C/r['path']
    if not p.is_file() or p.stat().st_size!=int(r['bytes']) or sha(p)!=r['sha256']:bad.append(r['path'])
assert not bad,bad
status=read(C/'results/DELIVERY_STATUS.json')
native=read(C/'results/NATIVE_DELTA_DELIVERY.json')
assert not status['whole_mechatronic_detailed_design_complete']
assert native['actual_relocated_cold_state_count']==3
keys=['results/DELIVERY_STATUS.json','review/SYSTEM_ACCEPTANCE_MATRIX.csv','results/NATIVE_DELTA_DELIVERY.json','results/MASS_ROLLFORWARD_873.json','ecad/MASTER_FROM_TO.csv','ecad/MASTER_BOM.csv','electrical_delta/wp09_stop_circuit.kicad_sch','software_native/DM_REFERENCE_CONFIG.json']
(D/'results').mkdir(exist_ok=True)
out={'schema':'WP10_BASELINE_INTAKE_V1','status':'PASS_SEALED_PARENT_SOURCE_INTEGRITY__NO_ENGINEERING_PROMOTION','utc':datetime.now(timezone.utc).isoformat(),
 'source_root':str(C),'manifest_sha256':sha(manifest),'files_checked':len(rows),'parent_mutations':0,'source_full_system_design_complete':False,'declared_open_work_packages':status['required_design_open_count'],
 'frozen_mechanical_subitem':{'leaf_parts_each':873,'top_level_containers_each':10,'original_cold_states':3,'relocated_cold_states':3,'whole_mass_known':False},
 'sources':[{'path':str(C/k),'sha256':sha(C/k)} for k in keys]}
(D/'results/INPUT_BASELINE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='sources'},ensure_ascii=False))

