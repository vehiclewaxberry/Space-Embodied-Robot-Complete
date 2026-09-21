
# 机械 Loop Engineering 续接裁决 V1

## 当前结论

- 机械研究已经推进到“可发出供应商 RFI + 可复算非发布轨迹种子”的阶段。
- Route-C 产品/接口最低输入仍为 **0/8 CONTROLLED**，RC-CEG-03 保持 **HOLD**。
- e17 已形成 **5 条数值臂轨迹种子 + 1 条符号骨架 + 2 条阻断未实例化段**，任务发布仍为 **0/8**。
- ODR-42 仍为 **PENDING**；accepted URDF 与 Solar R2 哈希保持不变；本续接包生成几何数量为 **0**。

机器裁决：`MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_VERIFIED_RFI_AND_TRAJECTORY_SEEDS__PRE_CAD_AND_MISSION_RELEASE_HOLD`

## 现在可直接执行

1. 用 `ROUTE_C_VENDOR_RFI_REQUIREMENTS_V1.yaml` 向候选供应商索取精确料号、总成图、成品外径/公差、动态弯扭寿命、质量、恢复力矩、电气降额、环境及交付证据。
2. 由 B601 电气/航电负责人填写 PRJ-01..PRJ-03：负载表、协议/EMC、回路—针脚—导体表。
3. 由机械接口负责人冻结 HN-00..HN-03、J1..J6 的坐标、姿态、基准、公差和安装可达性。
4. 由夹爪负责人裁决 `15 m/s` 与 `15 mm/s` 的单位冲突；未裁决前禁止推导物理闭合时间。
5. 补 M01 释放扫掠权威和 22 kg 目标相对状态/接触边界，再把 e17 从数值种子升级为非发布任务轨迹候选。

## 进入 Route-C CAD 的双入口

- 入口 A：独立签发 ODR-42 `APPROVE_BOUNDED_DETAILED_DESIGN`。
- 入口 B：MPI-01..MPI-08 全部由具名 Owner 配置受控；目录典型值、TBD、null 或 Route-B 种子不得代替。

只有 A 与 B 同时闭合，才允许创建单独版本的 Route-C 参数化 CAD/STEP；随后仍需逐级完成八段轨迹、耦合 SAFE、质量/质心/惯量、恢复力矩、环境与寿命验证，不能直接宣称机械发布或飞行资格。
