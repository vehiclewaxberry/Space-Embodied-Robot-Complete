"""What do the +/-Y walls really look like under and around the CF1 lugs?

Each wall STEP (as bound by the V27 parent rows shear_web_1 / shear_web_-1, with their transforms) is ONE solid:
a 2 mm inner web, a 2 mm gap layer that contains only discrete bridge blocks, and an 8 mm outer radiator
panel (see mechanical/fixed_heat_common.py). The V27 bounding boxes extend inward to S y 96.5 / -83.5 only
because of the CHB cold-finger bridge. This receipt records, from 0.25 mm y-slabs inside each lug footprint
and a 5 mm x/z occupancy scan of the gap layer over the whole wall:
  * the web inner face, web thickness, gap thickness, panel thickness (sub-mm, from the slab profile);
  * whether ANY bridge material exists in the gap layer under the lug footprint (it does not);
  * every bridge block in the gap layer (bbox, area) and the distance from the lug footprint to the nearest one;
  * the TIM-plane contact area of the current lug boxes with the wall (0.2 mm slab common volume / 0.2).
The thermal model (thermal_cf1.py) reads the bridge patches and web thickness from this file; the geometry
file no longer restates them. OCP only, read-only on the host. Output: results/mechanical/WEB_FACE_PROBE_CF1.json
"""
from pathlib import Path
import json, hashlib
import numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.gp import gp_Trsf, gp_Pnt
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

HERE = Path(__file__).resolve().parent
C = HERE.parent
A = C.parent
R = C / 'results/mechanical'
SPEC = C / 'mechanical/THERMAL_PATH_GEOMETRY_CF1.json'
FINE = 0.25          # mm, y-slab resolution inside the lug footprint
CELL = 5.0           # mm, x/z occupancy cell for the gap-layer scan


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def step(p):
    r = STEPControl_Reader(); assert r.ReadFile(str(p)) == 1, p; r.TransferRoots(); return r.OneShape()


def tr(s, T):
    t = gp_Trsf(); t.SetValues(*[float(T[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(s, t, True).Shape()


def box(x0, y0, z0, x1, y1, z1):
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()


def vol(s):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); return g.Mass()


def common(a, b):
    c = BRepAlgoAPI_Common(a, b); c.Build(); assert c.IsDone(); return vol(c.Shape())


def n_solids(s):
    ex = TopExp_Explorer(s, TopAbs_SOLID); n = 0
    while ex.More():
        n += 1; ex.Next()
    return n


def layers_from_profile(ys, fills, sign):
    """Contiguous runs of filled / empty fine slabs, ordered from the wall's inner side outward."""
    runs = []
    for y, f in zip(ys, fills):
        state = 'material' if f >= 0.5 else 'empty'
        if runs and runs[-1]['state'] == state:
            runs[-1]['y1'] = y + FINE; runs[-1]['n'] += 1; runs[-1]['fill_sum'] += f
        else:
            runs.append(dict(state=state, y0=y, y1=y + FINE, n=1, fill_sum=f))
    for r in runs:
        r['thickness_mm'] = round(r['y1'] - r['y0'], 3); r['mean_fill'] = round(r['fill_sum'] / r['n'], 4); del r['fill_sum']; del r['n']
    # drop leading/trailing empties, then order inner->outer
    while runs and runs[0]['state'] == 'empty':
        runs.pop(0)
    while runs and runs[-1]['state'] == 'empty':
        runs.pop()
    if sign < 0:
        runs = runs[::-1]
    return runs


def main():
    R.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC.read_text(encoding='utf-8')); off = spec['frame']['S_from_module_mm']
    par = json.loads((A / 'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json').read_text(encoding='utf-8-sig'))
    rad = json.loads((A / 'thermal/RADIATOR_OBSTACLE_BOUNDS.json').read_text(encoding='utf-8-sig'))
    rows = {r['id']: r for r in par['states']['service'] if r['id'] in ('shear_web_-1', 'shear_web_1')}
    rad_rows = {r['id']: r for r in rad['states']['service'] if r['id'] in ('shear_web_-1', 'shear_web_1')}
    hosts = {k: tr(step(r['step_path']), r['T_S_step']) for k, r in rows.items()}
    boxes = {p['id']: p['boxes_module_mm'] for p in spec['parts']}
    def S(b):
        return [b[0] + off[0], b[1] + off[1], b[2] + off[2], b[0] + b[3] + off[0], b[1] + b[4] + off[1], b[2] + b[5] + off[2]]
    out = dict(schema='CF1_WEB_FACE_PROBE', parent_bounds_sha256=sha(A / 'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json'),
               fine_slab_mm=FINE, gap_scan_cell_mm=CELL, webs={})
    for wid, lug_id, sign in [('shear_web_1', 'CF1_LUG_PLUS_Y', +1), ('shear_web_-1', 'CF1_LUG_MINUS_Y', -1)]:
        r = rows[wid]; h = hosts[wid]; lb = S(boxes[lug_id][0])
        x0, x1, z0, z1 = lb[0], lb[3], lb[2], lb[5]; full = (x1 - x0) * (z1 - z0)
        # 1 fine y profile inside the lug footprint
        # slab boundaries are aligned to the V27 bbox outer face (+/-113.15) so that faces at x.15 fall on the grid
        ys = np.arange(84.15, 114.15, FINE) if sign > 0 else np.arange(-114.15, -84.15, FINE)
        fills = []
        for y in ys:
            v = common(box(x0, float(y), z0, x1, float(y) + FINE, z1), h); fills.append(v / (full * FINE))
        runs = layers_from_profile([float(y) for y in ys], fills, sign)
        mats = [ru for ru in runs if ru['state'] == 'material']; gaps = [ru for ru in runs if ru['state'] == 'empty']
        web = mats[0]; panel = mats[-1]; gap = gaps[0] if gaps else None
        inner_face = web['y0'] if sign > 0 else web['y1']
        # 2 bridge material in the gap layer under the lug footprint and over the whole wall
        gy0, gy1 = (gap['y0'] + 0.05, gap['y1'] - 0.05) if gap else (None, None)
        gap_under_lug = common(box(x0, gy0, z0, x1, gy1, z1), h) if gap else None
        bridges = []
        if gap:
            grid = {}
            for x in np.arange(-172.0, 172.0, CELL):
                for z in np.arange(-101.0, 101.0, CELL):
                    v = common(box(float(x), gy0, float(z), float(x) + CELL, gy1, float(z) + CELL), h)
                    if v > 1e-6:
                        grid[(float(x), float(z))] = v
            # cluster occupied cells into blocks (4-connectivity)
            seen = set()
            for key in grid:
                if key in seen:
                    continue
                stack = [key]; cells = []
                while stack:
                    k = stack.pop()
                    if k in seen or k not in grid:
                        continue
                    seen.add(k); cells.append(k)
                    stack += [(k[0] + CELL, k[1]), (k[0] - CELL, k[1]), (k[0], k[1] + CELL), (k[0], k[1] - CELL)]
                xs = [c[0] for c in cells]; zs = [c[1] for c in cells]; v = sum(grid[c] for c in cells)
                bx = [min(xs), max(xs) + CELL, min(zs), max(zs) + CELL]
                # refine the block bbox with the exact common of a slightly larger box
                bridges.append(dict(bbox_x0=bx[0], bbox_x1=bx[1], bbox_z0=bx[2], bbox_z1=bx[3], volume_mm3=round(v, 2),
                                    area_mm2=round(v / (gy1 - gy0), 2), cells=len(cells)))
            for b in bridges:
                # distance from the lug footprint box (in the gap layer) to this block's material
                blk = box(b['bbox_x0'], gy0, b['bbox_z0'], b['bbox_x1'], gy1, b['bbox_z1'])
                c = BRepAlgoAPI_Common(blk, h); c.Build(); mat = c.Shape()
                d = BRepExtrema_DistShapeShape(box(x0, gy0, z0, x1, gy1, z1), mat); d.Perform()
                b['distance_from_lug_footprint_mm'] = round(d.Value(), 3)
                b['patch_center_ab_mm'] = [round(0.5 * (b['bbox_x0'] + b['bbox_x1']), 2), round(0.5 * (b['bbox_z0'] + b['bbox_z1']), 2)]
                b['patch_size_ab_mm'] = [round(b['bbox_x1'] - b['bbox_x0'], 2), round(b['bbox_z1'] - b['bbox_z0'], 2)]
            bridges.sort(key=lambda b: b['distance_from_lug_footprint_mm'])
        # 3 contact of the CURRENT lug box with the wall at its web-side face
        yf = lb[4] if sign > 0 else lb[1]
        slab = box(x0, yf, z0, x1, yf + 0.2, z1) if sign > 0 else box(x0, yf - 0.2, z0, x1, yf, z1)
        contact_mm2 = common(slab, h) / 0.2
        d = BRepExtrema_DistShapeShape(box(*lb), h); d.Perform()
        out['webs'][wid] = dict(
            step_path=r['step_path'], source_sha256=r['source_sha256'], T_S_step=r['T_S_step'], bbox_S_mm=r['bbox_S_mm'], solids=n_solids(h),
            thermal_side_binding=dict(step_path=rad_rows[wid]['step_path'], source_sha256=rad_rows[wid]['source_sha256'],
                                      same_file_as_V27=rad_rows[wid]['source_sha256'] == r['source_sha256']),
            lug_id=lug_id, lug_box_S_mm=lb, footprint_mm2=full,
            fine_profile=[dict(y0=round(float(y), 3), fill=round(f, 4)) for y, f in zip(ys, fills) if f > 0],
            layers_inner_to_outer=runs,
            inner_face_S_y=round(inner_face, 3), web_thickness_mm=web['thickness_mm'],
            gap_thickness_mm=(gap['thickness_mm'] if gap else 0.0), panel_thickness_mm=panel['thickness_mm'],
            outer_face_S_y=round(panel['y1'] if sign > 0 else panel['y0'], 3),
            gap_material_under_lug_mm3=(round(gap_under_lug, 3) if gap else None),
            gap_bridges=bridges, nearest_bridge_distance_mm=(bridges[0]['distance_from_lug_footprint_mm'] if bridges else None),
            current_lug_web_face_S_y=yf, current_lug_contact_mm2=round(contact_mm2, 2), current_lug_contact_fraction=round(contact_mm2 / full, 4),
            current_lug_to_web_distance_mm=d.Value(),
            note='Contact is with the 2 mm inner web only. The radiating 8 mm panel is reached through the gap-layer bridges listed in '
                 'gap_bridges; there is no bridge under either lug, so the thermal model must carry the web laterally to the nearest bridge.')
        print(json.dumps(dict(wall=wid, inner_face=round(inner_face, 3), web_mm=web['thickness_mm'], gap_mm=(gap['thickness_mm'] if gap else 0), panel_mm=panel['thickness_mm'],
                              gap_under_lug=(round(gap_under_lug, 2) if gap else None), bridges=len(bridges), nearest=(bridges[0]['distance_from_lug_footprint_mm'] if bridges else None),
                              contact=round(contact_mm2, 1))))
    (R / 'WEB_FACE_PROBE_CF1.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
