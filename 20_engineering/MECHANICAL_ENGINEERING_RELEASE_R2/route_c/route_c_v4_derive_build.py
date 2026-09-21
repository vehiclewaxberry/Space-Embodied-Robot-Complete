# Derive B601_ROUTE_C_BUILD_V4.py from B601_ROUTE_C_BUILD_V3.py.
# Wrist relocation per RC-4 fixed-code probe (mission-pose clearance vs the
# gripper assembly, HOME pose):
#   W1 J5 wrap center (76.908,0,210) -> (50,-40,210): off-axis omega; probe
#      clearance vs gripper +17.7 mm (was -10.4 mm inside the palm back plate)
#   W2 J6 helix origin x 150 -> 105 (slides along the J6 axis, axisymmetry kept):
#      probe clearance vs gripper root +11 mm (was -8.1 mm inside gripper body)
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "B601_ROUTE_C_BUILD_V3.py")
DST = os.path.join(HERE, "B601_ROUTE_C_BUILD_V4.py")

text = open(SRC, encoding="utf-8").read()

for a, b in [
    ('J5_C = (76.908, 0.0, 210.0)', 'J5_C = (50.0, -40.0, 210.0)'),
    ('J6_ORIGIN = (150.0, 0.0, 191.7)', 'J6_ORIGIN = (105.0, 0.0, 191.7)'),
]:
    assert a in text, "missing: %s" % a
    text = text.replace(a, b)

for a, b in [
    ('OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V3.FCStd")',
     'OUT_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V4.FCStd")'),
    ('OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V3.step")',
     'OUT_STEP = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_V4.step")'),
    ('OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V3.json")',
     'OUT_CENTERLINE = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_HARNESS_CENTERLINE_V4.json")'),
    ('OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V3.csv")',
     'OUT_CLAMPS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_CLAMP_AND_GUIDE_REGISTER_V4.csv")'),
    ('OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V3.json")',
     'OUT_MASS = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V4.json")'),
    ('OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V3.json")',
     'OUT_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_V4.json")'),
    ('App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V3")',
     'App.newDocument("B601_ROUTE_C_GUIDED_DRESS_PACK_V4")'),
    ('"schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V3"', '"schema": "B601_ROUTE_C_HARNESS_CENTERLINE_V4"'),
    ('"schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V3"',
     '"schema": "B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V4"'),
    ('"schema": "B601_ROUTE_C_BUILD_RECEIPT_V3"', '"schema": "B601_ROUTE_C_BUILD_RECEIPT_V4"'),
]:
    assert a in text, "missing: %s" % a
    text = text.replace(a, b)

open(DST, "w", encoding="utf-8", newline="\n").write(text)
print("V4 build script written:", DST)
