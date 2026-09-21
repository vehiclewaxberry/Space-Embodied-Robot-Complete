# F3R1 donor down-select

依据 `F3R1_CANDIDATE_ASSEMBLY_REGISTER.csv`（9 候选逐一哈希登记）。选择规则按 ECR §6：
原生优先 / 引用完整 / B601 链完整 / 与 accepted URDF 一致 / 已有翼与主结构 /
不选零几何文件当顶装。

## 选定

| donor | 内容 | 关键证据 |
|---|---|---|
| **D1 = V2_2_NATIVE**（108 文件全树） | 主结构（5 环框+4 纵梁+3 甲板+6 可拆板）、安装链（扩散板→前端框→法兰→160×160×12 适配板→Ø110 凸台+双载荷桥）、三鞍座塔、左右翼根（各 13 件，含**太阳翼 HDRM** Base×2+Rod×2/侧）、Master Skeleton | 人工裁决 canonical（按哈希 `30C09B50` 绑定）；本轮 108/108 复验 |
| **D2 = B51_ARTICULATED_20260728T008** | B601 六轴铰接臂：8 个厂商 link 件 + 12 个 datum 铰链件 + 25 配合 | 构建 trace `errors:0 warnings:0 full_rebuild:true`；P2 复验 6 关节全 ALIGNED（对 accepted URDF 轴共线、公件原点重合 <0.5 mm） |
| **D3 = V2_2 翼板 4 件** | `WING_L/R_DEPLOYED/STOWED.SLDPRT`（200×227×6 冻结板实体，全局坐标建模） | V2_2 整树=REFERENCE_DONOR_ONLY（人工裁决禁整体合并顶装），**仅取件**合规 |

## 否决

| 候选 | 理由 |
|---|---|
| V2_3 集成树 | R3-02：顶装漂移无受控摘要 |
| B50 q0 刚性臂 | 被铰接版取代 |
| B51R1 carrier pilot R10–R14 | 检查点性质；B51R1 S01 从未产出终骨架（COM 0x8002802B） |
| F3_P3_TOP_ASSEMBLY.FCStd | R3-03；按 ECR 降级 `INCOMPLETE_GEOMETRY_DONOR_AND_AUDIT_EVIDENCE_ONLY` |
| SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd | R3-01 零几何；降级 `STATE_AND_ENVELOPE_REFERENCE_ONLY` |
| V2_1 翼 | 谱系旧于 V2_2 板；翼根站位已被 O9/O10 取代 |

## 已知缺口（选型时即登记，进 Loop 补件）

1. **gripper_left / gripper_right 无独立组件**（P2 判 `G2_PARTIAL`）——donor 手指几何都在
   `B51_REF_gripper_detail_LINKLOCAL` 单件内 → P5 以实体拆分/新建手指件补齐，按 URDF
   prismatic 轴放置。
2. **ARM_HDRM 无任何 donor**（V2_2_NATIVE 的 HDRM 全在翼根，是太阳翼 HDRM）→ 按 P5B
   比赛演示规格（电磁铁+弹簧 6 mm）新建原生件，标 `COMPETITION_DEMONSTRATOR_ONLY`。
3. **相机及支架无 donor** → 新建简单原生支架+相机体（末端/腕/基座三处，FOV 参数取
   F3-P3 报告口径 60°/90°/120°，标定待视觉组）。
4. **接触垫无实体件**（P5B 只有规格矩阵）→ 新建 G07/G08 垫片件，厚度由 P4 posed 实测
   间隙决定；Mid 面到面 2.00 mm 名义。
