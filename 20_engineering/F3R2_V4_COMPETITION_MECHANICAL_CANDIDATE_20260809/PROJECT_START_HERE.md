# F3R2 V4 竞赛机械候选——阅读入口

本目录是 2026-08-09 建立的后继机械设计树。它不覆盖 F3R1，也不覆盖冻结的 F3R2 顶装；目标是把最后一轮可安全完成的机械设计做成可复核的中性 CAD，并把必须依赖 SolidWorks、实物或人审的门禁准确隔离。

当前机器裁定为：

`MFINAL_V4_NEUTRAL_MECHANICAL_DESIGN_BASIS_ESTABLISHED_NATIVE_RELEASE_HOLD`

这表示 Rev-B2 基座、翼根叉耳候选、G07/G08/Mid V2 支撑、HDRM 功能骨架、相机/线束包络以及夹爪三组分体已经形成中性几何和证据，但仍不是原生 SolidWorks 制造发布，也不是发射/飞行基线。

## 1. 本轮已经完成的内容

| 工作包 | 当前结果 | 不得外推的边界 |
|---|---|---|
| M-FINAL-01 基座 | Stage A 保持实测 4×M4 接口；Stage B Rev-B2 增加四个 R15 局部承载耳，4×M6@140×140 的净孔边由 6.7 mm 提升到 11.7 mm | 载荷桥实物孔系、紧固件预紧、MoS、试装、原生冷开仍待完成 |
| M-FINAL-02 翼根 | 左/右三腹板双剪叉耳、间隔片、挡块和护线套候选已建；Ø8 销/Ø8.4 孔、每侧 0.5 mm 耳侧间隙 | 尚未与真实翼板做原生布尔合并、配合、运动与干涉验证 |
| M-FINAL-03 支撑 | G07/G08/Mid V2 支撑体、载台与垫块已建；垫面分别锁定 z=261.5016/208.4929/212.9189 mm | 底脚孔位仍是工程候选，需从原生旧塔脚直接复测；预载需台架标定 |
| M-FINAL-04 HDRM | 权威链已统一为预载 +X、工作释放 -X、地面拆装 +Z、行程 6 mm；建立保守扫掠包络 | 未选电磁件、孔阵时钟角/定位销坐标、约束杯与物理释放试验，只有 skeleton |
| M-FINAL-05 相机/线束 | 40×34×26 相机包络和 OD9 静态线束扫掠已建；曲线最小弯曲半径 114.665 mm，超过 25 mm 要求 | `SERVICE_CAMERA=UNSELECTED`；无光学标定、连接器、活动线束扫掠 |
| M-FINAL-06 夹爪 | 58 个源实体分为 palm 10、left 24、right 24，并输出三组 FCStd/STL | 尚未 Save Bodies 成 SLDPRT、建立 SLDASM/棱柱配合/原生配置 |
| M-FINAL-07 位姿/路径 | 继承 5 个已有 q 向量并建立 V4 权限表 | 新硬件加入后必须重算；服务抓取等姿态不得由代理自行授权 |
| M-FINAL-08 放行/CM | 生成 BOM、构建回执、独立 OCP 回读验证与散列清单 | 原生工程图、全配置重建、Pack-and-Go、双进程冷开和人审仍为 HOLD |

## 2. 首选阅读顺序

1. `01_authority/MFINAL_CONTROL_BASELINE.yaml`：唯一控制边界。
2. `01_authority/MFINAL_AUTHORITY_MATRIX.csv`：八个工作包的 authority 与剩余门禁。
3. `10_validation/MFINAL_FREECAD_BUILD_RECEIPT.json`：全部几何、体积、质量、边界和输出路径。
4. `10_validation/MFINAL_INDEPENDENT_VALIDATION.json`：独立 STEP 回读与 10 组检查。
5. `09_bom/MFINAL_PROVISIONAL_BOM.csv`：23 行候选 BOM。
6. `08_poses_paths/MFINAL_POSE_AUTHORITY_REGISTER.csv`：姿态可用性与人审边界。
7. `11_release/MFINAL_GATE.json`：最终机器 Gate。

## 3. 重要工程数值

- 中性 CAD：26 FCStd、23 STEP、23 STL。
- Manifest 受控行：73；缺失 0；散列漂移 0。
- STEP 单零件回读：20/20 单实体、体积一致。
- 新增候选已知材料质量：1,293.360439 g；不含夹爪真实多材料质量、HDRM、相机、连接器和紧固件完整质量。
- 基座 Stage B Rev-B2：最大局部外廓 170 mm；M6 孔中心到局部边缘 15.0 mm，孔边净韧带 11.7 mm。
- 静态线束：OD 9 mm，Bezier 最小曲率半径 114.664713 mm。

## 4. 下一次原生执行条件

只有同时满足以下条件才进入 SolidWorks 写入轮：稳定可用物理内存至少 6 GiB；由当前用户人工启动 SolidWorks 2024 SP05；attach-only 预检通过；新 run-id 目录不存在；输入与模板散列完全匹配。原生构建与冷验证必须使用两个干净 SolidWorks 会话。

当前安全门位于 `99_tools/mfinal_solidworks_v4_attach.py`。它不会自行启动或关闭 SolidWorks，也不会把静态校验冒充冷重开验收。

## 5. 可接受的当前签署语义

可以签署：

`F3R2_V4_COMPETITION_NEUTRAL_MECHANICAL_DESIGN_BASIS`

不可以签署：

- `FINAL_NATIVE_CAD_BASELINE`
- `MANUFACTURING_RELEASED_BASELINE`
- `LAUNCH_OR_FLIGHT_QUALIFIED_BASELINE`
- `FULLY_AUTHORIZED_SERVICE_AND_GRASP_TRAJECTORY`

