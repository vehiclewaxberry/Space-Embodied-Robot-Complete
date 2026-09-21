from pathlib import Path
import json
H=Path(__file__).resolve().parent
p=json.loads((H/'design_parameters.json').read_text(encoding='utf-8'))
p['configuration_id']='WP04_ROBOT_ASSEMBLY_'+H.parent.name
p['r07']={'status':'NOMINAL_CONNECTION_DESIGN_NOT_MANUFACTURING_RELEASE','cap_thickness_mm':3,'left_rail_x_mm':15,'front_axial_length_mm':14,'rear_axial_length_mm':22,'material_allowables':None,'bolt_grade':None,'preload_N':None,'root_wrench_envelope_S_N_Nm':None,'actual_threads':None}
(H/'design_parameters.json').write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8')
(H/'results').mkdir(exist_ok=True)
print(p['configuration_id'])
