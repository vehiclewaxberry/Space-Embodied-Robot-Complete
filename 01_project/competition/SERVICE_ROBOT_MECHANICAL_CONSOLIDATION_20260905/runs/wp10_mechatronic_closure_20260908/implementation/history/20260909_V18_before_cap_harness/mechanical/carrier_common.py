from pathlib import Path
from build123d import Box,Cylinder,Pos,Rot,Align,import_step,Compound,Color
PARAMS={'plate_x_mm':90.,'plate_y_mm':90.,'plate_t_mm':4.,'oem_pitch_x_mm':48.3,'oem_pitch_y_mm':50.8,'oem_clear_d_mm':4.,'frame_pitch_mm':76.,'frame_clear_d_mm':4.5,'interface_gap_mm':.229,'tim_x_mm':55.9,'tim_y_mm':59.,'tim_hole_d_mm':4.5}
def carrier():
 p=PARAMS;s=Box(p['plate_x_mm'],p['plate_y_mm'],p['plate_t_mm'],align=(Align.CENTER,Align.CENTER,Align.MIN))
 for pitchx,pitchy,d in [(p['oem_pitch_x_mm'],p['oem_pitch_y_mm'],p['oem_clear_d_mm']),(p['frame_pitch_mm'],p['frame_pitch_mm'],p['frame_clear_d_mm'])]:
  for x in [-pitchx/2,pitchx/2]:
   for y in [-pitchy/2,pitchy/2]:s-=Pos(x,y,0)*Cylinder(d/2,p['plate_t_mm'],align=(Align.CENTER,Align.CENTER,Align.MIN))
 s.label='WP10_CHB_CARRIER_6061_MODEL';s.color=Color(.68,.73,.79);return s
def thermal_pad(thickness_mm=None,material_name='TSP1600S'):
 # Project cut of TSP1600S nominal uncompressed stock; not an OEM die-cut MPN.
 p=PARAMS.copy()
 if thickness_mm is not None:p['interface_gap_mm']=thickness_mm
 s=Box(p['tim_x_mm'],p['tim_y_mm'],p['interface_gap_mm'],align=(Align.CENTER,Align.CENTER,Align.MIN))
 for x in [-p['oem_pitch_x_mm']/2,p['oem_pitch_x_mm']/2]:
  for y in [-p['oem_pitch_y_mm']/2,p['oem_pitch_y_mm']/2]:s-=Pos(x,y,0)*Cylinder(p['tim_hole_d_mm']/2,p['interface_gap_mm'],align=(Align.CENTER,Align.CENTER,Align.MIN))
 s.label='WP10_'+material_name.replace(' ','_')+'_PROJECT_CUT_UNCOMPRESSED';s.color=Color(.1,.4,.85) if thickness_mm is not None else Color(.93,.51,.60);return s

def assembly():
 m=import_step(Path(__file__).resolve().parents[1]/'sources/CHB500W_STANDARD_OEM.step')
 m=Pos(0,0,PARAMS['plate_t_mm']+PARAMS['interface_gap_mm']+1.6)*Rot(90,0,0)*m
 m.label='CHB500W_STANDARD_OEM_N_LOGIC_SAME_MECHANICAL';m.color=Color(.22,.25,.30)
 return Compound(children=[carrier(),m,Pos(0,0,PARAMS['plate_t_mm'])*thermal_pad()],label='WP10_SINGLE_CONVERTER_WITH_REAL_TIM_CANDIDATE')
