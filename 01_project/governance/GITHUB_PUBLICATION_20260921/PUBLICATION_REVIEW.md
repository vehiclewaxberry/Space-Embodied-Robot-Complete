# 完整硬件包公开发布独立审阅（2026-09-21）

用户已授权将完整硬件设计及必要依赖公开到 `vehiclewaxberry/Space-Embodied-Robot-Complete` 并替换远端旧内容。本审阅只读检查 `20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921`，未改原包、未上传、未代作者选择开源授权。

可作为**长期迭代的四系统硬件数字设计候选**准备发布；不能称整星设计完成、可采购制造、可上电或飞行就绪。现有 OPEN_ITEMS 和机器状态已诚实保留这些边界，它们本身不阻止开发态公开。公开发布授权与第三方授予的再分发权分别记录。

## 可立即执行的发布修整

| 项目 | 核验结果与执行建议 |
|---|---|
| Plotly 查看器 | R6H HTML 内嵌 Plotly.js **3.1.0**，有版权标记但无完整 MIT 原文。已从[官方精确版本](https://raw.githubusercontent.com/plotly/plotly.js/v3.1.0/LICENSE)取得 `license_candidates/Plotly.js_v3.1.0_LICENSE.txt`；1086 字节，SHA256 `8c45d9eaf50c2f72dd9c7ab9ef440788ba58a3538484b5c51c1f17d5128752e7`。将该文件和明确的组件归属添加到发布暂存包即可；原包未改。 |
| 已有具名开源来源 | 保留 reBot / BIRDSX / LC2102 / motorbridge 的各自原文和来源身份；四份许可不能成为全仓统一许可证。oresat 只有 FETCH 声明，不能写成已取得且适用于其全部版本/文件的许可全文。 |
| KiCad 库 | 32 个选中系统资产标识为官方 KiCad 库（符号/封装20、模型12），现有 `02_electrical/third_party_notices/` 已包含许可与获取记录。保留这些文件；[官方库许可](https://www.kicad.org/libraries/license/)与设计例外应按库副本及使用库的项目分别处理。 |
| B601 历史断言 | 当前[官方 reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm)与本地 LICENSE/README 指向硬件 CERN-OHL-W-2.0；旧远端“B601 一概只准内部研究、不能再分发”没有当前依据，勿复制。仍需保留实际来源版本、派生修改记录；这不覆盖无关 OEM 零件。 |
| 项目自有材料库 | `GROUND_CANDIDATE_MATERIALS.sldmat` 来自项目 `assign_native_materials.py::make_database` 生成的四项密度 XML；未识别为复制商业 SolidWorks 材料库。旧 local_only 标签不是排除理由，保留候选材料限制。 |
| 自有授权 | 作者未选择统一开源许可证不妨碍按其请求公开自有材料，也不授权代理替作者放弃权利。GitHub 公开可见与允许任意再利用不同，参见[GitHub 授权说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)。 |

## 5 个 Molex 模型：具体的 3D 完整性缺口

`02_electrical/MODEL_DEPENDENCIES.json` 共19个精确模型依赖，已带14个，缺5个。核对已安装目录 `G:/Windows_program_file/Kicad/share/kicad/3dmodels/Connector_Molex.3dshapes` 的89个文件，以下精确名称均不存在，不能从该已装目录直接补齐：

- `Molex_Micro-Fit_3.0_43045-0200_2x01_P3.00mm_Horizontal.step`
- `Molex_Micro-Fit_3.0_43045-0400_2x02_P3.00mm_Horizontal.step`
- `Molex_Micro-Fit_3.0_43045-0600_2x03_P3.00mm_Horizontal.step`
- `Molex_Micro-Fit_3.0_43045-0800_2x04_P3.00mm_Horizontal.step`
- `Molex_Micro-Fit_3.0_43650-0200_1x02_P3.00mm_Horizontal.step`

这五项影响 PCB 3D 查看/完整 STEP 导出，不阻止现有原理图和 PCB 文本解析。完整硬件依赖的目标要求取得精确型号模型并核对来源、许可、几何和相对路径；不能换近似件或改扩展名伪装完成。此处仅检验指定已装目录，不声称全盘不存在。后续暂存包若补齐，应更新依赖账并重新检查；本审阅快照不继承后续通过状态。

## Wurth：存在具体条款，适用范围仍待确定

两个独立上游资产为：

- `02_electrical/kicad/wp10/WP10_TERMINALS.pretty/MP_Wurth_WP-THRSH_74651195R.kicad_mod`，SHA256 `a7dc274f5838ffdef6f2e2bfd0dce89780e72372413430c726b98ffcf2de0229`。
- `02_electrical/kicad/wp10/models/project/MP_Wurth_WP-THRSH_74651195.step`，SHA256 `dac7e6ef1bad5864510c98dde5ba9913ea084e7800e1f4df7eb36fdde3c83968`。

[原厂 WP-THRSH 产品页](https://www.we-online.com/en/components/products/WP-THRSH)公开提供相同 [KiCad rev26b ZIP](https://www.we-online.com/components/products/download/KiCad_WP-THRSH%20%28rev26b%29.zip) 和 [74651195 rev1 STEP](https://www.we-online.com/components/products/download/74651195%20%28rev1%29.stp)。本地ZIP有17个条目，无以 license/readme/terms/notice 命名的条目；这既不证明许可，也不证明禁止。

官网 [Imprint](https://www.we-online.com/en/service/imprint)保留版权，并限制为商业目的复制、分发、修改或提供网站内容给第三方。官方德国 eiSos [General Terms §8.3](https://www.we-online.com/files/pdf1/gtc-we-eisos-germany-en.pdf)另规定：向客户提供的图纸、模型等用于合同履行，向第三方提供需书面同意。后者面向客户合同，本次未取得其对免费公开 CAD 下载的具体适用约定；未找到这两个文件的专门再分发许可证，也未找到明确针对本次非商业公开 GitHub 场景的许可或禁止。

因此结论是 **OEM 再分发范围未明，且有实际限制性条款需要保留**。不能因旧 NOT_CLEARED 标签自动删除，也不能把公开下载变成 MIT/可商业再用授权。发布说明需将 OEM 权利与自有设计分开、提供原厂获取链并避免再许可承诺。若需要肯定的完全再分发授权，取得针对文件的许可，或以项目独立编写的同接口模型/封装替代；这属于后续明确动作，不是本审阅已完成项。

同一几何已传播至 MAIN 电路板和机械总装：`wp10_main_input.kicad_pcb` 中有4个封装实例；源 MAIN_GEOMETRY_COVERAGE 绑定 J204/J205/J206/J207。还涉及：

- `01_mechanical/native/P_f011e65d5e5452c37d2b_e3e9a9.SLDPRT`
- `01_mechanical/step/R6H_MAIN_PCBA_INSTALLED.step`
- `01_mechanical/views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html`

若选择仅保留来源链接的替换路线，不能只移走两个独立文件便称已剔除全部副本；需要同步处理嵌入内容并复验装配。当前审阅没有擅自这样修改或缩减用户要求的完整包。

## 私人路径、凭据与可移植性

扫描960个当前文件、150447159字节，包含原生文件 UTF-8/UTF-16 可见字符串。高特征令牌、私钥头、URL内嵌用户名密码等模式命中 **0**；`C:/Users/...` 类个人路径 **0**；55个文件含 F/G 绝对路径。未披露实际秘密值。

F/G 路径主要需要按执行入口、来源证据或原生残留分别处理。发布暂存包的运行路径应相对化，并保留源文件到公开文件的哈希映射；历史溯源里的机器路径不等于凭据，不能为“清理”篡改原始证据。已有两处冷开结果是机械构建者的验证，本审阅没有重启 CAD/ECAD。未做旧 Git 历史、每个 OLE 自定义属性或所有二进制语义的穷尽扫描，所以不能把0模式命中称为全面隐私认证。

机器清单、文件哈希、精确缺项和人工裁定见 `PUBLICATION_REVIEW.json`。本报告审阅的是原 compact 快照，不是后续发布暂存包或远端最终提交。
