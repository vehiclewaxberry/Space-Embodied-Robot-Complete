"""One current +Y rear rib connection, explicit CAD calls only.

Imports current STEP solids and removes two bores, preserving every other face.
Catalogue fasteners are distinct M3x16/washer/nut source files, not stretched M3x12.
All emitted solids use the spacecraft S frame in mm. No integration credit.
"""
from pathlib import Path
import json,hashlib,sys,importlib.util
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]
CONTRACT=R/'inputs/REAR_RIB_DESIGN_CONTRACT.json'
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load_module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def build():
    c=json.loads(CONTRACT.read_text(encoding='utf-8'))
    for path,digest in c['source_inputs'].items():
        if sha(path)!=digest:raise ValueError('Source changed: '+path)
    reader=load_module(c['geometry_reader'],'rear_source_geometry')
    g=reader.Geometry({'parts':c['sources_by_state']['service'],'tolerances':c['acceptance']},dict(c['source_inputs']))
    from build123d import import_step,Plane,Color
    g.import_step=import_step
    parts={};metadata={};p=c['parameters']
    for ident in ('rear_launch_bulkhead','rear_vertical_rib_86'):
        shape=g.load(ident)
        for z in p['axis_z_mm']:
            shape=shape-g.Solid.make_cylinder(p['clearance_hole_d_mm']/2,16,Plane(origin=(-197,p['axis_y_mm'],z),z_dir=(1,0,0)))
        if not shape.is_valid or len(shape.solids())!=1:raise ValueError('Invalid bored part: '+ident)
        parts[ident]=shape
        metadata[ident]=dict(operation='REPLACE_IN_FUTURE_LOCAL_INTEGRATION_ONLY',source=c['sources_by_state']['service'][ident],representation_role='PHYSICAL_GEOMETRY')
    catalogue={}
    for role,row in c['catalogue_parts'].items():
        tree=import_step(row['path']);shape=type(tree)(tree.wrapped).located(tree.global_location)
        if not shape.is_valid or len(shape.solids())!=1:raise ValueError('Invalid catalogue solid: '+role)
        catalogue[role]=shape
    for z in p['axis_z_mm']:
        placements=[('screw','screw',p['underhead_x_mm'],-1),
            ('washer_head','washer',p['washer_head_bottom_x_mm'],-1),
            ('washer_inner','washer',p['washer_inner_bottom_x_mm'],1),
            ('nut','nut',p['nut_bottom_x_mm'],1)]
        for role,source,x,sign in placements:
            ident=f'WP08_REAR_YPLUS_{int(z)}_{role}'
            pose=Plane(origin=(x,p['axis_y_mm'],z),x_dir=(0,1,0),z_dir=(sign,0,0)).location
            parts[ident]=catalogue[source].moved(pose)
            metadata[ident]=dict(operation='NEW_LOCAL_CANDIDATE',catalogue=c['catalogue_parts'][source],representation_role='SIMPLIFIED_PROXY',
                qualification='CATALOGUE_NOMINAL_GEOMETRY_ONLY_NO_ACTUAL_THREAD_MATERIAL_LOCKING_OR_STRENGTH')
    parts['CONTEXT_RB_end_frame_-1']=g.load('RB_end_frame_-1')
    metadata['CONTEXT_RB_end_frame_-1']=dict(operation='CONTEXT_ONLY_NOT_NEW_SPACECRAFT_PART',source=c['sources_by_state']['service']['RB_end_frame_-1'],representation_role='PHYSICAL_GEOMETRY')
    from cadgen.assembly import AssemblyHelper
    assembly=AssemblyHelper('WP08_RIGHT_REAR_RIB_LOCAL_CANDIDATE')
    for ident,shape in parts.items():
        detached=type(shape)(shape.wrapped).located(shape.global_location)
        assembly.add(detached,ident,color=Color(*((.64,.69,.73) if ident.startswith('WP08_') else (.35,.45,.52) if ident.startswith('CONTEXT_') else (.84,.62,.29))))
    for path,digest in c['source_inputs'].items():
        if sha(path)!=digest:raise ValueError('Source changed during build: '+path)
    return parts,metadata,assembly.build(),g

def emit():
    out=R/'results/rear_rib';out.mkdir(exist_ok=True)
    receipt=out/'EMISSION.json'
    if receipt.exists():raise ValueError('Existing emission protected')
    parts,metadata,assembly,g=build()
    from build123d import export_step
    rows={}
    for ident,shape in parts.items():
        path=out/(ident+'.step')
        if path.exists():raise ValueError('Existing STEP protected')
        export_step(shape,path)
        rows[ident]=dict(path=str(path),sha256=sha(path),**g.facts(shape),**metadata[ident])
    path=R/'candidate/rear_rib_connection.step'
    if path.exists():raise ValueError('Existing assembly STEP protected')
    export_step(assembly,path)
    data=dict(schema='WP08_REAR_RIB_EMISSION',status='EMITTED_NOT_INDEPENDENTLY_CHECKED',
        contract_path=str(CONTRACT),contract_sha256=sha(CONTRACT),producer_path=str(Path(__file__)),producer_sha256=sha(__file__),
        frame='S world mm; emitted part placement identity',parts=rows,
        assembly_step=dict(path=str(path),sha256=sha(path)),replacement_count=2,addition_count=8,context_count=1,
        integrated_into_wp08_three_state=False,manufacturing_release=False)
    receipt.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':data['status'],'solids':len(parts),'path':str(path)}))

if __name__=='__main__':emit()
