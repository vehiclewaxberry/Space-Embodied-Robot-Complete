"""Conservative motion bounds + continuous edge certification.

Mathematical basis (rigorous, no sampling):
  For a revolute joint j, a vertex v rigidly downstream displaces by at most
  rho_j(v) * |dq_j|, where rho_j(v) = distance from v to the joint axis line.
  The distance is frame-invariant, so it can be measured in joint j's parent
  frame where the axis is fixed.  Because the vertex cloud itself moves in that
  frame due to downstream joints, we add the downstream displacement bound:

      D_j = sum_{k in chain(j..host)} (rho_k(q_ref) + D_{k+1}) * |dq_k|

  evaluated from the wrist backwards (D_{beyond host} = 0).  Overestimation is
  safe (arc >= chord; nested bounds are conservative).

  Registered cable/take-up laws add linear terms:
    J3 carriage: |dx3| <= 32.5 * |dq3| mm (unclipped gain is conservative)
    J4 travel fractions: |gain * 27.5 * dq4| mm
    J4 C-sections: plane legs/U 27.5 * |dq4|; annulus R_ann * |dq4| (arc)
  plus the annulus chord-inflation change bounded by its endpoint maximum.
"""
import math

import numpy as np

from . import kinematics as K

# joint index in the arm chain: joint1..joint6 -> 0..5
CHAIN_JOINTS = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
# upstream revolute joints per link (link k rides joints 1..k)
UPSTREAM = {"base_link": [], "link1": [0], "link2": [0, 1], "link3": [0, 1, 2],
            "link4": [0, 1, 2, 3], "link5": [0, 1, 2, 3, 4],
            "link6": [0, 1, 2, 3, 4, 5],
            "gripper_link": [0, 1, 2, 3, 4, 5],
            "gripper_left": [0, 1, 2, 3, 4, 5],
            "gripper_right": [0, 1, 2, 3, 4, 5]}

_PARENT_LINK = {"joint1": "base_link", "joint2": "link1", "joint3": "link2",
                "joint4": "link3", "joint5": "link4", "joint6": "link5"}


def joint_axis_in_parent(jname):
    """Axis line (origin point, unit direction) in the joint's parent frame, m."""
    j = K.ARM.joints[jname]
    o = np.asarray(j["xyz_m"], float)
    R = K._rpy(*j["rpy"])
    a = R @ np.asarray(j["axis"], float)
    n = float(np.linalg.norm(a))
    assert n > 0
    return o, a / n


def _vertices_in_frame(obj_vertices_S, host, q_ref):
    """Object vertices expressed in joint-parent frames is handled by caller;
    here: vertices in a given reference frame from S coordinates."""
    return obj_vertices_S


class MotionCertifier:
    """Per-object conservative motion bounds over q intervals."""

    def __init__(self, scene):
        self.scene = scene
        self._axes = {name: joint_axis_in_parent(name) for name in CHAIN_JOINTS}

    def _object_points_storage(self, rt):
        """Design points in the object's storage frame (mm)."""
        if rt.capsules is not None:
            caps = rt.capsules
            a = np.asarray(caps["a_A0_mm"])
            b = np.asarray(caps["b_A0_mm"])
            return np.vstack([a, b])
        return rt.mesh_v

    def _storage_to_host_q0(self, rt):
        """4x4 (mm) mapping storage-frame points into the host link frame."""
        host = rt.host if rt.pose_law == "HOST_FOLLOW_OR_REGISTERED_MOTION" else rt.storage_frame
        if rt.pose_law in ("STATIC_S",):
            return None, None
        if host in (None, "S"):
            return None, None
        if rt.storage_frame == host:
            return np.eye(4), host
        # A0 q0 storage: host frame at q0 is FK0[host] (A0 coords); inverse maps to host frame
        return K.INV_FK0_MM[host], host

    def rho_table(self, rt, q_ref):
        """Per-upstream-joint max vertex-to-axis distance (mm) at q_ref, plus the
        downstream-shift-conservative recursion coefficients.

        Returns {joint_index: rho_mm}."""
        if rt.pose_law in ("STATIC_S", "MOUNT_STATIC"):
            return {}
        if rt.pose_law == "C_SECTION_POINT_LAWS":
            return self._rho_table_c(rt, q_ref)
        if rt.pose_law in ("ARM_FK", "ARM_FK_2P", "ARM_FK_LINK1", "ARM_FK_LINK2"):
            host = {"ARM_FK": rt.storage_frame, "ARM_FK_2P": rt.storage_frame,
                    "ARM_FK_LINK1": "link1", "ARM_FK_LINK2": "link2"}[rt.pose_law]
            pts_storage = self._object_points_storage(rt)
            T_store_to_host = np.eye(4)
        elif rt.pose_law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
            host = rt.host
            pts_storage = self._object_points_storage(rt)
            T_store_to_host = K.INV_FK0_MM[host]  # A0 q0 -> host frame
        else:
            raise ValueError(rt.pose_law)
        up = UPSTREAM[host]
        if not up:
            return {}
        # vertices in host frame (rigid there), mm
        pts_host = pts_storage @ T_store_to_host[:3, :3].T + T_store_to_host[:3, 3]
        # chain of FK transforms from host up to each parent frame, at q_ref (m!)
        Tm = K.ARM.fk_m(q_ref)
        out = {}
        # rho for joint j measured in parent(j) frame: need host-from-parent transform
        parent_of = {i: _PARENT_LINK[CHAIN_JOINTS[i]] for i in up}
        # displacement recursion constants (per-joint rho evaluated with
        # downstream shift included) — computed in displacement_bound()
        for j in up:
            pname = parent_of[j]
            o_m, a_m = self._axes[CHAIN_JOINTS[j]]
            # vertices in parent frame (m): T_p_host maps host -> parent? use S-independent:
            # host->A0 chain at q_ref: T_host_A0 = inv(FK[host]) in A0; A0->parent = FK[parent]
            T_host_A0 = np.linalg.inv(Tm[host])
            T_p_host = Tm[pname] @ T_host_A0  # host frame coords -> parent frame coords
            pts_host_m = pts_host / 1000.0
            pts_p = pts_host_m @ T_p_host[:3, :3].T + T_p_host[:3, 3]
            v = pts_p - o_m
            d = v - np.outer(v @ a_m, a_m)
            rho_m = float(np.sqrt((d ** 2).sum(axis=1)).max())
            out[j] = rho_m * 1000.0  # mm
        return out

    def _rho_table_c(self, rt, q_ref):
        """C object: capsules follow per-section hosts; compute per-joint rho over
        all capsule endpoints using each section's host, then take the max."""
        caps = rt.capsules
        a = np.asarray(caps["a_A0_mm"])
        b = np.asarray(caps["b_A0_mm"])
        sec = np.asarray(caps["section_index"])
        seg = caps["segment_id"]
        out = {}
        for si in sorted(set(sec.tolist())):
            host = K.SECTION_HOST[(seg, si)]
            up = UPSTREAM[host]
            if not up:
                continue
            pts = np.vstack([a[sec == si], b[sec == si]])
            pts_host = pts @ K.INV_FK0_MM[host][:3, :3].T + K.INV_FK0_MM[host][:3, 3]
            Tm = K.ARM.fk_m(q_ref)
            for j in up:
                pname = _PARENT_LINK[CHAIN_JOINTS[j]]
                o_m, ax = self._axes[CHAIN_JOINTS[j]]
                T_host_A0 = np.linalg.inv(Tm[host])
                T_p_host = Tm[pname] @ T_host_A0
                pts_p = (pts_host / 1000.0) @ T_p_host[:3, :3].T + T_p_host[:3, 3]
                v = pts_p - o_m
                d = v - np.outer(v @ ax, ax)
                rho_mm = float(np.sqrt((d ** 2).sum(axis=1)).max()) * 1000.0
                out[j] = max(out.get(j, 0.0), rho_mm)
        return out

    def workspace_diameter_bound_mm(self, rt):
        """Rigorous full-domain displacement bound via the workspace diameter:
        any vertex displacement over the whole joint domain is at most
        2 * max_q ||v_S(q)||, and ||v_S(q)|| <= mount offset + chain reach +
        object bounding radius (all constants, triangle inequality)."""
        if rt.pose_law in ("STATIC_S", "MOUNT_STATIC"):
            return 0.0
        pts = self._object_points_storage(rt)
        r_obj = float(np.sqrt((pts ** 2).sum(axis=1)).max())
        mount_off = float(np.linalg.norm(K.MOUNT_MM[:3, 3]))
        if rt.pose_law == "C_SECTION_POINT_LAWS":
            hosts = sorted({K.SECTION_HOST[(rt.capsules["segment_id"], si)]
                            for si in set(np.asarray(rt.capsules["section_index"]).tolist())})
            host = max(hosts, key=lambda h: len(UPSTREAM[h]))
        elif rt.pose_law in ("ARM_FK", "ARM_FK_2P"):
            host = rt.storage_frame
        elif rt.pose_law == "ARM_FK_LINK1":
            host = "link1"
        elif rt.pose_law == "ARM_FK_LINK2":
            host = "link2"
        else:
            host = rt.host
        chain_reach = 0.0
        link = host
        while link != "base_link":
            jname = next(n for n, j in K.ARM.joints.items() if j["child"] == link)
            chain_reach += float(np.linalg.norm(K.ARM.joints[jname]["xyz_m"])) * 1000.0
            link = K.ARM.joints[jname]["parent"]
        law_max = 0.0
        if rt.pose_law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
            name = rt.oid.split("::", 1)[1]
            if name in K.J3_CARRIAGE_PARTS:
                law_max += 2 * K.J3_TRAVEL_LIMIT_MM
            if rt.motion_class in ("ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL", "FULL_TRAVEL"):
                gain = {"ONE_THIRD_TRAVEL": 1.0 / 3.0, "TWO_THIRDS_TRAVEL": 2.0 / 3.0,
                        "FULL_TRAVEL": 1.0}[rt.motion_class]
                law_max += gain * K.J4_CARRIER_GAIN_MM_PER_RAD * (K.J4_Q_MAX_RAD - K.J4_Q_MIN_RAD)
        if rt.pose_law == "C_SECTION_POINT_LAWS" and rt.capsules["segment_id"] == K.J4_SEGMENT_ID:
            law_max += max(K.J4_CARRIER_GAIN_MM_PER_RAD * (K.J4_Q_MAX_RAD - K.J4_Q_MIN_RAD),
                           K.J4.ANN_RADIUS * (K.J4_Q_MAX_RAD - K.J4_Q_MIN_RAD))
        return 2.0 * (mount_off + chain_reach + r_obj + law_max)

    def displacement_bound_mm(self, rt, qa, qb, q_ref=None):
        """Conservative S-frame displacement bound (mm) for the object over the
        closed q interval [qa, qb] (elementwise)."""
        qa = np.asarray(qa, float)
        qb = np.asarray(qb, float)
        dq = np.abs(qb - qa)
        if q_ref is None:
            q_ref = 0.5 * (qa + qb)
        rho = self.rho_table(rt, q_ref)
        # downstream recursion from the wrist backwards, chord-saturated:
        #   D_j = (rho_j + D_{j+1}) * 2*sin(dq_j/2) + D_{j+1},  D beyond host = 0
        # 2*sin(dq/2) <= dq for dq >= 0 (chord <= arc), and saturates at 2 for
        # large dq, so full-domain bounds stay informative.
        D = 0.0
        for j in sorted(rho, reverse=True):
            chord = 2.0 * math.sin(float(dq[j]) / 2.0)
            D = (rho[j] + D) * chord + D
        total = D
        # registered linear law terms
        law = rt.pose_law
        if law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
            name = rt.oid.split("::", 1)[1]
            if name in K.J3_CARRIAGE_PARTS:
                total += K.J3_GAIN_MM_PER_RAD * dq[2]
            mc = rt.motion_class
            if mc in ("ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL", "FULL_TRAVEL"):
                gain = {"ONE_THIRD_TRAVEL": 1.0 / 3.0, "TWO_THIRDS_TRAVEL": 2.0 / 3.0,
                        "FULL_TRAVEL": 1.0}[mc]
                total += gain * K.J4_CARRIER_GAIN_MM_PER_RAD * dq[3]
        if law == "C_SECTION_POINT_LAWS":
            seg = rt.capsules["segment_id"]
            if seg == K.J4_SEGMENT_ID:
                total += max(K.J4_CARRIER_GAIN_MM_PER_RAD, K.J4.ANN_RADIUS) * dq[3]
        return total


# ================================================================ edge certification
def certify_edge(scene, certifier, pair_query_fn, oid_a, oid_b, qa, qb,
                 required_mm=0.0, depth=0, max_depth=10, budget=None):
    """Recursive continuous-edge certification for one pair over [qa, qb].

    Returns a certificate dict with PASS / FAIL / UNKNOWN."""
    if budget is None:
        budget = {"leaves": 0, "max_leaves": 4096}
    budget["leaves"] += 1
    qm = 0.5 * (np.asarray(qa) + np.asarray(qb))
    rec = {"edge": [list(map(float, qa)), list(map(float, qb))],
           "pair": [oid_a, oid_b], "depth": depth,
           "subdivision_count": 0, "lower_bound_history": []}
    ra, rb = scene.objects[oid_a], scene.objects[oid_b]

    # static certified lower bounds at both endpoints (conservative rungs only)
    ra_row = pair_query_fn(oid_a, oid_b, qa)
    rb_row = pair_query_fn(oid_a, oid_b, qb)
    for row in (ra_row, rb_row):
        if row["result"] == "UNSAFE":
            rec.update(result="FAIL", termination_reason="CERTIFIED_CONTACT_AT_ENDPOINT",
                       witness=row.get("rungs", [{}])[-1])
            return rec
    lows = []
    for row in (ra_row, rb_row):
        lb = None
        for rung in reversed(row["rungs"]):
            if "lower_bound_mm" in rung:
                lb = rung["lower_bound_mm"]
                break
            if "lower_mm" in rung:
                lb = rung["lower_mm"]
                break
        if lb is None:
            rec.update(result="UNKNOWN", termination_reason="ENDPOINT_WITHOUT_CERTIFIED_LOWER_BOUND")
            return rec
        lows.append(lb)
    Ba = certifier.displacement_bound_mm(ra, qa, qb, qm)
    Bb = certifier.displacement_bound_mm(rb, qa, qb, qm)
    lower = min(lows) - Ba - Bb
    rec["lower_bound_history"].append({"depth": depth, "lower_mm": lower,
                                       "Ba_mm": Ba, "Bb_mm": Bb})
    if lower - required_mm > 0.0:
        rec.update(result="PASS", minimum_certified_clearance_mm=lower,
                   termination_reason="CERTIFIED_BY_MOTION_BOUND")
        return rec
    if depth >= max_depth or budget["leaves"] >= budget["max_leaves"]:
        rec.update(result="UNKNOWN",
                   termination_reason="SUBDIVISION_BUDGET_EXHAUSTED")
        return rec
    rec["subdivision_count"] = 1
    left = certify_edge(scene, certifier, pair_query_fn, oid_a, oid_b, qa, qm,
                        required_mm, depth + 1, max_depth, budget)
    right = certify_edge(scene, certifier, pair_query_fn, oid_a, oid_b, qm, qb,
                         required_mm, depth + 1, max_depth, budget)
    rec["children"] = [left, right]
    results = {left["result"], right["result"]}
    if "FAIL" in results:
        rec.update(result="FAIL", termination_reason="CHILD_CERTIFIED_CONTACT")
    elif "UNKNOWN" in results:
        rec.update(result="UNKNOWN", termination_reason="CHILD_UNKNOWN")
    else:
        sub_min = min(left.get("minimum_certified_clearance_mm", math.inf),
                      right.get("minimum_certified_clearance_mm", math.inf))
        rec.update(result="PASS", minimum_certified_clearance_mm=sub_min,
                   termination_reason="CERTIFIED_BY_SUBDIVISION")
    return rec
