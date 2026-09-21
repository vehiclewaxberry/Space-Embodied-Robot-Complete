# V1 failure root-cause probe (diagnostic, not a gate artifact)
import importlib.util, json, math, os
import numpy as np
import yaml

spec = importlib.util.spec_from_file_location(
    'sw', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ROUTE_C_EXACT_SWEEP_V1.py'))
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)
HERE = os.path.dirname(os.path.abspath(__file__))

mount_yaml = yaml.safe_load(open(sw.P_MOUNT, encoding='utf-8'))
arm = sw.ArmModel(sw.P_URDF, mount_yaml['mount']['transform_mm_rows'])
T0 = arm.fk([0.0] * 6)
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}
center = json.load(open(os.path.join(HERE, 'B601_ROUTE_C_HARNESS_CENTERLINE_V1.json')))
HOSTS = sw.HOSTS
host_plan = {
    ('SEG-00_BUS_FEEDTHROUGH_AND_RISER', 0): ('base_link', None),
    ('SEG-01_J1_ANNULAR_SERVICE_LOOP', 0): ('base_link', None),
    ('SEG-01_J1_ANNULAR_SERVICE_LOOP', 1): ('link1', None),
    ('SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL', 0): ('link1', 'link2'),
    ('SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL', 1): ('link2', 'link1'),
    ('SEG-03_J3_CARRIER_HYBRID_WRAP', 0): ('link2', 'link3'),
    ('SEG-03_J3_CARRIER_HYBRID_WRAP', 1): ('link3', 'link2'),
    ('SEG-04_J4_LOOP_LINK4_CHANNEL_RISER', 0): ('link3', 'link4'),
    ('SEG-04_J4_LOOP_LINK4_CHANNEL_RISER', 1): ('link4', 'link3'),
    ('SEG-05_J5_WRIST_WRAP', 0): ('link4', 'link5'),
    ('SEG-05_J5_WRIST_WRAP', 1): ('link5', 'link4'),
    ('SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN', 0): ('link5', None),
    ('SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN', 1): ('link6', None),
    ('SEG-07A_WRIST_TAIL_DATA', 0): ('link6', None),
    ('SEG-07B_WRIST_TAIL_POWER', 0): ('link6', None)}
seg_pts = {}   # seg_id -> list of (pts, host, alt)
for seg in center['segments']:
    arr = []
    for ci, sec in enumerate(seg['sections']):
        pts, L, r = sw.build_section(sec)
        h, a = host_plan[(seg['id'], ci)]
        arr.append((pts, h, a))
    seg_pts[seg['id']] = arr

manifest = json.load(open(os.path.join(HERE, 'ROUTE_C_SWEEP_MESH_PACK_V1', 'MANIFEST.json')))
def loadt(f):
    return np.load(os.path.join(HERE, 'ROUTE_C_SWEEP_MESH_PACK_V1', f), allow_pickle=False)
vf = {}
solar = None
for grp in manifest['files']:
    if grp['group'] == 'arm_vendor':
        for e in grp['entries']:
            vf[e['link']] = sw.TriField(e['link'], loadt(e['file']))
    if grp['group'] == 'solar':
        solar = sw.TriField('SOLAR', loadt(grp['entries'][0]['file']))
rc = {}
for grp in manifest['files']:
    if grp['group'] == 'route_c_parts':
        for e in grp['entries']:
            if e.get('valid') and e.get('kind') != 'bundle_envelope':
                rc[e['name']] = (e['host_link'], sw.TriField(e['name'], loadt(e['file'])))

STOW = [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236]
RC = [-1.570796, -2.094395, -2.094395, -1.047198, -0.523599, 0.0]
HOME = [-1.570796, -2.094395, -1.047198, 0.0, -0.523599, 0.0]
TASK = [-1.570796, -1.047198, -2.094395, -0.523599, 0.0, 0.0]
PRE = [-1.47e-05, -1.0482, -1.39898, -1.22001, 3.67e-06, 1.84e-05]

def pose(P, host, T):
    return sw.xform_batch(arm.mount @ T[host] @ inv_T0[host], P)

def q_interp(a, b, t):
    return [x + (y - x) * t for x, y in zip(a, b)]

print('=== (1) SEG-06 helix vs SOLAR along M01 (STOW->RELEASE_CLEAR) ===')
hel = [p for p in seg_pts['SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN']]
worst = (1e9, None)
for k in range(41):
    q = q_interp(STOW, RC, k / 40.0)
    T = arm.fk(q)
    for pts, h, a in hel:
        for host in {h} | ({a} if a else set()):
            if host is None:
                continue
            P = pose(pts, host, T)
            c = solar.signed_clearance_batch(P, 4.5)
            ok = ~np.isnan(c)
            if ok.any() and c[ok].min() < worst[0]:
                i = int(np.flatnonzero(ok)[int(np.argmin(c[ok]))])
                worst = (float(c[ok].min()), k, q[0], host, P[i])
print('  worst %.3f at k=%s q1=%.3f host=%s pt_S=%s' % worst)
# map: which solar leaf region? print solar tris bbox near the point
if worst[1] is not None:
    pS = worst[4]
    d = np.sqrt(((solar.v0 - pS) ** 2).sum(1))
    i = int(np.argmin(d))
    print('  nearest solar tri centroid %s (dist %.2f)' % (np.round(solar.v0[i], 1), d[i]))

print()
print('=== (2) SEG-03 span vs vendor link3 across mission q3 range ===')
seg3 = seg_pts['SEG-03_J3_CARRIER_HYBRID_WRAP']
fld3 = vf['link3']
for q3v in np.linspace(-2.0944, -0.9948, 12):
    q = list(HOME)
    q[2] = float(q3v)
    T = arm.fk(q)
    inv3 = np.linalg.inv(arm.mount @ T['link3'])
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        vals = []
        for pts, h, a in seg3:
            n = len(pts)
            s = int(round(frac * (n - 1)))
            part1 = pts[:s + 1]      # link2 side
            part2 = pts[s:]          # link3 side
            if len(part1):
                P1 = pose(part1, 'link2', T)
                c = fld3.signed_clearance_batch(sw.xform_batch(inv3, P1), 4.5)
                ok = ~np.isnan(c)
                if ok.any():
                    vals.append(float(c[ok].min()))
            if len(part2):
                P2 = pose(part2, 'link3', T)
                c = fld3.signed_clearance_batch(sw.xform_batch(inv3, P2), 4.5)
                ok = ~np.isnan(c)
                if ok.any():
                    vals.append(float(c[ok].min()))
        v = min(vals) if vals else float('nan')
        print('  q3=%+.4f frac=%.2f min=%8.3f' % (q3v, frac, v))

print()
print('=== (3) STOW: SEG-05 poly vs RC-GDE-J6-RING-0 ===')
ring_host, ring_fld = rc['RC-GDE-J6-RING-0']
print('  ring host:', ring_host)
T = arm.fk(STOW)
invR = np.linalg.inv(arm.mount @ T[ring_host] @ inv_T0[ring_host])
for pts, h, a in seg_pts['SEG-05_J5_WRIST_WRAP']:
    for host in {h} | ({a} if a else set()):
        if host is None:
            continue
        P = pose(pts, host, T)
        Pl = sw.xform_batch(invR, P)
        c = ring_fld.signed_clearance_batch(Pl, 4.5)
        ok = ~np.isnan(c)
        if ok.any():
            i = int(np.flatnonzero(ok)[int(np.argmin(c[ok]))])
            print('  host=%s min=%.3f at ptA0=%s ringLocal=%s'
                  % (host, float(c[ok].min()), np.round(pts[i], 1), np.round(Pl[i], 1)))
# ring bounds in its local frame
print('  ring local bbox:', np.round(ring_fld.bmin, 1), np.round(ring_fld.bmax, 1))

print()
print('=== (4) J1 annulus vs vendor link3/link4 along q1-crossing segments ===')
seg1 = seg_pts['SEG-01_J1_ANNULAR_SERVICE_LOOP']
for segname, qa, qb in [('M04', TASK, PRE), ('M07', PRE, HOME)]:
    for k in range(21):
        q = q_interp(qa, qb, k / 20.0)
        T = arm.fk(q)
        for lname in ('link3', 'link4'):
            fld = vf[lname]
            invL = np.linalg.inv(arm.mount @ T[lname])
            for pts, h, a in seg1:
                P = pose(pts, h, T)
                Pl = sw.xform_batch(invL, P)
                c = fld.signed_clearance_batch(Pl, 4.5)
                ok = ~np.isnan(c)
                if ok.any() and c[ok].min() < 3.0:
                    print('  %s k=%d %s min=%.3f' % (segname, k, lname, float(c[ok].min())))
print('  (only lines with min < 3.0 mm printed)')
