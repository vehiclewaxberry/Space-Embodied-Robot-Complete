# 机械 Loop Engineering：Route C 与 Sim13 重绑定裁决

日期：2026-08-23  
适用对象：12U 服务航天器、M3R、B601 六自由度机械臂、Gripper R1、Solar R2 及其后续抓取动力学消费者。

## 1. 当前总裁决

本轮已经完成两项可立即闭合的工程工作：

1. 将 Route-B 线束负结果转换为 Route-C 受导向 dress-pack 的授权前工程包；
2. 将更新后的 M7 机械负证据对旧 Sim13 “production binding” 做时序覆盖，保留历史运动学自举结果，但撤销其作为当前生产动力学、物理接触或 RL 入口的解释空间。

当前单一阶段裁决为：

`MECHANICAL_LOOP_ENGINEERING_PRE_CAD_HOLD_WITH_ACTIONABLE_ROUTE_C_PACKAGE_AND_SIM13_FAIL_CLOSED_SUPERSESSION`

这不是工作失败。它表示：授权前需求、概念、CAD brief、验证路线和下游隔离已经闭合；正式 Route-C 几何仍需独立 Owner 决策与最低产品/接口输入，因此没有生成 STEP/FCStd，也没有修改已接受 URDF 或 Solar R2。

## 2. 工程状态矩阵

| 对象 | 当前状态 | 可做 | 禁止解释 |
|---|---|---|---|
| M4 数字样机 | 受限工作发布 | 哈希/结构、静态几何、诊断桥 | 完整物理样机、正式结构入口或接触 RL 已通过 |
| M7 主机械 Gate | 未发布 | 保留已完成的局部设计级证据 | 以旧 5 PASS + 12 open + 1 HOLD 宣称终局放行 |
| Route B 外置固定线束 | REJECTED | 保留负结果和局部设计种子 | 继承其构型、0.68406762184 kg 质量或任务包络 |
| Route C 受导向 dress-pack | 授权前包完整，CAD entry HOLD | Owner 审批、产品数据采集、概念/验证细化 | 当前已选硬件、已生成 CAD、已满足全域 |
| Sim13 | 历史运动学 bootstrap 保留 | ABORT 与诊断级运动学研究 | 生产抓取动力学、物理接触或 RL 训练 ready |
| 后续抓取入口 | HOLD | 准备新接口和运行时 harness gate 的要求 | 直接把旧 V1 loader/action mask 重命名为生产消费者 |

## 3. Route-C 首选提案

首选提案为 `captive-guided-hybrid`，仍待 ODR-42 选择：

- J1：封闭式、定曲率储线盒；
- J2/J3：安装于父子链节之间的半约束移动导向或 rolling loop，消除 Route B 的无约束折叠和尖点；
- J4：局部旁路与导向 rolling loop 并行权衡；
- J5/J6：定曲率腕部 wrap；
- power/data 分包：仅保留为 trade，必须由载流、数据率、屏蔽/EMC、连接器、体积和寿命共同裁决。

Route-B 的 10 mm bundle OD、30 mm 弯曲半径和 4001.158 mm 裁切长度只作为隔离的 provisional seed；必须按所选产品和 Route-C 几何重新建立。Route-B 的 0.68406762184 kg 诊断质量禁止继承。

## 4. 一次通过的执行顺序

1. C0：Owner 独立签发引用当前请求哈希的 ODR-42；
2. C1：冻结芯线/连接器、bundle OD、适用弯曲限制、安装接口、材料/工艺和寿命目标；
3. C2：在独立命名空间创建 STEP-first 参数化 Route-C 设计，不回写接受 URDF；
4. C3：发布 8/8 具时标的连续任务轨迹 `q(t), dq(t), ddq(t)` 与夹爪状态；
5. C4：先在任务域执行间隙、弯曲、夹挤、长度、导向闭合、Solar keep-out 与关节余量的精确耦合验证；只有明确要求全硬件域时再扩展；
6. C5：重新计算 Route-C 与九构型质量、CG、六惯量及不确定度，并获得各关节恢复力矩/阻尼/摩擦证据；
7. C6：闭合磨耗、碎屑、热真空、弯折寿命、安装检查与安装后电测计划/证据；
8. C7：发布新版本接口，运行时直接绑定精确 harness evaluator，并用 UNKNOWN/UNSAFE→ABORT、篡改和绕过负控证明不可绕过；随后分别重开机械 handoff、physical-contact 和 production-dynamics Gate。

22 kg@0.5°/s 保持名义捕获链；150 kg@3°/s 保持 physics-veto→ABORT/RECOVERY，不包装成成功捕获。

## 5. 当前机器真值入口

- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_CAD_BRIEF_V1.md`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_CAD_ENTRY_GATE_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_PRELIMINARY_VALIDATION_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_BINDING_AUDIT_VALIDATION_REPORT_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/10_loop_integration/MECHANICAL_LOOP_ENGINEERING_STAGE_GATE_V1.json`
- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/10_loop_integration/MECHANICAL_LOOP_ENGINEERING_VALIDATION_REPORT_V1.json`

## 6. 方法来源边界

NASA-STD-8739.4、ECSS-E-ST-33-01C Rev.2、NASA LLIS 687 与 30101 只用于线束工作质量、机构生命周期、受控导向/防挂及安装后检查与电测的方法规划；它们不提供本项目的尺寸、质量、寿命或接受门槛，也不等于自动合规。

## 7. 下一项必须由 Owner 作出的决定

对 `ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml` 选择：

- `APPROVE_BOUNDED_DETAILED_DESIGN`；或
- `REVISE_SCOPE_AND_RESUBMIT`；或
- `REJECT`。

只有第一项，并且最低产品/接口输入受控后，才允许创建 Route-C 参数化几何。任何自然语言继续研究请求都不会被静默改写成 Owner 授权记录。

## 8. 最终验证收据

- Route-C 授权前包：55/55 PASS；manifest SHA-256 `9AE751FBF8595EC390CF0D0FF4BC477C3947FA69E9D5B62013FCBF2C1A67593D`；
- ODR-42 请求 SHA-256：`B4E73CB4B143413D583FC32C7FE94EC8413AEBE626A57970EF8E6B0CB90DB953`；
- Sim13 当前绑定审计：29/29 PASS，负控 7/7；Gate SHA-256 `7FD3C63AF46BE4BA3055CCF87EFD1A71C13517EC872B1F3EDC52304B070D9153`；
- 机械 Loop 集成 Gate：事实 7/7，验证 16/16，负控 5/5；Gate SHA-256 `72BA8E36072C3F21B3EB7CF3A94E30E93C56D368F3412B6D8DBF07970EB482CB`；
- 独立对抗复核：CRITICAL/HIGH/MEDIUM/LOW 均为 0；四组 manifest、集成输入绑定及冻结资产哈希全部匹配；
- 冻结资产：accepted URDF SHA-256 `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`，Solar R2 SHA-256 `21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795`；
- 本轮新增几何文件：0。

以上 PASS 均为包完整性、时序覆盖或负控结果，不升级机械释放、接触动力学、RL 或飞行资格结论。
