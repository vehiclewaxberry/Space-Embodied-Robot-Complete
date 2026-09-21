# V2 Serviceability and Keepout Plan

> `STATUS: PRE_CAD_SERVICEABILITY_PROPOSAL`  
> 本计划定义审查责任和候选方向，不证明真实可达性或无碰撞。

## 1. 外板与维护方向

| 对象 | 候选拆卸方向 | 状态 | B3 必须验证 |
|---|---|---|---|
| front mission access panel | `+X_S` | `DESIGN_PROPOSAL` | 不与 B601/mount/sensor reserve 冲突 |
| rear service panel | `-X_S` | `DESIGN_PROPOSAL` | 可访问 comm/prop/thermal/service owner |
| left side panel | `+Y_S` | `DESIGN_PROPOSAL` | 不侵入 solar root/rail reference |
| right side panel | `-Y_S` | `DESIGN_PROPOSAL` | 不侵入 solar root/rail reference |
| top/bottom access panels | `±Z_S` | `DESIGN_PROPOSAL` | 不穿越结构框、线束或安装件 |
| middle-bay equipment tray | null | `UNKNOWN_BLOCKED` | 根据 volume owner、连接器和主结构选择抽取方向 |

这些方向不包含工具尺寸、紧固方式、手部/机械臂可达性或在轨维护假设。

## 2. 线束与服务通道

当前只定义 owner：

```text
rear service breakout
  → longitudinal internal harness corridor candidate
  → middle avionics/EPS/ADCS branches
  → front mission / robot mount / sensor reserve
```

保持未知：

- corridor cross-section；
- connector type and bend radius；
- separation of power/data/RF；
- strain relief and grounding；
- thermal/EMC constraints；
- moving-joint harness。

## 3. Keepout Owner

| keepout | owner | 当前状态 |
|---|---|---|
| rail/tab and insertion path | Standards/Configuration Owner | `UNKNOWN_BLOCKED` |
| B601 folded/deployed/workspace | Robotics/Geometry Owner | q0 only；global unknown |
| left/right solar swept zone | Deployables Owner | deployed reference only |
| sensor optical/occlusion zone | Perception Owner | `UNKNOWN_BLOCKED` |
| propulsion plume | Propulsion Owner | `UNKNOWN_BLOCKED` |
| antenna sweep/RF field | Communications Owner | `UNKNOWN_BLOCKED` |
| thermal rejection surface | Thermal Owner | `UNKNOWN_BLOCKED` |
| mount tool access | Mechanical Interface Owner | `DESIGN_PROPOSAL` |
| target approach/contact | Mission/Target Owner | `EXCLUDED` |

## 4. 装配顺序候选

```text
Master Skeleton
  → Primary Structure
  → bay decks / mount planes
  → subsystem volume-owner placeholders
  → harness references
  → removable panels
  → Robot Mount Module
  → accepted B601 visual assembly
  → solar interface references
  → review overlays
```

该顺序是 B3 建模/审查顺序，不是制造工艺。

## 5. 验收视图

B3 至少提供：

- 所有外板候选拆卸方向；
- middle-bay tray 抽取方向；
- robot mount 工具访问；
- longitudinal harness corridor；
- solar root 与 side panel 冲突检查；
- named configuration 下的 keepout overlay；
- 无法关闭的访问或干涉作为负结果保留。
