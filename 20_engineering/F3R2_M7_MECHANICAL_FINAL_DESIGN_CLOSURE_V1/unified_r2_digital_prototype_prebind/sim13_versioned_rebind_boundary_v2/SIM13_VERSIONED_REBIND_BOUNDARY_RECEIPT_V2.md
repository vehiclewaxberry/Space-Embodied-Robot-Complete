# Sim13 V2 版本化机械重绑定边界回执

- 机器检查：`21/21`；裁决：`PASS_VERSIONED_REBIND_BOUNDARY_DEFINITION_ONLY`。
- 本包只冻结未来接口字段、19-link/18-joint 系统不变量、八个继承安全门＋四个新增机械门、20 项负对照要求和六级 Gate 顺序。
- 20 项负对照本轮仅完成机器可判定的需求声明，`executed_count=0`；将在对应系统绑定、运行时、动力学与接触 Gate 中执行。
- 未生成 `.urdf`，未实例化 `MECH_RL_SYSTEM_INTERFACE_V2.yaml`，未建立或修改 Sim13 V2/V1 运行时代码。
- 当前只允许 `ABORT` 或历史诊断性运动学 bootstrap；不得宣称已进入动力学抓取。
- 下一有效动作：Owner 接受无 Route-C 研究候选范围后，签发独立、单次、哈希绑定的 Unified R2 URDF 生成授权。
- `next_stage_authorized=false`；无接触、生产动力学、飞行或发布信用。
