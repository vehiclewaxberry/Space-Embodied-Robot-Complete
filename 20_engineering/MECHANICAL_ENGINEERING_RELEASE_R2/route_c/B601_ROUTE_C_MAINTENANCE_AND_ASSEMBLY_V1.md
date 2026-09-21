# B601 Route-C Guided Dress Pack V1 — 装配与维护（DESIGN_CANDIDATE）

状态：`DESIGN_CANDIDATE / PENDING_OWNER_REVIEW / next_stage_authorized=false / release_credit=false`。
本文件描述 Route-C 分段导向 dress-pack 候选的装配顺序、检修接口与维护约束。
所有尺寸为设计候选值；权威参数见 `ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml` 与
`B601_ROUTE_C_HARNESS_CENTERLINE_V1.json`。

## 1. 架构与分段

Bus Feedthrough → J1 Protected Annular Service Loop → Link-1 Fixed Channel →
J2 Semi-Captive Guided U-Loop → Link-2 Fixed Channel → J3 Mini Cable-Carrier/Moving-Guide
Hybrid → Link-3/4 Fixed Channel → J4–J6 Short Joint-Local Service Loops →
Wrist Strain Relief → Gripper/Sensor Connectors（与 ODR-52 一致）。

每个关节段具备 ODR-52 要求的六要素：固定夹点、运动夹点、自由弯曲段（R≥50 mm）、
防磨导向面（iglidur 衬垫候选 μ 0.06–0.20）、strain relief、检修接口。

## 2. 装配顺序（设计候选，待 RC-4 精确扫掠验证后冻结）

1. **总线穿舱段（S 框）**：先将 RC-BRK-BUS-FLANGE 以 4×M3 固定于穿舱通道口支架；
   线束从 HN-00 连接器板引入，经 RC-CHN-BUS-FT 通道至 HN-02 固定夹+strain relief。
2. **基座环支架**：RC-BRK-BASE-COLLAR 抱箍于 base_link 颈圈（8×M3 于 R45.25 螺栓节圆面，
   不修改 B601 donor 壳体）；安装 CN-BASE-00 连接器板（HN-03）。
3. **J1 环形服务环**：线束沿缓弯上升段（C1/C2/C2B/JV/KP，弯曲半径均 ≥50 mm）上行至 z=126 环形
   通道（下/上颊板+外壁，带入口槽），切向进入并在环内盘绕 1.2 圈（R60，螺旋节距 12 mm）；
   出口经 CM-J1-M 旋转夹点接到 link1。
4. **J2 Ω 环**：线束经 link1 上升至 CF-J2-F 固定夹点，绕 J2 R50 导向芯轴（带衬套）250°，
   由 CM-J2-M 运动夹点落到 link2 通道。
5. **link2 通道与 J3 承载**：线束沿 RC-CHN-L2 通过 CF-L2-01，穿过 J3 移动滑车
   （E2.10 级链节 6 节，行程 ±55 mm，硬限位 x=-85/-195），再经 CF-L2-02 进入 J3 导向鞍。
6. **J3 鞍形导向**：线束绕 R63 鞍面 200°（带衬套），出鞍后上 link3 通道
   （CF-L3-01/02 两个中间夹点）。
7. **J4 Ω 环**：经 CF-J4-F 绕 R50 芯轴 315°，CM-J4-M 落到 link4 通道；通道尽头
   CF-L4-01，沿倾斜通道爬升至 CF-J5-F（wrap 平面 z=210）。
8. **J5 腕部环绕**：绕 R50 环 185°（z=210 平面），CM-J5-M 出环。
9. **J6 螺旋环绕**：绕 link6 轴线 R50 螺旋 1.75 圈（节距 20），4 个导向环支撑；
   CM-J6-F/CM-J6-M 夹点。
10. **腕部分线**：轴向腕段经 CF-WR-SR strain relief（含橡胶护套候选）至
    CF-WR-PL 分线板；数据尾缆 CN-WR-D1、电源/传感尾缆 CN-WR-P1 分接到夹爪/传感器连接器。

力矩与工装：M3 紧固件力矩值未定（owner/工艺输入，HOLD 登记）；装配后电测规程
（绝缘/导通/屏蔽连续性）按 NASA-STD-8739.4 方法规划，接受值为下游 C6 项。

## 3. 检修接口

- **分段可更换**：J2/J4 Ω 环段、J5/J6 腕部环绕段均可通过松开固定/运动夹点整体更换，
  不扰动上游段；J1 环形段揭开上颊板即可检查盘绕状态。
- **连接器分线**：腕部分线板允许夹爪/传感器侧线束独立拆装；基座 HN-03 连接器板允许
  机械臂侧与总线侧分离。
- **滑车维护**：J3 滑车沿导轨滑出（拆硬限位 B）即可更换链节或衬套。
- **衬垫磨损**：所有导向衬垫（J2/J3/J4/J5 衬套、通道衬条、J6 导向环）为易损件，
  设计磨损余量 0.5 mm（1.0e4 循环设计分配，C6 验证项）。

## 4. 维护约束与禁区

- 禁止改变任何夹点/导向件的坐标与弯曲半径（R≥50 mm 为 P06 设计分配下限）；
  任何变更必须回归 RC-4 精确扫掠与任务覆盖验证。
- 禁止在导向段内使用锐边紧固件或外露扎带端头（防磨/防挂，NASA LLIS 687 方法）。
- 禁止修改 accepted URDF 几何、Solar R2、M3R、Gripper R1 或 B601 donor 壳体；
  所有支架只安装在派生支架上。
- J3 滑车硬限位不得拆除或移位；行程 110 mm 为 P04 设计候选，变更需重开 P04/P07 预算。
- 线束更换时必须使用同构造子束（Axon P551259 + 8×TE 55/9960-26 候选构成），
  安装后 OD 估计 9.0 [8.0,10.0] mm；禁止超通道 12 mm 容量。
- 装配后必须进行剩余长度/收放余量检查：总余量（容量 1877.766 − 需求 1333.82 = 543.946 mm，
  以 `B601_ROUTE_C_HARNESS_CENTERLINE_V1.json` 的 take_up_summary 为准）。

## 5. 已知 HOLD（如实登记，不阻塞本阶段）

- 恢复力矩曲线、动态弯折寿命定量数据：供应商试验项（C5/C6），当前为 DESIGN_CANDIDATE 分配。
- e-chain、iglidur、护套的空间环境（TVAC/出气/辐照）适用性证据：C6 项。
- 确切连接器件号/背壳/针脚图（MPI-01..04）：owner 电气权威输入。
- 热膨胀对收放预算的贡献：C4/C5 项。
- 线束阻力矩 vs 执行器预算校核：ODR-50 重开触发守卫项。
