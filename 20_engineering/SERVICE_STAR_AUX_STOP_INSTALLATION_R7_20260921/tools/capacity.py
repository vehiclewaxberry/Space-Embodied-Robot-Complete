"""How much horizontal board area is actually left in the upper bay, and who holds it.

Two passes over the same voxel grid:

  all        every host row is an obstacle
  hardware   the reserved *functional envelopes* (routing corridors and max-size
             allocations that are claims on volume, not manufactured parts) are
             dropped, so the difference shows what is blocked by hardware and
             what is blocked by a reservation somebody could renegotiate

For each pass and each required slab height it reports the largest free
axis-aligned rectangle in plan view, which is the largest horizontal board that
could be installed there. Voxels come from bounding boxes, so the areas reported
are lower bounds, never optimistic.
"""
from geometry import *
from free_space import occupancy, UPPER_BAY
import argparse

# Rows whose representation_role or id marks them as a reserved volume rather
# than a manufactured body.
RESERVATION_IDS = ('WP10_INTERNAL_BATTERY_BYPASS', 'WP10_RRC3570_4_D_MAX_ENVELOPE',
                   'PROP_PWR_ROUTE', 'PROP_DATA_ROUTE', 'launch_interface_reserved_volume',
                   'equipment_adcs_propulsion_allocation')


def largest_rectangle(mask):
    """Largest all-True axis-aligned rectangle in a 2-D boolean mask."""
    nx, ny = mask.shape
    best = (0, 0, 0, 0, 0)  # area, i0, j0, w, h
    heights = np.zeros(ny, dtype=int)
    for i in range(nx):
        heights = np.where(mask[i], heights + 1, 0)
        stack = []
        for j in range(ny + 1):
            h = heights[j] if j < ny else 0
            start = j
            while stack and stack[-1][1] >= h:
                s, sh = stack.pop()
                area = sh * (j - s)
                if area > best[0]:
                    best = (area, i - sh + 1, s, sh, j - s)
                start = s
            stack.append((start, h))
    return best


def report(host, tag, step):
    lo = [UPPER_BAY[k][0] for k in ('x', 'y', 'z')]
    grid, (nx, ny, nz) = occupancy(host, lo, [UPPER_BAY[k][1] for k in ('x', 'y', 'z')], step)
    free = ~grid
    out = []
    for h_mm in (35.0, 30.5, 25.0, 21.6, 15.0, 10.0):
        sz = int(np.ceil(h_mm / step))
        best = (0,)
        at = None
        for k in range(nz - sz + 1):
            slab = free[:, :, k:k + sz].all(axis=2)
            r = largest_rectangle(slab)
            if r[0] > best[0]:
                best = r
                at = k
        if best[0] == 0:
            out.append(dict(slab_height_mm=h_mm, largest_free_plan_mm=[0, 0], area_mm2=0, at=None))
            print('  %-8s slab %5.1f mm -> nothing' % (tag, h_mm), flush=True)
            continue
        w, d = best[3] * step, best[4] * step
        origin = [lo[0] + best[1] * step, lo[1] + best[2] * step, lo[2] + at * step]
        out.append(dict(slab_height_mm=h_mm, largest_free_plan_mm=[w, d], area_mm2=w * d,
                        origin_S_mm=origin))
        print('  %-8s slab %5.1f mm -> %6.1f x %6.1f mm at S%s' % (
            tag, h_mm, w, d, [round(v, 1) for v in origin]), flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', type=float, default=2.5)
    a = ap.parse_args()
    host = host_rows()['service']
    hardware = [r for r in host if r['id'] not in RESERVATION_IDS]
    dropped = sorted({r['id'] for r in host} & set(RESERVATION_IDS))
    print('upper bay %s, step %.1f mm' % (UPPER_BAY, a.step), flush=True)
    print('all rows %d ; reservation rows dropped in second pass: %s' % (len(host), dropped), flush=True)
    res = dict(schema='R7_BAY_CAPACITY_V1', step_mm=a.step, upper_bay=UPPER_BAY,
               occupancy_from='HOST_AXIS_ALIGNED_BOUNDING_BOXES_CONSERVATIVE',
               reservation_ids_dropped_in_hardware_pass=dropped,
               required_STOP_envelope_mm=[92.0, 72.0, 30.5],
               required_AUX_envelope_mm=[62.0, 72.0, 21.6])
    print('pass: all obstacles', flush=True)
    res['all'] = report(host, 'all', a.step)
    print('pass: hardware only (reservations dropped)', flush=True)
    res['hardware_only'] = report(hardware, 'hardware', a.step)
    write(D / 'results/BAY_CAPACITY.json', res)
