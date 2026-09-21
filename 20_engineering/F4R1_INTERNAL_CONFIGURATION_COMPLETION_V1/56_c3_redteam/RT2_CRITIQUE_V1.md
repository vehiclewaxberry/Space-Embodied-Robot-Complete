---
title: RT2 质量/质心/姿控接口红队审查（CA-A/CA-B/CA-C）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
author_agent: RT2 redteam（质量/质心/姿控接口）；工具循环事故后由主代理按其完整报告落盘
verification: 数值为红队手工复核；机器验证见 rt_verify.py 输出 RT_VERIFY_OUT_V1.json，差异以脚本为准
---

# RT2 质量/质心/姿控接口红队审查

## 1. 复核基础
重跑 compute_candidates.py 输出逐字节一致（sha256 3729c177…），未改任何既有文件。结构质量与主口径总质量：**CA-A 1.2168 kg→31.2397 kg；CA-B 2.0668 kg→32.0896 kg；CA-C 4.9277 kg（本体 1.3241+钢压载 3.6036）→34.9506 kg**。CDS 口径：CA-C 闭合 x 裕度仅 **+1.14 mm**；CA-A/B 仍超差（−55.43/−50.07 mm）。

## 2. kill-issue：CA-C 压载几何自相矛盾且为裕度致命
压载 pos[-163]+宽 15 mm→跨 [-170.5,-155.5]，越出舱面 −170.25 达 0.25 mm；function 自述宽 14.5 mm↔质量差 120 g→CG_x 移动 ≈+1.45 mm→裕度 +1.14→**约 −0.3 mm FAIL**。闭合裕度小于文件自身簿记噪声。

## 3. ±5% 不确定度传播（待脚本复核的估计）
区间最坏 ΔCG_x≈2–3 mm ≫ 1.14 mm 裕度；蒙特卡洛失败概率估计 10–35%。

## 4. kill-issue：构型错位（OI-3）
CDS 质心要求针对**发射收拢构型**；CA-C 闭合仅对展开构型成立。收拢臂 CG 偏移 >4.7 mm 即吃光 CA-C x 裕度（实际收拢偏移远大于此）。闭合主张落错构型。

## 5. 惯量与锚点登记
- CA-C 主口径 ΔIyy≈+15%、ΔIzz≈+12%、惯量积增量 ~0.04 kg·m²，须登记 sim_08/sim_10；
- sim_10 μ=m_target/24（scan_v0.yaml）：候选主口径质量使锚点漂移 **−23.2%/−25.2%/−31.3%**，哈希锁定锚点须登记重锚；
- 轮组容量缺口：sim_08 actuator_budget.py:116 轮组 0.3 N·m·s（→12× 口径）；C1 选型 4×RW400=30 mNms×4=0.12 N·m·s，**实际缺口 30.4×**（登记点）。

## 6. 压载效率对比
纯压载最小 3.696 kg（与 CA-C 设计一致）；设备重排极限 −9.1 mm（C1 已证不可行）；推进升级 −22.8 mm 单独不足；**混合变体（4×BPX+1.87 kg 压载）+0.27 kg 换 200 Wh 有用质量**——压载不应是纯死重的可行方向（变体研究，不进 C3 构建）。

## 7. 磁清洁
3.6 kg 钢块距磁强计最近表面 ≈65 mm（CG 152 mm），且位于 ANT-S/SS6 后面板设备正后方 → UNKNOWN；条件项：改钨/无磁钢+磁实测。

## 8. verdict
- CA-A = ACCEPTABLE_WITH_CONDITIONS；CA-B = ACCEPTABLE_WITH_CONDITIONS；CA-C = **REJECT (as-published)**。
- kill-issue=裕度级几何自相矛盾+脆弱闭合+构型错位；修复方向：几何修正、裕度重设计 ≥5 mm、钨压载+磁实测、OI-3 闭合后按收拢构型重配平。
