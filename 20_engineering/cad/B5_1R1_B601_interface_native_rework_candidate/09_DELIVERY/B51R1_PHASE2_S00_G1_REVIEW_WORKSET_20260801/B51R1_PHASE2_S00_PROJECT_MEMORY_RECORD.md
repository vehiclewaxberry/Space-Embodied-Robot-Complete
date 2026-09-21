# B5.1R1 Phase 2 S00 项目持久化记忆记录

记录日期：2026-08-01  
状态：`B51R1_PHASE2_S00_AUTHORITY_INPUTS_HASH_VERIFIED_G1_HOLD`

## 后续任务必须先恢复的事实

- 候选根目录：`20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate`。
- Loop+Multi-Agent intake ZIP：11,814 bytes，SHA-256 `277AFF81693DF362BBE45B01528452156E9481FD003E07C903E8E0358BABFDD2`。
- 原 Phase 2A 启动包必须保持不可变：11 文件；ZIP SHA-256 `EE44124CC0DB1E0F6757F3662D66729B2D4CB3CF2F3391D2370CC0F8CC8D226C`。
- V1 input lock 当前 15/15 匹配，但没有锁入本工作集或未来人类签名，不能称 `PASS_HASH_LOCKED`。
- accepted URDF：SHA-256 `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`；10 links、9 joints、`6R + 1 fixed + 2 independent P`；质量权威精确文本 `4.6955559493429862 kg`。
- Stage A：SHA-256 `5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B`；策略只读但 Windows ReadOnly=false；同目录有 6-byte 残留锁文件，须人类裁决，禁止自动删除。
- Single-CS 持久化 PASS 不授予原生建模；S01～S06 当前授权数均为 0。
- 最终 Skeleton 不存在、Carrier `0/10`、原生 chain/B601/顶层整星不存在；H10 `0/28`；T005-A/B/C `NOT_RUN`；控制交接 `0/8`。

## 已建立的新工程规则

1. 原 G1 拆为：
   - `G1A_AUTHORITY_AND_HASH_LOCK`；
   - `G1B_S01_ADMISSION`。
2. 原 11 文件包不原地签署；使用独立 S00 review workset，签署后生成 V2 refrozen input lock。
3. Datum 专家候选：101.65 mm 纵梁轴、110.15 mm 主承力面、113.15 mm 面板/footprint；105.65 mm 可签署为历史语义未解决且禁止驱动，不强迫猜测。
4. 命名候选采用逐 link/joint 展开名称；父/子 token 方向和 axis/q0 ownership 反直觉，必须逐 Carrier 人工冻结。
5. CAD—URDF 容差拆成 14 项；R joint 使用 unwrapped bounded coordinate + branch index，FK 旋转使用 SO(3) geodesic。
6. G1A 只关闭与 S01/G1A 相关 finding；下游 Critical/High 可由 A0/A6 登记为具名 `DEFERRED_HOLD`，并在指定 Gate 自动重新阻断。
7. 后续 S01 只能使用 G1B admission V2，必须绑定 G1A PASS receipt、V2 lock、Stage A 锁文件处置、finding disposition 和 Owner 精确授权；`authorized_session_ids` 必须恰为 `[S01]`，可见启动数恰为 1。

## 必须保留的下游 HOLD

- URDF 引用的 10 个 `meshes_b601_gripper/*.STL` 在工作区为 `0/10`；visual/collision/MuJoCo/Isaac 依赖未闭合。
- URDF header 的“2P locked for dynamics v1”与 XML 的两个可动 P 存在模式冲突。
- fixed joint 零轴需 parser compatibility；J6 近 2π 需 branch continuity oracle。
- 113.15 mm 面板层/G07/G08 footprint 永远不自动获得载荷信用；必须有面板旁路到命名主框/纵梁。
- 适配器 trade、G07/G08/HDRM DOF/预紧/释放、H9/H10、连续间隙、结构/质量、控制/SAFE/传感/碰撞均未闭合。
- 刚体连续间隙 G8a 后必须在结构/热/容差/线束结果可用时执行 G8b 鲁棒复查。

## 用户工作偏好

用户要求先构建完整工程框架并由其审核，审核和新授权之前不得进入实际工程操作或 SolidWorks 写入。

## 下次恢复顺序

1. 重读 `LOOP00_AUTHORITY_LOCK.json`、G1 multi-agent review、finding disposition、claim matrix。
2. 现场复算 intake、11 文件包、Stage A、accepted URDF、Phase/Single-CS Gate 和所有 workset hash。
3. 检查 `SLDWORKS.exe=0`、Stage A 锁文件、G1A/G1B 状态和授权次数。
4. 只有在人类签署三项权威、批准 finding disposition、完成 V2 lock 与 G1A PASS 后，才可请求 G1B/S01 精确授权。

