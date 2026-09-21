"""Centre the AUX board in the gap under the RB bridge, and verify it per solid.

The only structure that spans the whole AUX footprint is WP01-RB-BRIDGE-R2, whose
underside is at z=107.15. Everything load bearing *below* the board sits in
y 29..53 while the board spans y 31.5..91.5, so a bottom mount would leave ~38 mm
of board cantilevered. Hanging the board from the bridge on standoffs keeps the
board plane parallel to the bridge, which is what a bench technician would do and
what avoids any tilted installation.

The usable band is bounded below by the dual battery tie rods (tops at z=72.5) and
above by the bridge underside minus the tallest component (19.595 mm over the board
base). This sweeps that band and reports the clearance either side so the pose can
be centred rather than pushed against a limit.
"""
from geometry import *
from solid_wise import overlap
from search_boards import yaw, corner_pose

BRIDGE_UNDERSIDE = 107.15
TIEROD_TOP = 72.5


def main():
    cov = read(D / 'inputs/AUX_GEOMETRY_COVERAGE.json')
    local = source(cov['board'])
    host = host_rows()['service']
    lo0, hi0 = g.precise_bounds(moved(local, yaw(90)))
    height = hi0[2] - lo0[2]
    print('AUX yawed envelope %.2f x %.2f x %.2f mm' % (hi0[0] - lo0[0], hi0[1] - lo0[1], height))
    print('band: tie rod tops %.2f .. bridge underside %.2f  (%.2f mm for a %.2f mm board)' % (
        TIEROD_TOP, BRIDGE_UNDERSIDE, BRIDGE_UNDERSIDE - TIEROD_TOP, height), flush=True)

    trials = []
    for z in (80.0, 79.0, 81.0, 78.0, 82.0, 77.0, 83.0, 76.0, 84.0, 75.0):
        t = corner_pose(local, 90, (30.5, 31.5, z))
        T = yaw(90)
        T[:3, 3] = t
        s = moved(local, T)
        blo, bhi = g.precise_bounds(s)
        hits, unknown = [], []
        for r in candidates(s, host):
            v, errs = overlap(g, common, s, source(r), b_key=r['id'],
                              bounds=lambda q: g.precise_bounds(q))
            if errs:
                unknown.append(dict(id=r['id'], errors=errs))
            if v > 1e-5:
                hits.append(dict(id=r['id'], volume_mm3=v))
        row = dict(board_base_z_mm=z, yaw_deg=90, tilt_deg=0, T_S_board=T.tolist(),
                   world_bbox_mm={'min_mm': list(blo), 'max_mm': list(bhi)},
                   gap_below_to_tierod_mm=blo[2] - TIEROD_TOP,
                   gap_above_to_bridge_mm=BRIDGE_UNDERSIDE - bhi[2],
                   method='PER_SOLID_BRepAlgoAPI_Common',
                   hits=hits, unknown=unknown, clean=not hits and not unknown)
        trials.append(row)
        print('z=%5.1f  below %+6.2f  above %+6.2f  %s' % (
            z, row['gap_below_to_tierod_mm'], row['gap_above_to_bridge_mm'],
            'CLEAN' if row['clean'] else 'hits=' + ','.join(h['id'] for h in hits[:3])), flush=True)
        write(D / 'results/AUX_BRIDGE_POSE_SWEEP.json',
              dict(schema='R7_AUX_BRIDGE_POSE_V1', bridge_underside_z_mm=BRIDGE_UNDERSIDE,
                   tierod_top_z_mm=TIEROD_TOP, yaw_only=True, tilt_searched=False, trials=trials))

    clean = [t for t in trials if t['clean']]
    best = max(clean, key=lambda t: min(t['gap_below_to_tierod_mm'], t['gap_above_to_bridge_mm'])) if clean else None
    write(D / 'results/AUX_BRIDGE_POSE_SWEEP.json',
          dict(schema='R7_AUX_BRIDGE_POSE_V1', bridge_underside_z_mm=BRIDGE_UNDERSIDE,
               tierod_top_z_mm=TIEROD_TOP, yaw_only=True, tilt_searched=False, trials=trials,
               clean_count=len(clean), selected=best,
               selection_rule='largest minimum of the two end clearances'))
    if best:
        write(D / 'inputs/AUX_INSTALL_POSE.json', dict(
            schema='R7_AUX_INSTALL_POSE_V1', board='AUX', **{k: best[k] for k in (
                'board_base_z_mm', 'yaw_deg', 'tilt_deg', 'T_S_board', 'world_bbox_mm',
                'gap_below_to_tierod_mm', 'gap_above_to_bridge_mm', 'method')},
            mount_reference='WP01-RB-BRIDGE-R2 underside', mount_built=False,
            preload_strength_tool_access_qualified=False, ready_to_power=False, flight_ready=False))
        print('selected board_base_z=%.1f  below %+.2f  above %+.2f' % (
            best['board_base_z_mm'], best['gap_below_to_tierod_mm'],
            best['gap_above_to_bridge_mm']), flush=True)
    else:
        print('NO CLEAN POSE IN BAND', flush=True)


if __name__ == '__main__':
    main()
