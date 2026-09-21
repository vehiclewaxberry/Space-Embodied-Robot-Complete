from pathlib import Path
import json,html
F=Path(__file__).resolve().parents[1];em=json.loads((F/'results/PORTS_EMISSION.json').read_text())
lines=['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1050" viewBox="0 0 1500 1050"><rect width="1500" height="1050" fill="white"/><style>text{font-family:Microsoft YaHei,Arial;fill:#152d43} .t{font-size:19px}.s{font-size:16px}.dim{stroke:#36617d;stroke-width:1.4;fill:none}.metal{fill:#dbe4eb;stroke:#20384c;stroke-width:2}</style>', '<text x="50" y="55" font-size="29" font-weight="700">WP09F 前盖电缆入口增量尺寸图</text>','<text x="50" y="88" class="t">S 系 / mm · 地面可拆配置候选 · 安装孔位置图，非加工放行图</text>']
def text(x,y,s,cls='t'):lines.append(f'<text x="{x}" y="{y}" class="{cls}">{html.escape(s)}</text>')
def line(x1,y1,x2,y2,dash=False):lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="dim" '+('stroke-dasharray="8 4"' if dash else '')+'/>')
# Looking inward along -X: plotted +Y to the right and +Z up. Sketch convention explicitly stated.
cx,cy,scale=365,430,2.25
px=lambda y:cx+y*scale
py=lambda z:cy-z*scale
lines.append(f'<rect x="{px(-107)}" y="{py(107)}" width="481.5" height="481.5" class="metal"/>')
line(px(-125),cy,px(125),cy,True);line(cx,py(-125),cx,py(125),True)
text(px(118),cy-8,'+Y','s');text(cx+8,py(117),'+Z','s')
for tag,y,z,od in em['locations']:
 x,v=px(y),py(z);lines.append(f'<circle cx="{x}" cy="{v}" r="{8.1*scale}" fill="white" stroke="#db662e" stroke-width="3"/>');line(x-27,v,x+27,v,True);line(x,v-27,x,v+27,True)
 text(x-80,v-40,tag+' / Ø16.2','s');line(cx,py(z),x,py(z),True);text((cx+x)/2-20,py(z)+23,str(y),'s');text(x+26,(cy+v)/2,str(z),'s')
line(px(-107),py(-124),px(107),py(-124));line(px(-107),py(-110),px(-107),py(-130));line(px(107),py(-110),px(107),py(-130));text(cx-20,py(-140),'214')
text(130,790,'正视位置约定：从 +X 看向盖板，+Y 向右、+Z 向上。','s')
text(130,820,'原有外形、紧固孔及倒角继承父版 STEP；本图仅显示新增两孔。','s')
text(130,850,'前盖 X = 183…185；板厚 2；孔轴均沿 X。','s')
text(760,165,'安装叠层示意（放大示意，非比例）')
lines.append('<rect x="990" y="225" width="25" height="250" class="metal"/><rect x="940" y="285" width="50" height="130" fill="#768794" stroke="#233f52"/><rect x="920" y="320" width="95" height="60" fill="#adbbc5" stroke="#233f52"/><rect x="1015" y="295" width="290" height="110" fill="#526775" stroke="#233f52"/>')
line(850,350,1380,350,True);text(1330,340,'+X')
text(800,225,'舱内侧');text(1190,225,'地面电缆侧')
text(765,520,'螺纹段：X 177…185，名义 M16×1.5 / L=8','s')
text(765,550,'锁紧螺母：X 179…183，厚度 4 为设计假设','s')
text(765,580,'本体：X 185…211；总长 34；扳手口 AF19','s')
text(765,610,'锁母 AF22；几何用外接圆包络，未建内螺纹/密封','s')
text(765,650,'料号：LAPP 53111010 + 53119010，各 2 件','s')
text(765,680,'名义夹持 4…10；PWR 电缆 Ø7.5，RS-422 Ø5','s')
text(765,710,'2 mm 未分配螺纹长度不能当作锁固/啮合验收通过','s')
text(765,765,'机械载荷路径：护套 → 填料函 → 前盖 → 原有螺栓 → 框架','s')
text(765,795,'先穿未端接电缆，再锁内侧螺母，最后装前盖。','s')
text(765,825,'电缆压紧力、垫圈厚度、扭矩与拉脱强度待实物验证。','s')
lines.extend(['<line x1="50" y1="905" x2="1450" y2="905" stroke="#23485f"/>'])
text(50,938,'孔位置：PWR (Y,Z)=(+70,+55)；RS-422=(−70,−55)。径向孔余量为名义值，未分配公差。','s')
text(50,968,'更改原因：旧 PWR (−70,+55) 与导航相机干涉。修订后仅声明本轮三态新增范围零实体交叠。','s')
text(50,998,'原型范围：非承压/非飞行接口；接插件穿过孔洞、工具轨迹、前盖连续拆装与强度尚未验证。','s')
lines.append('</svg>');(F/'candidate/PORT_DIMENSION_DRAWING.svg').write_text('\n'.join(lines),encoding='utf-8')
archive=F/'candidate/rejected_camera_overlap'
mapping=[]
for n in ['EMISSION.json','CHECK.json']:
 if (archive/n).exists():mapping.append(dict(receipt=n,note='Receipt paths originally point to active candidate paths; archived same-name parts hold rejected hashes. Do not resolve original active paths as rejected geometry.'))
(archive/'ARCHIVE_NOTE.json').write_text(json.dumps(dict(status='REJECTED_CAMERA_OVERLAP_NOT_CURRENT',old_PWR_yz_mm=[-70,55],current_PWR_yz_mm=[70,55],path_mapping='old candidate/parts/<name> -> this directory/parts/<name>; old candidate/functional_ports.py -> this directory/functional_ports.py; verify actual archive layout before use',receipts=mapping),ensure_ascii=False,indent=2),encoding='utf-8')
