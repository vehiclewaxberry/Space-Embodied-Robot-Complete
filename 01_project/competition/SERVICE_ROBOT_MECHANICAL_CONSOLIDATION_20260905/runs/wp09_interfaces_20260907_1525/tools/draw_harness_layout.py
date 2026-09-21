"""Deterministic projections of emitted centerlines; engineering review drawing, not cut-wire release."""
from pathlib import Path
import json,math,html
R=Path(__file__).resolve().parents[1]
e=json.loads((R/'results/EMISSION_V6.json').read_text());c=json.loads((R/'inputs/INTEGRATION_HARNESS_CONTRACT_V6.json').read_text())
def sample(p):
    pts=p['waypoints'];r=p['radius_mm'];out=[pts[0]]
    for i,arc in enumerate(e['routes'][next(k for k,v in c['routes'].items() if v==p)]['arcs']):
        center=arc['center'];start=arc['start'];end=arc['end'];u=[(start[j]-center[j])/r for j in range(3)];v=[(end[j]-center[j])/r for j in range(3)];out.append(start)
        for t in range(1,33):
            ang=t*math.pi/64;out.append([center[j]+r*(u[j]*math.cos(ang)+v[j]*math.sin(ang)) for j in range(3)])
    out.append(pts[-1]);return out
S=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="950" viewBox="0 0 1400 950"><rect width="1400" height="950" fill="white"/><g font-family="Microsoft YaHei, sans-serif" fill="#183045">', '<text x="50" y="45" font-size="27">WP09 — 推进静态线束布置 / V6</text>', '<text x="50" y="76" font-size="16">S 世界坐标，单位 mm；端点为 ICD 交接截面，未绑定设备连接器；不得据此裁线或上电。</text>']
for title,axes,ybase in [('俯视 X–Y', (0,1),350),('侧视 X–Z',(0,2),680)]:
    S.append(f'<text x="50" y="{ybase-(205 if axes==(0,2) else 235)}" font-size="21">{title}</text>')
    for xx in range(-180,181,20):
        x=570+xx*2.7;S.append(f'<path d="M{x},{ybase-210} V{ybase+65}" stroke="#e7edf3"/><text x="{x}" y="{ybase+90}" font-size="11">{xx}</text>')
    for k,p in c['routes'].items():
        points=sample(p);xy=[(570+pt[axes[0]]*2.7,ybase-pt[axes[1]]*2.7) for pt in points];path=' '.join(('M' if n==0 else 'L')+f'{x:.4f},{y:.4f}' for n,(x,y) in enumerate(xy));color='#d87505' if 'PWR' in k else '#087bc1'
        S.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="6"/>')
        for n,pt in enumerate((points[0],points[-1])):
            x=570+pt[axes[0]]*2.7;y=ybase-pt[axes[1]]*2.7;tx=x+12;tag=('P' if 'PWR' in k else 'D')+str(n+1)
            S.append(f'<circle cx="{x}" cy="{y}" r="6" fill="white" stroke="{color}" stroke-width="2"/><text x="{tx}" y="{y-10 if n==0 else y+8}" font-size="14">{tag}</text>')
    if axes==(0,1):
        for x,y in c['feedthrough_xy']:
            S.append(f'<circle cx="{570+x*2.7}" cy="{ybase-y*2.7}" r="12.42" fill="none" stroke="#394957" stroke-dasharray="4 2"/>')
S.extend(['<text x="1060" y="130" font-size="18">名义几何</text>','<text x="1060" y="165" font-size="15">线束外径：6 mm（待实物）</text>','<text x="1060" y="195" font-size="15">中心线弯曲半径：21 mm</text>','<text x="1060" y="225" font-size="15">内侧名义半径：18 mm</text>','<text x="1060" y="265" font-size="15">PWR：316.9734 mm</text>','<text x="1060" y="295" font-size="15">DATA：204.9734 mm</text>','<text x="1060" y="335" font-size="15">末端余量 / 裁线长度：未知</text>','<text x="1060" y="375" font-size="15">穿舱孔：2 × Ø9.2</text>','<text x="1060" y="405" font-size="15">护线套通孔：Ø8</text>','<text x="50" y="925" font-size="15">几何与机械支撑候选；NASA 类别筛查不等于电缆工艺验收。细节见 From-To.csv 和预制检验单。</text>','</g></svg>'])
(R/'docs/HARNESS_LAYOUT_S_WORLD.svg').write_text('\n'.join(S),encoding='utf-8')
svg=(R/'docs/HARNESS_LAYOUT_S_WORLD.svg').read_text()
labels=''.join(f'<text x="1060" y="{460+i*30}" font-size="15">{s}</text>' for i,s in enumerate(['P1 = (-60, 69, 45)','P2 = (144, 48, -65)','D1 = (78, -15, 45)','D2 = (140, 56, -45)']))
(R/'docs/HARNESS_LAYOUT_S_WORLD.svg').write_text(svg.replace('</g></svg>',labels+'</g></svg>'),encoding='utf-8')
