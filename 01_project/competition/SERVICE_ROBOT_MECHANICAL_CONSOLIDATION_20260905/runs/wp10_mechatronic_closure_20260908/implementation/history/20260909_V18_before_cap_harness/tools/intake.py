"""Continue WP10 in an isolated active candidate, preserving its sealed parent."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,csv,json,urllib.request,shutil
A=Path(__file__).resolve().parents[1];D=A.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['sources','power','mechanical','ecad','results','review']:(A/n).mkdir(exist_ok=True)
source=D/'SYSTEM_CLOSURE_MATRIX.csv'
rows=list(csv.DictReader(source.open(encoding='utf-8-sig')))
assert len([r for r in rows if r['status'] in ['INTERNAL_DESIGN_OPEN','EXTERNAL_INTERFACE_UNBOUND']])==23
fields=list(rows[0])+['execution_root_cause','next_source_edit','acceptance_action','execution_state','new_evidence']
for r in rows:
    r.update(execution_root_cause='',next_source_edit='',acceptance_action='',execution_state='UNCHANGED_PARENT_SCOPE',new_evidence='')
    if r['id'] in ['B03','A05','B05','F03','E06','H03']:
        r.update(execution_root_cause='Existing high-power battery/converter candidate requires parallel current sharing and has incomplete charge/interfaces; select a documented single high-current protected pack and single converter, integrate without claiming unknown margins.',next_source_edit='power/POWER_CHAIN.json; ecad/wp10_power_detail.kicad_sch; mechanical/power_carrier.step.py; ecad/MASTER_FROM_TO.csv',acceptance_action='Source-bound capacity/current/voltage/charge/thermal calculations; actual KiCad netlist; mounting geometry and inherited-system interface checks',execution_state='EXECUTING_POWER_SELECTION')
    elif r['id'] in ['E04','F02','G02','G03']:
        r.update(execution_root_cause='B601 official DM revision differs from current CAD reference; joint6/terminal frame and gripper travel must not be silently mixed.',next_source_edit='mechanical/B601_ENGINEERING_TREE.json; mechanical/B601_LOAD_INPUT.json',acceptance_action='Exact source/axis/frame/mass identity; deterministic forward kinematics against selected geometry; separate manufacturer reference from as-built facts',execution_state='READ_ONLY_SOURCE_INTAKE')
    elif r['id'] in ['D02','D03','D04']:
        r.update(execution_root_cause='C-POD same-model conflicting public datasheets and missing nozzle/command/mechanical ICD; published catalog page cannot supply proprietary pinout.',next_source_edit='power/PROPULSION_INTERFACE.json',acceptance_action='Single-revision actual nozzle/pin/command/install mapping; admissible allocation at task inputs',execution_state='TARGETED_PUBLIC_SOURCE_SEARCH')
with (A/'SYSTEM_CLOSURE_MATRIX.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
manifest={
 'rrc3570':'https://www.rrc-ps.com/fileadmin/Dokumente/Data-Sheets/DS_RRC3570.pdf',
 'rrc3570_4':'https://www.rrc-ps.com/fileadmin/user_upload/DS_RRC3570-4_D.pdf',
 'cincon_chb500w':'https://www.cincon.com/productdownload/Datasheet-CHB500W-series.pdf',
 'rrc_pmm35_page':'https://www.rrc-ps.com/power-management/lademanagement-module/produkt/RRC-PMM35',
 'rrc_mc35_page':'https://www.rrc-ps.com/kr/power-management/battery-connectors/product/RRC-MC35-180-30'
}
receipts=[]
for name,url in manifest.items():
    target=A/'sources'/(name+('.pdf' if '.pdf' in url else '.html'))
    try:
        if not target.exists():
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=25) as res:target.write_bytes(res.read())
        receipts.append(dict(id=name,url=url,path=str(target),bytes=target.stat().st_size,sha256=sha(target),status='FETCHED'))
    except Exception as ex:receipts.append(dict(id=name,url=url,status='FETCH_FAILED',error=repr(ex)))
(A/'sources/SOURCE_MANIFEST.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8')
(A/'results/ACTIVE_CANDIDATE.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'same_WP10_execution':True,'active_root':str(A),'sealed_parent':str(D),'source_worktable':{'path':str(source),'sha256':sha(source)},'writer':'root_only','secondary_agent':'one_read_only_checker','original_open_work_packages':23,'hardware_io':0,'full_design_complete':False},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'active':str(A),'sources':receipts},ensure_ascii=False))
