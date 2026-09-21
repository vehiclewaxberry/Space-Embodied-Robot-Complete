# 变换与姿态约定（冻结，S00 强制）

来源 SSOT：`coordinate_frame_definition_v0.md`（frame 命名与 T_XY 记号）、
`POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1.json`（se3_convention）、
`UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml`（matrix_semantics）。本文件只汇编，不新设约定。

## 变换

- `T_A_B` 表示"B 在 A 中的位姿"：`x_A = R_A_B · x_B + p_A_B`（与 kernel 合同 se3_convention 逐字一致；
  与 frame SSOT 的 `p_X = T_XY · p_Y` 一致；与 V2 frame tree 的
  `p_parent = R_parent_child · p_child + t_parent_child` 一致）。
- 复合：`T_A_C = T_A_B · T_B_C`。求逆：`T_B_A = T_A_B^{-1}`。
- 旋转矩阵列 = 子系坐标轴在父系中的表达。主动/被动措辞差异不改变上式代数。
- URDF `<origin xyz rpy>` 给出 `T_parent_child`，rpy 为固定轴 XYZ：`R = Rz(y)·Ry(p)·Rx(r)`。

## 四元数

- 存储顺序 **scalar-first `[w, x, y, z]`**（SSOT 与 30_simulation/common/rigid_body.py 先例一致），单位范数。
- `q_A_B` 与 `R_A_B` 同义；积分中每步重归一并记录累计漂移（`quat_renorm` 审计列）。

## 动量记号（防混用，sim_10/12 教训）

- `h_O`：关于**惯性系原点**的空间动量 `[n; f]`（对应 sim_11 `|H_O|` 口径）。
- `h_C`：关于**系统质心**、惯性系表达（对应 sim_11 `|L_C|` 口径）。
- 外部矢量角冲量 `|ΔH_vec|` 与标量 `|H|` 变化严禁混用（sim_12 B_anchor 教训，引用时必须带口径）。

## 代码绑定

实现于 `src/dh_v1/frames.py` / `spatial.py`；S00 以正负测试同时验证"约定成立"与"违反可检出"。
