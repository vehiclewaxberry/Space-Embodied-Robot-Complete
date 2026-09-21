"""Render nine actual merged STEP candidates with OCP meshes and matplotlib.

No SolidWorks, image generation, CAD regeneration or upstream mutations.
Output colors are for geometry visibility and are not material assignments.
"""
from pathlib import Path
import hashlib
import json
import math
import datetime as dt

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.TopLoc import TopLoc_Location
from OCP.TopExp import TopExp_Explorer, TopExp
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_REVERSED
from OCP.TopoDS import TopoDS
from OCP.TopTools import TopTools_IndexedMapOfShape

D = Path(__file__).resolve().parents[1]
SOURCE = D / 'results/INTERFACE_MERGE.json'
PNG = D / 'views/INTERFACE_9_CANDIDATES.png'
CHECK = D / 'results/INTERFACE_VISUAL_CHECK.json'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def triangulate(path):
    reader = STEPControl_Reader()
    assert reader.ReadFile(str(path)) == IFSelect_RetDone
    assert reader.TransferRoots() > 0
    shape = reader.OneShape()
    mesher = BRepMesh_IncrementalMesh(shape, 0.10, False, 0.20, False)
    mesher.Perform()
    assert mesher.IsDone()
    triangles = []
    faces = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        where = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, where)
        assert triangulation is not None
        transform = where.Transformation()
        nodes = np.asarray([[p.X(), p.Y(), p.Z()] for p in
                            [triangulation.Node(i).Transformed(transform)
                             for i in range(1, triangulation.NbNodes() + 1)]])
        for i in range(1, triangulation.NbTriangles() + 1):
            ijk = list(triangulation.Triangle(i).Get())
            if face.Orientation() == TopAbs_REVERSED:
                ijk[1], ijk[2] = ijk[2], ijk[1]
            triangles.append(nodes[np.asarray(ijk) - 1])
        faces += 1
        explorer.Next()
    edges = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, edges)
    curves = []
    for i in range(1, edges.Extent() + 1):
        edge = TopoDS.Edge_s(edges.FindKey(i))
        if BRep_Tool.Degenerated_s(edge):
            continue
        curve = BRepAdaptor_Curve(edge)
        u0, u1 = curve.FirstParameter(), curve.LastParameter()
        assert math.isfinite(u0) and math.isfinite(u1)
        # Use exact edge curves for visible hole outlines, not triangle edges.
        n = 2 if 'Line' in str(curve.GetType()) else 49
        points = [curve.Value(float(u)) for u in np.linspace(u0, u1, n)]
        curves.append(np.asarray([[p.X(), p.Y(), p.Z()] for p in points]))
    return np.asarray(triangles), curves, faces


def main():
    assert not PNG.exists() and not CHECK.exists(), 'Refuse replacing prior visual evidence'
    data = json.loads(SOURCE.read_text(encoding='utf8'))
    assert len(data['rows']) == 9 and data['candidate_count'] == 9
    source_hash = sha(SOURCE)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    fig = plt.figure(figsize=(18, 16), facecolor='#f7f9fc')
    fig.suptitle('Nine merged interface candidates', fontsize=24, fontweight='bold', y=.977, color='#172638')
    fig.text(.5, .951, 'Actual STEP geometry  |  preserved WP10 substrate + R01/R07 cuts  |  no assembly or qualification credit',
             ha='center', fontsize=11, color='#465466')
    light = np.array([.2, -.5, 1.])
    light /= np.linalg.norm(light)
    records = []
    for number, r in enumerate(data['rows'], 1):
        path = Path(r['output']['path'])
        assert sha(path) == r['output']['sha256']
        triangles, curves, face_count = triangulate(path)
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        lengths = np.linalg.norm(normals, axis=1)
        normals /= np.maximum(lengths[:, None], 1e-15)
        shade = .62 + .32 * np.maximum(normals @ light, 0.)
        rgb = np.array([.54, .69, .81])
        colors = np.clip(shade[:, None] * rgb, 0, 1)
        ax = fig.add_subplot(3, 3, number, projection='3d', computed_zorder=False)
        ax.set_facecolor('#f7f9fc')
        polygons = Poly3DCollection(triangles, facecolors=colors, edgecolors='none', linewidths=0., zorder=1)
        ax.add_collection3d(polygons)
        ax.add_collection3d(Line3DCollection(curves, colors='#233442', linewidths=.28, alpha=.85, zorder=2), autolim=False)
        bounds = r['candidate_facts']['bbox_mm']
        low, high = np.array(bounds['min_mm']), np.array(bounds['max_mm'])
        center, widths = (low + high) / 2, high - low
        half = max(widths) * .52
        ax.set_xlim(center[0] - half, center[0] + half)
        ax.set_ylim(center[1] - half, center[1] + half)
        ax.set_zlim(center[2] - half, center[2] + half)
        ax.set_box_aspect((1, 1, 1))
        ax.set_proj_type('ortho')
        if 'shear_web' in r['id']:
            elevation, azimuth = 10, -75 if r['id'].endswith('-1') else 75
        elif 'angle' in r['id']:
            elevation, azimuth = 32, -65 if '_-1_' in r['id'] else 65
        else:
            elevation, azimuth = 64, -65
        ax.view_init(elev=elevation, azim=azimuth)
        ax.set_axis_off()
        label = r['host_id'].replace('lower_equipment_deck_B', 'Lower equipment deck B').replace('upper_equipment_deck_B', 'Upper equipment deck B')
        ax.set_title(f'{number:02d}  {label}', fontsize=12, fontweight='bold', color='#172638', pad=0)
        difference = r['source_facts']['X']['volume_mm3'] - r['candidate_facts']['volume_mm3']
        note = 'X unchanged geometrically' if abs(difference) < r['zero_volume_tolerance_mm3'] else f'Additional cut: {difference:.3f} mm3'
        ax.text2D(.5, .025, note + '\n' + ' x '.join(f'{v:.2f}' for v in widths) + ' mm',
                  transform=ax.transAxes, ha='center', va='bottom', fontsize=9, color='#465466')
        records.append({'panel': number, 'id': r['id'], 'host_id': r['host_id'],
                        'STEP_path': str(path), 'STEP_sha256': sha(path), 'triangle_count': len(triangles),
                        'face_count': face_count, 'edge_curve_count': len(curves),
                        'camera': {'elevation_deg': elevation, 'azimuth_deg': azimuth, 'projection': 'ORTHOGRAPHIC'},
                        'bounds_mm': bounds, 'additional_cut_from_X_mm3': difference,
                        'visual_observation': 'PENDING_MODEL_IMAGE_REVIEW'})
    fig.text(.5, .016, 'Equal X/Y/Z scale inside each panel; panel scales differ. Colors identify geometry only, not assigned materials.\n'
             'Legacy holes remain by design. Screenshots do not establish hole dimensions, bearing edges, fit, strength or thermal performance.',
             ha='center', fontsize=10, color='#465466')
    fig.subplots_adjust(left=.015, right=.985, bottom=.06, top=.925, wspace=.02, hspace=.11)
    PNG.parent.mkdir(exist_ok=True)
    fig.savefig(PNG, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    assert sha(SOURCE) == source_hash
    report = {'schema': 'INTERFACE_VISUAL_CHECK_V1', 'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'status': 'RENDERED_PENDING_MODEL_IMAGE_REVIEW', 'method': 'OCP actual STEP tessellation + exact-edge curve overlay + matplotlib orthographic rasterization',
              'input_receipt': {'path': str(SOURCE), 'sha256': source_hash}, 'generator': {'path': str(Path(__file__)), 'sha256': sha(__file__)},
              'image': {'path': str(PNG), 'sha256': sha(PNG), 'pixels': [2880, 2560]},
              'mesh_parameters': {'linear_deflection_mm': .10, 'angular_deflection_rad': .20, 'parallel': False},
              'panels': records, 'source_files_mutated': False, 'solidworks_started': False,
              'CAD_generation_executed': False, 'whole_assembly_fit_evaluated': False,
              'independent_review': False, 'material_assignment_credit': False,
              'limitations': ['One view per part does not expose every occluded hole.',
                             'Matplotlib edge overlays may show edges through a nearer surface; actual solid surfaces are tessellated STEP.',
                             'Legacy open holes and bearing-edge completeness need new source-specific checks.',
                             'Geometry colors are not SolidWorks physical material assignments.']}
    CHECK.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf8'))
    print(json.dumps({'image': str(PNG), 'report': str(CHECK), 'triangles': sum(q['triangle_count'] for q in records)}))


if __name__ == '__main__':
    main()
