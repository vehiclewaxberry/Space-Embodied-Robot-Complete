# SOLIDWORKS-NATIVE-MECHANICAL-REALIZATION-01 第一阶段报告（A–F）

日期：2026-07-27（UTC）　唯一写区：`20_engineering/cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/`
纠偏依据：用户裁决 2026-07-27——VENDOR-CAD-03 封存为 B601 几何来源与工程 HOLD 记录；
主线改为**可由 SolidWorks 2024 直接打开、编辑、配置、重建的原生机械装配**。
Python 图/STEP/JSON **不替代** .SLDPRT/.SLDASM，仅作辅助证据。

## 1. 交付的原生模型

顶层：`Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM`（7 个顶层组件）

```
Space_Embodied_Service_Spacecraft_V2_2.SLDASM
├── 00_Master_Skeleton_V2_2.SLDPRT            18 基准面 + 3D 包络草图 + 34 参数属性（零实体）
├── 01_Primary_Structure_V2_2.SLDASM          (7)
│   ├── Front_End_Frame / Rear_End_Frame      环框（4×17×17 横梁，纵梁间端接）
│   ├── Front_Transverse_Frame                X 119..125
│   ├── Mid_Transverse_Frame_1 / _2           X ±(58..64)
│   ├── Longerons_4X.SLDPRT                   4 根 17×17，角点 ±101.65，X -183..183
│   └── Equipment_Decks.SLDASM (3)            前/中/后舱甲板 z -40..-36
├── Removable_Panels.SLDASM (6)               ±Y 前后分缝 ×4 + ±Z ×2，3mm，外表面齐平 113.15
├── 02_B601_Mount_and_Load_Path.SLDASM (8)    扩散板→前端框→法兰→160×160×12 适配板→Ø110 导向凸台
│                                             + 双载荷桥 + 线束通道 + 内维修盖
├── 04_ARM_STOW_SUPPORT.SLDASM (5)            上臂/前臂/腕鞍座（接触高 234.77/248.49/253.80 实测）
│                                             + 发射锁参考 + 释放净空包络
├── 05_Solar_Array_Root_Left.SLDASM (9)       SC 侧支座 + 前后铰链耳（带 Ø8.4 销孔）+ 销包络
└── 06_Solar_Array_Root_Right.SLDASM (9)      + 翼板侧叶片 + 机械止挡 + HDRM 座 + 释放机构包络
                                              + 线束服务环
```

零件 47 个、装配 8 个、断链 0、重复装入 0。每个零件带
`ROLE / STATUS / OWNER / PARENT_ASSEMBLY / GEOMETRY_AUTHORITY / MASS_AUTHORITY /
STRENGTH_AUTHORITY / BLOCKED_CONSUMERS` 自定义属性。

## 2. 配置（9 个，冷启动重开后读回验证）

正式 7：`STOWED / DEPLOYED_NOMINAL / DEPLOY_FAILED_BOTH / L_FAIL / R_FAIL /
PARTIAL_DEPLOYMENT / MAINTENANCE`
工程比较 2：`STOW_VENDOR_25DEG_PROPOSAL / STOW_NO_CLOCK_COMPARATOR`

抑制矩阵：`MAINTENANCE` → 抑制 `Removable_Panels`（开盖态）；
`STOW_NO_CLOCK_COMPARATOR` → 抑制 `04_ARM_STOW_SUPPORT`（该族鞍座尚未设计）。
其余配置全解析。**L_FAIL / R_FAIL / PARTIAL_DEPLOYMENT 在第一阶段几何等同**——
翼板本体不在 A–F 范围内，如实登记，不伪造差异。

## 3. 本轮抓出并修复的四类真实缺陷

| 编号 | 缺陷 | 发现方式 | 处置 |
|---|---|---|---|
| **D-NATIVE-03** | `SetSuppression2` 枚举用反（写成 2=抑制/0=解析，实为 **0=Suppressed、2=FullyResolved**）→ STOWED 把全部组件抑制成**空装配**，MAINTENANCE 只剩外板 | STOWED 配置 STEP 导出仅 **305 字节** | 改为 `0 if want_sup else 2` 并常量化；**此前"0 干涉/配置 PASS"全部作废重测** |
| **D-NATIVE-01** | `Removable_Panels` 被重复装入（01 子装配内一份 + 顶层一份），顶层抑制对嵌套那份无效；重合重复件还把干涉检测骗成 0 | 视图显示 MAINTENANCE 仍有外板 | 外板只保留顶层（子装配子件配置抑制在本机不可持久）；验证器加**重复装入检测** |
| **D-NATIVE-02** | SolidWorks `SaveBMP` 渲染固定内部相机——`ShowNamedView2`(12 种形式)、`IModelView.RotateAboutCenter`、可见/无头切换，图像哈希**逐位不变** | 4 张"不同方位"视图哈希完全相同 | 评审出图改为：原生装配→按配置导出 STEP→OCC 网格化→渲染（含真实剖切） |
| **几何互穿 37 处** | 扩散板 vs 四纵梁、维修盖 vs 前横框、铰链耳/销/支座相互、支座 vs 纵梁、释放包络 vs 鞍座 | 冷启动全树干涉检测（枚举修正后） | 逐条改几何：扩散板缩至 ±93.15、维修盖 X 起点 126、太阳翼根部重新分层（支座 z[-100.15,-93.15] / 耳片 z[-110.15,-100.15] / y≤88 让开纵梁）、耳片与叶片开 Ø8.4 销孔、释放包络下沿抬至 z=256 |

**设计纪律**：所有相邻件只允许**接触共面**，禁止实体重叠；纵梁与环框同截面
17×17、角点 ±101.65，环框横梁在纵梁之间端接。

## 4. 未解决问题（第一阶段不消解）

1. **收拢态 Z 包络仍未定义**：`STOW_Z_LIMIT_REFERENCE=UNKNOWN` 已写入 Master Skeleton
   属性。整星盒顶 z=+113.15，而 25° 提案位形臂顶 z≈361——**合规性无判据可判**。
2. **B601 三表示未建**（任务书第 9 项，不在 A–F 范围）：`B601_STOWED_HIFI.SLDPRT` /
   `B601_Q0_KINEMATIC_PROXY.SLDASM` / `B601_MASS_SURROGATE.SLDPRT` 待第二阶段。
   本阶段安装链按 Ø100 中央接口 + 160×160×12 适配板预留，**未装入任何 B601 实体**。
3. **T_SM 双轨冲突**：用户指令写 `T_SM=[185.25,0,0]`（340.5 动力学轨），与本装配的
   366 显示轨（±183）不自洽——若取 185.25，12mm 适配板会落在 X[173.25,185.25]，
   与前端框（175..183）互穿。本阶段采用显示轨 `MOUNT_FACE_X=198`，冲突全文登记在
   骨架属性 `T_SM_TRACK_CONFLICT`，**待人工裁决**。
4. **铰链销轴站位偏离冻结值**：冻结 `翼根 Y=±110, Z=-105.65` 指**翼板根缘**；销轴若
   置于该处会嵌入纵梁体积。本阶段销轴取 `Y=±76, Z=-105.15`，翼板侧叶片伸臂到 ±110
   的连接段标 `TBD`（翼板本体不在本阶段）。
5. **25° 时钟角未定案**：两个比较配置并存，选择依据（高度/宽度/间隙/鞍座数/解锁路径/
   翼避让/相机遮挡）需在第二阶段用真实 B601 三表示逐项量化后人工裁决。
6. **爆炸视图未创建**：本机组件变换持久性缺陷（V2.2 三次复现），爆炸视图以组件变换
   存储，同型风险；改以 MAINTENANCE 抑制态 + 四分之一剖切表达装配层次。
7. 材料、强度、公差、紧固件、热、FEA、动力学——按任务书全部**未定义/未运行**。

## 5. 验收对照（用户第七节标准）

| 标准 | 结果 |
|---|---|
| 顶层 .SLDASM 可直接打开 | ✅ 冷启动重开通过 |
| 关键结构均为独立 .SLDPRT/.SLDASM | ✅ 47 + 8 |
| 零缺件、零断链 | ✅ broken_links = 0 |
| 主结构不是单一方盒 | ✅ 5 环框 + 4 纵梁 + 3 甲板 + 6 可拆板 |
| 太阳翼根部不是零实体 | ✅ 每侧 9 个实体零件 |
| B601 安装结构与主结构无未裁决互穿 | ⏳ 见 `evidence/phase1_verify.json` 收尾干涉数 |
| 收拢支承是实际 SolidWorks 实体 | ✅ 3 鞍座 + 锁参考 + 净空包络 |
| 配置保存/关闭/重开后保持 | ✅ 冷启动读回矩阵 |
| B601 高保真外观与质量代理分离 | ⏳ 第二阶段（本阶段无 B601 实体） |
| accepted URDF 未改变 | ✅ 字节未动 |
| 每个一级部件有来源/状态/用途属性 | ✅ |
| Python 图只作辅助证据 | ✅ 模型交付=原生文件；PNG 仅评审 |
