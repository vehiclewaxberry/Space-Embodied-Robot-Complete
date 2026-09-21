"""Source-pinned, named XCAF STEP assemblies and actual BRep rendering.

Only the neutral outputs, one snapshot, and NEUTRAL_ASSEMBLY.json are written.
Run each build/verify/render operation in a fresh process to release OCCT memory.
No SolidWorks, no material-density assignment, and no mechanical release credit.
"""
from pathlib import Path
import argparse
import collections
import datetime as dt
import gc
import hashlib
import json
import time

import numpy as np
from OCP.STEPControl import STEPControl_Reader, STEPControl_AsIs
from OCP.STEPCAFControl import STEPCAFControl_Writer, STEPCAFControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool, XCAFDoc_ColorGen
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.TopLoc import TopLoc_Location
from OCP.gp import gp_Trsf
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

D = Path(__file__).resolve().parents[1]
MAP = D / 'inputs/NEUTRAL_SOURCE_MAP.json'
RECEIPT = D / 'results/NEUTRAL_ASSEMBLY.json'
PNG = D / 'views/INTEGRATED_1110_SERVICE.png'
SOURCE_DIAGNOSTICS = []


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def memory_metrics():
    import psutil
    mem = psutil.Process().memory_info()
    return {'process_peak_working_set_MiB': getattr(mem, 'peak_wset', mem.rss) / 2**20,
            'process_current_working_set_MiB': mem.rss / 2**20,
            'system_available_MiB': psutil.virtual_memory().available / 2**20}


def persist(state, mode, data):
    out = json.loads(RECEIPT.read_text(encoding='utf-8')) if RECEIPT.exists() else {
        'schema': 'NAMED_NEUTRAL_ASSEMBLY_V1', 'states': {},
        'engineering_limits': {
            'whole_design_complete': False, 'SolidWorks_opened': False,
            'native_material_assignment': False, 'whole_spacecraft_mass_inertia': None,
            'motion_mates': False, 'interference_clearance_release': False,
            'power_readiness': False, 'flight_readiness': False,
            'historical_PASS_inherited': False,
            'geometry_contains_proxy_and_functional_envelope_parts': True,
            'merged_interfaces_are_candidates_not_mechanical_release': True,
        },
    }
    out['source_map'] = {'path': str(MAP), 'sha256': sha(MAP)}
    out['generator'] = {'path': str(Path(__file__).resolve()), 'sha256': sha(__file__)}
    out['updated_utc'] = stamp()
    data['memory_metrics'] = memory_metrics()
    out['states'].setdefault(state, {})[mode] = data
    verified = [s for s, v in out['states'].items()
                if v.get('verify', {}).get('status') == 'NAMED_LEAF_COUNTS_AND_TRANSFORMS_REOPENED']
    out['status'] = ('THREE_STATES_NAMED_STEP_REOPENED_NOT_NATIVE_MATERIAL_RELEASE'
                     if len(verified) == 3 else 'NEUTRAL_DELIVERY_IN_PROGRESS')
    if data.get('status') == 'FAILED_CLOSED':
        out['status'] = 'BLOCKED_FAILED_CLOSED'
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')


def load_map(state):
    data = json.loads(MAP.read_text(encoding='utf-8-sig'))
    assert data['counts']['blockers'] == 0 and not data['blockers']
    groups = [g for g in data['groups'] if g['id'] in data['states'][state]['groups']]
    rows = [r for g in groups for r in g['rows']]
    assert len(rows) == data['states'][state]['leaf_count'] == 1110
    assert len({r['id'] for r in rows}) == len(rows)
    for r in rows:
        assert not r['blockers'] and r['status'] == 'SOURCE_AND_TRANSFORM_PINNED'
        T = np.asarray(r['T_S_local'], dtype=float)
        assert T.shape == (4, 4) and np.isfinite(T).all()
        assert np.allclose(T[3], [0, 0, 0, 1], atol=1e-12)
        assert np.allclose(T[:3, :3].T @ T[:3, :3], np.eye(3), atol=1e-9)
        assert abs(np.linalg.det(T[:3, :3]) - 1) < 1e-9
    return data, groups, rows


def outpath(state):
    return D / 'neutral' / ('SERVICE_STAR_' + state.upper() + '_R1.step')


def name(label, text):
    TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))


def getname(label):
    att = TDataStd_Name()
    return att.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), att) else ''


def transform(T):
    t = gp_Trsf()
    t.SetValues(*[T[i][j] for i in range(3) for j in range(4)])
    return TopLoc_Location(t)


def matrix(location):
    t = location.Transformation()
    return np.asarray([[t.Value(i, j) for j in range(1, 5)] for i in range(1, 4)] + [[0, 0, 0, 1]])


def solids(shape):
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n


def read_part(row):
    path = Path(row['step_path'])
    assert path.is_file(), f'Missing source: {path}'
    assert sha(path) == row['source_sha256'], f'Hash mismatch: {path}'
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone, f'Cannot read {path}'
    check = reader.Model().GlobalCheck(True)
    failures = [check.CFail(i) for i in range(1, check.NbFails() + 1)]
    if failures:
        # OEM LPS300 has a malformed authorisation header field; OCCT returns
        # complete geometry. Preserve the exact diagnostic, allow only this
        # demonstrated non-geometric header issue, and regenerate a valid header.
        assert failures == ['Parameter n0.7 (authorisation) not a quoted String'], failures
        SOURCE_DIAGNOSTICS.append({'id': row['id'], 'path': str(path),
                                   'sha256': row['source_sha256'],
                                   'classification': 'SOURCE_HEADER_AUTHORISATION_FIELD_ONLY',
                                   'messages': failures,
                                   'source_changed': False})
    assert reader.TransferRoots() > 0
    shape = reader.OneShape()
    assert not shape.IsNull()
    return shape


def color(row):
    key = row['id'].lower()
    if 'b601' in key:
        return (0.72, 0.77, 0.82)
    if any(k in key for k in ['cic_', 'cell_', 'glass_', 'wing_']) and not any(k in key for k in ['pin', 'screw', 'frame', 'fork', 'hinge']):
        return (0.08, 0.20, 0.42)
    if any(k in key for k in ['wire', 'route', 'harness', 'cable']):
        return (0.72, 0.33, 0.12)
    if any(k in key for k in ['thermal', 'radiator', 'spreader']):
        return (0.76, 0.60, 0.25)
    if any(k in key for k in ['screw', 'bolt', 'nut', 'washer', 'pin']):
        return (0.45, 0.48, 0.53)
    if any(k in key for k in ['equipment', 'c203', 'battery', 'connector']):
        return (0.22, 0.46, 0.48)
    return (0.63, 0.70, 0.78)


def build(state):
    started = time.time()
    data, groups, rows = load_map(state)
    doc = TDocStd_Document(TCollection_ExtendedString('XmlXCAF'))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    root = st.NewShape()
    name(root, 'SERVICE_STAR_' + state.upper() + '_R1')
    labels, source_counts, observations = {}, {}, []
    total = 0
    for g in groups:
        gl = st.NewShape()
        name(gl, g['id'])
        st.AddComponent(root, gl, TopLoc_Location())
        for row in g['rows']:
            key = row['step_path']
            if key not in labels:
                shape = read_part(row)
                n = solids(shape)
                source_counts[key] = n
                pl = st.AddShape(shape, False, False)
                name(pl, row['id'])
                rgb = color(row)
                ct.SetColor(pl, Quantity_Color(*rgb, Quantity_TOC_RGB), XCAFDoc_ColorGen)
                labels[key] = pl
                if n != row['expected_solids']:
                    observations.append({'id': row['id'], 'source_solids': n,
                                         'native_expected_solids': row['expected_solids']})
            component = st.AddComponent(gl, labels[key], transform(row['T_S_local']))
            name(component, row['id'])
            total += source_counts[key]
        print(f'{state}: group {g["id"]}, sources={len(labels)}, solids={total}', flush=True)
    assert not observations, f'Source/native solid count differences: {observations}'
    assert total == data['states'][state]['expected_solids']
    st.UpdateAssemblies()
    target = outpath(state)
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.SetColorMode(True)
    Interface_Static.SetCVal_s('write.step.schema', 'AP242DIS')
    Interface_Static.SetCVal_s('write.step.unit', 'MM')
    assert writer.Transfer(doc, STEPControl_AsIs)
    assert writer.Write(str(target)) == IFSelect_RetDone
    result = {'status': 'NAMED_STEP_WRITTEN_REOPEN_PENDING', 'path': str(target),
              'sha256': sha(target), 'bytes': target.stat().st_size,
              'leaf_instances': len(rows), 'groups': len(groups), 'source_solids': total,
              'unique_sources': len(labels), 'elapsed_s': time.time() - started,
              'length_unit': 'mm', 'coordinate_contract': 'Each exact source T applied once at leaf component',
              'STEP_schema': 'AP242DIS', 'external_references_requested': False,
              'color_meaning': 'Visual role only; not engineering material or density',
              'source_geometry_validity_release': False,
              'source_import_diagnostics': SOURCE_DIAGNOSTICS,
              'representation_roles': dict(collections.Counter(r['representation_role'] for r in rows))}
    persist(state, 'build', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


def read_assembly(state):
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    reader.SetColorMode(True)
    assert reader.ReadFile(str(outpath(state))) == IFSelect_RetDone
    global_check = reader.Reader().Model().GlobalCheck(True)
    assert global_check.NbFails() == 0, [global_check.CFail(i) for i in range(1, global_check.NbFails() + 1)]
    doc = TDocStd_Document(TCollection_ExtendedString('XmlXCAF'))
    assert reader.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    assert roots.Length() == 1, f'Expected one free assembly, found {roots.Length()}'
    return doc, st, roots.Value(1)


def leaves(st, root):
    found = []
    def visit(label, T, instance_name=''):
        if st.IsReference_s(label):
            ref = TDF_Label()
            assert st.GetReferredShape_s(label, ref)
            return visit(ref, T @ matrix(st.GetLocation_s(label)), getname(label))
        seq = TDF_LabelSequence()
        if st.GetComponents_s(label, seq, False) and seq.Length():
            for i in range(1, seq.Length() + 1):
                visit(seq.Value(i), T)
        else:
            found.append((instance_name or getname(label), label, T))
    visit(root, np.eye(4))
    return found


def verify(state):
    started = time.time()
    data, groups, rows = load_map(state)
    old = json.loads(RECEIPT.read_text(encoding='utf-8'))['states'][state]['build']
    assert old['sha256'] == sha(outpath(state))
    doc, st, root = read_assembly(state)
    found = leaves(st, root)
    expected = {r['id']: r for r in rows}
    actual_names = [x[0] for x in found]
    assert len(actual_names) == len(set(actual_names)) == 1110
    assert set(actual_names) == set(expected), {'missing': sorted(set(expected) - set(actual_names)),
                                               'extra': sorted(set(actual_names) - set(expected))}
    maximum, total, errors = 0., 0, []
    for ident, label, T in found:
        delta = float(np.max(np.abs(T - np.asarray(expected[ident]['T_S_local']))))
        maximum = max(maximum, delta)
        assert delta < 1e-7, (ident, delta)
        n = solids(st.GetShape_s(label))
        total += n
        if n != expected[ident]['expected_solids']:
            errors.append({'id': ident, 'actual': n, 'expected': expected[ident]['expected_solids']})
    assert not errors, errors
    assert total == data['states'][state]['expected_solids']
    result = {'status': 'NAMED_LEAF_COUNTS_AND_TRANSFORMS_REOPENED',
              'path': str(outpath(state)), 'sha256': sha(outpath(state)),
              'root_name': getname(root), 'leaf_instances': len(found), 'solids': total,
              'names_exact_set_and_unique': True, 'max_absolute_T_entry_error': maximum,
              'T_tolerance_mm_and_dimensionless': 1e-7,
              'all_leaf_solid_counts_match_source_map': True,
              'exported_STEP_global_syntactic_failures': 0,
              'validator': 'Fresh-process OCP STEPCAFControl_Reader, named XCAF recursion',
              'geometry_boolean_equivalence_rechecked': False,
              'elapsed_s': time.time() - started}
    persist(state, 'verify', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


def vtk_mesh(shape):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRep import BRep_Tool
    from OCP.TopoDS import TopoDS
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_EDGE
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    mesh = BRepMesh_IncrementalMesh(shape, 0.35, False, 0.30, False)
    mesh.Perform()
    assert mesh.IsDone()
    point_blocks, triangle_blocks, offset = [], [], 0
    unmeshed, fallback_curves = [], []
    face_index = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        face_index += 1
        location = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, location)
        if tri is None:
            props = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, props)
            unmeshed.append({'face_index': face_index, 'surface_area_mm2': abs(props.Mass()),
                            'display': 'Boundary curves only; original BRep preserved in STEP'})
            edges = TopExp_Explorer(face, TopAbs_EDGE)
            while edges.More():
                edge = TopoDS.Edge_s(edges.Current())
                if not BRep_Tool.Degenerated_s(edge):
                    curve = BRepAdaptor_Curve(edge)
                    u0, u1 = curve.FirstParameter(), curve.LastParameter()
                    if np.isfinite([u0, u1]).all():
                        pts = [curve.Value(float(u)) for u in np.linspace(u0, u1, 17)]
                        fallback_curves.append(np.asarray([[p.X(), p.Y(), p.Z()] for p in pts], dtype=np.float32))
                edges.Next()
            exp.Next()
            continue
        tr = location.Transformation()
        pts = np.asarray([[p.X(), p.Y(), p.Z()] for p in
                         [tri.Node(i).Transformed(tr) for i in range(1, tri.NbNodes() + 1)]], dtype=np.float32)
        cells = np.asarray([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)], dtype=np.int64) - 1 + offset
        if face.Orientation() == TopAbs_REVERSED:
            cells[:, [1, 2]] = cells[:, [2, 1]]
        point_blocks.append(pts)
        triangle_blocks.append(cells)
        offset += len(pts)
        exp.Next()
    assert point_blocks, 'No faces could be tessellated'
    points = np.concatenate(point_blocks + fallback_curves)
    cells = np.concatenate(triangle_blocks)
    vp = vtk.vtkPoints()
    vp.SetData(numpy_to_vtk(points, deep=True))
    ca = vtk.vtkCellArray()
    packed = np.column_stack((np.full(len(cells), 3, dtype=np.int64), cells)).ravel()
    ca.SetCells(len(cells), numpy_to_vtkIdTypeArray(packed, deep=True))
    poly = vtk.vtkPolyData()
    poly.SetPoints(vp)
    poly.SetPolys(ca)
    if fallback_curves:
        lines = vtk.vtkCellArray()
        start = sum(len(x) for x in point_blocks)
        for curve in fallback_curves:
            line = vtk.vtkPolyLine()
            line.GetPointIds().SetNumberOfIds(len(curve))
            for j in range(len(curve)):
                line.GetPointIds().SetId(j, start + j)
            lines.InsertNextCell(line)
            start += len(curve)
        poly.SetLines(lines)
    return poly, len(cells), unmeshed


def render(state):
    assert state == 'service'
    import vtk
    started = time.time()
    data, groups, rows = load_map(state)
    expected = {r['id']: r for r in rows}
    receipt = json.loads(RECEIPT.read_text(encoding='utf-8'))
    assert receipt['states'][state]['verify']['status'] == 'NAMED_LEAF_COUNTS_AND_TRANSFORMS_REOPENED'
    assert receipt['states'][state]['verify']['sha256'] == sha(outpath(state))
    # Render the actual reopened delivery; shared source shape meshes avoid 1110 copies.
    doc, st, root = read_assembly(state)
    found = leaves(st, root)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(2400, 1500)
    window.SetMultiSamples(4)
    main = vtk.vtkRenderer()
    detail = vtk.vtkRenderer()
    main.SetViewport(0., 0., 0.71, 1.)
    detail.SetViewport(0.71, 0., 1., 1.)
    for ren in [main, detail]:
        ren.SetBackground(0.035, 0.055, 0.085)
        ren.SetBackground2(0.13, 0.18, 0.24)
        ren.GradientBackgroundOn()
        window.AddRenderer(ren)
    meshes, triangle_total, unmeshed_sources = {}, 0, []
    all_bounds = np.asarray([np.inf, -np.inf, np.inf, -np.inf, np.inf, -np.inf])
    for index, (ident, label, T) in enumerate(found):
        row = expected[ident]
        key = row['step_path']
        if key not in meshes:
            poly, n, omitted = vtk_mesh(st.GetShape_s(label))
            if omitted:
                unmeshed_sources.append({'id': ident, 'source': key, 'faces': omitted,
                                         'count': len(omitted),
                                         'surface_area_mm2': sum(f['surface_area_mm2'] for f in omitted)})
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(poly)
            meshes[key] = (mapper, n)
        mapper, n = meshes[key]
        triangle_total += n
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        m = vtk.vtkMatrix4x4()
        for i in range(4):
            for j in range(4):
                m.SetElement(i, j, float(T[i, j]))
        actor.SetUserMatrix(m)
        actor.GetProperty().SetColor(*color(row))
        actor.GetProperty().SetInterpolationToPhong()
        actor.GetProperty().SetAmbient(0.2)
        actor.GetProperty().SetDiffuse(0.72)
        actor.GetProperty().SetSpecular(0.20)
        actor.GetProperty().SetSpecularPower(26)
        if 'ENVELOPE' in row['representation_role']:
            actor.GetProperty().SetOpacity(0.35)
        main.AddActor(actor)
        detail.AddActor(actor)
        b = np.asarray(actor.GetBounds())
        all_bounds[::2] = np.minimum(all_bounds[::2], b[::2])
        all_bounds[1::2] = np.maximum(all_bounds[1::2], b[1::2])
        if index % 150 == 0:
            print(f'render {index + 1}/{len(found)}, unique meshes={len(meshes)}', flush=True)
    center = (all_bounds[::2] + all_bounds[1::2]) / 2
    camera = main.GetActiveCamera()
    camera.SetViewUp(0, 0, 1)
    camera.SetFocalPoint(*center)
    camera.SetPosition(*(center + np.asarray([1.3, -1.8, 1.25]) * 1700))
    main.ResetCamera()
    camera.Zoom(1.12)
    main.ResetCameraClippingRange()
    c2 = detail.GetActiveCamera()
    c2.SetViewUp(0, 0, 1)
    c2.SetFocalPoint(0, 0, 10)
    c2.SetPosition(900, -1200, 650)
    c2.ParallelProjectionOn()
    c2.SetParallelScale(430)
    detail.ResetCameraClippingRange()
    def text_actor(ren, title, xy, size, rgb):
        actor = vtk.vtkTextActor()
        actor.SetInput(title)
        actor.GetTextProperty().SetFontFamilyToArial()
        actor.GetTextProperty().SetFontSize(size)
        actor.GetTextProperty().SetColor(*rgb)
        actor.SetPosition(*xy)
        ren.AddActor2D(actor)
    text_actor(main, 'SERVICE STAR / INTEGRATED SERVICE CONFIGURATION', (45, 1425), 30, (.92, .96, 1.))
    text_actor(main, '1110 named instances | 1513 source solids | actual exported STEP geometry', (45, 1380), 23, (.65, .78, .90))
    text_actor(main, 'REFERENCE DIGITAL PROTOTYPE  -  2026-09-19', (45, 65), 23, (.65, .78, .90))
    text_actor(main, 'Proxy/envelope parts included. Colors show visual roles, not assigned engineering materials.', (45, 30), 19, (.70, .76, .83))
    text_actor(detail, 'BODY / INTERFACE DETAIL', (25, 1425), 26, (.92, .96, 1.))
    text_actor(detail, 'Same assembly; closer view', (25, 1380), 20, (.65, .78, .90))
    text_actor(detail, 'Geometry review candidate\nB601 face tessellation limits disclosed\nSystem qualification remains open', (25, 40), 20, (.80, .75, .61))
    window.Render()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetInputBufferTypeToRGB()
    capture.ReadFrontBufferOff()
    capture.Update()
    PNG.parent.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(PNG))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    window.Finalize()
    result = {'status': 'ACTUAL_EXPORTED_STEP_RENDERED_VISUAL_REVIEW_PENDING',
              'path': str(PNG), 'sha256': sha(PNG), 'pixels': [2400, 1500],
              'actual_geometry_source': str(outpath(state)), 'source_step_sha256': sha(outpath(state)),
              'exported_STEP_global_syntactic_failures': 0,
              'rendered_leaf_instances': len(found), 'unique_meshes': len(meshes),
              'instanced_triangles': triangle_total, 'mesh_linear_deflection_mm': 0.35,
              'unmeshed_face_boundary_fallback': unmeshed_sources,
              'unmeshed_face_count_unique_sources': sum(x['count'] for x in unmeshed_sources),
              'render_engine': 'OCP BRepMesh + VTK offscreen', 'world_bounds_mm': all_bounds.tolist(),
              'projection': 'Main perspective plus body orthographic detail',
              'view_limitations': ['Occluded internal interfaces are not verified by this image',
                                   'Translucent functional envelopes are included',
                                   'Facet and screen resolution do not establish fit or clearance',
                                   'Colors do not establish physical material assignments'],
              'elapsed_s': time.time() - started}
    persist(state, 'render', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', choices=['service', 'parking', 'released'], required=True)
    parser.add_argument('--mode', choices=['build', 'verify', 'render'], required=True)
    args = parser.parse_args()
    try:
        globals()[args.mode](args.state)
    except Exception as exc:
        persist(args.state, args.mode, {'status': 'FAILED_CLOSED', 'type': type(exc).__name__, 'error': str(exc)})
        raise
