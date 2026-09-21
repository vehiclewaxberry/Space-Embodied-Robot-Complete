# 11 须 Owner/外部完成事项（OWNER_ACTIONS_REQUIRED）

- 生成日期：2026-08-27；生成者：综合代理 SYN-C。以下事项审计代理与综合代理均无权完成（只读铁律/授权边界），须 Owner 或外部方执行；每项给触发证据、最晚期限与未闭合后果。

| # | 事项 | 触发证据 | 最晚期限 | 未闭合后果 |
|---|---|---|---|---|
| 1 | **下载 2026 正式参赛指南+模板并回填 04 矩阵**：取得官方指南/报名系统字段/报告模板，登记入 `01_project/inbox/source_manifest.csv`（现仅 2 行协作者输入，sha256 `7d1d733eb792`），回填 04 要求矩阵 | B-CD01（P0）：2026 官方文件仓内零命中；唯一格式描述在归档文件 `01_project/competition/archive/项目现状总览_20260715.md` 第 11 行（`e65cf431ba00`），被 `AGENTS.md` 第 14 行禁作现行依据（`3d2269562678`）；决策问题 17/18 均 UNKNOWN | **2026-08-28** | fail-closed 条件 12 维持 TRIGGERED；COMPETITION_SUBMISSION 降 NO_GO |
| 2 | **确认技术类是否强制实物并定展示方案**：若强制实物→须处理与 `B601_MOTION=PROHIBITED`（`10_research/competition_convergence/competition_gate_check.json` `$.hardware_component_status`，`8b3cdbdaa09e`）的直接冲突；**若无实物→冻结「operational baseline 结构图+动画」替代展示方案**（资产基础：07-20 mp4/pptx 与六图） | 同 #1；能力侧证据：H0/H1/H2 NOT_STARTED、`stop_rules.start_hil=false`（`8b3cdbdaa09e`）；`10_research/on_orbit_assembly/approvals/` 目录不存在（embodied fragment 2026-08-27 核实） | **2026-08-28** | 展架/照片/实物分支无法规划（B-CD06 悬置） |
| 3 | **GitHub 仓库 public/forks 与敏感资产人工处置**：人工登录核对仓库可见性、fork 列表、协作者权限；如确认公开且有 forks，作书面裁决（改私有/清理敏感资产/评估已泄露面） | B-CD04（P0）：`git remote -v` 空、`.git/config` 无 `[remote]` 节，继承包「要求 Private 但元数据 public 且有 forks」声明仓内不可定位原文，离线不可验证（compdeliv fragment §C.2） | **2026-08-29** | fail-closed 条件 13 维持 TRIGGERED：仓库公开/外链/镜像分支冻结；合规风险悬置 |
| 4 | **PENDING_OWNER_REVIEW / PENDING_REVIEW Gate 人工复核决定**（审计代理不得重发）：至少包括 00_RELEASE_GATE（`review_status=PENDING_OWNER_REVIEW`，`14d30fd40ac6`）、SIM13 20/20 后端包（`4a813f2ee3b0`）、e23 18/18（`1ad4993fd9df`）、SAFE-00（`ff56929dd835` 第 9 行 PENDING_REVIEW）、CTRL-02（`240fa708b536` 第 1078 行） | 各 gate JSON `review_status` 字段；复核权在 Owner，机器无权自审自批 | **2026-08-30**（或明示延期登记） | 相关证据在材料中继续带 PENDING 限定语；正式 Release 维持 HOLD（不阻 9-01 提交） |
| 5 | **标题收窄决定签收**：签收或修改 `13_TITLE_AND_CLAIM_CEILING.md` 推荐标题（当前 PENDING_OWNER_SIGNOFF）；同步冻结唯一科学主问题表述（BLK-MEM-03 三版本择一）与禁用词表 | BLK-MEM-01（P0）：候选标题仓内业务文档零命中（grep 仅 fragments 命中）；「具身智能/自主抓取/数字孪生/在轨装配」四词证据不足（`PROJECT_CURRENT_STATUS.md` EMBODIED_AI 行，`cce6517b4cd5`；framework 矩阵 C21/C23-C29，`7d296e7a2437`） | **2026-08-27 当日**（最迟 8-28 晨） | 报告/PPT/展架无法定稿；CONDITIONAL_GO 条件 3 不闭合 |
| 6 | **Route-C P01–P13 外部实物参数决定延期**：确认 P08/P10/P11 null、MPI-01..04、C5/C6 供应商输入（RFI/试验）全部延期至赛后；赛后按受控值升级并复审 | BLK-MECH-01..04：`ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml`（`1e70d6f95141`）无 MEASURED/AS_BUILT 值；V9F 已被 M01 负见证终局否决（`09c3199bd982`/`09611ddb8adc`） | **赛前登记延期，赛后执行** | 维持 KNOWN HOLD 叙事；禁止赛前任何 Route-C 闭合动作（伪闭合即审计事故） |
| 7 | **杨恒三项待办排赛后**：帆板面密度占位（0.348 kg SSOT vs 真实 2-5 kg/m²，`AGENTS.md` 待办 3，`3d2269562678`）、T_c 夹爪闭合实测（`scene_A2_capture.yaml` 第 25 行 20 ms 占位，`4b979a1dfd18`）、数值案例（替换 `coupled_model_v0.yaml` 占位，`67a532fb29c7`）——全部排赛后，赛前材料引用一律带 PROVISIONAL 声明 | DYN-B01/DYN-B02（P1）；`AGENTS.md` 待办 1-3（第 54-56 行） | **赛后**（赛前仅作 PROVISIONAL 标注） | sim_11 柔性耦合结论在真实参数下可能翻转的风险保持披露；决赛答辩须能复述该边界 |

## 附：审计/综合代理侧承诺

- 以上事项的触发证据均来自只读审计，未做任何 git 写操作、未重发任何 Gate、未改源码/CAD/仿真。
- 凡标「最晚期限」为赛前的事项，对应 CONDITIONAL_GO 解除条件（`09_COMPETITION_DECISION_MEMO.md` §c）；8-31 终核时逐项核证。
