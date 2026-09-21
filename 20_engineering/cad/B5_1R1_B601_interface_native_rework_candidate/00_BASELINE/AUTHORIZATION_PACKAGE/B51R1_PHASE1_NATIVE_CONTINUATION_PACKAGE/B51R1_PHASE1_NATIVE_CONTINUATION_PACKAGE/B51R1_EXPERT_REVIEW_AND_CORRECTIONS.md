# B5.1R1 第一轮实际推进专家复核与修正

日期：2026-07-29

## 1. 复核结论

当前结果总体符合既定 B5.1R1 Phase 1 要求，正确完成了：

- 冻结基线和启动包哈希复核；
- 4 mm / 3 mm 偏差的因果识别；
- Master Skeleton V2 中性几何见证；
- 10-link、6R + 1 fixed + 2P carrier q0 拓扑见证；
- 未把 STEP 见证虚报为原生 SolidWorks 可运动装配；
- 未提前关闭 H10 或运行 T005。

推荐把中间 Gate 的工程解释写成：

`B51R1_PHASE1A_1B_NEUTRAL_WITNESS_PASS_WITH_NATIVE_SOLIDWORKS_AUTHORING_SESSION_HOLD`

而不是把它理解为 G2/G3 已部分通过。

## 2. 必须修正的表述

### 2.1 4 mm

推荐：

> 4 mm 已被识别为陈旧截面/层级基准与当前 canonical 主承力基准之间的偏差；该结果否决“整体平移旧纵梁或旧适配器”的处理方式。

不要写成：

> 4 mm 几何问题已经修复。

### 2.2 3 mm

推荐：

> 当前鞍座候选几何停留在可拆面板层，与真实主承力结构之间仍缺少连续承载接口；3 mm 不能用普通垫片直接跨越并视为载荷路径闭合。

不要在没有厚度测量证据时写成：

> 3 mm 就是面板厚度。

### 2.3 Master Skeleton STEP

推荐：

> 中性 STEP 已证明关键平面、轴线、包络和尺寸的几何构造自洽。

仍不得宣称：

- 原生特征树已经建立；
- 后续零件已经建立耐久外部引用；
- Mode A / Mode B 已裁决；
- Skeleton 已成为 SolidWorks 装配唯一定位母体。

### 2.4 Carrier q0 STEP

推荐：

> 中性 STEP 已证明 10-link / 9-joint 拓扑、q0空间关系和末端分叉的几何构造自洽。

仍需从 accepted URDF逐项记录：

- 精确 joint name；
- parent / child；
- axis；
- origin；
- lower / upper；
- zero；
- sign；
- 是否 mimic 或独立。

`+71.5 mm / -71.5 mm` 只能先作为两条P轴的坐标方向见证，不得直接解释成每条关节的对称总行程或夹爪总开度，除非 accepted URDF 明确支持。

### 2.5 “唯一阻塞”

推荐：

> 当前进入原生 CAD 创作的唯一直接工具链阻塞是 SolidWorks 会话注册失败。

项目级阻塞仍包括：

- H9 未裁决；
- H10 0/28；
- T005-A/B/C NOT_RUN；
- G07/G08/HDRM 未闭合；
- 连续间隙和结构分析未授权。

## 3. 当前 Gate 不应升级的项目

仍保持：

- G0：PASS
- G1：HOLD_HUMAN_DECISION_REQUIRED
- G2：FAIL_GEOMETRY_REDESIGN_REQUIRED
- G3：HOLD_NATIVE_ARTICULATION_NOT_ACCEPTED
- G4：HOLD
- G5/G6：NOT_RUN
- G7：PARTIAL

本轮中性见证只关闭 Phase 1A/1B 的“测量和构造可行性”，不关闭 G2/G3。
