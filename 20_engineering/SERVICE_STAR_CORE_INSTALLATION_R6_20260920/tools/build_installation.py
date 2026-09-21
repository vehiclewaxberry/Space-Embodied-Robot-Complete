from geometry import *
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
pose=read(D/'inputs/MAIN_INSTALL_POSE.json');assert not pose['hits'] and not pose['unknown'];T=np.array(pose['T_S_core'])
rows=state_rows()['service'];rr={r['id']:r for r in rows};parts=[];replacements=[]
pcba=read(D/'inputs/MAIN_GEOMETRY_COVERAGE.json')['board']
parts.append(emit('R6_MAIN_PCBA_INSTALLED',moved(source(pcba),T),'SOURCE_BOUND_MIXED_35_REF_PCBA_CANDIDATE',source_local_row=pcba,installed=True,electrically_qualified=False))
rail=[]
for x in [4,96]:
 r=box(x-3,-78,-7.5,x+3,-2,-5.5)
 for y in [-4,-76]:r=cut(r,cyl(1.7,-16,10,x,y))
 if x==4:
  # Third corner has a P60 post below it: use a flush reverse countersunk bolt.
  # Local R4 pad leaves 1 mm radial material beyond the R3 countersink mouth.
  r=union(r,cut(cyl(4,-7.5,-5.5,4,-76),cyl(1.7,-16,10,4,-76)))
  cone=BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(4,-76,-7.5),gp_Dir(0,0,1)),3,1.5,1.7).Shape()
  r=cut(r,cone)
 rail.append(moved(r,T))
for x0,x1 in [(1,13),(83,99)]:rail.append(moved(box(x0,-44,-7.5,x1,-36,-5.5),T))
deck=source(rr['upper_equipment_deck_B']);adapter=source(rr['adapter_compute_communications']);bases=[]
for n,x in enumerate([10,86],1):
 p=(T@np.array([x,-40,-6.5,1]))[:3];X,Y=p[:2]
 post=box(X-3,Y-4,-6.5,X+3,Y+4,14);hole=cyl(1.7,-20,30,X,Y);rail.append(post)
 deck=cut(deck,hole);adapter=cut(adapter,hole);bases.append({'n':n,'xy_mm':[X,Y],'foot_z_mm':-6.5,'top_z_mm':14,'bore_mm':3.4})
 bolt=union(cyl(1.5,-12,18,X,Y),cyl(2.75,-15,-12,X,Y))
 for kind,s in [('BASE_BOLT',bolt),('BASE_WASHER_BOTTOM',cut(cyl(3.5,-12,-11.5,X,Y),hole)),('BASE_WASHER_TOP',cut(cyl(3.5,14,14.5,X,Y),hole)),('BASE_NUT',c.r4.hex_nut(X,Y,14.5,2.4,5.5))]:
  parts.append(emit(f'R6_MAIN_{kind}_{n}',s,'INSTALLATION_HARDWARE_CANDIDATE',MPN=None,thread_geometry='smooth nominal cylinder; sourcing/preload not qualified'))
carrier=rail[0]
for s in rail[1:]:carrier=union(carrier,s)
for b in bases:carrier=cut(carrier,cyl(1.7,-20,30,*b['xy_mm']))
for b in bases:carrier=cut(carrier,cyl(3.6,14,24,*b['xy_mm']))
parts.append(emit('R6_MAIN_ANGLED_CARRIER',carrier,'TWO_INDEPENDENT_MACHINED_SUPPORTS_CANDIDATE',material_candidate='6061 Alloy',physical_support_quantity=2,countersink_nominal_radial_ligament_mm=1.0,manufacturing_drawing_released=False))
for n,(x,y) in enumerate([(4,-4),(96,-4),(4,-76),(96,-76)],1):
 hole=cyl(1.7,-20,10,x,y)
 geometries={'SPACER':cut(cyl(3,-5.5,0,x,y),hole),
 'BOLT':union(cyl(1.5,-11.905,2.095,x,y),cyl(2.75,2.095,5.095,x,y)),
 'WASHER_TOP':cut(cyl(3.5,1.595,2.095,x,y),hole),
 'WASHER_BOTTOM':cut(cyl(3.5,-8,-7.5,x,y),hole),'NUT':c.r4.hex_nut(x,y,-10.4,2.4,5.5)}
 if n==3:
  geometries.pop('WASHER_BOTTOM')
  geometries['NUT']=c.r4.hex_nut(x,y,2.095,2.4,5.5)
  geometries['BOLT']=union(cone,cyl(1.5,-5.8,6.5,x,y))
 for kind,s in geometries.items():parts.append(emit(f'R6_MAIN_PCB_{kind}_{n}',moved(s,T),'INSTALLATION_HARDWARE_CANDIDATE',nominal_size=('M3x14_COUNTERSUNK_REVERSED' if n==3 else 'M3x14') if kind=='BOLT' else None,MPN=None))
replacements.append(emit('upper_equipment_deck_B',deck,'PHYSICAL_GEOMETRY_DESIGN_MODIFIED',change='two3.4mm mounting bores; source R4 retained'))
replacements.append(emit('adapter_compute_communications',adapter,'PHYSICAL_GEOMETRY_DESIGN_MODIFIED',change='two3.4mm mounting bores for core carrier'))
parts += read(D/'inputs/INTERFACE_BRIDGE.json')['parts']
ports=[]
for f in read(D/'inputs/MAIN_POPULATION_READBACK.json')['footprints']:
 if f['ref'] in ['J204','J205','J206','J207'] or f['ref'].startswith('PORT_'):
  pos=(T@np.array([f['xy_mm'][0],-f['xy_mm'][1],1.595,1]))[:3]
  ports.append({'ref':f['ref'],'MPN_or_role':f['value'],'PCB_reference_S_mm':pos.tolist(),'installed_ring_lug':False,'mating_contact_point_S_mm':None,'wire_cut_length_mm':None})
write(D/'inputs/INSTALLATION_LAYOUT.json',{'schema':'R6_CORE_INSTALLATION_LAYOUT_V1','parts':parts,'replacements':replacements,'MAIN_pose':pose,'base_mounts':bases,'ports':ports,'source_board_sha256':sha(read(D/'inputs/MAIN_POPULATION_READBACK.json')['source']),
 'main_component_ref_count':35,'static_check_pending':True,'STOP_installed':False,'AUX_installed':False,'electrical_connections_completed':False,'propulsion_installation_frozen':False,'ready_to_power':False,'flight_ready':False})
print('LAYOUT',len(parts),'new parts',len(replacements),'modified support parts')
