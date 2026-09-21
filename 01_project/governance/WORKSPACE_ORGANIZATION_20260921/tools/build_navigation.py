"""Create a lightweight whole-project directory index; preserve original navigation bytes."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv, hashlib, html, json, re, shutil

D=Path(__file__).resolve().parents[1]; ROOT=D.parents[2]
domains=['01_project','10_research','20_engineering','30_simulation','40_evidence','50_literature','70_tools','80_third_party']
labels={'CURRENT_DESIGN':'现行设计','ACTIVE_RESEARCH':'研究模块','SOURCE_DEPENDENCY':'上游来源与依赖','IMMUTABLE_EVIDENCE':'原始证据与回执','HISTORICAL_RETAIN':'历史留存','REGENERABLE_TOOL':'工具与可再生容器','LOCAL_PRIVATE':'本机私有与版本库','REVIEW_REQUIRED':'待确认用途'}
backup=D/'navigation_history'; backup.mkdir(exist_ok=True)
backup_rows=[]
for relative in ['PROJECT_MAP.md']+[f'{domain}/README.md' for domain in domains]:
    source=ROOT/relative; dest=backup/relative
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists(): shutil.copy2(source,dest)
    backup_rows.append({'source':relative,'backup':dest.relative_to(ROOT).as_posix(),'sha256_before':hashlib.sha256(dest.read_bytes()).hexdigest()})

project_map='''# 项目总导航

更新：2026-09-21。本页负责文件用途和入口；工程与科学结论仍以各包的原始裁决为准。

**全项目归档导航：[可搜索目录总览](01_project/governance/WORKSPACE_ORGANIZATION_20260921/WORKSPACE_INDEX.html) · [整理结果与规则](01_project/governance/WORKSPACE_ORGANIZATION_20260921/README.md)。** 原始来源与历史证据多数按用途归档、原位保存，避免破坏引用。

## 日常从这里进入

| 要做的事 | 入口 | 对象与范围 |
|---|---|---|
| 查看四系统硬件主设计 | [硬件精简设计包](20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md) | 机械、电气线束、能源热控、动力推进；当前候选与未完成项均有说明 |
| 打开后续机械臂—服务星总装 | [R6H原总装](20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM)、[可移植副本](20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/01_mechanical/native/SERVICE_STAR_SERVICE_R6H.SLDASM) | 原件保留；没有回退为早期WP03 |
| 接续电气与安装设计 | [R5E电气指针](20_engineering/SERVICE_STAR_ELECTRICAL_LATEST.json)、[R7布局草案](20_engineering/SERVICE_STAR_AUX_STOP_INSTALLATION_R7_20260921/) | 选型候选和未安装草案分别看待，不按日期推定完工 |
| 查上游机械来源 | [WP03](20_engineering/service_robot_wp03_spacecraft_body_r1/README.md)、[工程域](20_engineering/README.md) | WP01/02、R1/R4等仍有消费者；旧目录不是可批量删除清单 |
| 找研究问题与知识 | [研究域](10_research/README.md) | 主题、合同、论文和知识导航 |
| 找计算程序与原始结果 | [仿真域](30_simulation/README.md) | 按模块保留源码、测试、结果和Gate；不集中搬走结果 |
| 找文献和图表 | [文献域](50_literature/README.md)、[展示证据域](40_evidence/README.md) | 全文、阅读卡、题录及生成图表各有用途 |
| 查历史来源或恢复记录 | [治理入口](01_project/README.md)、[本轮归档账本](01_project/governance/WORKSPACE_ORGANIZATION_20260921/README.md) | 物理移动/删除与逻辑分类分开记录 |

## 八个业务域

| 目录 | 保存什么 | 怎样归档 |
|---|---|---|
| [01_project](01_project/README.md) | 项目入口、治理、协作原件与历次工作记录 | competition是沿用的历史名称，其中不少仍是工程来源；按工作包与日期索引 |
| [10_research](10_research/README.md) | 研究主题、方法、合同、知识与论文材料 | 按主题导航，旧阶段计划保留日期 |
| [20_engineering](20_engineering/README.md) | CAD、电气、BOM、参数、接口和设计证据 | 现行设计、上游依赖、历史验证分栏；保持原生引用 |
| [30_simulation](30_simulation/README.md) | 模型、程序、测试、结果、机器裁决 | 模块自包含，保留失败和UNKNOWN |
| [40_evidence](40_evidence/README.md) | 图表、媒体和离线展示 | 原始证据与纯复制展示件区分；可证明的重复件指回规范源 |
| [50_literature](50_literature/README.md) | 题录、阅读卡、BibTeX与全文 | manifest导航；全文与阅读卡不互相替代 |
| [70_tools](70_tools/README.md) | 编目、展示、校验工具及运行环境 | 工具源码、运行时、可再生缓存分开处理 |
| [80_third_party](80_third_party/README.md) | 外部代码、厂家模型与许可 | 保留来源版本、许可、消费者和独立历史 |

## 根配置与保存规则

- `.git`保存版本与LFS对象；`.codex/.agents/.claude`为客户端配置。它们不属于可随意去重的设计副本。
- `AGENTS.md`、`CLAUDE.md`保留客户端工作约定；本页保持唯一全项目根导航，不再建立平行src/docs/results业务树。
- 停用的根MCP配置已原字节移入本地私有档案；活跃配置没有修改。见[归档映射](01_project/governance/WORKSPACE_ORGANIZATION_20260921/ROOT_ARCHIVE_ACTIONS.json)。
- 同名、同日期或位于archive/_work/__cadgen__都不足以证明文件无用。实际清理只认精确候选、可恢复来源与引用核验。
- 本轮导航更新前的说明已原字节保存于[导航历史](01_project/governance/WORKSPACE_ORGANIZATION_20260921/navigation_history/)。历史文中的相对路径仍按其原目录解释。
'''
(ROOT/'PROJECT_MAP.md').write_text(project_map,encoding='utf-8')
for domain in domains:
    path=ROOT/domain/'README.md'
    content=path.read_text(encoding='utf-8')
    content=re.sub(r'<!-- WORKSPACE_NAV_START -->.*?<!-- WORKSPACE_NAV_END -->\s*','',content,flags=re.S)
    banner=f'''<!-- WORKSPACE_NAV_START -->
**2026-09-21 目录整理入口：** [本域用途与归档总览](../01_project/governance/WORKSPACE_ORGANIZATION_20260921/WORKSPACE_INDEX.html?domain={domain}) · [全项目导航](../PROJECT_MAP.md)。历史来源和证据原位保留；本轮整理不改变设计或科学结论。
<!-- WORKSPACE_NAV_END -->

'''
    heading,sep,rest=content.partition('\n')
    path.write_text(heading+'\n\n'+banner+rest.lstrip('\n'),encoding='utf-8')
for r in backup_rows:
    r['sha256_after']=hashlib.sha256((ROOT/r['source']).read_bytes()).hexdigest()
(D/'NAVIGATION_CHANGES.json').write_text(json.dumps(backup_rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(backup/'README.md').write_text('# 导航修改前的原件\n\n本目录保存2026-09-21本轮导航更新前的9份说明，字节与原文一致。它们是历史存档，相对路径按其原位置解释；日常使用当前PROJECT_MAP和各域README。\n',encoding='utf-8')

with (D/'DIRECTORY_ROLES.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
with (D/'DIRECTORY_USAGE.csv').open(encoding='utf-8-sig',newline='') as f: sizes={r['path']:r for r in csv.DictReader(f)}
inv=json.loads((D/'INVENTORY_SUMMARY.json').read_text(encoding='utf-8'))
data=[]
for r in rows:
    size=sizes.get(r['path'],{})
    data.append({'path':r['path'],'depth':int(r['depth']),'domain':r['path'].split('/')[0],
        'role':r['primary_role'],'label':labels[r['primary_role']],'purpose':r['responsibility'],
        'files':int(size.get('files',0)),'bytes':int(size.get('bytes',0)),
        'exists':(ROOT/r['path']).exists(),'href':'../../../'+r['path']+'/'})
payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
role_options=''.join(f'<option value="{html.escape(k)}">{html.escape(v)}</option>' for k,v in labels.items())
domain_options=''.join(f'<option>{d}</option>' for d in domains)
html_text='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>项目全景与归档导航</title>
<style>body{font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif;color:#173245;background:#f2f5f7;margin:0}main{max-width:1260px;margin:auto;padding:30px}h1{font-size:28px;margin:0}h2{font-size:19px}a{color:#08638b;text-decoration:none}a:hover{text-decoration:underline}.muted{color:#567080}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:22px 0}.card,section{background:#fff;border:1px solid #d9e3e9;border-radius:10px;padding:18px}.card b{display:block;font-size:21px}.card small{color:#567080}.filters{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}input,select{font:inherit;border:1px solid #c1d1dc;border-radius:6px;padding:8px;background:#fff}input{flex:1;min-width:240px}.table{overflow:auto;max-height:620px}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #e0e8ec;text-align:left;padding:10px;vertical-align:top}th{position:sticky;top:0;background:#eaf2f6}.path{font:13px/1.6 ui-monospace,monospace;word-break:break-all;min-width:270px}.badge{white-space:nowrap;background:#edf3f6;border-radius:5px;padding:3px 7px}.current{background:#ddf4e9;color:#166544}.note{border-left:4px solid #3591ac;padding:8px 14px;background:#eaf4f7}.small{font-size:13px}footer{margin:20px 0;color:#567080}</style>
<main><h1>项目全景与归档导航</h1><p class="muted">2026-09-21 · 现行设计、来源依赖、研究模块和历史记录分栏查看。逻辑归档保持原路径；实际删除与搬移另有回执。</p>
<div class="cards"><div class="card"><b><a href="../../../20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md">四系统硬件设计</a></b><small>机械 · 电气线束 · 能源热控 · 推进</small></div><div class="card"><b><a href="../../../20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM">R6H原总装</a></b><small>后续集成版本保留，WP03是上游来源</small></div><div class="card"><b><a href="../../../10_research/README.md">研究与计算模块</a></b><small><a href="../../../30_simulation/README.md">模型、程序及原始结果</a></small></div><div class="card"><b><a href="README.md">本次整理记录</a></b><small>精确删除 · 归档映射 · 保留与未覆盖项</small></div></div>
<p class="note">清理前可读快照：__FILES__个文件，约__GB__ GB，其中根Git约__GITGB__ GB。__ERRORS__个目录仍访问受限，因此体积为可读下限。目录角色不是整树删除清单。</p>
<section><h2>目录用途与责任</h2><div class="filters"><input id="q" placeholder="搜索目录、用途，例如 R6H、热控、Gate"><select id="domain"><option value="">全部业务域与本机配置</option>__DOMAIN_OPTIONS__</select><select id="role"><option value="">全部用途</option>__ROLE_OPTIONS__</select><select id="depth"><option value="">两层目录</option><option value="1">仅顶层</option><option value="2">仅第二层</option></select></div><p id="count" class="small muted"></p><div class="table"><table><thead><tr><th>目录 / 入口</th><th>用途类别</th><th>责任及保存范围</th><th>清理前体积</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section style="margin-top:18px"><h2>维护方式</h2><p>新业务资产继续放入八个域。现行设计通过指针与主入口定位；被引用的旧版本保留原位。历史结果与失败证据按日期和对象归档。只有经逐文件确认的可再生缓存、无绑定重复副本进入清理清单。</p><p><a href="ARCHIVE_PLAN.md">详细归档计划</a> · <a href="DIRECTORY_ROLES.csv">172项目录分类快照</a> · <a href="LARGE_FILES_CURRENT.csv">大文件清单</a> · <a href="../../../PROJECT_MAP.md">返回根导航</a></p></section><footer>此页离线运行，不加载外部脚本。目录链接用于本机或提供目录浏览的本地服务；原生CAD请用对应软件打开。保存规则不升级工程或科学结论。</footer></main>
<script>const data=__DATA__;const $=id=>document.getElementById(id);const initial=new URLSearchParams(location.search).get('domain');if(initial)$('domain').value=initial;function size(n){return n>=1e9?(n/1e9).toFixed(2)+' GB':n>=1e6?(n/1e6).toFixed(1)+' MB':n>=1000?(n/1000).toFixed(1)+' KB':n+' B'}function render(){let q=$('q').value.trim().toLowerCase(),dom=$('domain').value,role=$('role').value,depth=$('depth').value;let filtered=data.filter(r=>(!q||(r.path+' '+r.purpose+' '+r.label).toLowerCase().includes(q))&&(!dom||r.domain===dom)&&(!role||r.role===role)&&(!depth||r.depth===Number(depth)));$('count').textContent='显示 '+filtered.length+' / '+data.length+' 个目录记录；已删除的空容器保留动作标识。';$('rows').replaceChildren();for(let r of filtered){let tr=document.createElement('tr'),a=document.createElement(r.exists&&!r.path.startsWith('.')?'a':'span'),cell=document.createElement('td');a.textContent=r.path+(r.exists?'':'（空容器已移除）');if(a.tagName==='A')a.href=r.href;cell.className='path';cell.append(a);tr.append(cell);cell=document.createElement('td');let tag=document.createElement('span');tag.className='badge'+(r.role==='CURRENT_DESIGN'?' current':'');tag.textContent=r.label;cell.append(tag);tr.append(cell);cell=document.createElement('td');cell.textContent=r.purpose;tr.append(cell);cell=document.createElement('td');cell.textContent=size(r.bytes)+' / '+r.files+'文件';tr.append(cell);$('rows').append(tr)}}for(let id of ['q','domain','role','depth'])$(id).addEventListener('input',render);render();</script></html>'''
replacements={'__DATA__':payload,'__ROLE_OPTIONS__':role_options,'__DOMAIN_OPTIONS__':domain_options,
              '__FILES__':f"{inv['files']:,}",'__GB__':f"{inv['bytes']/1e9:.2f}",'__GITGB__':f"{inv['root_git_bytes']/1e9:.2f}",'__ERRORS__':str(len(inv['errors']))}
for key,value in replacements.items(): html_text=html_text.replace(key,value)
(D/'WORKSPACE_INDEX.html').write_text(html_text,encoding='utf-8')
print(json.dumps({'navigation_backups':len(backup_rows),'domains_updated':len(domains),'indexed_directory_rows':len(data),'currently_existing':sum(r['exists'] for r in data)},ensure_ascii=False))
