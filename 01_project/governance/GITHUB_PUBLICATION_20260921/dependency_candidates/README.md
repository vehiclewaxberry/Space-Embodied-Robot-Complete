# KiCad 精确 Molex STEP 依赖核验

**结果：0/5 个精确 STEP 取得；5 个原始 3D 依赖缺口保留。**

官方 GitLab 固定提交：`8d4070daa0fa3f7a7f3c176f4ca7bffc4df392be`；核验完成：2026-09-21T10:37:05.640850+00:00。官方完整 `Connector_Molex.3dshapes` 目录共 90 条记录，五个精确文件名均不在其中。

| 精确型号 | GitLab 直接下载 | 归档 GitHub 下载 | 固定 ref 的路径历史 |
|---|---|---|---|
| 43045-0200 | 404 | 404 | 0 条 |
| 43045-0400 | 超时；目录快照确认当前缺项 | 404 | 0 条 |
| 43045-0600 | 404 | 404 | 0 条 |
| 43045-0800 | 404 | 404 | 0 条 |
| 43650-0200 | 404 | 404 | 0 条 |

这里的 404、空历史和网络超时分别记录；未断言这些模型在所有历史分支、厂家或其他来源“从未存在”。GitHub 官方仓库已于 2020 年迁移至 GitLab，归档固定版本只用于补充核对。

已保存原始官方提交元数据、完整目录快照、库许可证和 Molex 署名记录；每份文件的来源 URL、固定 commit 和 SHA256 均见 `MOLEX_DEPENDENCY_CANDIDATES.json`。缺失模型的 hash 明确为 null，不虚构模型许可或几何。

[KiCad 官方许可说明](https://www.kicad.org/libraries/license/)采用 CC-BY-SA-4.0 及 KiCad libraries exception。库文件作为集合再分发仍需保留署名和原许可；该说明不自动许可未取得的 OEM 模型。本目录的官方许可证字节副本为 `evidence/LICENSE.KICAD_LIBRARIES.md`，署名为 `evidence/MOLEX_CREDITS.md`。

未使用近似件、未改 compact 或原理图/PCB、未上传。原 compact 依赖清单 SHA256 前后一致。缺少 3D 模型本身不妨碍加载原理图/PCB；本次未运行 KiCad，不能据此声称新增开档验收通过。

后续发布应保留这 5 项 3D 缺失状态，不能把模型路径字符串或对应 footprint 的存在称为 STEP 已交付。
