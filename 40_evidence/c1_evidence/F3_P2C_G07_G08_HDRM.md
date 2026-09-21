# B601 G07/G08 接触面冻结与 HDRM 功能包络设计

**文档编号：** `F3-P2C-G07-G08-HDRM-20260805`
**生成 UTC：** 2026-08-05
**状态：** `FROZEN_FOR_F3_P3`
**前置：** F3-P2B 基座适配器与载荷桥制造级深化

---

## 1. G07 主鞍座接触面冻结

### 1.1 接触面定义

基于 STOW FK + HIFI 几何，G07 主鞍座接触面冻结如下：

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| **接触中心 X** | [-20, 0] mm | `o13_saddle_stations.json` | FROZEN |
| **接触高 z** | 261.08 mm | `o13_saddle_stations.json` | FROZEN |
| **塔高** | 147.93 mm | `o13_saddle_stations.json` | FROZEN |
| **Y 范围** | [-71.33, 77.70] mm | `o13_saddle_stations.json` | FROZEN |
| **接触 link** | link6（腕部） | STOW FK | FROZEN |
| **承载方向** | Tz（竖向主承托）+ Tx（轴向挡块）+ Rx（防扭） | F3-P2A | FROZEN |

### 1.2 接触面结构

```
        link6 (腕部)
           │
           ▼
    ┌─────────────┐
    │  导入斜面     │  ← 15° 导向锥面
    │  (Guide Cone) │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  柔性接触垫   │  ← 材料 TBD，厚度 3 mm
    │ (Contact Pad) │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  横向止挡     │  ← 横向限位块
    │(Lateral Stop) │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  轴向止挡     │  ← 轴向挡块
    │ (Axial Stop)  │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  预紧件       │  ← 预紧弹簧
    │ (Preload)     │
    └─────────────┘
```

### 1.3 接触面参数

| 特征 | 候选值 | 状态 |
|---|---|---|
| 导入斜面角度 | 15° | `DESIGN_PROPOSAL` |
| 接触垫厚度 | 3 mm | `DESIGN_PROPOSAL` |
| 接触垫材料 | TBD（待 HAG-A 物理分支） | `UNKNOWN_BLOCKED` |
| 接触垫刚度 | TBD（待实测） | `UNKNOWN_BLOCKED` |
| 横向止挡间隙 | 2 mm | `DESIGN_PROPOSAL` |
| 轴向止挡间隙 | 1 mm | `DESIGN_PROPOSAL` |
| 预紧力 | 50 N | `DESIGN_PROPOSAL` |
| 预紧弹簧刚度 | 10 N/mm | `DESIGN_PROPOSAL` |

---

## 2. G08 腕部支撑接触面冻结

### 2.1 接触面定义

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| **接触中心 X** | [160, 180] mm | `o13_saddle_stations.json` | FROZEN |
| **接触高 z** | 209.42 mm | `o13_saddle_stations.json` | FROZEN |
| **塔高** | 96.27 mm | `o13_saddle_stations.json` | FROZEN |
| **Y 范围** | [2.99, 80.11] mm | `o13_saddle_stations.json` | FROZEN |
| **接触 link** | gripper_link（末端） | STOW FK | FROZEN |
| **承载方向** | Ry（防摆） | F3-P2A | FROZEN |

### 2.2 接触面结构

```
      gripper_link (末端)
           │
           ▼
    ┌─────────────┐
    │  导入斜面     │  ← 15° 导向锥面
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  柔性接触垫   │  ← 材料 TBD，厚度 2 mm
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  主止挡       │  ← Primary Stop
    │(Primary Stop) │
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  备用止挡     │  ← Secondary Stop
    │(Secondary Stop)│
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  预紧弹簧     │  ← Preload Spring
    │(Preload Spring)│
    └─────────────┘
           │
           ▼
    ┌─────────────┐
    │  阻尼元件     │  ← Damping Element
    │(Damping Element)│
    └─────────────┘
```

### 2.3 接触面参数

| 特征 | 候选值 | 状态 |
|---|---|---|
| 导入斜面角度 | 15° | `DESIGN_PROPOSAL` |
| 接触垫厚度 | 2 mm | `DESIGN_PROPOSAL` |
| 接触垫材料 | TBD（待 HAG-A 物理分支） | `UNKNOWN_BLOCKED` |
| 主止挡间隙 | 1 mm | `DESIGN_PROPOSAL` |
| 备用止挡间隙 | 2 mm | `DESIGN_PROPOSAL` |
| 预紧弹簧刚度 | 5 N/mm | `DESIGN_PROPOSAL` |
| 阻尼系数 | TBD（待选型） | `UNKNOWN_BLOCKED` |

---

## 3. Mid 鞍座取舍决策

### 3.1 当前状态

| 参数 | 值 | 来源 |
|---|---|---|
| **接触中心 X** | [80, 100] mm | `o13_saddle_stations.json` |
| **接触高 z** | 214.92 mm | `o13_saddle_stations.json` |
| **塔高** | 101.77 mm | `o13_saddle_stations.json` |
| **Y 范围** | [7.72, 87.87] mm | `o13_saddle_stations.json` |

### 3.2 取舍判据

Mid 鞍座是否保留，必须由以下分析决定：

1. **反力分析：** 六分量单位载荷下，G07/G08 是否已能承担所有约束
2. **模态分析：** 有无 Mid 鞍座对第一阶模态频率的影响
3. **刚度分析：** Mid 鞍座是否显著提高整体刚度
4. **质量分析：** Mid 鞍座的质量代价是否值得

**决策：** `PENDING_FEA_ANALYSIS`

---

## 4. HDRM 功能包络设计

### 4.1 HDRM 功能定义

HDRM（Hold-down and Release Mechanism）提供预紧和释放功能，**不承担所有横向定位**。

### 4.2 HDRM 状态机

```
LOCKED
   │
   ▼ (预紧力建立)
PRELOADED
   │
   ▼ (释放指令)
RELEASE_COMMANDED
   │
   ▼ (释放确认)
RELEASE_CONFIRMED
   │
   ▼ (臂抬离)
ARM_CLEAR
```

**故障状态：**
- `RELEASE_FAILED` — 释放失败
- `PARTIAL_RELEASE` — 部分释放

### 4.3 HDRM 功能包络

| 组件 | 功能 | 候选值 | 状态 |
|---|---|---|---|
| **Latch** | 锁紧机构 | 机械锁销 | `DESIGN_PROPOSAL` |
| **Release Actuator** | 释放作动器 | 功能包络（非飞行型号） | `DESIGN_PROPOSAL` |
| **Preload Spring** | 预紧弹簧 | 刚度 10 N/mm | `DESIGN_PROPOSAL` |
| **Status Sensor** | 状态传感器 | 到位开关 + 释放开关 | `DESIGN_PROPOSAL` |
| **Mechanical Stop** | 机械止挡 | 硬止挡 | `DESIGN_PROPOSAL` |

### 4.4 HDRM 关键参数

| 参数 | 候选值 | 状态 |
|---|---|---|
| 预紧力 | 50 N | `DESIGN_PROPOSAL` |
| 释放行程 | 5 mm | `DESIGN_PROPOSAL` |
| 释放时间 | < 1 s | `DESIGN_PROPOSAL` |
| 到位检测 | 机械开关 | `DESIGN_PROPOSAL` |
| 释放确认 | 机械开关 | `DESIGN_PROPOSAL` |
| 失效安全 | 机械止挡 | `DESIGN_PROPOSAL` |

### 4.5 HDRM 残留包络

释放后所有 HDRM 残留件必须**退出运动包络**：
- Latch 必须完全收回
- Release Actuator 必须完全退出臂运动路径
- Preload Spring 必须完全释放
- 任何残留突出件必须 < 2 mm

---

## 5. 释放初始抬离检查

### 5.1 释放顺序

```
HDRM 释放
   │
   ▼
臂抬离 G08（Fwd）
   │
   ▼
臂抬离 G07（Aft）
   │
   ▼
臂完全脱离鞍座
```

### 5.2 抬离间隙

| 阶段 | 最小间隙 | 状态 |
|---|---|---|
| 初始抬离（HDRM 释放后） | 10 mm | `DESIGN_PROPOSAL` |
| G08 脱离后 | 20 mm | `DESIGN_PROPOSAL` |
| G07 脱离后 | 40 mm | `DESIGN_PROPOSAL` |
| 完全脱离 | > 50 mm | `DESIGN_PROPOSAL` |

### 5.3 失效安全间隙

若 HDRM 释放失败，臂必须保持安全间隙：
- 最小间隙：5 mm
- 最大允许干涉：0 mm（不允许）

---

## 6. 未消解 HOLD

1. **接触垫材料** — TBD，待 HAG-A 物理分支
2. **接触垫刚度** — TBD，待实测
3. **阻尼系数** — TBD，待选型
4. **HDRM 具体型号** — 功能包络，非飞行型号
5. **Mid 鞍座取舍** — PENDING_FEA_ANALYSIS
6. **发射载荷谱** — 未定义，无法做强度/刚度校核
7. **收拢态 Z 上限** — UNKNOWN，臂顶 z=359.02 高出整星盒顶 245.87 mm

---

## 7. 禁止声明

- 不得在没有反力和模态分析的情况下保留 Mid 鞍座
- 不得将 HDRM 作为所有横向定位的唯一来源
- 不得在没有释放净空包络验证的情况下冻结接触面
- 不得在没有失效安全间隙验证的情况下宣称释放安全
- 不得使用视觉模型或案例推断接触垫材料、刚度、阻尼系数
