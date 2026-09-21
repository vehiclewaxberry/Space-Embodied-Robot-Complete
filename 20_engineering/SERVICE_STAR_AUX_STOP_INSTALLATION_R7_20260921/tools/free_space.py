"""Where, if anywhere, does a horizontal AUX or STOP board still fit after R6H?

Occupancy is voxelised from host axis-aligned bounding boxes, which over-occupies
(a bounding box is never smaller than its shape). So this stage can only be too
pessimistic, never too optimistic: any candidate it reports still has to survive
the real boolean test in search_boards.py, and any candidate it rejects is
reported rather than silently dropped.

Only yaw is varied. The board plane stays parallel to the equipment deck.
"""
from geometry import *
import argparse

STEP = 5.0
CLEAR = 1.0  # mm of clearance demanded on every face of the board envelope

# The pressurised-volume equivalent for this bus: inboard of the two shear webs
# (y -83.5 / +96.5), inboard of the end frames (x +-177), and above the upper
# equipment deck, whose top face is z=-8.5. Outside this box "free" would only
# mean free space outside the spacecraft.
UPPER_BAY = dict(x=(-177.0, 177.0), y=(-83.5, 96.5), z=(-8.5, 110.0))


def occupancy(host, lo, hi, step):
    nx, ny, nz = [int(np.ceil((hi[i] - lo[i]) / step)) for i in range(3)]
    grid = np.zeros((nx, ny, nz), dtype=bool)
    for r in host:
        a, b = world_bounds(r)
        i0, j0, k0 = [max(0, int(np.floor((a[i] - lo[i]) / step))) for i in range(3)]
        i1, j1, k1 = [min([nx, ny, nz][i], int(np.ceil((b[i] - lo[i]) / step)) + 1) for i in range(3)]
        if i0 < i1 and j0 < j1 and k0 < k1:
            grid[i0:i1, j0:j1, k0:k1] = True
    return grid, (nx, ny, nz)


def free_boxes(grid, dims, lo, step, size, label, limit=40):
    """Positions where an axis-aligned box of `size` sits entirely in free voxels."""
    nx, ny, nz = dims
    sx, sy, sz = [int(np.ceil(size[i] / step)) for i in range(3)]
    # 3-D prefix sum of occupancy, so each candidate box is an O(1) lookup.
    c = np.zeros((nx + 1, ny + 1, nz + 1), dtype=np.int64)
    c[1:, 1:, 1:] = np.cumsum(np.cumsum(np.cumsum(grid.astype(np.int64), 0), 1), 2)

    def occupied(i, j, k):
        return (c[i + sx, j + sy, k + sz] - c[i, j + sy, k + sz] - c[i + sx, j, k + sz]
                - c[i + sx, j + sy, k] + c[i, j, k + sz] + c[i, j + sy, k] + c[i + sx, j, k]
                - c[i, j, k])

    out = []
    for i in range(nx - sx + 1):
        for j in range(ny - sy + 1):
            for k in range(nz - sz + 1):
                if occupied(i, j, k) == 0:
                    out.append(dict(label=label,
                                    min_mm=[lo[0] + i * step, lo[1] + j * step, lo[2] + k * step],
                                    size_mm=list(size)))
                    if len(out) >= limit:
                        return out
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', type=float, default=STEP)
    a = ap.parse_args()
    host = host_rows()['service']
    lo = [UPPER_BAY[k][0] for k in ('x', 'y', 'z')]
    hi = [UPPER_BAY[k][1] for k in ('x', 'y', 'z')]
    print('host rows %d  upper bay lo=%s hi=%s' % (len(host), lo, hi), flush=True)
    grid, dims = occupancy(host, lo, hi, a.step)
    print('voxels %s at %.1f mm  occupied %.1f%%' % (dims, a.step, 100 * grid.mean()), flush=True)

    report = dict(schema='R7_FREE_SPACE_V1', step_mm=a.step, clearance_mm=CLEAR,
                  envelope={'min_mm': lo, 'max_mm': hi}, upper_bay=UPPER_BAY,
                  occupancy_from='HOST_AXIS_ALIGNED_BOUNDING_BOXES_CONSERVATIVE',
                  boards={}, yaw_only=True, tilt_searched=False)
    for tag in ('STOP', 'AUX'):
        cov = read(D / 'inputs' / ('%s_GEOMETRY_COVERAGE.json' % tag))
        b = cov['installed_local_bbox_mm']
        raw = [b['max_mm'][i] - b['min_mm'][i] for i in range(3)]
        entry = dict(local_bbox_size_mm=raw, below_board_mm=cov['below_board_extent_mm'],
                     above_stack_mm=cov['above_board_extent_mm'], yaw={})
        for deg in (0, 90):
            size = [raw[1] if deg == 90 else raw[0], raw[0] if deg == 90 else raw[1], raw[2]]
            need = [s + 2 * CLEAR for s in size]
            boxes = free_boxes(grid, dims, lo, a.step, need, '%s_yaw%d' % (tag, deg))
            entry['yaw'][str(deg)] = dict(required_envelope_mm=need, free_positions=len(boxes),
                                          examples=boxes[:8])
            print('%-5s yaw %3d  needs %s mm  ->  %d free voxel positions' % (
                tag, deg, [round(v, 1) for v in need], len(boxes)), flush=True)
        report['boards'][tag] = entry
    write(D / 'results/FREE_SPACE_SCAN.json', report)
