"""SOLIDWORKS-NATIVE-MECHANICAL-REALIZATION-01：几何参数 SSOT（方程 API 已死，
参数经此文件 + PARAM_* 自定义属性入模型）。

设计纪律（针对 VENDOR-CAD-03 的 V14 28 处互穿）：
**所有零件按全局坐标建模，相邻件只允许接触面（共面），不得实体重叠。**
纵梁与环框同截面 17×17、角点 ±101.65；环框横梁在纵梁之间端接（端面接触）。
外板 3mm 贴在纵梁外表面（110.15）之外，齐平 113.15。
"""
from __future__ import annotations

# ── 主包络（显示轨 BUS_X_TOTAL=366；Gate 0 已裁决）────────────────────────
X_FRONT, X_REAR = 183.0, -183.0
ENV = 113.15                       # ±Y/±Z 外皮
PANEL_T = 3.0
SKIN_IN = ENV - PANEL_T            # 110.15 纵梁/环框外表面
LONG_C = 101.65                    # 纵梁/环框角点中心
LONG_H = 8.5                       # 半截面 → 93.15..110.15（17mm 见方）
RAIL_IN = LONG_C - LONG_H          # 93.15 环框横梁端接站位

# ── 站位（X）────────────────────────────────────────────────────────────
STA = {
    "REAR_END":      (-183.0, -175.0),
    "MID2":          (-64.0, -58.0),
    "MID1":          (58.0, 64.0),
    "FRONT_TRANS":   (119.0, 125.0),
    "FRONT_END":     (175.0, 183.0),
}
DECK_Z = (-40.0, -36.0)

# ── B601 安装链（双轨冲突显式登记，不静默混用）──────────────────────────
MOUNT_FACE_X_DISPLAY = 198.0       # 本装配采用（与 ±183 显示轨自洽）
T_SM_DYNAMICS_TRACK = 185.25       # 340.5 动力学轨；与 366 结构不自洽，仅登记
ADAPTER_PLATE = (160.0, 12.0)      # 边长、厚
CENTRAL_BORE_D = 100.0

# ── 收拢支承（接触高度=130 真实厂商几何顶点实测，25° 时钟提案位形）───────
SADDLE = {   # tag: (x_lo, x_hi, z_contact, y_min, y_max)
    "UPPER_ARM": (10.0, 60.0, 234.77, -66.48, 92.89),
    "FOREARM":   (-40.0, 0.0, 248.49, -77.84, 75.65),
    "WRIST":     (-100.0, -40.0, 253.80, -27.25, 104.24),
}

# ── 太阳翼根部机构（铰链销轴平行 X）──────────────────────────────────────
# O9 返工：全部改用 Codex 100_Mechanical_Continuation / SOURCE_B5 值（外挂式）
ROOT_BASE_X = (-79.0, -43.0)
ROOT_BASE_Y = (113.15, 121.15)      # bus 侧起 113.15，外伸 8
ROOT_BASE_Z = (-40.0, 40.0)
ROOT_SPINE_X = (-67.0, -55.0)
# Codex 原值 (110.15,121.15) 与 ROOT_BASE 实体重叠 7680mm³（其自述"故意嵌入"）；
# 本轮缩至板厚区间：内接节点垫、外抵 Root_Base 内面，桥接功能保留且零干涉
ROOT_SPINE_Y = (110.15, 113.15)
ROOT_SPINE_Z = (-75.0, 75.0)
EAR_X = ((-75.0, -65.0), (-57.0, -47.0))
EAR_Y = (121.15, 151.15)            # 耳片外缘 151.15 → 机构下限宽 302.3
EAR_HALF_T = 5.0                    # 厚 10
HINGE_PIN_Y = 143.15                # 113.15+8+30-8
HINGE_PIN_Z = 0.0
HINGE_PIN_R = 4.0                   # Ø8
HINGE_PIN_LEN = 24.0
HINGE_BORE_D = 8.4
SPRING_R = 8.0                      # Ø16
SPRING_LEN = 18.0
HDRM_STATIONS_X = (-160.0, 40.0)
HDRM_BASE_HALF = 12.0               # 24 见方
HDRM_BASE_Y = (113.15, 121.15)      # 厚 8
HDRM_BASE_ZC = -100.0
HDRM_ROD_R = 5.0                    # Ø10
HDRM_ROD_Y = (121.15, 141.15)       # 长 20
HARD_STOP_X = (-64.0, -58.0)
HARD_STOP_Y = (121.15, 129.15)      # 厚 8
HARD_STOP_ZC, HARD_STOP_HALF = 30.0, 7.0   # 14 见方

# O10 不可消解负结果（Codex C5-PACKAGE-01，禁止通过移动/减薄制造假通过）
C5_BUS_AVAILABLE_WIDTH = 226.3
C5_STOWED_PACKAGE_WIDTH = 238.3
C5_OVERAGE = 12.0
SOLAR_ROOT_MECHANISM_LOWER_BOUND_WIDTH = 302.3
PANEL_ROOT_Y = 110.0      # 冻结：翼板根缘（本阶段不建翼板）
PANEL_ROOT_Z = -105.65
HINGE_X = {"EAR_FWD": (130.0, 142.0), "BLADE": (142.0, 158.0),
           "EAR_AFT": (158.0, 170.0), "PIN": (128.0, 172.0)}

# ── 未定义判据（必须显式入模型，禁止默认合规）──────────────────────────
UNKNOWNS = {
    "STOW_Z_LIMIT_REFERENCE": "UNKNOWN",
    "STOW_Z_LIMIT_NOTE": "冻结输入无收拢态 Z 上限；主结构盒顶 z=+113.15，"
                          "而 25° 提案位形臂顶 z≈361 —— 合规性未定，禁止默认判定",
    "T_SM_TRACK_CONFLICT": f"display={MOUNT_FACE_X_DISPLAY} 采用（人工裁决 2026-07-27，"
                            f"与 Codex adapter_outer_face_x 一致）；"
                            f"dynamics_SSOT={T_SM_DYNAMICS_TRACK} 不采用",
    "C5_PACKAGE_NEGATIVE": f"收拢翼包宽 {C5_STOWED_PACKAGE_WIDTH} > 可用 "
                            f"{C5_BUS_AVAILABLE_WIDTH}，超 {C5_OVERAGE}mm —— "
                            "NEGATIVE_PRESERVED_NOT_CLOSED（继承 Codex C5-PACKAGE-01，"
                            "禁止通过隐藏/减薄/移动制造假通过）",
    "SOLAR_ROOT_WIDTH_NEGATIVE": f"双侧根部硬件达 |Y|=151.15 → 机构下限宽 "
                                   f"{SOLAR_ROOT_MECHANISM_LOWER_BOUND_WIDTH}mm "
                                   f"> {C5_BUS_AVAILABLE_WIDTH} —— 同为不可消解负结果",
}


def ring_rects():
    """环框 = 4 根 17×17 横梁，在纵梁之间端接（不进入纵梁体积）。"""
    return [(0.0, LONG_C, RAIL_IN, LONG_H),      # 顶梁
            (0.0, -LONG_C, RAIL_IN, LONG_H),     # 底梁
            (LONG_C, 0.0, LONG_H, RAIL_IN),      # +Y 梁
            (-LONG_C, 0.0, LONG_H, RAIL_IN)]     # -Y 梁


def longeron_rects():
    return [(sy * LONG_C, sz * LONG_C, LONG_H, LONG_H)
            for sy in (1, -1) for sz in (1, -1)]


def props(name, role, status, owner, claim, parent, extra=None):
    p = {"PART_NAME": name, "ROLE": role, "STATUS": status, "OWNER": owner,
         "PARENT_ASSEMBLY": parent, "CLAIM_LIMIT": claim,
         "GEOMETRY_AUTHORITY": "NATIVE_SW_THIS_FILE",
         "KINEMATIC_AUTHORITY": "ACCEPTED_URDF",
         "MASS_AUTHORITY": "EXCLUDED_URDF_ONLY",
         "MANUFACTURING_AUTHORITY": "NONE",
         "STRENGTH_AUTHORITY": "NONE",
         "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing"}
    if extra:
        p.update(extra)
    return p


CLAIM = ("PHASE1_NATIVE_MECHANICAL;NO_STRENGTH_CLAIM;NO_MATERIAL;NO_TOLERANCE;"
         "CONTACT_FACES_NOT_VERIFIED_JOINTS")
