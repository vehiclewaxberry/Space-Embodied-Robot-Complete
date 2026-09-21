# B601 夹爪 2P Operational Proxy CAD Brief V1

## 工程裁决

本工作包允许后续构建三个、且仅三个本地几何候选容器：palm、left finger、right finger。三个主交付物均以 STEP 为第一权威格式；每个 STEP 可以是包含多个封闭实体的 compound，不要求、也禁止为了凑成单实体而执行并集、外包络或发明连接结构。

本工作包不是新夹爪方案设计，不修改接受版 URDF，不选择 C01–C09 中任何 Owner 状态，也不产生 system narrowphase、pair、edge、path、contact、strength、manufacturing 或 release credit。

## CAD brief

- 模型：B601 两指平移夹爪的三容器 operational geometry proxy。
- 任务类型：对冻结源几何做成员筛选、坐标重定位和 STEP-first 再封装；不是从零建模，也不是结构优化。
- 主输入：R1 palm STEP、neutral multi-body donor STEP、冻结 solid assignment、native receipt、接受版 B601 URDF、M5 frame decision。
- STEP 原生长度单位：mm。
- URDF 与运行时长度单位：m；转动单位 rad；两条 prismatic 状态单位 m。
- 坐标约定：palm 存储在 gripper_link；left finger 存储在 gripper_left；right finger 存储在 gripper_right；均为右手系并遵循接受版 URDF。
- 关键定位：两指从 gripper_link-local donor 几何出发，在 URDF q=0 参考变换处各做一次且仅一次逆变换，得到 child-link-local STEP；q=0 仅是坐标定义，不是 Owner 状态。
- 主输出：01_cad 下三个独立 STEP；02_runtime 下三个以 m 为单位的 PLY sidecar。
- 可选派生输出：确定性 NPZ 或 STL 只可作为非权威运行/显示 sidecar，必须由已验证 STEP 派生并单列 hash/单位/坐标收据。
- 验证目标：源 pin 全匹配；容器数 3；独立 reopen；逐 solid valid、closed、finite positive volume；实体成员与数量账本一致；child-local 输出经精确 q=0 URDF 变换重组后返回 gripper_link-local 源；mm→m 只转换一次；双重坐标变换负控被捕获。
- 制造假设：无。不得补填间隙、材料、强度、接触参数、执行器能力或公差。
- 快照：本合同阶段不生成几何，因此无快照；后续实际生成每个主 STEP 后必须分别制作并人工检查快照，且快照不替代确定性几何验证。

## 冻结源与使用边界

| 作用 | 冻结源 | SHA-256 | 允许用途 |
| --- | --- | --- | --- |
| 接受版 frame tree 与 2P domain | 20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf | 1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164 | 读取 joint origin、axis、parent/child 与 0–0.0715 m 定义域；不得把 effort/velocity literal 当硬件权威 |
| palm 主 BRep | 20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.step | 97E2FE07FE24673DEAE473D0518FD30E3345ED85A82F8811265482B0215811BC | 直接 reopen、保留多实体结构、输出 gripper_link-local palm 容器 |
| finger 主 donor BRep | 20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/vendor_reference_linklocal/B50_REF_gripper_detail_LINKLOCAL.step | DEEF375F2FFE6A019A7348F14FC5AE4C4ACCC950A4C92351607350335A5A2E7F | 只提取冻结分组中的 24 left 与 24 right physical bodies |
| body 分组 | 20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/08_camera_harness/F3R2_GRIPPER_SOLID_ASSIGNMENT.csv | 419F63149413E5EC5677357D95639CFACF68CE143964485EFB402F2A803B2C78 | 绑定 native 9 palm / 24 left / 24 right；排除 aggregate wrapper |
| native receipt | 20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json | 5E1808E659B039791061BCE93D15D60BC95CAE06641B02954E1EDFC09E2258A8 | 证明 native physical-body lineage 为 57，并排除 B51_REF_gripper_detail_LINKLOCAL057 |
| frame 与 travel 冲突 | 20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json | 2A99484C6CE55B402CB06380F5DCB71D5A8B4BA622A371EEF72F4EC69EF124FF | 锁定 gripper_link 数值 frame、拒绝直接 link6 binding，并保持 travel authority 为 null |
| Owner 状态真值 | 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l02_configuration_state_contract_v1/R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1.yaml | C60744D6978AFA8987D3D294792044380ACA27E0F30C2E3DE7C0AA2747F23D63 | 保持全部九种配置的 gripper_joint1_m / gripper_joint2_m 为 null、仅定义域有效 |

完整字节数与 SHA 锁以 SOURCE_AUTHORITY_LOCK_V1.json 为准。任何 pin 不匹配都必须在读取几何前 fail closed。

## 三个主 STEP 容器

### 1. Palm

- 输出：01_cad/B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_V1.step。
- owning link / local frame：gripper_link。
- 主源：R1 palm STEP，直接读取，不用旧 native 9-body palm 替换。
- 当前冻结 reopen 证据：12 个 valid solids，正总体积。
- 后续验收：再次独立 reopen 必须精确得到 12 个 solid，且每个 solid 都必须 closed、valid、finite positive volume。
- 禁止把 rail-slot cut 后的 12 solids 重新并成 9、1 或其他数量。

### 2. Left finger

- 输出：01_cad/B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_V1.step。
- owning link / local frame：gripper_left。
- 主源：neutral donor STEP 中由冻结 assignment 与 native receipt 同时确认的 24 个 left physical bodies。
- donor 输入坐标：gripper_link-local。
- 离线操作：对每个选中 body 应用 accepted URDF gripper_joint1 q=0 origin 的逆刚体变换一次，得到 gripper_left-local 几何。
- 后续验收：选择计数和独立 reopen 输出计数均为 24；逐 solid closed、valid、finite positive volume。

### 3. Right finger

- 输出：01_cad/B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_V1.step。
- owning link / local frame：gripper_right。
- 主源：neutral donor STEP 中由冻结 assignment 与 native receipt 同时确认的 24 个 right physical bodies。
- donor 输入坐标：gripper_link-local。
- 离线操作：对每个选中 body 应用 accepted URDF gripper_joint2 q=0 origin 的逆刚体变换一次，得到 gripper_right-local 几何。
- 后续验收：选择计数和独立 reopen 输出计数均为 24；逐 solid closed、valid、finite positive volume。

## 57 与 60 的计数解释

冻结 native lineage 在排除 aggregate wrapper 后为 57 个 physical bodies，分组为 9 palm + 24 left + 24 right。R1 对 palm 执行 rail-slot cut 后，直接 palm STEP 的 reopen 结果变为 12 solids；两侧 finger 仍各为 24。因此新三容器的预期独立 reopen 计数是 12 + 24 + 24 = 60。

这两个数字描述不同阶段，不可互相替换：57 是 native lineage 计数，60 是 R1 palm 派生后三个新容器的预期 reopen 计数。后续 builder 与独立 validator 都必须实际重数；不得通过 fuse、split、drop 或 duplicate 人为满足数字。

## 坐标与单位操作

接受版 URDF 采用 parent-to-child 约定：joint origin 把 child/joint frame 映射到 parent frame；prismatic axis 写在 joint frame。

对任一 finger，令 R0、t0 为相应 URDF joint 在 q=0 的 parent-to-child rotation 与 translation。donor 点以 gripper_link-local mm 表示，则 child-local STEP 点为：

    p_child_mm = transpose(R0) * (p_parent_mm - 1000 * t0_m)

运行时 sidecar 已是 child-local m，采用：

    p_parent_m(q) = R0 * (p_child_m + axis_joint * q_m) + t0_m

必须满足以下防错规则：

1. t0 从 m 到 mm 只在 STEP 离线重定位边界乘 1000 一次。
2. validated STEP 从 mm 到 runtime sidecar m 只在导出边界乘 0.001 一次。
3. child-local finger 几何内置 placement 为 identity；运行时 joint origin 与 prismatic motion 各只应用一次。
4. palm 始终 gripper_link-local，不得预烘焙 link6→gripper_link 后又在运行时重复应用。
5. 不得把当前 M5 的 gripper_link-local finger PLY 直接改标签当成 child-link-local 资产。
6. 不得同时对同一资产应用 M5 简化的 parent-frame 平移表达与接受版 URDF 精确变换。

精确 origin、矩阵、axis 与变换公式见 URDF_FRAME_AND_STATE_LEDGER_V1.json。

## 后续 builder 工作顺序

1. 在打开任何 CAD/BRep 前重算所有必需源文件的 bytes 与 SHA-256；任一不符即停止。
2. 直接 reopen R1 palm STEP；记录 12 个 source solids 的稳定标识、valid、closed、volume 与总体 bounds。
3. reopen neutral donor STEP；用 assignment + receipt 的交集选择 24 left 与 24 right；明确排除 aggregate wrapper。
4. 在 mm 域对两组 finger 分别执行一次 inverse-q0 child-frame reframe；不得改形、并集或补连接。
5. 分别发射三个带明确容器/solid 标签的 STEP；不得再包成第四个 aggregate STEP 作为本合同主交付物。
6. 用独立进程重新 reopen 三个 STEP，逐 solid 检查 valid、closed、finite positive volume 与精确计数 12/24/24。
7. 将 child/palm-local STEP 派生为 m 单位 runtime PLY；生成 scale、frame、bounds、source/output hash 收据。
8. 做 q=0 重组检查：finger child-local 输出经接受版 URDF q=0 变换后应返回选中的 gripper_link-local donor 几何。比较阈值必须在首次执行前冻结，禁止看到结果后放宽。
9. 为每个主 STEP 生成独立快照并人工检查 left/right 对称性、palm rail-slot 与异常漂移；视觉检查只作补充。
10. 运行合同列出的负控并生成 local candidate Gate；Gate 不得修改 M01 registry 或父发布 Gate。

## Swept volume 边界

全行程 swept volume 或运动包络只可用于 broadphase conservative screening。它可以用于剔除显然不可能相交的 pair，但不得：

- 给出 SAFE、UNSAFE 或 CONTACT 终裁；
- 替代 exact narrowphase pair query；
- 作为连续 edge certificate；
- 掩盖 Owner gripper state 未绑定；
- 增加 system safe、pair、edge 或 path 计数。

## Owner named-state → travel HOLD

当前存在三组非权威 witness：

- R1/M5 named travel：CLOSED 0.0 m、PARTIAL 0.03575 m、PREGRASP 0.055 m、OPEN 0.0715 m；
- alternate equal-increment witness：0.0、0.023833、0.047667、0.0715 m；
- dynamics locked-2P diagnostic：qP_star = [0.03575, 0.03575] m。

configuration_travel_authority 仍为 null，C01–C09 的两条 gripper value 仍全部为 null。上述任何 witness 都不能被写回 Owner state。裁决保持 HOLD_UNTIL_CONFIGURATION_TO_TRAVEL_MAP_IS_RATIFIED；本包只构建 link-local 几何，不构建 named-state 或 scene-instance 几何。

## Fail-closed 验收与非升级声明

后续 local Gate 只有在以下条件全部满足时才可报告 local candidate PASS：三个源绑定 STEP 容器存在；12/24/24 经独立 reopen；每个 solid closed、valid、finite positive volume；frame/unit 重定位可复算；负控全部被捕获；所有源 pin 重验通过。

即便 local Gate PASS，系统真值仍必须原样保持：

- operational asset authority：1/150；
- required pair queries：0/11166 executed；
- certified system edges：0；
- bound stage instances：0/3；
- system safe certificates：0；
- system pair evaluation、path search、parent gate credit、next stage、release credit：全部 false。

## 本合同阶段执行记录

本阶段仅完成只读源核验与设计合同冻结。未运行 CAD、BRep、mesh、snapshot、pair query、collision、path search 或仿真程序，也未生成 01_cad 或 02_runtime 资产。
