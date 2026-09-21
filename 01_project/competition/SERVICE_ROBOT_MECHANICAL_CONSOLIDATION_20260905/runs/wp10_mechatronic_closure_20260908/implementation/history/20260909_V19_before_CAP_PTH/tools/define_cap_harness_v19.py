"""Bind two physical C203-to-CHB wires to unchanged native endpoints."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
cap=json.loads((A/'power/CAP_TERMINAL_DEFINITION.json').read_text())
chb=json.loads((A/'power/CHB_INPUT_DEFINITION.json').read_text())
wire=cap['wire'].copy()
for k in ['installed_cut_length_mm','minimum_installation_bend_radius_mm','physical_termination_and_strain_relief_complete']:wire.pop(k,None)
wires=[]
for side,name,num in [(-1,'PLUS','1'),(1,'MINUS','4')]:
 start=next(x for x in cap['terminal_features'] if x['id']=='WIRE_'+name)
 end=next(x for x in chb['pads'] if x['id']=='CAP_'+num)
 assert start['S_face_mm'][1:]==[14*side,-64] and 'solder_exit_S_x_mm' in start
 assert end['S_xy_mm']==[-42,17.78*side]
 wires.append(dict(id='C203_W_'+name,from_feature='C203_PCB.WIRE_'+name,to_feature='CHB_INPUT_PCB.CAP_'+num,
  logical_to='U203.'+num,net=start['native_net'],
  sharp_vertices_S_mm=[[-3.9,14*side,-64],[-17,14*side,-64],[-26,17.78*side,-64],[-42,17.78*side,-64],[-42,17.78*side,-82.3]],
  bend_radius_mm=10.0,strip_start_mm=4.2,strip_end_mm=3.6,
  insulation_start_S_mm=[-8.1,14*side,-64],insulation_end_S_mm=[-42,17.78*side,-78.7],
  conductor_tip_start_S_mm=[-3.9,14*side,-64],conductor_tip_end_S_mm=[-42,17.78*side,-82.3],
  C203_solder_projection_mm=round(-3.9-start['solder_exit_S_x_mm'],9),CHB_solder_projection_mm=1.0))
inputs=['power/CAP_TERMINAL_DEFINITION.json','power/CHB_INPUT_DEFINITION.json','mechanical/C203_SURFACE_PROFILE_V19.json','ecad/wp10_c203_terminal.kicad_pcb','ecad/wp10_chb_input.kicad_pcb','ecad/wp10_system.xml','mechanical/CHB_INPUT_INSTANCE_PLAN.json',wire['source_file']]
out=dict(schema='WP10_C203_PHYSICAL_WIRING_V19',frame='S_mm',units='mm',parent_plan='mechanical/CHB_INPUT_INSTANCE_PLAN.json',wire=wire,wires=wires,
 route_intent='Separate short static wires on opposite sides of the capacitor; no claim of twisted pair, minimum inductance or qualified input stability',
 bend_basis='Project-selected 10mm centerline radius; 6.35 times maximum single-wire OD. NASA-STD-8739.4A Change4 Table7-1 is a workmanship reference, not TE installation qualification or flight compliance.',
 dimension_status='NOMINAL_DESIGN_CANDIDATE; no cut/strip manufacturing tolerance assigned',
 conductor_geometry='Maximum stranded-conductor outer envelope; not solid-copper area for resistance or mass',
 strain_relief_complete=False,physical_termination_qualified=False,geometry_verified=False,whole_design_complete=False,
 sources=dict(wire_drawing=wire['source_file'],manufacturer_installation='sources/chemi_al_precautions_2026.pdf',bend_reference_url='https://standards.nasa.gov/sites/default/files/standards/NASA/A/4/nasa-std-87394a_w_change_4_0.pdf'),inputs={p:sha(p) for p in inputs})
(A/'power/CAP_HARNESS_DEFINITION_V19.json').write_text(json.dumps(out,indent=2))
print('Two wires defined against current native board/STEP endpoints; retention remains open')
