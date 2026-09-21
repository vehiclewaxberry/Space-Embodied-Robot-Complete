"""Read-only, independent STEP geometry measurements for WP06 side joints.

Usage: python verify_joint_geometry.py path/to/job.json
Job: {parts:{id:{path:absolute_STEP,T_S_local:4x4_mm}}, tests:[...], output:path,
      tolerances:{linear_mm:...,volume_mm3:...,integration_eps:...}}
Optional tolerances.rotation is a dimensionless rigid-transform tolerance;
otherwise integration_eps supplies that numerical tolerance.

Kinds: facts(part), clearance(a,b,min_mm), intersection(a,b),
axis_bore(part,axis_point,axis_dir,diameter,length),
compare_source(target,reference), axis_line_intervals(part,point,dir), bearing.
axis_bore starts at axis_point and extends length along the normalized axis_dir.
axis_line_intervals reports signed millimetres along dir from point. Optional
expected_intervals_mm enables an explicit interval comparison. bearing returns
NOT_IMPLEMENTED plus actual distance/intersection evidence, never invented area.
No design generator or producer check module is loaded. Only job.output is written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
from collections import Counter, OrderedDict
from pathlib import Path


CADGEN = Path('F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')


class MissingInput(RuntimeError):
    pass


def need(obj, key):
    if key not in obj or obj[key] is None:
        raise MissingInput('Required input is missing: '+key)
    return obj[key]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, path)


def vector(value):
    result = [float(x) for x in value]
    if len(result) != 3 or not all(math.isfinite(x) for x in result):
        raise ValueError('Expected finite three-vector')
    return result


def direction(value):
    value = vector(value)
    length = math.sqrt(sum(x*x for x in value))
    if length <= 0:
        raise ValueError('Axis direction must be nonzero')
    return [x/length for x in value]


def positive(value, name, allow_zero=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
        raise ValueError('Invalid '+name)
    return value


class Geometry:
    def __init__(self, job, snapshots):
        self.job, self.snapshots, self.cache = job, snapshots, OrderedDict()
        tol = need(job, 'tolerances')
        self.linear = positive(need(tol, 'linear_mm'), 'linear tolerance')
        self.volume_tol = positive(need(tol, 'volume_mm3'), 'volume tolerance', True)
        self.eps = positive(need(tol, 'integration_eps'), 'integration epsilon')
        if self.eps > 0.001:
            raise ValueError('integration_eps must request adaptive integration (<= 0.001)')
        self.rotation_tol = positive(tol.get('rotation', self.eps), 'rotation tolerance')
        sys.path.insert(0, str(CADGEN))
        import cadgen  # noqa: F401 - installed font guard precedes build123d imports
        from cadgen.step_scene import import_step
        from build123d import Solid, Plane, Location
        from OCP.gp import gp_Trsf, gp_Pnt, gp_Dir, gp_Lin
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.TopAbs import TopAbs_IN, TopAbs_ON, TopAbs_OUT
        self.import_step, self.Solid, self.Plane, self.Location = import_step, Solid, Plane, Location
        self.Trsf, self.Pnt, self.Dir, self.Line = gp_Trsf, gp_Pnt, gp_Dir, gp_Lin
        self.GProp, self.Props, self.Distance = BRepGProp, GProp_GProps, BRepExtrema_DistShapeShape
        self.Intersector, self.Classifier = IntCurvesFace_ShapeIntersector, BRepClass3d_SolidClassifier
        self.IN, self.ON, self.OUT = TopAbs_IN, TopAbs_ON, TopAbs_OUT

    def location(self, T):
        if len(T) != 4 or any(len(row) != 4 for row in T):
            raise ValueError('T_S_local must be 4 by 4')
        T = [[float(x) for x in row] for row in T]
        if not all(math.isfinite(x) for row in T for x in row):
            raise ValueError('Nonfinite transform')
        e = self.rotation_tol
        if max(abs(T[3][i]-(1 if i == 3 else 0)) for i in range(4)) > e:
            raise ValueError('Invalid homogeneous transform row')
        if max(abs(sum(T[k][i]*T[k][j] for k in range(3))-(1 if i == j else 0))
               for i in range(3) for j in range(3)) > e:
            raise ValueError('Transform is not rigid')
        det = (T[0][0]*(T[1][1]*T[2][2]-T[1][2]*T[2][1])
               - T[0][1]*(T[1][0]*T[2][2]-T[1][2]*T[2][0])
               + T[0][2]*(T[1][0]*T[2][1]-T[1][1]*T[2][0]))
        if abs(det-1) > e:
            raise ValueError('Transform includes reflection or scale')
        tr = self.Trsf()
        tr.SetValues(*[x for row in T[:3] for x in row])
        return self.Location(tr)

    def load(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        item = need(need(self.job, 'parts'), key)
        path = Path(need(item, 'path')).resolve()
        if not path.is_file():
            raise MissingInput('STEP file missing: '+str(path))
        if path.suffix.lower() not in ('.step', '.stp'):
            raise ValueError('Actual STEP input required: '+str(path))
        digest = sha(path)
        if item.get('sha256') and item['sha256'].lower() != digest:
            raise ValueError('Declared STEP SHA mismatch: '+key)
        if str(path) in self.snapshots and self.snapshots[str(path)] != digest:
            raise ValueError('STEP changed during measurements: '+key)
        self.snapshots[str(path)] = digest
        tree = self.import_step(path)
        intrinsic = tree.global_location
        detached = type(tree)(tree.wrapped)
        if detached.parent is not None or getattr(detached, 'children', ()):
            raise RuntimeError('Unsafe assembly detachment')
        own_shape = detached.located(intrinsic)
        world = own_shape.moved(self.location(need(item, 'T_S_local')))
        del tree, detached, own_shape
        self.cache[key] = world
        while len(self.cache) > 2:
            self.cache.popitem(last=False)
        return world

    def volume(self, shape):
        if shape is None:
            return 0.0
        values = []
        for solid in shape.solids():
            if not solid.is_valid:
                raise RuntimeError('Invalid solid encountered in material measurement')
            props = self.Props()
            error = self.GProp.VolumeProperties_s(solid.wrapped, props, Eps=self.eps, OnlyClosed=True, SkipShared=False)
            mass = float(props.Mass())
            if error is None or not math.isfinite(float(error)) or error < 0 or not math.isfinite(mass):
                raise RuntimeError('Adaptive material integration failed')
            values.append(abs(mass))
        return math.fsum(values)

    def facts(self, shape):
        box = shape.bounding_box()
        return dict(shape_valid=bool(shape.is_valid), solid_count=len(shape.solids()), volume_mm3=self.volume(shape),
                    bbox_mm=dict(min_mm=list(box.min), max_mm=list(box.max), size_mm=list(box.size)))

    def separation(self, a, b):
        if not a.is_valid or not b.is_valid:
            raise RuntimeError('Separation requires valid input shapes')
        distance = self.Distance(a.wrapped, b.wrapped)
        distance.Perform()
        if not distance.IsDone():
            raise RuntimeError('Actual shape minimum-distance computation failed')
        common = a & b
        result = dict(minimum_distance_mm=float(distance.Value()), intersection_volume_mm3=self.volume(common),
                      a_facts=self.facts(a), b_facts=self.facts(b))
        del common
        return result

    def line_intervals(self, part, test):
        if not part.is_valid or not part.solids():
            raise RuntimeError('Line intervals require valid closed solids')
        point = vector(need(test, 'point'))
        axis = direction(need(test, 'dir'))
        bbox = self.facts(part)['bbox_mm']
        projections = [sum((corner[k]-point[k])*axis[k] for k in range(3))
                       for corner in ((x,y,z) for x in (bbox['min_mm'][0],bbox['max_mm'][0])
                                      for y in (bbox['min_mm'][1],bbox['max_mm'][1])
                                      for z in (bbox['min_mm'][2],bbox['max_mm'][2]))]
        lo = float(test.get('t_min_mm', min(projections)-self.linear))
        hi = float(test.get('t_max_mm', max(projections)+self.linear))
        if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
            raise ValueError('Invalid signed line parameter range')
        intersector = self.Intersector()
        intersector.Load(part.wrapped, self.linear)
        intersector.Perform(self.Line(self.Pnt(*point), self.Dir(*axis)), lo, hi)
        if not intersector.IsDone():
            raise RuntimeError('OCC line/face intersection did not finish')
        events = [float(intersector.WParameter(i)) for i in range(1, intersector.NbPnt()+1)]
        raw = sorted([lo, hi]+[t for t in events if lo <= t <= hi])
        knots = []
        for value in raw:
            if not knots or value-knots[-1] > self.linear:
                knots.append(value)
        if hi-knots[-1] > 0:
            knots.append(hi)
        intervals, boundary, classified = [], [], []
        solids = part.solids()
        for a,b in zip(knots, knots[1:]):
            if b-a <= self.linear:
                continue
            mid = (a+b)/2
            p = self.Pnt(*[point[k]+mid*axis[k] for k in range(3)])
            states = [self.Classifier(s.wrapped, p, self.linear).State() for s in solids]
            if any(state not in (self.IN, self.ON, self.OUT) for state in states):
                raise RuntimeError('OCC midpoint classification returned UNKNOWN')
            label = 'INSIDE_MATERIAL' if self.IN in states else 'BOUNDARY_ONLY' if self.ON in states else 'OUTSIDE'
            classified.append(dict(interval_mm=[a,b], classification=label))
            target = intervals if label == 'INSIDE_MATERIAL' else boundary if label == 'BOUNDARY_ONLY' else None
            if target is not None:
                if target and abs(target[-1][1]-a) <= self.linear:
                    target[-1][1] = b
                else:
                    target.append([a,b])
        return dict(point_mm=point, unit_direction=axis, parameter_range_mm=[lo,hi],
                    raw_face_intersection_parameters_mm=sorted(events), material_intervals_mm=intervals,
                    boundary_only_intervals_mm=boundary, classified_intervals=classified,
                    method='Actual OCC line-face intersection and midpoint solid classification',
                    computational_linear_tolerance_mm=self.linear)

    def evaluate(self, test):
        kind = need(test, 'kind')
        vtol = positive(test.get('volume_tolerance_mm3', self.volume_tol), 'volume tolerance', True)
        ltol = positive(test.get('linear_tolerance_mm', self.linear), 'linear tolerance')
        if kind == 'facts':
            value = self.facts(self.load(need(test, 'part')))
            return dict(status='PASS' if value['shape_valid'] and value['solid_count'] > 0 else 'FAIL', **value,
                        scope='Measured validity and dimensions; no design or strength acceptance')
        if kind in ('clearance', 'intersection', 'bearing'):
            measured = self.separation(self.load(need(test, 'a')), self.load(need(test, 'b')))
            if kind == 'bearing':
                return dict(status='INCOMPLETE', implementation_status='NOT_IMPLEMENTED', **measured,
                    reason='Bearing-plane common contact area is not implemented; distance/intersection do not establish supported bearing area',
                    requested_plane_point=test.get('plane_point'), requested_plane_normal=test.get('plane_normal'))
            if kind == 'clearance':
                minimum = positive(need(test, 'min_mm'), 'required minimum clearance', True)
                ok = measured['minimum_distance_mm']+ltol >= minimum and measured['intersection_volume_mm3'] <= vtol
                return dict(status='PASS' if ok else 'FAIL', required_minimum_mm=minimum,
                            linear_tolerance_mm=ltol, volume_tolerance_mm3=vtol, **measured)
            maximum = positive(test.get('max_volume_mm3', vtol), 'maximum intersection volume', True)
            minimum = test.get('min_volume_mm3')
            ok = measured['intersection_volume_mm3'] <= maximum
            if minimum is not None:
                minimum = positive(minimum, 'minimum intersection volume', True)
                ok = ok and measured['intersection_volume_mm3'] >= minimum
            return dict(status='PASS' if ok else 'FAIL', max_volume_mm3=maximum, min_volume_mm3=minimum, **measured)
        if kind == 'axis_bore':
            part = self.load(need(test, 'part'))
            p = vector(need(test, 'axis_point'))
            axis = direction(need(test, 'axis_dir'))
            diameter = positive(need(test, 'diameter'), 'bore test diameter')
            length = positive(need(test, 'length'), 'bore test length')
            probe = self.Solid.make_cylinder(diameter/2, length, self.Plane(origin=tuple(p), z_dir=tuple(axis)))
            common = part & probe
            volume = self.volume(common)
            return dict(status='PASS' if part.is_valid and volume <= vtol else 'FAIL',
                probe_start_mm=p, probe_axis_unit=axis, probe_diameter_mm=diameter, probe_length_mm=length,
                probe_volume_mm3=self.volume(probe), body_overlap_volume_mm3=volume,
                volume_tolerance_mm3=vtol, part_facts=self.facts(part),
                scope='Actual supplied cylinder is material-free; surrounding-wall/support and opening connectivity are separate contracts')
        if kind == 'compare_source':
            a, b = self.load(need(test, 'target')), self.load(need(test, 'reference'))
            af, bf = self.facts(a), self.facts(b)
            forward, backward = a-b, b-a
            av, bv = self.volume(forward), self.volume(backward)
            bbox_diff = max(abs(af['bbox_mm'][side][i]-bf['bbox_mm'][side][i])
                            for side in ('min_mm','max_mm') for i in range(3))
            delta = math.fsum((av,bv))
            ok = (af['shape_valid'] and bf['shape_valid'] and af['solid_count'] == bf['solid_count']
                  and bbox_diff <= ltol and delta <= vtol and abs(af['volume_mm3']-bf['volume_mm3']) <= vtol)
            return dict(status='PASS' if ok else 'FAIL', target_minus_reference_mm3=av,
                        reference_minus_target_mm3=bv, symmetric_difference_mm3=delta,
                        bbox_max_difference_mm=bbox_diff, volume_difference_mm3=abs(af['volume_mm3']-bf['volume_mm3']),
                        target_facts=af, reference_facts=bf, linear_tolerance_mm=ltol, volume_tolerance_mm3=vtol)
        if kind == 'axis_line_intervals':
            result = self.line_intervals(self.load(need(test, 'part')), test)
            expected = test.get('expected_intervals_mm')
            if expected is None:
                result.update(status='MEASURED', acceptance_evaluated=False)
            else:
                actual = result['material_intervals_mm']
                ok = (len(actual) == len(expected) and all(len(pair) == 2 for pair in expected)
                      and all(abs(actual[i][j]-float(expected[i][j])) <= ltol
                              for i in range(len(actual)) for j in range(2)))
                result.update(status='PASS' if ok else 'FAIL', acceptance_evaluated=True,
                              expected_intervals_mm=expected, linear_tolerance_mm=ltol)
            return result
        return dict(status='INCOMPLETE', implementation_status='NOT_IMPLEMENTED', reason='Unknown test kind: '+str(kind))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('job', type=Path)
    args = ap.parse_args(argv)
    job_path = args.job.resolve()
    job = json.loads(job_path.read_text(encoding='utf-8-sig'))
    output = Path(need(job, 'output')).resolve()
    protected = {job_path, Path(__file__).resolve()} | {Path(p['path']).resolve() for p in job.get('parts', {}).values() if p.get('path')}
    if output in protected:
        raise ValueError('Output cannot overwrite an input or the measurement script')
    base_snapshots = {str(job_path):sha(job_path), str(Path(__file__).resolve()):sha(__file__)}
    snapshots, results, geometry = dict(base_snapshots), [], None
    for index,test in enumerate(need(job, 'tests')):
        refs = [test[k] for k in ('part','a','b','target','reference') if k in test]
        result = dict(id=test.get('id', str(index)), kind=test.get('kind'), input_sha256=dict(base_snapshots),
                      validation_script_path=str(Path(__file__).resolve()), validation_script_sha256=base_snapshots[str(Path(__file__).resolve())])
        try:
            if geometry is None:
                geometry = Geometry(job, snapshots)
            result.update(geometry.evaluate(test))
        except MissingInput as exc:
            result.update(status='INCOMPLETE', reason=str(exc))
        except Exception as exc:
            result.update(status='FAIL', reason=str(exc), exception_type=type(exc).__name__)
        for key in refs:
            item = job.get('parts', {}).get(key, {})
            if item.get('path'):
                p = str(Path(item['path']).resolve())
                if p in snapshots:
                    result['input_sha256'][p] = snapshots[p]
        result['part_inputs'] = {key:job.get('parts', {}).get(key) for key in refs}
        results.append(result)
        print(json.dumps(dict(id=result['id'], kind=result['kind'], status=result['status']), ensure_ascii=False), flush=True)
        write(output, dict(status='IN_PROGRESS', results=results, input_sha256_before=snapshots,
                           physical_assembly_completed=False, manufacturing_release=False, strength_verified=False))
    after = {p:sha(p) if Path(p).is_file() else None for p in snapshots}
    unchanged = snapshots == after
    if not unchanged:
        for result in results:
            result.update(status='FAIL', reason='Input files changed during independent measurements')
    counts = dict(Counter(r['status'] for r in results))
    status = ('FAIL' if counts.get('FAIL') else 'INCOMPLETE' if counts.get('INCOMPLETE') or not results else
              'MEASUREMENTS_COMPLETE' if counts.get('MEASURED') else 'PASS_SCOPED_GEOMETRY_TESTS_ONLY')
    report = dict(schema='WP06_INDEPENDENT_JOINT_GEOMETRY_V1', status=status, counts=counts,
                  generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(), results=results,
                  input_sha256_before=snapshots, input_sha256_after=after, input_files_unchanged=unchanged,
                  thresholds_from_job=job.get('tolerances'), no_producer_generator_loaded=True,
                  physical_assembly_completed=False, manufacturing_release=False, strength_verified=False)
    write(output, report)
    return 1 if status == 'FAIL' else 2 if status == 'INCOMPLETE' else 0


if __name__ == '__main__':
    raise SystemExit(main())
