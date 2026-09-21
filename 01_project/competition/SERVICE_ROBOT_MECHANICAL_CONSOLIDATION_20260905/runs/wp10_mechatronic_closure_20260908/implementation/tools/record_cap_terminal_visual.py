"""Record root's actual view_image inspection, after current images are viewed."""
from pathlib import Path
import sys,json,hashlib,datetime
A=Path(__file__).resolve().parents[1]
assert sys.argv[1:]==['--current-images-viewed'], 'Only execute after root has inspected all current outputs'
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
images=['review/C203_PCB_V17.png','review/C203_ASSEMBLY_V17.png','review/C203_TERMINAL_LAYOUT_V17.png']
export=read('results/CAP_TERMINAL_LAYOUT_EXPORT_V17.json')
assert export['board_sha256']==sha(export['board']) and all(sha(p)==h for p,h in export['outputs'].items())
for phase in ['PCB','ASSEMBLY','PCB_SHOT','ASSEMBLY_SHOT']:
    q=read('results/CAP_TERMINAL_CAD_'+phase+'_V17.json');assert q['source_sha256']==sha(q['source'])
    for r in q['results']:assert r['sha256']==sha(r.get('result',r.get('image')))
files=images+['ecad/wp10_c203_terminal.kicad_pcb','mechanical/input_cap_pcb.step','mechanical/input_cap_detail.step','mechanical/input_cap_integration.step','results/CAP_TERMINAL_LAYOUT_EXPORT_V17.json','results/CAP_TERMINAL_CAD_PCB_V17.json','results/CAP_TERMINAL_CAD_ASSEMBLY_V17.json','results/CAP_TERMINAL_CAD_PCB_SHOT_V17.json','results/CAP_TERMINAL_CAD_ASSEMBLY_SHOT_V17.json']
out=dict(schema='WP10_V17_ACTUAL_VISUAL_INSPECTION',recorded_local=datetime.datetime.now().astimezone().isoformat(),root_viewed_current_images=True,method='Root directly inspected current three PNGs using view_image',
    observations=['PCB face shows four mounting holes, two capacitor holes and two outboard wire holes; no visible unintended cut.',
    'Native mirrored B.Cu PDF shows separate positive and return branches with capacitor polarity labels individually aligned to their pads; combined ambiguous top label removed.',
    'Local STEP screenshot shows capacitor fixture and CHB after hiding seven obstructing background parts; no installed capacitor-to-CHB wire is represented.'],
    context_file_instances=37,context_visible_instances=30,hidden_only_for_view=['upper_equipment_deck_B','radiator_spreader','equipment_battery','adapter_battery','equipment_adcs_propulsion_allocation','adapter_adcs_propulsion_allocation','lower_equipment_deck_B'],
    PCB_full_geometry_validation=True,context_topology_validation=True,context_full_self_intersection_validation=False,whole_965_validation=False,
    viewer_runtime_status='FONT_FILTER_AND_NATIVE_STEP_SNAPSHOTS_WORK;_INTERACTIVE_3245_NOT_RESTARTED_TO_LIMIT_MEMORY',pending_items=[],inputs={p:sha(p) for p in files},whole_design_complete=False)
(A/'results/CAP_TERMINAL_VISUAL_REVIEW_V17.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print('Recorded actual root visual inspection and current hashes')
