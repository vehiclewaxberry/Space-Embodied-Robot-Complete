"""B601 只读运动学参考实现（SIM13R / RC1-MR1）。

唯一 L0 权威 = 已接受 URDF `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`
（SHA-256 1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164）。
本模块**只读**该文件，不写回、不改写、不缓存派生质量属性。

URDF 语义（与 UNIFIED_R2_SYSTEM_FRAME_TREE_V2 一致）：
  T_parent_child(q) = T_origin(xyz, rpy) · T_motion(q)
  * joint origin 在 **parent link 帧**中表达；
  * q=0 时 child link 帧与 joint 帧重合；
  * axis 在 **joint/child 帧**中表达；
  * rpy = 固定轴 XYZ 外旋，R = Rz(yaw)·Ry(pitch)·Rx(roll)。

用法：
    from b601_kinematics import B601
    arm = B601()
    T = arm.fk(q6=[0]*6, qp=(0.0, 0.0))     # dict: link name -> 4x4
"""
import hashlib
import os
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
URDF_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
MESH_DIR_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper"

REVOLUTE_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
PRISMATIC_ORDER = ["gripper_joint1", "gripper_joint2"]


def rpy_to_R(rpy):
    """固定轴 XYZ 外旋：R = Rz(y)·Ry(p)·Rx(r)。"""
    r, p, y = (float(v) for v in rpy)
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def se3(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.asarray(t, float)
    return T


def axis_angle_to_R(axis, theta):
    """Rodrigues。axis 需为单位向量。"""
    k = np.asarray(axis, float)
    n = np.linalg.norm(k)
    if n < 1e-15:
        return np.eye(3)
    k = k / n
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(theta) * K + (1.0 - np.cos(theta)) * (K @ K)


class B601:
    """已接受 URDF 的只读运动学 + 惯性读取器。"""

    def __init__(self, urdf_rel=URDF_REL, verify_hash=True):
        self.urdf_path = os.path.join(REPO, urdf_rel)
        raw = open(self.urdf_path, "rb").read()
        self.urdf_sha256 = hashlib.sha256(raw).hexdigest().upper()
        self.urdf_bytes = len(raw)
        if verify_hash and self.urdf_sha256 != URDF_SHA256:
            raise RuntimeError(
                f"ACCEPTED_URDF_HASH_DRIFT: expected {URDF_SHA256} got {self.urdf_sha256}. "
                "fail-closed: refuse to run on a mutated L0 authority.")
        root = ET.fromstring(raw.decode("utf-8"))
        self.robot_name = root.get("name")

        self.links = {}
        for lk in root.findall("link"):
            ine = lk.find("inertial")
            rec = {"name": lk.get("name")}
            if ine is not None:
                o = ine.find("origin")
                i = ine.find("inertia")
                rec["mass"] = float(ine.find("mass").get("value"))
                rec["com"] = np.array([float(v) for v in o.get("xyz").split()])
                rec["com_rpy"] = np.array([float(v) for v in (o.get("rpy") or "0 0 0").split()])
                rec["I"] = np.array([
                    [float(i.get("ixx")), float(i.get("ixy")), float(i.get("ixz"))],
                    [float(i.get("ixy")), float(i.get("iyy")), float(i.get("iyz"))],
                    [float(i.get("ixz")), float(i.get("iyz")), float(i.get("izz"))]])
            mesh = lk.find("./collision/geometry/mesh")
            rec["collision_mesh"] = mesh.get("filename") if mesh is not None else None
            self.links[rec["name"]] = rec

        self.joints = {}
        self.order = []
        for j in root.findall("joint"):
            o = j.find("origin")
            ax = j.find("axis")
            lim = j.find("limit")
            name = j.get("name")
            rec = {
                "name": name,
                "type": j.get("type"),
                "parent": j.find("parent").get("link"),
                "child": j.find("child").get("link"),
                "origin_xyz": np.array([float(v) for v in (o.get("xyz") or "0 0 0").split()]),
                "origin_rpy": np.array([float(v) for v in (o.get("rpy") or "0 0 0").split()]),
                "axis_child": (np.array([float(v) for v in ax.get("xyz").split()])
                               if ax is not None else np.zeros(3)),
            }
            if lim is not None and lim.get("lower") is not None:
                rec["lower"] = float(lim.get("lower"))
                rec["upper"] = float(lim.get("upper"))
                rec["effort"] = float(lim.get("effort"))
                rec["velocity"] = float(lim.get("velocity"))
            rec["R_origin"] = rpy_to_R(rec["origin_rpy"])
            # 轴在 parent 帧中的表达（q=0 时 child 帧 = joint 帧）
            rec["axis_parent"] = rec["R_origin"] @ rec["axis_child"]
            self.joints[name] = rec
            self.order.append(name)

        # 父子拓扑：从 base_link 出发的链
        self.root_link = "base_link"
        self.child_joints = {}
        for n, jr in self.joints.items():
            self.child_joints.setdefault(jr["parent"], []).append(n)

    # ------------------------------------------------------------------ FK
    def joint_transform(self, name, q):
        jr = self.joints[name]
        T0 = se3(jr["R_origin"], jr["origin_xyz"])
        if jr["type"] == "revolute" or jr["type"] == "continuous":
            Tm = se3(axis_angle_to_R(jr["axis_child"], float(q)), np.zeros(3))
        elif jr["type"] == "prismatic":
            a = jr["axis_child"]
            Tm = se3(np.eye(3), a / max(np.linalg.norm(a), 1e-15) * float(q))
        else:                                       # fixed
            Tm = np.eye(4)
        return T0 @ Tm

    def q_map(self, q6, qp):
        m = {n: 0.0 for n in self.joints}
        for n, v in zip(REVOLUTE_ORDER, q6):
            m[n] = float(v)
        for n, v in zip(PRISMATIC_ORDER, qp):
            m[n] = float(v)
        return m

    def fk(self, q6=(0,) * 6, qp=(0.0, 0.0), base_T=None):
        """返回 {link_name: 4x4 T_base_link}。base_T 可注入 T_SB。"""
        qm = self.q_map(q6, qp)
        T = {self.root_link: np.eye(4) if base_T is None else np.asarray(base_T, float)}
        stack = [self.root_link]
        while stack:
            p = stack.pop()
            for jn in self.child_joints.get(p, []):
                jr = self.joints[jn]
                T[jr["child"]] = T[p] @ self.joint_transform(jn, qm[jn])
                stack.append(jr["child"])
        return T

    def axis_in_frame(self, joint_name, target_link, q6=(0,) * 6, qp=(0.0, 0.0)):
        """关节轴在任一 link 帧中的方向（单位向量）。"""
        T = self.fk(q6, qp)
        jr = self.joints[joint_name]
        a_child_world = T[jr["child"]][:3, :3] @ jr["axis_child"]
        a = T[target_link][:3, :3].T @ a_child_world
        n = np.linalg.norm(a)
        return a / n if n > 1e-15 else a

    # -------------------------------------------------------------- meshes
    def mesh_path(self, link):
        fn = self.links[link].get("collision_mesh")
        if not fn:
            return None
        return os.path.join(REPO, MESH_DIR_REL, os.path.basename(fn))

    def load_mesh(self, link):
        import trimesh
        p = self.mesh_path(link)
        if p is None or not os.path.isfile(p):
            return None
        return trimesh.load_mesh(p, process=False)

    # --------------------------------------------------------------- misc
    def total_mass(self):
        return sum(v["mass"] for v in self.links.values() if "mass" in v)

    def provenance(self):
        return {"urdf_path": URDF_REL, "urdf_sha256": self.urdf_sha256,
                "urdf_bytes": self.urdf_bytes, "robot_name": self.robot_name,
                "n_links": len(self.links), "n_joints": len(self.joints),
                "total_mass_kg": self.total_mass()}


if __name__ == "__main__":
    import json
    arm = B601()
    print(json.dumps(arm.provenance(), indent=1))
    T = arm.fk()
    for lk in ["base_link", "link6", "gripper_link", "gripper_left", "gripper_right"]:
        print(f"  {lk:15s} p = {np.round(T[lk][:3, 3], 6)}")
