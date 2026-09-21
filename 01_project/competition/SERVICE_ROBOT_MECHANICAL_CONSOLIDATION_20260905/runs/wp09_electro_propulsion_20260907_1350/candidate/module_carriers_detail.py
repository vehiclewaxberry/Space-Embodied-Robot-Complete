"""Local A3200 reference carrier / non-pressure MiPS external cradle."""
from pathlib import Path
import json,hashlib,sys,importlib.util,argparse
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];CP=R/'inputs/MODULE_CARRIERS_CONTRACT.json'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def build(kind):
    c=json.loads(CP.read_text());p=c[kind];pins=c['source_inputs']
    assert all(sha(k)==v for k,v in pins.items())
    spec=importlib.util.spec_from_file_location('wp09_module_geom',c['geometry_reader']);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    g=mod.Geometry({'parts':{},'tolerances':c['acceptance']},dict(pins))
    from build123d import Plane,Color,import_step
    from cadgen.assembly import AssemblyHelper
    def box(b):return g.Solid.make_box(*(b[1][i]-b[0][i] for i in range(3)),Plane(origin=tuple(b[0])))
    def cyl(r,h,o,d=(0,0,1)):return g.Solid.make_cylinder(r,h,Plane(origin=o,z_dir=d))
    parts={};meta={}
    def add(i,s,role='PHYSICAL_GEOMETRY',**kw):
        parts[i]=s;meta[i]=dict(representation_role=role,operation='NEW_LOCAL',**kw)
    if kind=='a3200':
        carrier=box(p['carrier_box_mm']);board=box(p['board_box_mm'])
        for x,y in p['board_holes_xy_mm']:
            carrier=carrier-cyl(1.7,4,(x,y,-1));board=board-cyl(1.6,4,(x,y,4))
        for x,y in p['carrier_holes_xy_mm']:carrier=carrier-cyl(1.7,4,(x,y,-1))
        add('A3200_CARRIER',carrier)
        add('A3200_BOARD_REFERENCE',board,'SIMPLIFIED_PROXY',qualification='OEM_BOARD_OUTLINE_PLUS_DERIVED_SYMMETRIC_HOLES_NO_COMPONENT_MAP')
        catalog={}
        for role,row in c['catalogue_parts'].items():
            t=import_step(row['path']);catalog[role]=type(t)(t.wrapped).located(t.global_location)
        for n,(x,y) in enumerate(p['board_holes_xy_mm']):
            add(f'A3200_SPACER_{n}',cyl(2.75,3,(x,y,2))-cyl(1.6,3,(x,y,2)))
            for role,tag,z,sign in [('screw','SCREW',7.3,1),('washer','TOP_WASHER',6.8,1),('washer','BOTTOM_WASHER',0,-1),('nut','NUT',-.5,-1)]:
                pose=Plane(origin=(x,y,z),x_dir=(1,0,0),z_dir=(0,0,sign)).location
                add(f'A3200_{tag}_{n}',catalog[role].moved(pose),'SIMPLIFIED_PROXY',catalogue_source=c['catalogue_parts'][role],catalogue_transform=dict(origin_mm=[x,y,z],z_sign=sign))
    elif kind=='mips':
        carrier=None
        for b in p['carrier_union_boxes_mm']:carrier=box(b) if carrier is None else carrier+box(b)
        for z in p['mounting_holes_z_mm']:
            carrier=carrier-cyl(1.6,110,(3.175,-55,z),(0,1,0))
        for x,y in p['base_mount_holes_xy_mm']:carrier=carrier-cyl(1.7,5,(x,y,-5))
        add('MIPS_EXTERNAL_CRADLE',carrier,qualification='NON_PRESSURE_EXTERNAL_MACHINED_CANDIDATE')
        add('MIPS_OEM_MAX_ENVELOPE',box(p['equipment_envelope_mm']),'FUNCTIONAL_ENVELOPE',qualification='OEM_MAX_BOX_ONLY_NO_INTERNALS_OR_THREAD_DEPTH')
        for side,y in [(-1,-44.5008),(1,44.5008)]:
            for n,z in enumerate(p['mounting_holes_z_mm']):
                shim=cyl(3.5,.25,(3.175,y,z),(0,side,0))-cyl(1.6,.25,(3.175,y,z),(0,side,0))
                add(f'MIPS_INTERFACE_SHIM_{side}_{n}',shim,qualification='NOMINAL_CUSTOM_SHIM_NOT_TOLERANCE_STACK_RELEASE')
    else:raise ValueError(kind)
    assert len(parts)==p['expected_instances']
    a=AssemblyHelper('WP09_'+kind.upper()+'_LOCAL')
    for ident,s in parts.items():
        assert s.is_valid and len(s.solids())==1,ident
        role=meta[ident]['representation_role']
        col=(.12,.48,.39) if 'BOARD' in ident else (.16,.51,.56,.24) if role=='FUNCTIONAL_ENVELOPE' else (.74,.53,.26) if 'CARRIER' in ident or 'CRADLE' in ident else (.68,.72,.76)
        a.add(type(s)(s.wrapped).located(s.global_location),ident,color=Color(*col))
    assert all(sha(k)==v for k,v in pins.items())
    return parts,meta,a.build(),g
def emit(kind):
    out=R/'results'/kind;out.mkdir(exist_ok=True);receipt=out/'EMISSION.json';assert not receipt.exists()
    parts,meta,a,g=build(kind)
    from build123d import export_step
    rows={}
    for ident,s in parts.items():
        path=out/(ident+'.step');assert not path.exists();export_step(s,path)
        rows[ident]=dict(path=str(path),sha256=sha(path),bbox_mm=g.facts(s)['bbox_mm'],**meta[ident])
    primary=R/'candidate'/(kind+'_carrier.step');assert not primary.exists();export_step(a,primary)
    c=json.loads(CP.read_text())
    d=dict(schema='WP09_MODULE_LOCAL_EMISSION',module=kind,status='EMITTED_NOT_INDEPENDENTLY_CHECKED',frame=c[kind]['frame'],
      parts=rows,assembly_step=dict(path=str(primary),sha256=sha(primary)),producer_path=str(Path(__file__)),producer_sha256=sha(__file__),
      contract_path=str(CP),contract_sha256=sha(CP),instances=len(parts),solids=len(parts),
      integrated_into_wp08=False,electrical_complete=False,manufacturing_release=False)
    receipt.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(module=kind,solids=len(parts))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['a3200','mips']);emit(p.parse_args().kind)

