# V5R-RAPID 写入边界（WRITE BOUNDARY）

- 轮次：`V5R_RAPID_MECHANICAL_CLOSURE`
- 建立时间：2026-08-20T04:52:28Z
- Git 快照：`5c5addea00ddb70d86a5cc37a88bbcda50350e43` @ `publication/stage3-integrity-closure`（dirty 92 项）
- 备份回执：[BACKUP_RECEIPT.json](BACKUP_RECEIPT.json) → `V5R_PHASE0_BACKUP_AND_WRITE_BOUNDARY_ESTABLISHED_VERIFIED`

---

## 1. 唯一允许写入的目录

```
20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/
├── 00_authority/        权威裁决与输入清单
├── 01_native_cad/       V5R 轻量原生零件与子装配
├── 02_interfaces/       M3R 两级转接、接触区、载荷路径
├── 03_configurations/   构型矩阵、包络、干涉矩阵
├── 04_validation/       质量/惯量/坐标映射、单位载荷、模态筛查
├── 05_drawings/         工程图、BOM、接口控制图
├── 06_pack_and_go/      Pack and Go 独立重开验证
├── 07_evidence/         哈希清单、截图、备份回执
├── 08_gate/             机器可读 Gate JSON
└── 99_tools/            本轮脚本
```

本轮**新建**目录，快照时不存在。备份核验将本目录从两侧同时排除（理由见回执 `verification.scope_exclusion`）。

## 2. 逻辑只读资产（禁止回写）

以下六项在 `M3R_INTERFACE_AUTHORITY_GATE.json` 中登记为 `protected_assets`，Phase 0 已逐项复核哈希，**6/6 全部吻合**：

| 资产 | 路径 | 状态 |
|---|---|---|
| accepted B601 URDF | `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` | 双口径吻合 |
| 质量惯量台账 | `20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv` | 吻合 |
| V2_2 原生 donor 顶装 | `20_engineering/cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM` | 吻合 |
| B51 受保护 donor | `20_engineering/cad/B5_1_B601_interface_closure_candidate/.../B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM` | 吻合 |
| F3R1 顶装 | `20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_..._V3_CONFIGURED.SLDASM` | 吻合 |
| F3R2 冻结顶装 | `20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_..._OPERATIONAL_BASELINE.SLDASM` | 吻合 |

**URDF 哈希双口径要求**：`core.autocrlf=true` 会把 292 处 LF 改成 CRLF（11029→11321 字节）。单口径比对会在非事件上触发停机条件。必须同时核验：
- 磁盘 CRLF：`1BC2B748…C164`
- LF 归一化：`408147DD…A3A4`

## 3. 额外只读域（本轮不得写入）

- `20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/` — 原 V5 目录。**仅作失败证据与建模参考**，不得在其中原地修补，不得覆盖任何回执。
- `20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/` — V4 中性 CAD，本轮几何输入，只读引用。
- `20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/` — 含 M3R 权威源与 F3R2 冻结顶装。
- `20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/`
- 所有既有 `*_gate_check.json` / Gate JSON / 阈值 registry。
- 项目根其余七个域（`01_project/`、`10_research/`、`30_simulation/`、`40_evidence/`、`50_literature/`、`70_tools/`、`80_third_party/`）。

## 4. 目录冻结（REORG04）合规

本轮不新建根级目录，全部产物落在既有 `20_engineering/` 域内，符合八域约束。

## 5. 长路径操作规程

`core.longpaths` **未启用**。据此：

- 建立哈希清单**禁止**使用 `git ls-files --others`——它会静默跳过超 MAX_PATH 的目录（实测 git 少看见 196 个文件，439 个文件路径超 260 字符，最长 348）。
- 一律使用 `99_tools/V5R_PHASE0_HASH_MANIFEST.py`（`os.walk` + `\\?\` 扩展长度前缀）。
- 拷贝一律用 robocopy，且必须 `MSYS_NO_PATHCONV=1`，否则 Git Bash 会把 `/E` 改写成 `E:/`，robocopy 静默什么都不拷而 shell 仍报 exit 0。
- 拷贝后必须检查目标目录存在 + robocopy 汇总块，不得以 shell 退出码为准。

## 6. 停机条件（沿用负责人 14 条，本轮已生效检查）

Phase 0 已实测：
- ✅ 可核验备份存在（逐文件 SHA-256，非抽样）
- ✅ 原冻结文件哈希未变（6/6）
- ✅ 未打开 SolidWorks
- ✅ 未修改任何预存资产

## 7. 内存门限

原项目要求 ≥6.0 GiB 可用物理内存方可执行全量原生装配，此前的人工 override **不计为门通过**。SolidWorks 启动前必须实测可用物理内存并写入回执；连续两次内存型崩溃即停止攻击同一路线，转 `NEUTRAL_CAD_PROTOTYPE_BASELINE_CLOSED_NATIVE_CAD_HOLD` 回退路线。
