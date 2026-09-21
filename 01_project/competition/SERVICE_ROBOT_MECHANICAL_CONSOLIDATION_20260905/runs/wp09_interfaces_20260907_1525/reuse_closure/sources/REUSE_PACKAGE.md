# 本轮真实复用来源包

这里保存实际取得的源文件与版本记录。用户附件中的索引作为研究参考保存在 `../inputs/`；索引本身不作为下载或本地验收证据。

|来源|锁定版本|实际复用及限界|
|---|---|---|
|[MotorBridge](https://github.com/motorbridge/motorbridge)|`c48ebc4b2f250aa1f411a580d9d7b626e187040f`|协议、串口帧、型号/寄存器及 Python API 源；MIT。18件真实源；Python移植和上游Python方法假ABI执行，Rust本体未执行。|
|[OreSat FlatSat](https://github.com/oresat/oresat-flatsat)|`e997fb732a88809b0ad0dc5ab6828edd77feae05`|主原理图125354 B、PCB982157 B、工程、BOM、库表及历史EAGLE辅助板。上游主图实际打开并导出网表；未把空辅助KiCad图视为电路。|
|[OreSat KiCad libraries](https://github.com/oresat/oresat-kicad)|`fdd45420db40cb4feef138c048a49eeb5911b84b`|实际取SFM封装、测试点封装及连接器/杂项符号库。派生测试板保留5个测试孔的铜箔/钻孔几何，修改丝印可读性，新增10个焊线孔及5条铜线。|
|[ATMOS/PX4](https://docs.px4.io/main/en/frames_spacetug/kth_atmos)|PX4 `0fb3847cd91ebdfb5763357647b326011d95a406`；ATMOS docs `b8f9da43eb70deb497738c202054618889db4b85`|实际8通道构型与消息，详见推进来源清单。地面平面基准不等于VACCO三维在轨ICD。|
|GomSpace、MEAN WELL、E-T-A、Sensata、Samtec、Molex、AZUR、VACCO等原厂|各文件版本见 power / propulsion 合同|厂商公开文档，不意味着取得内部PCB开源设计或本项目环境验证。保留原版本和网页/PDF冲突。|

OreSat README 声明 CERN-OHL-S-v2-or-later，保留 PSAS 上游版权与声明。标准许可全文补存在 [CERN-OHL-S-2.0.txt](oresat-kicad/CERN-OHL-S-2.0.txt)，取得URL/哈希见同目录 `LICENSE_FETCH.json`。本轮派生PCB及相应封装、原理图、生成脚本以 CERN-OHL-S-2.0-or-later 提供，标明2026-09-07项目修改，不继承上游测试结论。现有原厂商标与闭源器件资料不据此改许可。

上游源保持原样；`ecad/upstream_review` 为独立检查副本，其本地库表仅绑定实际使用的库。上游表内其他未使用库不冒充已经下载。主图使用 KiCad9源格式，由实际 KiCad10.0.6 读取；仍有11项同名局部/全局标签警告。上游PCB有2项 courtyard重叠错误和其他警告，详见真实报告。辅助 `.kicad_sch` 232字节为空，EAGLE `.sch/.brd` 未迁移、未验证。

KiCad10.0.6来自[官方Windows下载入口](https://www.kicad.org/download/windows/)，以入口列出的镜像下载967765696 B安装包；Windows Authenticode 验签为有效，签名者 KICAD SERVICES CORPORATION。使用已有7-Zip提取局部运行时，没有运行安装向导、变更全局库表或安装3D图库。运行时放在项目 `70_tools/runtime_wp09_kicad/portable`，命令与CLI哈希见 `../results/KICAD_RUN.json`；配置隔离于本候选。参考[KiCad10 CLI手册](https://docs.kicad.org/10.0/en/cli/cli.html)，实际版本以命令回执为准。

`../results/REUSE_SOURCE_FILES.csv` 将本目录所有取得文件的字节数与SHA256列入交付封包。各代理自己的来源清单同时保留，不把下载失败页面或搜索摘要记为PDF实读。
