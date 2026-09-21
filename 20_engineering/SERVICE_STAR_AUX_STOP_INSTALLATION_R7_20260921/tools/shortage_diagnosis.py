"""Is the upper bay physically full, or just fully claimed?

Splits upper-bay occupancy into manufactured hardware and reserved volume, and
measures how much of the reserved volume is exclusively reserved — i.e. voxels no
manufactured part occupies. A bay that is full of hardware needs a layout change.
A bay that is full of reservations needs an allocation decision, which is a much
cheaper thing to be blocked on.

Voxels come from bounding boxes and therefore overstate occupancy for both
categories alike; the split between them is what this is for, not an absolute
packing factor.
"""
from geometry import *
from free_space import occupancy, UPPER_BAY
from capacity import RESERVATION_IDS
import argparse

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', type=float, default=2.5)
    a = ap.parse_args()
    host = host_rows()['service']
    lo = [UPPER_BAY[k][0] for k in ('x', 'y', 'z')]
    hi = [UPPER_BAY[k][1] for k in ('x', 'y', 'z')]
    bay_mm3 = np.prod([hi[i] - lo[i] for i in range(3)])

    present = sorted({r['id'] for r in host} & set(RESERVATION_IDS))
    hardware = [r for r in host if r['id'] not in RESERVATION_IDS]
    reserved = [r for r in host if r['id'] in RESERVATION_IDS]

    gh, dims = occupancy(hardware, lo, hi, a.step)
    gr, _ = occupancy(reserved, lo, hi, a.step)
    total = gh | gr
    voxel = a.step ** 3
    only_reserved = gr & ~gh

    out = dict(schema='R7_SHORTAGE_DIAGNOSIS_V1', step_mm=a.step, upper_bay=UPPER_BAY,
               bay_volume_mm3=float(bay_mm3), voxel_mm3=voxel,
               occupancy_from='HOST_AXIS_ALIGNED_BOUNDING_BOXES_CONSERVATIVE',
               reservation_ids=present, reservation_rows=len(reserved),
               hardware_rows=len(hardware),
               hardware_occupied_fraction=float(gh.mean()),
               reserved_occupied_fraction=float(gr.mean()),
               total_occupied_fraction=float(total.mean()),
               exclusively_reserved_fraction=float(only_reserved.mean()),
               free_after_hardware_only_fraction=float((~gh).mean()),
               free_after_everything_fraction=float((~total).mean()))
    print('upper bay %.0f x %.0f x %.0f mm = %.2f litre' % (
        hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], bay_mm3 / 1e6), flush=True)
    print('hardware occupies         %5.1f %%' % (100 * gh.mean()), flush=True)
    print('reserved volumes occupy   %5.1f %%' % (100 * gr.mean()), flush=True)
    print('  of which exclusively    %5.1f %%  (no hardware there at all)' % (100 * only_reserved.mean()), flush=True)
    print('everything together       %5.1f %%' % (100 * total.mean()), flush=True)
    print('free if reservations kept %5.1f %%' % (100 * (~total).mean()), flush=True)
    print('free if reservations lift %5.1f %%' % (100 * (~gh).mean()), flush=True)

    # Per reservation: how much of the bay does each one hold on its own?
    per = []
    for r in reserved:
        gi, _ = occupancy([r], lo, hi, a.step)
        excl = gi & ~gh
        per.append(dict(id=r['id'], fraction_of_bay=float(gi.mean()),
                        exclusive_fraction_of_bay=float(excl.mean()),
                        exclusive_volume_mm3=float(excl.sum() * voxel)))
    per.sort(key=lambda r: -r['exclusive_fraction_of_bay'])
    out['per_reservation'] = per
    print(flush=True)
    for r in per:
        print('   %-38s holds %5.1f %% of bay, %5.1f %% exclusively (%.2f litre)' % (
            r['id'][:38], 100 * r['fraction_of_bay'], 100 * r['exclusive_fraction_of_bay'],
            r['exclusive_volume_mm3'] / 1e6), flush=True)
    write(D / 'results/SHORTAGE_DIAGNOSIS.json', out)
