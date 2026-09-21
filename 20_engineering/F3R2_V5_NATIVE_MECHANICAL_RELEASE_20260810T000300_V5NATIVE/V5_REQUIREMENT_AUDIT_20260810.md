# F3R2 V5 机械主线要求审计（2026-08-10）

当前机器裁决：`TOOLING_HOLD`（可用内存 3.02 GiB，SolidWorks 2024 SP05 在运行）。

| 要求段 | 状态 | 证据 / 说明 |
|---|---:|---|
| 1 真值保护 | PASS | URDF/质量预算/F3R1/F3R2/V2_2 哈希 6/6 未漂移 |
| 2 G0 门禁 | HOLD | 内存 3.02 GiB < 6 GiB；不伪造 PASS |
| 3 V5 唯一树 | PASS | `F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE` |
| 4 M-FINAL-01 基座 | 部分 PASS | Rev-B2 零件与子装配原生 PASS；顶装复测待 Loop2 |
| 5 M-FINAL-02 翼根 | 部分 PASS | donor 零件/U 耳/保持件 PASS；真铰链六配置待 Loop1B |
| 6 M-FINAL-03 G07/G08/Mid | 部分 PASS | 原生子装配 PASS；顶装面距/干涉待 Loop2 |
| 7 M-FINAL-04 HDRM | PENDING | 六状态原生功能样机待 Loop1D |
| 8 M-FINAL-05 相机/线束 | PENDING | 相机保持 UNSELECTED/HOLD；线束静态包络已导入 |
| 9 M-FINAL-06 夹爪 | PENDING | 57 实体三零件与棱柱装配待 Loop1C0/1C1 |
| 10 姿态 Authority | HOLD | 三个运行时输入保留；服务姿态需人工授权 |
| 11 原生连续路径 | PENDING | 待 Loop1E 顶装后 Loop2 |
| 12 紧固件 | PASS（原型级） | `V5_FASTENER_REGISTER.csv` 8 行；`FORMAL_LAUNCH_FASTENER_MOS=HOLD` |
| 13 质量/质心/惯量 | 部分 PASS | 16 项来源分级种子已建；原生测量待 Loop3 |
| 14 工程图/BOM | 部分 PASS | 原生 BOM 种子 49 行已建（`08_bom/V5_NATIVE_BOM_SEED.csv`）；工程图/正式 BOM 待 Loop3 |
| 15 数字线程 | PASS | 六文件 Loop3 静态审计 PASS |
| 16 Pack-and-Go | PENDING | 待顶装后执行 |
| 17 双会话冷重开 | PENDING | 旧 Session B 已失效；新会话重认证机制就绪 |
| 18 人审图册 | PENDING | 22 张 RAW/ANNOTATED 待截图 |
| 19 Loop 工程 | 进行中 | Loop1 静态就绪；Loop2/3 按依赖 PENDING |
| 20 最终 Gate | PENDING | 未达任何最终称谓 |
| 21 冻结规则 | 待生效 | 最终 Gate 通过后 `FREE_MECHANICAL_CAD_AUTHORING=PROHIBITED` |

## 唯一阻塞

可用物理内存不足 6 GiB。原生写入只有在稳定达标后开始；当前不伪造 G0/native PASS。

## 下一动作（内存达标后自动执行）

`G0 smoke + Session B 冷重开 → V5_SESSION_REQUALIFY → Loop1B → Loop1C0/1C1 → Loop1D → Loop1E → Loop2 → Loop3 → FINAL GATE`
