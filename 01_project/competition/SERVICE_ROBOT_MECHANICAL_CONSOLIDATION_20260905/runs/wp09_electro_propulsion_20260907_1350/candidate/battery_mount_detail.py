"""Current battery-carrier to deck fastening; no battery device retention claim."""
from pathlib import Path
import json,sys,hashlib,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];CP=R/'inputs/BATTERY_MOUNT_CONTRACT.json'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def build():
    c=json.loads(CP.read_text());p=c['parameters'];pins=c['source_inputs']
    assert all(sha(k)==v for k,v in pins.items())
    spec=importlib.util.spec_from_file_location('battery_source_reader',c['geometry_reader']);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    g=reader.Geometry({'parts':c['sources_by_state']['service'],'tolerances':c['acceptance']},dict(pins))
    from build123d import import_step,Plane,Color,Location
    from cadgen.assembly import AssemblyHelper
    g.import_step=import_step
    parts={k:g.load(k) for k in c['replaced_ids']};meta={k:dict(operation='REPLACE_LOCAL',representation_role='PHYSICAL_GEOMETRY') for k in parts}
    for x in p['axis_x_mm']:
        for y in p['axis_y_mm']:
            # Cone virtual topØ6.4 matches measured catalogue main-cone continuation.
            cone=g.Solid.make_cone(3.2,1.7,1.5,Plane(origin=(x,y,p['adapter_top_z_mm']),z_dir=(0,0,-1)))
            parts['adapter_battery']=parts['adapter_battery']-cone
            drill=g.Solid.make_cylinder(1.7,8,Plane(origin=(x,y,-103),z_dir=(0,0,1)))
            parts['lower_equipment_deck']=parts['lower_equipment_deck']-drill
    catalog={}
    for role,row in c['catalogue_parts'].items():
        tree=import_step(row['path']);catalog[role]=type(tree)(tree.wrapped).located(tree.global_location)
    for x in p['axis_x_mm']:
        for y in p['axis_y_mm']:
            for role,z,direction in [('screw',p['screw_top_z_mm'],1),('washer',p['washer_top_z_mm'],-1),('nut',p['nut_top_z_mm'],-1)]:
                ident=f'WP09_BAT_{int(x)}_{int(y)}_{role}'
                pose=Plane(origin=(x,y,z),x_dir=(1,0,0),z_dir=(0,0,direction)).location
                parts[ident]=catalog[role].moved(pose)
                meta[ident]=dict(operation='NEW_LOCAL',representation_role='SIMPLIFIED_PROXY',catalogue_source=c['catalogue_parts'][role],
                    qualification='CATALOGUE_GEOMETRY_NOT_ACTUAL_MATERIAL_THREAD_PRELOAD')
    for ident in c['context_ids']:
        key='CONTEXT_'+ident;parts[key]=g.load(ident)
        meta[key]=dict(operation='CONTEXT_ONLY',representation_role='SIMPLIFIED_PROXY' if ident=='equipment_battery' else 'PHYSICAL_GEOMETRY')
    a=AssemblyHelper('WP09_BATTERY_CARRIER_MOUNT_LOCAL')
    for ident,s in parts.items():
        assert s.is_valid and len(s.solids())==1,ident
        color=(.16,.43,.46,.28) if 'equipment_battery' in ident else (.65,.70,.72) if ident.startswith('WP09') else (.88,.61,.26) if ident=='adapter_battery' else (.42,.48,.56)
        a.add(type(s)(s.wrapped).located(s.global_location),ident,color=Color(*color))
    assert all(sha(k)==v for k,v in pins.items())
    return parts,meta,a.build(),g
def emit():
    out=R/'results/battery_mount';out.mkdir(exist_ok=True);receipt=out/'EMISSION.json'
    assert not receipt.exists()
    parts,meta,a,g=build()
    from build123d import export_step
    rows={}
    for ident,s in parts.items():
        p=out/(ident+'.step');assert not p.exists();export_step(s,p)
        rows[ident]=dict(path=str(p),sha256=sha(p),bbox_mm=g.facts(s)['bbox_mm'],**meta[ident])
    primary=R/'candidate/battery_mount.step';assert not primary.exists();export_step(a,primary)
    data=dict(schema='WP09_BATTERY_MOUNT_EMISSION',status='EMITTED_NOT_INDEPENDENTLY_CHECKED',parts=rows,
        assembly_step=dict(path=str(primary),sha256=sha(primary)),producer_path=str(Path(__file__)),producer_sha256=sha(__file__),
        contract_path=str(CP),contract_sha256=sha(CP),instances=16,solids=16,integrated_into_wp08=False,
        battery_self_retention_verified=False,electrical_complete=False,manufacturing_release=False)
    receipt.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':data['status'],'solids':len(parts)}))
if __name__=='__main__':emit()
