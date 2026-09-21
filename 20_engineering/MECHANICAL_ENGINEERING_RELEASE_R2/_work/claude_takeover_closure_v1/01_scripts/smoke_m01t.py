"""Smoke test for the m01t library core. Fail-closed assertions."""
import numpy as np

from m01t import assets, kinematics as K

# FK at q0: base_link identity; mount translation [208,0,0] mm
T0 = K.fk_mm([0.0] * 6)
assert np.allclose(T0["base_link"], np.eye(4))
print("mount t (mm):", K.MOUNT_MM[:3, 3].tolist())
assert abs(K.MOUNT_MM[0, 3] - 208.0) < 1e-9

# joint1 origin at z=84.65mm
assert abs(T0["link1"][2, 3] - 84.65) < 1e-9, T0["link1"]
# link2 origin: 84.65 + (0.020084,0.031625,0.05555)*1000 rotated by joint2 rpy
print("T link2 q0:\n", np.round(T0["link2"], 6))

# q0 host-follow equals MOUNT for every host (maps A0 coords into S)
for h in ("base_link", "link1", "link2", "link3", "link4", "link5", "link6"):
    M = K.host_follow_mm(h, [0.0] * 6)
    assert np.allclose(M, K.MOUNT_MM, atol=1e-9), h
print("host-follow q0 == MOUNT: PASS")

# J4 law sanity: dx(0)=0, beta(0)=seed+Q_MAX
assert K.J4.dx_mm(0.0) == 0.0
print("J4 F_A:", np.round(K.J4.F_A, 3), "U_R:", K.J4.U_RADIUS, "ANN_R:", K.J4.ANN_RADIUS)
print("J4 ANN_ALPHA_FIXED deg:", np.degrees(K.J4.ANN_ALPHA_FIXED), "BETA_Q0 deg:", np.degrees(K.J4.ANN_BETA_Q0))

# capsule + hull + box smoke
cap = assets.capsule_compound([0, 0, 0], [10, 0, 0], 2.0)
v = assets.validate_closed_solid_set(cap)
print("capsule:", v["solid_count"], "solids, vol", round(v["volume_mm3"], 1))
box = assets.box_from_bounds([20, 0, 0], [25, 5, 5])
d = assets.dist_shapes(cap, box)
print("capsule-box dist (expect 8.0):", None if d is None else round(d[0], 6))

# hull of a small L-shaped point set (concave) + containment
pts = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10], [10, 10, 0],
                [10, 0, 10], [0, 10, 10], [10, 10, 10], [5, 5, 5]], float)
solid, hull = assets.hull_solid(pts)
viol = assets.hull_contains(hull, pts)
print("hull solids:", assets.count_solids(solid), "containment viol:", viol)

# FCStd extraction (solar left leaf 1 stowed)
shape, pl = assets.extract_fcstd_brep(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.FCStd",
    "R2_LEFT_LEAF1_STOWED")
v = assets.validate_closed_solid_set(shape)
print("solar stowed leaf1:", v["solid_count"], "solids, bounds", np.round(v["bounds_lo"], 1), np.round(v["bounds_hi"], 1), "placement:", pl)
print("SMOKE PASS")
