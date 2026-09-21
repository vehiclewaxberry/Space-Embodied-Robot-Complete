# 第三方来源与许可说明

本说明记录精简硬件设计包涉及的具名上游许可来源，更新于 2026-09-21。下列许可文本从本地保留的上游文件逐字节复制，未改变其版权、许可和免责条款。

这些许可分别适用于其对应的上游材料；**不构成对整个硬件包的统一 MIT、CERN-OHL 或其他授权**。具体哪些选中资产来自、修改自或仅参考了某个上游，仍须由逐文件来源、版本、修改记录和发布清单确定。下表也不表示各上游的完整仓库被包含在本包中。

| 具名上游 | 已识别文本/声明 | 随包记录 | 范围说明 |
|---|---|---|---|
| reBot-DevArm（B601 相关机械臂来源） | CERN Open Hardware Licence Version 2 — Weakly Reciprocal；`CERN-OHL-W-2.0` | [许可原文](licenses/reBot-DevArm_LICENSE_CERN-OHL-W-2.0.txt) | 仅对应此上游及实际适用的派生材料，不能覆盖其他厂商部件或整星设计 |
| BIRDSX-CAD | MIT；Copyright (c) 2024 BIRDS Project, Kyushu Institute of Technology | [许可原文与署名](licenses/BIRDSX-CAD_LICENSE_MIT.txt) | 仅对应 BIRDSX-CAD 的适用材料 |
| LibreCube LC2102 | CERN Open Hardware Licence Version 2 — Weakly Reciprocal；`CERN-OHL-W-2.0` | [许可原文](licenses/LC2102_LICENSE_CERN-OHL-W-2.0.txt) | 独立保留 LC2102 本地原件，不因与 reBot 同名许可而丢弃其来源身份 |
| motorbridge | MIT；Copyright (c) 2026 motorbridge | [许可原文与署名](licenses/motorbridge_LICENSE_MIT.txt) | 仅对应 motorbridge 的适用材料，不自动覆盖邻近 EDA 库或 OEM 来源 |
| oresat-kicad | 本地获取记录称上游 README 声明 `CERN-OHL-S-v2-or-later`；记录指向 SPDX 标准文本 | [原获取/声明记录](licenses/oresat-kicad_LICENSE_FETCH.json) | **只有来源声明记录**；本包没有将标准许可证模板当作已取得、已绑定具体版本和所有文件的项目许可全文 |

## 尚需按实际选中资产核对的范围

其他 OEM 图纸与数据页、厂家 CAD/STEP、KiCad 符号/封装/三维模型、第三方材料库，以及查看器中可能嵌入的 Plotly 或其他软件库，应按本包实际选中的文件、版本和派生关系分别核验。没有文件级来源与适用许可绑定的资产保持“待核验”；本说明没有批准其全部再分发，也没有把“能够下载”视为“可以再发布”。

尤其需要区分：原始厂商资产、转换格式后的副本、修改后的设计和仅用于说明的引用。格式转换、加入总装、包络简化或嵌入 HTML 均不自动赋予本项目对上游材料的新许可。对应的来源、版权说明和适用条款应随实际公开材料保留。

## 自有材料

本项目自有硬件设计、代码、说明文档与数据的授权方案尚未在此文件中选择。这里不代作者新增许可证，也不把上述第三方许可证套用于自有或权属未确定的材料。公开版本的资产范围、第三方逐项核验和自有授权决定应另行记录。

本说明仅涉及硬件设计包，不包含研究或控制目录内容。
