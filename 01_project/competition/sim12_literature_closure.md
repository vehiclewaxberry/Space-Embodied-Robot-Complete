# sim_12 文献闭环：接触冲量 / 捕获-消旋策略对比 / 动量补偿 / 策略选择

> 日期：2026-07-18
> 目的：补齐《文献缺口审计_20260718.md》§6 第 1 项——此前因用量限制未跑完的
> **contact-impulse 专线**，并对 sim_12 四条主题线做一次闭环检索。
> SIM12 定位：**冻结执行器预算下跨策略类（被动 / 速度匹配 / 动量预置 / 捕获后消旋）
> 捕获可行域对比**；核心发现：**速度匹配使接触冲量 J −43%，但系统需管理的角动量
> H +24%**（J–H 权衡）。
>
> **覆盖度声明（科学诚实）**：本文基于 2026-07-18 十轮 WebSearch 定向检索（四主题
> + 元数据核实），共筛得 14 篇。存在性结论均为"**本次检索范围内未见**"级别，
> 非穷尽证明；与 59 篇附录（`文献缺口审计_附录_59papers_20260718.json`）有部分
> 重叠（Virgili-Llop 2019、Giordano 2020、arXiv 2512.09213），此处按 sim_12
> 口径重新标注。

---

## A. 接触冲量 / 碰撞动量传递（contact-impulse 专线，5 篇）

### A1. Impact analysis and post-impact motion control issues of a free-floating space robot subject to a force impulse
- **Year/Journal**: 1999，IEEE Transactions on Robotics and Automation, 15(3): 548–557（Nenchev & Yoshida）
- **Method**: 手端受力冲量下自由漂浮空间机器人的冲击动力学解析；关节空间正交分解 + 反作用零空间（reaction null space），给出冲量→关节/基座速度突变的映射。
- **Compared strategy**: 冲击前构型选择（冲击最小化构型）vs 冲击后 RNS 控制（把角动量从基座转移到臂）。
- **Limitation**: 单点瞬时冲量模型（接触时长为零）；非冗余臂特例；不含执行器容量约束，也不含柔性附件。
- **Relation to SIM12**: sim_06/sim_12 冲量记账的理论源头。SIM12 的 J 指标即该冲量映射的标量化；但该文只管"冲量怎么分"，不管"冲量+动量两本账在冻结预算下哪本先爆"——后者是 SIM12 空位。
- **URL**: https://ieeexplore.ieee.org/document/768186/

### A2. Dynamics, control and impedance matching for robotic capture of a non-cooperative satellite
- **Year/Journal**: 2004，Advanced Robotics, 18(2): 175–198（Yoshida, Nakanishi, Ueno, Inaba, Nishimaki, Oda）
- **Method**: 定义"阻抗匹配虚质量"（Virtual-mass for Impedance Matching）刻画手端阻抗对目标接触后运动的影响；双机械臂地面运动模拟器实验，阻抗控制探针插入目标喷管锥完成捕获。
- **Compared strategy**: 阻抗匹配 vs 失配（欠阻抗把目标推走 / 过阻抗产生翻滚）两种接触后果。
- **Limitation**: 刚体二体接触；只优化接触界面动力学（J 侧），不记系统动量账（H 侧）；无柔性帆板。
- **Relation to SIM12**: "降 J"路线的奠基。SIM12 的发现恰是其盲区：把接触做软（速度/阻抗匹配）付出的动量代价（H +24%）在该路线中从未出现。
- **URL**: https://tohoku.elsevierpure.com/en/publications/dynamics-control-and-impedance-matching-for-robotic-capture-of-a-

### A3. On the capture of tumbling satellite by a space robot
- **Year/Journal**: 2006，IEEE/RSJ IROS（Yoshida, Dimitrov, Nakanishi）
- **Method**: 翻滚目标捕获全流程控制序列：接近段偏置动量（bias momentum）+ 冲击段阻抗控制 + 冲击后分布式动量控制（distributed momentum control）。
- **Compared strategy**: 三种手段按阶段**固定串联**（bias→impedance→DMC），非按条件选择。
- **Limitation**: 序列是设计者预先固定的，不随目标参数/预算绑定情况切换；无可行域概念；无容量约束量化。
- **Relation to SIM12**: 文献里最接近"多策略组合"的先例，但它回答"怎么串"，SIM12 回答"给定冻结预算，哪一类策略在哪片参数区间可行、由哪条约束封边"——层级不同，可引作策略类存在性证据。
- **URL**: https://ieeexplore.ieee.org/document/4059057/

### A4. Contact dynamics and control of a space robot capturing a tumbling object
- **Year/Journal**: 2018，Acta Astronautica, 151: 532–542（Wu, Mou, Liu）
- **Method**: 真实接触几何下抓取翻滚目标的连续接触动力学（含滑移、卡阻等多点持续接触行为）与抓取控制。
- **Compared strategy**: 冲量-动量类瞬时模型 vs 连续接触模型两种建模路线（明确指出前者不适用于多点持续接触抓取）。
- **Limitation**: 计算代价高，不适合千格级可行域扫描；未上升到策略类对比或预算约束。
- **Relation to SIM12**: 给 SIM12 冲量式记账划定**适用边界**——当抓取进入持续多点接触区，J 的冲量近似失效。与 sim_11 G4 修复方向（方案 B 有物理依据的接触带宽/柔顺性）同一条线：SIM12 网格用冲量模型先行，边界格须做接触带宽敏感性说明。
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0094576517319288

### A5. Impact modeling and reactionless control for post-capturing and maneuvering of orbiting objects using a multi-arm space robot
- **Year/Journal**: 2021，Acta Astronautica, 182: 21–36（Raina, Gora, Maheshwari, Shah）
- **Method**: DeNOC 多体建模 + 闭环约束；接近/冲击/冲击后三阶段统一用冲量-动量法与动量守恒建模；冲击后无反作用（reactionless）控制最小化基座扰动，含未知参数自适应版本。
- **Compared strategy**: 单臂 vs 多臂捕获的冲击与基座扰动对比；reactionless vs 常规控制。
- **Limitation**: 无执行器预算/可行域框架；reactionless 依赖运动学冗余，不解决系统总动量归宿（H 仍在系统里）。
- **Relation to SIM12**: 冲量记账在多臂场景的方法学近亲，验证"三阶段全用冲量-动量法"在工程上成立；其"动量只能重分配不能消灭"的结论正是 SIM12 动量记账 Gate（§5.2 裁决）的文献佐证。
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S009457652100045X

---

## B. 捕获-消旋策略对比（5 篇）

### B1. Review and comparison of active space debris capturing and removal methods
- **Year/Journal**: 2016，Progress in Aerospace Sciences, 80: 18–32（Shan, Guo, Gill；700+ 引用，ESI 高被引）
- **Method**: 主动碎片移除方法系统综述与多准则定性对比：刚性连接类（机械臂/触手）vs 柔性连接类（飞网/系绳/鱼叉）。
- **Compared strategy**: 这是корpus 内唯一明确以"**跨方法族对比**"为题的文献，但对比维度是任务级定性打分（成熟度/风险/适用目标）。
- **Limitation**: 定性、任务层；无动力学预算量化，无可行域，无"给定同一执行器配置哪族可行"的判据。
- **Relation to SIM12**: 直接佐证 SIM12 空位——"对比"传统上停留在方法族定性层，**冻结预算下的定量可行域对比无人做**；引言引用它来定义"对比"一词的现有高度。
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0376042115300221

### B2. Simultaneous Capture and Detumble of a Resident Space Object by a Free-Flying Spacecraft-Manipulator System
- **Year/Journal**: 2019，Frontiers in Robotics and AI, 6:14（Virgili-Llop & Romano）
- **Method**: 把捕获（末端位置+速度终端约束）与消旋（追踪星动量终端约束→捕获后系统零角动量）合并为凸优化可行性问题，含避碰与执行器限幅；HIL 气浮台验证。
- **Compared strategy**: "同时捕获+消旋"单策略类内的可行 vs 不可行（回答"轨迹是否存在"，不设计轨迹）。
- **Limitation**: 单策略类；不做跨策略类对比；预算作为约束出现但不做容量扫描；刚体模型。
- **Relation to SIM12**: SIM12 可行域思想的方法学锚点（C 类奠基，缺口审计 §5 已定为必引）；SIM12 的推广是：同一冻结预算下把**四个策略类**放进同一张可行域图并标出各自的绑定约束。其 HIL 结果可作边界图上的已验证点。
- **URL**: https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2019.00014/full

### B3. Optimal control of a space manipulator for detumbling of a target satellite
- **Year/Journal**: 2009，IEEE ICRA（Aghili）
- **Method**: 捕获前：末端与目标抓点**同速到达会合点**（速度匹配作为硬约束）的最优轨迹；捕获后：力矩限幅下最短时间消旋（Pontryagin 闭式解，最优力矩反平行于瞬时角动量）。
- **Compared strategy**: 捕获前速度匹配 vs 捕获后消旋两阶段各自最优化（分开处理，不互相记账）。
- **Limitation**: 速度匹配机动本身的**动量代价不入账**——追踪星为匹配翻滚目标末速所吸收的动量去哪了、占执行器容量多少，全文不问；两阶段割裂。
- **Relation to SIM12**: 速度匹配（S2）策略类的经典实现。SIM12 核心发现（J −43% 但 H +24%）正是给这条经典路线补上被略去的另一半账本：匹配得越好，捕获后要吞的动量越多。
- **URL**: https://ieeexplore.ieee.org/document/5152235/

### B4. Capture and detumbling control for active debris removal by a dual-arm space robot
- **Year/Journal**: 2022，Chinese Journal of Aeronautics, 35(9): 342–353
- **Method**: 无专用抓点、参数未知的非合作目标：柔顺夹持控制 + 自适应反步预定轨迹跟踪（PTTC）消旋。
- **Compared strategy**: 先消旋后移除 vs 直接移除——给出**单一定量预算收益数**：消旋可省推进剂最多 24.11%。
- **Limitation**: 单策略路线内的收益量化；无跨策略类可行域；轮组容量约束不出现；数字是特定场景仿真值。
- **Relation to SIM12**: 精神上最接近 SIM12 的"用百分数说话"（其 24.11% 省推进剂 vs 我们的 J −43% / H +24%），可作对比叙事的参照系；差异在 SIM12 把百分数放到整张冻结预算可行域上而非单场景。
- **URL**: https://www.sciencedirect.com/science/article/pii/S1000936121003708

### B5. Space Debris Reliable Capturing by a Dual-Arm Orbital Robot: Detumbling and Caging
- **Year/Journal**: 2024，IEEE 会议论文（IEEE Xplore 10687710）；预印本 arXiv:2405.00943
- **Method**: 双臂轨道机器人两阶段策略：反复冲击式（repeated impact-based）消旋衰减目标转速，再几何笼捕（caging）约束目标。
- **Compared strategy**: 直接笼捕 vs 先消旋再笼捕——明确论证**高转速下直接笼捕会失败或损毁硬件，须先消旋**。
- **Limitation**: 策略次序判据是定性的硬件生存性门槛（"转速高就先消旋"），非预算绑定判据；无可行域图；双臂特定构型。
- **Relation to SIM12**: корpus 内**最接近"条件依赖的策略选择"**的先例，但其切换条件是定性阈值。SIM12 把这类阈值升级为可行域上的绑定约束边界（哪条约束先饱和决定选哪类策略），二者可在相关工作里直接对话。
- **URL**: https://arxiv.org/abs/2405.00943

---

## C. 动量补偿 / 轮组预置（3 篇）

### C1. Momentum distribution in a space manipulator for facilitating the post-impact control
- **Year/Journal**: 2004，IEEE/RSJ IROS（Dimitrov & Yoshida）
- **Method**: **偏置动量预加载**：接触前在追踪星系统内预置动量（bias momentum approach），使冲击后系统总动量落在便于分布式动量控制处理的分布上；关注捕获前/中/后基座姿态。
- **Compared strategy**: 有预置 vs 无预置的冲击后基座扰动与可控性对比。
- **Limitation**: **默认所需偏置量可实现**——不问轮组容量够不够；平面/低维算例；无"预置量-改善量"的定量权衡曲线，更无可行域。
- **Relation to SIM12**: S3a（轮组预偏置）策略类的直系祖先。SIM12 的增量正是补上它缺的容量约束：sim_08 已证轮组容量仅为需求的 8%（0.3 vs 3.65 N·m·s），"8% 预置换多少可行域边界改善"是该文 22 年后仍未回答的定量问题。
- **URL**: https://ieeexplore.ieee.org/document/1389933/ （PDF: https://astro.mech.tohoku.ac.jp/~yoshida/paperlist/IROS04-1958.pdf ）

### C2. Coordination of thrusters, reaction wheels, and arm in orbital robots
- **Year/Journal**: 2020，Robotics and Autonomous Systems, 131: 103564（Giordano, Dietrich, Ott, Albu-Schäffer，DLR）
- **Method**: 推力器/反作用轮/机械臂三类执行器的省燃料协同控制：无接触机动时理想零燃耗（轮+臂承担），接触后自动激活推力器稳定惯性运动。
- **Compared strategy**: 执行器**层内分配**策略对比（谁出力、何时切换），非捕获策略类对比。
- **Limitation**: 缺口审计 §2 已裁定：这是"部分覆盖"——协同分配做了，但冻结预算下跨策略类的可行域对比与选择判据没有；也不输出目标参数空间上的可行/不可行划分。
- **Relation to SIM12**: SIM12 与之拉开差距的基准线之一：它回答"三类执行器怎么配合"，SIM12 回答"配合到顶也不够时，换哪类捕获策略、边界在哪"。
- **URL**: https://www.sciencedirect.com/science/article/abs/pii/S0921889020304048 （开放 PDF: https://elib.dlr.de/137974/ ）

### C3. MPC for momentum counter-balanced and zero-impulse contact with a free-spinning satellite
- **Year/Journal**: 2025（2025-12-10 提交，AIAA SciTech 2026 投稿），arXiv:2512.09213（Karampela, Seshadri, Dörfler, Li）
- **Method**: 非线性 MPC 协调服务星两个独立执行模块（动量生成模块 + 操作模块），显式建模跨耦合动力学，实现对自旋目标的**零冲量接触**，可施加执行与状态约束。
- **Compared strategy**: 动量反配平 MPC vs 不能处理该约束的既有控制方法（控制律层对比）。
- **Limitation**: 单策略（S3 动量预置类）的控制律实现；无目标质量×转速网格上的可行域；无跨策略类对比；预算不冻结（约束可行即用）。
- **Relation to SIM12**: 缺口审计 §5 已定的相邻线：引作 **S3 策略类的实现存在性证据**；SIM12 的规避即差异——我们不做控制律，做容量约束下的策略类对比与可行域漂移（含 8% 预置定量上限）。
- **URL**: https://arxiv.org/abs/2512.09213

---

## D. 综述 / 任务级策略选择（1 篇）

### D1. Robotic Manipulation and Capture in Space: A Survey
- **Year/Journal**: 2021，Frontiers in Robotics and AI, 8: 686723（Papadopoulos, Aghili, Ma, Lampariello）
- **Method**: 空间操作与捕获全链条综述：接近/捕获/捕获后阶段划分，各阶段方法目录（含冲击最小化、消旋、动量管理各支线）。
- **Compared strategy**: 分类学层面罗列各策略支线，**不给选择判据**。
- **Limitation**: 综述确认各策略类是**互相独立的文献群**——没有任何小节回答"给定执行器预算与目标参数如何在策略类之间选"。
- **Relation to SIM12**: 作为"策略类各自成篇、选择判据缺位"的权威佐证；SIM12 引言可用它铺垫"对比与选择"空位。
- **URL**: https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2021.686723/full

---

## E. 存在性结论：有没有人做过 "binding-gate dependent strategy selection"？

**结论：本次检索范围内未见。**（十轮检索、四主题、含 "active/binding constraint + strategy
selection"、"go/no-go / abort criteria + wheel saturation" 等定向查询，均无直接命中。）

最近邻及其与 SIM12 的距离，按接近程度排序：

| 最近邻 | 它做到哪 | 距离 SIM12 还差什么 |
|---|---|---|
| B5 双臂消旋+笼捕（2024） | 定性切换规则："转速高→先消旋再笼捕"（硬件生存性门槛） | 阈值非预算绑定判据；无可行域图；不问哪条预算约束先饱和 |
| B2 Virgili-Llop & Romano 2019 | 单策略类的可行性判定（轨迹存在性 + 执行限幅约束） | 单策略类；不在多策略类之间比，更不按绑定约束选 |
| C2 Giordano 2020 | 执行器层内协同分配（谁出力、何时切换） | 分配≠策略类选择；无目标参数空间可行/不可行划分 |
| A3 Yoshida 2006 | 多手段固定串联序列（bias→impedance→DMC） | 序列预先固定，不随绑定情况切换 |
| C3 Karampela 2025 | 单策略类内把动量/执行约束显式进 MPC | 约束在控制律内消化，不驱动策略类切换 |

**这正是 SIM12 核心发现的价值所在**：J −43% / H +24% 意味着**绑定约束会翻面**——
冲量受限区（结构/接触载荷封边）速度匹配占优，动量容量受限区（轮组 8% 容量封边）
速度匹配反而恶化可行性。单策略文献各自只看见自己那半张图，所以 22 年
（Dimitrov 2004 → 今）没人画出"绑定门限决定策略选择"的整图。
写论文时该结论表述为"检索корpus 内未见"，并按缺口审计 §6 要求找 2 名独立核查。

---

## F. 与《文献缺口审计_20260718.md》的衔接

- ✅ **§6 第 1 项闭环**：contact-impulse 专线已补（A1–A5，含 finite contact duration
  适用边界一条：A4 直接支撑 sim_11 方案 B 接触带宽的文献依据）。
- ✅ 附录 59 篇之外新增且此前缺失的关键条目：A1（1999 冲量映射奠基）、A2（2004
  阻抗匹配）、A4（2018 连续接触对冲量模型的否证边界）、B3（2009 速度匹配经典）、
  B4（2022 消旋收益 24.11%）、B5（2024 条件依赖策略次序最近邻）、C1（2004 动量
  预置直系祖先）。
- ⬜ 仍未闭环（保持开放）：§6 第 2 项 "capturability" GNC 同名概念排查；§6 第 3 项
  两个存在性结论各找 2 名独立核查。

---

## G. 2026-08-23 查新补充（claim 边界收紧）

> 裁决全文见 `01_project/competition/文献查新裁决_claim边界_20260823.md`。
> 本文件 E 节存在性结论（"binding-gate dependent strategy selection 未见"）**维持不变**，
> 检索截止为 2026-07-18；08-23 补检索后结论不变，引用时须附检索截止与范围声明。

1. **C 线升级**：momentum feedforward compensation 已有 2026 年双臂地面实验论文
   （Wang et al., Acta Astronautica 245:1035–1054, 2026）——S3a 的 baseline 强度从
   C1（Dimitrov 2004 理论）推进到 2026 实验实现。该文为 candidate trajectory →
   predict base reaction → feedforward compensation 闭环，仍无 binding-gate
   strategy selection 与可行域裁决。S3a 定位不变：候选策略类，不作创新。
2. **新增强近邻**：Lu et al. 2026（AST 177:112197）完成 structure–contact–mission
   全阶段虚拟验证（cone complementarity 非光滑接触 + 多时间尺度积分），
   "首次综合动力学框架"类声称从此禁用；SIM12 的 feasibility/decision 层与其互补。
3. **控制层拥挤确认**：Ma 2026（Sci Rep, vision+RL, 纯仿真）、Cai 2026（Astrodynamics,
   DSE-TRMPC post-capture）、Mao 2026（FITEE, Koopman/model-free FFSR 控制）——
   post-capture 控制与 learned control 均定为工具层/baseline，不作创新。
