"""Build four R01 forms and128 source-frame leaves, ONLY when --build-cad is given.

Prepared by mass subtask; root runs this sequentially with its CAD worker.
Does not modify frozen N, original source, native parts or any assembly.
"""
from pathlib import Path
import argparse, hashlib, json, math, sys

sys.dont_write_bytecode = True
C = Path(__file__).resolve().parents[1]
PLAN = C / 'mass/R01_GEOMETRY_DELTA_PLAN.json'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def position(point, axis, amount):
    return tuple(point[i] + axis[i] * amount for i in range(3))

def canonical_form(spec):
    # Lazy import: --help, --check-plan, and source preparation never open OCC.
    from build123d import Cylinder, Location, RegularPolygon, extrude
    kind = spec['kind']
    if kind == 'screw':
        L = spec['length_mm']
        h = spec['head_h_mm']
        s = Cylinder(1.5, L).moved(Location((0,0,-L/2))) + Cylinder(spec['head_d_mm']/2,h).moved(Location((0,0,h/2)))
        depth = spec['model_socket_depth_mm']
        hexagon = RegularPolygon(spec['model_socket_AF_mm']/math.sqrt(3),6,major_radius=True)
        cutter = extrude(hexagon,amount=depth+.02).moved(Location((0,0,h-depth)))
        return s-cutter
    if kind == 'washer':
        return Cylinder(spec['od_mm']/2,spec['thickness_mm']) - Cylinder(spec['id_mm']/2,spec['thickness_mm']+.1)
    if kind == 'nut':
        h = spec['thickness_mm']
        s = extrude(RegularPolygon(spec['af_mm']/math.sqrt(3),6,major_radius=True),amount=h).moved(Location((0,0,-h/2)))
        return s-Cylinder(spec['model_threadless_bore_mm']/2,h+.1)
    raise ValueError(kind)

def gen_step(variant='SCREW_M3X10'):
    """Optional source entry for parent-created .step.py wrapper; canonical reference only."""
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    return canonical_form(plan['variants'][variant])

def occurrence_origin(row):
    component=row['component']
    if component == 'screw':
        t=row['head_bearing_axis_t_mm']
    elif component == 'washer_head':
        t=row['head_bearing_axis_t_mm']-.25
    elif component == 'washer_nut':
        t=-3-.25
    elif component == 'nut':
        t=-3-.5-1.2
    else:
        raise ValueError(component)
    return position(row['axis_point_S_mm'],row['axis_S'],t)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-cad',action='store_true')
    parser.add_argument('--check-plan',action='store_true')
    parser.add_argument('--canonical-only',action='store_true',help='Four reference solids only; does not fulfill128 source-frame replacement contract.')
    args=parser.parse_args()
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    assert sha(plan['selection_file']) == plan['selection_sha256'], 'Selection changed; regenerate plan intentionally before CAD execution.'
    identities={x['id'] for x in plan['instances']}
    assert len(identities)==128 and len(plan['variants'])==4
    identity=[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]
    assert all(x['old_native_T_local_to_S']==identity for x in plan['instances'])
    if not args.build_cad:
        print(json.dumps(dict(status='PLAN_CHECK_PASS_NO_CAD_IMPORT',identities=len(identities),forms=4,all_original_T_preserved=True,build_executed=False)))
        return
    out=Path(plan['output_dir']).resolve()
    allowed=(C/'mass/r01_geometry_delta').resolve()
    assert out==allowed, 'Output outside owned delta path'
    out.mkdir(parents=True,exist_ok=True)
    # A receipt must never be silently overwritten; parent chooses a new revision if required.
    receipt_path=out/('CANONICAL_BUILD_RECEIPT.json' if args.canonical_only else 'BUILD_RECEIPT.json')
    if receipt_path.exists():
        raise FileExistsError(str(receipt_path))
    from build123d import Plane, export_step, import_step
    forms={}
    receipts=[]
    def emit(shape, target, expected_v, meta):
        assert shape.is_valid and len(shape.solids())==1
        volume=float(shape.volume)
        assert abs(volume-expected_v)<1e-7, (target.name,volume,expected_v)
        if target.exists():
            raise FileExistsError(str(target))
        shape.label=meta['id']
        export_step(shape,str(target))
        restored=import_step(str(target))
        assert restored.is_valid and len(restored.solids())==1
        assert abs(float(restored.volume)-expected_v)<1e-6
        bb=restored.bounding_box()
        fact=dict(meta,step_path=str(target),sha256=sha(target),volume_mm3=float(restored.volume),density_kg_mm3=7.85e-6,material_mass_kg=float(restored.volume)*7.85e-6,shape_valid=True,solid_count=1,STEP_readback_validated=True,bounds_mm={'min_mm':list(bb.min),'max_mm':list(bb.max)},representation_role='SIMPLIFIED_PROXY',geometry_model='SELECTED_STANDARD_NOMINAL_THREADLESS_PROXY',as_built_mass_kg=None)
        receipts.append(fact)
        del restored
        return fact
    canonical=out/'canonical';canonical.mkdir(exist_ok=True)
    for name,spec in plan['variants'].items():
        shape=canonical_form(spec)
        emit(shape,canonical/(name+'.step'),spec['corrected_proxy_volume_mm3'],{'id':name,'scope':'REFERENCE_FORM_NOT_CURRENT_ASSEMBLY_INSTANCE','supplier_article':spec['supplier_article']})
        forms[name]=shape
    if not args.canonical_only:
        leaves=out/'source_frame';leaves.mkdir(exist_ok=True)
        for row in plan['instances']:
            origin=occurrence_origin(row)
            shape=forms[row['variant']].moved(Plane(origin=origin,z_dir=tuple(row['axis_S'])).location)
            emit(shape,leaves/(row['id']+'.step'),row['corrected_proxy_analytic_volume_mm3'],dict(id=row['id'],variant=row['variant'],scope='SOURCE_FRAME_REPLACEMENT_REQUIRES_PARENT_ASSEMBLY_VALIDATION',old_source_sha256=row['source_step_sha256'],native_T_local_to_S=row['old_native_T_local_to_S'],supplier_article=row['supplier_article'],same_id_and_same_T=True,canonical_datum_origin_in_old_source_frame_mm=origin))
    physical_rows=[x for x in receipts if x['scope'].startswith('SOURCE_FRAME')]
    result=dict(status='PASS_SOURCE_PART_GEOMETRY_ONLY',source_plan=str(PLAN),source_plan_sha256=sha(PLAN),generator_sha256=sha(__file__),canonical_forms=4,source_frame_leaves=len(physical_rows),physical_mass_kg=sum(x['material_mass_kg'] for x in physical_rows) if physical_rows else None,canonical_forms_not_added_to_mass=True,original_instance_count_change=0,original_source_modified=False,N_modified=False,CAD_executed=True,native_assembly_integrated=False,tool_path_interference_verified=False,snapshot_review='PENDING_PARENT_CAD_WORKER',manufacturing_release=False,rows=receipts)
    receipt_path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','canonical_forms','source_frame_leaves','physical_mass_kg']}))

if __name__=='__main__':
    main()
