# V2 Mechanical Interface Control Document

> `STATUS: PRE_CAD_ICD_BASELINED`  
> `PHYSICAL_QUALIFICATION: NOT_STARTED`  
> `CAD_AUTHORING: NOT_AUTHORIZED`

## 1. 目的与约定

本 ICD 定义 V2.0 一级机械接口的身份、frame、已知几何、未知物理字段和禁止外推。完整机器登记见 [V2_interface_register.yaml](./V2_interface_register.yaml)。

坐标统一使用 `T_XY`：表示 frame `Y` 在 frame `X` 中的位姿。机械臂安装使用 `T_SM`；`T_SB` 只表示服务星几何 frame `S` 到自由漂浮动力学基座 `B`，当前未知。

## 2. 接口总表

| ID | parent → child | frame | 已绑定 | 未闭合 | 当前用途 |
|---|---|---|---|---|---|
| IF-RM-001 | bus task face → robot mount adapter | `S/M` | `T_SM`、160 mm flange、adapter plate/boss identity | bolt/locator/tolerance/load/stiffness/material | skeleton 和 mount 结构提案 |
| IF-RM-002 | adapter → B601 base | `M/A0` | `T_MA0=identity`、accepted B601 topology | physical stack-up/tolerance/fasteners | B601 插入和身份保持 |
| IF-SA-L/R | bus → left/right solar interface | `S/F_L/F_R` | root frame nominal locations | hinge/release/lock/harness/stowed state/load | root/hinge reference 与 keepout |
| IF-PL-001 | front mission module → perception payload | `S/T_SC future` | reserved task-face area | hardware/mount/FOV/calibration/mass | zero-solid volume/interface reserve |
| IF-EE-001 | B601 end → capture tool/contact | `G/E_virtual/TCP` | gripper identity、`E_virtual` | physical TCP/contact/F/T/compliance | semantic reserve only |
| IF-AV-001 | primary structure → avionics/EPS/ADCS | `S` | middle-bay owner | equipment dimensions/mount/thermal/connectors | volume owner 与未来 mount plane |
| IF-SV-001 | primary structure → rear service systems | `S` | rear-bay owner | propulsion/comm/thermal hardware | volume owner 与 keepout owner |
| IF-MA-001 | primary/secondary structure → service access | `S` | panel roles | latches/fasteners/tool clearance/sequence | maintenance direction proposal |
| IF-TG-001 | servicer → target | `T_ST/T_SD future` | independent scene rule | target pose/contact/rigid lock | `EXCLUDED` |

## 3. Robot Mount Interface

### 3.1 已绑定几何

```text
T_SM:
  t = [185.25, 0, 0] mm in S
  R = R_y(+90 deg)

servicer flange reference:
  160 × 160 × 15 mm

adapter reference:
  plate = 160 × 160 × 12 mm
  boss = D100 × 15 mm

T_MA0:
  identity design contract
```

这些数据只绑定当前 `COMPETITION_DISPLAY_V0`。A4-B1 已验证视觉装配中的 `T_SM`，但未资格化真实连接、叠层公差或承载性能。

### 3.2 必须保持未知

| 字段 | 值 | owner |
|---|---|---|
| bolt pattern | null | Mechanical Interface Owner |
| locating pins/features | null | Mechanical Interface Owner |
| fastener type/grade/preload | null | Structural Design Owner |
| fit/tolerance/flatness | null | Manufacturing Owner |
| force `F_M` / moment `M_M` | null | Loads & Dynamics Owner |
| stiffness/strength/modal target | null | Structural Verification Owner |
| material/surface treatment | null | Materials/Manufacturing Owner |
| thermal/electrical bonding | null | Thermal/Electrical Owner |

### 3.3 反力链要求

未来 CAD 必须能画出并审查：

```text
B601/A0
  → M interface
  → adapter plate + boss
  → local reinforcement proposal
  → front task-face load-spreading frame
  → longitudinal members / transverse ring
  → bus primary structure
```

该链存在只代表拓扑完整，不代表强度、刚度或载荷通过。

## 4. Solar Array Interface

当前名义 root frames：

```text
F_L origin in S = [-56.75, +113.15, 0] mm
F_R origin in S = [-56.75, -113.15, 0] mm
```

允许建立 root plane、hinge-axis candidate、stowed/deployed/safe-display 状态槽和 swept keepout owner。

保持未知：

- hinge geometry and axis qualification；
- release/lock/drive；
- harness bend and strain relief；
- stowed envelope；
- deployment loads；
- flight deployment sequence。

## 5. Payload / Perception Interface

前任务面只保留：

- sensor mount reserve；
- optical-axis candidate frame；
- cable/data/power passage owner；
- robot/solar occlusion review owner。

不得建立：

- 真实相机、镜头、FOV 数字；
- `T_SC` 数值；
- 标定、分辨率、检测距离；
- 有效 BOM、质量或感知能力声明。

## 6. Avionics / EPS / ADCS Interface

中舱必须为 OBC/C&DH、EPS/PMAD、电池、reaction-wheel/IMU 分配互不重叠的 volume owner。每个 owner 后续需要 mount plane、service direction、harness entry、thermal interface 和 mass owner；当前未绑定硬件时全部保留 null。

## 7. Rear Service Interface

后舱必须分离：

- propulsion reserved zone；
- communication reserved zone；
- thermal/radiator reserved zone；
- debug/ground service interface。

推进 plume、天线扫掠和散热表面只建立 keepout owner，不建立硬件或性能。

## 8. Service Access Interface

未来 CAD 必须能审查：

- 外板拆卸方向；
- 设备托盘抽取方向；
- robot mount 工具访问；
- 线束/连接器接近；
- 不穿越机械臂、太阳翼和 rail/tab reference 的装配顺序。

没有明确 clearance、紧固和工具数据时，只能称 `SERVICEABILITY_PROPOSAL`。

## 9. 接口停止条件

出现以下任一项立即停止：

- 用 `T_SB` 替代 `T_SM`；
- 无来源添加孔位、螺栓、材料或载荷；
- 由 CAD 默认质量覆盖 mass owner registry；
- physical TCP、target contact 或相机硬件进入 active assembly；
- 太阳翼静态位置被称为部署验证；
- 反力链图被称为强度或刚度验证。
