"""Link CAD instance IDs, native circuit and installation-only BOM without duplicating C203."""
from pathlib import Path
import csv,json,hashlib,math,xml.etree.ElementTree as ET
A=Path(__file__).resolve().parents[1]
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
c=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');p=read('mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json');g=read('results/INPUT_CAP_MOUNT_EXACT.json');assert g['passed'] and all(sha(q)==h for q,h in g['inputs'].items())
sp=p['states']['service'];rows={r['id']:r for r in sp['rows']};bom=[]
for k in sp['added_ids']:
 r=rows[k];stem=Path(r['step_path']).stem
 bom.append(dict(instance_id=k,electrical_ref='C203' if k=='C203_BODY' else '',MPN=c['MPN'] if k=='C203_BODY' else '',quantity=1,source_STEP=Path(r['step_path']).relative_to(A).as_posix(),source_sha256=r['source_sha256'],status='EXISTING_ELECTRICAL_BOM_ITEM_BODY_ENVELOPE_ONLY_DO_NOT_ORDER_TWICE' if k=='C203_BODY' else 'PROJECT_NOMINAL_GEOMETRY_NO_MANUFACTURING_RELEASE'))
with (A/'mechanical/INPUT_CAP_INSTALLATION_BOM.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(bom[0]));w.writeheader();w.writerows(bom)
xml=ET.parse(A/'ecad/wp10_system.xml');netmap={v.get('ref')+'.'+v.get('pin'):n.get('name') for n in xml.findall('.//net') for v in n.findall('node')}
interface=dict(schema='WP10_C203_CAD_ECAD_INTERFACE_V1',bindings={q:sha(q) for q in ['mechanical/INPUT_CAP_MOUNT_DESIGN.json','mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json','results/INPUT_CAP_MOUNT_EXACT.json','ecad/wp10_system.xml','ecad/WP10_PASSIVES.pretty/CP_ChemiCon_VS_D30_P10_2mm_Candidate.kicad_mod','mechanical/INPUT_CAP_INSTALLATION_BOM.csv']},electrical_ref='C203',CAD_body_instance='C203_BODY',CAD_board_instance='C203_PCB',MPN=c['MPN'],footprint=c['native_footprint'],frame='S_mm',footprint_local_to_S=c['cap_local_to_S'],board_x_mm=c['board_x_mm'],pins=[dict(**q,native_net=netmap['C203.'+q['number']]) for q in c['pads']],board_routed=False,actual_lead_shape_bound=False,CHB_connection_complete=False,axial_retention_qualified=False,whole_design_complete=False)
dump('ecad/C203_MECHANICAL_INTERFACE.json',interface)
stack=dict(schema='WP10_C203_FASTENER_NOMINAL_STACK_V1',source_design_sha256=sha('mechanical/INPUT_CAP_MOUNT_DESIGN.json'),deck_bolt_projection_beyond_nut_mm=12-4-3-.5-2.4,lower_clamp_nominal_embed_mm=10-4,lower_blind_end_clearance_mm=2.5,board_nominal_embed_mm=8-1.6,board_blind_end_clearance_mm=.5,OEM_min_lead_projection_after_board_mm=3.5-1.6,real_thread_effective_engagement_verified=False,preload_or_PEEK_creep_verified=False,axial_antislip_verified=False)
dump('results/INPUT_CAP_FASTENER_STACK.json',stack)
print(json.dumps(dict(installation_BOM_instances=len(bom),duplicate_C203_purchase=False,interface_checks=len(g['interface_checks']))))
