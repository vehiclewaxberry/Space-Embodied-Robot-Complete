"""Bounded WP06 parameter evidence: baseline reconstruction, perturbation, restoration.

Run serially under the root-owned CAD guard. This writes only PARAMETER_PROOF.json
and independent STEP readbacks below results/parameter_geometry; it never writes
the parameter file, source geometry, C01 assembly, or C01 split parts.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import sys
import traceback
from pathlib import Path


R=Path(__file__).resolve().parents[1]
CANDIDATE=R/'candidate'
OUTPUT=R/'results/PARAMETER_PROOF.json'
GEOMETRY_OUT=R/'results/parameter_geometry'
IDENTITY=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
LINEAR_MM=1e-5
VOLUME_MM3=1e-5
PERTURBED_MATERIAL_MIN_MM3=1e-3
PERTURBATION_MM=0.25
INTEGRATION_EPS=1e-13
STRUCTURE_IDS={f'shear_web_{s}' for s in (-1,1)}|{
    f'shear_clip_{s}_150_{z}' for s in (-1,1) for z in (-94,94)}|{
    f'lower_deck_angle_{s}_1' for s in (-1,1)}
HARDWARE_IDS={f'WP06_{kind}_{s}_{z}' for kind in
              ('screw','washer_outer','washer_inner','nut')
              for s in (-1,1) for z in (-94,94)}
ALL_IDS=STRUCTURE_IDS|HARDWARE_IDS


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(data):
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUTPUT.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(temp,OUTPUT)


def local_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def centroid(g,shape):
    """Volume-weighted centroid from actual readback solids and adaptive integration."""
    masses=[];moments=[[],[],[]]
    for solid in shape.solids():
        if not solid.is_valid:
            raise RuntimeError('Invalid solid in centroid measurement')
        props=g.Props()
        error=g.GProp.VolumeProperties_s(solid.wrapped,props,Eps=g.eps,OnlyClosed=True,SkipShared=False)
        if error is None or not math.isfinite(float(error)) or error<0:
            raise RuntimeError('Adaptive centroid integration failed')
        mass=float(props.Mass());center=props.CentreOfMass()
        if not math.isfinite(mass) or mass<=0:
            raise RuntimeError('Nonpositive or nonfinite readback solid volume')
        masses.append(mass)
        for i,value in enumerate((center.X(),center.Y(),center.Z())):
            if not math.isfinite(float(value)):
                raise RuntimeError('Nonfinite readback centroid')
            moments[i].append(mass*value)
    total=math.fsum(masses)
    if total<=0:
        raise RuntimeError('Readback has no material')
    return [math.fsum(values)/total for values in moments]


def material_comparison(g,a,b):
    af,bf=g.facts(a),g.facts(b)
    valid=af['shape_valid'] and bf['shape_valid'] and af['solid_count']>0 and bf['solid_count']>0
    if not valid:
        raise RuntimeError('Material comparison requires valid positive-solid readbacks')
    forward=g.volume(a-b)
    reverse=g.volume(b-a)
    box_error=max(abs(af['bbox_mm'][edge][i]-bf['bbox_mm'][edge][i])
                  for edge in ('min_mm','max_mm') for i in range(3))
    return dict(a_facts=af,b_facts=bf,a_minus_b_mm3=forward,b_minus_a_mm3=reverse,
                bidirectional_material_difference_mm3=forward+reverse,
                bbox_max_difference_mm=box_error,
                volume_difference_mm3=abs(af['volume_mm3']-bf['volume_mm3']),
                solid_counts_equal=af['solid_count']==bf['solid_count'])


def equal_material(comparison):
    return (comparison['solid_counts_equal']
            and comparison['bidirectional_material_difference_mm3']<=VOLUME_MM3
            and comparison['bbox_max_difference_mm']<=LINEAR_MM
            and comparison['volume_difference_mm3']<=VOLUME_MM3)


def main():
    report=dict(schema='WP06_PARAMETER_PROOF_V1',status='RUNNING',
                started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                script=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),
                tolerances=dict(linear_mm=LINEAR_MM,volume_mm3=VOLUME_MM3,
                                perturb_material_min_mm3=PERTURBED_MATERIAL_MIN_MM3,
                                integration_eps=INTEGRATION_EPS),
                parameter_mutation='IN_MEMORY_DICTIONARY_ONLY',
                source_sha256_before={},generated_step_files={},phases={},
                physical_assembly_completed=False,manufacturing_release=False)
    pins=report['source_sha256_before'];snapshots={}
    parameter_path=CANDIDATE/'design_parameters.json'
    def pin(path,expected=None):
        path=Path(path).resolve();digest=sha(path)
        if expected is not None and digest!=expected:
            raise RuntimeError('Input SHA mismatch: '+str(path))
        if str(path) in pins and pins[str(path)]!=digest:
            raise RuntimeError('Input changed within proof: '+str(path))
        pins[str(path)]=digest
        return digest
    try:
        for name in ('side_joint_design.py','r01_design.py','r07_design.py','local_assembly.py','design_parameters.json'):
            pin(CANDIDATE/name)
        pin(__file__);pin(R/'tools/verify_joint_geometry.py')
        for name in ('iso4762_socket_head_cap_screw_m3x12','din125_flat_washer_m3','iso4032_hex_nut_m3'):
            pin(R/'inputs/catalog'/(name+'.step'))
        baseline_path=R/'inputs/baseline_job.json';actual_path=R/'results/LOCAL_PARTS.json'
        pin(baseline_path);pin(actual_path)
        baseline=read(baseline_path);actual=read(actual_path)
        pin(actual['source_path'],actual['source_sha256'])
        if not STRUCTURE_IDS<=set(baseline['parts']) or not ALL_IDS<=set(actual['parts']):
            raise RuntimeError('Baseline or C01 actual part coverage is incomplete')
        parameter_before=pin(parameter_path)
        P=read(parameter_path)
        if P['wp06']['joint_x_mm']!=146.0:
            raise RuntimeError('C01 nominal joint_x_mm must be 146.0 for this declared proof')
        report['parameters']=dict(path=str(parameter_path),sha256_before=parameter_before,
                                  nominal_joint_x_mm=146.0,perturbed_joint_x_mm=146.25)
        job=dict(parts={},tolerances=dict(linear_mm=LINEAR_MM,volume_mm3=VOLUME_MM3,
                                         integration_eps=INTEGRATION_EPS,rotation=1e-10))
        for prefix,source,ids in (('baseline',baseline,STRUCTURE_IDS),('actual',actual,ALL_IDS)):
            for instance in sorted(ids):
                item=copy.deepcopy(source['parts'][instance])
                digest=pin(item['path'],item.get('sha256'))
                item['sha256']=digest
                job['parts'][prefix+':'+instance]=item
        write(report)
        sys.path.insert(0,'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
        import cadgen  # noqa: F401 - guarded font loader must precede build123d.
        from build123d import export_step
        sys.path.insert(0,str(CANDIDATE))
        local=local_module('wp06_parameter_proof_local',CANDIDATE/'local_assembly.py')
        verifier=local_module('wp06_parameter_proof_verifier',R/'tools/verify_joint_geometry.py')
        g=verifier.Geometry(job,snapshots)
        GEOMETRY_OUT.mkdir(parents=True,exist_ok=True)

        def emitted(prefix,instance,shape):
            path=GEOMETRY_OUT/(prefix+'_'+instance+'.step')
            # Re-wrap before placing, so a parent-linked source cannot be copied recursively.
            detached=type(shape)(shape.wrapped)
            if detached.parent is not None or getattr(detached,'children',()):
                raise RuntimeError('Unsafe generated shape detachment')
            detached=detached.located(shape.global_location)
            export_step(detached,path)
            item=dict(path=str(path.resolve()),sha256=sha(path),T_S_local=copy.deepcopy(IDENTITY))
            key=prefix+':'+instance
            job['parts'][key]=item;report['generated_step_files'][key]=item
            return g.load(key),item

        def phase(name,shapes,expected,operation):
            rows=[]
            record=dict(status='RUNNING',expected_count=len(expected),items=rows)
            report['phases'][name]=record;write(report)
            if set(shapes)!=set(expected):
                record.update(status='FAIL',error='Generated instance set mismatch',
                              actual_ids=sorted(shapes),expected_ids=sorted(expected));write(report)
                return
            for instance in sorted(expected):
                try:
                    shape,item=emitted(name,instance,shapes[instance])
                    row=operation(instance,shape)
                    row.update(instance_id=instance,generated_step=item)
                except Exception as exc:
                    row=dict(instance_id=instance,status='ERROR',error=repr(exc),traceback=traceback.format_exc())
                rows.append(row);record['completed_count']=len(rows);write(report)
                print(json.dumps(dict(phase=name,id=instance,status=row['status']),ensure_ascii=False),flush=True)
            record['status']='PASS' if all(row['status']=='PASS' for row in rows) else 'FAIL'
            write(report)

        def compare_legacy(instance,shape):
            baseline_shape=g.load('baseline:'+instance)
            result=material_comparison(g,shape,baseline_shape)
            return dict(status='PASS' if equal_material(result) else 'FAIL',
                        comparison=result,reference=job['parts']['baseline:'+instance])

        def compare_perturbed(instance,shape):
            reference=g.load('actual:'+instance)
            if instance in STRUCTURE_IDS:
                result=material_comparison(g,shape,reference)
                ok=result['bidirectional_material_difference_mm3']>PERTURBED_MATERIAL_MIN_MM3
                return dict(status='PASS' if ok else 'FAIL',comparison=result,
                            reference=job['parts']['actual:'+instance],proof='ACTUAL_STRUCTURAL_MATERIAL_CHANGED')
            af,bf=g.facts(shape),g.facts(reference)
            ac,bc=centroid(g,shape),centroid(g,reference)
            delta=[ac[i]-bc[i] for i in range(3)]
            errors=[abs(delta[i]-(PERTURBATION_MM if i==0 else 0)) for i in range(3)]
            bbox_deltas={edge:[af['bbox_mm'][edge][i]-bf['bbox_mm'][edge][i] for i in range(3)]
                         for edge in ('min_mm','max_mm')}
            box_error=max(abs(values[i]-(PERTURBATION_MM if i==0 else 0))
                          for values in bbox_deltas.values() for i in range(3))
            valid=af['shape_valid'] and bf['shape_valid'] and af['solid_count']>0 and af['solid_count']==bf['solid_count']
            volume_error=abs(af['volume_mm3']-bf['volume_mm3'])
            ok=valid and max(errors)<=LINEAR_MM and box_error<=LINEAR_MM and volume_error<=VOLUME_MM3
            return dict(status='PASS' if ok else 'FAIL',proof='ACTUAL_HARDWARE_X_TRANSLATION',
                        perturbed_facts=af,reference_facts=bf,centroid_delta_mm=delta,
                        centroid_max_translation_error_mm=max(errors),bbox_delta_mm=bbox_deltas,
                        bbox_max_translation_error_mm=box_error,volume_difference_mm3=volume_error,
                        reference=job['parts']['actual:'+instance])

        def compare_restored(instance,shape):
            reference=g.load('actual:'+instance)
            result=material_comparison(g,shape,reference)
            return dict(status='PASS' if equal_material(result) else 'FAIL',
                        comparison=result,reference=job['parts']['actual:'+instance])

        legacy=copy.deepcopy(P);legacy.pop('wp06')
        phase('legacy',local.design.build_changed(legacy),STRUCTURE_IDS,compare_legacy)
        perturbed=copy.deepcopy(P);perturbed['wp06']['joint_x_mm']=146.25
        phase('perturbed',local.parts(perturbed,include_context=False),ALL_IDS,compare_perturbed)
        # Reload the unchanged original file: restoration is a new generation, not reused shapes.
        if sha(parameter_path)!=parameter_before:
            raise RuntimeError('Parameter file changed before restoration')
        restored=read(parameter_path)
        phase('restored',local.parts(restored,include_context=False),ALL_IDS,compare_restored)
        report['status']='PASS' if all(v['status']=='PASS' for v in report['phases'].values()) else 'FAIL'
    except Exception as exc:
        report.update(status='INCOMPLETE',error=repr(exc),traceback=traceback.format_exc())
    finally:
        after={};mismatches=[]
        for path,before in pins.items():
            digest=sha(path) if Path(path).is_file() else None
            after[path]=digest
            if digest!=before:
                mismatches.append(dict(path=path,before=before,after=digest))
        report['source_sha256_after']=after
        report['source_files_unchanged']=not mismatches
        report['source_mismatches']=mismatches
        report['readback_sha256']=snapshots
        if 'parameters' in report:
            report['parameters']['sha256_after']=sha(parameter_path) if parameter_path.is_file() else None
            report['parameters']['file_unchanged']=report['parameters']['sha256_before']==report['parameters']['sha256_after']
        if mismatches:
            report['status']='FAIL'
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        write(report)
    print(json.dumps(dict(status=report['status'],output=str(OUTPUT)),ensure_ascii=False),flush=True)
    return 0 if report['status']=='PASS' else 2


if __name__=='__main__':
    raise SystemExit(main())
