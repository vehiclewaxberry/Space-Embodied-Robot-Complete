from geometry import *
rr={r['id']:r for r in state_rows()['service']}
# Existing post stack fixes PCB underside at -1.5 and lower TIM top at -6.0mm.
# Capture a separate removable bridge/pad; do not falsely fill the whole old TIM area.
bridge=emit('R6_IF_THERMAL_BRIDGE',box(-120,-59,-6,-80,-37,-2),'PROJECT_THERMAL_BRIDGE_CANDIDATE',material_candidate='6061 Alloy',material_qualified=False)
pad=emit('R6_IF_TOP_ISOLATION_PAD',box(-120,-59,-2,-80,-37,-1.5),'PROJECT_INTERFACE_PAD_CANDIDATE',material_candidate=None,pad_MPN=None,electrical_isolation_verified=False)
contact=[]
for a,b in [(bridge,pad),(bridge,rr['thermal_interface_arm_drive']),(pad,rr['equipment_arm_drive'])]:
 contact.append({'a':a['id'],'b':b['id'],'gap_mm':distance(source(a),source(b)),'overlap_mm3':g.volume(common(source(a),source(b)))})
write(D/'inputs/INTERFACE_BRIDGE.json',{'parts':[bridge,pad],'gap_before_mm':4.5,'bridge_thickness_mm':4,'top_pad_installed_nominal_thickness_mm':.5,
 'nominal_contact_area_mm2':880,'contacts':contact,'actual_heat_W':None,'TIM_conductivity_W_mK':None,'contact_pressure_Pa':None,
 'dielectric_withstand_V':None,'material_ground_connection':None,'thermal_performance_pass':False,'mechanical_capture':'Existing four-point PCB stack; pad preload and PCB bending not yet qualified'})
print('BRIDGE',contact)
