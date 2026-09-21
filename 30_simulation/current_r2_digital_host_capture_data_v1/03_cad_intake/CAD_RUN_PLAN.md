# 有界 CAD run 计划（授权后执行；当前 FROZEN）

前置条件（全部满足才启动，见 `CAD_RUN_AUTHORIZATION_INTAKE.yaml` admission_predicate）：
命名授权 PRESENT + 内存 ≥6 GiB（或 run-bound override）+ 保护输入 SHA 全验 + 会话独占 + 输出目录空/版本化。

## 执行链（当前权威：FreeCAD/OCP/build123d 源只读生成器）

1. 校验 `CAD_PROTECTED_INPUTS.csv` 全部 SHA（失配即中止，不打开任何 CAD 文档）。
2. **第一步固定为 D01**：执行已就绪的 `D01_R2_SOLAR_B601_FIXED_Q0_DIAGNOSTIC` 配方
   （预期 403 leaf solids / 3 groups），输出 `D01_R2_SOLAR_B601_FIXED_Q0_DIAGNOSTIC_V1.step`。
   D01 是固定 q0 诊断几何，**永不**成为 joint/limit/mass authority。
3. 逐状态 C01→C09（每个状态一个封闭事务）：
   打开权威装配 → 解析状态（joint 向量/帆板/HDRM/夹爪/目标出席，按 `04_step_states/CURRENT_STATE_REGISTER.csv`）
   → 重建 → 检查未解析引用（有则该状态记 FAIL 并继续下一状态）
   → 保存到隔离候选目录 `04_step_states/CXX/` → STEP-first 导出
   → **冷重开** STEP → 提取单位/包围盒/体数量 → 前视、侧视、顶视、等轴四视图 PNG
   → SHA-256 + 字节数入 `CURRENT_STEP_MANIFEST.json` → 正常关闭。
4. 全部状态完成后：`FOUR_VIEW_MANIFEST.csv` 汇总、冷校验一轮（重新哈希全部输出）、正常退出进程。
5. 输出合同见 `CAD_OUTPUT_CONTRACT.yaml`；任何一步失败只冻结该状态，不回滚已完成状态，不触碰保护输入。

## 明确边界

- 阻塞状态照实登记：C08/C09 缺 T_E_T/接触权威 → 该两状态 STEP 只能以"无目标附着"的
  服务星本体几何生成并标 `TARGET_ABSENT_ATTACHMENT_NOT_EVALUATED`，禁止摆放目标。
- SolidWorks 路线为终局 Gate A external_only_hold；如 Owner 改令 SolidWorks 会话，另行签发计划修订。
- 本计划不含任何 pair/edge/path 碰撞评价——那属于 DH-G3/G4，需 collision assets 与 M01 证书链。
