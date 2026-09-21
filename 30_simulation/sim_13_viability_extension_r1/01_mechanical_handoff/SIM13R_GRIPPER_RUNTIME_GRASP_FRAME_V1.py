"""M5-B：B601 夹爪运行时抓取帧 / 开口 / 接触点 / 接触法向模型。

纪律
----
* grasp frame **不是**固定 CAD 帧。它由 (q_p1, q_p2)、目标几何、所选接触点与
  接触法向在运行时计算。参考构型只作 witness 保留。
* 左右指方向来自 M1 已闭合的调和结论：URDF 把左右不对称编码在 joint origin 的
  rpy(Rz(∓90°)) 里，因此在 palm 帧中左指沿 -Y、右指沿 +Y。
* 颚面几何由 accepted URDF 的 collision mesh 派生，标记 PROVISIONAL_MESH_DERIVED。
* 任何 CAD 派生质量属性都不得写回 L0。

坐标约定（palm = gripper_link 帧）
    +X  远端（接近/抓取方向），link6 在 -X
    ±Y  指开合方向
    +Z  与 X、Y 构成右手系
"""
import os

import numpy as np

from b601_kinematics import B601

HERE = os.path.dirname(os.path.abspath(__file__))

# 颚片切片区间（palm 帧 X），由 M1 网格切片确定
JAW_X_LO, JAW_X_HI = -0.050, -0.015
FACE_BAND = 3e-4          # 内颚面取样带宽 [m]
TIP_BAND = 2e-3           # 指尖取样带宽 [m]
STROKE = 0.0715           # 单指行程 [m]（accepted URDF 上限）


class GripperGraspModel:
    """运行时抓取帧与接触几何。"""

    def __init__(self, arm=None):
        self.arm = arm or B601()
        T0 = self.arm.fk()
        self._Tp0 = T0["gripper_link"]
        self._feat = {"LEFT": self._finger_features("gripper_left", "LEFT", T0),
                      "RIGHT": self._finger_features("gripper_right", "RIGHT", T0)}
        self.aperture_closed = float(self._feat["RIGHT"]["face_y"]
                                     - self._feat["LEFT"]["face_y"])

    # ------------------------------------------------------------------
    def _finger_features(self, link, side, T0):
        m = self.arm.load_mesh(link)
        V = np.asarray(m.vertices)
        Tl = np.linalg.inv(T0["gripper_link"]) @ T0[link]
        Vp = (Tl[:3, :3] @ V.T).T + Tl[:3, 3]
        jaw = Vp[(Vp[:, 0] >= JAW_X_LO) & (Vp[:, 0] <= JAW_X_HI)]
        if side == "LEFT":                       # 左指在 -Y 侧，内面 = 最大 y
            y_face = float(jaw[:, 1].max())
            face = jaw[np.abs(jaw[:, 1] - y_face) <= FACE_BAND]
            n_in = np.array([0.0, 1.0, 0.0])     # 指向抓取轴
        else:                                    # 右指在 +Y 侧，内面 = 最小 y
            y_face = float(jaw[:, 1].min())
            face = jaw[np.abs(jaw[:, 1] - y_face) <= FACE_BAND]
            n_in = np.array([0.0, -1.0, 0.0])
        x_tip = float(Vp[:, 0].max())
        tip = Vp[Vp[:, 0] >= x_tip - TIP_BAND]
        return {"face_y": y_face, "contact_point": face.mean(axis=0),
                "inward_normal": n_in, "tip_point": tip.mean(axis=0),
                "face_vertex_count": int(len(face)),
                "face_extent_x": [float(face[:, 0].min()), float(face[:, 0].max())],
                "face_extent_z": [float(face[:, 2].min()), float(face[:, 2].max())]}

    # ---------------------------------------------------------- 接口 API
    def aperture(self, q_p1, q_p2):
        """开口 a(q_p1,q_p2) [m]：两内颚面之间的距离。"""
        return self.aperture_closed + float(q_p1) + float(q_p2)

    def contact_points_palm(self, q_p1, q_p2):
        """左右接触点在 palm 帧的位置 [m]。左指沿 -Y，右指沿 +Y。"""
        L = self._feat["LEFT"]["contact_point"] + np.array([0.0, -float(q_p1), 0.0])
        R = self._feat["RIGHT"]["contact_point"] + np.array([0.0, +float(q_p2), 0.0])
        return L, R

    def contact_normals_palm(self, q_p1=0.0, q_p2=0.0):
        """接触法向（指向抓取轴，即作用在目标上的法向方向）。平移不改变法向。"""
        return self._feat["LEFT"]["inward_normal"].copy(), \
            self._feat["RIGHT"]["inward_normal"].copy()

    def tip_points_palm(self, q_p1, q_p2):
        L = self._feat["LEFT"]["tip_point"] + np.array([0.0, -float(q_p1), 0.0])
        R = self._feat["RIGHT"]["tip_point"] + np.array([0.0, +float(q_p2), 0.0])
        return L, R

    def grasp_frame_palm(self, q_p1, q_p2, contact_normal_hint=None):
        """运行时 grasp 帧 T_palm_grasp (4x4)。

        原点 = 两接触点中点；
        Y_g  = 闭合方向（右接触点 - 左接触点，归一化）；
        X_g  = 接近方向（palm +X），必要时按接触法向提示修正；
        Z_g  = X_g x Y_g。
        """
        L, R = self.contact_points_palm(q_p1, q_p2)
        o = 0.5 * (L + R)
        y = R - L
        ny = np.linalg.norm(y)
        y = y / ny if ny > 1e-12 else np.array([0.0, 1.0, 0.0])
        x = np.array([1.0, 0.0, 0.0]) if contact_normal_hint is None \
            else np.asarray(contact_normal_hint, float)
        x = x - np.dot(x, y) * y
        nx = np.linalg.norm(x)
        x = x / nx if nx > 1e-12 else np.array([1.0, 0.0, 0.0])
        z = np.cross(x, y)
        T = np.eye(4)
        T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = x, y, z, o
        return T

    def grasp_frame_world(self, q6, qp, base_T=None, contact_normal_hint=None):
        """grasp 帧在 base_link（或注入 base_T 后的上级）帧中的位姿。"""
        T = self.arm.fk(q6=q6, qp=qp, base_T=base_T)
        return T["gripper_link"] @ self.grasp_frame_palm(qp[0], qp[1],
                                                         contact_normal_hint)

    def grasp_radius(self, q_p1, q_p2):
        return 0.5 * self.aperture(q_p1, q_p2)

    def valid_configuration(self, q_p1, q_p2):
        """有效 P 关节构型判定（仅 accepted URDF 限位；不含接触力判定）。"""
        ok = (0.0 <= q_p1 <= STROKE) and (0.0 <= q_p2 <= STROKE)
        return {"valid": bool(ok), "q_p1": float(q_p1), "q_p2": float(q_p2),
                "stroke_limit_m": STROKE,
                "aperture_m": self.aperture(q_p1, q_p2) if ok else None,
                "reason": "" if ok else "PRISMATIC_LIMIT_VIOLATION"}

    def target_fits(self, target_width_m, q_p1=STROKE, q_p2=STROKE, margin_m=0.0):
        """目标尺寸包络判定：能否在给定开口下容纳该宽度。"""
        a_max = self.aperture(q_p1, q_p2)
        a_min = self.aperture_closed
        return {"target_width_m": float(target_width_m),
                "aperture_min_m": a_min, "aperture_max_m": a_max,
                "fits": bool(a_min + margin_m <= target_width_m <= a_max - margin_m),
                "reason": ("" if a_min + margin_m <= target_width_m <= a_max - margin_m
                           else ("TARGET_TOO_LARGE" if target_width_m > a_max - margin_m
                                 else "TARGET_TOO_SMALL_JAWS_CANNOT_CLOSE_ON_IT"))}

    def witness_reference_configuration(self):
        """仅作 witness 保留的参考构型，**不是**固定 grasp 帧。"""
        return {"note": "reference witness only; the active grasp frame is computed "
                        "at runtime from (q_p1, q_p2), target geometry and contacts",
                "q_p1": 0.0, "q_p2": 0.0,
                "aperture_m": self.aperture_closed,
                "T_palm_grasp": self.grasp_frame_palm(0.0, 0.0).tolist()}


if __name__ == "__main__":
    g = GripperGraspModel()
    print(f"aperture closed = {g.aperture(0,0)*1000:.3f} mm")
    print(f"aperture open   = {g.aperture(STROKE,STROKE)*1000:.3f} mm")
    print(f"grasp radius    = {g.grasp_radius(0,0)*1000:.3f} .. "
          f"{g.grasp_radius(STROKE,STROKE)*1000:.3f} mm")
    L, R = g.contact_points_palm(0.02, 0.05)
    print("asymmetric contacts:", np.round(L, 6), np.round(R, 6))
    print("grasp frame origin :", np.round(g.grasp_frame_palm(0.02, 0.05)[:3, 3], 6))
