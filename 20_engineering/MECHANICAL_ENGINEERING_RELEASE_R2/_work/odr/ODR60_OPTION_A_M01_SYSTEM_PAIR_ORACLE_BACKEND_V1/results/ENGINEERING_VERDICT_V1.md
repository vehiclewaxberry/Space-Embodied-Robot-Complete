# M01 system pair-oracle backend V1 engineering verdict

## 裁决

`PAIR_ORACLE_SCHEMA_AND_FAIL_CLOSED_BACKEND_IMPLEMENTED_AND_SYNTHETICALLY_VALIDATED__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__ZERO_SAFE_PAIRS__NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT`

本包的 OCP/BRep 单-pair 后端已通过合成软件资格验证：4 个几何状态夹具与 1 个精确相邻例外均按冻结合同输出；29 个 pytest、18/18 个适用负控和独立 OCP 复算均通过。未适用于本软件层的 8 个动力学/接触/路径负控明确记录为 `NOT_APPLICABLE`，没有计作 PASS。

## 单位与数值边界

- BRep 原生长度为 mm；S 系位姿平移输入为 m，仅在 OCP transform 边界执行一次 `×1000`。
- q 为 rad 和精确 binary64 字节哈希。
- 距离、witness、clearance、Hausdorff derate、backend debit 与 margin 均为 mm。
- SAFE 只由严格正下裕量签发；下界不足而上界未证明越限时为 UNKNOWN；UNSAFE 只由非正认证上裕量或接触见证签发。

## 未改变的系统状态

- 当前系统运行几何 authority 仍为 1/150；link1-link6 仍为 `PENDING_OWNER_REVIEW` 本地候选。
- clearance policy 仍为 0/11,166，三阶段实例仍为 0/3。
- 当前系统 pair query=0、system SAFE pair=0、continuous edge=0、path search=false。
- TMG-4、G12、父机械 Gate、next-stage 与 release credit 均未重发/未解锁。

因此，本 Gate 只关闭 CP-3 的“后端实现与 fail-closed 合成资格”子项，不关闭真实系统绑定、批完整性、连续路径或发布。
