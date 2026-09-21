# Paper 1 文献战略分析（审稿人视角）— 2026-07-17

> 方法：5 簇并行网络检索（捕获冲量/消旋与动量管理/非合作服务任务/学习型与具身智能/抓取规划与可行域），
> 61 篇去重真实论文（1993–2026，全部带出处，见 `tables/paper01_literature_scan.csv`），
> 每条裁决注明依据。诚实纪律：撞车即明示，创新措辞用 "to the best of our knowledge"。

## Part 1 领域发展时间线

| 年代 | 里程碑 |
|---|---|
| 1993 | Wee & Walker (T-RA)：接触冲量写成构型相关标量"冲击度量"，构型优化最小化冲击 |
| 1999 | Nenchev & Yoshida (T-RA)：反作用零空间(RNS)冲击分析与后冲击控制 |
| 2004 | **Dimitrov & Yoshida (IROS)：捕获前后角动量分配+偏置动量——"捕获前后一体化考虑动量"概念基石** |
| 2010–14 | Liou (2010) 环境侧 ADR 目标排序（质量×碰撞概率）；Flores-Abad (PAS 2014) 四阶段综述框架固化；Flores-Abad (JGCD 2014) 最优捕获时机/位姿最小化基座扰动 |
| 2016–18 | 黄攀峰系"组合体姿态接管"主线成形 (AST 2016→2025 Elsevier 专著)；e.Deorbit 工程化（Envisat 5°/s 设计上限+176 N·m 关节力矩，逐例蒙特卡洛验证）；Sternberg & Miller 同步接近轨迹 |
| 2019 | **Virgili-Llop & Romano (Frontiers)：唯一系统报告"捕获-消旋可行性随目标角动量衰减"（特定组合 <7°/s），但单一质量比、理想抓取、逐例蒙特卡洛** |
| 2021–22 | 未知惯量消旋成熟（Gangapersaud ASR、Dou ASR）；Raina (Acta Astro 2021) DeNOC 多臂冲量-动量高保真建模；西工大 MSD 2022 任务相容度选抓捕构型 |
| 2022–25 | 学习型进入接触段：气浮台 DRL 捕获制导 (JGCD 2022)、触觉 DRL 软捕获 (CASE 2024)、深度视觉+伪谱 (JSR 2025)；ClearSpace-1 因 VESPA 被撞自旋加剧**换目标**（自旋超界=任务死亡的工程实证） |
| 2024 | **Aghili (arXiv:2402.01959)：自旋匹配无缝捕获+轮组阻尼——承认执行器容量约束但只给单例存在性证明** |
| 2025–26 | 耦合利用范式（Das arXiv:2508.15732 SVD 耦合度量）；零冲量 MPC（Karampela）；RL 消旋 AARD (Acta Astro 2026)；**SpaceMind (arXiv:2604.14399)：MCP 工具+具身 VLM agent，但工具不含动力学、任务止于接近巡检** |

## Part 2 方法分类（A/B/C/D）

- **A 纯捕获**（怎么抓住）：冲击最小化谱系（Wee-Walker→零冲量 MPC）、同步/自旋匹配接近（Sternberg 2018、Aghili 2024、Li AST 2026）、软捕获凸优化（Sow iSpaRo 2024 SOCP）。**共同局限：把捕获当终点，隐含"同步⇒安全"，不问抓完之后**。
- **B 捕获+消旋**（抓完怎么办）：偏置动量（D-Y 2004）、最短时间消旋轨迹（Zong AST 2021）、未知惯量鲁棒/辨识消旋（ASR 2019/2022）、接管控制专著（黄攀峰系）。**局限：全部"先捕获、后应对"，执行器容量只作控制器内约束，从不前馈为捕获前判据**。
- **C 动量管理**（容量视角）：轮组饱和补偿（Lee IJASS 2026）、动量卸载。**局限：容量与任务筛选层无桥接**。
- **D 学习型**（数据视角）：DRL 制导（气浮台验证 JGCD 2022）、触觉软捕获、RL 消旋 AARD、meta-RL 学 CBF 参数（2026）、LLM/VLM agent（LLMSat、KSP、SpaceMind）。**局限：可行性一律隐式化为训练成功率；无一给出参数化不可行边界；LLM-agent 均无物理校验层（作者自陈需要约束）**。

## Part 3 论文清单

61 篇去重清单（Title/Authors/Year/Venue/IF估计/Problem/Method/Limitation/URL）：
`tables/paper01_literature_scan.csv`。其中核心 30 篇 = 时间线加粗项 + 各簇 gap 裁决依据文献。

## Part 4 三个研究空白裁决

**问1：是否存在 "capture feasibility boundary under mass ratio and angular momentum constraints"？**
**裁决：未发现直接先例。** 最接近三篇及差异：
① Virgili-Llop & Romano 2019（唯一系统"可行性 vs 角动量"报告）——单一质量比、无参数化边界、理想抓取无接触冲量；
② Aghili 2024（承认 RW 力矩/末端力矩上限决定可行性的最直接表述）——单例存在性证明，无 (μ,h*,容量) 地图；
③ Sow 2024（可行性=SOCP 可解性）——逐轨迹非任务级。
补强证据：ADR 目标筛选文献（Liou 2010→McKnight 2021→Fuzzy TOPSIS 2021→debris index 2025）**全部为环境侧准则，零动力学可捕获性**；工程侧只有点值阈值（e.Deorbit ≤5°/s、ESA CAT-IOD ≤1°/s、MEV 仅三轴稳定），ClearSpace-1 用"换目标"回避翻滚——**"值不值得移"与"抓不抓得住"之间存在方法学断层**。术语空位：文献中 "capture feasibility envelope" 几乎只有运动学含义（可达域/capability map，Porges 2015），动力学任务可行域地图是可占领的命名空间。

**问2：是否有人提出 "post-capture stabilizability-aware grasp planning"？**
**裁决：无同名先例，但存在必须引用并划界的近亲。**
① **西工大 Xu/Luo/Wang (MSD 2022, DOI:10.1007/s11044-022-09835-y)**：最接近——"基于任务相容度选抓捕构型以快速稳定翻滚目标"，但指标是雅可比层面力/速度相容椭球（运动静力学代理），**不建组合体冲量/动量模型、无执行器容量、无 fail-closed**；
② Flores-Abad (JGCD 2014)：最优捕获时机选择，评价停在接触瞬间运动学量；
③ Das 2025 (arXiv:2508.15732)：耦合 SVD 度量，作用于轨迹层、不含冲击相、非抓取点级。
**"可操作度并列时杠杆选点使 ω⁺ 减半（几何最优≠系统最优）"的分歧案例与 M_PCS+fail-closed 语义均未发现对应先例。**

**问3：是否有人结合 ANCF + spacecraft capture + embodied intelligence？**
**裁决：确认无人同时结合三者。** 各占两角的最近工作：SpaceMind（agent+服务，全刚体、无物理工具）；Wang (Actuators 2025, 14(7):358)（ANCF+捕获，绳网非机械臂、无学习）；Liu/Liu/Cai (JAS 2022)（柔性+消旋控制、无智能体）。→ 该三结合留给 Paper 3；Paper 1 只引用以界定展望。

## Part 5 三条创新点（含诚实说明）

**C1 面向任务判定的六维塑性捕获冲量模型与简化式误差量化**
- 最近先例：Dimitrov-Yoshida 2004（动量分配，平面验证）、Raina 2021（DeNOC 高保真但服务于控制律）、Zhang 2022（"综合等效质量"标量式=被批判对象）。
- 差异：谱系把冲量当"要压小的量/控制初条件"；**无人将含 Steiner+质心迁移+r×mv 完整模型用于抓取候选系统性 ω⁺ 评估，也无人量化标量简化式误差（本项目 −2.9%~−12.3%）**。模型保真度对比仅存在于绳系域（Aleksander Aerospace 2022），机械臂域空缺。
- 诚实说明：模型本身的力学并非新（教科书级动量守恒）；**新颖性在"任务级接入+误差量化+可行性判定用途"，措辞须限定于此**。

**C2 质量比-角动量-执行机构容量约束下的捕获-消旋任务可行域（无量纲地图）**
- 最近先例：Virgili-Llop & Romano 2019（单质量比逐例）、Aghili 2024（单例存在性）、工程点值阈值（5°/s、1°/s）。
- 差异：**existence proof vs. feasibility boundary**——本项目证明给定 μ=6.25+2°/s 预算下含速度匹配同步捕获的整族策略系统性不可行（216 例无 SAFE），并将其推广为 (μ, ω̂, h*, j*) 无量纲地图（sim10）。对 Sternberg/Aghili "同步⇒安全" 隐含假设的定量反驳（质心不重合时 Steiner+r×mv 不为零）是高辨识度论点。
- 诚实说明：**必须显式引用 Aghili 并以"存在性证明 vs 边界刻画"框架区分，否则审稿人会判撞车**；可行域结论限定于冻结 PROVISIONAL 阈值+当前候选空间。

**C3 抓取后可稳定性感知的候选评价与 fail-closed 决策框架（M_PCS）**
- 最近先例：西工大 MSD 2022（任务相容度选构型）、Flores-Abad 2014、Das 2025。
- 差异：评价量从运动学/静力学代理升级为**捕获后系统级量（ω⁺、轮组容量、推进剂、柔性激励）**；提供"几何最优≠系统最优"分歧实例；fail-closed 三态语义（无 SAFE 即中止而非硬选 Top-3）在全部候选评价文献中未出现。
- 诚实说明：M_PCS 是项目定义指标（min-margin 形式本身平凡），**卖点是"评价对象错位"的发现与证据纪律，不宣称指标公式创新**；须与 MSD 2022 逐条划界。

**必须正面对话的文献清单（Related Work 强制引用）**：Dimitrov & Yoshida 2004；Virgili-Llop & Romano 2019；Aghili arXiv:2402.01959；Xu/Luo/Wang MSD 2022；Flores-Abad JGCD 2014 + PAS 2014 综述；Das arXiv:2508.15732；Sternberg & Miller 2018；SpaceMind（仅展望）；Papadopoulos 2021 综述与 Fallahiarezoodar & Zhu 2025 综述（gap statement 权威出处）；Jaekel 2018 / Estable 2020（e.Deorbit 工程锚点）；McKnight 2021 / Liou 2010（环境侧断层证据）。

**可引用的真实自旋数据锚点**：Envisat 实测 ~3°/s；LEO 废弃物均值 ~2°/s、观测高至 20°/s；极端 BREEZE-M 409.6°/s；ADRAS-J 目标呈重力梯度稳定低速——把 2°/s 预算与 3°/s 案例锚定到真实任务谱。

## 结论

三条创新在 61 篇核查后**全部成立但均需收窄措辞**：C1 收窄为"任务级接入+误差量化"，C2 必须与 Aghili 划界为"边界刻画"，C3 必须与西工大 MSD 2022 划界为"捕获后系统级量+fail-closed"。论文引言按"环境准则筛选→（空白：动力学可行性）→GNC 执行"三段式定位。学习型断裂处（捕获前制导已验证、捕获后消旋刚起步、**捕获瞬间物理与任务级判据双缺**）即本文位置。
