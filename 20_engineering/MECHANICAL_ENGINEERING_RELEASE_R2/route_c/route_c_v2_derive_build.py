# Derive B601_ROUTE_C_BUILD_V2.py from B601_ROUTE_C_BUILD_V1.py (A1 frozen input,
# NOT modified).  Line-anchored replacements implementing the RC-4 V1->V2 design
# iteration (rationale in the RC-4 V2 gate declared_findings):
#   C1 bend radii: all dynamic loops >= 55 mm (J1 coil unchanged at 60), fillets 55
#   C2 routing plane YC 69.625 -> 81.625 (lifts link3 span/channel off the vendor
#      link3 housing facet that V1 grazed by 0.14-0.6 mm)
#   C3 J6 helix origin -20 mm in x (150,0,191.7): clears the deployed solar wing
#      outboard-bottom corner contact found on M01 (raw -4.45 mm)
#   C4 J6 guide rings: bore 52 -> 58, outer 58 -> 62 (clears STOW descent excursion)
#   C5 wrist descent: W1 exit stub 50 -> 70, A6 helix entry stub 65 -> 75,
#      W2 placed 105 mm along the descent direction (fillet legs)
#   C6 SEG-00 riser simplified to one straight diagonal HN02 -> KP (KP moved to
#      (14.56,-85,126) so the annulus tangent leg >= 56 mm for the R55 90 deg turn);
#      riser bracket and riser clamp follow the diagonal
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "B601_ROUTE_C_BUILD_V1.py")
DST = os.path.join(HERE, "B601_ROUTE_C_BUILD_V2.py")

lines = open(SRC, encoding="utf-8").read().split("\n")

EDITS = [
    (30,  '    "r_path_min": 50.0,', '    "r_path_min": 55.0,'),
    (289, 'YC = 69.625', 'YC = 81.625'),
    (297, 'JV = (14.56, -77.98, 50.0)', 'JV = (14.56, -77.98, 50.0)'),
    (298, 'KP = (14.56, -77.98, 126.0)', 'KP = (14.56, -100.0, 126.0)'),
    (299, '', 'RISER_DIR = v_norm(v_sub(KP, HN02))\nRISER_MID = v_add(HN02, v_mul(RISER_DIR, 75.9))'),
    (316, 'j2_t1_xz, j2_start_ang = tangent_point_from_external((J2_C[0], J2_C[2]), 50.0, (P_J1OUT[0], P_J1OUT[2]), -1)',
          'j2_t1_xz, j2_start_ang = tangent_point_from_external((J2_C[0], J2_C[2]), 55.0, (P_J1OUT[0], P_J1OUT[2]), -1)'),
    (317, 'T1_J2 = circle_point(J2_C, (1, 0, 0), (0, 0, 1), 50.0, j2_start_ang)',
          'T1_J2 = circle_point(J2_C, (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang)'),
    (320, 'j2_end = circle_point(J2_C, (1, 0, 0), (0, 0, 1), 50.0, j2_end_ang)',
          'j2_end = circle_point(J2_C, (1, 0, 0), (0, 0, 1), 55.0, j2_end_ang)'),
    (331, 'j3_end = circle_point(J3_C, (1, 0, 0), (0, 0, 1), 63.0, j3_end_ang)',
          'j3_end = circle_point(J3_C, (1, 0, 0), (0, 0, 1), 65.0, j3_end_ang)'),
    (335, 'T1_J4 = (5.0, YC, 185.0)', 'T1_J4 = (5.0, YC, 190.0)'),
    (342, 'j4_end = circle_point(J4_C, (1, 0, 0), (0, 0, 1), 50.0, j4_end_ang)',
          'j4_end = circle_point(J4_C, (1, 0, 0), (0, 0, 1), 55.0, j4_end_ang)'),
    (351, 'j5_t1_xy, j5_start_ang = tangent_point_from_external((J5_C[0], J5_C[1]), 50.0, (K2[0], K2[1]), -1)',
          'j5_t1_xy, j5_start_ang = tangent_point_from_external((J5_C[0], J5_C[1]), 55.0, (K2[0], K2[1]), -1)'),
    (355, 'j5_end = circle_point(J5_C, (1, 0, 0), (0, 1, 0), 50.0, j5_end_ang)',
          'j5_end = circle_point(J5_C, (1, 0, 0), (0, 1, 0), 55.0, j5_end_ang)'),
    (357, 'W1 = v_add(j5_end, v_mul(j5_exit_tan, 50.0))', 'W1 = v_add(j5_end, v_mul(j5_exit_tan, 70.0))'),
    (358, 'W2 = (93.11, 89.04, 227.3)', 'W2 = v_add(W1, v_mul(v_norm(v_sub((73.11, 89.04, 227.3), W1)), 130.0))'),
    (361, 'J6_ORIGIN = (170.0, 0.0, 191.7)', 'J6_ORIGIN = (150.0, 0.0, 191.7)'),
    (366, 'H0 = circle_point(J6_ORIGIN, (0, 1, 0), (0, 0, 1), 50.0, j6_start_ang)',
          'H0 = circle_point(J6_ORIGIN, (0, 1, 0), (0, 0, 1), 55.0, j6_start_ang)'),
    (367, 'j6_entry_tan = helix_tangent((1, 0, 0), (0, 1, 0), (0, 0, 1), 50.0, j6_pitch, j6_start_ang, +1)',
          'j6_entry_tan = helix_tangent((1, 0, 0), (0, 1, 0), (0, 0, 1), 55.0, j6_pitch, j6_start_ang, +1)'),
    (368, 'A6 = v_sub(H0, v_mul(j6_entry_tan, 65.0))', 'A6 = v_sub(H0, v_mul(j6_entry_tan, 110.0))'),
    (369, 'j6_end = circle_point(J6_ORIGIN, (0, 1, 0), (0, 0, 1), 50.0, j6_end_ang)',
          'j6_end = circle_point(J6_ORIGIN, (0, 1, 0), (0, 0, 1), 55.0, j6_end_ang)'),
    (371, 'j6_exit_tan = helix_tangent((1, 0, 0), (0, 1, 0), (0, 0, 1), 50.0, j6_pitch, j6_end_ang, +1)',
          'j6_exit_tan = helix_tangent((1, 0, 0), (0, 1, 0), (0, 0, 1), 55.0, j6_pitch, j6_end_ang, +1)'),
    (381, '        "sections": [("poly", [HN00, HN01, HN02, C1, C2, C2B, JV, KP, T1_COIL],',
          '        "sections": [("poly", [HN00, HN01, HN02, KP, T1_COIL],'),
    (382, '                      [0.0, 0.0, 50.0, 50.0, 50.0, 50.0, 50.0])],',
          '                      [0.0, 55.0, 54.0])],'),
    (392, '            ("poly", [j1_end, P_J1OUT, T1_J2], [50.0]),',
          '            ("poly", [j1_end, P_J1OUT, T1_J2], [55.0]),'),
    (402, '            ("arc", (J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 50.0, j2_start_ang, j2_sweep)),',
          '            ("arc", (J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang, j2_sweep)),'),
    (403, '            ("poly", [j2_end, M2, (-208.0, YC, 145.0), (-255.0, YC, 145.0)], [50.0, 0.0, 0.0]),',
          '            ("poly", [j2_end, M2, (-208.0, YC, 147.0), (-255.0, YC, 147.0)], [55.0, 0.0, 0.0]),'),
    (405, '        "take_up_required_mm": 50.0*3.14,', '        "take_up_required_mm": 55.0*3.14,'),
    (406, '        "take_up_capacity_mm": 50.0*math.radians(abs(j2_sweep)),',
          '        "take_up_capacity_mm": 55.0*math.radians(abs(j2_sweep)),'),
    (413, '            ("arc", (J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 63.0, j3_start_ang, j3_sweep)),',
          '            ("arc", (J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 65.0, j3_start_ang, j3_sweep)),'),
    (414, '            ("poly", [j3_end, M3, F4, T1_J4], [50.0, 50.0, 0.0]),',
          '            ("poly", [j3_end, M3, F4, T1_J4], [55.0, 55.0, 0.0]),'),
    (416, '        "take_up_required_mm": 63.0*3.14,', '        "take_up_required_mm": 65.0*3.14,'),
    (424, '            ("arc", (J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 50.0, j4_start_ang, j4_sweep)),',
          '            ("arc", (J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j4_start_ang, j4_sweep)),'),
    (425, '            ("poly", [j4_end, M4, K2, T1_J5], [50.0, 50.0, 50.0]),',
          '            ("poly", [j4_end, M4, K2, T1_J5], [55.0, 55.0, 55.0]),'),
    (427, '        "take_up_required_mm": 50.0*3.44,', '        "take_up_required_mm": 55.0*3.44,'),
    (428, '        "take_up_capacity_mm": 50.0*math.radians(abs(j4_sweep)),',
          '        "take_up_capacity_mm": 55.0*math.radians(abs(j4_sweep)),'),
    (435, '            ("arc", (J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 50.0, j5_start_ang, j5_sweep)),',
          '            ("arc", (J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 55.0, j5_start_ang, j5_sweep)),'),
    (436, '            ("poly", [j5_end, W1, W2, A6, H0], [50.0, 50.0, 50.0]),',
          '            ("poly", [j5_end, W1, W2, A6, H0], [55.0, 55.0, 55.0]),'),
    (438, '        "take_up_required_mm": 50.0*3.14,', '        "take_up_required_mm": 55.0*3.14,'),
    (439, '        "take_up_capacity_mm": 50.0*math.radians(abs(j5_sweep)),',
          '        "take_up_capacity_mm": 55.0*math.radians(abs(j5_sweep)),'),
    (446, '            ("helix", (J6_ORIGIN, (1, 0, 0), (0, 1, 0), (0, 0, 1), 50.0, j6_pitch, j6_start_ang, j6_sweep)),',
          '            ("helix", (J6_ORIGIN, (1, 0, 0), (0, 1, 0), (0, 0, 1), 55.0, j6_pitch, j6_start_ang, j6_sweep)),'),
    (447, '            ("poly", [j6_end, STUB_END, PLATE], [50.0]),',
          '            ("poly", [j6_end, STUB_END, PLATE], [55.0]),'),
    (449, '        "take_up_required_mm": 50.0*6.28,', '        "take_up_required_mm": 55.0*6.28,'),
    (450, '        "take_up_capacity_mm": 50.0*math.radians(abs(j6_sweep))*1.002,',
          '        "take_up_capacity_mm": 55.0*math.radians(abs(j6_sweep))*1.002,'),
    (604, 'clamp_saddle("RC-CLP-BUS-RISER", C2, v_norm(v_sub(C2B, C2)), "aluminum", "base_link",',
          'clamp_saddle("RC-CLP-BUS-RISER", RISER_MID, RISER_DIR, "aluminum", "base_link",'),
    (606, 'oriented_box("RC-BRK-J1-RISER", (14.56, -77.98, 88.0), (8.0, 12.0, 76.0), (0, 0, 1), (0, 1, 0),',
          'oriented_box("RC-BRK-J1-RISER", RISER_MID, (8.0, 12.0, 140.0), RISER_DIR, (0, 1, 0),'),
    (629, 'guide_tube("RC-GDE-J2-MANDREL", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 50.0, j2_start_ang, j2_sweep, 6.0,',
          'guide_tube("RC-GDE-J2-MANDREL", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang, j2_sweep, 6.0,'),
    (631, 'guide_tube("RC-GDE-J2-MANDREL-LINER", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 50.0, j2_start_ang, j2_sweep, 7.5,',
          'guide_tube("RC-GDE-J2-MANDREL-LINER", J2_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j2_start_ang, j2_sweep, 7.5,'),
    (638, 'channel_section("RC-CHN-L2", M2, (-208.0, YC, 145.0), 12.0, 12.0, "aluminum", "link2",',
          'channel_section("RC-CHN-L2", M2, (-208.0, YC, 147.0), 12.0, 12.0, "aluminum", "link2",'),
    (640, 'clamp_saddle("RC-CLP-L2-01", (-80.0, YC, 145.0), (-1, 0, 0), "aluminum", "link2", "CF-L2-01 fixed clamp")',
          'clamp_saddle("RC-CLP-L2-01", (-80.0, YC, 147.0), (-1, 0, 0), "aluminum", "link2", "CF-L2-01 fixed clamp")'),
    (641, 'clamp_saddle("RC-CLP-L2-02", (-208.0, YC, 145.0), (-1, 0, 0), "aluminum", "link2", "CF-L2-02 fixed clamp at channel end")',
          'clamp_saddle("RC-CLP-L2-02", (-208.0, YC, 147.0), (-1, 0, 0), "aluminum", "link2", "CF-L2-02 fixed clamp at channel end")'),
    (646, 'oriented_box("RC-CAR-J3-CARRIAGE", (-140.0, YC, 145.0), (36.0, 24.0, 22.0), (1, 0, 0), (0, 1, 0), "aluminum", "link2",',
          'oriented_box("RC-CAR-J3-CARRIAGE", (-140.0, YC, 147.0), (36.0, 24.0, 22.0), (1, 0, 0), (0, 1, 0), "aluminum", "link2",'),
    (648, 'clamp_saddle("RC-CLP-J3-MOV", (-140.0, YC, 145.0), (-1, 0, 0), "polymer", "link2", "CM-J3-M moving clamp on carriage")',
          'clamp_saddle("RC-CLP-J3-MOV", (-140.0, YC, 147.0), (-1, 0, 0), "polymer", "link2", "CM-J3-M moving clamp on carriage")'),
    (650, '    box_at("RC-CHN-E210-LINK-%02d" % i, (-95.0 - i*20.0, YC, 145.0), (18.0, 16.0, 10.0), "polymer", "link2",',
          '    box_at("RC-CHN-E210-LINK-%02d" % i, (-95.0 - i*20.0, YC, 147.0), (18.0, 16.0, 10.0), "polymer", "link2",'),
    (654, 'guide_tube("RC-GDE-J3-SADDLE", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 63.0, j3_start_ang, j3_sweep, 7.0,',
          'guide_tube("RC-GDE-J3-SADDLE", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 65.0, j3_start_ang, j3_sweep, 7.0,'),
    (656, 'guide_tube("RC-GDE-J3-SADDLE-LINER", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 63.0, j3_start_ang, j3_sweep, 8.6,',
          'guide_tube("RC-GDE-J3-SADDLE-LINER", J3_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 65.0, j3_start_ang, j3_sweep, 8.6,'),
    (669, 'guide_tube("RC-GDE-J4-MANDREL", J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 50.0, j4_start_ang, j4_sweep, 6.0,',
          'guide_tube("RC-GDE-J4-MANDREL", J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j4_start_ang, j4_sweep, 6.0,'),
    (671, 'guide_tube("RC-GDE-J4-MANDREL-LINER", J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 50.0, j4_start_ang, j4_sweep, 7.5,',
          'guide_tube("RC-GDE-J4-MANDREL-LINER", J4_C, (0, 1, 0), (1, 0, 0), (0, 0, 1), 55.0, j4_start_ang, j4_sweep, 7.5,'),
    (682, 'guide_tube("RC-GDE-J5-WRAP", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 50.0, j5_start_ang, j5_sweep, 6.0,',
          'guide_tube("RC-GDE-J5-WRAP", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 55.0, j5_start_ang, j5_sweep, 6.0,'),
    (684, 'guide_tube("RC-GDE-J5-WRAP-LINER", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 50.0, j5_start_ang, j5_sweep, 7.5,',
          'guide_tube("RC-GDE-J5-WRAP-LINER", J5_C, (0, 0, 1), (1, 0, 0), (0, 1, 0), 55.0, j5_start_ang, j5_sweep, 7.5,'),
    (692, '    ring("RC-GDE-J6-RING-%d" % idx, c, (1, 0, 0), 58.0, 52.0, 4.0, "polymer", "link6",',
          '    ring("RC-GDE-J6-RING-%d" % idx, c, (1, 0, 0), 62.0, 58.0, 4.0, "polymer", "link6",'),
    (694, 'box_at("RC-BRK-J6-GUIDE-A", (180.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm A")',
          'box_at("RC-BRK-J6-GUIDE-A", (160.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm A")'),
    (695, 'box_at("RC-BRK-J6-GUIDE-B", (200.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm B")',
          'box_at("RC-BRK-J6-GUIDE-B", (180.0, 0.0, 250.0), (8.0, 30.0, 6.0), "aluminum", "link6", "J6 guide ring support arm B")'),
    (740, '    ("CF-BUS-03", "base_link", C2, "FIXED", "2xM3 on bracket arm",',
          '    ("CF-BUS-03", "base_link", RISER_MID, "FIXED", "2xM3 on bracket arm",'),
    (747, '    ("CF-L2-01", "link2", (-80.0, YC, 145.0), "FIXED", "2xM3 on RC-CHN-L2", "link2 channel fixed clamp"),',
          '    ("CF-L2-01", "link2", (-80.0, YC, 147.0), "FIXED", "2xM3 on RC-CHN-L2", "link2 channel fixed clamp"),'),
    (748, '    ("CM-J3-M", "link2", (-140.0, YC, 145.0), "MOVING_CARRIER", "carriage RC-CAR-J3-CARRIAGE",',
          '    ("CM-J3-M", "link2", (-140.0, YC, 147.0), "MOVING_CARRIER", "carriage RC-CAR-J3-CARRIAGE",'),
    (750, '    ("CF-L2-02", "link2", (-208.0, YC, 145.0), "FIXED", "2xM3 on RC-CHN-L2", "link2 channel end clamp"),',
          '    ("CF-L2-02", "link2", (-208.0, YC, 147.0), "FIXED", "2xM3 on RC-CHN-L2", "link2 channel end clamp"),'),
    (751, '    ("CG-J3-S", "link2", (-255.0, YC, 145.0), "GUIDE_SADDLE", "4xM3 saddle bracket", "J3 guide saddle entry tangent"),',
          '    ("CG-J3-S", "link2", (-255.0, YC, 147.0), "GUIDE_SADDLE", "4xM3 saddle bracket", "J3 guide saddle entry tangent"),'),
]

lines[0] = lines[0].replace(
    "# B601 Route-C Guided Dress Pack V1 - headless FreeCAD build script (structured-section builder)",
    "# B601 Route-C Guided Dress Pack V2 - headless FreeCAD build script (derived from V1 by route_c_v2_derive_build.py)")
lines[2] = lines[2].replace(
    "# Stage RC-3 of R2 terminal dual-lane closure, lane A1 (Route-C task-level guided harness).",
    "# Stage RC-4/V2 of R2 terminal dual-lane closure, lane A2 (Route-C exact-verification iteration).")

for ln, old, new in EDITS:
    assert lines[ln - 1] == old, "line %d mismatch:\n  got: %r\n  exp: %r" % (ln, lines[ln - 1], old)
    lines[ln - 1] = new

text = "\n".join(lines)
for a, b in [
    ('OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V1.FCStd")',
     'OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V2.FCStd")'),
    ('OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V1.step")',
     'OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V2.step")'),
    ('OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V1.json")',
     'OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V2.json")'),
    ('OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V1.csv")',
     'OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V2.csv")'),
    ('OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V1.json")',
     'OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V2.json")'),
    ('OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V1.json")',
     'OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V2.json")'),
    ('App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V1")',
     'App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V2")'),
    ('"schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V1"', '"schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V2"'),
    ('"schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V1"',
     '"schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V2"'),
    ('"schema": "B601_ROUTE_C_BUILD_RECEIPT_V1"', '"schema": "B601_ROUTE_C_BUILD_RECEIPT_V2"'),
    ('"generated_utc": "2026-08-25T10:02:34Z"', '"generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK"'),
]:
    assert a in text, "missing: %s" % a
    text = text.replace(a, b)

open(DST, "w", encoding="utf-8", newline="\n").write(text)
print("V2 build script written:", DST)
