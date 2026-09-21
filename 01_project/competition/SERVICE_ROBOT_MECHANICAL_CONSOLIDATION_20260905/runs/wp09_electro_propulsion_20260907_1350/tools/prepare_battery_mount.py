from pathlib import Path
import json,hashlib
R=Path(__file__).resolve().parents[1];W8=R.parent/'wp08_retention_delta_20260907_1228'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
mp=W8/'results/INTEGRATION_MANIFEST.json';m=json.loads(mp.read_text())
rc=json.loads((W8/'inputs/REAR_RIB_DESIGN_CONTRACT.json').read_text())
I=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
pins={str(p.resolve()):sha(p) for p in (mp,R/'results/CATALOGUE_M3_CSK_FACTS.json',R/'logs/catalog_countersunk_download.json',Path(__file__))}
all_states={};sources={}
for state,s in m['states'].items():
    all_states[state]=s['instances']
    sources[state]={}
    for row in s['instances']:
        assert sha(row['step_path'])==row['source_sha256']
        pins[str(Path(row['step_path']).resolve())]=row['source_sha256']
        if row['id'] in ('adapter_battery','lower_equipment_deck','equipment_battery','thermal_interface_battery'):
            sources[state][row['id']]=dict(path=row['step_path'],sha256=row['source_sha256'],T_S_local=row['T_S_local'])
    assert len(sources[state])==4
catalogue={'screw':dict(path=str((R/'inputs/catalog/iso10642_socket_countersunk_screw_m3x10.step').resolve()),part_id='iso10642_socket_countersunk_screw_m3x10'),**{k:rc['catalogue_parts'][k] for k in ('washer','nut')}}
for row in catalogue.values():
    row['sha256']=sha(row['path']);pins[str(Path(row['path']).resolve())]=row['sha256']
gp=R.parent/'wp06_side_joint_20260907_0233/tools/verify_joint_geometry.py';pins[str(gp.resolve())]=sha(gp)
c=dict(schema='WP09_BATTERY_CARRIER_MOUNT_CONTRACT',status='NOMINAL_DESIGN_CANDIDATE',frame='S_WORLD_MM',
    manifest_path=str(mp),manifest_sha256=sha(mp),geometry_reader=str(gp),source_inputs=pins,sources_by_state=sources,
    catalogue_parts=catalogue,replaced_ids=['adapter_battery','lower_equipment_deck'],
    context_ids=['equipment_battery','thermal_interface_battery'],
    parameters=dict(axis_x_mm=[-152.,-76.],axis_y_mm=[-78.,78.],axis_direction=[0,0,1],
        adapter_bottom_z_mm=-98.15,adapter_top_z_mm=-96.15,deck_bottom_z_mm=-101.15,deck_top_z_mm=-98.15,
        hole_d_mm=3.4,countersink_top_virtual_d_mm=6.4,countersink_included_angle_deg=90.,countersink_cone_depth_mm=1.5,
        csk_basis='Current catalogue conical head: r=1.5 at z=-1.7, 45deg slope -> virtual r=3.2 at flush top z=0; clearance bore r=1.7 intersects at depth1.5. Actual countersink residual cylindrical thickness=0.5mm; no strength/countersink tolerance qualification.',
        screw_top_z_mm=-96.15,screw_tip_z_mm=-106.15,washer_top_z_mm=-101.15,washer_bottom_z_mm=-101.65,
        nut_top_z_mm=-101.65,nut_bottom_z_mm=-104.05,nominal_protrusion_mm=2.1),
    assembly_sequence=['Mount battery carrier to lower deck using four countersunk screws, underside washers and nuts','Only after carrier fastening, place thermal interface and battery device; battery-to-carrier clamp design remains open'],
    tool_envelopes=dict(top_driver_d_mm=4.,top_driver_length_mm=40.,top_driver_z_min_mm=-96.15,
        bottom_socket_d_mm=8.,bottom_socket_inner_clearance_d_mm=4.,bottom_socket_length_mm=40.,bottom_socket_z_max_mm=-104.05,
        top_stage_removed_ids=['equipment_battery','thermal_interface_battery'],
        exceptions='Only corresponding fastener terminal-face contact/engagement; structural interference not exempt. Upper operation is evaluated at carrier-fastening stage with named battery and pad absent, and current final-state collisions must be reported separately.'),
    acceptance=dict(linear_mm=1e-5,volume_mm3=1e-5,integration_eps=1e-7,min_bearing_area_mm2=.01),
    unknowns=dict(actual_battery_model=None,battery_self_retention=False,material=None,preload=None,locking=None,load_case=None,
        manufacturing_tolerances=None,thermal_interface_material=None,electrical_current_profile=None),
    integrated_into_wp08=False,pressure_hardware=False,manufacturing_release=False)
out=R/'inputs/BATTERY_MOUNT_CONTRACT.json';assert not out.exists()
out.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'contract':str(out),'inputs':len(pins),'positions':4}))
