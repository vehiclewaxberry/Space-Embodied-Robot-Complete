# F3R2 V5 当前状态

更新：2026-08-11（本轮收口）。会话已重认证至 SolidWorks PID 87516（2026-08-10T13:43Z，`00_authority/V5_SESSION_REQUALIFICATION.json`，空文档 attach-only，保留历史 G0 回执，非新双会话 G0 重复）。内存门禁 `TOOLING_HOLD`（≥6 GiB）仍未通过：用户 override 已签署并持续有效（`00_authority/V5_MEMORY_GATE_USER_OVERRIDE.json`，scope ALL_V5_NATIVE_EXECUTION_AND_G0，override 后实际样本约 1.3–4.0 GiB 逐回执记录，记 USER_OVERRIDE 非 PASS），原生执行在 override 下进行。

## PASS / 已固化

| 项 | 状态 | 权威证据 |
|---|---|---|
| G0 smoke + Session B 冷重开（旧会话） | PASS（历史） | `_MFINAL_G0_SMOKE_20260809T172928_P4E8/G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json` |
| 受保护资产 PRE/POST | 6/6 PASS | `00_authority/V5_PROTECTED_BASELINE_PRE.json`；本轮完整性审计再次 PASS |
| V4 中性部件原生导入 | 20/20 PASS | `13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json` |
| Rev-B2 基座 + G07/G08/Mid 子装配 | PASS | `13_validation/V5_LOOP1A_SUBASSEMBLY_RECEIPT.json` |
| 翼根 donor 隔离零件 + U 耳/轴向保持件 | 零件层 PASS | `13_validation/V5_LOOP1B_ARTIFACT_*.json` |
| Loop1B 左/右真实铰链装配（六配置，冷重开 DOF/配合证明） | PASS | `13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json`（verdict `V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS`，2026-08-10T22:57Z）；`02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM` / `RIGHT_WING_ROOT_TRUE_HINGE.SLDASM`；`14_release/V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt`（15 张历史 FAIL 回执保留为历史；最终阻塞 HINGE_GROUP_KINEMATIC_DRIFT/TRUE_1R 经 suppress/pose/unsuppress 驱动 + 对齐修正解决） |
| Loop1D HDRM/相机/线束原生功能接口 | PASS | `13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json`（verdict `V5_LOOP1D_HDRM_CAMERA_HARNESS_NATIVE_FUNCTIONAL_INTERFACE_PASS`，2026-08-11T10:23Z）：`ARM_HDRM_FUNCTIONAL_ENVELOPE`（六状态）/ `SERVICE_CAMERA_INTERFACE_HOLD`（SERVICE_CAMERA 保持 UNSELECTED）/ `B601_HARNESS_STATIC_INTERFACE_HOLD`；`14_release/V5_LOOP1D_HDRM_CAMERA_HARNESS_MANIFEST_SHA256.txt`（根因修复：SW2024 SP05 组件抑制不级联 lock mates → 显式逐配置配合抑制驱动） |
| 会话重认证（Session B PID 87516，空文档） | PASS（重认证，USER_OVERRIDE 下，非新双会话 G0） | `00_authority/V5_SESSION_REQUALIFICATION.json` |
| 太阳翼候选原生构建（6 简化面板 + L/R 侧装配，各 7 配置，冷验证） | PASS（候选占位，非最终基线） | `13_validation/V5_SOLAR_ARRAY_NATIVE_RECEIPT_20260810T135905.775293Z.json`（5 张早期 FAIL 回执保留为历史） |
| 太阳翼收口（LOOP-SOLAR-B：42/42 面板位姿应用并冷验证非续跑，7 配置×3 面板×2 侧；8 占位件；状态寄存器） | PASS（候选占位，非最终基线） | `13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json`（verdict `V5_SOLAR_ARRAY_COMPLETION_PASS`，2026-08-11T11:31Z）；`04_configurations/V5_SOLAR_STATE_REGISTER.csv`（collision/camera/clearance 列 PENDING_LOOP2）；`06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_SOLAR_ANNEX.csv`（ESTIMATED/PENDING）；`09_digital_thread/V5_SOLAR_ARRAY_THREAD_ANNEX.yaml`（CANDIDATE/PENDING_LOOP2_NATIVE_REVALIDATION） |
| Loop1C0 夹爪三零件原生拆分（57 实体→PALM/LEFT_FINGER/RIGHT_FINGER） | 零件层 PASS | `13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json` + 3 张 checkpoint |
| 原生文件完整性 | 41/41 PASS | `13_validation/V5_NATIVE_INTEGRITY_AUDIT_20260809T205139.808119Z.json` |
| 数字线程六文件 | PASS | Loop3 静态审计 `DIGITAL_THREAD=PASS` |
| 原型紧固件注册表 | PASS | `00_authority/V5_FASTENER_REGISTER.csv`；Loop3 静态审计 `FASTENERS=PASS` |

## 静态就绪 / 等待上游

- Loop1B：已 PASS（见上表，2026-08-10T22:57Z，冷重开 DOF/配合证明齐全）。
- Loop1C0：已完成（见上表，零件层 PASS）。
- Loop1C1：HOLD——`BLOCKED_AT_INTERFERENCE_GATE_PENDING_CONTRACT_DECISION`。23 张 fail-closed 回执（`13_validation/V5_LOOP1C1_FAIL_*.json`）；装配侧缺陷全部修复并实测证明（guide 配合对齐、limit-mate plain-create+ModifyDefinition 配方、逐配置 SetSystemValue3 驱动、配合台账动态分发）；最终阻塞 = donor 继承几何：donor 零件 `B51_REF_gripper_detail_LINKLOCAL.SLDPRT` 含 81 处内部正体积干涉，与 V5 CLOSED 态逐行 bit-identical（探针证据 `99_tools/probe_logs/`，尤其 INTERFERENCE_BODIES 日志）。裁决选项见 `99_tools/V5_LOOP1C1_FIX_PROPOSAL_20260810.md` §5：A 合同修订接受 donor 继承指纹表（推荐）/ B 零件返工（级联冻结输入哈希）/ C 无门禁接受（不推荐）。
- Loop1D：已 PASS（见上表，2026-08-11T10:23Z）。
- Loop1E / Loop2 / Loop3：被上游阻塞（见下节）。

## PENDING / HOLD

- 夹爪棱柱装配与四状态（Loop1C1 `BLOCKED_AT_INTERFERENCE_GATE_PENDING_CONTRACT_DECISION`）、顶装（Loop1E）、Loop2 路径验证、工程图/BOM/Pack-and-Go、双会话冷重开、人审图册、最终门禁。
- Loop1E：`V5_LOOP1E_STATIC_PENDING_UPSTREAM`，execution_authorized=false——唯一缺失回执 = GRIPPER（Loop1C1），其余 9 个 v5_components 回执齐全。
- Loop2：`V5_LOOP2_SCRIPT_READY_LOOP1E_INPUTS_PENDING`，execution_authorized=false。
- Loop3：`V5_LOOP3_STATIC_HOLD`（上游 LOOP1E、LOOP2 未通）。
- 唯一解锁键 = Loop1C1 合同裁决（A/B/C）：Loop1E → Loop2 → Loop3 全部在其下游。
- `TOOLING_HOLD`：可用内存需 ≥6 GiB。
- 内存门禁至今未通过；2026-08-10 用户签署 override（`00_authority/V5_MEMORY_GATE_USER_OVERRIDE.json`，scope ALL_V5_NATIVE_EXECUTION_AND_G0，override 后实际样本约 1.3–4.0 GiB 逐回执记录），记 USER_OVERRIDE 而非 PASS，原生执行已在 override 下进行。
- `CAMERA_MODEL_SELECTION_HOLD`、`FORMAL_LAUNCH_FASTENER_MOS=HOLD`、`AUTHORIZED_LAUNCH_LOAD=HOLD`、`FLIGHT_QUALIFICATION=HOLD` 等不变。

## 禁止称谓

`FINAL_NATIVE_CAD_BASELINE`、`MANUFACTURING_RELEASED_BASELINE`、`FLIGHT_READY`、`LAUNCH_QUALIFIED`、`FULLY_AUTHORIZED_SERVICE_AND_GRASP_TRAJECTORY`。
