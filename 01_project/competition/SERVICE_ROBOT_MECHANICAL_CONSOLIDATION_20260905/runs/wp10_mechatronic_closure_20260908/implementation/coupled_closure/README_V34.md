# WP10 V34 · 电源接口与辅助保护 PCB

2026-09-14。本版完成同版本 ECAD 候选，整星机电设计尚未闭环。

本轮新增 60 × 40 mm 双层辅助保护板：F202 后接 TPS26600，再供给 THN 隔离电源和 STOP 控制。它与主 Q201 开关支路分开，但共用电池；不是冗余电池电源。主输入板承担 LM5069 预充/限流及相关启动接口，本轮把主采样电阻 R202 改为 0.5 mΩ，总采样电阻 2.5 mΩ。负载侧回生吸收仍在既有独立设计链中，不由这块辅助板吸收电机制动能量。

已完成 14 页整机 ERC（0 错误、0 警告），主板 43 个电气封装及辅助板 11 个电气封装分别 DRC 0 违规、0 未连接。辅助板另有 4 个非电气安装孔、9 个 RTN 散热过孔、与主回流隔离的背面铜区。电气位号由 211 增至 222，针脚网络由 677 增至 714；原位号仅 U202.1 网络和 R202 规格变化。原 873 组件父本、99 位号谱系及 37 行闭环表保持。

96 个保存工况完成独立 KCL/KVL/功率/器件分项热量核对；7 个旧字段/NaN/热量错分负控被检测。RTN–GND 短接副本触发 4 条原生 DRC 违规，活动板未改变。忽略项逐条见 VERIFICATION.json：ERC 4 类，DRC 5 类。上述检查不是所有规则、所有板或硬件性能的合格证。

主限流条件范围约 18.99–25.14 A，辅助约 2.103–2.358 A；限流平台相加约 27.504 A，仅在所列器件参数迁移条件下成立，不能作为瞬态 30 A 上界。360 W 机械臂筛查需求未降低。32 个配对工况仍为 16 个 UVLO 阻断、13 个条件保持、3 个角点相关。

384 个主启动端点场景中，192 冷态 UVLO 关闭、16 在预充期间 UVLO、176 退出限流区。15.531 ms 是完成子集的最差调节时间；28.2 ms 定时器最小值扣除 1.5 倍项目分配后余 4.904 ms。模型假设辅助保护已经导通，不是联合冷启动证明。THN 在 8/9 V 开始吸取满辅助恒功率时仍有负的充电电流余量反例。

新增铜阻按原生走线长度/宽度、35 µm 铜、100°C、20 µm 过孔镀铜假设分项计入；不视作实测阻抗。Molex 配套壳体 430250200、端子 430300007 已选为候选，20 AWG、绝缘外径须≤1.85 mm；线材具体料号、裁线长度和压接过程仍待整机布置绑定。依 PS-43045 Rev R，四个配对接点和四个压接点采用初始合计 0.060 Ω，以及规定应力试验变化量转移后的 0.140 Ω 场景。不得把这些表格条件扩展成空间环境保证。

为什么继续复用成熟方案：B601 DM 的结构、电机及软件沿用开源项目；卫星低功耗电源/背板参考 OreSat 与 P60。本项目新增的仅是现有模块之间的高功率保护和停止接口。GomSpace PDU-200 公布单通道 2 A，与本项目保留的 24 V/15 A 筛查工况不匹配；OreSat 的 1U–3U、7.2 V 电池卡也不能不经重设计就移植为本机高功率系统。GITAI S1 的 ISS 舱内机械臂演示可以参考任务与验证方法，其公开页面不是本项目 12U 自由漂浮整机的完整制造设计。

原厂/项目依据：
- [B601 开源项目](https://github.com/Seeed-Projects/reBot-DevArm/blob/main/README.md)
- [GomSpace P60 PDU-200](https://gomspace.com/UserFiles/Subsystems/datasheet/gs-ds-nanopower-p60-pdu200-26.pdf)
- [OreSat 子系统](https://www.oresat.org/technologies/cubesat-subsystems)
- [GITAI S1 ISS 演示](https://gitai.tech/2021/10/28/iss-tech-demo-ja/)
- [TI TPS2660](https://www.ti.com/lit/ds/symlink/tps2660.pdf)
- [Vishay WSLP2726](https://www.vishay.com/docs/30179/wslp2726.pdf)
- [Molex PS-43045](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf?inline=)

下一项应解决辅助电源/STOP 的联合冷启动与复位，再开展剩余 STOP/回生板布线、热通路及整舱集成。FLT/IMON 本版未接遥测；J210 只是相对于 RTN 的本地短接复位测试点。安装位置、热边界、制动能量和推进受控接口仍开放。未制造、未接电、未驱动实物，未宣布制造或飞行放行。

KiCad 打开 ecad/revisions/v34/wp10_system.kicad_sch 查看整机层次，第 14 页是辅助板。PCB 分别打开 wp10_main_input.kicad_pcb 与 wp10_aux_protection.kicad_pcb；MCP 与 GUI 不是实时同步，重新载入已保存文件后查看。标准 3D 模型依赖本机 KiCad 10 模型库；本次并未生成完整实体或更新整机 CAD。包内 PDF/PNG/CSV 可直接查看，复算使用原工作区及记录的运行时路径。
