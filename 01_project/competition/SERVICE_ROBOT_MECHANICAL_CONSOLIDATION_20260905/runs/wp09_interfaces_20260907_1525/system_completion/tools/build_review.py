"""Build the human entry point from real, completed delivery receipts."""
import csv, html, json
from pathlib import Path
from datetime import datetime, timezone
C=Path(__file__).resolve().parents[1]
def read(rel): return json.loads((C/rel).read_text(encoding='utf-8-sig'))
def href(p):
    p=Path(p)
    return p.relative_to(C).as_posix() if p.is_absolute() else p.as_posix()
native=read('results/NATIVE_DELTA_DELIVERY.json')
portable=read('results/PORTABLE_DELIVERY.json')
electric=read('results/ELECTRICAL_REFERENCE_DELIVERY.json')
accept=read('results/SYSTEM_ACCEPTANCE_REVIEW.json')
mass=read('results/MASS_ROLLFORWARD_873.json')
independent=read('results/INDEPENDENT_DELTA_REVIEW.json')
assert str(native.get('status','')).startswith('PASS'),native.get('status')
assert str(electric.get('status','')).startswith('PASS')
assemblies=[Path(native['assembly_paths'][s]) for s in ('service','parking','released')]
assert len(assemblies)==3
images=[Path(p) for p in native['png_paths']]
zips=[Path(native['archive']['path'])]
native_links='\n'.join('- ['+p.stem+']('+href(p)+')' for p in assemblies)
ziplinks='\n'.join('- ['+p.name+']('+href(p)+')' for p in zips)
ziplinks+='\n- [原生电气与 DM 离线参考包]('+href(electric['archive']['path'])+')'
entry=f'''# WP09R 机电设计增量与原生装配交付

2026-09-07。此次完成太阳翼叠层几何修订、R01 标准件修正、三态原生装配增量和可迁移交付核查。**完整机电系统详细设计尚未完成，不能签发总体设计完成状态。** 高功率星上支路、真实停止驱动与回生、推进受控接口、完整线束以及全系统热/强度/运动验证仍有尚未完成的设计责任。

从 [可视化查看页](REVIEW.html) 查看实际 CAD 图像与文件；从 [机器交付状态](results/DELIVERY_STATUS.json) 核对结论。

## 三态实际 SolidWorks 装配

{native_links}

原生装配及全部零件引用在短名 cad 目录。完整包请解压到较短本机路径后再打开，避免 Windows 长路径问题。装配计数、冷重开、依赖和迁移证据均来自 [实际回执](results/NATIVE_DELTA_DELIVERY.json)。固定姿态和实体通过不代表全部运动配合、强度或电气功能通过。

{ziplinks}

## 本轮实际变更

|对象|实际工作|适用范围|
|---|---|---|
|太阳翼|3.0→4.5 mm 叠层步距，8 个边框形体修订、24 个旧实例几何或姿态更新、168 个面层实例加入|84 个 CIC 代理只表示玻璃外形，另有 84 个有限胶层；焊片外伸和胶材仍未完整绑定|
|R01 设备连接|128 个紧固件实例绑定 4 类标准件并改正形体|螺纹省略的采购件定位代理；不冒充制造螺纹和完整预紧强度验证|
|展开路径|四段串联铰链路径，776 个连续区间独立复算|六块分层矩形面板下界 0.30064349 mm；整机/线束/焊片不在此证明范围|
|电气交付|85 份原样 ECAD/DM 文件迁移；重新导出 47 网络一致；地面板 DRC 与 29 项 Python 离线测试通过|系统原有 1 项 ERC 停止链边界问题仍在；Rust 本体、硬件 I/O 未执行|
|质量|最终实例责任结转、R01 材料模型及新增太阳层单独记账|归属完整不等于全部有数值质量；全星质量/质心/惯量未以未知填零|
|资源|退出已确认自有 CAD 进程、回收闲置工具工作集、分批导入和逐态冷重开|启动可用内存门槛 2048 MiB；运行全局可用内存门槛 512 MiB；Python+自有 SW 按 1400 MiB 阈值采样保护，触发后清理再续跑|

[装配说明](mechanical/ASSEMBLY_DELTA_ZH.md) · [太阳翼布局和来源](solar/SOLAR_DESIGN.md) · [紧固件选择](mass/R01_FASTENER_SELECTION.csv) · [来源修订勘误](review/SOURCE_REVISION_ERRATUM.json) · [873 实例质量账](review/MASS_ASSIGNMENT_873.csv)

太阳翼和紧固件来源文档中的“待执行 CAD”保留其源码交付时刻的身份；本轮随后完成的原生执行以 NATIVE_DELTA_DELIVERY 回执为准。8 件边框的 SW 质量属性体积与 OCC 默认积分存在差异，已用同内核回导 STEP、高精度积分和双向布尔差检查几何等价；没有把质量标量差异改成通过，也没有重测全部 1254 个实体。

## 机电系统实际判定

[统一验收表](review/SYSTEM_ACCEPTANCE_MATRIX.csv) 与 [复核结论](review/SYSTEM_REVIEW_ZH.md) 区分了已完成子项、未实现设计和未执行物理检查。既有 705 组件母版另行完成了两个目录位置的三态冷重开，共 6 次通过；[便携母版回执](results/PORTABLE_DELIVERY.json) 与新增量互为父子证据。

[电源推导](power/POWER_DESIGN_UPDATE.md) 保留 360 W 筛查工况。两套 MB-2590-300 与 i7C 的组合只是进入详细评估的候选，均流/充电/BMS/热接口和完整支路尚未实现，不能以额定瓦数相加宣布闭环。

[停止监督源](control/README.md) 实际通过 13 项离线策略测试；驱动 PCB、独立停止硬件、掉电回生与机械承托尚未完成。170–230 ms 的看门狗候选不能满足既有 0.1 s 故障分断要求。

[推进选型复核](propulsion/PROPULSION_SELECTION_REVIEW.md) 已核查四个实际候选，并保留同料号 C-POD 两份官方数据表的冲突。未取得适用硬件/固件版本的喷口坐标、允许并发、针位及命令/遥测 ICD，不能据公开盒体尺寸制造出真实推进控制接口。

原 24 项物理检查仍未执行；未采购、制造、接电、动作、校零、刷固件、充装或承压。新物理设计不继承原动力学科学 Gate 的通过结论。 [母版 320 文件保留检查](results/PARENT_PRESERVATION.json) 与 [本轮完整性检查](results/FINAL_INTEGRITY.json) 仅证明文件和证据链。
'''
(C/'README.md').write_text(entry,encoding='utf-8')
rows=list(csv.DictReader((C/'review/SYSTEM_ACCEPTANCE_MATRIX.csv').open(encoding='utf-8-sig')))
# Keep the reviewed schema intact in the UI; no inferred percentage or green system-complete badge.
cols=list(rows[0]) if rows else []
table='<tr>'+''.join('<th>'+html.escape(k)+'</th>' for k in cols)+'</tr>'
for row in rows:
    table+='<tr>'+''.join('<td>'+html.escape(str(row[k]))+'</td>' for k in cols)+'</tr>'
cards=''.join('<a class="file" href="'+href(p)+'">'+html.escape(p.stem)+'<small>原生 SolidWorks 装配</small></a>' for p in assemblies)
imgs=''.join('<figure><img loading="lazy" src="'+href(p)+'"><figcaption>'+html.escape(p.stem)+' · SolidWorks 实际导出图像</figcaption></figure>' for p in images)
downloads=''.join('<a href="'+href(p)+'">'+html.escape(p.name)+'</a>' for p in zips)
downloads+='<a href="'+href(electric['archive']['path'])+'">原生电气与 DM 参考 ZIP</a>'
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WP09R 机电设计交付</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f8;color:#172437;font:16px/1.7 "Microsoft YaHei",sans-serif}main{max-width:1320px;margin:auto;padding:40px 28px}h1{font-size:36px;line-height:1.3;margin:12px 0}h2{font-size:24px;margin:35px 0 16px}p{max-width:1050px}a{color:#075da8}header{border-bottom:1px solid #cbd4dd;padding-bottom:26px}.eyebrow{color:#637487;letter-spacing:2px;font-size:13px}.status{background:#fff0d5;border-left:5px solid #b97012;padding:16px 20px;border-radius:5px;margin:22px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.file{display:block;background:white;border:1px solid #cbd4dd;border-radius:8px;padding:22px;text-decoration:none;font-weight:700}.file small{display:block;font-weight:400;color:#617184}.downloads{display:flex;gap:20px;flex-wrap:wrap;margin:22px 0}figure{margin:18px 0;background:white;border:1px solid #dae1e7;border-radius:8px;overflow:hidden}figure img{display:block;width:100%;max-height:850px;object-fit:contain}figcaption{padding:10px 18px;color:#536578}details{background:white;padding:16px;border:1px solid #d2dbe3;margin-top:16px}summary{cursor:pointer;font-weight:bold}.table{overflow:auto}table{border-collapse:collapse;min-width:1100px;font-size:13px}td,th{padding:10px;border:1px solid #dde3e8;vertical-align:top;max-width:320px}th{background:#eef3f7;text-align:left}.note{font-size:14px;color:#526376}footer{margin:36px 0;color:#607286;font-size:13px}@media(max-width:700px){main{padding:24px 16px}.grid{grid-template-columns:1fr}h1{font-size:28px}}</style><main><header><div class="eyebrow">WP09R · 2026-09-07 · LOCAL ENGINEERING DELIVERY</div><h1>服务星与 B601 DM<br>机电设计增量和原生装配</h1><p>太阳翼叠层修订、设备标准件替换、三态 CAD 集成，以及原生电气与协议离线文件的迁移核查。</p><div class="status"><strong>完整机电系统详细设计：尚未完成</strong><br>已完成的几何和可迁移交付有独立证据；星上高功率支路、停止回生、真实推进接口和全系统验证仍包含未完成设计。</div></header><h2>直接查看原生装配</h2>'''+ '<div class="grid">'+cards+'</div><div class="downloads">'+downloads+'</div><p class="note">解压到短本机路径后使用 SolidWorks 打开。冷重开证明文件与依赖可用，不证明真实装配、运动安全或飞行鉴定。</p>'+imgs+'''<h2>设计源与证据</h2><p><a href="README.md">交付说明</a> · <a href="mechanical/ASSEMBLY_DELTA_ZH.md">装配变更说明</a> · <a href="solar/SOLAR_LAYOUT.svg">太阳翼排布图</a> · <a href="review/MASS_ASSIGNMENT_873.csv">质量责任账</a> · <a href="results/NATIVE_DELTA_DELIVERY.json">原生验收回执</a></p><p><a href="power/POWER_DESIGN_UPDATE.md">电源与回生计算</a> · <a href="propulsion/PROPULSION_SELECTION_REVIEW.md">推进模块核查</a> · <a href="control/README.md">停止监督实现</a> · <a href="electrical_reference/package/START_HERE_ZH.md">原生电气和 DM 文件</a></p><details><summary>展开完整验收责任表</summary><div class="table"><table>'''+table+'</table></div></details><footer>当前源与实际执行记录可追溯。未变对象按哈希继承；物理检查未执行；原始负结果保留。<br><a href="results/DELIVERY_STATUS.json">机器状态</a> · <a href="results/FINAL_INTEGRITY.json">文件完整性</a></footer></main></html>'
(C/'REVIEW.html').write_text(page,encoding='utf-8')
print(json.dumps({'readme':str(C/'README.md'),'review':str(C/'REVIEW.html'),'native_links':len(assemblies),'actual_images':len(images)}))
