# B2.8 Mechanical PDR Research Execution Plan

> `PLAN_ID: COMP-PROT-03-A4-B2.8-PLAN`  
> `STATUS: EXECUTED_WITHIN_USER_APPROVED_PDR_SCOPE`  
> `CAD_EXECUTION: false`

## 1. Engineering question

如何在不猜测材料、载荷、板厚、连接、物性和硬件选型的前提下，把 B2.5 的需求、ICD、volume owner、mass owner、frame 和 unknown register 推导成一套可供 B3 参数化 CAD 直接消费、且可审计回退的系统机械初步设计？

## 2. Engineering proposition

若所有 V2 对象均由 Master Skeleton、唯一 interface owner、唯一 mass owner 和显式 evidence state 驱动，并把未知物理量保持为 null，则可以形成一套“可开始受控 CAD、但不冒充物理资格”的 PDR 输出。

这是待评审的工程组织命题，不是新的科学结论。

## 3. Controlled relations

本阶段只使用以下符号关系：

```text
T_SA0 = T_SM · T_MA0
T_MA0 = identity contract
w_M = [Fx, Fy, Fz, Mx, My, Mz]^T
```

其中 `T_SM` 来自既有 SSOT；`w_M` 六个数值全部为 null，等待 loads owner。不得计算结构响应。

## 4. Inputs

- `20_engineering/design_inputs/v2_system_mechanical/`
- A4-B2 architecture packet
- frame SSOT、geometry/profile SSOT
- accepted B601 10-link/9-joint URDF
- A4-B1 V1.0 evidence seal
- CAD Reference Pattern Library
- 已记录的十处 `DEPLOYED_REFERENCE_Q0` 静态干涉负结果

## 5. Outputs

- 系统机械 PDR；
- 主结构和概念载荷路径方案；
- 十个机械接口的 PDR 就绪矩阵；
- 三舱安装逻辑和 serviceability 方案；
- robot mount 六维载荷接口合同；
- Master Skeleton 构造规范和 SolidWorks 建模标准；
- CAD—frame—mass—URDF—simulation 数字线程合同；
- 柔性结构候选登记；
- 三轮 Engineering Loop 评审与 PDR 退出 Gate。

## 6. Tests

1. 所有 YAML 可解析；
2. 所有相对 Markdown 链接可解析；
3. interface ID 与 B2.5 的十项登记一一对应；
4. mass owner 不重复、unknown mass 不进入总量；
5. `T_SM`、`T_MA0`、`T_SB` 语义不漂移；
6. 17 个上游 unknown 均未被默认值关闭；
7. target、physical TCP、contact、selected hardware 仍不进入 active CAD；
8. A4-B2、B2.5、V1.0、B601 URDF 哈希复核；
9. geometry、simulation、evidence、URDF tracked/staged diff 为零；
10. V2 SolidWorks 根目录不存在。

## 7. Acceptance gate

只有在 PDR 文件齐全、机器测试通过、负结果保留且没有越权 CAD/物理值时，才能输出：

`COMP-PROT-03-A4-B2.8-PDR-COMPLETE`

该状态只允许申请 B3 人工批准。

## 8. Rollback plan

本阶段只新增 `20_engineering/design_review/` 下的文档、YAML 和 CSV。若输入完整性或冻结边界失败，停止生成退出 Gate；回滚对象仅限本次新目录，不触碰 B2.5、V1.0、A3、URDF、Gate、仿真或证据。
