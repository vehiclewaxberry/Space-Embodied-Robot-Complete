# V2 Subsystem Packaging Preliminary Review

> `STATUS: INSTALLATION_LOGIC_DEFINED_HARDWARE_ENVELOPES_OPEN`  
> `PACKAGING_METHOD: OWNER_FIRST`  
> `REAL_HARDWARE_SELECTED: false`

## 1. Packaging principle

PDR 不用通用方块冒充设备选型，而是为每个子系统建立：

```text
bay owner
  -> future mount-plane owner
  -> service-direction owner
  -> harness-entry owner
  -> thermal/keepout owner
  -> mass owner
```

具体 envelope、坐标、连接和质量缺失时保持 null。

## 2. Front Mission Module

### Bound object

`VOL-FM-ROBOT` 由 task-face `M/A0` 中央接口驱动，是 front bay 的第一优先结构对象。其 adapter envelope 已有来源，但局部加强、线束穿越和工具区仍是 proposal/unknown。

### Reserved objects

`VOL-FM-SENSOR` 只保留：

- perception owner；
- future mount-plane owner；
- cable passage owner；
- occlusion review owner。

PDR 不分配相机外观、位置、FOV、质量或标定。其未来位置必须服从：

1. 不改变 `T_SM`；
2. 不进入 robot primary load path；
3. 不遮挡任务面/机械臂评审视图；
4. 不与 front access proposal 发生未经记录的冲突。

## 3. Middle Avionics/EPS/ADCS Bay

四个独立 owner：

- `VOL-MID-OBC`
- `VOL-MID-EPS`
- `VOL-MID-BAT`
- `VOL-MID-ADCS`

PDR 安装逻辑：

- 共享 bay boundary reference，但不能共享质量 owner；
- 每个对象必须有独立未来 mount plane；
- 电池只能登记为 future balance owner，不能在未知质量下宣称完成配平；
- ADCS 位置不能被机械外观推断为控制可行；
- EPS/OBC/ADCS 的线束入口必须连接到 longitudinal corridor owner；
- 托盘抽取方向在真实连接器和工具约束给出前保持 null。

## 4. Rear Service Module

四个独立 owner：

- `VOL-REAR-PROP`
- `VOL-REAR-COMM`
- `VOL-REAR-THERMAL`
- `VOL-REAR-SERVICE`

PDR 安装逻辑：

- propulsion 只保留 volume/plume owner，不建立 tank、valve 或 thruster；
- communications 保留 antenna/RF keepout owner，不建立天线机构；
- thermal 保留 rejection-surface owner，不给 radiator area；
- service owner 位于 rear-access responsibility chain，用于 debug、ground service 和 harness breakout；
- rear panel `-X_S` 拆卸方向仍是 proposal。

## 5. Side Deployables

`VOL-SIDE-SOLAR-L/R` 只消费 `F_L/F_R` 根 frame 和已封存 deployed reference。stowed envelope、hinge、release、lock、drive、harness 和 loads 不得由 PDR补齐。

## 6. Corridor and conflict logic

建立一个非实体 `LONGITUDINAL_HARNESS_CORRIDOR_OWNER`：

```text
rear service breakout
  -> rear bay branches
  -> middle OBC/EPS/battery/ADCS branches
  -> front robot/sensor branches
```

走廊横截面、具体路径、弯曲半径、power/data/RF 分离、接地和热/EMC 全部为空。未来 B3 可以显示 reference path，不可切除结构或声称线束闭合。

## 7. Packaging review checks

| 检查 | PDR 结果 |
|---|---|
| 三舱 owner 清晰 | `PASS` |
| 12 个 volume owner 身份保留 | `PASS` |
| owner 重叠被默许 | `NO` |
| 具体硬件或质量被虚构 | `NO` |
| mount plane 全部物理闭合 | `NO / BLOCKED` |
| service direction 全部闭合 | `NO / BLOCKED` |
| thermal/harness/EMC 闭合 | `NO / BLOCKED` |
| target 进入 active assembly | `NO` |

## 8. B3 handoff

B3 应先建立 bay boundary 和 owner overlay，再由未来真实硬件输入替换 reservation。任何 placeholder 都必须携带 `NO_MASS_AUTHORITY=true`、`NO_DYNAMICS_USE=true` 和 source/state 属性。
