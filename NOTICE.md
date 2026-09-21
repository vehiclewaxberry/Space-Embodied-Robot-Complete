# 第三方来源登记 / Third-Party Notices

本仓库**不转发（does not redistribute）**下列上游代码库。它们作为参考平台、对标求解器或设计参考在本项目中被使用或对比，请从各自上游获取。

*This repository does not redistribute the upstream libraries listed below. They are used as reference platforms, cross-check solvers, or design references. Obtain them from their respective upstreams.*

本地工作副本位于 `80_third_party/vendor/`（未纳入版本控制）。许可证以**各来源目录中的实际 LICENSE 文件为准**；本表为导航，不替代原文。

---

## 求解器与仿真平台 / Solvers and simulation platforms

| 组件 | 许可（依据本地 LICENSE 文件头） | 在本项目中的用途 |
|---|---|---|
| **Basilisk** | ISC License — Copyright (c) 2016, Autonomous Vehicle Systems Lab, University of Colorado at Boulder | 航天器动力学对标 |
| **Exudyn** | BSD 式条款（"...are permitted provided that the following conditions are..."），见 `vendor/EXUDYN/LICENSE.txt` | 柔性多体 / ANCF 对标 |
| **Chrono** | BSD 式条款（"Redistribution and use in source and binary forms..."），见 `vendor/chrono/LICENSE` | 多体动力学对标 |
| **SPART** | GPL 系（LICENSE 含 GPL 前言"Everyone is permitted to copy and distribute verbatim copies..."），见 `vendor/SPART/LICENSE` | 空间机器人学运动/动力学对标（实测跑通） |
| **SpaceDyn** | **未随附 LICENSE 文件** — 使用前须回上游确认授权条款 | 空间机器人动力学历史参考 |

> ⚠️ **SPART 为 GPL 系强 copyleft，SpaceDyn 无随附许可**。若将其代码并入本项目发布物，需先做许可相容性审查。当前二者仅作为**独立对标工具**在本地使用，未并入本仓库任何交付物。

## 机器人学与具身智能 / Robotics and embodied AI

| 组件 | 许可（依据本地 LICENSE 文件头） | 用途 |
|---|---|---|
| **Astrobee** (NASA) | Apache License | 在轨自由飞行机器人参考 |
| **Space Robotics Bench** | Apache License | 空间机器人任务基准参考 |
| **OpenVLA** | MIT License | 视觉-语言-动作模型参考（规划态，未实施） |
| **openpi** | Apache License | 机器人策略模型参考（规划态，未实施） |

## 硬件设计参考 / Hardware design references

| 组件 | 许可 | 用途 |
|---|---|---|
| **reBot-DevArm** | **CERN Open Hardware Licence v2 — Weakly Reciprocal (CERN-OHL-W v2)** | 机械臂开源硬件参考 |
| **BIRDSX-CAD** | 见 `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/LICENSE` | 立方星构型参考 |
| **LibreCube / LC2102** | 见 `80_third_party/external/spacecraft_layout_refs/librecube/LC2102/` | 模块化开源空间系统接口思想参考（未深入代码） |
| **OreSat 12U** | CERN-OHL-S（**强互惠 / Strongly Reciprocal**） | 12U 结构基准实测参考 |

> ⚠️ **CERN-OHL-S 为强互惠许可**。若本项目的机械设计构成 OreSat 的**衍生设计**，分发时须按 CERN-OHL-S 提供完整设计源。当前 OreSat 仅用作**尺寸与面密度基准实测对照**（侧板 226.30×340.50×11.5 mm / 0.4118 kg，面密度 4.22 vs 4.33 互证），未复制其几何。若后续引入其结构件，须重新评估。

## 供应商模型 / Vendor models

| 组件 | 来源 |
|---|---|
| **Damiao DM-J4340P-2EC** 关节模组 | `80_third_party/external/step_parts/damiao_dm_j4340p_2ec/`，来源回执见同目录 `SOURCE_RECEIPT.json` |

---

## 本仓库自有内容 / First-party content

除上述登记项外，`01_project/` `10_research/` `20_engineering/` `30_simulation/` `40_evidence/` `50_literature/` `70_tools/` 下的设计、模型、程序、结果与文档为本项目自有产出，适用根目录 [LICENSE](LICENSE)。

---

*本表依据各来源目录中 LICENSE 文件的实际文件头于 2026-09-21 核验。标注"BSD 式""GPL 系"处表示按文件头特征归类，未逐条比对 SPDX 标识符；正式分发前请以原文为准。*
