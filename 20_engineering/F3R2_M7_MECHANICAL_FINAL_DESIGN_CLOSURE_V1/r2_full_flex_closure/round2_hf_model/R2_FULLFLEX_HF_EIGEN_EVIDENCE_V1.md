# R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1 — 人读版（机器字段以同basename JSON 为准）

- schema: `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1`
- 生成时间：2026-08-23T20:45:41.771960+08:00（宿主机本地钟）
- 生成方：KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) / AGENT-B1 round2_hf_model builder (pure numpy/scipy; upstream read-only)
- 状态：CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED；`next_stage_authorized=false`；`release_credit=false`
- 范围：定基座自由振动，单翼，展开锁定平直构型；ζ=0 守恒审计车道。

## 名义构型前 6 阶模态（N=20/叶，ndof=183）

| # | f (Hz) | 类别 | 主导叶 | 主导柔顺 |
|---|---|---|---|---|
| 1 | 4.3005 | BENDING | leaf-3 | root hinge |
| 2 | 6.2586 | TORSION | leaf-3 | leaf torsion GJ |
| 3 | 18.7800 | TORSION | leaf-1 | leaf torsion GJ |
| 4 | 25.7850 | BENDING | leaf-2 | root hinge |
| 5 | 31.3142 | TORSION | leaf-1 | leaf torsion GJ |
| 6 | 43.8700 | TORSION | leaf-3 | leaf torsion GJ |

## HF 前 3 阶弯曲模态 vs ROM 见证（REPORT ONLY，禁止调参）

| 工况 | HF bending first-3 (Hz) | ROM e21 全精度 (Hz) | 有符号偏差 (%) |
|---|---|---|---|
| nominal | 4.3005 | 25.7850 | 67.4298 | 6.9726 | 39.3586 | 98.0042 | -38.3234 | -34.4870 | -31.1971 |
| all_low | 2.8420 | 16.1557 | 39.8977 | 3.3278 | 18.2952 | 44.1763 | -14.5965 | -11.6944 | -9.6853 |
| all_high | 5.0857 | 31.3689 | 85.2840 | 13.9452 | 78.7172 | 196.0085 | -63.5306 | -60.1499 | -56.4896 |
| root_low_inter_high | 3.4091 | 25.3810 | 75.3830 | 4.3424 | 65.0146 | 190.5319 | -21.4936 | -60.9611 | -60.4355 |
| root_high_inter_low | 3.5874 | 21.4717 | 47.6803 | 4.7369 | 30.2986 | 74.9597 | -24.2659 | -29.1331 | -36.3920 |

锚点漂移（模态1，名义）：-38.3234%（-2.672139 Hz）。偏差归因：叶柔性串联
柔顺（HF 低于刚叶 ROM，阶次越高越显著，第 3 阶落向叶悬臂尺度 49.15 Hz 名义）、多叶
耦合分布曲率、铰柔顺登记带不变（含 latch，SLOT-03）、MC-A 铰质量刚性非随动记账。

## 网格收敛（名义；按阶次对齐）

| # | N=10 (Hz) | N=20 (Hz) | N=40 (Hz) | N20 vs N40 偏移 | 类别 |
|---|---|---|---|---|---|
| 1 | 4.3005 | 4.3005 | 4.3005 | +0.0000% | BENDING |
| 2 | 6.2591 | 6.2586 | 6.2584 | +0.0021% | TORSION |
| 3 | 18.7944 | 18.7800 | 18.7763 | +0.0193% | TORSION |
| 4 | 25.7850 | 25.7850 | 25.7850 | +0.0000% | BENDING |
| 5 | 31.3813 | 31.3142 | 31.2975 | +0.0536% | TORSION |
| 6 | 44.0543 | 43.8700 | 43.8240 | +0.1050% | TORSION |
| 7 | 56.8479 | 56.4558 | 56.3580 | +0.1735% | TORSION |
| 8 | 67.4299 | 67.4298 | 67.4298 | +0.0000% | BENDING |

首 3 阶 |偏移| max = 0.019277%（门槛 <1%）。

## 检查摘要

- 质量闭合：HF 动能叶质量 0.534399107142857 kg（期望 0.54）
  + 刚性记账 0.24 = 0.774399107142857 kg/翼（期望 0.78，
  绝对误差 5.601e-03 kg）。
- SPD：M min-eig 1.636777e-09；K（锁定名义）min-eig
  1.026489e-01；min ω² 7.301135e+02。
- 解锁零空间健全性：k_root=k_inter=0 时恰 4 个近零
  特征值（期望 3：根铰/铰1/铰2 三刚体链转；扭转车道因根端夹紧无刚体模态）→ FAIL。
- 刚化极限：EI×1e9 时 HF 弯曲前 3 阶 vs ROM 全精度 max 相对差
  1.472e+00 → FAIL。
- ROM 独立复现：Mqq max-abs 差 1.324e-02 kg·m²；
  五工况频率 max-abs 差 1.245e+02 Hz。

## 意外与观察（逐字自证据 JSON）

- torsion interleave: at nominal GJ (1.5228 N m2) the first TORSION mode sits at overall rank 2 (6.2586 Hz), i.e. inside the ROM bending witness band [6.9726, 39.3586, 98.0042] Hz; the ROM is bending-only, so all HF-vs-ROM comparisons are made on BENDING-classified modes only
- anchor drift: HF bending mode 1 = 4.300463 Hz vs ROM witness 6.9726 Hz (-38.3234 pct, -2.672139 Hz) - leaf flexibility adds series compliance; report only
- mode 3 deviation is the largest (-31.1971 pct nominal): the ROM third mode (98 Hz) is a rigid-leaf chain artifact; with leaf elasticity the third bending mode drops toward the leaf-cantilever scale (49.15 Hz nominal standalone)
- case all_low: first torsion mode rank 2 (6.2586 Hz); band corners re-order the torsion/bending interleave
- case all_high: first torsion mode rank 2 (6.2586 Hz); band corners re-order the torsion/bending interleave

## 扭转/阻尼角点（新车道）

- GJ 角点：GJ_low=0.135687 / nominal=1.522824 / high=17.090769 N·m²（名义刚度、
  名义 EI 下各跑一组特征值，见 JSON eigen_cases）。
- ζ 角点（耗散车道 report-only）：ζ ∈ {0.002, 0.005, 0.02}；阻尼频率偏移
  √(1-ζ²) 与衰减时间常数见 JSON damping_lane；守恒结论一律出自 ζ=0 车道。

## nonclaims（逐字）

- this is NOT a ROM: no modal truncation is delivered for dynamics consumption
- this is NOT a coupled/free-floating evaluation: fixed-base per-wing eigen only
- r2_full_flexible_coupling stays NOT_EVALUATED; this file does not close it
- e15 REPEAT_ANCF_CERTIFICATION is unchanged; no recertification run is authorized
- no measurement authority: every stiffness/damping band is PROVISIONAL_DERIVED
- no production/manufacturing/qualification/launch/flight authority
- GAP-12 whole-satellite mass budget reallocation untouched (stays OPEN)
