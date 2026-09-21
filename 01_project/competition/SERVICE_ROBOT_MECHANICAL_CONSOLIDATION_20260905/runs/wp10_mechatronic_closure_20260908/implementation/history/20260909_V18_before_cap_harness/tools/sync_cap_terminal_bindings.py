"""Keep current design declarations and mechanical bindings in one revision."""
from pathlib import Path
import json,hashlib,csv
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,x):(A/p).write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
d=read('power/CAP_TERMINAL_DEFINITION.json');s=read('results/CAP_TERMINAL_STACKUP.json')
assert s['native_board_sha256']==sha(d['board']) and s['layers_mm']['B.Cu']==.07 and s['layers_mm']['F.Cu']==0
d.update(finished_copper_thickness_native_bound=True,native_stackup_mm=s['layers_mm'],thickness_scope='Native nominal stackup: F.Mask .01, F.Cu 0, core1.50, B.Cu .07, B.Mask .02 mm, total1.6mm; PCB STEP is a finished-board mechanical envelope, not material-resolved laminate/copper; tolerance and material qualifications OPEN')
dump('power/CAP_TERMINAL_DEFINITION.json',d)
c=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');c['source_files']['power/CAP_TERMINAL_DEFINITION.json']=sha('power/CAP_TERMINAL_DEFINITION.json');dump('mechanical/INPUT_CAP_MOUNT_DESIGN.json',c)
rows=[]
for pin,pol,net,target in [('1','PLUS','WP10_PRECHARGED_PLUS','1'),('2','MINUS','WP10_INPUT_RETURN','4')]:
    rows.append(dict(wire_id='C203_W_'+pol,from_physical_feature='C203_PCB.WIRE_'+pol,to_electrical_pin='U203.'+target,to_physical_termination='CHB_INPUT_TERMINAL_BOARD_NOT_YET_IMPLEMENTED',net=net,wire_MPN=d['wire']['MPN'],quantity_conductors=1,cut_length_mm='',strip_length_mm='',route_complete=False,termination_qualified=False,status='SELECTED_WIRE_MATERIAL_AND_NET_ASSIGNMENT_ONLY_NOT_CUT_OR_ASSEMBLY_RELEASE'))
with (A/'power/C203_WIRE_SCHEDULE.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(dict(native_stackup_bound=True,wire_material_and_net_rows=2)))
