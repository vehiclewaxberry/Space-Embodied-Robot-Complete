# B2.8 Scope, Evidence States and Loop Method

> `STATUS: PRELIMINARY_MECHANICAL_DESIGN_ONLY`  
> `SCIENTIFIC_GATE: false`  
> `SOLIDWORKS_AUTHORITY: false`

## 1. 允许范围

- 对 B2.5 输入进行结构化推导和 PDR；
- 确定结构拓扑、接口责任、安装逻辑、命名和建模顺序；
- 定义六维载荷、质量、frame、URDF 和 simulation 的空值接口；
- 生成未来 CAD 的 reference plane、coordinate system、feature tree 和属性规范；
- 对设计方案做跨文档一致性审查和修正。

## 2. 禁止范围

- 创建、打开改写或保存 V2 SolidWorks；
- 修改 V1.0、A3、accepted B601 URDF、geometry SSOT、Gate、simulation 或 evidence；
- 选择材料、板厚、紧固件、连接、公差、预紧或制造工艺；
- 填写 robot mount、发射、部署或操作载荷数值；
- 计算强度、刚度、模态、热、质量、CoM 或惯量；
- 建立真实传感器、physical TCP、contact、target mate 或推进硬件；
- 运行 FEA、动力学、控制、SAFE、VLA/RL、Isaac/ROS 或硬件。

## 3. Evidence states

| 状态 | 含义 | B2.8 处理 |
|---|---|---|
| `EVIDENCE_BOUND` | 已有 SSOT、hash 或受控文件支持 | 原样继承并给出来源 |
| `DERIVED` | 只由受控几何关系直接推导 | 记录推导式，不升级物理状态 |
| `DESIGN_PROPOSAL` | PDR 候选设计 | 可进入未来 CAD，但必须可抑制/替换 |
| `UNKNOWN_BLOCKED` | 缺少 owner 输入 | 保持 null/disabled/reserved |
| `EXCLUDED` | 当前 active system 不消费 | 不建 mate、contact 或活动引用 |
| `NEGATIVE_RESULT` | 已发现未闭合问题 | 必须保留并在评审视图中可见 |

## 4. Loop Engineering 方法

### Loop 0 — Constraint lock

核对 profile、frame、interface、mass owner、unknown、负结果和冻结哈希；输出不可变输入表。

### Loop 1 — Topology synthesis

建立主结构、反力链、舱段安装逻辑和维护路径；逐项反查是否有需求和 owner。

### Loop 2 — Digital-thread cross review

检查 CAD ID、frame、mass、URDF、simulation placeholder 是否表达同一对象；发现语义漂移立即修正。

### Loop 3 — Red-flag review

搜索默认材料、具体载荷、物理资格、目标接触、硬件选型和“已实现能力”等越界表述；关闭文档问题，保留物理 blocker。

## 5. 变更规则

以下变化使 PDR 立即失效并要求重新评审：

- project profile 或 body envelope 改变；
- `T_SM`、`M/A0` 或 B601 topology 改变；
- B2.5/A4-B2/V1 seal 哈希变化；
- 17 项 unknown 中任一被无来源关闭；
- target、physical TCP、selected sensor/propulsion hardware 被要求进入 active CAD；
- B3 授权文本或范围变化。
