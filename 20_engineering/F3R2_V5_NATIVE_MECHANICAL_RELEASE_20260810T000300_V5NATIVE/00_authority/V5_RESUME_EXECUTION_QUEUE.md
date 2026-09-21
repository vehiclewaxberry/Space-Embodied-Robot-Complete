# V5 恢复执行队列

Run ID: `20260810T000300_V5NATIVE`

当前裁决：本轮执行已在用户 override 下推进至收口（2026-08-11）。会话重认证完成：Session B = SolidWorks PID `87516`（2026-08-10T13:43Z，`00_authority/V5_SESSION_REQUALIFICATION.json`，空文档，attach-only；保留历史 G0 回执，非新双会话 G0 重复）。内存门禁 ≥6 GiB 未通过，按 `00_authority/V5_MEMORY_GATE_USER_OVERRIDE.json`（scope ALL_V5_NATIVE_EXECUTION_AND_G0）以 USER_OVERRIDE 执行（非 PASS），逐回执记录实际内存样本（override 后约 1.3–4.0 GiB）。Loop1B / Loop1C0 / Loop1D / LOOP-SOLAR-B 已 PASS；Loop1C1 = `BLOCKED_AT_INTERFERENCE_GATE_PENDING_CONTRACT_DECISION`（待合同裁决 A/B/C）；Loop1E / Loop2 / Loop3 被上游阻塞，未执行。

## 会话重认证机制

状态：已完成（2026-08-10T13:43Z）。重认证回执 `00_authority/V5_SESSION_REQUALIFICATION.json` 已写入，Session B PID `87516`（SW 2024 SP05，空文档）；用户豁免新双会话 G0 重复，保留历史 G0 ready 回执。以下程序已执行完毕，仅在未来会话再次失效时重跑：

原固定 Session B PID `42276` 已失效。恢复 SolidWorks 后先执行新的 G0 smoke + Session B 冷重开，取得新 G0 ready 回执，然后运行：

`python 99_tools/F3R2_V5_G0_SMOKE_ATTACH_ONLY.py _MFINAL_G0_SMOKE_20260809T<HHMMSS>_<ID>`

`python 99_tools/F3R2_V5_G0_SESSION_B_VERIFY_ATTACH_ONLY.py _MFINAL_G0_SMOKE_20260809T<HHMMSS>_<ID>`

`python 99_tools/F3R2_V5_SESSION_REQUALIFY.py --g0-receipt <新的_G0_SOLIDWORKS_NATIVE_EXECUTION_READY.json>`

Session-B 验证器已参数化，可从新 run 目录动态读取 Session-A 证据；重认证程序只写入 `00_authority/V5_SESSION_REQUALIFICATION.json`，不改动历史回执；Loop1B/1C0/1C1/1D/1E 的 V5 执行脚本已接入会话解析器。

## 静态审计现状（2026-08-11 收口）

| 脚本 | 静态裁决 |
|---|---|
| Loop1B | `V5_LOOP1B_STATIC_PASS_OR_VERIFIED_RESUME`；运行侧已 PASS（2026-08-10T22:57Z，见下） |
| Loop1C0 R3 | `V5_LOOP1C0_STATIC_AUDIT_PASS_EXECUTION_AUTHORIZED`；运行侧已 PASS（零件层） |
| Loop1C1 | `V5_LOOP1C1_STATIC_AUDIT_PASS_EXECUTION_AUTHORIZED`（Loop1C0 产物已就绪）；运行侧 fail-closed 于干涉门禁，HOLD 待裁决（见下） |
| Loop1D | `V5_LOOP1D_STATIC_PASS_OR_VERIFIED_RESUME`；运行侧已 PASS（2026-08-11T10:23Z，见下） |
| Loop1E | `V5_LOOP1E_STATIC_PENDING_UPSTREAM`（唯一缺失 = Loop1C1 GRIPPER 回执；其余 9 个 v5_components 回执齐全） |
| Loop2 | `V5_LOOP2_SCRIPT_READY_LOOP1E_INPUTS_PENDING` |
| Loop3 | `V5_LOOP3_STATIC_HOLD`（上游 LOOP1E、LOOP2 未通） |

## 运行现状（2026-08-11 收口）

- 太阳翼候选：原生构建 PASS——6 个简化面板 SLDPRT + `02_native_subassemblies/L_SOLAR_ARRAY.SLDASM` / `R_SOLAR_ARRAY.SLDASM`，各 7 配置，冷验证（`13_validation/V5_SOLAR_ARRAY_NATIVE_RECEIPT_20260810T135905.775293Z.json`；5 张早期 FAIL 回执保留为历史）。相对本队列的位置：它是独立配置族的外部 subsystem 候选模块（`SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md` §6 顺序：Adapter → 多板太阳翼 → Wing Root → …），在本队列之外提前完成，不替代 Loop1B 真实铰链装配，不构成任何最终基线/飞行声明。
- LOOP-SOLAR-B 太阳翼收口：PASS（2026-08-11T11:31Z，`13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json`，verdict `V5_SOLAR_ARRAY_COMPLETION_PASS`）——42/42 面板位姿应用并冷验证非续跑（7 配置×3 面板×2 侧，闭合 F-3 证据链缺口）；8 个占位件（SOLAR_HARNESS_EXIT_L/R、SOLAR_STOW_PAD_L/R、SOLAR_DEPLOY_STOP_L/R_H1/H2）；逐状态寄存器 `04_configurations/V5_SOLAR_STATE_REGISTER.csv`（collision/camera/clearance 列 PENDING_LOOP2）；FAIL 配置显式 CANDIDATE 注册并附到权威 L_FAIL(0/90)/R_FAIL(90/0) 的映射说明；annex `06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_SOLAR_ANNEX.csv`（ESTIMATED/PENDING）与 `09_digital_thread/V5_SOLAR_ARRAY_THREAD_ANNEX.yaml`（CANDIDATE/PENDING_LOOP2_NATIVE_REVALIDATION）。候选占位性质不变。
- Loop1B：PASS（2026-08-10T22:57Z，`13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json`，verdict `V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS`）——`02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM` / `RIGHT_WING_ROOT_TRUE_HINGE.SLDASM` 六配置建成并冷重开验证；manifest `14_release/V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt`。15 张历史 FAIL 回执保留；最终阻塞 HINGE_GROUP_KINEMATIC_DRIFT/TRUE_1R 经 suppress/pose/unsuppress 驱动 + 对齐修正解决。
- Loop1C0：57 实体三零件原生拆分 PASS（`13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json` + PALM/LEFT_FINGER/RIGHT_FINGER 3 张 checkpoint）。
- Loop1C1：HOLD——`BLOCKED_AT_INTERFERENCE_GATE_PENDING_CONTRACT_DECISION`。23 张 fail-closed 回执；装配侧缺陷全部修复并实测证明（guide 配合对齐、limit-mate plain-create+ModifyDefinition 配方、逐配置 SetSystemValue3 驱动、配合台账动态分发）；最终阻塞 = donor 继承几何：donor 零件 `B51_REF_gripper_detail_LINKLOCAL.SLDPRT` 含 81 处内部正体积干涉，与 V5 CLOSED 态逐行 bit-identical（探针证据 `99_tools/probe_logs/`，尤其 INTERFERENCE_BODIES 日志）。裁决选项 A/B/C 见 `99_tools/V5_LOOP1C1_FIX_PROPOSAL_20260810.md` §5。
- Loop1D：PASS（2026-08-11T10:23Z，`13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json`，verdict `V5_LOOP1D_HDRM_CAMERA_HARNESS_NATIVE_FUNCTIONAL_INTERFACE_PASS`）——checkpoint `ARM_HDRM_FUNCTIONAL_ENVELOPE` / `SERVICE_CAMERA_INTERFACE_HOLD`（SERVICE_CAMERA 保持 UNSELECTED）/ `B601_HARNESS_STATIC_INTERFACE_HOLD`；manifest `14_release/V5_LOOP1D_HDRM_CAMERA_HARNESS_MANIFEST_SHA256.txt`。根因修复：SW2024 SP05 组件抑制不级联 lock mates → 显式逐配置配合抑制驱动。
- Loop1E / Loop2 / Loop3：BLOCKED 上游——Loop1E `V5_LOOP1E_STATIC_PENDING_UPSTREAM`、Loop2 `V5_LOOP2_SCRIPT_READY_LOOP1E_INPUTS_PENDING`、Loop3 `V5_LOOP3_STATIC_HOLD`，execution_authorized 均为 false，未执行。唯一解锁键 = Loop1C1 合同裁决（A/B/C）。

## 恢复条件（实际处置）

1. 可用物理内存稳定 `>= 6 GiB`：未满足；由用户 override 覆盖（`00_authority/V5_MEMORY_GATE_USER_OVERRIDE.json`，记 USER_OVERRIDE 非 PASS，实际样本逐回执记录）。
2. 用户人工启动 SolidWorks 2024 SP05 空文档会话：已满足（PID `87516`，重认证 2026-08-10T13:43Z）。该会话保留给编排器，仅 attach-only。
3. 只允许 attach-only，脚本不得自动启动或关闭 SolidWorks：仍然有效。

## 恢复后的唯一动作顺序（逐阶段注记至 2026-08-11 收口）

1. 【已完成】用新的干净会话重新执行 G0 smoke + Session B 冷重开，取得新的会话身份证据；若新会话 PID 与已冻结的 `42276` 不同，先以会话重认证回执更新 Loop1B/1C/1D/1E 的执行绑定，再继续，禁止把旧 Session B PID 当作新会话证据。（实际：重认证至 PID `87516`，用户豁免新双会话 G0 重复，保留历史 G0 回执。）
2. 【已完成 PASS 2026-08-10T22:57Z】`F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py --stage ALL`：左/右真实铰链装配 + STOWED/DEPLOYING/DEPLOYED/L_FAIL/R_FAIL/BOTH_FAIL 六配置。回执 `13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json`（`V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS`），manifest `14_release/V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt`；15 张历史 FAIL 回执保留为历史。
3. 【已完成 PASS】`F3R2_V5_NATIVE_LOOP1C_GRIPPER_ATTACH_ONLY_R3.py`：57 实体三零件 Save Bodies 原生拆分（`13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json`）。
4. 【HOLD 待裁决 A/B/C】`F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY.py`：OPEN/PREGRASP/CLOSED/HOLDING 棱柱配合与原生最小距离。装配侧缺陷全部修复并实测证明；最终阻塞 = donor 继承几何（81 处内部正体积干涉与 V5 CLOSED 态 bit-identical），`BLOCKED_AT_INTERFERENCE_GATE_PENDING_CONTRACT_DECISION`；裁决选项见 `99_tools/V5_LOOP1C1_FIX_PROPOSAL_20260810.md` §5（A 合同修订·推荐 / B 零件返工 / C 无门禁接受·不推荐）。
5. 【已完成 PASS 2026-08-11T10:23Z】`F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY.py`：HDRM 六状态、相机包络支架、OD9 静态线束。回执 `13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json`（`V5_LOOP1D_HDRM_CAMERA_HARNESS_NATIVE_FUNCTIONAL_INTERFACE_PASS`），manifest `14_release/V5_LOOP1D_HDRM_CAMERA_HARNESS_MANIFEST_SHA256.txt`；SERVICE_CAMERA 保持 UNSELECTED。
6. 【已完成 PASS 2026-08-11T11:31Z】LOOP-SOLAR-B `F3R2_V5_NATIVE_SOLAR_ARRAY_COMPLETION_ATTACH_ONLY.py`：太阳翼收口——42/42 面板位姿冷验证非续跑、8 占位件、逐状态寄存器（`13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json`，`V5_SOLAR_ARRAY_COMPLETION_PASS`）。独立配置族候选模块，不构成任何最终基线/飞行声明。
7. 【BLOCKED 上游】`F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py`：`SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM`。静态审计 `V5_LOOP1E_STATIC_PENDING_UPSTREAM`，execution_authorized=false；唯一缺失回执 = GRIPPER（Loop1C1），其余 9 个 v5_components 回执齐全。
8. 【BLOCKED 上游】`F3R2_V5_NATIVE_LOOP2_MOTION_ROBOTICS_ATTACH_ONLY.py`：原生路径/干涉/最小距离；缺失服务姿态输出 `IK_CANDIDATE_SET` 与 `POSE_AUTHORIZATION_REQUIRED`，不自动授权。静态审计 `V5_LOOP2_SCRIPT_READY_LOOP1E_INPUTS_PENDING`，execution_authorized=false。
9. 【BLOCKED 上游】`F3R2_V5_NATIVE_LOOP3_RELEASE_EVIDENCE_ATTACH_ONLY.py`：工程图、BOM、Pack-and-Go、双会话冷重开、人审图册与最终门禁。静态审计 `V5_LOOP3_STATIC_HOLD`（上游 LOOP1E、LOOP2 未通）。

唯一解锁键 = Loop1C1 合同裁决（A/B/C）：Loop1E → Loop2 → Loop3 全部在其下游。

## 当前已固化

- 20/20 V4 中性部件原生导入 + 冷重开 PASS（`V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json`）。
- Rev-B2 基座 + G07/G08/Mid 子装配冷重开 PASS（`V5_LOOP1A_SUBASSEMBLY_RECEIPT.json`）。
- 翼根 donor 隔离零件与左右 U 耳/轴向保持件 checkpoint PASS（Loop1B0/1B1 零件层）。
- Loop1B 左/右真实铰链装配六配置冷重开 PASS（`13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json` + `14_release/V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt`）。
- 太阳翼候选 6 简化面板 + 左右侧装配（各 7 配置）冷验证 PASS（`13_validation/V5_SOLAR_ARRAY_NATIVE_RECEIPT_20260810T135905.775293Z.json`）。
- LOOP-SOLAR-B 太阳翼收口 PASS（`13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json`，42/42 位姿冷验证 + 8 占位件 + 状态寄存器 + 质量/线程 annex，候选占位性质不变）。
- 夹爪 57 实体三零件原生拆分 PASS（`13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json` + 3 张 checkpoint）。
- Loop1D HDRM/相机/线束原生功能接口 PASS（`13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json` + `14_release/V5_LOOP1D_HDRM_CAMERA_HARNESS_MANIFEST_SHA256.txt`；SERVICE_CAMERA 保持 UNSELECTED）。
- 数字线程六文件种子 PASS（`09_digital_thread/`）。
- 原型紧固件注册表 `V5_FASTENER_REGISTER.csv` 8 行 PASS，未定义紧固件单独记入 `V5_FASTENER_HOLD_REGISTER.csv`（3 行 HOLD）。
- 最新 Loop1B→Loop3 执行脚本已复制进 `99_tools/`。

## 不得触碰

- accepted B601 URDF、joint topology/axes/lengths/mass/inertia。
- F3R1/F3R2 冻结顶层、V2_2 donor、V4 中性候选与全部历史 Gate/evidence。
- `SERVICE_CAMERA=UNSELECTED` 与 `CAMERA_MODEL_SELECTION_HOLD`。
- `FORMAL_LAUNCH_FASTENER_MOS = HOLD`、`AUTHORIZED_LAUNCH_LOAD = HOLD`、`FLIGHT_QUALIFICATION = HOLD` 等既有 HOLD。

## 禁止称谓

`FINAL_NATIVE_CAD_BASELINE`、`MANUFACTURING_RELEASED_BASELINE`、`FLIGHT_READY`、`LAUNCH_QUALIFIED`、`FULLY_AUTHORIZED_SERVICE_AND_GRASP_TRAJECTORY`。
