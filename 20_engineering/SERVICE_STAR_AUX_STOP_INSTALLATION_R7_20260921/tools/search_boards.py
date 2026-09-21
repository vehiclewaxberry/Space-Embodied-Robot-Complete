"""Find horizontal poses for STOP and AUX inside the post-R6H bay.

Only translations and yaw about the spacecraft Z are searched. Roll and pitch are
never varied: the board plane stays parallel to the equipment deck, so no pose
this file can produce is a tilted installation. Every trial is recorded, including
the ones that collide, and a pose is only accepted when the real boolean
intersection against every host candidate is empty and nothing failed to evaluate.

STOP is placed first because its envelope is the constrained one (8.155 mm of
Q101 lead below the board, 20.370 mm of Q101 body above it). AUX is then searched
against the host *plus* the accepted STOP.
"""
from geometry import *
from solid_wise import overlap
import argparse

BAY = dict(x=(-175.0, -50.0), y=(-5.0, 100.0), z=(-8.5, 53.0))


def yaw(deg):
    a = np.radians(deg)
    T = np.eye(4)
    T[0, 0] = T[1, 1] = np.cos(a)
    T[0, 1] = -np.sin(a)
    T[1, 0] = np.sin(a)
    return T


def place(local, x, y, z, deg):
    """Board-local origin to spacecraft S: yaw about Z, then translate. No tilt."""
    T = yaw(deg)
    T[:3, 3] = [x, y, z]
    return T


def survey(host):
    """What the bay looks like before anything new goes in."""
    rows = []
    for r in host:
        lo, hi = world_bounds(r)
        if (hi[0] > BAY['x'][0] and lo[0] < BAY['x'][1] and hi[1] > BAY['y'][0]
                and lo[1] < BAY['y'][1] and hi[2] > BAY['z'][0] and lo[2] < BAY['z'][1]):
            rows.append(dict(id=r['id'], lo=[round(v, 3) for v in lo], hi=[round(v, 3) for v in hi],
                             role=r.get('representation_role')))
    rows.sort(key=lambda r: r['lo'][2])
    return rows


def corner_pose(local, deg, corner):
    """Translation that lands the yawed board's bbox minimum at `corner`."""
    lo, _ = g.precise_bounds(moved(local, yaw(deg)))
    return [corner[i] - lo[i] for i in range(3)]


def trial(local, host, x, y, z, deg, extra=()):
    T = place(local, x, y, z, deg)
    s = moved(local, T)
    hits, unknown = [], []
    for r in candidates(s, list(host) + list(extra)):
        # Per solid: a whole-compound boolean silently loses real overlaps on
        # these PCBA operands (see solid_wise.py).
        v, errs = overlap(g, common, s, source(r), b_key=r['id'],
                          bounds=lambda q: g.precise_bounds(q))
        if errs:
            unknown.append(dict(id=r['id'], errors=errs))
        if v > 1e-5:
            hits.append(dict(id=r['id'], volume_mm3=v))
    lo, hi = g.precise_bounds(s)
    return dict(xyz=[x, y, z], yaw_deg=deg, tilt_deg=0, T_S_board=T.tolist(),
                world_bbox_mm={'min_mm': list(lo), 'max_mm': list(hi)},
                method='PER_SOLID_BRepAlgoAPI_Common',
                hits=hits, unknown=unknown, clean=not hits and not unknown)


def search(tag, grid, host, extra, out, path):
    cov = read(D / 'inputs' / ('%s_GEOMETRY_COVERAGE.json' % tag))
    local = source(cov['board'])
    trials = []
    accepted = None
    for (x, y, z, deg) in grid:
        t = trial(local, host, x, y, z, deg, extra)
        trials.append(t)
        print('%-5s x=%-7.1f y=%-6.1f z=%-6.1f yaw=%-4d %s' % (
            tag, x, y, z, deg,
            'CLEAN' if t['clean'] else 'hits=' + ','.join(h['id'] for h in t['hits'][:4])), flush=True)
        write(path, dict(schema='R7_HORIZONTAL_SEARCH_V1', board=tag, tilt_searched=False,
                         yaw_only=True, bay=BAY, trials=trials))
        if t['clean']:
            accepted = t
            break
    out[tag] = dict(accepted=accepted, trials=len(trials))
    return accepted


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--survey-only', action='store_true')
    a = ap.parse_args()
    host = host_rows()['service']
    rows = survey(host)
    write(D / 'results/BAY_SURVEY.json', dict(schema='R7_BAY_SURVEY_V1', bay=BAY,
                                              objects=len(rows), rows=rows))
    print('bay objects:', len(rows), flush=True)
    for r in rows:
        print('   %-38s z %8.2f..%8.2f  x %8.1f..%8.1f  y %7.1f..%7.1f' % (
            r['id'][:38], r['lo'][2], r['hi'][2], r['lo'][0], r['hi'][0], r['lo'][1], r['hi'][1]), flush=True)
    if a.survey_only:
        raise SystemExit(0)

    # Regions the voxel capacity scan left with any usable slab height. Voxel
    # occupancy comes from bounding boxes, so a region it sizes slightly too small
    # can still pass the real boolean test; these sweeps check that, fail-closed.
    REGIONS = [
        ('above_battery_plusY', (30.5, 150.0), (31.5, 94.0), (69.0, 101.0)),
        ('above_P60_tray_plusY', (-158.0, -44.0), (74.0, 96.0), (56.0, 101.0)),
        ('above_P60_tray_midY', (-158.0, -44.0), (6.0, 43.0), (56.0, 101.0)),
    ]

    def grid_for(tag):
        cov = read(D / 'inputs' / ('%s_GEOMETRY_COVERAGE.json' % tag))
        local = source(cov['board'])
        pts, skipped = [], []
        for name, (x0, x1), (y0, y1), (z0, z1) in REGIONS:
            for deg in (0, 90):
                lo, hi = g.precise_bounds(moved(local, yaw(deg)))
                w, d, h = [hi[i] - lo[i] for i in range(3)]
                if x0 + w > x1 or y0 + d > y1 or z0 + h > z1:
                    skipped.append(dict(region=name, yaw_deg=deg,
                                        needs_mm=[w, d, h],
                                        region_mm=[x1 - x0, y1 - y0, z1 - z0]))
                    print('%-5s yaw %-3d %-22s SKIP needs %.1fx%.1fx%.1f in %.1fx%.1fx%.1f' % (
                        tag, deg, name, w, d, h, x1 - x0, y1 - y0, z1 - z0), flush=True)
                    continue
                for cx in np.arange(x0, x1 - w + 1e-6, 10.0):
                    for cy in np.arange(y0, y1 - d + 1e-6, 10.0):
                        for cz in np.arange(z0, z1 - h + 1e-6, 5.0):
                            t = corner_pose(local, deg, (cx, cy, cz))
                            pts.append((t[0], t[1], t[2], deg))
        return local, pts, skipped

    out = {}
    _, pts, skip_stop = grid_for('STOP')
    print('STOP candidate poses:', len(pts), flush=True)
    stop = search('STOP', pts, host, (), out, D / 'results/STOP_HORIZONTAL_SEARCH.json') if pts else None
    extra = []
    if stop:
        cov = read(D / 'inputs/STOP_GEOMETRY_COVERAGE.json')
        extra = [dict(cov['board'], id='R7_STOP_PCBA_INSTALLED', T_S_local=stop['T_S_board'])]
    _, pts, skip_aux = grid_for('AUX')
    print('AUX candidate poses:', len(pts), flush=True)
    aux = search('AUX', pts, host, extra, out, D / 'results/AUX_HORIZONTAL_SEARCH.json') if pts else None
    write(D / 'results/BOARD_POSE_SEARCH.json', dict(
        schema='R7_POSE_SEARCH_V1', boards=out, regions=[r[0] for r in REGIONS],
        skipped_region_orientations=dict(STOP=skip_stop, AUX=skip_aux),
        tilt_searched=False, yaw_only=True,
        STOP_pose_found=bool(stop), AUX_pose_found=bool(aux),
        both_installable=bool(stop and aux)))
