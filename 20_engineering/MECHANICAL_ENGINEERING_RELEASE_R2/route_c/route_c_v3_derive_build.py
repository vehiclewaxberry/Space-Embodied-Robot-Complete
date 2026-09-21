# Derive B601_ROUTE_C_BUILD_V3.py from B601_ROUTE_C_BUILD_V2.py.
# Targeted geometry relocation per RC-4 fixed-code root-cause table:
#   R1 J6 guide rings: closed annulus -> open-sector annulus (240 deg kept,
#      120 deg opening centered at azimuth 165 deg in the ring y-z plane, i.e.
#      the STOW descent-approach side).  Root cause: SEG-05 descent clipped the
#      closed ring material at STOW (-4.7 mm).  Inner radius 58 -> 60, outer
#      62 -> 66 so the R55 helix tube (59.5 mm extent) seats in the bore.
#   R2 link4 riser top waypoint K2 moved A0 (0,-30,+50): root cause: the riser
#      tip sat inside the gripper palm back plate at every mission pose
#      (-11.0 mm).  Probe-verified clearance +24.7 mm after the move.
#   R3 SEG-00 corner-3 requested radius 54.0 (fits without clamping; the single
#      build-self-check violation of V2 is resolved).
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "B601_ROUTE_C_BUILD_V2.py")
DST = os.path.join(HERE, "B601_ROUTE_C_BUILD_V3.py")

text = open(SRC, encoding="utf-8").read()

REPL = [
    # --- R3: r_path_min 55 -> 54 (SEG-00 corner 3 is the global minimum) -------
    ('    "r_path_min": 55.0,', '    "r_path_min": 54.0,'),
    # --- R2: K2 waypoint -------------------------------------------------------
    ('K2 = (115.0, YC, 210.0)', 'K2 = (115.0, YC - 30.0, 260.0)'),
    # --- R1: open-sector J6 rings ----------------------------------------------
    ('''for idx, ang in enumerate([180.0, 360.0, 540.0, 720.0]):
    along = j6_pitch * math.radians(ang - j6_start_ang) / (2.0*math.pi)
    c = (J6_ORIGIN[0] + along, J6_ORIGIN[1], J6_ORIGIN[2])
    ring("RC-GDE-J6-RING-%d" % idx, c, (1, 0, 0), 62.0, 58.0, 4.0, "polymer", "link6",
         "J6 helix guide ring %d at wrap angle %.0f deg" % (idx, ang))''',
     '''for idx, ang in enumerate([180.0, 360.0, 540.0, 720.0]):
    along = j6_pitch * math.radians(ang - j6_start_ang) / (2.0*math.pi)
    c = (J6_ORIGIN[0] + along, J6_ORIGIN[1], J6_ORIGIN[2])
    robj = ring("RC-GDE-J6-RING-%d" % idx, c, (1, 0, 0), 66.0, 60.0, 4.0, "polymer", "link6",
                "J6 helix guide ring %d (open-sector, opening az 105-225 deg) at wrap angle %.0f deg" % (idx, ang))
    if robj is not None:
        a1_, a2_ = math.radians(105.0), math.radians(225.0)
        w0 = App.Vector(c[0] - 7.0, 0.0, c[2])
        w1 = App.Vector(c[0] - 7.0, 100.0 * math.cos(a1_), c[2] + 100.0 * math.sin(a1_))
        w2 = App.Vector(c[0] - 7.0, 100.0 * math.cos(a2_), c[2] + 100.0 * math.sin(a2_))
        wedge = Part.Face(Part.makePolygon([w0, w1, w2, w0])).extrude(App.Vector(14.0, 0.0, 0.0))
        robj.Shape = robj.Shape.cut(wedge)'''),
]

for a, b in REPL:
    assert a in text, "missing: %s" % a[:60]
    text = text.replace(a, b)

for a, b in [
    ('OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V2.FCStd")',
     'OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V3.FCStd")'),
    ('OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V2.step")',
     'OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V3.step")'),
    ('OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V2.json")',
     'OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V3.json")'),
    ('OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V2.csv")',
     'OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V3.csv")'),
    ('OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V2.json")',
     'OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V3.json")'),
    ('OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V2.json")',
     'OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V3.json")'),
    ('App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V2")',
     'App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V3")'),
    ('"schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V2"', '"schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V3"'),
    ('"schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V2"',
     '"schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V3"'),
    ('"schema": "B601_ROUTE_C_BUILD_RECEIPT_V2"', '"schema": "B601_ROUTE_C_BUILD_RECEIPT_V3"'),
]:
    assert a in text, "missing: %s" % a
    text = text.replace(a, b)

open(DST, "w", encoding="utf-8", newline="\n").write(text)
print("V3 build script written:", DST)
