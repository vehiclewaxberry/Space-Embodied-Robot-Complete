# B601 Route-C V8 局部硬件设计简报

## 1. 任务与权限

- 任务：在不修改 B601 供方本体、accepted URDF、关节拓扑/限位/惯量、M3R、Gripper R1、Solar R2、MPI、E23 和主结构的前提下，闭合 V7 的 D1/D2/D3 三项 Route-C 局部机械缺陷。
- 设计权威：`DESIGN_CANDIDATE`；不得声明 `AS_BUILT`、`MEASURED`、`FLIGHT_QUALIFIED` 或发布信用。
- 迭代上限：每缺陷最多 3 个不同物理候选；最多 4 次正式 build/sweep 回路。本文件登记第 1 回路。
- 判据：未知量不转为 PASS，null 不填零；诊断通过不等于 Gate 通过。

## 2. 坐标、单位与冻结接口

- 几何单位：mm；质量输出：g/kg；惯量：kg·m²；力矩：N·m。
- Route-C 构建坐标：A0，即 accepted B601 `base_link` 在 q=0 的坐标；运动评估再由 accepted URDF FK 映射至系统 S 系。
- accepted URDF SHA-256：`1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`。
- V7 源 SHA-256：`A25B4E0A028ECAC725433E1D20334E4D1381B7FEACFE769A5773EEEBF026B315`。
- V7 STEP SHA-256：`AE0A70AA441CF948517343F138E87C813D915F3DD656A148D7CA623B7B1D8101`。
- 跟踪管静态降额：安装 0.5 + 几何 1.0 + 热 1.0 + 网格 0.1 = 2.6 mm；9 mm 束半径为 4.5 mm，静态径向包络为 7.1 mm，姿态相关轴误差另算。

## 3. V7 缺陷基线

| 缺陷 | V7 机器证据 | V8 第 1 候选 |
|---|---|---|
| D1 腕部/link4-link3 走廊 | mission fast-check 最差 gated -18.7458 mm；J4 pinch -17.695 mm；J5 pinch -14.561 mm；约 5 mm 走廊小于 7.1 mm 静态径向包络 | `D1-A_HIGH_EXTERNAL_STANDOFF`：把 J5 回路移至外侧 `y≈-150 mm, z=260 mm`，以 `x≈200 mm` 绕过 link4 外缘；设置 R55 折弯和高位回转腿，保持 J6 入口切向连续。预探针 q=0 raw 最差约 +13.86 mm，最小有效半径 55 mm；只作为建模种子。 |
| D2 J1 线圈/link1 凸台 | raw -2.05 mm；pinch gated -4.98 mm；420° 全周使移相无效 | `D2-A_R66_ANNULAR_LOOP`：J1 线圈半径 60→66 mm，同时扩展保护环径向容量；不改关节轴、角覆盖和供方壳体。 |
| D3 J1 导向壁/link2 STOW | WALL -2.913、UP -2.858、LOW -2.788、LINER -0.470 mm | `D3-A_FULL_SECTOR_RELIEF`：对 wall、upper cheek、lower cheek、liner 在 A0 方位角 100°–190° 作完整开口，覆盖已定位的 117.1°–174.3° 接触区；开口端设置局部鞍夹，不切削 link2。 |

## 4. D1-A 名义中心线

- `K2=(115, 51.625, 270)`
- `E1=(200, 51.625, 275)`
- `E2=(200, -90, 275)`
- `J5_C=(105, -150, 260)`，R55，CW 185°
- J5 出口保持 70 mm 切向引出；第二切向点位于出口后 210 mm。
- 高位回转点的 z 与 `A6` 一致；`A6` 沿冻结 J6 入口切向后退 180 mm，随后进入冻结的 J6 螺旋拓扑。
- 每个非共线拐点名义 R55；构建器不得把有效半径夹缩至 54 mm 以下。

## 5. D2/D3 名义几何

- J1 线圈：中心仍与 joint1 轴同轴，`R=66 mm`、`sweep=-420°`、`pitch=-12 mm/rev`。
- annulus lower/upper cheek：`r_out=74 mm, r_in=52 mm`。
- outer wall：`r_out=78 mm, r_in=74 mm`。
- liner：`r_out=69 mm, r_in=63 mm`。
- relief 扇区：100°–190°，切除半径至少 90 mm，轴向覆盖所有四件；不得把 71 mm 外壁半径误写为 D1 的包络需求。
- 端部鞍夹位置按 R66、方位 95°/195° 的线圈中心附近布置；正式接受以 RC-part/vendor cross-clearance 与线束 mission sweep 为准。

## 6. 生成与验证合同

1. 由独立 `B601_ROUTE_C_BUILD_V8.py` 生成 FCStd、STEP、centerline、clamp/guide register、mass-delta 与 receipt；不得覆盖 V1–V7。
2. 生成 V8 mesh pack，并锁定所有文件哈希。
3. 快速检查只作缺陷定位；最终结论必须来自完整 mandatory-state/trajectory sweep、收放、弯曲、pinch、热/安装降额、阻力矩与 RC hardware cross-clearance。
4. 新增高位导向件必须纳入 `SEG_INTENDED_PARTS`，但只有服务自身线段的接触可排除；与其他线段或供方几何的接触仍门控。
5. clamp co-location 必须逐项审计；现有 57.496 mm 最大残差不得被静默当作 PASS。任何豁免必须逐夹具给出物理接口理由。
6. V8 质量/CG/惯量只在最终几何选定后传播。修复 RC-5 的 `composition` 绑定并以九个真实姿态重算；旧 V1 q=0 烟测不得获得 Gate 信用。
7. STEP 必须运行 facts/planes/positioning 检查、V7→V8 diff 和至少一组多视图快照；最后交给 CAD Viewer。

## 7. 本回路的合法结局

- `CANDIDATE_ACCEPTED_FOR_FULL_SWEEP`
- `CANDIDATE_REJECTED_WITH_MACHINE_EVIDENCE`
- `ARCHITECTURE_ESCALATION_REQUIRED`

任何结局均不自动改变 TMG-4、TMG-2、Gate A 或飞行鉴定状态。
