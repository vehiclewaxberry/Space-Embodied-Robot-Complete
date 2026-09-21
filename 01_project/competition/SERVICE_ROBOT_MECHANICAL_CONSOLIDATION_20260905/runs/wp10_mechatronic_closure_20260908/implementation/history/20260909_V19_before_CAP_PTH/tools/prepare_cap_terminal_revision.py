"""Archive V16 before terminal-board edits; persist the engineering brief."""
from pathlib import Path
import json, hashlib, shutil, datetime
A=Path(__file__).resolve().parents[1]
H=A/'history/20260909_V16_before_cap_terminal'
if H.exists():
    raise SystemExit('Archive already exists: do not overwrite')
H.mkdir(parents=True)
rows=[]
for folder in ['ecad','power','results','tools','mechanical','docs/hardware']:
    for p in sorted((A/folder).rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        # Generated BRep/render packages remain in the previous sealed ZIP;
        # preserve all direct mechanical sources, STEP and parameter contracts.
        if folder=='mechanical' and len(p.relative_to(A/folder).parts)>1:continue
        rel=p.relative_to(A);target=H/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
        rows.append(dict(path=rel.as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
for name in ['README.md','REVIEW.html','SYSTEM_CLOSURE_MATRIX.csv']:
    p=A/name
    if p.exists():
        shutil.copy2(p,H/name);rows.append(dict(path=name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(H/'ARCHIVE_SHA256.json').write_text(json.dumps(dict(time=datetime.datetime.now().astimezone().isoformat(),files=rows),indent=2),encoding='utf-8')
brief='''# C203 端接板 V17 设计输入

在现有 965 源装配候选内修订 C203_PCB，保留 873 / 99 父本与原 37 行闭环表。C203 电气型号不变，不引入第二只电容或虚构采购连接器。板为 50 × 48 × 1.6 mm 完成厚度；S 坐标 x=-7..-5.4，y=-25..25，z=-74..-26；组件面 x=-7，背面 x=-5.4。cap_local_to_S 沿用现有右手矩阵。

电容脚孔 local(-5,0)/(5,0)，孔径 2 mm。外接线焊孔改为 local(-14,14)/(14,14)，候选成品孔径 1.8 mm，焊盘外径 3.5 mm；后者距最大 Ø31 电容侧面投影约 2.55 mm，也处于 carrier 的 33 × 33 mm 开窗内。四个 Ø3.4 mm 安装孔、外轮廓、定位及其他 964 实例的 STEP 不变。

审阅发现原拟双面板与 Chemi-Con E1001A 2026 第 2 页的安装限制冲突，停止采用。改为只有 B.Cu 导体的候选：组件/密封侧无铜迹和焊盘；B.Cu 每网一条 4 mm 宽走线，从电容自有端接至外围线端。必须检查实际原生层、成品孔/铜环工艺及原厂安装语义；无法由公共材料证明的部分仍开放，不以 DRC 消除这项限制。候选铜厚 70 µm，属于项目参数而非原厂热额定承诺。

优先评估 TE 55A0111-18-9，18 AWG，19/30 股；导体直径上界 1.2446 mm，成品绝缘外径上界 1.5748 mm，20°C 电阻上界 0.02043963255 Ω/m。热浸/冷弯试验芯棒不是安装最小弯曲半径。线缆主要承担 C203 的充电和纹波电流，不把整条 20 A 主支路电流自动赋给并联电容引线。实际至 CHB 的端接、保持、长度、L/R 及故障热积累另需证据。

实际修改需产出 KiCad 原生板、铜层/孔位核验、板上独立连通性检查、STEP 几何、检查截图以及同版本绑定。重复同号焊盘必须额外验证铜迹连续，不能使用器件内部等电位假设把断迹视为通过。只对确已通过的局部范围记账；CHB 端接、轴向保持、热环境和整机详细设计状态继续由原表逐项裁决。

CAD 字体故障另以项目私有启动器处理：跳过已经识别且哈希绑定的非 SFNT 文件，只作用于 build123d.text 的系统字体枚举，不删除字体、不修改全局 Python 或技能源码。必须实际导入、生成和截图验证。
'''
(A/'docs/hardware/C203_TERMINAL_DESIGN_BRIEF_V17.md').write_text(brief,encoding='utf-8')
print(json.dumps(dict(archived=len(rows),bytes=sum(r['bytes'] for r in rows))))
