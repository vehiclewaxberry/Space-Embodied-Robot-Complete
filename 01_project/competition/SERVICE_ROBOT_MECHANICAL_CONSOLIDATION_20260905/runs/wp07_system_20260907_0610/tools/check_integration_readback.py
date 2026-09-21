"""Independent, bounded WP07 native/STEP readback. Run one state at a time.

Uses pure OCP STEPControl readers without CAD scene/cache helpers. All 978 solid
occurrences are counted. Only the 24 changed/added parts receive source-material
comparisons; validity or material equivalence of the remaining 573 instances is
not inferred. Existing B601 geometry holds remain unchanged.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import traceback

R=Path(__file__).resolve().parents[1]
LINEAR_MM=1e-5
VOLUME_MM3=1e-5
INTEGRATION_EPS=1e-13
IDENTITY=[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]
BASIS=[[0.,0.,0.],[10.,0.,0.],[0.,10.,0.],[0.,0.,10.]]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(temp,path)


def norm(path):
    return str(Path(path).resolve()).casefold()


def t16(T):
    return [T[i][j] for j in range(3) for i in range(3)]+[T[i][3]/1000 for i in range(3)]+[1.,0.,0.,0.]


def native_rows_check(observed,expected):
    """The same pure-metadata validator also rejects wrong transforms/missing IDs."""
    by_id={p['id']:p for p in observed};expected_by_id={p['id']:p for p in expected}
    coverage=(len(observed)==len(by_id)==597 and set(by_id)==set(expected_by_id))
    results=[]
    for instance in sorted(set(by_id)&set(expected_by_id)):
        a,e=by_id[instance],expected_by_id[instance]
        values=a.get('transform_sw16',[])
        finite=len(values)==16 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in values)
        error=max(abs(x-y) for x,y in zip(values,t16(e['T_S_local']))) if finite else None
        derived=[];point_error=None
        if finite:
            for local in BASIS:
                derived.append([sum(values[3*j+i]*local[j]*values[12] for j in range(3))+values[9+i]*1000 for i in range(3)])
            T=e['T_S_local']
            point_error=max(abs(derived[k][i]-(sum(T[i][j]*BASIS[k][j] for j in range(3))+T[i][3]))
                            for k in range(4) for i in range(3))
        direct=a.get('world_basis_points_mm')
        direct_error=None
        if direct is not None:
            if len(direct)==4 and all(len(p)==3 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in p) for p in direct):
                T=e['T_S_local']
                direct_error=max(abs(direct[k][i]-(sum(T[i][j]*BASIS[k][j] for j in range(3))+T[i][3]))
                                 for k in range(4) for i in range(3))
        checks=dict(path=norm(a.get('path',''))==norm(e['native_path']),sha256=a.get('sha256')==e['native_sha256'],
                    fixed=a.get('fixed') is True,solid_count=a.get('solid_count')==e['expected_solids'],
                    sheet_count=a.get('sheet_count')==0,transform=error is not None and error<=1e-8,
                    matrix_derived_basis=point_error is not None and point_error<=LINEAR_MM,
                    direct_com_basis_if_persisted=direct is None or (direct_error is not None and direct_error<=LINEAR_MM))
        results.append(dict(id=instance,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
                            transform_max_error=error,matrix_derived_basis_max_error_mm=point_error,
                            matrix_derived_world_basis_points_mm=derived,
                            direct_com_basis_status='NOT_PERSISTED_IN_PRODUCER_RECEIPT' if direct is None else 'ACTUAL_VECTORS_CHECKED',
                            direct_com_basis_error_mm=direct_error,
                            producer_reported_basis_error_mm=a.get('world_basis_error_mm')))
    total=sum(p.get('solid_count',0) for p in observed)
    dependency_count=len({norm(p.get('path','')) for p in observed})
    ok=coverage and total==978 and dependency_count==445 and all(p['status']=='PASS' for p in results)
    return dict(status='PASS' if ok else 'FAIL',coverage_pass=coverage,
                actual_id_count=len(by_id),actual_component_count=len(observed),actual_solid_count=total,
                actual_unique_dependencies=dependency_count,results=results,
                independent_scope='STORED_ACTUAL_NATIVE_PATHS_HASHES_BODY_COUNTS_AND_TRANSFORM_MATRICES; DIRECT_COM_POINT_VECTORS_ONLY_IF_PRESENT')


class Kernel:
    def __init__(self):
        from OCP.STEPControl import STEPControl_Reader
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopoDS import TopoDS
        from OCP.BRepBndLib import BRepBndLib
        from OCP.Bnd import Bnd_Box
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
        from OCP.gp import gp_Trsf
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        self.Reader,self.Done=STEPControl_Reader,IFSelect_RetDone
        self.Explorer,self.SOLID,self.TopoDS=TopExp_Explorer,TopAbs_SOLID,TopoDS
        self.Bounds,self.Box=BRepBndLib,Bnd_Box
        self.Analyzer,self.GProp,self.Props=BRepCheck_Analyzer,BRepGProp,GProp_GProps
        self.Cut,self.Trsf,self.Transform=BRepAlgoAPI_Cut,gp_Trsf,BRepBuilderAPI_Transform

    def load(self,path):
        reader=self.Reader()
        if reader.ReadFile(str(path))!=self.Done:
            raise RuntimeError('STEP ReadFile failed: '+str(path))
        if reader.TransferRoots()<=0:
            raise RuntimeError('STEP has no transferable roots: '+str(path))
        shape=reader.OneShape()
        if shape.IsNull():
            raise RuntimeError('STEP returned a null shape')
        del reader
        return shape

    def solids(self,shape):
        found=[];ex=self.Explorer(shape,self.SOLID)
        while ex.More():
            found.append(self.TopoDS.Solid_s(ex.Current()));ex.Next()
        return found

    def bbox(self,shape):
        box=self.Box()
        self.Bounds.AddOptimal_s(shape,box,False,False)
        if box.IsVoid() or box.IsWhole():
            raise RuntimeError('Invalid or unbounded solid bounding box')
        values=list(box.Get())
        if len(values)!=6 or not all(math.isfinite(v) for v in values):
            raise RuntimeError('Nonfinite bounding box')
        return dict(min_mm=values[:3],max_mm=values[3:])

    def valid(self,shape):
        return bool(self.Analyzer(shape,True).IsValid())

    def volume(self,shape):
        values=[]
        for solid in self.solids(shape):
            if not self.valid(solid):
                raise RuntimeError('Invalid body encountered in scoped material comparison')
            props=self.Props()
            error=self.GProp.VolumeProperties_s(solid,props,Eps=INTEGRATION_EPS,OnlyClosed=True,SkipShared=False)
            value=float(props.Mass())
            if error is None or not math.isfinite(float(error)) or error<0 or not math.isfinite(value):
                raise RuntimeError('Adaptive volume integration failed')
            values.append(abs(value))
        return math.fsum(values)

    def difference(self,a,b):
        operation=self.Cut(a,b)
        if not operation.IsDone():
            raise RuntimeError('Scoped Boolean subtraction failed')
        return self.volume(operation.Shape())

    def transformed(self,shape,T):
        transform=self.Trsf()
        transform.SetValues(*[float(v) for row in T[:3] for v in row])
        return self.Transform(shape,transform,True).Shape()

    def compare(self,actual,expected):
        a_box,e_box=self.bbox(actual),self.bbox(expected)
        error=max(abs(a_box[edge][i]-e_box[edge][i]) for edge in ('min_mm','max_mm') for i in range(3))
        a_count,e_count=len(self.solids(actual)),len(self.solids(expected))
        result=dict(status='FAIL',actual_bounds_mm=a_box,expected_bounds_mm=e_box,bbox_max_error_mm=error,
                    actual_solid_count=a_count,expected_solid_count=e_count,
                    actual_minus_expected_mm3=None,expected_minus_actual_mm3=None,
                    bidirectional_material_difference_mm3=None,volume_difference_mm3=None)
        if error>LINEAR_MM or a_count!=e_count or a_count<=0:
            result['failure']='BOUNDING_BOX_OR_SOLID_COUNT_MISMATCH';return result
        av,ev=self.valid(actual),self.valid(expected)
        result.update(actual_valid=av,expected_valid=ev)
        if not av or not ev:
            result['failure']='INVALID_SCOPED_SHAPE';return result
        va,ve=self.volume(actual),self.volume(expected)
        forward,reverse=self.difference(actual,expected),self.difference(expected,actual)
        result.update(actual_volume_mm3=va,expected_volume_mm3=ve,volume_difference_mm3=abs(va-ve),
                      actual_minus_expected_mm3=forward,expected_minus_actual_mm3=reverse,
                      bidirectional_material_difference_mm3=forward+reverse)
        if forward+reverse<=VOLUME_MM3 and abs(va-ve)<=VOLUME_MM3:
            result['status']='PASS'
        else:
            result['failure']='SCOPED_MATERIAL_DIFFERENCE'
        return result


def subset_check(kernel,actual,expected,ids=None):
    """Common material validator used by real export matches and memory-only controls."""
    required=set(expected) if ids is None else set(ids)
    coverage=set(actual)==required
    results=[]
    if not coverage:
        return dict(status='FAIL',coverage_pass=False,missing_ids=sorted(required-set(actual)),
                    unexpected_ids=sorted(set(actual)-required),results=[])
    for instance in sorted(required&set(actual)):
        try:
            row=kernel.compare(actual[instance],expected[instance])
        except Exception as exc:
            row=dict(status='ERROR',error=repr(exc))
        row['id']=instance;results.append(row)
    return dict(status='PASS' if coverage and all(p['status']=='PASS' for p in results) else 'FAIL',
                coverage_pass=coverage,missing_ids=sorted(required-set(actual)),unexpected_ids=sorted(set(actual)-required),results=results)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('state',choices=('service','parking','released'))
    args=parser.parse_args(argv);state=args.state
    out=R/'results'/('INTEGRATION_READBACK_'+state.upper()+'.json')
    manifest_path=R/'results/INTEGRATION_MANIFEST.json'
    receipt_path=R/'results'/('NATIVE_'+state.upper()+'.json')
    report=dict(schema='WP07_SCOPED_INTEGRATION_READBACK_V1',state=state,status='RUNNING',
                started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),inputs_sha256_before={},
                tolerances=dict(linear_mm=LINEAR_MM,volume_mm3=VOLUME_MM3,integration_eps=INTEGRATION_EPS),
                complete_step_solid_count=None,matched_delta_parts=[],negative_controls={},
                all_597_material_equivalence_verified=False,remaining_573_material_equivalence='NOT_REEVALUATED',
                B601_geometry_holds='INHERITED_UNCHANGED_NOT_CLEARED',physical_assembly_completed=False,
                manufacturing_release=False,strength_verified=False,continuous_motion_verified=False)
    pins=report['inputs_sha256_before']
    def pin(path,expected=None):
        path=Path(path).resolve();digest=pins.get(str(path)) or sha(path)
        if expected is not None and digest!=expected:
            raise RuntimeError('Input SHA mismatch: '+str(path))
        pins[str(path)]=digest
        return dict(path=str(path),sha256=digest)
    try:
        report['script']=pin(__file__);report['manifest']=pin(manifest_path);report['native_receipt']=pin(receipt_path)
        manifest=read(manifest_path);receipt=read(receipt_path);state_info=manifest['states'][state]
        rows=state_info['instances'];by_id={p['id']:p for p in rows}
        if not receipt.get('status','').startswith('PASS_'):
            raise RuntimeError('Producer native receipt is not completed')
        if receipt['manifest_sha256']!=report['manifest']['sha256']:
            raise RuntimeError('Native producer used a different manifest')
        native_path=R/'native'/('WP07_ROBOT_'+state.upper()+'.SLDASM')
        report['native_assembly']=pin(native_path,receipt['final_native_sha256'])
        export=receipt['step_export']
        report['actual_step']=pin(export['path'],export['sha256'])
        observed=receipt['cold_inspection']['components']
        for row in rows:
            pin(row['native_path'],row['native_sha256'])
        report['native_receipt_check']=native_rows_check(observed,rows)
        write(out,report)
        changed=set(manifest['replaced_ids']);added=set(manifest['added_ids']);delta_ids=changed|added
        if len(delta_ids)!=24 or len(changed)!=8 or len(added)!=16:
            raise RuntimeError('Unexpected delta contract')
        kernel=Kernel();sources={}
        for instance in sorted(delta_ids):
            row=by_id[instance];pin(row['step_path'],row['source_sha256'])
            raw=kernel.load(row['step_path'])
            sources[instance]=kernel.transformed(raw,row['T_S_local'])
            if len(kernel.solids(sources[instance]))!=row['expected_solids'] or row['expected_solids']!=1:
                raise RuntimeError('The bounded delta requires one actual source solid per part')
        full=kernel.load(report['actual_step']['path']);solids=kernel.solids(full)
        report['complete_step_solid_count']=len(solids)
        report['complete_step_solid_count_pass']=len(solids)==978
        write(out,report)
        source_bounds={k:kernel.bbox(v) for k,v in sources.items()}
        candidates={k:[] for k in delta_ids};box_errors=[]
        # No arm volumes/validity/Booleans are evaluated during this broad-phase scan.
        for index,solid in enumerate(solids):
            try:
                bounds=kernel.bbox(solid)
                for instance,expected in source_bounds.items():
                    error=max(abs(bounds[edge][i]-expected[edge][i]) for edge in ('min_mm','max_mm') for i in range(3))
                    if error<=LINEAR_MM:
                        candidates[instance].append(index)
            except Exception as exc:
                box_errors.append(dict(solid_index=index,error=repr(exc)))
            if (index+1)%100==0:
                report['broad_phase_solids_scanned']=index+1;write(out,report)
        report['non_delta_bbox_diagnostics']=box_errors
        report['bbox_candidate_indices']={k:v for k,v in sorted(candidates.items())}
        selected={};used=set()
        for instance in sorted(delta_ids):
            attempts=[];match=None
            for index in candidates[instance]:
                if index in used:
                    continue
                evidence=subset_check(kernel,{instance:solids[index]},sources,{instance})
                attempts.append(dict(solid_index=index,evidence=evidence))
                if evidence['status']=='PASS':
                    match=index;selected[instance]=solids[index];used.add(index);break
            report['matched_delta_parts'].append(dict(id=instance,status='PASS' if match is not None else 'FAIL',
                solid_index=match,source_step=dict(path=by_id[instance]['step_path'],sha256=by_id[instance]['source_sha256']),
                attempts=attempts))
            write(out,report)
            print(json.dumps(dict(state=state,part=instance,status='PASS' if match is not None else 'FAIL'),ensure_ascii=False),flush=True)
        report['delta_unique_matching_pass']=set(selected)==delta_ids and len(used)==24
        report['full_step_matching_scope']='24_ACTUAL_GLOBAL_MATERIAL_MATCHES_WITH_UNIQUE_SOLID_OCCURRENCES; NO_PRODUCT_NAME_OR_GLOBAL_COLLISION_CLAIM'
        if report['delta_unique_matching_pass']:
            # Drop the large parent/arm occurrence list before memory-only falsifiers.
            del full,solids;gc.collect()
            clip=next(k for k in sorted(changed) if k.startswith('shear_clip_'))
            old=by_id[clip];old_part=manifest['parts'][old['previous_part_key']]
            pin(old_part['source_step']['path'],old_part['source_step']['sha256'])
            old_shape=kernel.transformed(kernel.load(old_part['source_step']['path']),old['previous_T_S_local'])
            wrong_clip=subset_check(kernel,{clip:old_shape},sources,{clip})
            report['negative_controls']['wrong_old_clip']=dict(status='PASS' if wrong_clip['status']=='FAIL' else 'FAIL',
                expected_validator_status='FAIL',observed_validator_status=wrong_clip['status'],evidence=wrong_clip,
                scope='ONE_PART_SAME_MATERIAL_VALIDATOR_MEMORY_ONLY')
            shift=copy.deepcopy(IDENTITY);shift[0][3]=1.0
            shifted_shape=kernel.transformed(selected[clip],shift)
            wrong_transform=subset_check(kernel,{clip:shifted_shape},sources,{clip})
            report['negative_controls']['actual_part_transform_plus_1mm']=dict(
                status='PASS' if wrong_transform['status']=='FAIL' else 'FAIL',expected_validator_status='FAIL',
                observed_validator_status=wrong_transform['status'],evidence=wrong_transform,scope='MEMORY_ONLY')
            missing=dict(selected);missing.pop(sorted(added)[0])
            missing_part=subset_check(kernel,missing,sources)
            report['negative_controls']['missing_added_part']=dict(status='PASS' if missing_part['status']=='FAIL' else 'FAIL',
                expected_validator_status='FAIL',observed_validator_status=missing_part['status'],evidence=missing_part,scope='MEMORY_ONLY')
            write(out,report)
        # Pure receipt controls do not mutate or ask SolidWorks to re-evaluate a model.
        wrong_rows=copy.deepcopy(observed)
        wrong_rows[0]['transform_sw16'][9]+=0.001
        metadata_control=native_rows_check(wrong_rows,rows)
        report['negative_controls']['stored_native_transform_plus_1mm']=dict(
            status='PASS' if metadata_control['status']=='FAIL' else 'FAIL',observed_validator_status=metadata_control['status'],
            scope='MEMORY_ONLY_SAME_NATIVE_RECEIPT_VALIDATOR')
        ok=(report['native_receipt_check']['status']=='PASS' and report['complete_step_solid_count_pass']
            and report['delta_unique_matching_pass'] and len(report['negative_controls'])==4
            and all(v['status']=='PASS' for v in report['negative_controls'].values()))
        report['status']='PASS_SCOPED_INTEGRATION_WITH_INHERITED_GEOMETRY_HOLDS' if ok else 'FAIL_SCOPED_INTEGRATION'
    except Exception as exc:
        report.update(status='INCOMPLETE',error=repr(exc),traceback=traceback.format_exc())
    finally:
        after={path:sha(path) if Path(path).is_file() else None for path in pins}
        report['inputs_sha256_after']=after
        report['inputs_unchanged']=after==pins
        if not report['inputs_unchanged']:
            report['status']='FAIL_INPUT_CHANGED'
        report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat();write(out,report)
    print(json.dumps(dict(status=report['status'],output=str(out)),ensure_ascii=False),flush=True)
    return 0 if report['status']=='PASS_SCOPED_INTEGRATION_WITH_INHERITED_GEOMETRY_HOLDS' else 2


if __name__=='__main__':
    raise SystemExit(main())
