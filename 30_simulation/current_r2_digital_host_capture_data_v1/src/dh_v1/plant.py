"""Floating-base rigid multibody plant built from an extracted URDF model.

Scope guard: this is the PREBIND dynamics candidate for scenario S01/S02/S03
(no contact, no gravity, no flexible bodies). It is NOT a contact authority,
NOT a time-domain control certificate, and does not replace sim_05/sim_10..12
machine gates.

Algorithms: body-frame Featherstone — CRBA for the joint-space inertia matrix
(floating base treated as a 6-DOF joint), RNEA for velocity-product bias.
Spatial vector ordering [angular; linear]; conventions from dh_v1.frames.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .frames import invert_T, make_T, rpy_to_R, skew
from .spatial import X_force, X_motion, crf, crm, spatial_inertia, transform_spatial_inertia
from .urdf_extract import validate_tree


class PlantBuildError(RuntimeError):
    pass


@dataclass
class DynBody:
    name: str                       # name of the URDF link that defines this body frame
    parent: int                     # parent dynamic-body index (-1 for base)
    T_tree: np.ndarray | None       # parent body frame -> joint origin frame (q-independent)
    jtype: str | None               # 'revolute' | 'prismatic' (None for base)
    axis: np.ndarray | None         # unit axis in child body frame
    limits: dict | None
    I_sp: np.ndarray = field(default_factory=lambda: np.zeros((6, 6)))  # lumped, body frame
    lumped_links: list = field(default_factory=list)  # [(link_name, T_body_link)]


def _axis_rot(axis: np.ndarray, q: float) -> np.ndarray:
    K = skew(axis)
    return np.eye(3) + np.sin(q) * K + (1.0 - np.cos(q)) * (K @ K)


def compose_models(parent_model: dict, child_model: dict, parent_link: str,
                   mount_xyz, mount_rpy, mount_joint_name: str) -> dict:
    """Merge two URDF-extracted models with a fixed mount joint
    parent_link -> child root. Fails if names collide."""
    p_links = {l["name"] for l in parent_model["links"]}
    c_links = {l["name"] for l in child_model["links"]}
    if p_links & c_links:
        raise PlantBuildError(f"link name collision: {p_links & c_links}")
    child_root = validate_tree(child_model)["root_link"]
    if parent_link not in p_links:
        raise PlantBuildError(f"mount parent link {parent_link!r} not in parent model")
    merged = {
        "robot_name": f"{parent_model['robot_name']}+{child_model['robot_name']}",
        "links": [dict(l) for l in parent_model["links"]] + [dict(l) for l in child_model["links"]],
        "joints": [dict(j) for j in parent_model["joints"]]
        + [
            {
                "name": mount_joint_name,
                "type": "fixed",
                "parent": parent_link,
                "child": child_root,
                "origin_xyz": list(mount_xyz),
                "origin_rpy": list(mount_rpy),
                "axis": None,
                "limits": None,
            }
        ]
        + [dict(j) for j in child_model["joints"]],
        "provenance": {
            "composition": {
                "parent": parent_model["provenance"],
                "child": child_model["provenance"],
                "mount_joint": mount_joint_name,
                "mount_xyz": list(mount_xyz),
                "mount_rpy": list(mount_rpy),
            }
        },
    }
    validate_tree(merged)
    return merged


class FloatingPlant:
    """Kinematic tree of dynamic bodies over a free-floating base."""

    def __init__(self, model: dict):
        topo = validate_tree(model)
        root = topo["root_link"]
        links = {l["name"]: l for l in model["links"]}
        joints_by_parent: dict[str, list] = {}
        for j in model["joints"]:
            joints_by_parent.setdefault(j["parent"], []).append(j)

        self.model_provenance = model.get("provenance", {})
        self.bodies: list[DynBody] = [DynBody(name=root, parent=-1, T_tree=None, jtype=None, axis=None, limits=None)]
        self._lump_link(0, root, np.eye(4), links)

        # depth-first walk; fixed joints lump, movable joints spawn bodies
        stack = [(root, 0, np.eye(4))]  # (link, owner body idx, T_ownerbody_link)
        order_guard = 0
        while stack:
            link, owner, T_ol = stack.pop(0)
            for j in joints_by_parent.get(link, []):
                T_o_jorigin = T_ol @ make_T(rpy_to_R(j["origin_rpy"]), j["origin_xyz"])
                if j["type"] == "fixed":
                    self._lump_link(owner, j["child"], T_o_jorigin, links)
                    stack.append((j["child"], owner, T_o_jorigin))
                elif j["type"] in ("revolute", "prismatic", "continuous"):
                    jt = "revolute" if j["type"] == "continuous" else j["type"]
                    body = DynBody(
                        name=j["child"],
                        parent=owner,
                        T_tree=T_o_jorigin,
                        jtype=jt,
                        axis=np.asarray(j["axis"], dtype=float),
                        limits=j["limits"],
                    )
                    self.bodies.append(body)
                    idx = len(self.bodies) - 1
                    if idx <= owner:
                        raise PlantBuildError("topological order violated")
                    self._lump_link(idx, j["child"], np.eye(4), links)
                    stack.append((j["child"], idx, np.eye(4)))
                else:
                    raise PlantBuildError(f"joint {j['name']}: type {j['type']} not supported in plant")
            order_guard += 1
            if order_guard > 10000:
                raise PlantBuildError("tree walk did not terminate")

        self.nj = len(self.bodies) - 1
        self.joint_names = [b.name for b in self.bodies[1:]]
        for b in self.bodies:
            if abs(b.I_sp[5, 5]) < 1.0e-12:
                raise PlantBuildError(f"dynamic body {b.name} has zero lumped mass")

    def _lump_link(self, body_idx: int, link_name: str, T_body_link: np.ndarray, links: dict) -> None:
        l = links[link_name]
        body = self.bodies[body_idx]
        if l["inertial"] is not None:
            I_link = spatial_inertia(
                l["inertial"]["mass"], l["inertial"]["com"], np.asarray(l["inertial"]["inertia_com"])
            )
            body.I_sp = body.I_sp + transform_spatial_inertia(I_link, T_body_link)
        body.lumped_links.append((link_name, T_body_link.copy()))

    # --- kinematics -------------------------------------------------------
    def _kin(self, q: np.ndarray):
        """Per movable body i (1..nb-1): (T_p_i, X_up = Xm(i<-p), S_i)."""
        out = []
        for k, b in enumerate(self.bodies[1:]):
            qi = float(q[k])
            if b.jtype == "revolute":
                T_j = make_T(_axis_rot(b.axis, qi), np.zeros(3))
                S = np.concatenate([b.axis, np.zeros(3)])
            else:  # prismatic
                T_j = make_T(np.eye(3), b.axis * qi)
                S = np.concatenate([np.zeros(3), b.axis])
            T_p_i = b.T_tree @ T_j
            out.append((T_p_i, X_motion(invert_T(T_p_i)), S))
        return out

    def body_poses_world(self, R_WB: np.ndarray, p_WB: np.ndarray, q: np.ndarray) -> list[np.ndarray]:
        kin = self._kin(q)
        T_W = [make_T(R_WB, p_WB)]
        for i in range(1, len(self.bodies)):
            T_W.append(T_W[self.bodies[i].parent] @ kin[i - 1][0])
        return T_W

    def fk_links_world(self, R_WB: np.ndarray, p_WB: np.ndarray, q: np.ndarray) -> dict[str, np.ndarray]:
        T_W = self.body_poses_world(R_WB, p_WB, q)
        out: dict[str, np.ndarray] = {}
        for i, b in enumerate(self.bodies):
            for link_name, T_bl in b.lumped_links:
                out[link_name] = T_W[i] @ T_bl
        return out

    def body_velocities(self, q: np.ndarray, v_base: np.ndarray, qd: np.ndarray, kin=None):
        kin = kin or self._kin(q)
        v = [np.asarray(v_base, dtype=float)]
        for i in range(1, len(self.bodies)):
            T_p_i, X_up, S = kin[i - 1]
            v.append(X_up @ v[self.bodies[i].parent] + S * qd[i - 1])
        return v, kin

    # --- dynamics ---------------------------------------------------------
    def crba(self, q: np.ndarray, kin=None) -> np.ndarray:
        """Generalized inertia H (6+nj x 6+nj), base rows/cols first (base body
        coordinates about base origin)."""
        kin = kin or self._kin(q)
        nb = len(self.bodies)
        Ic = [b.I_sp.copy() for b in self.bodies]
        H = np.zeros((6 + self.nj, 6 + self.nj))
        for i in range(nb - 1, 0, -1):
            T_p_i, X_up, S = kin[i - 1]
            p = self.bodies[i].parent
            Xf = X_force(T_p_i)
            Ic[p] += Xf @ Ic[i] @ X_up
            # column for joint i
            F = Ic[i] @ S
            H[6 + i - 1, 6 + i - 1] = float(S @ F)
            j = i
            Fj = F.copy()
            while self.bodies[j].parent > 0:
                T_p_j = kin[j - 1][0]
                Fj = X_force(T_p_j) @ Fj
                j = self.bodies[j].parent
                Sj = kin[j - 1][2]
                H[6 + i - 1, 6 + j - 1] = float(Fj @ Sj)
                H[6 + j - 1, 6 + i - 1] = H[6 + i - 1, 6 + j - 1]
            # base coupling: transform F into base coordinates
            Fb = X_force(kin[j - 1][0]) @ Fj
            H[:6, 6 + i - 1] = Fb
            H[6 + i - 1, :6] = Fb
        H[:6, :6] = Ic[0]
        return H

    def bias(self, q: np.ndarray, v_base: np.ndarray, qd: np.ndarray, kin=None) -> np.ndarray:
        """Velocity-product generalized force C(q, u) with zero gravity and zero
        base spatial acceleration (floating-base RNEA)."""
        v, kin = self.body_velocities(q, v_base, qd, kin)
        nb = len(self.bodies)
        a = [np.zeros(6) for _ in range(nb)]
        f = [np.zeros(6) for _ in range(nb)]
        f[0] = crf(v[0]) @ (self.bodies[0].I_sp @ v[0])
        for i in range(1, nb):
            T_p_i, X_up, S = kin[i - 1]
            p = self.bodies[i].parent
            vJ = S * qd[i - 1]
            a[i] = X_up @ a[p] + crm(v[i]) @ vJ
            f[i] = self.bodies[i].I_sp @ a[i] + crf(v[i]) @ (self.bodies[i].I_sp @ v[i])
        C = np.zeros(6 + self.nj)
        for i in range(nb - 1, 0, -1):
            T_p_i, X_up, S = kin[i - 1]
            C[6 + i - 1] = float(S @ f[i])
            f[self.bodies[i].parent] += X_force(T_p_i) @ f[i]
        C[:6] = f[0]
        return C

    def forward_dynamics(self, q, v_base, qd, tau_joints):
        kin = self._kin(q)
        H = self.crba(q, kin)
        C = self.bias(q, v_base, qd, kin)
        rhs = np.concatenate([np.zeros(6), np.asarray(tau_joints, dtype=float)]) - C
        udot = np.linalg.solve(H, rhs)
        return udot, H, C

    # --- ledgers ------------------------------------------------------------
    def momentum_world(self, R_WB, p_WB, q, v_base, qd):
        """Returns (h_O world origin [n; f], h_C about system CoM, p_com, m_total,
        E_kin)."""
        v, kin = self.body_velocities(q, v_base, qd)
        T_W = [make_T(R_WB, p_WB)]
        for i in range(1, len(self.bodies)):
            T_W.append(T_W[self.bodies[i].parent] @ kin[i - 1][0])
        h_O = np.zeros(6)
        E = 0.0
        m_total = 0.0
        m_r = np.zeros(3)
        for i, b in enumerate(self.bodies):
            h_i = b.I_sp @ v[i]
            h_O += X_force(T_W[i]) @ h_i
            E += 0.5 * float(v[i] @ h_i)
            m_i = b.I_sp[5, 5]
            # CoM from the skew block: I_sp[:3,3:] = m*skew(c), so
            # m*cx = I_sp[2,4], m*cy = I_sp[0,5], m*cz = I_sp[1,3]
            c_body = np.array([b.I_sp[2, 4], b.I_sp[0, 5], b.I_sp[1, 3]]) / m_i
            c_world = (T_W[i] @ np.concatenate([c_body, [1.0]]))[:3]
            m_total += m_i
            m_r += m_i * c_world
        p_com = m_r / m_total
        h_C = h_O.copy()
        h_C[:3] = h_O[:3] - np.cross(p_com, h_O[3:])
        return h_O, h_C, p_com, m_total, E

    def base_velocity_from_momentum(self, R_WB, p_WB, q, qd, h_O_target):
        """Solve base spatial velocity that realizes a target world-origin
        momentum given joint rates (free-floating momentum-projection form)."""
        kin = self._kin(q)
        H = self.crba(q, kin)
        T_WB = make_T(R_WB, p_WB)
        # momentum about base origin, base coords: h_B = H[:6,:6] v_base + H[:6,6:] qd
        h_B_target = np.linalg.solve(X_force(T_WB), np.asarray(h_O_target, dtype=float))
        rhs = h_B_target - H[:6, 6:] @ np.asarray(qd, dtype=float)
        return np.linalg.solve(H[:6, :6], rhs)
