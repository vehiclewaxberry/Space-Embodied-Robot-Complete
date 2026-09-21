# NATIVE-MECH-REAL-01 / Stage 2 执行任务书

## 0. 执行身份与唯一写入边界

- 任务：在隔离版 `Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION` 内关闭一条源基线引用泄漏，并构建 B601 三表示原生 SolidWorks 子系统。
- 本任务的 SolidWorks 唯一写入者必须是 **Claude Code**，与 `phase0_record.json` 的人工裁决一致。
- Codex 与所有 Reviewer 只做工程定义、只读审查和结果复验，不得写入 `.SLDPRT/.SLDASM/.SLDDRW`。
- **唯一允许写入的目录**：
  `20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/`
- 下列目录和文件一律只读，不得保存、重建后保存、改属性、改引用或覆盖：
  - `Space_Embodied_Robot_CAD_V2_0/`
  - `Space_Embodied_Robot_CAD_V2_1/`
  - `Space_Embodied_Robot_CAD_V2_2/`
  - `Space_Embodied_Robot_CAD_V2_2_NATIVE/`
  - accepted URDF 及其 mesh 目录
  - 外部注册供应商 STEP
  - 既有 Gate、历史 evidence 和 frozen manifest
- 不提交 Git，不清理用户现有未提交内容。

## 1. 当前输入和必须保持的裁决

### 1.1 唯一原生基线

- 源基线：
  `Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM`
- 源顶装 SHA-256：
  `30c09b50a0d2967ec1f48050caac34d12a43565c44978d54e3785595202def7a`
- 源角色：`READ_ONLY_ACCEPTED_BASELINE`
- 目标顶装：
  `Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM`
- V2.0/V2.1：`FROZEN_HISTORICAL_BASELINES`
- V2.2：`REFERENCE_DONOR_ONLY`

执行前后都必须重算 `baseline_freeze_manifest.yaml` 所列源文件哈希，结果必须逐项相同。

### 1.2 当前已知隔离缺陷

目标顶装当前有且仅有一条已知引用泄漏：

```text
F:\China Graduate Future Flight Vehicle Innovation Competition\
20_engineering\cad\Space_Embodied_Robot_CAD_V2_2_NATIVE\
01_Primary_Structure\Removable_Panels\Removable_Panels.SLDASM
```

目标内同名副本已存在，且当前 SHA-256 与源副本相同：

```text
Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION\
01_Primary_Structure\Removable_Panels\Removable_Panels.SLDASM
```

必须只在 V2.3 目标顶装内把引用重定向到目标副本。不得通过再次复制整个源树、
重建源顶装或保存源文件来“修复”。

隔离验收：

- 顶装递归组件引用全部位于 V2.3 根；
- 允许的非组件权威输入只可作为自定义属性/证据路径存在，不得成为运行时装配依赖；
- `outside_v23 = []`；
- 关闭文档、退出 SolidWorks、重新启动、重开后仍为 `outside_v23 = []`。

## 2. B601 三表示的源权威合同

### 2.1 Accepted URDF

- 路径：
  `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`
- SHA-256：
  `1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164`
- 角色：
  - 唯一运动学 authority；
  - 唯一 B601 质量、质心与惯量 authority；
  - 不得修改。
- 总质量：
  `4.695555949342986 kg`
- 10 个 link 的质量、惯量和惯性原点必须从 URDF 在执行时解析，禁止手工转录后失去可追踪性。

### 2.2 高保真几何

优先使用已生成并锁定在供应商真实几何收拢位形的只读 STEP：

```text
Space_Embodied_Robot_CAD_V2_2\
130_B601_Vendor_CAD_Direct_Integration_03\
cad\B601_VENDOR_STOW.step
```

- SHA-256：
  `cc8cfdd20865d25832a077ec54d4057386d2dcdf69db4d66917d91e6b1e928ab`
- 字节：
  `252874670`
- 几何来源上游：
  `F:\Robotic arm\High_performance_robotics_arm\vendor\reBot-DevArm\
  hardware\reBot_B601_DM\reBot_B601_DM_v1.1_20260425.step`
- 上游 SHA-256：
  `87a0537d1afd50c04fc441fde11dd4f2ebbb368fe27f6c10fda8567be696d968`
- 许可/流转：
  `CERN-OHL-W-2.0`，但当前项目继续执行
  `LICENSE_CLASS=E3_INTERNAL_RESEARCH_ONLY`、
  `DO_NOT_REDISTRIBUTE=TRUE_UNTIL_URDF_LICENSE_CLARIFIED`。
- 该 STEP 只拥有几何 authority，不拥有运动学、质量、惯量、强度、制造或飞行 authority。

旧 `B601_SWAP01` 的无界面 `LoadFile4` 已发生不返回，禁止以同一无界面路线重复。
本轮必须使用可见 SolidWorks 2024 SP5.0、单 PID 绑定、分阶段保存和可见模态窗口诊断。
如高保真导入仍失败，应留下新的、可区分的失败证据并保持 HIFI 为 HOLD；不得生成假 HIFI。

### 2.3 安装和姿态边界

- `B601_MOUNT_CLOCK_BASELINE = 25 deg`
- 状态：`PROVISIONAL_INTERFACE_BASELINE`
- 唯一允许理由：`joint1 limit margin`
- 禁止声称全局最优、发射合规或收拢包络通过。
- 当前候选关节向量：
  `[145.572, -168.0, -57.0, -41.143, -20.954, -3.0] deg`
- 状态必须保持：
  `STOW_VECTOR_STATUS = CANDIDATE_HOLD`
- 本任务只消费现有 O13 结果，不重新搜索 clock/q，不运行 FEA、动力学、控制、ROS、
  Isaac、RL 或 VLA。
- 收拢态 Z 上限仍为 `UNKNOWN`。
- 鞍座接触资格、垫材料、预紧、HDRM、发射载荷和 B601 壳体承载能力仍为 `HOLD/TBD`。

## 3. 必须构建的原生对象

在 V2.3 内新增：

```text
03_B601_Three_Representations/
  B601_STOWED_HIFI/
  B601_KINEMATIC_PROXY/
  B601_MASS_SURROGATE/
  B601_THREE_REPRESENTATIONS.SLDASM
```

### 3.1 `B601_STOWED_HIFI`

- 原生容器：`SLDPRT` 或自包含 `SLDASM`；
- 必须来自上述已锁定供应商收拢 STEP，不得用方块或 URDF mesh 冒充；
- 允许为导入体/多实体零件，但必须在断开外部链接后自包含；
- 关闭重开后 body/component count、bbox、源哈希属性保持；
- 属性至少包含：
  - `OBJECT_ID=B601_STOWED_HIFI`
  - `REPRESENTATION_LAYER=L2_HIFI_STATIC_GEOMETRY`
  - `GEOMETRY_AUTHORITY=REGISTERED_VENDOR_STEP`
  - `SOURCE_STEP_SHA256=cc8c...28ab`
  - `MASS_AUTHORITY=EXCLUDED`
  - `KINEMATIC_AUTHORITY=NONE`
  - `STOW_VECTOR_STATUS=CANDIDATE_HOLD`
  - `CLOCKING_STATUS=PROVISIONAL_INTERFACE_BASELINE`
  - `LICENSE_CLASS=E3_INTERNAL_RESEARCH_ONLY`
  - `DO_NOT_REDISTRIBUTE=TRUE`
- 不得从该表示读取或汇总 B601 质量。

### 3.2 `B601_KINEMATIC_PROXY`

- 原生 `SLDASM`，10 个可追踪 link 对象；
- 由 accepted URDF 在执行时解析生成；
- link/joint 命名必须可一一追踪回 URDF；
- 关节原点、轴和父子关系均以 URDF 为准；
- 可使用简化原生包络体，但必须标记为
  `CONSERVATIVE_PROXY_NOT_VENDOR_SHELL`；
- 至少保留 `Q0_REFERENCE` 与 `STOW_CANDIDATE_25DEG` 两个配置或等价持久化状态；
- 夹爪 prismatic joint 继续使用 accepted URDF 当前锁定语义；
- 属性：
  - `KINEMATIC_AUTHORITY=ACCEPTED_URDF`
  - `URDF_SHA256=1bc2...c164`
  - `MASS_AUTHORITY=EXCLUDED_IN_THIS_REPRESENTATION`
  - `GEOMETRY_AUTHORITY=PROXY_ONLY`
- 不得把代理几何升级成真实壳体、碰撞通过或工作空间证明。

### 3.3 `B601_MASS_SURROGATE`

- 原生 `SLDASM`，10 个 link 质量对象；
- 每个 link 的质量、质心和完整惯量张量都由 accepted URDF 解析；
- 使用 SolidWorks 持久化质量属性覆盖，并在关闭重开后逐 link 读回；
- 单位转换必须显式记录：URDF 使用 kg、m、kg·m²；
- assembly 总质量读回目标：
  `4.695555949342986 kg`；
- 总质量容差：绝对误差 `<= 1e-9 kg`，若 SolidWorks 存储精度不能满足，必须如实记录实际精度并 HOLD；
- 每个 link 的属性必须包含 URDF link 名、源质量、源惯性原点、6 个独立惯量分量和 URDF 哈希；
- `MASS_AUTHORITY=ACCEPTED_URDF`；
- `KINEMATIC_AUTHORITY=NONE_FOR_THIS_REPRESENTATION`；
- 任何默认材料/密度计算值都不得覆盖 URDF 值。

### 3.4 互斥总成

`B601_THREE_REPRESENTATIONS.SLDASM` 至少包含三个持久化配置：

| 配置 | HIFI | KINEMATIC_PROXY | MASS_SURROGATE | 允许用途 |
|---|---:|---:|---:|---|
| `HIFI_STOWED_REVIEW` | resolved | suppressed | suppressed | 外形/安装/静态干涉审查 |
| `KINEMATIC_PROXY_REVIEW` | suppressed | resolved | suppressed | URDF 链和姿态审查 |
| `MASS_SURROGATE_REVIEW` | suppressed | suppressed | resolved | 唯一 B601 质量/惯量审查 |

验收必须证明每个配置恰好一个表示 resolved，不得出现：

- HIFI 与 MASS 同时 resolved；
- proxy 与 MASS 同时 resolved；
- 三者全部 suppressed；
- 同一表示重复实例。

将互斥总成以单一实例插入 V2.3 顶装。不得插入三份独立顶层组件。
不得删除或覆盖旧配置；可新增显式 review 配置。任何已有七/九状态的语义必须保持，
且关闭、退出、重启、重开后抑制矩阵一致。

## 4. 执行顺序

1. 对 V2.2_NATIVE 源冻结清单做 pre-hash；若不匹配立即停止。
2. 检查当前 SolidWorks PID、可见性、活动文档和未保存文档；只保留一个可见写入进程。
3. 先修复 V2.3 顶装的 `Removable_Panels` 外部引用并执行一次关闭重开隔离复验。
4. 退出并重启 SolidWorks。
5. 解析 URDF，生成 machine-readable authority contract。
6. 先构建 `KINEMATIC_PROXY`，关闭重开复验。
7. 退出并重启 SolidWorks。
8. 构建 `MASS_SURROGATE`，关闭重开并逐 link/总质量复验。
9. 退出并重启 SolidWorks。
10. 在有充足资源时才执行可见 HIFI 导入；监测模态窗口。不得重复无响应的相同调用。
11. 构建三表示互斥总成并插入 V2.3 顶装。
12. 保存、关闭全部文档、退出 SolidWorks、重新启动并重开顶装。
13. 逐配置读回、完整主结构干涉检查、依赖检查、BOM/质量排除检查。
14. 对 V2.2_NATIVE 源冻结清单做 post-hash。

每一步使用小脚本、小事务；任何 COM API 行为不确定时先做只读探针。

## 5. 验收产物

所有新证据必须位于：

```text
Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/
evidence/stage2_b601_three_rep/
```

至少包括：

- `execution_log.jsonl`
- `preflight_and_source_hashes.json`
- `v23_isolation_repair.json`
- `b601_authority_contract.json`
- `hifi_import_and_reopen.json`
- `kinematic_proxy_readback.json`
- `mass_surrogate_readback.json`
- `three_rep_configuration_matrix.json`
- `top_configuration_persistence.json`
- `dependency_check.json`
- `interference_classification.json`
- `source_baseline_post_hash.json`
- `stage2_machine_verdict.json`
- `NATIVE_MECH_REAL_01_STAGE2_REPORT.md`

机器 verdict 只允许以下三类之一：

- `STAGE2_PASS_WITH_ENGINEERING_HOLDS`
- `STAGE2_PARTIAL_HOLD`
- `STAGE2_FAIL_CLOSED`

即使几何与持久化全部通过，也必须继续保留：

- `STOW_VECTOR_STATUS=CANDIDATE_HOLD`
- `STOW_Z_LIMIT=UNKNOWN`
- `STOW_CONTACT_QUALIFICATION=HOLD`
- `MATERIAL/LOAD/FASTENER/PRELOAD=UNKNOWN_OR_TBD`
- `NO_FEA_NO_DYNAMICS_NO_FLIGHT_RELEASE`
- C5 收拢翼包宽 `238.3 > 226.3 mm`；
- 双侧太阳翼根机构下限宽 `302.3 > 226.3 mm`。

最终报告必须区分：

- 已建立的原生对象；
- 关闭重开后实际读回的状态；
- 未执行/失败/HOLD 的项目；
- 只具几何、运动学或质量 authority 的对象；
- 不得由本轮推出的强度、制造、发射和飞行结论。
