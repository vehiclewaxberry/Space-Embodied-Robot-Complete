"""Minimum-change horizontal installation: one P60 support relocates, no route/exterior change."""
from geometry import *
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID
from OCP.gp import gp_GTrsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
from OCP.BRepCheck import BRepCheck_Analyzer
rr={r['id']:r for r in state_rows()['service']};parts=[];replacements=[];poses=[]
T=np.eye(4);T[:3,3]=[-164,86,11.5]
cov=read(R6/'inputs/MAIN_GEOMETRY_COVERAGE.json');old_local=source(cov['board'])
# The imported dielectric body is 1.51 mm. The authoritative PCB total stack is
# 1.60 mm (including Cu/mask). Represent that stack envelope for mounting only.
ex=TopExp_Explorer(old_local,TopAbs_SOLID);shapes=[]
while ex.More():shapes.append(ex.Current());ex.Next()
assert len(shapes)==40
bb=np.array(g.precise_bounds(shapes[25]));assert np.allclose(bb,[[0,-80,0],[100,0,1.51]],atol=1e-5)
gt=gp_GTrsf();gt.SetValue(3,3,1.6/1.51);shapes[25]=BRepBuilderAPI_GTransform(shapes[25],gt,True).Shape();assert BRepCheck_Analyzer(shapes[25]).IsValid()
local=emit('R6H_MAIN_LOCAL_STACK_ENVELOPE',compound(shapes),'MIXED_PCBA_WITH_NOMINAL_TOTAL_STACK_ENVELOPE',bulk_PCB_material_assigned=False)
parts.append(emit('R6H_MAIN_PCBA_INSTALLED',moved(source(local),T),'MIXED_35_REF_PCBA_HORIZONTAL_CANDIDATE',local_source=local,bulk_PCB_material_assigned=False))
cov.update(board=local,mechanical_stack_envelope_mm=1.6,source_dielectric_export_mm=1.51,stack_geometry_update='Z scaling of board body only to actual nominal total stack; copper/mask not separately materialized; component XY/Z untouched',original_source_board=cov['board'])
write(D/'inputs/MAIN_GEOMETRY_COVERAGE.json',cov)
deck=source(rr['upper_equipment_deck_B']);adapter=source(rr['adapter_compute_communications']);tray=source(rr['P60_TRAY_B'])
mounts=[]
for n,(x,y) in enumerate([(4,-4),(96,-4),(4,-76),(96,-76)],1):
    X,Y=(T@np.array([x,y,0,1]))[:2];hole=cyl(1.7,-25,30,X,Y)
    deck=cut(deck,hole)
    shapes={'SPACER':cut(cyl(3,-8.5,11.5,X,Y),hole),
      'BOLT':union(cyl(1.5,-16.4,13.6,X,Y),cyl(2.75,13.6,16.6,X,Y)),
      'WASHER_TOP':cut(cyl(3.5,13.1,13.6,X,Y),hole),
      'WASHER_BOTTOM':cut(cyl(3.5,-12,-11.5,X,Y),hole),
      'NUT':c.c.r4.hex_nut(X,Y,-14.4,2.4,5.5)}
    for kind,s in shapes.items():
        parts.append(emit(f'R6H_MAIN_{kind}_{n}',s,'HORIZONTAL_INSTALLATION_HARDWARE_CANDIDATE',nominal_size={'SPACER':'OD6 ID3.4 L20','BOLT':'M3x30'}.get(kind),MPN=None))
    mounts.append(dict(id=n,S_xy_mm=[X,Y],spacer_bottom_z_mm=-8.5,PCB_bottom_z_mm=11.5,PCB_top_nominal_z_mm=13.1))
# Reuse all six original post/rod/washer/nut native files at new transforms.
P=np.eye(4);P[0,3]=-4;P[1,3]=12
for ident in [k for k in rr if k.startswith('P60_HOST_2_')]:
    r=rr[ident];M=P@np.array(r['T_S_local'])
    if ident.endswith(('_BN','_BW')):M[2,3]-=3
    if ident.endswith('_ROD'):
        r=emit(ident,cyl(1.5,-20.5,61.5,-158,92),'RELOCATED_EXTENDED_NOMINAL_M3_ROD',change_kind='MOVED_AND_LENGTHENED_ROD',nominal_length_mm=82,MPN=None,source_row=rr[ident])
        replacements.append(r);M=np.eye(4)
    poses.append(dict(r,T_S_local=M.tolist(),pose_change='P60 support 2 shifts S_X -4mm and S_Y +12mm; bottom bearing moves below existing 3mm frame angle; no nut clocking',source_T_S_local=rr[ident]['T_S_local']))
# A 5 mm local edge extension gives the relocated 8 mm support full top bearing.
# The existing spacecraft envelope, P60 box and battery/propulsion routes stay put.
tray=union(tray,box(-163,86,53,-158,98,55))
hole=cyl(1.7,-25,65,-158,92);deck=cut(deck,hole);tray=cut(tray,hole)
frame=cut(source(rr['upper_deck_angle_1_0']),hole)
for k,s,change in [('upper_equipment_deck_B',deck,'Four MAIN Ø3.4 bores plus one relocated P60 Ø3.4 bore; old holes retained'),('P60_TRAY_B',tray,'One Ø3.4 bore at S[-158,92] and local 5x12x2mm bearing tab; old hole retained'),('upper_deck_angle_1_0',frame,'One Ø3.4 aligned bore; original 3mm horizontal flange retained as lower bearing')]:
    replacements.append(emit(k,s,'LOCAL_MOUNTING_HOLE_CHANGE_ONLY',change=change))
bridge=read(R6/'inputs/INTERFACE_BRIDGE.json')['parts']
for r in bridge:
    parts.append(emit(r['id'].replace('R6_','R6H_'),source(r),r['representation_role'],material_candidate=r.get('material_candidate'),source_row=r))
ports=[]
for f in read(R6/'inputs/MAIN_POPULATION_READBACK.json')['footprints']:
    if f['ref'] in ['J204','J205','J206','J207'] or f['ref'].startswith('PORT_'):
        p=(T@np.array([f['xy_mm'][0],-f['xy_mm'][1],1.595,1]))[:3]
        ports.append(dict(ref=f['ref'],MPN_or_role=f['value'],PCB_reference_S_mm=p.tolist(),mating_contact_point_S_mm=None,wire_cut_length_mm=None,installed_ring_lug=False))
layout=dict(schema='R6H_HORIZONTAL_INSTALLATION_V1',parts=parts,replacements=replacements,pose_changes=poses,T_S_MAIN=T.tolist(),MAIN_mounts=mounts,ports=ports,
    horizontal_board=True,board_out_of_plane_tilt_deg=0,exterior_changed=False,other_equipment_poses_changed=False,battery_and_propulsion_routes_changed=False,
    relocated_P60_supports=1,local_P60_tray_extension_mm=[5,12,2],P60_support_shift_S_mm=[-4,12,0],nut_clocking_required=False,preload_strength_tool_access_qualified=False,STOP_installed=False,AUX_installed=False,electrical_connections_completed=False,ready_to_power=False,flight_ready=False)
write(D/'inputs/INSTALLATION_LAYOUT.json',layout);print('HORIZONTAL',len(parts),'new;',len(replacements),'hole/relief changes;',len(poses),'reused P60 parts repositioned',flush=True)
